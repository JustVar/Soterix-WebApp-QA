# The CI runners on spartan1

Written for: whoever keeps CI working.

GitHub charges for the minutes its own machines use. Ours do not. Since
09/22/2026 the 3 QA repos run their gates on spartan1 and bill nothing.

## What is installed

| Runner | Repo | Directory |
|---|---|---|
| `spartan1-1` | SOTERIX-QA-SHARED | `/opt/actions-runner` |
| `spartan1-webapp` | Soterix-WebApp-QA | `/opt/actions-runner-webapp` |
| `spartan1-api` | Soterix-API-QA | `/opt/actions-runner-api` |

GitHub scopes a runner to 1 repo, so each repo needs its own. Each runs as **its own user** (`ghrunner-shared`, `ghrunner-webapp`, `ghrunner-api`)
under systemd, because 1 shared user let a job in 1 repo read another repo's
runner credentials, and each has 1 runner, so the jobs of
1 workflow queue rather than run side by side. The jobs take seconds, so that
is a queue of seconds.

## What the runner account may and may not do

Each `ghrunner-*` user exists only for CI, and only for its own repo. A workflow file runs whatever it says, so the
account it runs as decides what a mistake can reach.

- None is `soterix`. That account owns the nightly, the `.env` with the
  tenant credentials, and the published archive.
- None can read `/data/qa/ci/Soterix-WebApp-QA/.env`, or `/opt/asset_tracker/.env`.
- None can write `/data/qa/runs`, the nightly clone, or `nightly.sh`.
- None has sudo, and none can read another runner's credentials.
- Its systemd services carry `CPUWeight=20`, `IOWeight=20` and
  `MemoryHigh=1500M`, `MemoryMax=3G` and `Restart=always`, so a CI job yields
  the machine to the nightly rather than competing with it, and a crash or an
  out-of-memory kill brings the runner back instead of leaving CI silently
  dead.

Check all of that at any time:

```bash
ssh spartan1 'for u in ghrunner-shared ghrunner-webapp ghrunner-api; do
  sudo -u $u test -r /data/qa/ci/Soterix-WebApp-QA/.env && echo "$u PROBLEM" || echo "$u ok"
  sudo -u $u test -w /data/qa/runs && echo "$u PROBLEM" || echo "$u ok"
done'
```

## The files on the box, and their copy here

Every file this setup puts on spartan1 has a copy in this folder. A box that is
rebuilt from the repo then comes back the same, and a change made by hand on the
box shows up as a difference against a file somebody can read.

| On the box | Here |
|---|---|
| `/etc/systemd/system/actions.runner.*.service.d/nice.conf` (one per runner) | `runner-nice.conf` |
| `/etc/logrotate.d/ci-runner-prune` | `logrotate.d-ci-runner-prune` |
| `/usr/local/bin/ci-runner-prune` | `ci-runner-prune` |
| `/etc/cron.d/qa-ci-prune` | `cron.d-qa-ci-prune` |

The drop-in is the same file for all 3 runners. Install it, or change it, for
each one:

```bash
scp deploy/spartan1/runner-nice.conf spartan1:/tmp/nice.conf
ssh spartan1 'for s in /etc/systemd/system/actions.runner.*.service; do
  d="$s.d"; sudo install -d "$d"; sudo cp /tmp/nice.conf "$d/nice.conf"
done; rm /tmp/nice.conf; sudo systemctl daemon-reload
sudo systemctl restart actions.runner.\*.service'
```

Read back what is really there, which is the check that matters:

```bash
ssh spartan1 'systemctl show actions.runner.\* -p Id -p MemoryHigh -p MemoryMax'
```

## How it reaches the private shared package

The gates install `soterix-qa-shared` from a private repo. Each user has a copy of the
key `~/.ssh/shared_ro`, registered on SOTERIX-QA-SHARED as a
**read-only** deploy key, plus `~/.ssh/config` pointing github.com at it and a
global git rewrite from the HTTPS url to the SSH one.

That key is read-only and reaches 1 repo. It cannot push anywhere.

The first attempt failed because `ghrunner` had no `known_hosts`, so every
clone failed host-key verification. The message git prints for that is "Please
make sure you have the correct access rights", which reads like a permission
problem and is not.

## What a job costs

Nothing. Check any run:

```bash
gh api repos/Soterix-Systems/SOTERIX-QA-SHARED/actions/runs/<id>/timing -q '.billable'
```

`{}` means it billed no minutes. A hosted run shows a `UBUNTU` entry instead.

