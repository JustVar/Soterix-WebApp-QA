#!/bin/sh
# One-time setup of the publish-only account on spartan1. Run it with sudo.
# It is safe to run again: each step checks before it changes something.
#
#   sudo sh setup-publish-user.sh                 # create the account
#   sudo sh setup-publish-user.sh add-key FILE    # add one person's public key
#
# Why: tools/publish_run.py copied runs to the box as user soterix. That user
# owns the nightly, the clone and the .env with the tenant passwords, so each
# laptop key that could publish a run could also read those. The account
# here can do one thing: sftp into a jail that holds the served run folders
# and nothing else. It has no shell, no password, no port forwarding and no
# sudo, and it cannot see the rest of the box (the clone keeps trace zips,
# which hold session cookies).
set -eu
USER_NAME=qa-publish
GROUP=qa-runs
RUNS=/data/qa/runs
JAIL=/srv/qa-publish          # root-owned, as sshd's ChrootDirectory requires
JAIL_RUNS="$JAIL/runs"        # $RUNS, bind-mounted: what the account sees as /runs
ENV_FILE=/data/qa/ci/Soterix-WebApp-QA/.env
SSHD_DROPIN=/etc/ssh/sshd_config.d/qa-publish.conf
KEYS="/home/$USER_NAME/.ssh/authorized_keys"

[ "$(id -u)" = 0 ] || { echo "run this with sudo"; exit 1; }

if [ "${1:-}" = "add-key" ]; then
  key_file="${2:?give the public key file}"
  # Exactly 1 line, and it must be a PUBLIC key: ssh-keygen -l also accepts a
  # private key file, and a file with no last newline glued 2 keys together.
  [ "$(grep -c . "$key_file")" = 1 ] || { echo "$key_file must hold exactly 1 key, on 1 line"; exit 1; }
  key=$(tr -d '\r' < "$key_file" | grep . | head -n 1)
  case "$key" in
    ssh-ed25519\ *|ssh-rsa\ *|ecdsa-sha2-*\ *|sk-ssh-ed25519@openssh.com\ *|sk-ecdsa-sha2-*\ *) ;;
    *) echo "$key_file is not a public key file (it must start with the key type, for example ssh-ed25519)"; exit 1 ;;
  esac
  printf '%s\n' "$key" | ssh-keygen -l -f - > /dev/null || { echo "$key_file does not parse as a public key"; exit 1; }
  if grep -qxF "$key" "$KEYS" 2>/dev/null; then echo "that key is already installed"; exit 0; fi
  printf '%s\n' "$key" >> "$KEYS"
  chown "$USER_NAME:$USER_NAME" "$KEYS" && chmod 600 "$KEYS"
  echo "added: $(printf '%s\n' "$key" | ssh-keygen -l -f -)"
  exit 0
fi

# 0. The secrets of the box must not be readable by a new account.
if [ -f "$ENV_FILE" ] && [ "$(stat -c %a "$ENV_FILE")" != 600 ]; then
  echo "$ENV_FILE has mode $(stat -c %a "$ENV_FILE"): setting it to 600"
  chmod 600 "$ENV_FILE"
fi

# 1. The group that may write run folders, and the account.
getent group "$GROUP" > /dev/null || groupadd "$GROUP"
if ! id "$USER_NAME" > /dev/null 2>&1; then
  useradd --create-home --shell /usr/sbin/nologin --groups "$GROUP" "$USER_NAME"
  passwd -l "$USER_NAME" > /dev/null
fi
usermod -aG "$GROUP" soterix
install -d -m 700 -o "$USER_NAME" -g "$USER_NAME" "/home/$USER_NAME/.ssh"
[ -f "$KEYS" ] || install -m 600 -o "$USER_NAME" -g "$USER_NAME" /dev/null "$KEYS"

# 2. The served directory. The group may add folders (g+w), a new folder gets
#    the group (setgid), and only the owner of a folder may rename or remove
#    it (sticky). Without the sticky bit, write access to this directory
#    alone let a laptop move a nightly run away, or replace index.html.
chgrp "$GROUP" "$RUNS"
chmod 3775 "$RUNS"

# 3. The jail. sshd refuses a chroot that root does not own, so the served
#    directory is bind-mounted into a root-owned folder.
install -d -m 755 -o root -g root "$JAIL"
# Not when it is mounted: install -d on the mount point is a chmod of /data/qa/runs itself, and a
# second run of this script took its sticky bit and its group write away (audit 09/21/2026).
mountpoint -q "$JAIL_RUNS" || install -d -m 755 "$JAIL_RUNS"
grep -qs "^$RUNS $JAIL_RUNS " /etc/fstab || echo "$RUNS $JAIL_RUNS none bind 0 0" >> /etc/fstab
mountpoint -q "$JAIL_RUNS" || mount "$JAIL_RUNS"
chmod 3775 "$RUNS"   # after the mount too: the mode is the last word of steps 2 and 3

# 4. sshd: sftp only, inside the jail. What a laptop publishes belongs to
#    the account with the modes the laptop sent (644 and 755, measured), so
#    only root removes it: the prune does, or a person with sudo.
probe() { sshd -T -C "user=$1,host=spartan1,addr=10.2.0.1"; }
before=$(probe soterix) || { echo "sshd -T failed before any change: nothing was changed"; exit 1; }
cat > "$SSHD_DROPIN.new" <<EOF
# Installed by deploy/spartan1/setup-publish-user.sh (Soterix-WebApp-QA).
Match User $USER_NAME
    ChrootDirectory $JAIL
    ForceCommand internal-sftp -d /runs -u 0002
    PasswordAuthentication no
    PermitTTY no
    AllowTcpForwarding no
    AllowAgentForwarding no
    X11Forwarding no
EOF
mv "$SSHD_DROPIN.new" "$SSHD_DROPIN"
undo() { echo "$1: removing $SSHD_DROPIN, sshd was not reloaded"; rm -f "$SSHD_DROPIN"; exit 1; }
sshd -t || undo "sshd refused the new file"
# The rule must change nothing for user soterix. If it did, the next ssh
# login to the box would get sftp and no shell.
after=$(probe soterix) || undo "sshd -T failed with the new file"
[ "$before" = "$after" ] || undo "the new file changes the settings of user soterix"
# And it must apply to the publish account. It does not when sshd_config has
# no Include line for sshd_config.d, and then the account is not confined.
mine=$(probe "$USER_NAME") || undo "sshd -T failed for $USER_NAME"
echo "$mine" | grep -qi '^forcecommand internal-sftp' || undo "the sftp-only rule does not apply to $USER_NAME"
echo "$mine" | grep -qi "^chrootdirectory $JAIL" || undo "the jail does not apply to $USER_NAME"
echo "$mine" | grep -qi '^allowtcpforwarding no' || undo "port forwarding is not off for $USER_NAME"
systemctl reload ssh || systemctl reload sshd

echo "done. Next: sudo sh $0 add-key <person>.pub   (one time for each laptop)"
echo "check from a laptop:  sftp $USER_NAME@10.2.0.2   ('pwd' must print /runs, and 'ls /' must show runs only)"
echo "check that a shell is refused:  ssh $USER_NAME@10.2.0.2 id   (must not print a uid)"
