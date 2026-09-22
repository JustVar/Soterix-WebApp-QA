#!/bin/sh
# Give each CI runner its own Unix user.
#
# Why: 3 runners, 3 different repos, 1 user. The directory modes (750) and the credential modes
# (600) keep OTHER users out, and every CI job IS that user, so a job in repo A could read repo
# B's runner credentials: its OAuth client id and RSA private key. With those it can mint B's
# runner token, take B's jobs and take the secrets delivered to them (audit 09/22/2026).
#
# After this, a job can still reach its own repo's credentials. That is unavoidable, and it is
# why a pull request no longer runs here at all.
#
# Run as root on spartan1. Safe to run again: it skips what is already done.
set -eu

for spec in \
  "/opt/actions-runner:ghrunner-shared" \
  "/opt/actions-runner-webapp:ghrunner-webapp" \
  "/opt/actions-runner-api:ghrunner-api"
do
  dir=${spec%%:*}
  user=${spec#*:}
  [ -d "$dir" ] || { echo "$dir is not there, skipped"; continue; }
  unit=$(ls /etc/systemd/system/actions.runner.*.service 2>/dev/null \
         | xargs -r grep -l "WorkingDirectory=$dir\$" 2>/dev/null | head -1)
  [ -n "$unit" ] || { echo "$dir: no unit found, skipped"; continue; }
  name=$(basename "$unit")

  if ! id "$user" >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash "$user"
    echo "created $user"
  fi

  systemctl stop "$name" 2>/dev/null || true
  ( cd "$dir" && ./svc.sh uninstall >/dev/null 2>&1 ) || true

  # The runner's own tree, and the ssh material it needs for the private shared package.
  chown -R "$user:$user" "$dir"
  chmod 700 "$dir"
  if [ -d /home/ghrunner/.ssh ] && [ ! -d "/home/$user/.ssh" ]; then
    cp -a /home/ghrunner/.ssh "/home/$user/.ssh"
    chown -R "$user:$user" "/home/$user/.ssh"
    chmod 700 "/home/$user/.ssh"
  fi
  if [ -f /home/ghrunner/.gitconfig ] && [ ! -f "/home/$user/.gitconfig" ]; then
    cp -a /home/ghrunner/.gitconfig "/home/$user/.gitconfig"
    chown "$user:$user" "/home/$user/.gitconfig"
  fi

  ( cd "$dir" && ./svc.sh install "$user" >/dev/null 2>&1 && ./svc.sh start >/dev/null 2>&1 ) || true
  echo "$name -> $user, $(systemctl is-active "$name")"
done

echo "--- each runner must now be refused the others' credentials ---"
for a in ghrunner-shared ghrunner-webapp ghrunner-api; do
  for d in /opt/actions-runner /opt/actions-runner-webapp /opt/actions-runner-api; do
    own=$(stat -c %U "$d" 2>/dev/null || echo "?")
    if sudo -n -u "$a" test -r "$d/.credentials_rsaparams" 2>/dev/null; then
      [ "$own" = "$a" ] && echo "  $a reads its own $d: correct" \
                        || echo "  $a READS $d (owned by $own): PROBLEM"
    fi
  done
done
