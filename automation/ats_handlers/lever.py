"""
automation/ats_handlers/lever.py — Lever ATS Form Handler
Automates form filling and document upload on Lever job boards.
Uploads resume first to prevent Lever parser from overwriting fields.
"""

import asyncio
import os
from typing import Dict, Any
from playwright.async_api import Page
from core.profile import CandidateProfile
from automation.screening_agent import ScreeningAgent


async def handle_lever_application(
    page: Page,
    job_url: str,
    profile: CandidateProfile,
    screening_agent: ScreeningAgent,
    resume_pdf_path: str,
    dry_run: bool = True
) -> Dict[str, Any]:
    """Fill and optionally submit a Lever application."""
    await page.goto(job_url, wait_until="networkidle", timeout=60000)
    await asyncio.sleep(1.5)

    # Click apply button if on landing view
    apply_link = await page.query_selector("a.postings-btn, a[href*='apply'], button:has-text('Apply')")
    if apply_link:
        await apply_link.click()
        await asyncio.sleep(1.5)

    # Step 1: Upload resume FIRST (Lever parses resume asynchronously and might overwrite fields)
    if resume_pdf_path and os.path.exists(resume_pdf_path):
        try:
            file_input = await page.query_selector("input[type='file'][name*='resume'], input[type='file']")
            if file_input:
                await file_input.set_input_files(resume_pdf_path)
                await asyncio.sleep(2.0)
        except Exception:
            pass

    # Step 2: Fill personal fields
    field_mappings = [
        ("input[name='name']", profile.name),
        ("input[name='email']", profile.contact.email),
        ("input[name='phone']", profile.contact.phone),
        ("input[name='org']", profile.experience[0]["company"] if profile.experience else ""),
        ("input[name*='urls[LinkedIn]'], input[name*='linkedin']", profile.contact.linkedin_url),
        ("input[name*='urls[GitHub]'], input[name*='github']", profile.contact.github_url),
        ("input[name*='urls[Portfolio]'], input[name*='portfolio']", profile.contact.portfolio_url),
    ]

    for selector, val in field_mappings:
        if val:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    await el.fill(val)
            except Exception:
                pass

    # Step 3: Handle custom questions and textareas
    custom_textareas = await page.query_selector_all(".application-question textarea, .custom-question textarea")
    for ta in custom_textareas:
        try:
            lbl = await ta.evaluate("el => el.closest('.application-question')?.innerText || ''")
            if lbl and not await ta.input_value():
                ans = screening_agent.answer_question(lbl, "textarea")
                await ta.fill(ans)
        except Exception:
            pass

    screenshot_path = "data/screenshots/lever_preview.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    await page.screenshot(path=screenshot_path)

    if dry_run:
        return {
            "success": True,
            "status": "dry_run_completed",
            "message": "Lever form prefilled successfully. Stopped before final submission (Dry-Run mode).",
            "screenshot": screenshot_path
        }

    # Autonomous Submission
    submit_btn = await page.query_selector("button#btn-submit, button[type='submit'], button:has-text('Submit application')")
    if submit_btn:
        await submit_btn.click()
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2.0)
        conf_screenshot = "data/screenshots/lever_submitted.png"
        await page.screenshot(path=conf_screenshot)
        return {
            "success": True,
            "status": "submitted",
            "message": "Lever application submitted successfully!",
            "screenshot": conf_screenshot
        }

    return {
        "success": False,
        "status": "failed",
        "message": "Could not locate final submit button."
    }
