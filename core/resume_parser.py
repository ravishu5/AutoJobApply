"""
core/resume_parser.py — Resume Ingestion and PDF Generator
Extracts plain text and metadata from uploaded PDF/text resumes,
and synthesizes formatted PDF resumes and cover letters.
"""

import os
import re
import io
from typing import Dict, Any, List, Optional
from pypdf import PdfReader


def extract_text_from_pdf_file(file_path: str) -> str:
    """Extract full textual content from a PDF file path."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Resume file not found: {file_path}")
    reader = PdfReader(file_path)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n".join(text_parts).strip()


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract textual content from raw PDF bytes (e.g. from file uploader)."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts).strip()
    except Exception as e:
        return f"[Error extracting PDF text: {e}]"


def extract_contact_info(text: str) -> Dict[str, Any]:
    """Parse contact info (emails, phone, URLs) from raw resume text."""
    # Email extraction
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    emails = re.findall(email_pattern, text)
    clean_emails = [e for e in emails if not any(x in e.lower() for x in ["example.com", "noreply"])]

    # Phone extraction
    phone_pattern = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    phones = re.findall(phone_pattern, text)

    # LinkedIn URL extraction
    linkedin_pattern = r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+"
    linkedin_urls = re.findall(linkedin_pattern, text)

    # GitHub URL extraction
    github_pattern = r"https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+"
    github_urls = re.findall(github_pattern, text)

    return {
        "email": clean_emails[0] if clean_emails else "",
        "phone": phones[0] if phones else "",
        "linkedin": linkedin_urls[0] if linkedin_urls else "",
        "github": github_urls[0] if github_urls else ""
    }


def generate_resume_pdf(
    resume_text: str,
    output_path: str,
    candidate_name: str = "Candidate",
    target_role: str = "",
    company_name: str = ""
) -> str:
    """
    Generate a styled PDF document from resume text using reportlab.
    Falls back gracefully if reportlab is not yet ready.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib import colors

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=0.5 * inch,
            rightMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch
        )
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ResumeTitle",
            parent=styles["Title"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1e293b"),
            alignment=0,
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            "ResumeSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=8
        )
        body_style = ParagraphStyle(
            "ResumeBody",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155")
        )
        heading_style = ParagraphStyle(
            "ResumeHeading",
            parent=styles["Heading2"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#2563eb"),
            spaceBefore=8,
            spaceAfter=3
        )

        story = []
        header_text = candidate_name
        if target_role:
            header_text += f" — {target_role}"
        story.append(Paragraph(header_text, title_style))

        if company_name:
            story.append(Paragraph(f"Prepared specifically for {company_name}", subtitle_style))
        story.append(Spacer(1, 0.1 * inch))

        # Process lines
        for line in resume_text.splitlines():
            line_str = line.strip()
            if not line_str:
                story.append(Spacer(1, 0.05 * inch))
            elif line_str.isupper() and len(line_str) < 40:
                story.append(Paragraph(line_str, heading_style))
            else:
                safe_text = line_str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe_text, body_style))

        doc.build(story)
        return output_path
    except ImportError:
        # Fallback: write text representation with .txt extension if reportlab is unavailable
        txt_path = output_path.replace(".pdf", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(resume_text)
        return txt_path
