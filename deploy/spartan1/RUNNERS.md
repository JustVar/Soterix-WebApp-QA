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

GitHub scopes a runner to 1 repo, so each repo needs its own. All 3 run as
the user **`ghrunner`** under systemd, and each has 1 runner, so the jobs of
1 workflow queue rather than run side by side. The jobs take seconds, so that
is a queue of seconds.

## What the runner account may and may not do

`ghrunner` exists only for CI. A workflow file runs whatever it says, so the
account it runs as decides what a mistake can reach.

- It is **not** `soterix`. That account owns the nightly, the `.env` with the
  tenant credentials, and the published archive.
- It cannot read `/data/qa/ci/Soterix-WebApp-QA/.env`.
- It cannot write `/data/qa/runs`, the nightly clone, or `nightly.sh`.
- It has no sudo.
- Its systemd services carry `CPUWeight=20`, `IOWeight=20` and
  `MemoryMax=4G`, so a CI job yields the machine to the nightly rather than
  competing with it.

Check all of that at any time:

```bash
ssh spartan1 'sudo -u ghrunner test -r /data/qa/ci/Soterix-WebApp-QA/.env && echo PROBLEM || echo ok
sudo -u ghrunner test -w /data/qa/runs && echo PROBLEM || echo ok
sudo -u ghrunner sudo -n true 2>/dev/null && echo PROBLEM || echo ok'
```

## How it reaches the private shared package

The gates install `soterix-qa-shared` from a private repo. `ghrunner` has its
own key, `~/.ssh/shared_ro`, registered on SOTERIX-QA-SHARED as a
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

Nothing detects a dead box on its own. A queued job that never starts is the
symptom, and it is not an error, so nobody is told.

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

## What to watch for

- **A reused machine is not a clean machine.** The shared package's `wheel`
  job checks that a base install cannot import the reporter without the pytest
  extra. On the first self-hosted run pytest was already installed from the
  previous job, so "a base install" was not base. That job now builds inside a
  venv of its own. Any job that assumes a clean machine needs the same care.
- **`_work` grows.** Each runner keeps a checkout and a tool cache there.
- **Never with a public repo.** A self-hosted runner on a public repo runs code
  from any fork's pull request. Both repos are private. If either becomes
  public, switch these off the same day.
