# Prompt for the club computer: Koha survey

**How to use this:** on the club computer (Ubuntu, where Koha runs), get this repository, start Claude Code
in its folder and paste everything below the line. Getting the repository:

```
git clone https://github.com/shubhamkmaurya03/bookclubiitk.git
cd bookclubiitk
claude
```
If `git` is not installed, download https://github.com/shubhamkmaurya03/bookclubiitk/archive/refs/heads/main.zip,
unzip it and open the unzipped folder instead.

When it is done, copy the `koha-info/` folder to your own computer into the website folder
(`bookclub/koha-info/`) using a pen drive or your own email/Drive. Do not upload it anywhere public or commit it.

---

You are helping the Book Club of IIT Kanpur connect its library system to its website. This computer runs
**Koha** (offline) for issuing and returning books. We are building a small program that will run here every
2 minutes and publish which books are currently issued, so the website catalogue can show live shelf status.
The program and its installer are already written (`tools/shelf/`, see `tools/shelf/README.md`), but we need
facts about this particular Koha setup to finish it. Your job is **only to collect those facts** and write
them down. Another Claude session, on a different computer, will use your findings.

## Strict rules

1. **Read only.** Do not change, install, upgrade, restart or delete anything: no `apt`, no `pip`, no edits to
   Koha or system settings, no SQL other than `SELECT`/`SHOW`. Do **not** run `tools/shelf/install.sh`.
2. **No member data, ever.** Do not query or print the `borrowers` table, any `borrower*`/`patron*` table,
   `accountlines`, `statistics`, `action_logs`, `message_queue`, `reserves`, `old_reserves`, or the
   `borrowernumber` column of any table. Counts and dates of loans are fine; who borrowed is not.
3. **No passwords or secrets.** Never print the `<pass>` line of `koha-conf.xml`, `/etc/mysql/debian.cnf`,
   or any password, key or token. Read only the database name, host and port from `koha-conf.xml`.
4. **Nothing leaves this computer** except the two test requests to github.com that the survey script makes.
   Do not upload, email, commit or push anything.
5. If something requires `sudo`, explain what the command does before running it. If a rule would stop you
   from finding something out, write down what is missing and why instead.

## Step 1: run the survey script

```
sudo bash tools/shelf/koha_info.sh
```
(If there is more than one Koha instance, it surveys the first enabled one; to choose, add the instance name:
`sudo bash tools/shelf/koha_info.sh <instance>`.)

It writes `koha-info/report.txt` and `koha-info/koha-books.tsv` (one line per copy: record number, item number,
barcode, title, author, ISBN, item type, collection, location, call number, stock number, copy number,
lost/withdrawn flags, date added). Read the script first if you want to check what it does.

If the script stops early (for example Koha was not installed with the standard `koha-common` package, so
`koha-list` or `/etc/koha/sites/` is missing), find the same facts by hand, following the rules above, and note
how Koha is installed (Docker, source install, another distribution).

## Step 2: check the output for personal data

Open both files and look through them, especially the sample values for `itemnotes`, `stocknumber` and
`itemcallnumber`. If any value contains a person's name, roll number, phone number or email (for example
"Donated by …"), replace that value with `[removed]` in both files and note it in `answers.md`.

## Step 3: ask the person at the computer, and look where needed

Write `koha-info/answers.md` with the answers to the questions below. Ask the person for anything you cannot see
yourself. Keep answers short and factual.

**Barcodes** (the club changed every book's barcode last year; the website's catalogue still uses the old list,
which has old barcodes such as `BK99593` and `MCFR03`)
1. Are the barcodes in Koha the **new** ones? About when were they changed?
2. Is there any record linking **old barcode → new barcode**? Look in Koha (the survey's stock number, copy
   number, call number and notes samples) and ask the person whether a spreadsheet or file exists. If a file
   exists on this computer, open it, check it has no member information, and copy **only the old-barcode,
   new-barcode, title and author columns** into `koha-info/barcode-map.csv`.
3. Does every physical copy have its own barcode, and is each copy a separate item in Koha?

**Cataloguing**
4. Is there one Koha record per title (with copies as items under it), or a separate record for every copy?
   (The survey's "copies_per_title" table and "same_title_author_groups" count help.)
5. Where is the genre recorded: item type, collection code, shelving location, call number, a MARC subject field,
   or not at all?
6. When new books arrive, are they added to Koha straight away?
7. Are lost or discarded books marked as lost/withdrawn in Koha, or deleted, or left as they are?

**Issuing**
8. Is every issue and return done in Koha at the desk, or are some written in a register and entered later?
9. Roughly how many issues and returns happen on a busy evening?

**This computer**
10. When is it switched on? Only during club hours, or always? Does it sleep or shut down by itself?
11. How does it get internet: campus LAN or Wi-Fi? Does it need the IITK firewall login page, and does that login
    stay active while the computer is on? Is a proxy needed? (The survey tests whether GitHub can be reached.)
12. Which Ubuntu user account is used, and does the person have `sudo` on it?
13. Is there more than one Koha instance (for example a test copy)? Which one is used at the desk?
14. Anything unusual about this setup (Koha in Docker or a virtual machine, a remote database, a custom
    database name, a very old Koha version)?

## Step 4: finish

Print a short summary for the person: what you found, anything missing, and the reminder:

> Copy the whole `koha-info/` folder to your own computer into the website folder (`bookclub/koha-info/`)
> with a pen drive or your own email/Drive, then tell the website Claude session it is there.
> Do not post it publicly or commit it to GitHub.
