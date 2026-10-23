#!/usr/bin/env bash
# Read-only survey of the club computer's Koha setup, needed to finish the shelf sync.
#
#   sudo bash tools/shelf/koha_info.sh [koha-instance]
#
# Writes koha-info/report.txt and koha-info/koha-books.tsv in the repository folder.
# It only reads: it changes nothing, installs nothing and sends nothing over the network except
# two test requests to github.com. It never reads member (patron) tables, member columns of loan
# tables, or passwords.
set -u
[ "$(id -u)" -eq 0 ] || { echo "Please run with sudo: sudo bash $0"; exit 1; }

umask 077   # the output (book list with barcodes) is readable only by its owner, not by other accounts
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$(cd "$HERE/../.." && pwd)/koha-info"
mkdir -p "$OUT"
chmod 700 "$OUT"
REPORT="$OUT/report.txt"
: > "$REPORT"
say() { printf '%s\n' "$*" | tee -a "$REPORT"; }
section() { say; say "==================== $*"; }
run() { "$@" 2>&1 | tee -a "$REPORT"; }

say "Koha survey for the Book Club shelf sync, $(date -Iseconds)"

# ------------------------------------------------------------ system
section "System"
run sh -c '. /etc/os-release; echo "OS: $PRETTY_NAME"'
run sh -c 'echo "Kernel: $(uname -r)  Uptime: $(uptime -p)"'
run sh -c 'timedatectl 2>/dev/null | grep -E "Time zone|synchronized" || date'
for c in python3 git curl mysql mariadb systemctl koha-list koha-mysql; do
  if command -v "$c" >/dev/null; then say "$c: $(command -v "$c")  $("$c" --version 2>/dev/null | head -1)"
  else say "$c: not installed"; fi
done
run sh -c 'dpkg-query -W -f="${Package} ${Version}\n" koha-common mariadb-server mysql-server 2>/dev/null'
run sh -c 'systemctl is-active mariadb mysql apache2 koha-common 2>/dev/null | paste -sd" " | sed "s/^/Services (mariadb mysql apache2 koha-common): /"'
run sh -c 'systemctl get-default; echo "Sleep/suspend targets: $(systemctl is-enabled sleep.target suspend.target 2>/dev/null | paste -sd" ")"'
run sh -c 'last -x reboot shutdown 2>/dev/null | head -12'

# ------------------------------------------------------------ network
section "Network (can this computer reach GitHub?)"
for u in https://github.com https://api.github.com/zen; do
  say "$u -> $(curl -sS -o /dev/null -m 15 -w 'HTTP %{http_code} in %{time_total}s' "$u" 2>&1)"
