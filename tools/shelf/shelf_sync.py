#!/usr/bin/env python3
"""
Book Club shelf sync. Runs on the club computer every 2 minutes (systemd timer,
set up by install.sh) and publishes which books are issued, so the website
catalogue can show live shelf status.

It reads Koha's database through a read-only login that can see only a few
columns of the item and title tables (never members or loans history), and
publishes two files to the "status" branch of the shelf repository:

    status.json  {"v":1,"updated":"…","out":{"<biblionumber>":[copies, issued, "earliest due"]}}
                 (only titles with at least one copy issued)
    books.json   {"v":1,"books":[[biblionumber,"title","author","isbn",copies,"genre code"], …]}
                 The genre code is the letters at the start of the barcode (FIC, BN, …),
                 which the website turns into a genre; barcodes themselves are not published.

Nothing is sent when nothing has changed. Each update replaces the previous one
(no history is kept), then GitHub is asked to publish the files on GitHub Pages.

    python3 shelf_sync.py              normal run (what the timer does)
    python3 shelf_sync.py --dry-run    read Koha and print a summary; send nothing
    python3 shelf_sync.py --force      send even if nothing changed

Settings are read from /etc/bookclub-shelf/config.json (or $SHELF_CONFIG).
"""
import base64
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

CONFIG = os.environ.get("SHELF_CONFIG", "/etc/bookclub-shelf/config.json")
DEFAULTS = {
    "api": "https://api.github.com",
    "branch": "status",
    "mysql": "mysql",
    "mysql_defaults": "/etc/bookclub-shelf/my.cnf",
    "token_file": "/etc/bookclub-shelf/token",
    "state_dir": "/var/lib/bookclub-shelf",
}

# Lost and withdrawn copies are not on the shelves, so they are left out.
STATUS_SQL = """
SELECT biblionumber, COUNT(itemnumber), SUM(onloan IS NOT NULL), IFNULL(MIN(onloan), '')
FROM items
WHERE IFNULL(itemlost, 0) = 0 AND IFNULL(withdrawn, 0) = 0
GROUP BY biblionumber
HAVING SUM(onloan IS NOT NULL) > 0
"""
BOOKS_SQL = """
SELECT b.biblionumber, IFNULL(b.title, ''), IFNULL(b.author, ''),
       IFNULL((SELECT bi.isbn FROM biblioitems bi WHERE bi.biblionumber = b.biblionumber LIMIT 1), ''),
       COUNT(i.itemnumber), IFNULL(MIN(i.barcode), '')
FROM biblio b JOIN items i ON i.biblionumber = b.biblionumber
WHERE IFNULL(i.itemlost, 0) = 0 AND IFNULL(i.withdrawn, 0) = 0
GROUP BY b.biblionumber, b.title, b.author
ORDER BY b.biblionumber
"""
FIREWALL_HINT = "Is the IITK firewall login active on this computer? It will retry in 2 minutes."
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


# ---------------------------------------------------------------- Koha
def query(cfg, sql):
    """Run a SELECT through the mysql client and return rows of strings."""
    cmd = [cfg["mysql"], "--defaults-extra-file=" + cfg["mysql_defaults"], "--batch", "--skip-column-names",
           "--default-character-set=utf8mb4", "-e", sql, cfg["database"]]
    res = subprocess.run(cmd, capture_output=True, timeout=120)
    if res.returncode:
        raise RuntimeError("database query failed: " + res.stderr.decode("utf-8", "replace").strip())
    # Batch mode escapes tab, newline, NUL and backslash inside values.
    unescape = lambda s: re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "0": "\0"}.get(m.group(1), m.group(1)), s)
    lines = res.stdout.decode("utf-8", "replace").split("\n")
    return [[unescape(v) for v in line.split("\t")] for line in lines if line]


def clean(s):
    # Koha keeps catalogue punctuation such as "Title /" and "Author,".
    return " ".join(s.split()).rstrip(" /:;,=").strip()


