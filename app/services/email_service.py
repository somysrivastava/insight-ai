# WHY THIS FILE EXISTS:
# The one place that talks to SendGrid. Callers (scheduled_tasks.py)
# never touch the SendGrid SDK directly — same reasoning as
# storage_service.py wrapping S3: swapping providers later is a change
# here, not a hunt through every caller.

import base64
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Attachment, Disposition, FileContent, FileName, FileType, Mail

load_dotenv()

_CONTENT_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}

_client: SendGridAPIClient | None = None


def _get_client() -> SendGridAPIClient:
    global _client
    if _client is None:
        _client = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
    return _client


def send_export_email(
    recipients: list[str],
    schedule_name: str,
    export_format: str,
    file_bytes: bytes,
    filename: str,
    summary: str | None = None,
) -> None:
    """
    Sends the export as a real attachment (not a link — a recipient
    might not have an InsightAI account at all, since recipients aren't
    restricted to the requesting user) to every address in `recipients`
    in one send. `summary` is whatever short narrative the export
    already produced (an AI query's answer, or a report's headline) —
    reused rather than generated separately, since export_service.py
    computes it anyway.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subject = f"{schedule_name} — {today}"

    body_lines = [f"<p>Your scheduled report <strong>{schedule_name}</strong> is attached.</p>"]
    if summary:
        body_lines.append(f"<p>{summary}</p>")
    html_content = "\n".join(body_lines)

    message = Mail(
        from_email=os.getenv("SENDGRID_FROM_EMAIL"),
        to_emails=recipients,
        subject=subject,
        html_content=html_content,
    )
    message.attachment = Attachment(
        FileContent(base64.b64encode(file_bytes).decode()),
        FileName(filename),
        FileType(_CONTENT_TYPES[export_format]),
        Disposition("attachment"),
    )

    response = _get_client().send(message)
    if response.status_code >= 300:
        raise Exception(f"SendGrid returned {response.status_code}: {response.body}")


def send_alert_email(
    recipients: list[str],
    rule_name: str,
    dataset_name: str,
    column: str,
    metric: str,
    condition: str,
    threshold: float,
    actual_value: float,
    alert_type: str,
    z_score: float | None,
) -> None:
    """Plain notification email — no attachment, unlike send_export_email (Day 18)."""
    now = datetime.now(timezone.utc)
    subject = f"⚠️ Alert: {rule_name} triggered"

    condition_text = {"gt": "above", "lt": "below", "gte": "at or above", "lte": "at or below", "eq": "equal to"}[condition]

    lines = [
        f"<p><strong>{rule_name}</strong> triggered on dataset <strong>{dataset_name}</strong>.</p>",
        "<ul>",
        f"<li>Column: {column}</li>",
        f"<li>Metric: {metric} = {actual_value:,.2f}</li>",
        f"<li>Condition: {metric} {condition_text} {threshold:,.2f}</li>",
    ]
    if alert_type == "statistical" and z_score is not None:
        lines.append(f"<li>Statistical: z-score = {z_score:,.2f}</li>")
    lines.append(f"<li>Detected at: {now.strftime('%Y-%m-%d %H:%M UTC')}</li>")
    lines.append("</ul>")
    html_content = "\n".join(lines)

    message = Mail(
        from_email=os.getenv("SENDGRID_FROM_EMAIL"),
        to_emails=recipients,
        subject=subject,
        html_content=html_content,
    )

    response = _get_client().send(message)
    if response.status_code >= 300:
        raise Exception(f"SendGrid returned {response.status_code}: {response.body}")
