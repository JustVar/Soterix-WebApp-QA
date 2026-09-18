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
# here can do one thing: sftp into /data/qa/runs. It has no shell, no
# password, no port forwarding and no sudo.
set -eu
USER_NAME=qa-publish
GROUP=qa-runs
RUNS=/data/qa/runs
SSHD_DROPIN=/etc/ssh/sshd_config.d/qa-publish.conf
KEYS="/home/$USER_NAME/.ssh/authorized_keys"

[ "$(id -u)" = 0 ] || { echo "run this with sudo"; exit 1; }

if [ "${1:-}" = "add-key" ]; then
  key_file="${2:?give the public key file}"
  # One key in the file, and it must parse as a public key.
  ssh-keygen -l -f "$key_file" > /dev/null || { echo "$key_file is not a public key"; exit 1; }
  grep -qxF "$(cat "$key_file")" "$KEYS" 2>/dev/null && { echo "that key is already installed"; exit 0; }
  cat "$key_file" >> "$KEYS"
  chown "$USER_NAME:$USER_NAME" "$KEYS" && chmod 600 "$KEYS"
  echo "added: $(ssh-keygen -l -f "$key_file")"
  exit 0
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

# 2. The served directory: the group may add folders, and a new folder gets
#    the group (setgid). The folders of the nightly stay writable by soterix
#    alone, so a laptop cannot replace a nightly run.
chgrp "$GROUP" "$RUNS"
chmod 2775 "$RUNS"

# 3. sshd: sftp only, into the served directory, files group-writable so the
#    nightly (soterix) and the prune can manage what a laptop published.
cat > "$SSHD_DROPIN.new" <<EOF
# Installed by deploy/spartan1/setup-publish-user.sh (Soterix-WebApp-QA).
Match User $USER_NAME
    ForceCommand internal-sftp -d $RUNS -u 0002
    PasswordAuthentication no
    PermitTTY no
    AllowTcpForwarding no
    AllowAgentForwarding no
    X11Forwarding no
EOF
mv "$SSHD_DROPIN.new" "$SSHD_DROPIN"
if ! sshd -t; then
  echo "sshd refused the new file: removing it, nothing was reloaded"
  rm -f "$SSHD_DROPIN"
  exit 1
fi
# The Match block must apply to the publish account only. If it reached
# user soterix, the next ssh login to the box would get sftp and no shell.
if sshd -T -C user=soterix,host=spartan1,addr=10.2.0.1 | grep -qi '^forcecommand internal-sftp'; then
  echo "the sftp-only rule would also apply to user soterix: removing it, nothing was reloaded"
  rm -f "$SSHD_DROPIN"
  exit 1
fi
systemctl reload ssh

echo "done. Next: sudo sh $0 add-key <person>.pub   (one time for each laptop)"
echo "check from a laptop:  sftp $USER_NAME@10.2.0.2   (pwd must print $RUNS)"
echo "check that a shell is refused:  ssh $USER_NAME@10.2.0.2 id   (must not print a uid)"
