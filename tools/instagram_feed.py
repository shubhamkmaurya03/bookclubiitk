#!/usr/bin/env python3
"""
Keep the club's Instagram posts for the Blogs & Events page.

    python3 tools/instagram_feed.py

Reads @bookclub_iitk's posts through Instagram's official API (the Instagram account linked to the
club's Facebook Page), using the Page token in the environment variable INSTAGRAM_PAGE_TOKEN (a
GitHub secret, given only to this step) and "instagram_id" in content/instagram.json. Without the
token, or if Instagram refuses it, the Behold feed in content/instagram.json is used instead
(behold.so: the 6 newest posts, refreshed daily).

Each new post is added to data/instagram.json, with a copy of its picture in assets/instagram/.
Posts already saved are kept, up to "max_posts" (the newest are kept). Posts listed under "hidden"
in content/instagram.json (by their Instagram link) are removed, picture included.

The website build runs this every 3 hours (.github/workflows/publish.yml). If nothing can be
read, nothing changes. The token is sent only in a request header and is never printed.
"""
import datetime
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SETTINGS = os.path.join(ROOT, "content", "instagram.json")
DATA = os.path.join(ROOT, "data", "instagram.json")
PICS = os.path.join(ROOT, "assets", "instagram")
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
UA = {"User-Agent": "BookClubIITK-website/1.0"}
SIZE = 600            # pictures are saved as 600 x 600 JPEGs
FEED_HOSTS = ("feeds.behold.so",)
GRAPH = "https://graph.facebook.com/v25.0"    # Meta keeps each version about two years; older ones are upgraded
GRAPH_HOSTS = ("graph.facebook.com",)
GRAPH_FIELDS = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,children{media_type,media_url,thumbnail_url}"
PICTURE_HOSTS = ("behold.pictures", ".cdninstagram.com", ".fbcdn.net")   # where Behold serves pictures from
MAX_FEED = 2 * 1024 * 1024        # bytes
MAX_PICTURE = 15 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 40_000_000


def shortcode(url):
    """The post's code in its Instagram link (instagram.com/p/CODE/ or /reel/CODE/)."""
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|tv)/([A-Za-z0-9_-]+)", url or "")
    return m.group(1) if m else (url or "").strip()


def allowed(url, hosts):
    """Only https links to the listed hosts (a name starting with "." also allows its subdomains)."""
    parts = urllib.parse.urlsplit(url or "")
    if parts.username or parts.password or "@" in parts.netloc or "\\" in parts.netloc or "%" in parts.netloc:
        return False                      # no user-name part or tricks that hide the real server
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == h or (h.startswith(".") and host.endswith(h)) for h in hosts)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get(url, hosts, limit, timeout=60, token=None):
    if not allowed(url, hosts):
        raise ValueError(f"address not allowed: {url[:80]}")
    headers = dict(UA)
    if token:   # in a header (not the address), and never across a redirect
        headers["Authorization"] = "Bearer " + token
    opener = urllib.request.build_opener(NoRedirect) if token else urllib.request.build_opener()
    with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        if not allowed(r.geturl(), hosts):
            raise ValueError("redirected to another server")
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"larger than {limit // (1024 * 1024)} MB")
    return data


def prune_caption(text):
    """Drop the block of hashtags at the end of a caption (as Behold does)."""
    lines = (text or "").replace("\r", "").rstrip().split("\n")
    while lines and re.fullmatch(r"[\s.•·]*((#|@)[\w.]+[\s.,•·]*)*", lines[-1]):
        lines.pop()
    if lines:
        lines[-1] = re.sub(r"(\s+#[\w]+)+\s*$", "", lines[-1])
    return "\n".join(lines)


def clean_caption(text):
    text = re.sub(r"[ \t]+", " ", (text or "").replace("\r", ""))
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:900]


def save_picture(url, path):
    if not url:
        return False
    img = Image.open(io.BytesIO(get(url, PICTURE_HOSTS, MAX_PICTURE)), formats=["JPEG", "PNG", "WEBP"])
    if img.width * img.height > Image.MAX_IMAGE_PIXELS:
        raise ValueError("picture too large")
    img = img.convert("RGB")
    side = min(img.size)                                   # square, centred
    left, top = (img.width - side) // 2, (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((SIZE, SIZE), Image.LANCZOS)
    img.save(path, "JPEG", quality=82, optimize=True, progressive=True)   # no metadata is copied
    return True


def drop_picture(post):
    if re.fullmatch(r"assets/instagram/\d{5,30}\.jpg", post.get("image", "")):   # only our own saved pictures
        pic = os.path.join(ROOT, post["image"])
        if os.path.exists(pic):
            os.remove(pic)


# ---------------------------------------------------------------- the two sources, as one kind of record
def from_behold(feed_url):
    feed = json.loads(get(feed_url, FEED_HOSTS, MAX_FEED))
    if not isinstance(feed, dict):
        raise ValueError("not a feed")
    out = []
    for post in (feed.get("posts") if isinstance(feed.get("posts"), list) else [])[:50]:
        if not isinstance(post, dict):
            continue
        sizes = post.get("sizes") if isinstance(post.get("sizes"), dict) else {}
        size = sizes.get("medium") or sizes.get("large") or sizes.get("small") or {}
        pic = ((size.get("mediaUrl") if isinstance(size, dict) else "") or post.get("thumbnailUrl")
               or (post.get("mediaUrl") if post.get("mediaType") != "VIDEO" else ""))
        out.append({"id": post.get("id"), "permalink": post.get("permalink"), "timestamp": post.get("timestamp"),
                    "type": post.get("mediaType"), "caption": post.get("prunedCaption") or post.get("caption"),
                    "picture": pic})
    return out


