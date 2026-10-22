# Prompt for the club computer: install the shelf sync

**Before this:** on your own computer, create the `bookclub-shelf` repository and its token
(steps 2 and 3 in `tools/shelf/README.md`). Then, on the club computer, in the `bookclubiitk` folder, start
`claude` and type:

> Run `git pull`, then read `tools/shelf/INSTALL-PROMPT.md` and follow the part below the line.

---

You are helping the Book Club of IIT Kanpur install the **shelf sync** on this computer, which runs Koha. Read
`tools/shelf/README.md` first: it explains what the sync does and how it is protected. Facts about this computer
(from a survey done earlier): Ubuntu 20.04, Koha 22.05 (instance `bookclubiitk`, database `koha_bookclubiitk`),
MySQL 8, Python 3.8, internet through the IITK firewall login page.

## Strict rules

1. **Never ask for, type, read or print the GitHub token**, the MySQL root password or the sudo password. The
   person types them into the installer themselves, in their own terminal. Do not open `/etc/bookclub-shelf/token`,
   `/etc/bookclub-shelf/my.cnf`, `/etc/mysql/debian.cnf` or `koha-conf.xml` passwords.
2. **Do not change Koha** or its database, other than what `install.sh` does (it adds one read-only login).
3. **Do not edit the scripts in `tools/shelf/`.** If something fails, describe it; the fix is made on the website
   side and pulled again.
4. Do not commit or push anything from this computer.

## Steps

1. **Update:** run `git pull` and confirm `tools/shelf/install.sh` exists.
2. **Check the prerequisites,** and stop with a clear message if one is missing:
   - The IITK firewall login is active: `curl -sS -o /dev/null -w '%{http_code}\n' https://api.github.com/zen` prints `200`.
   - The repository exists and has the publishing workflow:
     `curl -s -o /dev/null -w '%{http_code}\n' https://api.github.com/repos/shubhamkmaurya03/bookclub-shelf/contents/.github/workflows/publish.yml`
     prints `200`. (`404` means the repository or the `.github/workflows/publish.yml` file is missing.)
   - Ask the person to confirm: Pages source is set to **GitHub Actions** in the repository settings, and they have
     the token ready (fine-grained, only `bookclub-shelf`, Contents: Read and write).
3. **Install.** The installer asks for passwords and the token with hidden input, which you cannot do, so ask the
   person to open a **separate terminal window** and run:
   ```
   cd ~/bookclubiitk
   sudo bash tools/shelf/install.sh bookclubiitk shubhamkmaurya03/bookclub-shelf
   ```
   (adjust the folder if the repository is elsewhere). Tell them what to expect: their sudo password; maybe the MySQL
   root password (only if the installer cannot use `sudo mysql` or Ubuntu's maintenance login); then the GitHub token
   (pasting shows nothing, that is normal). It then tests the database login, sends a first update and starts the
   2-minute timer. Ask them to paste the installer's output back to you, **after checking it contains no password
   or token** (it should not).
4. **Verify** (these show no secrets):
   - `systemctl list-timers bookclub-shelf.timer` shows a next run within 2 minutes.
   - `sudo -u bookclub-shelf python3 /opt/bookclub-shelf/shelf_sync.py --dry-run` prints the number of titles,
     copies and copies issued (about 6,000 titles and 6,850 copies).
   - `journalctl -u bookclub-shelf --since "10 min ago" --no-pager` shows no errors.
   - `curl -s https://api.github.com/repos/shubhamkmaurya03/bookclub-shelf/actions/runs?per_page=1` shows the latest
     "Publish shelf status" run; wait until its `conclusion` is `success` (about 1 minute).
   - `curl -s https://shubhamkmaurya03.github.io/bookclub-shelf/status.json | head -c 300` shows
     `{"out":{…},"updated":"…","v":1}`.
5. **If something fails,** match it here and tell the person what to fix:
   - `HTTP 401`: the token is wrong or expired. Make a new one and run the installer again (it offers to replace the token).
   - `HTTP 403` or `404` from `/git/…` or `/dispatches`: the token is not limited to `bookclub-shelf` or lacks
     *Contents: Read and write*.
   - "Is the IITK firewall login active": log in to the firewall page in the browser; the sync retries by itself.
   - The publish run fails or never starts: in the repository's *Settings → Pages*, the source must be *GitHub Actions*;
     and `.github/workflows/publish.yml` must be in the repository's `main` branch.
   - "Cannot reach Koha's database" or a MySQL access error: report the exact message.
6. **Finish** with a short summary for the person, and remind them of the last steps on their own computer: in the
   website's admin panel, set *Timings, contact & home page → Live shelf status address* to
   `https://shubhamkmaurya03.github.io/bookclub-shelf/status.json`, then upload the new site.zip to iitk.ac.in once.
