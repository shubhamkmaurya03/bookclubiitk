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
import urllib.request

from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SETTINGS = os.path.join(ROOT, "content", "instagram.json")
DATA = os.path.join(ROOT, "data", "instagram.json")
PICS = os.path.join(ROOT, "assets", "instagram")
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
UA = {"User-Agent": "BookClubIITK-website/1.0"}
SIZE = 600            # pictures are saved as 600 x 600 JPEGs


def shortcode(url):
    """The post's code in its Instagram link (instagram.com/p/CODE/ or /reel/CODE/)."""
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|tv)/([A-Za-z0-9_-]+)", url or "")
    return m.group(1) if m else (url or "").strip()


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


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
    img = Image.open(io.BytesIO(get(url))).convert("RGB")
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
            feed = json.loads(get(feed_url))
        except Exception as e:                          # network, Behold down, bad JSON
            print(f"Could not read the Instagram feed ({e}); keeping the saved posts.")
            feed = {}
        os.makedirs(PICS, exist_ok=True)
        for post in feed.get("posts") or []:
            pid = str(post.get("id") or "")
            link = post.get("permalink") or ""
            if not re.fullmatch(r"\d{5,30}", pid) or not link.startswith("https://www.instagram.com/"):
                continue
            if shortcode(link) in hidden:
                continue
            when = datetime.datetime.strptime(post["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(IST)
            kind = {"VIDEO": "video", "CAROUSEL_ALBUM": "album"}.get(post.get("mediaType"), "image")
            entry = {"id": pid, "url": link, "time": when.isoformat(), "type": kind,
                     "caption": clean_caption(post.get("prunedCaption") or post.get("caption")),
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
