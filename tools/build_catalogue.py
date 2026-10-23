#!/usr/bin/env python3
"""
Build the public catalogue file (data/catalogue.json) from Koha's book list.

    python3 tools/build_catalogue.py                              rebuild from data/koha_books.json
    python3 tools/build_catalogue.py --survey koha-info/koha-books.tsv
                                  first refresh data/koha_books.json from a club-computer survey
    python3 tools/build_catalogue.py --fetch https://…/books.json
                                  first refresh it from the shelf repository (the website build does this)

Inputs (all public, no member data, no barcodes):
  data/koha_books.json     Koha's titles: [record number, title, author, ISBN, copies, genre code, date added]
                           (the genre code is the letters at the start of the barcode, e.g. FIC, BN)
  content/genres.json      genre code → genre name (editable in the admin panel)
  data/book_details.json   extra details per Koha record number, carried over from the old catalogue:
                           t/a (display title/author), r (Goodreads rating), i (cover), d (description),
                           ds (where the description came from), og (old genre, used if the code is unknown)
  tools/enrichment_cache.json   descriptions and covers found by enrich_catalogue.py

Each catalogue entry is one title: {"k": [record numbers], "t", "a", "g", "n": copies, "ad": date added,
"r", "i", "d", "ds"}. The catalogue page uses "k" to show live shelf status.

With --fetch, the shelf repository's status.json is also read, and its "most borrowed this semester" list
is saved to data/popular.json for the home page (that file is not kept in the repository).
"""
import csv
import json
import os
import re
import sys
import urllib.parse
import urllib.request

from enrich_catalogue import is_english

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
KOHA = os.path.join(ROOT, "data", "koha_books.json")
DETAILS = os.path.join(ROOT, "data", "book_details.json")
GENRES = os.path.join(ROOT, "content", "genres.json")
CACHE = os.path.join(HERE, "enrichment_cache.json")
POPULAR = os.path.join(ROOT, "data", "popular.json")
OUT = os.path.join(ROOT, "data", "catalogue.json")

SMALL = set("a an and as at but by for from in into nor of on or over the to under upon via with "
            "ka ke ki ko se me mein aur".split())
# Roman numerals, initials (JM, R.L.) and short all-consonant abbreviations stay in capitals.
KEEP_UPPER = re.compile(r"^(?:(?=[IVXLC])C{0,3}(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})|[B-DF-HJ-NP-TV-XZ]{2,3}"
                        r"|[A-Z](?:\.[A-Z])+\.?|[A-Z]\.?)$")


# ---------------------------------------------------------------- helpers
def clean(s):
    return " ".join((s or "").split()).rstrip(" /:;,=").strip()


def smart_case(s):
    """Koha keeps most titles in capitals; show them in title case."""
    if not s or s != s.upper():
        return s
    words = s.split(" ")
    out = []
    for n, w in enumerate(words):
        core = re.sub(r"^\W+|\W+$", "", w)
        if n and core.lower() in SMALL and not out[-1].endswith(":"):
            out.append(w.lower())
        elif KEEP_UPPER.match(core) and core.upper() not in ("DR", "MR", "MRS", "MS", "ST", "JR", "SR"):
            out.append(w)
        else:
            out.append(re.sub(r"[A-Za-z][A-Za-z']*", lambda m: m.group()[0].upper() + m.group()[1:].lower(), w))
    return " ".join(out)


# Goodreads/publisher boilerplate at the start of some descriptions.
BOILER_PREFIX = re.compile(r"^(?:(?:An )?alternate covers?(?: edition)?[^.]{0,80}(?:here\.?|\b(?:\d{13}|\d{9}[\dX]|B0[0-9A-Z]{8}))"
                           r"|Also see: Alternate Cover Editions for this ISBN \[ACE\]\s*(?:ACE #\d+)?)\s*", re.I)
BOILER_WHOLE = re.compile(r"^(?:This work has been selected by scholars as being culturally important"
                          r"|Please note that the content of this book primarily consists of articles)", re.I)


def clean_description(d):
    d = BOILER_PREFIX.sub("", d or "").strip()
    d = re.sub(r"\[([^\]]+)\]\[\d+\]", r"\1", d)                    # [The Dark Tower][1]
    d = re.sub(r"\[([^\]]+)\]\((?:https?:)?[^)]*\)", r"\1", d)       # [text](link)
    d = re.sub(r"\s*\[\d+\](?::\s*\S+)?", "", d)                     # stray [1] and [1]: link
    d = re.sub(r"\*\*([^*]+)\*\*", r"\1", d)                          # **bold**
    d = re.sub(r"\*{2,}", " ", d)                                        # leftover *** rules
    d = " ".join(d.split())
    return "" if BOILER_WHOLE.match(d) or len(d) < 40 else d


