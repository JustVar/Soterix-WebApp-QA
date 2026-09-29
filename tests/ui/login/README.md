# Login tests

This folder holds the browser tests of the login page. The page object is
`tests/shared/pages/login_page.py`.

The tests cover a valid login and logout, empty fields, wrong credentials,
a malformed email, SQL-like and script-like input, and a short password.
The test list is in the files here and in `docs/TEST_INVENTORY.md`.

## How to run

From the repo root:

```
venv\Scripts\python.exe run.py module login
venv\Scripts\python.exe run.py test "tests/ui/login/test_login_valid.py::test_logout[chromium]"
```

The account is `QA_USER` and `QA_PASSWORD` in `.env`. The server is
`base_url` in `config/env/qa.py`.

## What to know

- ReCAPTCHA is on the login page. `_handle_recaptcha` clicks the checkbox
  and waits for the client-side response. It is not a solver. Run the
  tests on the QA server, where the captcha lets the automation through.
- The other suites sign in once and reuse the session. The
  `authenticated_page` fixture saves the browser storage state to a file
  named by server and xdist worker (`tests/shared/auth_state.py`). The
  tests here submit the form on purpose.
- A login that kept the form on screen prints a `[LOGIN]` line that quotes
  the message on the form. Read it before you read the traceback.
