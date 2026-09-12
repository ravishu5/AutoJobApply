"""
automation/ats_handlers/greenhouse.py — Greenhouse ATS Form Handler
Automates form filling and document upload on Greenhouse job boards.
"""

import asyncio
import os
from typing import Dict, Any, Optional
from playwright.async_api import Page
from core.profile import CandidateProfile
from automation.screening_agent import ScreeningAgent


async def handle_greenhouse_application(
    page: Page,
    job_url: str,
    profile: CandidateProfile,
    screening_agent: ScreeningAgent,
    resume_pdf_path: str,
    dry_run: bool = True
) -> Dict[str, Any]:
    """Fill and optionally submit a Greenhouse application."""
    await page.goto(job_url, wait_until="networkidle", timeout=60000)
    await asyncio.sleep(1.5)

    name_parts = profile.name.split()
    first_name = name_parts[0] if name_parts else "Candidate"
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    # Common Greenhouse input selectors
    field_mappings = [
        ("#first_name, input[name='first_name'], input[autocomplete='given-name']", first_name),
        ("#last_name, input[name='last_name'], input[autocomplete='family-name']", last_name),
        ("#email, input[name='email'], input[type='email']", profile.contact.email),
        ("#phone, input[name='phone'], input[type='tel']", profile.contact.phone),
    ]

    for selector, val in field_mappings:
        if val:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    await el.fill(val)
            except Exception:
                pass

    # LinkedIn and Website URLs
    url_mappings = [
        ("input[name*='linkedin'], input[id*='linkedin'], input[aria-label*='LinkedIn']", profile.contact.linkedin_url),
        ("input[name*='website'], input[name*='portfolio'], input[id*='website']", profile.contact.portfolio_url or profile.contact.github_url)
    ]
    for selector, val in url_mappings:
        if val:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    await el.fill(val)
            except Exception:
                pass

    # Resume upload
    if resume_pdf_path and os.path.exists(resume_pdf_path):
        try:
            file_input = await page.query_selector("input[type='file'][name*='resume'], input[type='file']")
            if file_input:
                await file_input.set_input_files(resume_pdf_path)
                await asyncio.sleep(1.0)
        except Exception:
            pass

    # Answer custom questions if present
    custom_fields = await page.query_selector_all(".field label, .custom-question label")
    for lbl in custom_fields:
        try:
            q_text = await lbl.inner_text()
            for_attr = await lbl.get_attribute("for")
            if for_attr and q_text:
                inp = await page.query_selector(f"#{for_attr}")
                if inp and await inp.is_visible():
                    tag_name = await inp.evaluate("el => el.tagName.toLowerCase()")
                    if tag_name in ("input", "textarea"):
                        curr_val = await inp.input_value()
                        if not curr_val:
                            ans = screening_agent.answer_question(q_text, tag_name)
                            await inp.fill(ans)
        except Exception:
            pass

    # Check for Submit button
    submit_btn = await page.query_selector(
        "button#submit_app, input[type='submit'][value*='Submit'], button:has-text('Submit Application')"
    )

    screenshot_path = "data/screenshots/greenhouse_preview.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    await page.screenshot(path=screenshot_path)

    if dry_run:
        return {
            "success": True,
            "status": "dry_run_completed",
            "message": "Greenhouse form prefilled successfully. Stopped before final submission (Dry-Run mode).",
            "screenshot": screenshot_path
        }

    # Autonomous Submission
    if submit_btn:
        await submit_btn.click()
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2.0)
        conf_screenshot = "data/screenshots/greenhouse_submitted.png"
        await page.screenshot(path=conf_screenshot)
        return {
            "success": True,
            "status": "submitted",
            "message": "Greenhouse application submitted successfully!",
            "screenshot": conf_screenshot
        }

    return {
        "success": False,
        "status": "failed",
        "message": "Could not locate final submit button."
    }
