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
| `data/catalogue.json` | Catalogue data, built by `tools/build_catalogue.py` |
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

The library export (`data_updated.json`) contains member names and IDs, so it must **never** be committed
(it is in `.gitignore`) or uploaded. On your own computer:

```
python3 tools/build_catalogue.py path/to/data_updated.json      # writes data/catalogue.json
python3 tools/enrich_catalogue.py openlibrary                   # optional: fill missing descriptions/covers
GOOGLE_BOOKS_API_KEY=... python3 tools/enrich_catalogue.py google
python3 tools/build_catalogue.py path/to/data_updated.json      # merge them in
```
Then commit and push `data/catalogue.json`.

## Building locally

```
pip install -r tools/requirements.txt
python3 tools/build_site.py
python3 -m http.server 8000 --directory _site      # open http://127.0.0.1:8000
```
The build refuses to run if any image in `assets/` contains GPS location data.
