"""Manage manual review queue and generate/send daily review reports.

CLI: python tools/review_queue.py --generate-report

The script reads `tools/review_queue.json` and produces an HTML report. If SMTP
settings are provided via environment variables, it will try to email the report.
"""
from __future__ import annotations

import json
import os
import smtplib
from datetime import datetime
from typing import Any

import tools.email_client as email_client

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUEUE_PATH = os.path.join(ROOT, "tools", "review_queue.json")
REPORT_PATH = os.path.join(ROOT, "tools", "review_report.html")


def load_queue(path: str = QUEUE_PATH) -> dict[str, Any]:
    if not os.path.exists(path):
        return {"items": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def generate_html_report(queue: dict[str, Any]) -> str:
    items = queue.get("items", [])
    pending = [it for it in items if it.get("status", "pending") == "pending"]
    html = [
        "<html><head><meta charset='utf-8'><title>Review Queue</title></head><body>",
        f"<h1>Manual Review Queue &mdash; {datetime.utcnow().isoformat()}</h1>",
    ]
    if not pending:
        html.append("<p>No items pending review.</p>")
    else:
        html.append(
            "<table border='1' cellpadding='6'>"
            "<tr><th>ID</th><th>Test</th><th>Module</th><th>Severity</th>"
            "<th>Confidence</th><th>Reason</th><th>Timestamp</th><th>Artifacts</th></tr>"
        )
        for it in pending:
            entry_id = it.get('id', 'n/a')
            nodeid = it.get('nodeid', '')
            reason = it.get('reason', '')
            ts = it.get('ts', '')
            score = it.get('confidence_score', 'n/a')
            bug_data = it.get('bug_data') or {}
            module = bug_data.get('module', 'n/a')
            severity = bug_data.get('severity', 'n/a')
            # artifact links (best-effort): look for logs/<nodeid>.png or .mp4
            safe_name = nodeid.replace('/', '_').replace(':', '_')
            imgs = []
            img_path = os.path.join(ROOT, 'logs', f"{safe_name}.png")
            vid_path = os.path.join(ROOT, 'logs', f"{safe_name}.mp4")
            if os.path.exists(img_path):
                imgs.append(f"<a href='file://{img_path}'>screenshot</a>")
            if os.path.exists(vid_path):
                imgs.append(f"<a href='file://{vid_path}'>video</a>")
            artifacts = ', '.join(imgs) or 'n/a'
            html.append(
                f"<tr><td>{entry_id}</td><td>{nodeid}</td><td>{module}</td><td>{severity}</td>"
                f"<td>{score}</td><td>{reason}</td><td>{ts}</td><td>{artifacts}</td></tr>"
            )
        html.append("</table>")

    # Recently reviewed items
    reviewed = [it for it in items if it.get("status") in ("approved", "rejected")]
    if reviewed:
        html.append("<h2>Recently Reviewed</h2>")
        html.append(
            "<table border='1' cellpadding='6'>"
            "<tr><th>ID</th><th>Test</th><th>Decision</th>"
            "<th>Jira Key</th><th>Reviewed By</th></tr>"
        )
        for it in reviewed[-20:]:
            jira_key = it.get('jira_key') or 'n/a'
            html.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(it.get('id', ''), it.get('nodeid', ''),
                   it.get('status', ''), jira_key, it.get('reviewed_by', ''))
            )
        html.append("</table>")

    html.append("</body></html>")
    return '\n'.join(html)


def send_via_smtp(html: str, subject: str, to_addr: str) -> None:
    """Legacy SMTP sender (kept for fallback)."""
    from email.message import EmailMessage

    smtp_host = os.environ.get('SMTP_HOST', 'localhost')
    smtp_port = int(os.environ.get('SMTP_PORT', 25))
    from_addr = os.environ.get('SMTP_FROM', 'qa-reports@soterixsystems.com')

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg.set_content('Please view this HTML report in an HTML-capable client.')
    msg.add_alternative(html, subtype='html')

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
        # support optional auth
        user = os.environ.get('SMTP_USER')
        pwd = os.environ.get('SMTP_PASSWORD')
        if user and pwd:
            s.starttls()
            s.login(user, pwd)
        s.send_message(msg)


def send_via_graph(html: str, subject: str, to_addr: str) -> None:
    """Send report via Microsoft Graph using the OAuth client.

    Falls back to raising exceptions on failure.
    """
    try:
        attachments = []
        # include the report as an attachment
        report_path = REPORT_PATH
        if os.path.exists(report_path):
            attachments.append(report_path)
        email_client.send_email(to_addr, subject, html, attachments=attachments)
    except Exception:
        raise


def main_cli():
    import argparse

    parser = argparse.ArgumentParser(description='Review queue report generator')
    parser.add_argument('--generate-report', action='store_true')
    parser.add_argument('--email-to', default=os.environ.get('EMAIL_TO', ''))
    args = parser.parse_args()

    queue = load_queue()
    html = generate_html_report(queue)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Wrote report: {REPORT_PATH}')

    # Try sending via Microsoft Graph OAuth (preferred), fall back to SMTP if available.
    subject = f"Manual Review Queue - {datetime.utcnow().date().isoformat()}"
    try:
        send_via_graph(html, subject, args.email_to)
        print('Sent report via Microsoft Graph to', args.email_to)
    except Exception as e:
        print('Graph send failed:', str(e))
        print('Falling back to SMTP (if configured)...')
        try:
            send_via_smtp(html, subject, args.email_to)
            print('Sent report via SMTP to', args.email_to)
        except Exception as e2:
            print('SMTP send failed:', str(e2))
            print('Report written to', REPORT_PATH)


if __name__ == '__main__':
    main_cli()
