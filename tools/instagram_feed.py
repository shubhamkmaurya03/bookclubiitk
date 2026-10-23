#!/usr/bin/env python3
"""
Keep the club's Instagram posts for the Blogs & Events page.

    python3 tools/instagram_feed.py

Reads the Behold feed named in content/instagram.json. Behold (behold.so) is connected to
@bookclub_iitk and lists its newest posts (6 on the free plan, refreshed daily). Each new post
is added to data/instagram.json, with a copy of its picture in assets/instagram/. Posts already
saved are kept, so the page builds up an archive beyond Behold's six. Posts listed under
"hidden" in content/instagram.json (by their Instagram link) are removed, picture included.

The website build runs this every 3 hours (.github/workflows/publish.yml). If the feed cannot
be read, nothing changes.
"""
import datetime
import io
import json
import os
import re
import sys
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


def get(url, hosts, limit, timeout=60):
    if not allowed(url, hosts):
        raise ValueError(f"address not allowed: {url[:80]}")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        if not allowed(r.geturl(), hosts):
            raise ValueError("redirected to another server")
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"larger than {limit // (1024 * 1024)} MB")
    return data


def clean_caption(text):
    text = re.sub(r"[ \t]+", " ", (text or "").replace("\r", ""))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:900]


def save_picture(post, path):
    sizes = post.get("sizes") or {}
    url = ((sizes.get("medium") or sizes.get("large") or sizes.get("small") or {}).get("mediaUrl")
           or post.get("thumbnailUrl") or (post.get("mediaUrl") if post.get("mediaType") != "VIDEO" else ""))
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


def main():
    settings = json.load(open(SETTINGS, encoding="utf-8"))
    feed_url = (settings.get("feed") or "").strip()
    hidden = {shortcode(h) for h in settings.get("hidden") or [] if h}
    data = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else {"posts": []}
    saved = {p["id"]: p for p in data.get("posts", [])}
    changed = False

    if feed_url:
        try:
            feed = json.loads(get(feed_url, FEED_HOSTS, MAX_FEED))
            if not isinstance(feed, dict):
                raise ValueError("not a feed")
        except Exception as e:                          # network, Behold down, bad JSON, wrong address
            print(f"Could not read the Instagram feed ({e}); keeping the saved posts.")
            feed = {}
        os.makedirs(PICS, exist_ok=True)
        posts = feed.get("posts") if isinstance(feed.get("posts"), list) else []
        for post in posts[:50]:
            if not isinstance(post, dict):
                continue
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
            kind = {"VIDEO": "video", "CAROUSEL_ALBUM": "album"}.get(post.get("mediaType"), "image")
            entry = {"id": pid, "url": link, "time": when.isoformat(), "type": kind,
                     "caption": clean_caption(str(post.get("prunedCaption") or post.get("caption") or "")),
                     "image": f"assets/instagram/{pid}.jpg"}
            pic = os.path.join(ROOT, entry["image"])
            if not os.path.exists(pic):
                try:
                    if not save_picture(post, pic):
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
            if re.fullmatch(r"assets/instagram/\d{5,30}\.jpg", p.get("image", "")):   # only our own saved pictures
                pic = os.path.join(ROOT, p["image"])
                if os.path.exists(pic):
                    os.remove(pic)
            print(f"Hidden: {p['url']}")
            changed = True

    if changed or not os.path.exists(DATA):
        posts = sorted(saved.values(), key=lambda p: p["time"], reverse=True)
        with open(DATA, "w", encoding="utf-8") as fh:
            json.dump({"posts": posts}, fh, ensure_ascii=False, indent=1)
        print(f"data/instagram.json: {len(posts)} posts")
    else:
        print("No new Instagram posts.")


if __name__ == "__main__":
    sys.exit(main())
