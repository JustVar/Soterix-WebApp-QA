# Soterix WebApp QA

This repo holds the browser tests of the Soterix web application, NexaiQ-Core,
against one QA server. A test does what a user does in Google Chrome, and a
report page shows what failed and why.

The API tests live in a different repo, Soterix-API-QA.

## How it works

1. The tests are Python. Playwright drives Google Chrome, and pytest runs
   the tests.
2. Page objects in `tests/shared/pages/` hold the locators. When the app
   changes, you correct 1 file.
3. One file, `config/env/qa.py`, names the server, the test site and the
   test camera. One file, `.env`, holds the account. No test names any of
   them.
4. Each run keeps its evidence in `reports/runs/<run>/`: a report page
   (`run.html`), a screenshot of each test, and a video and a Playwright
   trace of each failure.
5. Git hooks and a CI gate check each change without a browser.

## Day one

You need read access to this repo and 1 account on the QA server. Nothing
else.

1. Install Python 3.14 and Google Chrome. The tests drive the Chrome on
   your machine (`--browser-channel chrome` in `pytest.ini`). Playwright's
   own browser is not used, and Node.js is not needed.
2. Clone into a short path, for example `C:\qa\webapp-qa`. A deep path
   pushes Windows past its path cap, and evidence files then fail to write.

   ```
   git clone https://github.com/Soterix-Systems/Soterix-WebApp-QA.git C:\qa\webapp-qa
   cd C:\qa\webapp-qa
   ```

3. Create the venv and install. The install takes the shared package from
   `vendor/`, so it asks for no credential and works offline.

   ```
   python -m venv venv
   venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   There is no activation step. Every command in this repo calls
   `venv\Scripts\python.exe` by path, because PowerShell blocks
   `Activate.ps1` by default and a global `pip` installs into the wrong
   Python without a word.

4. Turn on the git hooks for this clone. They run the same checks as CI
   before a commit exists, in 10 to 30 seconds.

   ```
   git config core.hooksPath tools/hooks
   ```

5. Copy the template and fill the 2 account lines, `QA_USER` and
   `QA_PASSWORD`. Leave the rest as it is.

   ```
   copy .env.template .env
   ```

6. If your server is not the one in `config/env/qa.py`, edit that file.
   A new server needs 7 keys: `base_url`, `api_base_url`,
   `default_site_id`, `test_site_name`, `test_camera_name`,
   `test_chat_user_search` and `test_chat_user_name`. Fill
   `camera_capabilities` only when a marker needs a particular camera.
   Fill `without` only after you measured what the server lacks. The
   file's header comment lists these keys.

7. Run 1 test.

   ```
   venv\Scripts\python.exe run.py test "tests/ui/login/test_login_valid.py::test_valid_credentials[chromium]"
   ```

   Before any browser opens, 1 `PREFLIGHT` line says whether the server
   and the account answered. Then Chrome opens, signs in and closes. The
   first sign-in through the browser takes about 65 seconds. Later runs
   reuse the saved session. The last lines print `Run report:` with the
   path of the run's `run.html`.

8. Open the printed `run.html`. The section "How to read a run" below
   says what is on it.

9. Run the smoke set, then read the health page after a few runs.

   ```
   venv\Scripts\python.exe run.py smoke
   venv\Scripts\python.exe run.py health
   ```

Every other command is in [docs/COMMAND_SHEET.md](docs/COMMAND_SHEET.md).

## How to read a run

- The first sentence of `run.html` is the verdict: how many tests failed,
  and how many causes. A cause is 1 error that several failures share.
  Correct the cause before you open a single failure.
- A failure shows its error first, then its screenshot, its video and the
  exact `show-trace` command. A trace holds the DOM at every action, so
  you do not need to run the test again to see what happened.
- A skip shows its reason. "Skipped" is not "passed". The line below the
  verdict gives the passed and skipped counts. A test that skips on every
  run proves nothing.
- `reports\runs\index.html` lists every run on this machine.

The terminal prints 4 lines that name a cause before you read a single
test:

| Line | Meaning |
|---|---|
| `PREFLIGHT:` | The server did not answer, or it refused the account, or the site id is wrong. No test ran. Correct `.env` or `config/env/qa.py`. |
| `[LOGIN]` | The browser login form stayed on screen after submit. The line quotes the message on the form. |
| `[SESSION]` | The server dropped the session in the middle of a test, and the app went back to the login screen. The locator is not at fault. |
| `[STREAM]` | What the stream guard measured on the test camera. It says whether the tests marked `livestream` ran, or why they skipped on this machine's Chrome. |

A `[CAMERA]` line prints only when the run drove a different camera than
`test_camera_name`, and says why.

When a test is red, start at the table in
[docs/FAILURE_TRIAGE.md](docs/FAILURE_TRIAGE.md). In the first week on a
new server, most red tests are a renamed site or camera, corrected in
`config/env/qa.py`.

## Adding a test

Read "Adding a test" in [docs/CONVENTIONS.md](docs/CONVENTIONS.md) first.
The facts the app taught us are in
[docs/QA_THINGS_TO_KNOW.md](docs/QA_THINGS_TO_KNOW.md). To look at the
app before you write a locator, run
`venv\Scripts\python.exe tools/explore_app.py --headed`.

## The checks a commit runs

The pre-commit hook runs 6 checks: no staged line carries a value from
`.env`, the house conventions hold on the added lines, the test inventory
page is current, ruff finds nothing, the collected-test count did not fall,
and the offline suites pass. The commit-message hook refuses a message that
carries an attribution or a co-author trailer. CI runs the same checks on
every push, on GitHub's machines, with no secret. See
[docs/CI.md](docs/CI.md).

`config/known_defects.yaml` lists tests that are red because of an app
defect somebody already reported. The run page labels those failures
"Known defect" and counts them apart. The list is empty. The file's header
shows the shape of an entry.

## Optional integrations

Nothing below runs unless you turn it on. A plain run contacts nothing but
the QA server. The repo files no Jira bug and sends no email.

- QA Touch. Results upload only with `pytest --qatouch-upload
  --qatouch-run <key>` and the 3 keys in `.env`. See
  [docs/QA_TOUCH_INTEGRATION.md](docs/QA_TOUCH_INTEGRATION.md).
- A scheduled run on a Windows machine. Nothing is scheduled today. See
  [deploy/windows-runner/README.md](deploy/windows-runner/README.md).
- H.265 on Linux. Chrome on Linux decodes the server's video only with the
  recipe in [docs/LINUX_H265.md](docs/LINUX_H265.md). On Windows and Mac,
  Chrome needs no setup.

## Where things went

Everything that served the old setup left the main branch under the git
tag `pre-pivot`. [docs/ARCHIVE.md](docs/ARCHIVE.md) lists what left, by
area, and the 1 command that brings a file back.

Writing rules for docs, comments and commit messages:
[docs/STYLE.md](docs/STYLE.md). The entry page for coding tools:
[AGENTS.md](AGENTS.md).