def full_title(s):
    """Whole title (with subtitle, so series volumes stay apart), lower case, no punctuation or leading article."""
    s = re.sub(r"^(the|a|an)\s+", "", (s or "").lower().strip())
    return " ".join(re.findall(r"[a-z0-9\u0900-\u09ff]+", s))


def genre_for(code, table):
    """Longest known code at the start of the barcode letters (handles typos like GNOOOSAMA)."""
    best = ""
    for known in table:
        if code.startswith(known) and len(known) > len(best):
            best = known
    return table.get(best, "")


def is_test(row):
    return row[5].startswith("TEST") or re.fullmatch(r"test\s*\d*", row[1].strip(), re.I)


COVER_HOSTS = ("covers.openlibrary.org", "images.gr-assets.com", "books.google.com", "books.googleusercontent.com")


def cover_ok(url):
    parts = urllib.parse.urlsplit(url if isinstance(url, str) else "")
    return parts.scheme == "https" and parts.hostname in COVER_HOSTS and not parts.username and "@" not in parts.netloc


# ---------------------------------------------------------------- refreshing Koha's list
def valid_books(rows):
    """Rows of [record number, title, author, ISBN, copies, genre code, date added]; older lists lack the date.
    The list comes from the club computer, so anything unexpected rejects the whole list."""
    ok = isinstance(rows, list) and all(
        isinstance(r, list) and len(r) in (6, 7)
        and type(r[0]) is int and 0 < r[0] < 10**9 and type(r[4]) is int and 0 <= r[4] < 10000
        and all(isinstance(v, str) for v in r[1:4] + r[5:])
        and len(r[1]) <= 500 and len(r[2]) <= 300 and len(r[3]) <= 40
        and re.fullmatch(r"[A-Za-z]{0,12}", r[5]) and (len(r) == 6 or re.fullmatch(r"(\d{4}-\d\d-\d\d)?", r[6]))
        for r in rows)
    if not ok or not 100 <= len(rows) <= 100000:
        raise ValueError("Koha's book list looks wrong")
    return [r + [""] * (7 - len(r)) for r in rows]


