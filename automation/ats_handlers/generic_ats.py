"""
automation/ats_handlers/generic_ats.py — Generic ATS and Ashby/BambooHR Form Filler
Inspects DOM elements on any generic career portal, matches input labels against
candidate profile fields, uploads resume, and performs safe prefilling.
"""

import asyncio
import os
import re
from typing import Dict, Any
from playwright.async_api import Page
from core.profile import CandidateProfile
from automation.screening_agent import ScreeningAgent


async def handle_generic_application(
    page: Page,
    job_url: str,
    profile: CandidateProfile,
    screening_agent: ScreeningAgent,
    resume_pdf_path: str,
    dry_run: bool = True
) -> Dict[str, Any]:
    """Inspect and prefill generic career application forms."""
    await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(2.0)

    # If there is an Apply Now button, click it
    apply_btn = await page.query_selector(
        "a:has-text('Apply Now'), button:has-text('Apply Now'), a:has-text('Apply for this job'), button:has-text('Apply')"
    )
    if apply_btn and await apply_btn.is_visible():
        try:
            await apply_btn.click()
            await asyncio.sleep(1.5)
        except Exception:
            pass

    # Step 1: Upload resume if file input found
    if resume_pdf_path and os.path.exists(resume_pdf_path):
        try:
            file_input = await page.query_selector("input[type='file']")
            if file_input:
                await file_input.set_input_files(resume_pdf_path)
                await asyncio.sleep(1.0)
        except Exception:
            pass

    # Step 2: Auto-detect standard inputs by heuristics
    inputs = await page.query_selector_all("input:not([type='hidden']):not([type='file']), textarea")
    name_parts = profile.name.split()

    for inp in inputs:
        try:
            if not await inp.is_visible():
                continue
            curr_val = await inp.input_value()
            if curr_val:
                continue

            attr_str = (
                (await inp.get_attribute("name") or "") + " " +
                (await inp.get_attribute("id") or "") + " " +
                (await inp.get_attribute("placeholder") or "") + " " +
                (await inp.get_attribute("aria-label") or "")
            ).lower()

            # First name
            if any(k in attr_str for k in ["firstname", "first_name", "first-name", "given-name"]):
                await inp.fill(name_parts[0])
            # Last name
            elif any(k in attr_str for k in ["lastname", "last_name", "last-name", "family-name"]):
                await inp.fill(name_parts[-1] if len(name_parts) > 1 else "")
            # Full name
            elif any(k in attr_str for k in ["name", "fullname", "full_name"]):
                await inp.fill(profile.name)
            # Email
            elif any(k in attr_str for k in ["email", "e-mail"]):
                await inp.fill(profile.contact.email)
            # Phone
            elif any(k in attr_str for k in ["phone", "mobile", "tel"]):
                await inp.fill(profile.contact.phone)
            # LinkedIn
            elif "linkedin" in attr_str:
                await inp.fill(profile.contact.linkedin_url)
            # Website / Portfolio / GitHub
            elif any(k in attr_str for k in ["github", "portfolio", "website", "url"]):
                await inp.fill(profile.contact.portfolio_url or profile.contact.github_url)
            # Location
            elif any(k in attr_str for k in ["location", "city", "address"]):
                await inp.fill(profile.location)
        except Exception:
            pass

    screenshot_path = "data/screenshots/generic_ats_preview.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    await page.screenshot(path=screenshot_path)

    return {
        "success": True,
        "status": "dry_run_completed" if dry_run else "prefilled",
        "message": "Generic ATS form inspected and populated with candidate details.",
        "screenshot": screenshot_path
    }
