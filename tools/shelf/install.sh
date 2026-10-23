#!/usr/bin/env bash
# Sets up the shelf sync on the club computer (Ubuntu with Koha). Run once:
#
#   sudo bash tools/shelf/install.sh <koha-instance> <github-owner/shelf-repo>
#   e.g. sudo bash tools/shelf/install.sh bookclubiitk shubhamkmaurya03/bookclub-shelf
#
# It creates:
#   - a system account "bookclub-shelf" that runs the sync and holds the token
#   - a read-only database login that can see only these columns:
#       items(itemnumber, biblionumber, barcode, dateaccessioned, onloan, itemlost, withdrawn)
#       biblio(biblionumber, title, author)   biblioitems(biblionumber, isbn)
#       issues(itemnumber, issuedate)   old_issues(itemnumber, issuedate)   (loan dates, to count borrowing)
#     and nothing about members
#   - /etc/bookclub-shelf/ (settings, database login, GitHub token; readable only by that account)
#   - a systemd timer that runs the sync every 2 minutes while the computer is on
#
# Running it again is safe: it replaces the database password and the program, and keeps the token
# unless you choose to replace it.
set -euo pipefail

INSTANCE="${1:-}"; REPO="${2:-}"
if [[ ! "$INSTANCE" =~ ^[a-z0-9_-]+$ ]] || [[ ! "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  sed -n '2,6p' "$0"; exit 1
fi
[ "$(id -u)" -eq 0 ] || { echo "Please run with sudo."; exit 1; }
for c in python3 mysql systemctl; do command -v "$c" >/dev/null || { echo "Missing: $c"; exit 1; }; done

HERE="$(cd "$(dirname "$0")" && pwd)"
ACCOUNT=bookclub-shelf
DBUSER=bookclub_shelf
ETC=/etc/bookclub-shelf
APP=/opt/bookclub-shelf

# Koha's database name, from the <config> section of the instance's settings (the file also has
# Zebra <database> entries, which are not it). Only the name is read, never the password.
koha_conf() {   # koha_conf <file> <field>: a field of the <config> section (never used for the password)
  python3 -c 'import sys, xml.etree.ElementTree as E
c = E.parse(sys.argv[1]).getroot().find("config")
print(c.findtext(sys.argv[2], "").strip() if c is not None else "")' "$1" "$2" 2>/dev/null
}
CONF="/etc/koha/sites/$INSTANCE/koha-conf.xml"
DB=""
[ -r "$CONF" ] && DB="$(koha_conf "$CONF" database)"
DB="${DB:-koha_$INSTANCE}"
[[ "$DB" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "Unexpected database name: $DB"; exit 1; }

# Database administrator login, needed once to create the read-only login: MySQL's root through
# sudo, else Ubuntu's maintenance login, else ask for the root password.
ADMIN_CNF=""
cleanup() { [ -n "$ADMIN_CNF" ] && rm -f "$ADMIN_CNF"; }
trap cleanup EXIT
if mysql -e "SELECT 1" >/dev/null 2>&1; then
  dbadmin() { mysql "$@"; }
elif [ -r /etc/mysql/debian.cnf ] && mysql --defaults-file=/etc/mysql/debian.cnf -e "SELECT 1" >/dev/null 2>&1; then
  dbadmin() { mysql --defaults-file=/etc/mysql/debian.cnf "$@"; }
else
  IFS= read -r -s -p "MySQL administrator (root) password: " ROOTPW; echo
  # Kept in /run (memory, never written to disk) and deleted on exit; quoted so any character works.
  ADMIN_CNF="$(umask 077; mktemp -p /run bookclub-shelf.XXXXXX)"
  ROOTPW="${ROOTPW//\\/\\\\}"; ROOTPW="${ROOTPW//\"/\\\"}"
  printf '[client]\nuser=root\npassword="%s"\n' "$ROOTPW" > "$ADMIN_CNF"; unset ROOTPW
  dbadmin() { mysql --defaults-extra-file="$ADMIN_CNF" "$@"; }
fi
dbadmin -e "SELECT 1 FROM \`$DB\`.items LIMIT 1" >/dev/null || {
  echo "Cannot reach Koha's database '$DB' as the database administrator."; exit 1; }
echo "Koha database: $DB"

# 1. System account (no login, no home folder).
id "$ACCOUNT" >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin "$ACCOUNT"

# 2. Read-only database login, limited to the columns the sync needs.
PASS="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
dbadmin <<SQL
DROP USER IF EXISTS '$DBUSER'@'localhost';
CREATE USER '$DBUSER'@'localhost' IDENTIFIED BY '$PASS';
GRANT SELECT (itemnumber, biblionumber, barcode, dateaccessioned, onloan, itemlost, withdrawn) ON \`$DB\`.\`items\` TO '$DBUSER'@'localhost';
GRANT SELECT (biblionumber, title, author) ON \`$DB\`.\`biblio\` TO '$DBUSER'@'localhost';
GRANT SELECT (biblionumber, isbn) ON \`$DB\`.\`biblioitems\` TO '$DBUSER'@'localhost';
GRANT SELECT (itemnumber, issuedate) ON \`$DB\`.\`issues\` TO '$DBUSER'@'localhost';
GRANT SELECT (itemnumber, issuedate) ON \`$DB\`.\`old_issues\` TO '$DBUSER'@'localhost';
SQL

# 3. Settings, database login and token, readable only by the sync account.
install -d -m 750 -o root -g "$ACCOUNT" "$ETC"
umask 077
printf '[client]\nuser=%s\npassword=%s\nhost=localhost\n' "$DBUSER" "$PASS" > "$ETC/my.cnf"
python3 - "$ETC/config.json" "$REPO" "$DB" <<'PY'
import json, sys
json.dump({"repo": sys.argv[2], "database": sys.argv[3]}, open(sys.argv[1], "w"), indent=2)
PY
[ -f "$ETC/env" ] || printf '# Add a line like https_proxy=http://host:port here if this computer needs a proxy.\n' > "$ETC/env"
NEWTOKEN=yes
if [ -s "$ETC/token" ]; then
  read -r -p "A GitHub token is already saved. Replace it? [y/N] " ans
  [[ "$ans" =~ ^[Yy] ]] || NEWTOKEN=""
fi
if [ -n "$NEWTOKEN" ]; then
  IFS= read -r -s -p "Paste the GitHub token for $REPO (input is hidden): " TOKEN; echo
  # Fine-grained tokens only (limited to one repository); a classic ghp_ token reaches every repository.
  [[ "$TOKEN" =~ ^github_pat_[A-Za-z0-9_]+$ ]] || {
    echo "That is not a fine-grained GitHub token (it should start with github_pat_). Nothing was changed."; exit 1; }
  # Check it can write before the saved one is replaced (the token goes through stdin, never the command line):
  # a "token-check" event needs Contents: Read and write, and no workflow reacts to that name.
  printf '%s' "$TOKEN" | python3 -c 'import sys, urllib.request
req = urllib.request.Request("https://api.github.com/repos/" + sys.argv[1] + "/dispatches", method="POST",
    data=b"{\"event_type\": \"token-check\"}", headers={"Authorization": "Bearer " + sys.stdin.read().strip(),
    "Accept": "application/vnd.github+json", "User-Agent": "bookclub-shelf-install"})
try:
    urllib.request.urlopen(req, timeout=30).close()
except Exception as e:   # 401: wrong or expired; 403/404: no write access to this repository
    sys.exit("GitHub did not accept the token for %s (%s)." % (sys.argv[1], getattr(e, "code", e)))' "$REPO" || {
    echo "Nothing was changed. (If GitHub could not be reached, log in to the IITK firewall and try again.)"; exit 1; }
  printf '%s\n' "$TOKEN" > "$ETC/token"; unset TOKEN
fi
chown root:"$ACCOUNT" "$ETC"/my.cnf "$ETC"/config.json "$ETC"/token "$ETC"/env
chmod 640 "$ETC"/my.cnf "$ETC"/config.json "$ETC"/token "$ETC"/env
umask 022

# 4. The program (owned by root, so the sync account cannot change it).
install -d -m 755 "$APP"
install -m 755 "$HERE/shelf_sync.py" "$APP/shelf_sync.py"

# 5. Every 2 minutes while the computer is on.
cat > /etc/systemd/system/bookclub-shelf.service <<UNIT
[Unit]
Description=Book Club shelf status sync (Koha to website)
After=network-online.target mysql.service mariadb.service
Wants=network-online.target

[Service]
Type=oneshot
User=$ACCOUNT
Group=$ACCOUNT
EnvironmentFile=-$ETC/env
ExecStart=/usr/bin/python3 $APP/shelf_sync.py
StateDirectory=bookclub-shelf
TimeoutStartSec=5min
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
RestrictNamespaces=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
CapabilityBoundingSet=
UNIT
cat > /etc/systemd/system/bookclub-shelf.timer <<UNIT
[Unit]
Description=Run the Book Club shelf sync every 2 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=2min
AccuracySec=10s

[Install]
WantedBy=timers.target
UNIT
install -d -m 755 -o "$ACCOUNT" -g "$ACCOUNT" /var/lib/bookclub-shelf
systemctl daemon-reload

# 6. Test, then start.
echo "Testing the database login…"
sudo -u "$ACCOUNT" python3 "$APP/shelf_sync.py" --dry-run
echo "Sending the first update to GitHub…"
sudo -u "$ACCOUNT" bash -c "set -a; . '$ETC/env'; exec python3 '$APP/shelf_sync.py' --force"
chown -R "$ACCOUNT:$ACCOUNT" /var/lib/bookclub-shelf
# One full run (database, token and network) under the service's own sandboxed settings, so a problem shows up
# now rather than silently later. Forgetting the last state makes it send again instead of finding nothing new.
rm -f /var/lib/bookclub-shelf/state.json
systemctl start bookclub-shelf.service || {
  echo "The sync failed when run as a service. See: journalctl -u bookclub-shelf -n 30 --no-pager"; exit 1; }
systemctl enable --now bookclub-shelf.timer
echo
echo "Done. The shelf status now updates every 2 minutes while this computer is on."
echo "  Check it:        systemctl list-timers bookclub-shelf.timer"
echo "  Recent activity: journalctl -u bookclub-shelf --since today"