def read_json(url, limit):
    req = urllib.request.Request(url, headers={"User-Agent": "bookclub-website-build"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"larger than {limit // (1024 * 1024)} MB")
    return json.loads(raw)


def keep_dates(rows):
    """A list without dates (from an older club-computer program) keeps the dates already known."""
    if all(r[6] for r in rows) or not os.path.exists(KOHA):
        return rows
    known = {r[0]: r[6] for r in valid_books(json.load(open(KOHA, encoding="utf-8"))["books"]) if r[6]}
    return [r[:6] + [r[6] or known.get(r[0], "")] for r in rows]


def save_popular(status_url):
    """The "most borrowed this semester" list from the shelf status, for the home page."""
    try:
        pop = read_json(status_url, 5 * 1024 * 1024).get("popular") or {}
        top = [[int(bn), min(max(int(n), 0), 10000)] for bn, n in pop.get("top", [])[:30]]
        since = str(pop.get("since", ""))
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", since):
            raise ValueError("no popular list yet")
    except (OSError, ValueError, TypeError, AttributeError) as e:
        print(f"No 'most borrowed' list ({e}).")
        return
    with open(POPULAR, "w", encoding="utf-8") as fh:
        json.dump({"since": since, "top": top}, fh)
    print(f"Saved data/popular.json: {len(top)} titles borrowed since {since}")


def from_survey(path):
    """One line per copy (from tools/shelf/koha_info.sh) → one row per Koha record."""
    recs = {}
    # The survey writes mysql batch output, which escapes tabs, newlines and backslashes inside values.
    unescape = lambda v: re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "0": ""}.get(m.group(1), m.group(1)), v or "")
    for r in csv.DictReader(open(path, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE):
        r = {k: unescape(v) for k, v in r.items()}
        if r.get("lost", "0") not in ("0", "") or r.get("withdrawn", "0") not in ("0", ""):
            continue
        bn = int(r["biblionumber"])
        rec = recs.setdefault(bn, {"t": clean(r["title"]), "a": clean(r["author"]), "isbn": r["isbn"], "n": 0, "bc": [], "ad": ""})
        rec["n"] += 1
        added = (r.get("added") or "")[:10]
        if re.fullmatch(r"\d{4}-\d\d-\d\d", added) and added > rec["ad"]:
            rec["ad"] = added
        if r["barcode"].strip():
            rec["bc"].append(r["barcode"].strip())
    rows = []
    for bn, rec in sorted(recs.items()):
        isbn = re.sub(r"[^0-9Xx]", "", re.split(r"[|\s(]", rec["isbn"].strip() + " ")[0])
        code = re.match(r"[A-Za-z]*", min(rec["bc"]) if rec["bc"] else "").group().upper()[:12]
        rows.append([bn, rec["t"], rec["a"], isbn, rec["n"], code, rec["ad"]])
    return rows


def fetch(url):
    data = read_json(url, 30 * 1024 * 1024)
    return data.get("books") if isinstance(data, dict) and data.get("v") == 1 else None


def not_shrunk(rows):
    """Refuse a list that suddenly lost many books (a fault or tampering on the club computer)."""
    if os.path.exists(KOHA):
        before = len(json.load(open(KOHA, encoding="utf-8"))["books"])
        if len(rows) < before * 0.8:
            raise ValueError(f"it has {len(rows)} records, down from {before}; check Koha before accepting it")
    return rows


# ---------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    if args[:1] == ["--survey"] and len(args) == 2:
        try:
            rows = valid_books(from_survey(args[1]))
        except (OSError, ValueError, KeyError) as e:
            sys.exit(f"Could not read the survey ({e}); data/koha_books.json left unchanged.")
    elif args[:1] == ["--fetch"] and len(args) == 2:
        try:
            rows = not_shrunk(keep_dates(valid_books(fetch(args[1]))))
        except (OSError, ValueError) as e:
            print(f"Could not fetch Koha's book list ({e}); using data/koha_books.json as it is.")
            rows = None
        if args[1].endswith("/books.json"):
            save_popular(args[1][: -len("books.json")] + "status.json")
    elif not args:
        rows = None
    else:
        sys.exit(__doc__)
    if rows is not None:
        with open(KOHA, "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "books": rows}, fh, ensure_ascii=False, separators=(",", ":"))
        print(f"Updated data/koha_books.json: {len(rows)} Koha records")

    books = valid_books(json.load(open(KOHA, encoding="utf-8"))["books"])
    details = json.load(open(DETAILS, encoding="utf-8")) if os.path.exists(DETAILS) else {}
    table = {g["code"].strip().upper(): g["genre"].strip()
             for g in json.load(open(GENRES, encoding="utf-8")).get("codes", []) if g.get("code") and g.get("genre")}
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

    entries = {}
    for row in books:
        if is_test(row):
            continue
        bn, title, author, _isbn, copies, code, added = row
        extra = details.get(str(bn), {})
        b = {"k": [bn], "t": extra.get("t") or smart_case(title), "a": extra.get("a") or smart_case(author), "n": copies}
        if added:
            b["ad"] = added
        g = genre_for(code, table) or extra.get("og", "")
        if g:
            b["g"] = g
        for f in ("r", "i", "d", "ds"):
            if extra.get(f):
                b[f] = extra[f]
        if "d" in b:
            b["d"] = clean_description(b["d"])
            if not b["d"]:
                del b["d"]
                b.pop("ds", None)
        # The same book catalogued twice in Koha becomes one entry.
        key = full_title(b["t"]) + "|" + " ".join(sorted(re.findall(r"[a-z]{2,}", b["a"].lower())))
        if key in entries:
            e = entries[key]
            e["k"].append(bn)
            e["n"] += copies
            if added > e.get("ad", ""):
                e["ad"] = added
            for f in ("g", "r", "i", "d", "ds"):
                if f in b and f not in e:
                    e[f] = b[f]
        else:
            entries[key] = b

    enriched = 0
    for b in entries.values():
        hit = cache.get(b["t"].strip().lower() + "|" + b["a"].strip().lower(), {})
        for source in ("openlibrary", "google"):
            extra = hit.get(source) or {}
            if "d" not in b and clean_description(extra.get("d")) and is_english(extra["d"]):
                b["d"], b["ds"] = clean_description(extra["d"]), extra.get("src", "")
                enriched += 1
            if "i" not in b and extra.get("i"):
                b["i"] = extra["i"]

    out = sorted(entries.values(), key=lambda b: re.sub(r"^[^0-9a-z]+", "", b["t"].lower()))
    for b in out:
        b["k"].sort()
        # Text from Open Library / Google is shown escaped; covers and ratings are checked here as well.
        if "i" in b and not cover_ok(b["i"]):
            del b["i"]
        if "r" in b and not (type(b["r"]) in (int, float) and 0 <= b["r"] <= 5):
            del b["r"]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"Wrote {len(out)} titles ({sum(b['n'] for b in out)} copies) to data/catalogue.json"
          + (f"; {enriched} descriptions from Open Library / Google Books" if enriched else ""))
    unknown = sorted({r[5] for r in books if r[5] and not genre_for(r[5], table) and not is_test(r)})
    if unknown:
        print("Genre codes not in content/genres.json (add them in the admin panel): " + ", ".join(unknown))


if __name__ == "__main__":
    main()
