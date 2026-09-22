# Concurrency, load and tenant testing: the plan

Written for: the QA team, and the app team who will receive what it finds.

This is a plan, not a built thing. It says what we would test, what we would
assert, what we need from the app team before we can assert anything, and in
what order to build it. Nothing here is scheduled yet.

Drafted 09/22/2026 from the research in [docs/BROWSER_TOPOLOGY.md](BROWSER_TOPOLOGY.md).

## Why

The defects this team already found point at concurrency, not at the browser.

- Register row 83: an app defect failed the same way on Linux and on Windows.
  The variable that changed the outcome was the worker count: it failed with 4
  workers and passed with 1.
- Register row 100: the server runs 1 search job for each account and offers no
  cancel. A logout while a job runs locks the slot for every account. It held 1
  worker for 40 minutes.
- Register row 99: a search over a camera that is unreachable never finishes.

Each of those is what a customer meets when a colleague is already using the
system. The suite finds them by accident today, because the nightly happens to
run 4 workers. Nothing looks for them on purpose.

## What is missing before we can assert anything

**We do not know the app's limits.** A load test that invents a number finds
nothing but its own guess. Before building, get these from the app team and
record them here:

| Question | Why it decides a test |
|---|---|
| How many streams does an edge box serve at once? | The assertion for edge-box load |
| How many sessions may 1 account hold? | Whether 2 clients on 1 account is supported or abuse |
| What happens to session 1 when session 2 signs in? | Whether a drop is a defect or the design |
| How many search jobs does the server run for each account, and for each tenant? | Row 100 says 1 for each account. For each tenant is unknown |
| What is a normal customer load? | Whether our numbers mean anything |
| Is there a documented limit anywhere? | The difference between a defect and a support answer |

Until those answers exist, the honest test is **observational**: run 2 clients,
record what happens, and report it. That is still worth doing, and it is how we
learn the limits when nobody has written them down.

## The 2-client shape

spartan1 alone runs 1 pytest session from 1 address. That is 1 client with
several workers, which is not the same as 2 people.

2 machines give 2 genuinely independent clients: their own addresses, their own
sessions, their own browser processes. That is what a second customer looks
like to the server.

```
spartan1  ──┐
            ├── 1 tenant / 1 account / 1 edge box
spartan20 ──┘
```

For this the browser must run **on** spartan20. `deploy/windows-runner/`
already has that shape: pytest runs there and publishes its run back to the
archive. Driving a remote browser from spartan1 would be 1 process with 2
browsers, which is not 2 users.

## What to test, in order of what we already suspect

### 1. The search slot (row 100, an open app defect)

The cheapest first test, because the defect is already recorded and the app
team already owns it.

- Client A starts a search. Client B starts a search on the same account.
- Record: does B queue, refuse, or take the slot from A? What does the UI say?
- Then: A signs out while its job runs. Does the slot free?
- The assertion, once the app team names the rule: the second client is told
  what is happening, and the slot frees when its owner leaves.

### 2. Two sessions on one account

- Both clients sign in as the same account.
- Record: are both live? Is one dropped? Is there a warning? What does the
  audit trail show?
- This bears directly on a real operations question: whether 2 people may
  share an account, which customers do whether or not it is supported.

### 3. Edge-box stream load

- Both clients open live tiles from cameras on 1 edge box, and climb: 1 tile,
  4, 9, then across machines.
- Record for each step: time to first frame, the frame rate once playing,
  dropped frames, stream restarts, and any error the app shows.
- `tools/livestream_bench.py` already reports exactly those fields for 1
  browser. The load version runs it on both machines at once and lines the
  numbers up by time.
- The failure we are hunting is the one customers describe as "the video went
  choppy when my colleague logged in".

### 4. Tenant-wide contention

- Both clients work in different parts of the app at once: one searching, one
  playing live, one in Admin.
- Record: does 1 slow area slow the others? Row 100 says a search can hold
  things. This asks how far that reaches.

## How a run would work

1. Both machines run the same commit. spartan1 already resets its clone from
   `origin/main`, and the Windows runner does the same.
2. A start time is agreed, so the 2 runs overlap on purpose. The simplest form
   is a fixed clock time in both schedules.
3. Each machine writes its own run folder and publishes to the same archive.
4. The run pages carry the machine in their provenance, so the 2 runs can be
   read side by side.
5. The reading is the point: the numbers from the 2 runs, lined up by time.

**What has to be built:** a way to line up 2 runs by time in the archive. Each
run records its start and its own machine already. The missing piece is a page
that shows both at once. That is the one real build item, and it is small.

## What would make the results untrustworthy

Write these down before running, not after:

- **The tenant is shared.** Another person working on it during the run changes
  the result. Runs need a quiet window, or a note saying who else was on.
- **The QA tenant is not production.** Its limits may not be the customer's.
  Anything we find needs the app team to say whether it is the same in
  production.
- **2 machines are not 20 users.** This finds contention between a small number
  of clients. It is not a load test in the traffic-generator sense, and it
  should not be described as one.
- **The stream restarts about once every 30 seconds on every machine,** the
  laptop included. That is the tenant's own behaviour and it is not a finding.
- **1 run proves nothing.** Every number here needs repeats before it goes to
  the app team.

## Order of work

This sits behind the foundations. It is the next capability, not the next task.

1. Make spartan20 able to run unattended: display never off, automatic sign-in,
   updates on demand. See [docs/BROWSER_TOPOLOGY.md](BROWSER_TOPOLOGY.md),
   "What the machine needs first". Without automatic sign-in a restart leaves
   no desktop and no browser.
2. Decide the admin channel. SSH resets under Chrome load. Measure WinRM, and
   keep box maintenance as local scheduled tasks.
3. Prove the Windows runner on its own: 1 box, no reset, no publish, then with
   a publish.
4. Ask the app team the questions above.
5. Build test 1, the search slot, because the defect is already known and owned.
6. Add the side-by-side reading to the archive.
7. Then tests 2, 3 and 4.
