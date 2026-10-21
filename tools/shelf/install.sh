#!/usr/bin/env bash
# Sets up the shelf sync on the club computer (Ubuntu with Koha). Run once:
#
#   sudo bash tools/shelf/install.sh <koha-instance> <github-owner/shelf-repo>
#   e.g. sudo bash tools/shelf/install.sh library shubhamkmaurya03/bookclub-shelf
#
# It creates:
#   - a system account "bookclub-shelf" that runs the sync and holds the token
#   - a read-only database login that can see only these columns:
#       items(itemnumber, biblionumber, onloan, itemlost, withdrawn)
#       biblio(biblionumber, title, author)   biblioitems(biblionumber, isbn)
#     and nothing about members
#   - /etc/bookclub-shelf/ (settings, database login, GitHub token; readable only by that account)
#   - a systemd timer that runs the sync every 2 minutes while the computer is on
#
# Running it again is safe: it replaces the database password and the program, and keeps the token
# unless you choose to replace it.
set -euo pipefail

INSTANCE="${1:-}"; REPO="${2:-}"
if [ -z "$INSTANCE" ] || [[ ! "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  sed -n '2,6p' "$0"; exit 1
fi
[ "$(id -u)" -eq 0 ] || { echo "Please run with sudo."; exit 1; }
for c in python3 mysql systemctl; do command -v "$c" >/dev/null || { echo "Missing: $c"; exit 1; }; done

HERE="$(cd "$(dirname "$0")" && pwd)"
ACCOUNT=bookclub-shelf
DBUSER=bookclub_shelf
ETC=/etc/bookclub-shelf
APP=/opt/bookclub-shelf

# Koha's database name, from the instance's settings (only the name is read, never the password).
CONF="/etc/koha/sites/$INSTANCE/koha-conf.xml"
DB=""
[ -r "$CONF" ] && DB="$(sed -n 's:.*<database>\(.*\)</database>.*:\1:p' "$CONF" | head -1)"
DB="${DB:-koha_$INSTANCE}"
[[ "$DB" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "Unexpected database name: $DB"; exit 1; }
mysql -e "SELECT 1 FROM \`$DB\`.items LIMIT 1" >/dev/null || {
  echo "Cannot reach Koha's database '$DB' as the database administrator (sudo mysql)."; exit 1; }
echo "Koha database: $DB"

# 1. System account (no login, no home folder).
id "$ACCOUNT" >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin "$ACCOUNT"

# 2. Read-only database login, limited to the columns the sync needs.
PASS="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
mysql <<SQL
DROP USER IF EXISTS '$DBUSER'@'localhost';
CREATE USER '$DBUSER'@'localhost' IDENTIFIED BY '$PASS';
GRANT SELECT (itemnumber, biblionumber, onloan, itemlost, withdrawn) ON \`$DB\`.\`items\` TO '$DBUSER'@'localhost';
GRANT SELECT (biblionumber, title, author) ON \`$DB\`.\`biblio\` TO '$DBUSER'@'localhost';
GRANT SELECT (biblionumber, isbn) ON \`$DB\`.\`biblioitems\` TO '$DBUSER'@'localhost';
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
if [ -s "$ETC/token" ]; then
  read -r -p "A GitHub token is already saved. Replace it? [y/N] " ans
  [[ "$ans" =~ ^[Yy] ]] && rm -f "$ETC/token"
fi
if [ ! -s "$ETC/token" ]; then
  read -r -s -p "Paste the GitHub token for $REPO (input is hidden): " TOKEN; echo
  [[ "$TOKEN" =~ ^(github_pat_|ghp_)[A-Za-z0-9_]+$ ]] || { echo "That does not look like a GitHub token."; exit 1; }
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
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectHome=yes
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
systemctl enable --now bookclub-shelf.timer
echo
echo "Done. The shelf status now updates every 2 minutes while this computer is on."
echo "  Check it:        systemctl list-timers bookclub-shelf.timer"
echo "  Recent activity: journalctl -u bookclub-shelf --since today"
