# Moving CI onto spartan1: the plan

Written for: whoever builds this, and whoever has to keep it running.

GitHub charges for the minutes our workflows use. On 09/22/2026 the allowance
reached 90 percent. A runner on our own machine costs nothing per minute. This
page says what to move, what not to move, what it costs to own, and in what
order.

**Built 09/22/2026.** All 3 repos now run their gates on spartan1 and bill nothing. How to keep
them alive, and what the runner account may and may not reach:
[deploy/spartan1/RUNNERS.md](../deploy/spartan1/RUNNERS.md). This page keeps the reasoning and
the order of work it was built from.

## What runs today, and what it costs

| Workflow | Repo | Fires on | Jobs |
|---|---|---|---|
| `collect-gate` | WebApp | push, pull request | collect, lint, offline tests, shim matrix |
| `ci` | shared package | push, pull request | offline tests on several interpreters |
| `collect-gate` | API | push, pull request | the same shape, 1 job |
| `QA nightly` | WebApp | by hand only | a smoke job. Its schedule is switched off |

Nothing runs on a schedule except the weekly interpreter matrix added
09/22/2026. Every other run comes from a push.

**What was cut on 09/22/2026, before any of this plan:**

- The 4-interpreter matrix now runs 1 interpreter on a push and all 4 once a
  week. It was the largest single consumer.
- The shared package no longer runs on a release tag. The tag points at a
  commit `main` already gated, so that run repeated work. 4 releases in 1 day
  meant 4 wasted runs.
- The workflows on the personal remotes are disabled. A double push ran every
  gate twice for no extra signal. Pushes to those remotes still happen, at the
  end of a day, and now cost nothing.
- Pushes are batched. A day's work goes up together, not after each fix.

Those 4 changes should be measured before anything below is built. They may be
enough on their own.

## The host

spartan1, measured 09/22/2026: 28 cores, 15 GB of memory, 272 GB free, load
average 0.25. It runs the nightly at 09:00 UTC and is close to idle the rest of
the day. It has room.

## What to move, and what to leave

**Move: the offline gates.** `collect-gate` and the shared package's `ci` run
no browser, reach no network and need no tenant credential. They are the bulk
of the minutes and the least risky thing to host.

**Leave on GitHub: anything that needs a secret we would not put on the box,
and anything that must work when the box is down.** If spartan1 is the only
runner, a box that is off means nobody can merge. Keep a GitHub-hosted path
available, even if it is normally idle.

**Never move: a workflow that runs code from a fork.** Both repos are private
today, so only people with access can open a pull request. If either repo ever
becomes public, self-hosted runners must be switched off the same day. GitHub
says this plainly, and it is the one rule here with no exceptions.

## What it costs to own

Honest list, because a runner is a service somebody has to keep alive:

- **A second thing on the box that can break.** The nightly is already there.
  A runner that wedges blocks merges, and the symptom is a queued job, not an
  error.
- **It must not collide with the nightly.** The nightly runs 09:00 UTC for
  1 to 2 hours and drives browsers. A CI job during it competes for the
  machine and could change a nightly result, which would be a bad way to learn
  this lesson. The runner needs a window, or a concurrency limit of 1 with the
  nightly holding a lock.
- **Its own account.** The runner must not run as `soterix`. That account owns
  the nightly, the `.env` with tenant credentials, and the published archive.
  A CI job runs whatever is in the branch, so it gets its own user with no
  access to those.
- **Updates.** The runner agent updates itself, but the machine, Python and the
  deploy keys are ours.
- **No cache, no matrix for free.** GitHub's hosted cache and its clean image
  each run are conveniences we would be giving up. A self-hosted runner keeps
  state between jobs unless we clean it, and stale state is a classic source of
  a green build that should be red.

## The order of work

1. **Measure first.** Watch the allowance for a week with the 4 cuts above in
   place. If usage is comfortable, stop here. This plan is insurance, not a
   goal.
2. **Make a runner user** on spartan1 with no access to `/data/qa/runs`, the
   nightly clone, or the `.env`.
3. **Register 1 runner** against the shared package only. It is the smallest
   repo, its tests are offline, and a mistake there does not block the suite.
4. **Run both** for a week: the hosted job and the self-hosted job on the same
   push. Compare results. A self-hosted runner that disagrees with the hosted
   one is the thing to find before trusting it.
5. **Add the lock** so a CI job and the nightly never run together.
6. **Move `collect-gate`** for the WebApp repo, then the API repo.
7. **Keep a hosted fallback** on `workflow_dispatch`, so a box outage does not
   stop work.

## What would make this the wrong move

- If the 4 cuts already brought usage well under the limit, this adds a service
  to maintain for no gain.
- If either repo becomes public.
- If the box's own reliability becomes the thing that blocks merges. The
  nightly can miss a night and be re-run. CI cannot miss an hour without
  somebody noticing.

## Open questions

- What is the actual allowance, and what is actually consumed? The billing API
  refused the token available here on 09/22/2026, so every number in this page
  is a run count, not minutes. Read the real figure from the organisation's
  billing page before building.
- Does a private repo's Actions usage bill the organisation or the account that
  owns the repo? The personal remotes and the company remotes may draw on
  different allowances, which changes where the saving lands.
