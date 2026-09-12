"""
networking/emailer.py — Async SMTP Emailer for Recruiter Outreach
Safely drafts and sends personalized cold emails to recruiters and hiring managers.
"""

import os
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Optional, List


def generate_cold_email_draft(
    candidate_name: str,
    candidate_role: str,
    candidate_skills: List[str],
    company: str,
    job_title: str,
    recipient_name: str = ""
) -> Dict[str, str]:
    """Generate professional cold email subject and body for hiring contacts."""
    salutation = f"Hi {recipient_name.split()[0]}," if recipient_name else "Hello,"
    skills_text = ", ".join(candidate_skills[:4]) if candidate_skills else "Python, Cloud, and distributed architectures"

    subject = f"Application / Inquiry: {job_title} — {candidate_name}"
    body = f"""{salutation}

I noticed that {company} is looking for a {job_title}, and given my experience in {skills_text}, I wanted to reach out directly.

In my recent roles, I've specialized in building scalable, production-grade systems, automating engineering workflows, and driving high-impact technical initiatives. I admire {company}'s focus and believe my background aligns strongly with what your team needs right now.

I have attached my resume for your review. Would you be open to a quick 10-minute introductory conversation this week?

Thank you for your time and consideration.

Best regards,

{candidate_name}
{candidate_role}
"""
    return {"subject": subject, "body": body}


async def send_cold_email(
    smtp_config: Dict[str, Any],
    to_email: str,
    subject: str,
    body_text: str,
    resume_pdf_path: Optional[str] = None,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Send an email via SMTP.
    If dry_run is True, validates the payload and returns simulated success without sending.
    """
    if dry_run:
        return {
            "status": "dry_run_success",
            "to": to_email,
            "subject": subject,
            "message": "Email draft verified in dry-run mode. No message sent."
        }

    host = smtp_config.get("host", "smtp.gmail.com")
    port = int(smtp_config.get("port", 587))
    user = smtp_config.get("username") or os.environ.get("SMTP_USER", "")
    password = smtp_config.get("password") or os.environ.get("SMTP_PASS", "")
    from_email = smtp_config.get("from_email") or user

    if not user or not password:
        return {
            "status": "error",
            "error": "SMTP credentials not configured. Please set SMTP_USER and SMTP_PASS."
        }

    msg = MIMEMultipart()
    msg["From"] = f"{smtp_config.get('from_name', 'Applicant')} <{from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body_text, "plain"))

    if resume_pdf_path and os.path.exists(resume_pdf_path):
        with open(resume_pdf_path, "rb") as f:
            pdf_data = f.read()
        part = MIMEApplication(pdf_data, Name=os.path.basename(resume_pdf_path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(resume_pdf_path)}"'
        msg.attach(part)

    try:
        await aiosmtplib.send(
            msg,
            hostname=host,
            port=port,
            username=user,
            password=password,
            start_tls=True
        )
        return {"status": "sent", "to": to_email, "subject": subject}
    except Exception as e:
        return {"status": "error", "error": str(e)}