GitHub bills each **job** rounded up to a whole minute, so a workflow of 5
jobs that each take 20 seconds costs 5 minutes. That is why the interpreter
matrices were cut to 1 version on a push.

## When the box is down

Every workflow takes a `hosted` input. Run it by hand with that ticked and it
goes to GitHub's machines:

```bash
gh workflow run ci.yml -R Soterix-Systems/SOTERIX-QA-SHARED -f hosted=true
```

There is also the repository variable `CI_RUNNER`. Set it to `hosted` and every
event goes to GitHub's machines, a push included. The `hosted` input above only
reaches a run somebody started by hand, so the variable is the one that helps
when the box dies and people keep pushing. It was exercised on the API repo on
09/22/2026 and does what it says. Remove it when the box is back, or every run
bills minutes again.

Nothing detects a dead box on its own. A queued job that never starts is the
symptom, and it is not an error, so nobody is told. GitHub cancels it after 24
hours.

## Keeping them alive

```bash
ssh spartan1 'systemctl list-units "actions.runner.*" --no-pager --plain'
gh api repos/Soterix-Systems/SOTERIX-QA-SHARED/actions/runners -q '.runners[] | .name + " " + .status'
```

A runner that says `offline` while its service is `active` usually lost its
registration. Register it again with a fresh token:

```bash
gh api -X POST repos/<owner>/<repo>/actions/runners/registration-token -q .token
```

Then, on the box, as root, from that runner's directory: `./config.sh --unattended
--url <repo url> --token <token> --name <name> --labels self-hosted,linux,x64,spartan1
--work _work --replace`, and `./svc.sh install ghrunner && ./svc.sh start`.

Do **not** pass `--ephemeral`. That runner takes 1 job, exits, and the service
stops with "no retry needed", because an ephemeral runner is consumed after
1 job and needs a fresh registration each time. A static machine wants a
persistent runner.

## A pull request never runs here

A workflow file is part of the branch it sits on, so anyone who can open a pull
request could otherwise run whatever they wrote, as the runner's own user, on
the box that runs the nightly, with the secrets that job is given. Pull
requests go to GitHub's machines, where that costs an attacker a throwaway
container.

## The weekly run goes to GitHub on purpose

spartan1 never uses the `QA_SHARED_DEPLOY_KEY` secret: `ghrunner` has its own key on disk and
`IdentitiesOnly yes` makes ssh ignore the agent. A revoked or wrong secret would pass green here
and fail only on the fallback, which is the 1 path used on a bad day.

So the Sunday run is hosted. It uses the secret, proves the fallback still works, and runs the
full interpreter matrix that a push no longer runs. About 15 job-minutes a week.

## What it costs the box

Measured 09/22/2026 on a 15 GB machine:

| | Memory |
|---|---|
| 3 idle listeners | about 450 MB, and that is the standing cost |
| 1 job, most of it pip | 790 MB on the smaller repos, and it reached 3.7 GB on the WebApp gate before the ceilings were set |

`MemoryHigh=1500M` is the working limit: above it the kernel reclaims from the
job rather than letting it grow, which costs the job a little speed and costs
the nightly nothing. `MemoryMax=3G` is the backstop that stops 1 job taking the
machine. The 3 together can reach 9 GB only if all 3 repos build at once, which
needs 3 pushes in the same seconds.

The peak is `pip`, not the tests. Each job installs into a venv of its own, so
nothing is shared between jobs except the download cache at
`each runner user's `~/.cache/pip``, which is 122 MB and is only downloaded files. That cache
is safe to keep: what leaked between jobs was installed packages, not downloads.

## The janitor

`/usr/local/bin/ci-runner-prune`, daily at 03:30 from `/etc/cron.d/qa-ci-prune`. It removes
`_work/_temp` entries older than 3 days, and on Sunday it clears `_work/_tool`, the interpreter
cache. It never touches `_work/<repo>`, which `actions/checkout` cleans itself.

Clearing the interpreter cache is not housekeeping. It is what stops a job inheriting the last
job's packages, which is how a base install stopped being base on 09/22/2026.

## What to watch for

- **A reused machine is not a clean machine.** The shared package's `wheel`
  job checks that a base install cannot import the reporter without the pytest
  extra. On the first self-hosted run pytest was already installed from the
  previous job, so "a base install" was not base. Every job now installs into a
  venv of its own, and the janitor clears the interpreter cache weekly. Any new
  job that assumes a clean machine needs the same care.
- **Never with a public repo.** A self-hosted runner on a public repo runs code
  from any fork's pull request. Both repos are private. If either becomes
  public, switch these off the same day.
