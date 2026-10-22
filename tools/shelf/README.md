# Live shelf status (Koha → website)

The club computer runs Koha offline. A small program on it checks Koha every 2 minutes and, when a book is
issued or returned, publishes which titles are out. The catalogue page, on both GitHub Pages and
iitk.ac.in, reads that file in the visitor's browser and shows **On the shelf**, **Issued · due 4 Nov** or
**2 of 3 on the shelf**.

```
 club computer (Koha) ──every 2 min, only when something changed──▶ bookclub-shelf repo, "status" branch
                                                                              │ GitHub Actions
                                                                              ▼
 visitor's browser ◀──────── status.json ◀──────────── GitHub Pages (shubhamkmaurya03.github.io/bookclub-shelf)
        ▲
        └── catalogue page from iitk.ac.in or GitHub Pages
```

## What is protected, and how

- **Nothing connects to the club computer.** It only sends files out to GitHub. No port is opened and Koha is not online.
- **Only titles and counts leave the computer.** `status.json` has, per Koha record, `[copies, issued, earliest due date]`;
  `books.json` has record number, title, author, ISBN, number of copies and the genre code (the letters at the start of
  the barcode, like `FIC`). No member data, no barcodes, no loan history.
- **The program cannot read member data even by mistake.** It uses its own database login that can read only
  `items(itemnumber, biblionumber, barcode, onloan, itemlost, withdrawn)`, `biblio(biblionumber, title, author)` and
  `biblioitems(biblionumber, isbn)`.
- **The GitHub token works only on the separate `bookclub-shelf` repository.** It cannot change the website or the
  admin panel. It is stored readable only by the `bookclub-shelf` system account on the club computer.
- **No history.** Each update replaces the previous one, so nobody can browse when each book went out.
- **The website treats the file as data.** The catalogue accepts only record numbers, counts and dates from it and
  ignores anything else.

## Files

| File | Where it runs | What it does |
|---|---|---|
| `koha_info.sh` | club computer, once | Read-only survey of Koha, used to finish the setup (see `KOHA-INFO-PROMPT.md`) |
| `install.sh` | club computer, once (guided by `INSTALL-PROMPT.md`) | Creates the account, database login, token file and 2-minute timer |
| `shelf_sync.py` | club computer, every 2 min | Reads Koha and publishes `status.json` and `books.json` |
| `shelf-repo/` | GitHub | Contents of the `bookclub-shelf` repository: the publishing workflow and a README |

## Setting it up

**1. Survey Koha (once; done in October 2026).** On the club computer, follow `KOHA-INFO-PROMPT.md` and bring
`koha-info/` back. The catalogue is built from Koha's list, so every book can show live status.

**2. Create the `bookclub-shelf` repository** at https://github.com/new: name `bookclub-shelf`, **Public**,
no README. Then upload the contents of `shelf-repo/` to it (keep the `.github/workflows/` folder), and:
- *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.

**3. Create a token only for that repository** at https://github.com/settings/personal-access-tokens/new:
- Token name: `Club computer shelf sync`. Expiration: 1 year (put a reminder in the calendar).
- Repository access: **Only select repositories → `bookclub-shelf`**.
- Repository permissions → **Contents: Read and write**. Nothing else.
- Generate, and keep the page open to copy the token (starts with `github_pat_`).

**4. Install on the club computer** (Ubuntu, with sudo):
```
git clone https://github.com/shubhamkmaurya03/bookclubiitk.git
cd bookclubiitk
sudo bash tools/shelf/install.sh bookclubiitk shubhamkmaurya03/bookclub-shelf
```
(`bookclubiitk` is the Koha instance on the club computer.) Paste the token when asked (it is not shown). The script
needs MySQL's administrator once: it tries `sudo mysql`, then Ubuntu's maintenance login, and otherwise asks for the
MySQL root password. The script tests the database login, sends the first update and
starts the timer. Within a minute, `https://shubhamkmaurya03.github.io/bookclub-shelf/status.json` should open.

**5. Turn it on in the website:** admin panel → *Timings, contact & home page* → **Live shelf status address**:
`https://shubhamkmaurya03.github.io/bookclub-shelf/status.json`. Saving rebuilds the website, which from then on also takes
Koha's book list from the same place (daily and on every change). Then upload the new site.zip to iitk.ac.in once.

## Day to day

Nothing to do. While the computer is on, issues and returns appear on the website within about 2–3 minutes.
When it is off, the website keeps showing the last status (which is still correct, since no books move without Koha).

```
systemctl list-timers bookclub-shelf.timer           # when it last ran and runs next
journalctl -u bookclub-shelf --since today           # what it did ("Sent: …" lines, or errors)
sudo -u bookclub-shelf python3 /opt/bookclub-shelf/shelf_sync.py --dry-run   # test the database side
```

- **Token expired or leaked:** create a new one (step 3) and run `install.sh` again; it asks to replace the token.
  Delete the old token on GitHub.
- **IITK firewall login expired:** the sync logs "Is the IITK firewall login active…" and retries every 2 minutes;
  log in again in the browser and it catches up.
- **Needs a proxy for internet:** add `https_proxy=http://host:port` to `/etc/bookclub-shelf/env`.
- **Koha upgraded or moved:** run `install.sh` again.
- **Turn it off:** `sudo systemctl disable --now bookclub-shelf.timer`, and empty the address in the admin panel.
- **Remove completely:**
  ```
  sudo systemctl disable --now bookclub-shelf.timer
  sudo rm /etc/systemd/system/bookclub-shelf.{service,timer} && sudo systemctl daemon-reload
  sudo mysql -e "DROP USER 'bookclub_shelf'@'localhost'"
  sudo rm -r /etc/bookclub-shelf /opt/bookclub-shelf /var/lib/bookclub-shelf && sudo userdel bookclub-shelf
  ```
