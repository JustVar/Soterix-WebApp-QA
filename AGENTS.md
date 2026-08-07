# Soterix-WebApp-QA - guidance for AI coding tools

If you use an AI tool to write, test, or update anything in this repo, point
it here first.

Read before making changes:

1. `docs/CONVENTIONS.md` - how tests are organized and written here: page
   objects, step capture, markers, adding a test.
2. `docs/writing/ste.md` - the writing rules for all prose: docs, comments,
   docstrings, error messages, commit messages. Use strict mode for error
   messages and log lines, flavored mode for docs. `docs/STYLE.md` is the
   short human summary. Never apply the rules to code, identifiers, or any
   name the reader must match against a screen.

Hard rules:

- Commit messages describe what the change does. No tool attribution, no
  co-author lines, no generated-with footers.
- Plain ASCII in prose: no em dashes, no curly quotes, no emoji.
- QA Touch case mappings go in `config/qatouch_case_mapping.json`, never in
  test files.
- API tests and API clients belong in the sibling repo Soterix-API-QA. Do
  not add them here.
- Never commit `.env` or any credential.
- Before you edit a file you did not create, read it fully and keep its
  intent. Propose a large rewrite instead of applying it.
