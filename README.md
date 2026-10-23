# Book Club IIT Kanpur — website

A static website: plain HTML, CSS and JavaScript, with no server code, which suits the IITK web server.
Content is kept in simple files and edited through an **admin panel**. Each save rebuilds the site automatically.

- **Live preview:** https://shubhamkmaurya03.github.io/bookclubiitk/
- **Admin panel:** https://shubhamkmaurya03.github.io/bookclubiitk/admin/ (see [ADMIN-GUIDE.md](ADMIN-GUIDE.md))
- **Official site:** https://www.iitk.ac.in/bookclub/ (uploaded by hand with WinSCP, see below)

## How it works

```
 admin panel ──save──▶ content/ on main ──GitHub Action──▶ tools/build_site.py ──▶ "site" branch
 (coordinators)          (blogs, team, rules…)                                       │
                                                                                     ├─▶ GitHub Pages (preview)
                                                                                     └─▶ site.zip ──WinSCP──▶ iitk.ac.in/bookclub
```

| Folder | What it holds |
|---|---|
| `content/blogs/*.md` | One file per blog post (details at the top, review text below) |
| `content/team.json` | Current team and past teams |
| `content/rules.json` | Rules page and fines table |
| `content/mellifluous.json` | Magazine editions (newest first) |
| `content/site.json` | Timings, location, socials, home page text, quotes |
| `assets/` | Stylesheet, scripts, images. `assets/uploads/` is where the admin panel puts new photos |
| `data/` | Catalogue data: Koha's book list, extra details, and `catalogue.json` built from them by `tools/build_catalogue.py` |
| `admin/` | The admin panel (Sveltia CMS) and its form definitions (`config.yml`) |
| `tools/` | Build scripts |
| `.github/workflows/publish.yml` | Rebuilds and publishes the site on every change |

## One-time GitHub setup

1. **Settings → Pages:** Source = *Deploy from a branch*, Branch = **`site`**, folder `/ (root)`.
   The `site` branch is created by the first run of the workflow.
2. **Settings → Actions → General → Workflow permissions:** select *Read and write permissions*.
3. **Settings → Collaborators:** add each coordinator's GitHub account (they should turn on two-factor authentication).

## Publishing to iitk.ac.in

1. After a change, wait for the green tick on the latest commit (Actions tab, about 2 minutes).
2. Download https://github.com/shubhamkmaurya03/bookclubiitk/archive/refs/heads/site.zip and unzip it.
3. Upload the **contents** of the unzipped folder to the `bookclub` folder with WinSCP, replacing existing files.
   You can skip the `admin/` folder, since the admin panel is used from GitHub Pages.

## Updating the catalogue

The catalogue lists what is in **Koha**, the library system on the club computer, one entry per title.

| File | What it holds |
|---|---|
| `data/koha_books.json` | Koha's titles: record number, title, author, ISBN, copies, genre code, date added (no barcodes, no members) |
| `content/genres.json` | Barcode genre code → genre name (admin panel → *Club pages → Genres*) |
| `data/book_details.json` | Per Koha record: display title/author, Goodreads rating, cover, description (carried over from the old catalogue; edit by hand to fix one) |

Once live shelf status is running, the club computer publishes Koha's list and the website build (on every
change and daily) picks it up, so new books appear by themselves. Until then, or to refresh it by hand from a
survey of the club computer (`tools/shelf/koha_info.sh`, which writes `koha-info/koha-books.tsv`):

```
python3 tools/build_catalogue.py --survey koha-info/koha-books.tsv     # updates data/koha_books.json and data/catalogue.json
python3 tools/enrich_catalogue.py openlibrary                         # optional: fill missing descriptions/covers
GOOGLE_BOOKS_API_KEY=... python3 tools/enrich_catalogue.py google
python3 tools/build_catalogue.py                                      # merge them in
```
Then commit and push `data/`. `koha-info/` has barcodes and stays on your computer (it is in `.gitignore`).

## Live shelf status

The club computer (Koha) publishes which books are issued every 2 minutes, and the catalogue page shows it.
Setup, safety and day-to-day checks: [tools/shelf/README.md](tools/shelf/README.md).

## Instagram posts (Blogs & Events)

[Behold](https://behold.so) is connected to @bookclub_iitk and publishes its newest posts as a JSON feed (address in
`content/instagram.json`). Every 3 hours the website build runs `tools/instagram_feed.py`, which saves new posts to
`data/instagram.json` with a copy of each picture in `assets/instagram/`, and commits them. Saved posts are kept, so
the page builds an archive. The Blogs & Events page also loads `data/instagram.json` live from GitHub Pages, so the
IITK copy shows new posts without an upload. Hide a post: admin panel → *Club pages → Instagram → Hidden posts*.

## Updating the admin panel

`admin/index.html` loads Sveltia CMS pinned to one version, with an integrity hash so that a tampered copy
is refused by the browser. To move to a newer version (only needed for a fix or feature you want):

```
V=0.250.1   # the new version, from https://www.npmjs.com/package/@sveltia/cms
curl -sL https://unpkg.com/@sveltia/cms@$V/dist/sveltia-cms.js | openssl dgst -sha384 -binary | openssl base64 -A
```
Put the version in the script address and `sha384-` followed by the printed hash in `integrity`.

## Updating the build tools

`tools/requirements.txt` pins exact versions with download checksums, so the build refuses a tampered package.
To move to a newer version, change the version number and regenerate the `--hash` lines from PyPI
(`pip download <name>==<version> --no-deps` and `pip hash <file>`, one line per file listed on PyPI).
The GitHub actions in `.github/workflows/publish.yml` are pinned to commits for the same reason.

## Security notes

- The admin panel (`admin/index.html`) loads only at `https://shubhamkmaurya03.github.io` (or localhost) and never
  inside another site's frame, because Sveltia keeps the sign-in token in the browser for that site. If the
  repository moves, change `HOME` there.
- Uploads through the admin panel are published only as re-encoded .jpg/.png/.webp pictures (or .gif as they are);
  anything else is left out with a warning.
- Blog page file names must be plain names like `my-review.html`; anything else falls back to `blog-<file>.html`.
- `build_catalogue.py --fetch` refuses a book list from the club computer with unexpected fields or with fewer than
  80% of the previous records. If many books were really withdrawn at once, run
  `python3 tools/build_catalogue.py --fetch <books.json address>` after moving `data/koha_books.json` aside, and commit.
- The Instagram fetch accepts the feed only from `feeds.behold.so` and pictures only from Behold's and Instagram's
  servers, with size limits.

## Building locally

```
pip install -r tools/requirements.txt
python3 tools/build_site.py
python3 -m http.server 8000 --directory _site      # open http://127.0.0.1:8000
```
The build refuses to run if any image in `assets/` contains GPS location data.