def graph_picture(m):
    """An image for the card: the photo, a video's cover, or an album's first photo or cover."""
    if m.get("media_type") == "VIDEO":
        return m.get("thumbnail_url")
    if m.get("media_type") == "CAROUSEL_ALBUM":
        kids = (m.get("children") or {}).get("data") if isinstance(m.get("children"), dict) else None
        for k in kids if isinstance(kids, list) else []:
            if isinstance(k, dict):
                return k.get("thumbnail_url") if k.get("media_type") == "VIDEO" else k.get("media_url")
    return m.get("media_url")


def from_graph(ig_id, token, have, max_posts):
    """Newest first, page by page, until a page holds nothing new (or max_posts is reached)."""
    out, after = [], ""
    while len(out) < max_posts:
        url = f"{GRAPH}/{ig_id}/media?" + urllib.parse.urlencode(
            {"fields": GRAPH_FIELDS, "limit": 50, **({"after": after} if after else {})})
        try:
            page = json.loads(get(url, GRAPH_HOSTS, MAX_FEED, token=token))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read(4096)).get("error", {}).get("message", "")
            except Exception:
                msg = ""
            raise ValueError(f"HTTP {e.code} {msg[:200]}") from None
        items = page.get("data") if isinstance(page, dict) and isinstance(page.get("data"), list) else []
        for m in items:
            if isinstance(m, dict):
                out.append({"id": m.get("id"), "permalink": m.get("permalink"), "timestamp": m.get("timestamp"),
                            "type": m.get("media_type"), "caption": prune_caption(str(m.get("caption") or "")),
                            "picture": graph_picture(m)})
        cursor = ((page.get("paging") or {}).get("cursors") or {}).get("after") if isinstance(page, dict) else None
        if not items or not cursor or not (page.get("paging") or {}).get("next") \
                or all(str(m.get("id")) in have for m in items if isinstance(m, dict)):
            break
        after = str(cursor)
    return out[:max_posts]


def main():
    settings = json.load(open(SETTINGS, encoding="utf-8"))
    feed_url = (settings.get("feed") or "").strip()
    ig_id = str(settings.get("instagram_id") or "").strip()
    token = os.environ.get("INSTAGRAM_PAGE_TOKEN", "").strip()
    try:
        max_posts = min(max(int(settings.get("max_posts") or 60), 6), 500)
    except (TypeError, ValueError):
        max_posts = 60
    hidden = {shortcode(h) for h in settings.get("hidden") or [] if h}
    data = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else {"posts": []}
    saved = {p["id"]: p for p in data.get("posts", [])}
    changed = False

    posts = None
    if token and re.fullmatch(r"\d{5,30}", ig_id):
        try:
            posts = from_graph(ig_id, token, set(saved), max_posts)
            print(f"Instagram (official): {len(posts)} posts read.")
        except Exception as e:                          # expired or withdrawn token, network, Meta down
            # A GitHub "warning" line, so a broken connection shows in the Actions tab.
            print(f"::warning::Instagram's official connection failed ({e}); using Behold instead. "
                  "The Page token may need renewing (see the handbook, section 8).")
    elif token or ig_id:
        print("::warning::Instagram token or instagram_id missing; using Behold.")
    if posts is None and feed_url:
        try:
            posts = from_behold(feed_url)
            print(f"Behold: {len(posts)} posts read.")
        except Exception as e:                          # network, Behold down, bad JSON, wrong address
            print(f"Could not read the Instagram feed ({e}); keeping the saved posts.")
    if posts:
        os.makedirs(PICS, exist_ok=True)
        for post in posts:
            pid = str(post.get("id") or "")
            link = post.get("permalink") if isinstance(post.get("permalink"), str) else ""
            if not re.fullmatch(r"\d{5,30}", pid) or not re.fullmatch(r"https://www\.instagram\.com/[A-Za-z0-9_./-]{1,200}", link):
                continue
            if shortcode(link) in hidden:
                continue
            try:
                when = datetime.datetime.strptime(str(post.get("timestamp")), "%Y-%m-%dT%H:%M:%S%z").astimezone(IST)
            except ValueError:
                print(f"Skipped {link}: no valid date.")
                continue
            kind = {"VIDEO": "video", "CAROUSEL_ALBUM": "album"}.get(post.get("type"), "image")
            entry = {"id": pid, "url": link, "time": when.isoformat(), "type": kind,
                     "caption": clean_caption(str(post.get("caption") or "")),
                     "image": f"assets/instagram/{pid}.jpg"}
            pic = os.path.join(ROOT, entry["image"])
            if not os.path.exists(pic):
                try:
                    if not save_picture(post.get("picture") if isinstance(post.get("picture"), str) else "", pic):
                        continue
                except Exception as e:
                    print(f"Could not save the picture of {link} ({e}); will try again next time.")
                    continue
                print(f"New post: {link}")
            if saved.get(pid) != entry:
                saved[pid] = entry
                changed = True

    for pid, p in list(saved.items()):                  # posts hidden in the admin panel
        if shortcode(p["url"]) in hidden:
            del saved[pid]
            drop_picture(p)
            print(f"Hidden: {p['url']}")
            changed = True

    newest = sorted(saved.values(), key=lambda p: p["time"], reverse=True)
    for p in newest[max_posts:]:                         # only the newest max_posts are kept
        drop_picture(p)
        changed = True
    if changed or not os.path.exists(DATA):
        posts = newest[:max_posts]
        with open(DATA, "w", encoding="utf-8") as fh:
            json.dump({"posts": posts}, fh, ensure_ascii=False, indent=1)
        print(f"data/instagram.json: {len(posts)} posts")
    else:
        print("No new Instagram posts.")


if __name__ == "__main__":
    sys.exit(main())
