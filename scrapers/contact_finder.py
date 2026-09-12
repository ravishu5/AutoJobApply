"""
scrapers/contact_finder.py — Hiring Contact & Recruiter Email Finder
Searches DuckDuckGo and company domains for direct hiring contacts,
talent acquisition specialists, and recruiters. (Derived from CareerPulse pattern)
"""

import re
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional


BAD_EMAIL_PREFIXES = {
    "noreply", "no-reply", "mailer-daemon", "postmaster",
    "support", "info", "sales", "help", "press", "billing", "security", "jobs-noreply"
}


def find_hiring_contact(company: str, job_title: str, location: str = "") -> Dict[str, Any]:
    """
    Search DuckDuckGo HTML for hiring manager / recruiter emails and contact names.
    Returns: {"name": str, "email": str, "title": str, "source": str, "confidence": str}
    """
    result = {
        "name": "",
        "email": "",
        "title": "",
        "source": "",
        "confidence": "none"
    }

    if not company:
        return result

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }

    queries = [
        f'"{company}" recruiter email {job_title}',
        f'"{company}" "talent acquisition" email',
        f'"{company}" hiring manager {job_title} email',
        f'site:linkedin.com/in/ "{company}" recruiter OR "talent acquisition"'
    ]

    with httpx.Client(timeout=12.0, headers=headers, follow_redirects=True) as client:
        # Strategy 1: DuckDuckGo HTML queries
        for query in queries[:2]:
            try:
                resp = client.get("https://html.duckduckgo.com/html/", params={"q": query})
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for body in soup.select(".result__body"):
                        text = body.get_text()
                        # Search for emails
                        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
                        for em in emails:
                            prefix = em.split("@")[0].lower()
                            if not any(bad in prefix for bad in BAD_EMAIL_PREFIXES):
                                result["email"] = em
                                result["source"] = "web_search"
                                result["confidence"] = "medium"
                                break

                        # Also look for recruiter name
                        title_link = body.select_one(".result__title a")
                        if title_link:
                            title_text = title_link.get_text()
                            if " - " in title_text and "LinkedIn" in title_text:
                                name_part = title_text.split(" - ")[0].strip()
                                result["name"] = name_part
                                result["title"] = f"Recruiter at {company}"
                                result["confidence"] = "high" if result["email"] else "medium"

                        if result["email"]:
                            break
                if result["email"]:
                    break
            except Exception:
                continue

        # Strategy 2: Common company careers/contact domains if email still not found
        if not result["email"]:
            company_slug = re.sub(r"[^a-z0-9]", "", company.lower())
            for domain in [f"{company_slug}.com", f"www.{company_slug}.com"]:
                for path in ["/careers", "/contact"]:
                    try:
                        resp = client.get(f"https://{domain}{path}")
                        if resp.status_code == 200:
                            emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", resp.text)
                            for em in emails:
                                prefix = em.split("@")[0].lower()
                                if any(x in prefix for x in ["careers", "recruiting", "talent", "hr"]):
                                    result["email"] = em
                                    result["source"] = f"{domain}{path}"
                                    result["confidence"] = "medium"
                                    break
                    except Exception:
                        pass
                    if result["email"]:
                        break
                if result["email"]:
                    break

    return result
