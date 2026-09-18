#!/bin/sh
# One-time move of the QA run archive from http://10.2.0.2/qa-runs/ to
# https://10.2.0.2:8444/qa-runs/. Run it with sudo, from the clone:
#
#   cd /data/qa/ci/Soterix-WebApp-QA && sudo sh deploy/spartan1/setup-https-archive.sh
#
# It is safe to run again. It does 3 things, and it puts the old files back
# if nginx refuses the result:
#   1. installs the HTTPS site (nginx-qa-runs-site.conf) and enables it,
#   2. in the port 80 site, replaces the 2 /qa-runs/ blocks with a redirect
#      to the HTTPS site, so old links still work and no password goes over
#      plain HTTP,
#   3. tests the configuration and reloads nginx.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
SITE_SRC="$HERE/nginx-qa-runs-site.conf"
SITE=/etc/nginx/sites-available/qa-runs
LINK=/etc/nginx/sites-enabled/qa-runs
DEFAULT=/etc/nginx/sites-enabled/default
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="/etc/nginx/qa-runs-backup-$STAMP"

[ "$(id -u)" = 0 ] || { echo "run this with sudo"; exit 1; }
[ -f "$SITE_SRC" ] || { echo "not found: $SITE_SRC"; exit 1; }
[ -f /etc/ssl/asset-tracker/asset-tracker.crt ] || { echo "the box certificate is not at /etc/ssl/asset-tracker/"; exit 1; }

mkdir -p "$BACKUP"
cp -p "$(readlink -f "$DEFAULT")" "$BACKUP/default"
[ -f "$SITE" ] && cp -p "$SITE" "$BACKUP/qa-runs"
HAD_LINK=no
[ -e "$LINK" ] && HAD_LINK=yes

restore() {
  echo "nginx refused the new configuration: putting the old files back"
  cp -p "$BACKUP/default" "$(readlink -f "$DEFAULT")"
  if [ -f "$BACKUP/qa-runs" ]; then cp -p "$BACKUP/qa-runs" "$SITE"; else rm -f "$SITE"; fi
  [ "$HAD_LINK" = yes ] || rm -f "$LINK"
  nginx -t && systemctl reload nginx
  exit 1
}

# 1. The HTTPS site.
install -m 644 "$SITE_SRC" "$SITE"
ln -sfn "$SITE" "$LINK"

# 2. The port 80 site.
python3 "$HERE/nginx_port80_redirect.py" "$(readlink -f "$DEFAULT")" || restore

# 3. Test, then reload.
nginx -t || restore
systemctl reload nginx

echo "done. The old files are in $BACKUP."
echo "check:  curl -sk -o /dev/null -w '%{http_code}\n' https://10.2.0.2:8444/qa-runs/     (401: it asks for the password)"
echo "check:  curl -s  -o /dev/null -w '%{http_code} %{redirect_url}\n' http://10.2.0.2/qa-runs/   (301 to https://10.2.0.2:8444/qa-runs/)"
