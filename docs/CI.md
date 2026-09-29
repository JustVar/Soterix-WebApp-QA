# CI

The repo has 1 workflow, `.github/workflows/collect-gate.yml`. It runs on
each push to `main`, on each pull request, and by hand from the Actions tab.
It runs on GitHub's machines (`ubuntu-latest`) with no secret and no
repository variable. The shared package is a wheel under `vendor/`, so
`pip install -r requirements.txt` is the whole setup. A push is not done
until the gate is green. To see the result:

```
gh run list --limit 3
gh run watch <run-id>
```

## What the gate checks

The `collect` job does these steps in order. The first step that fails stops
the job. It opens no browser and sends no request to the QA server.

| Step | What it proves | If it fails |
|---|---|---|
| Imports and fixture wiring | `pytest --collect-only` and `pytest --setup-plan` work for the whole repo. | Correct the import or the fixture that the error names. |
| Collected-test floor | The number of collected tests did not fall (`tools/collect_floor.py`). A suite that shrinks after a bad merge is silent without this. | If you removed tests on purpose, run `python tools/collect_floor.py --update` and commit the result with the reason. If you did not, a merge lost files: find them. |
| Offline suites | `pytest tests/plugins tests/tools tests/helpers` passes. This includes the shim guards and the shared package pin. | Run the same command on your machine. |
| Test inventory is current | `docs/TEST_INVENTORY.md` agrees with the tests. | Run `python tools/test_inventory.py` and commit the file. |
| Lint | `python -m ruff check .` finds nothing. | Correct the finding that the message names. |
| House conventions on the added lines | `tools/convention_check.py` finds no HIGH item on the lines that the push adds. | Correct the line. The message names the rule. |
| Commit messages | No commit in the push names an AI tool, a model or a co-author (`tools/hooks/commit-msg`). | Write the commit message again. |

## Cost

One job per push or pull request, about 2 minutes, most of it the pip
install. This is an estimate: the first hosted run since the pivot has not
been measured. Nothing is scheduled, so there is no cost between pushes.

## The same checks on your machine

The pre-commit hook runs the same checks before the commit exists, plus
`tools/secret_check.py`, which compares staged lines with the values in your
`.env`. To turn the hooks on in a new clone, run
`git config core.hooksPath tools/hooks` one time.

## Browser runs

The gate never runs a browser test. To run the suite on a schedule, use a
Windows machine and `deploy/windows-runner/`, not GitHub: the QA server's
login has reCAPTCHA, and nobody has proven that a datacenter IP gets past
it. If a machine of your own is ever registered as a runner, a pull request
must still run on GitHub's machines, because a workflow file is part of the
branch and anyone who can open a pull request could run their own code on
that machine.
