"""Send a test run report by email. Thin CLI over the shared package.

Usage:
  python tools/send_test_report.py [report_file] [recipient_email]

The recipient comes from the second argument or REPORT_RECIPIENT. The report
path is relative to this repo's root; the package's send_report takes the
absolute path. Credentials come from .env (AZURE_* / EMAIL_FROM), loaded
here because this is the entry point.
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from soterix_qa_shared.reporting.email import send_report

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = 'reports/report.html'


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / '.env')
    argv = sys.argv[1:] if argv is None else argv
    report = argv[0] if argv else DEFAULT_REPORT
    recipient = argv[1] if len(argv) > 1 else None
    return 0 if send_report(ROOT / report, recipient) else 1


if __name__ == '__main__':
    sys.exit(main())
