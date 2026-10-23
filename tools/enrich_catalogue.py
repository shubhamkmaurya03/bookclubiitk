#!/usr/bin/env python3
"""
Fill in missing descriptions and covers from open book databases.

    python3 tools/enrich_catalogue.py openlibrary
    GOOGLE_BOOKS_API_KEY=... python3 tools/enrich_catalogue.py google

Only books in data/catalogue.json that lack a description or a cover are looked
up. Results are cached in tools/enrichment_cache.json, so the script can be
stopped and resumed at any time (Google's daily quota will usually stop it
part-way; just run it again the next day). Afterwards run build_catalogue.py,
which merges the cache into data/catalogue.json.

Ratings are deliberately NOT taken from these sources: they are based on very
few votes and are not comparable with the existing ratings.
"""
import difflib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOGUE = os.path.join(HERE, "..", "data", "catalogue.json")
CACHE = os.path.join(HERE, "enrichment_cache.json")
UA = {"User-Agent": "BookClubIITK-catalogue/1.0 (iitkbookclub@gmail.com)"}


# ---------------------------------------------------------------- helpers
def key_for(book):
    return (book["t"].strip().lower() + "|" + (book.get("a") or "").strip().lower())


def norm_title(s):
    s = (s or "").lower()
    s = re.split(r"[:(\[]", s)[0]                      # drop subtitles / series
    s = re.sub(r"^(the|a|an)\s+", "", s.strip())
    return " ".join(re.findall(r"[a-z0-9ऀ-৿]+", s))


def titles_match(ours, theirs):
    a, b = norm_title(ours), norm_title(theirs)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 8 and longer.startswith(shorter):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def authors_match(ours, theirs):
    if not ours:
        return True
    ours_tokens = {t for t in re.findall(r"[a-z]+", ours.lower()) if len(t) > 2}
    if not ours_tokens:
        return True
    for name in theirs or []:
        their_tokens = {t for t in re.findall(r"[a-z]+", name.lower()) if len(t) > 2}
        for a in ours_tokens:
            for b in their_tokens:
                # tolerate spelling variants such as Dostoevsky / Dostoyevsky
                if a == b or (min(len(a), len(b)) >= 5 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.85):
                    return True
    return False


# A few common words per language, enough to spot a blurb that isn't in English.
_EN = set("the and of to a in is his her that with for was on as by it an".split())
_OTHER = set("el la los las que y del por una le les et des du une der die und das ist não com uma para il che".split())


def is_english(text):
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    other = sum(w in _OTHER for w in words)
    return other < 3 or other <= sum(w in _EN for w in words)


def clean_description(d):
    if isinstance(d, dict):
        d = d.get("value", "")
    d = d or ""
    d = re.split(r"\n-{3,}|\n\*{3,}|\nContains:|\n\(\[source\]", d)[0]  # Open Library footers
    d = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", d)                   # markdown links
    d = re.sub(r"\[\d+\]:\s*\S+", "", d)
    d = re.sub(r"<[^>]+>", " ", d)                                    # html tags (Google)
    d = " ".join(d.split())
    if len(d) > 1400:
        d = d[:1400].rsplit(" ", 1)[0] + "…"
    return d if len(d) >= 40 and is_english(d) else ""


def get_json(url, retries=4):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise
            if e.code == 404:
                return {}
            time.sleep(5 * (attempt + 1))
        except Exception:
            time.sleep(5 * (attempt + 1))
    return {}


# ---------------------------------------------------------------- sources
def lookup_openlibrary(book):
    q = urllib.parse.urlencode({"title": book["t"], "author": book.get("a", ""), "limit": 5,
                                "fields": "key,title,author_name,cover_i"})
    res = get_json("https://openlibrary.org/search.json?" + q)
    time.sleep(1)
    for doc in res.get("docs", []):
        if not (titles_match(book["t"], doc.get("title")) and authors_match(book.get("a"), doc.get("author_name"))):
            continue
        out = {}
        if isinstance(doc.get("cover_i"), int):
            out["i"] = f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg"
        if not re.fullmatch(r"/works/OL\d+W", str(doc.get("key", ""))):   # only ever ask openlibrary.org itself
            return out
        if not book.get("d"):
            work = get_json("https://openlibrary.org" + doc["key"] + ".json")
            time.sleep(1)
            desc = clean_description(work.get("description"))
            if desc:
                out["d"] = desc
        out["src"] = "Open Library"
        out["url"] = "https://openlibrary.org" + doc["key"]
        return out
    return {}


def lookup_google(book, api_key):
    # A plain keyword search finds far more books than intitle:/inauthor: (which need exact
    # spellings); titles_match/authors_match below keep only real matches.
    q = f'{book["t"]} {book.get("a", "")}'.strip()
    params = urllib.parse.urlencode({
        "q": q, "maxResults": 10, "printType": "books", "key": api_key,
        "fields": "items(volumeInfo(title,authors,description,imageLinks,infoLink))"})
    res = get_json("https://www.googleapis.com/books/v1/volumes?" + params)
    time.sleep(0.4)
    for item in res.get("items", []):
        v = item.get("volumeInfo", {})
        if not (titles_match(book["t"], v.get("title")) and authors_match(book.get("a"), v.get("authors"))):
            continue
        out = {}
        img = (v.get("imageLinks") or {}).get("thumbnail")
        if img:
            out["i"] = img.replace("http://", "https://").replace("&edge=curl", "")
        desc = clean_description(v.get("description"))
        if desc:
            out["d"] = desc
        if out:
            out["src"] = "Google Books"
            out["url"] = v.get("infoLink", "")
            return out
    return {}


# ---------------------------------------------------------------- main
def main():
    source = sys.argv[1] if len(sys.argv) > 1 else ""
    if source not in ("openlibrary", "google"):
        sys.exit(__doc__)
    api_key = os.environ.get("GOOGLE_BOOKS_API_KEY", "")
    if source == "google" and not api_key:
        sys.exit("Set GOOGLE_BOOKS_API_KEY first.")

    books = json.load(open(CATALOGUE, encoding="utf-8"))
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

    def still_missing(b):
        hit = cache.get(key_for(b), {})
        got = {}
        for src in ("openlibrary", "google"):
            got.update({k: v for k, v in (hit.get(src) or {}).items()
                        if k == "i" or (k == "d" and is_english(v))})
        return (not b.get("d") and "d" not in got) or (not b.get("i") and "i" not in got)

    todo = [b for b in books if (not b.get("d") or not b.get("i"))]
    todo = [b for b in todo if source not in cache.get(key_for(b), {}) and still_missing(b)]
    print(f"{len(todo)} books to look up on {source}", flush=True)

    found = 0
    for n, book in enumerate(todo, 1):
        try:
            hit = lookup_openlibrary(book) if source == "openlibrary" else lookup_google(book, api_key)
        except urllib.error.HTTPError as e:
            print(f"Rate limit reached after {n - 1} books (HTTP {e.code}). Run again later to resume.")
            break
        cache.setdefault(key_for(book), {})[source] = hit
        found += bool(hit.get("d") or hit.get("i"))
        if n % 25 == 0 or n == len(todo):
            json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"  {n}/{len(todo)} looked up, {found} enriched", flush=True)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Done: {found} books enriched from {source}. Now run build_catalogue.py.")


if __name__ == "__main__":
    main()