def read_koha(cfg):
    out = {}
    for bn, copies, issued, due in query(cfg, STATUS_SQL):
        out[str(int(bn))] = [int(copies), int(float(issued)), due[:10] if re.match(r"\d{4}-\d\d-\d\d", due) else ""]
    books = []
    for bn, title, author, isbn, copies, barcode in query(cfg, BOOKS_SQL):
        isbn = re.sub(r"[^0-9Xx]", "", re.split(r"[|\s(]", isbn.strip() + " ")[0])
        code = re.match(r"[A-Za-z]*", barcode.strip()).group().upper()[:12]
        books.append([int(bn), clean(title), clean(author), isbn, int(copies), code])
    return out, books


# ---------------------------------------------------------------- GitHub
def api(cfg, token, method, path, body=None):
    req = urllib.request.Request(
        cfg["api"].rstrip("/") + "/repos/" + cfg["repo"] + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "bookclub-shelf-sync",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"GitHub {method} {path} failed: HTTP {e.code} {detail}") from None
    except OSError as e:
        raise RuntimeError(f"cannot reach GitHub ({e}). {FIREWALL_HINT}") from None
    try:
        return json.loads(data) if data else {}
    except ValueError:
        raise RuntimeError(f"unexpected reply instead of GitHub's. {FIREWALL_HINT}") from None


def git_blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def publish(cfg, token, files, state):
    """Replace the status branch with a single commit holding `files`, then trigger the Pages deploy."""
    tree = []
    for path, data in files.items():
        sha = git_blob_sha(data)
        if state.get("blobs", {}).get(path) == sha:
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": sha})   # unchanged: reuse
        else:
            blob = api(cfg, token, "POST", "/git/blobs", {"content": base64.b64encode(data).decode(), "encoding": "base64"})
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree_sha = api(cfg, token, "POST", "/git/trees", {"tree": tree})["sha"]
    commit = api(cfg, token, "POST", "/git/commits", {"message": "Shelf status", "tree": tree_sha, "parents": []})
    try:
        api(cfg, token, "PATCH", "/git/refs/heads/" + cfg["branch"], {"sha": commit["sha"], "force": True})
    except RuntimeError as e:
        if "HTTP 422" not in str(e) and "HTTP 404" not in str(e):
            raise
        api(cfg, token, "POST", "/git/refs", {"ref": "refs/heads/" + cfg["branch"], "sha": commit["sha"]})
    api(cfg, token, "POST", "/dispatches", {"event_type": "shelf-updated"})
    return {path: entry["sha"] for path, entry in zip(files, tree)}


# ---------------------------------------------------------------- main
def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def main():
    args = set(sys.argv[1:])
    if args - {"--dry-run", "--force"}:
        sys.exit(__doc__)
    cfg = dict(DEFAULTS)
    with open(CONFIG, encoding="utf-8") as fh:
        cfg.update(json.load(fh))

    out, books = read_koha(cfg)
    issued = sum(v[1] for v in out.values())
    if "--dry-run" in args:
        print(f"Koha: {len(books)} titles, {sum(b[4] for b in books)} copies, {issued} copies issued "
              f"({len(out)} titles). Example: {books[0] if books else '-'}")
        return

    # Compare without the timestamp, so an unchanged shelf sends nothing.
    status_core, books_data = dumps({"v": 1, "out": out}), dumps({"v": 1, "books": books})
    digest = hashlib.sha256(status_core + b"\n" + books_data).hexdigest()
    state_path = os.path.join(cfg["state_dir"], "state.json")
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        state = {}
    if state.get("digest") == digest and "--force" not in args:
        return

    with open(cfg["token_file"], encoding="utf-8") as fh:
        token = fh.read().strip()
    updated = datetime.datetime.now(IST).replace(microsecond=0).isoformat()
    files = {"status.json": dumps({"v": 1, "updated": updated, "out": out}), "books.json": books_data}
    try:
        blobs = publish(cfg, token, files, state)
    except RuntimeError:
        if not state.get("blobs"):
            raise
        blobs = publish(cfg, token, files, {})       # a reused blob was missing: send everything
    state = {"digest": digest, "blobs": blobs, "sent": updated}
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, state_path)
    print(f"Sent: {issued} copies issued across {len(out)} titles; {len(books)} titles in Koha.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        sys.exit(f"shelf sync: {e}")
