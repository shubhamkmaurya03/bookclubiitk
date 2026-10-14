# Book Club, IIT Kanpur — website

A fully static site: plain HTML, one stylesheet and two small scripts. It has no build step, no server code and no frameworks, so it can be uploaded as-is to `iitk.ac.in/bookclub/`.

```
index.html  rules.html  catalogue.html  request.html  blogs.html  contact.html  mellifluous.html  404.html
blog1.html … blog6.html, "The Fault in Our Stars.html", "Notes from Underground.html"   (old URLs kept)
assets/css/style.css     all styling (light + dark theme)
assets/js/main.js        theme toggle, mobile menu, team tabs
assets/js/catalogue.js   catalogue search (runs in the browser)
assets/img/              logo, favicons, book covers, team photos
data/catalogue.json      public catalogue data (no member details)
tools/build_catalogue.py regenerates data/catalogue.json
```

## Preview locally
```
python3 -m http.server 8000
```
Then open http://127.0.0.1:8000. Opening the files directly with `file://` works too, except for the catalogue, which needs a server to load its data.

## Common updates

**Update the catalogue.** Export `data_updated.json` as before, then run:
```
python3 tools/build_catalogue.py path/to/data_updated.json
```
Upload the new `data/catalogue.json`. **Do not upload `data_updated.json` itself**, because it contains member names and IDs. Remove the old copy from the server too.

**Add a blog post.**
1. Copy an existing post (e.g. `blog6.html`) to `blog7.html`.
2. Change the title, date, reviewer, cover image and the `<p>` paragraphs.
3. Put the cover in `assets/img/books/` (about 420 px wide).
4. Add a card to `blogs.html`. Put it in the "Latest review" spot if it's the newest.
5. Optionally add it to "Latest reviews" on `index.html`.
6. Update the previous/next links at the bottom of the neighbouring posts.

**Change the team.** Edit the `<figure class="person">` blocks in `contact.html`. Before adding photos, resize them and strip their metadata, since phone photos often carry GPS location:
```
convert photo.jpg -auto-orient -strip -resize '480x480^' -quality 80 assets/img/team/name.jpg
```

**Change timings or quotes.** These are plain text inside each page. Search for "9 pm" or "blockquote".

## Notes
- Forms post to `https://formspree.io/iitkbookclub@gmail.com`, the same endpoint as the old site.
- Fonts come from Google Fonts (Cormorant Garamond and EB Garamond). Catalogue covers load from Goodreads' image CDN. A typeset cover appears when one is missing.
