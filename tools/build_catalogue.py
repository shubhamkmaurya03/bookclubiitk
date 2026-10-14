#!/usr/bin/env python3
"""
Build the public catalogue file (data/catalogue.json) from the library export.

Usage:
    python3 tools/build_catalogue.py path/to/data_updated.json

The export (data_updated.json) contains member names and IDs for issued books.
That file must NOT be uploaded to the website. This script keeps only what the
catalogue page needs: title, author, genre, rating, cover, description, and
whether the book is currently out on loan (without saying who has it).
"""
import json
import os
import re
import sys

# Clean up the many spellings of each genre in the export.
GENRE_MAP = {
    "fiction": "Fiction", "fictoin": "Fiction", "f": "Fiction",
    "bengali": "Bengali",
    "hindi": "Hindi",
    "fantasy": "Fantasy",
    "science fiction": "Science Fiction", "science ficition": "Science Fiction",
    "scince fiction": "Science Fiction",
    "biographies": "Biographies", "biography": "Biographies",
    "autobiography": "Autobiographies",
    "classic": "Classics", "classics": "Classics",
    "detective fiction": "Detective Fiction", "crime": "Crime",
    "science": "Science", "popular science": "Popular Science",
    "collection": "Collections", "collections": "Collections",
    "spirituality": "Spirituality", "spiritual": "Spirituality",
    "humor": "Humour", "humour": "Humour",
    "politics": "Politics",
    "self help": "Self Help",
    "history": "History",
    "romance": "Romance",
    "business": "Business",
    "poetry": "Poetry",
    "drama": "Drama", "dr": "Drama",
    "sociology": "Sociology",
    "travel": "Travel",
    "sports": "Sports",
    "do it yourself": "Do It Yourself",
    "art": "Art",
    "psychology": "Psychology", "psycology": "Psychology",
    "facts and mysteries": "Facts & Mysteries",
    "english": "English Literature", "english literature": "English Literature",
    "quiz": "Quiz",
    "graphic novel": "Graphic Novels",
}


def clean_genre(raw):
    key = (raw or "").strip().strip("`\\-").strip().lower()
    if not key:
        return ""
    return GENRE_MAP.get(key, key.title())


def clean_text(s):
    return " ".join((s or "").split())


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "data_updated.json"
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "data", "catalogue.json")

    with open(src, encoding="utf-8") as fh:
        rows = json.load(fh)

    # Extra descriptions/covers fetched by enrich_catalogue.py (optional).
    cache_path = os.path.join(here, "enrichment_cache.json")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as fh:
            cache = json.load(fh)
    enriched = 0

    books = []
    for row in rows:
        f = row["fields"]
        title = clean_text(f.get("Title")).strip("'\"")
        if not title:
            continue
        image = f.get("image") or ""
        if "nophoto" in image:
            image = ""
        try:
            rating = round(float(f.get("rating")), 2)
        except (TypeError, ValueError):
            rating = 0
        book = {"t": title, "a": clean_text(f.get("Author")).title() if (f.get("Author") or "").isupper() else clean_text(f.get("Author"))}
        if title.isupper():
            book["t"] = title.title()
        genre = clean_genre(f.get("Genre"))
        if genre:
            book["g"] = genre
        if rating:
            book["r"] = rating
        if image:
            book["i"] = image.replace("http://", "https://", 1)
        desc = clean_text(f.get("description"))
        if desc:
            book["d"] = desc
        if f.get("memberid"):
            book["o"] = 1  # currently issued

        # Fill gaps only; data from the club's own records always wins.
        hit = cache.get(book["t"].strip().lower() + "|" + book["a"].strip().lower(), {})
        for source in ("openlibrary", "google"):
            extra = hit.get(source) or {}
            if "d" not in book and extra.get("d"):
                book["d"] = extra["d"]
                book["ds"] = extra.get("src", "")
                enriched += 1
            if "i" not in book and extra.get("i"):
                book["i"] = extra["i"]
        books.append(book)

    books.sort(key=lambda b: re.sub(r"^[^0-9a-z]+", "", b["t"].lower()))
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(books, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"Wrote {len(books)} books to {os.path.normpath(out)}"
          + (f" ({enriched} descriptions added from Open Library / Google Books)" if enriched else ""))


if __name__ == "__main__":
    main()