done
# Proxy settings, with any user name/password removed.
for f in /etc/environment /etc/apt/apt.conf /etc/apt/apt.conf.d/*proxy*; do
  [ -r "$f" ] && grep -i proxy "$f" 2>/dev/null | sed -E 's#://[^ ]*@#://#; s#^#'"$f"': #' | tee -a "$REPORT"
done
env | grep -i '_proxy=' | sed -E 's#://[^ ]*@#://#' | tee -a "$REPORT"

# ------------------------------------------------------------ Koha instances
koha_conf() {   # koha_conf <file> <field>: a field of the <config> section (never used for the password)
  python3 -c 'import sys, xml.etree.ElementTree as E
c = E.parse(sys.argv[1]).getroot().find("config")
print(c.findtext(sys.argv[2], "").strip() if c is not None else "")' "$1" "$2" 2>/dev/null
}
section "Koha"
INSTANCES="$(koha-list 2>/dev/null || true)"
say "Instances: ${INSTANCES:-none found by koha-list}"
say "Enabled:   $(koha-list --enabled 2>/dev/null | paste -sd' ')"
INST="${1:-$(koha-list --enabled 2>/dev/null | head -1)}"
INST="${INST:-$(echo "$INSTANCES" | head -1)}"
say "Surveying instance: ${INST:-?}"
CONF="/etc/koha/sites/$INST/koha-conf.xml"
DB=""
if [ -n "$INST" ] && [ -r "$CONF" ]; then
  # Only the database name, host and port of the <config> section. The password is never read out.
  DB="$(koha_conf "$CONF" database)"
  say "Database name: $DB"
  say "Database host: $(koha_conf "$CONF" hostname)  port: $(koha_conf "$CONF" port)"
else
  say "Koha settings file not found at $CONF"
fi

# How to query: as the database administrator if that works, else with Koha's own login.
if [ -n "$DB" ] && mysql -e "SELECT 1" "$DB" >/dev/null 2>&1; then
  say "Database administrator access (sudo mysql): yes, $(mysql -N -e 'SELECT CONCAT(VERSION(), " as ", CURRENT_USER())')"
  q() { mysql --table "$DB" -e "$1" 2>&1 | tee -a "$REPORT"; }
  qraw() { mysql --batch "$DB" -e "$1"; }
elif [ -n "$INST" ] && command -v koha-mysql >/dev/null; then
  say "Database administrator access (sudo mysql): NO (using koha-mysql instead)"
  q() { printf '%s\n' "$1" | koha-mysql "$INST" 2>&1 | tee -a "$REPORT"; }
  qraw() { printf '%s\n' "$1" | koha-mysql "$INST"; }
else
  say "Cannot open Koha's database. Stopping here."; exit 1
fi

section "Koha version and tables"
q "SELECT value AS koha_version FROM systempreferences WHERE variable='Version'"
q "SELECT table_name, column_name, data_type FROM information_schema.columns
   WHERE table_schema = DATABASE() AND table_name IN ('items','biblio','biblioitems')
   ORDER BY table_name, ordinal_position"
q "SELECT table_name, table_rows AS approx_rows FROM information_schema.tables
   WHERE table_schema = DATABASE() AND table_name IN ('biblio','biblioitems','biblio_metadata','items','issues','old_issues','deleteditems')"

section "Books and copies"
q "SELECT COUNT(*) AS titles FROM biblio"
q "SELECT COUNT(*) AS copies, SUM(onloan IS NOT NULL) AS onloan_set, SUM(IFNULL(itemlost,0)<>0) AS lost,
          SUM(IFNULL(withdrawn,0)<>0) AS withdrawn, SUM(IFNULL(notforloan,0)<>0) AS not_for_loan,
          SUM(IFNULL(damaged,0)<>0) AS damaged FROM items"
q "SELECT copies_per_title, COUNT(*) AS titles FROM
   (SELECT COUNT(*) AS copies_per_title FROM items GROUP BY biblionumber) t GROUP BY copies_per_title ORDER BY 1 LIMIT 15"
q "SELECT COUNT(*) AS titles_without_copies FROM biblio b WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.biblionumber=b.biblionumber)"
q "SELECT COUNT(*) AS empty_title FROM biblio WHERE IFNULL(TRIM(title),'')=''"
q "SELECT COUNT(*) AS empty_author FROM biblio WHERE IFNULL(TRIM(author),'')=''"
q "SELECT COUNT(*) AS with_isbn FROM biblioitems WHERE IFNULL(TRIM(isbn),'')<>''"
q "SELECT COUNT(*) AS same_title_author_groups, SUM(n) AS records_in_them FROM
   (SELECT COUNT(*) n FROM biblio GROUP BY LOWER(TRIM(title)), LOWER(TRIM(IFNULL(author,''))) HAVING n>1) t"
q "SELECT biblionumber, title, author FROM biblio ORDER BY RAND() LIMIT 20"
q "SELECT YEAR(dateaccessioned) AS year_added, COUNT(*) AS copies FROM items GROUP BY 1 ORDER BY 1"

section "Barcodes"
q "SELECT COUNT(*) AS copies, SUM(IFNULL(TRIM(barcode),'')='') AS without_barcode,
          COUNT(DISTINCT barcode) AS distinct_barcodes FROM items"
q "SELECT barcode, COUNT(*) AS copies FROM items WHERE IFNULL(barcode,'')<>'' GROUP BY barcode HAVING COUNT(*)>1 LIMIT 10"
q "SELECT barcode FROM items ORDER BY RAND() LIMIT 20"
say "Barcode shapes (each digit shown as 9):"
qraw "SELECT IFNULL(barcode,'') FROM items" | tail -n +2 | sed 's/[0-9]/9/g' | sort | uniq -c | sort -rn | head -20 | tee -a "$REPORT"
q "SELECT DATE_FORMAT(timestamp,'%Y-%m') AS month_last_edited, COUNT(*) AS copies FROM items GROUP BY 1 ORDER BY 1"

section "Fields that might hold the OLD barcodes or the genre"
for col in stocknumber copynumber itemcallnumber itemnotes cn_source uri; do
  q "SELECT '$col' AS field, COUNT(*) AS filled_in FROM items WHERE IFNULL(TRIM($col),'')<>''"
done
# Samples only of short code-like fields; free-text notes and links may hold names, so they are only counted.
for col in stocknumber copynumber itemcallnumber cn_source; do
  q "SELECT $col AS sample_values FROM items WHERE IFNULL(TRIM($col),'')<>'' AND CHAR_LENGTH($col)<=20 ORDER BY RAND() LIMIT 8"
done
q "SELECT 'itemnotes_nonpublic' AS field, COUNT(*) AS filled_in FROM items WHERE IFNULL(TRIM(itemnotes_nonpublic),'')<>''"
q "SELECT 'more_subfields_xml' AS field, COUNT(*) AS filled_in FROM items WHERE IFNULL(TRIM(more_subfields_xml),'')<>''"
q "SELECT i.itype, t.description, COUNT(*) AS copies FROM items i LEFT JOIN itemtypes t ON t.itemtype=i.itype
   GROUP BY 1,2 ORDER BY 3 DESC LIMIT 40"
q "SELECT i.ccode AS collection_code, a.lib AS description, COUNT(*) AS copies FROM items i
   LEFT JOIN authorised_values a ON a.category='CCODE' AND a.authorised_value=i.ccode GROUP BY 1,2 ORDER BY 3 DESC LIMIT 40"
q "SELECT i.location AS shelving_location, a.lib AS description, COUNT(*) AS copies FROM items i
   LEFT JOIN authorised_values a ON a.category='LOC' AND a.authorised_value=i.location GROUP BY 1,2 ORDER BY 3 DESC LIMIT 40"
if qraw "SELECT 1 FROM biblio_metadata LIMIT 1" >/dev/null 2>&1; then
  q "SELECT SUM(metadata LIKE '%tag=\"650\"%') AS with_subject_650, SUM(metadata LIKE '%tag=\"082\"%') AS with_dewey_082,
            SUM(metadata LIKE '%tag=\"655\"%') AS with_genre_655 FROM biblio_metadata"
  q "SELECT ExtractValue(metadata,'//datafield[@tag=\"650\"][1]/subfield[@code=\"a\"]') AS subject, COUNT(*) AS titles
     FROM biblio_metadata GROUP BY 1 ORDER BY 2 DESC LIMIT 30"
  q "SELECT ExtractValue(metadata,'//datafield[@tag=\"655\"][1]/subfield[@code=\"a\"]') AS genre_655, COUNT(*) AS titles
     FROM biblio_metadata GROUP BY 1 ORDER BY 2 DESC LIMIT 20"
fi

section "Loans (counts and dates only, no members)"
q "SELECT COUNT(*) AS current_loans, MIN(date_due) AS earliest_due, MAX(date_due) AS latest_due FROM issues"
q "SELECT COUNT(*) AS loans_where_item_onloan_is_empty FROM issues s JOIN items i ON i.itemnumber=s.itemnumber WHERE i.onloan IS NULL"
q "SELECT COUNT(*) AS items_onloan_without_a_loan FROM items i WHERE i.onloan IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM issues s WHERE s.itemnumber=i.itemnumber)"
q "SELECT DATE(issuedate) AS day, COUNT(*) AS issued FROM
   (SELECT issuedate FROM issues UNION ALL SELECT issuedate FROM old_issues) t
   WHERE issuedate > NOW() - INTERVAL 45 DAY GROUP BY 1 ORDER BY 1"
q "SELECT HOUR(issuedate) AS hour_of_day, COUNT(*) AS issued_last_year FROM
   (SELECT issuedate FROM issues UNION ALL SELECT issuedate FROM old_issues) t
   WHERE issuedate > NOW() - INTERVAL 1 YEAR GROUP BY 1 ORDER BY 1"
q "SELECT DATE(MAX(returndate)) AS last_return_recorded FROM old_issues"

# ------------------------------------------------------------ book list
section "Book list"
qraw "SELECT i.biblionumber, i.itemnumber, IFNULL(i.barcode,'') AS barcode, IFNULL(b.title,'') AS title,
             IFNULL(b.author,'') AS author, IFNULL(bi.isbn,'') AS isbn, IFNULL(i.itype,'') AS itype,
             IFNULL(i.ccode,'') AS ccode, IFNULL(i.location,'') AS location, IFNULL(i.itemcallnumber,'') AS callnumber,
             IFNULL(i.stocknumber,'') AS stocknumber, IFNULL(i.copynumber,'') AS copynumber,
             IFNULL(i.itemlost,0) AS lost, IFNULL(i.withdrawn,0) AS withdrawn, IFNULL(i.dateaccessioned,'') AS added
      FROM items i JOIN biblio b ON b.biblionumber=i.biblionumber
      LEFT JOIN biblioitems bi ON bi.biblionumber=i.biblionumber
      ORDER BY i.biblionumber, i.itemnumber" > "$OUT/koha-books.tsv"
say "Wrote $(($(wc -l < "$OUT/koha-books.tsv") - 1)) copies to koha-books.tsv (titles, authors, barcodes; no members, no loans)."

[ -n "${SUDO_USER:-}" ] && chown -R "$SUDO_USER": "$OUT"
section "Done"
say "Report: $REPORT"
