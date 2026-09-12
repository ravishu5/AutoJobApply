"""
scrapers/job_poster_extractor.py — Authenticated Job Poster & Hiring Team Extractor
Inspects authenticated LinkedIn job postings to extract the recruiter or engineering manager
featured in the "Meet the hiring team" section.
"""

import re
import urllib.parse
from typing import Optional, Dict, Any
from playwright.async_api import Page


def clean_linkedin_profile_url(raw_url: str) -> str:
    """Normalize LinkedIn profile URL by removing tracking query parameters."""
    if not raw_url:
        return ""
    parsed = urllib.parse.urlparse(raw_url)
    clean_path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{clean_path}"


async def extract_job_poster(page: Page) -> Optional[Dict[str, str]]:
    """
    Extract hiring manager or recruiter details from the active LinkedIn job page.
    Works reliably on authenticated job detail pages.
    """
    try:
        # Common selectors used across LinkedIn web layouts for 'Meet the hiring team'
        poster_selectors = [
            ".hirer-card__hirer-information",
            "[data-view-name*='job-poster']",
            ".jobs-poster",
            ".hiring-team",
            "div:has-text('Meet the hiring team')"
        ]

        card = None
        for sel in poster_selectors:
            card = await page.query_selector(sel)
            if card:
                break

        if not card:
            # Look for links that link to an /in/ profile inside the job details section
            link_el = await page.query_selector("a[data-control-name='hiring_member_profile'], a[href*='/in/'][class*='poster']")
            if link_el:
                href = await link_el.get_attribute("href") or ""
                text = (await link_el.inner_text() or "").strip()
                if href and text:
                    return {
                        "name": text,
                        "headline": "Hiring Team Member",
                        "profile_url": clean_linkedin_profile_url(href)
                    }
            return None

        # Extract profile link
        link_el = await card.query_selector("a[href*='/in/']")
        if not link_el:
            return None

        href = await link_el.get_attribute("href") or ""
        clean_url = clean_linkedin_profile_url(href)
        if not clean_url:
            return None

        # Extract name
        name_el = await card.query_selector(".jobs-poster__name, strong, h3, [class*='name']")
        name = (await name_el.inner_text() or "").strip() if name_el else ""
        if not name:
            name = (await link_el.inner_text() or "").strip()

        # Clean out any trailing status strings like '1st', '2nd', '3rd+'
        name = re.sub(r"\s*·\s*(?:1st|2nd|3rd\+?).*$", "", name).strip()
        name = re.sub(r"\n.*$", "", name).strip()

        # Extract title / headline
        headline_el = await card.query_selector(".hirer-card__headline, [class*='title'], [class*='headline'], p")
        headline = (await headline_el.inner_text() or "").strip() if headline_el else "Hiring Manager"
        headline = re.sub(r"\s+", " ", headline).strip()

        if name and clean_url:
            return {
                "name": name,
                "headline": headline,
                "profile_url": clean_url
            }

        return None

    except Exception:
        return None
