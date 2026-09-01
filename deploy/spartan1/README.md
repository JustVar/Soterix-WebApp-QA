# spartan1 deployment

The CI host serving the run archive and running the nightly QA suite. These
files are the live configuration on spartan1 (10.2.0.2), version-controlled
here so they are auditable and recoverable rather than living only on the
box. The adversarial audit flagged that the nightly script was unauditable
because it existed nowhere in git.

## What runs on spartan1

| File here | Lives on the box at | What it does |
|---|---|---|
| `nightly.sh` | `/data/qa/ci/nightly.sh` | The nightly QA run: pull, install, pytest, publish evidence minus traces/videos. Cron at 04:00 America/Chicago. |
| `qa-runs-prune` | `/usr/local/bin/qa-runs-prune` | Deletes run folders older than 30 days. Cron at 03:00. |
| `nginx-qa-runs.conf` | inside `/etc/nginx/sites-enabled/default` | The `/qa-runs/` location: serves `/data/qa/runs` read-only, basic auth, dotfiles denied. |

## Access

- SSH alias `spartan1` = `soterix@10.2.0.2`.
- The archive is at `http://10.2.0.2/qa-runs/` behind HTTP basic auth (user
  `qa`; password in the team password store).
- Two read-only per-repo deploy keys on the box pull the repos over SSH.

## Deploying a change

These are copies for the record. To change what runs, edit the file ON THE
BOX and update the copy here (or copy this file up), then reload:

```bash
# nightly / prune: no reload needed, cron reads them each run
scp deploy/spartan1/nightly.sh spartan1:/tmp/ && \
  ssh spartan1 'sudo cp /tmp/nightly.sh /data/qa/ci/nightly.sh && sudo chmod 755 /data/qa/ci/nightly.sh'

# nginx: after editing /etc/nginx/sites-enabled/default
ssh spartan1 'sudo nginx -t && sudo systemctl reload nginx'
```

## Retention and safety

- Evidence is pruned after 30 days on the box. The permanent record is the
  git ledger (`history/*.jsonl`), not the evidence.
- Traces and videos never reach the box: they carry live session cookies
  and, on a fresh-login test, the account password. `nightly.sh` rsyncs with
  `--exclude=traces/ --exclude=*.webm`, and `tools/publish_run.py` stages a
  filtered copy. Keep traces local for `playwright show-trace`.
