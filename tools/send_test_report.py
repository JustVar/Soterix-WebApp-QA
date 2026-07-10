"""Send test run report via email.

Usage:
  python tools/send_test_report.py [report_file] [recipient_email]

Examples:
  python tools/send_test_report.py report.html person@example.com
  python tools/send_test_report.py report.html  # Uses default recipient
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from email_client import GraphEmailClient

DEFAULT_RECIPIENT = "person@example.com"
DEFAULT_REPORT = "report.html"
ROOT = Path(__file__).resolve().parent.parent


def send_report(report_file: str = DEFAULT_REPORT, recipient: str = DEFAULT_RECIPIENT):
    """Send HTML test report via email.

    Args:
        report_file: Path to HTML report file
        recipient: Email address to send to
    """
    report_path = ROOT / report_file

    if not report_path.exists():
        print("[ERROR] Report file not found: " + str(report_path))
        return False

    # Read the HTML report
    with open(report_path, 'r') as f:
        html_content = f.read()

    # Extract title from HTML for email subject
    title = "Test Run Report"
    if "<title>" in html_content:
        start = html_content.find("<title>") + 7
        end = html_content.find("</title>")
        title = html_content[start:end].strip()

    # Create email body with embedded report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    email_body = f"""
    <h2>{title}</h2>
    <p><strong>Generated:</strong> {timestamp}</p>
    <hr>
    {html_content}
    """

    try:
        client = GraphEmailClient()
        status = client.send_email(
            to=recipient,
            subject=f"Test Report: {title}",
            body_html=email_body,
            attachments=[str(report_path)]
        )
        print("[SUCCESS] Email sent to " + recipient)
        print("   Report: " + report_file)
        print("   Status: " + str(status))
        return True
    except Exception as e:
        print("[ERROR] Failed to send email: " + str(e))
        return False


if __name__ == "__main__":
    report = DEFAULT_REPORT
    recipient = DEFAULT_RECIPIENT

    if len(sys.argv) > 1:
        report = sys.argv[1]
    if len(sys.argv) > 2:
        recipient = sys.argv[2]

    success = send_report(report, recipient)
    sys.exit(0 if success else 1)
