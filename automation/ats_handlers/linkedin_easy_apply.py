"""
automation/ats_handlers/linkedin_easy_apply.py — LinkedIn Easy Apply Multi-Step Stepper
Handles multi-page Easy Apply modal workflows:
Phone entry, resume upload, experience questions, next/review, and submit.
(Synthesized from JobPilot and Applied architectures)
"""

import asyncio
import os
from typing import Dict, Any, Optional
from playwright.async_api import Page
from core.profile import CandidateProfile
from automation.screening_agent import ScreeningAgent


async def handle_linkedin_easy_apply(
    page: Page,
    job_url: str,
    profile: CandidateProfile,
    screening_agent: ScreeningAgent,
    resume_pdf_path: str,
    dry_run: bool = True
) -> Dict[str, Any]:
    """Execute LinkedIn Easy Apply stepper workflow."""
    await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(2.0)

    # Click Easy Apply button
    easy_btn = await page.query_selector(
        "button.jobs-apply-button, button[aria-label*='Easy Apply'], button:has-text('Easy Apply')"
    )
    if not easy_btn:
        # Check for external apply button or company website link
        external_btn = await page.query_selector("a.jobs-apply-button, a[href*='apply'], a:has-text('Apply'), a:has-text('Apply on company website')")
        if external_btn:
            ext_url = await external_btn.get_attribute("href") or ""
            if ext_url:
                from automation.ats_handlers.generic_ats import handle_generic_application
                return await handle_generic_application(
                    page=page,
                    job_url=ext_url,
                    profile=profile,
                    screening_agent=screening_agent,
                    resume_pdf_path=resume_pdf_path,
                    dry_run=dry_run
                )

        return {
            "success": True,
            "status": "external_apply_ready",
            "message": "Direct external application portal identified. Ready for browser submission."
        }

    await easy_btn.click()
    await asyncio.sleep(2.0)

    # Wait for modal
    modal = await page.query_selector(".jobs-easy-apply-modal, [class*='easy-apply']")
    if not modal:
        return {
            "success": False,
            "status": "modal_error",
            "message": "Easy Apply modal did not appear."
        }

    # Step through multi-page modal (max 7 steps)
    max_steps = 7
    for step in range(max_steps):
        await asyncio.sleep(1.0)

        # 1. Fill phone number if empty
        phone_input = await page.query_selector("input[name*='phone'], input[aria-label*='phone'], input[id*='phone']")
        if phone_input:
            val = await phone_input.input_value()
            if not val and profile.contact.phone:
                await phone_input.fill(profile.contact.phone)

        # 2. Upload resume if file input present
        file_input = await page.query_selector("input[type='file']")
        if file_input and resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                await file_input.set_input_files(resume_pdf_path)
                await asyncio.sleep(1.0)
            except Exception:
                pass

        # 3. Handle radio / select / text questions
        questions = await page.query_selector_all(".jobs-easy-apply-form-section__grouping, .fb-dash-form-element")
        for q_el in questions:
            try:
                q_text = await q_el.inner_text()
                # Check for empty text inputs
                text_input = await q_el.query_selector("input[type='text'], textarea")
                if text_input and not await text_input.input_value():
                    ans = screening_agent.answer_question(q_text, "text")
                    await text_input.fill(ans)

                # Check for unselected radios (e.g. Yes/No questions)
                radios = await q_el.query_selector_all("input[type='radio']")
                if radios:
                    ans = screening_agent.answer_question(q_text, "radio")
                    for r in radios:
                        lbl = await r.evaluate("el => el.labels ? el.labels[0]?.innerText : ''")
                        if (ans.lower() == "yes" and "yes" in lbl.lower()) or (ans.lower() == "no" and "no" in lbl.lower()):
                            await r.check()
                            break
            except Exception:
                pass

        # 4. Check for Submit button (final step)
        submit_btn = await page.query_selector(
            "button[aria-label*='Submit'], button:has-text('Submit application')"
        )
        if submit_btn:
            screenshot_path = "data/screenshots/linkedin_easy_apply_preview.png"
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            await page.screenshot(path=screenshot_path)

            if dry_run:
                return {
                    "success": True,
                    "status": "dry_run_completed",
                    "message": "LinkedIn Easy Apply form prefilled. Paused before final submission.",
                    "screenshot": screenshot_path
                }
            else:
                await submit_btn.click()
                await asyncio.sleep(3.0)
                conf_shot = "data/screenshots/linkedin_easy_apply_submitted.png"
                await page.screenshot(path=conf_shot)
                return {
                    "success": True,
                    "status": "submitted",
                    "message": "LinkedIn Easy Apply application submitted successfully!",
                    "screenshot": conf_shot
                }

        # 5. Click Next or Review button
        next_btn = await page.query_selector(
            "button[aria-label*='Next'], button[aria-label*='Review'], button:has-text('Next'), button:has-text('Review')"
        )
        if next_btn:
            await next_btn.click()
        else:
            break

    screenshot_path = "data/screenshots/linkedin_easy_apply_stopped.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    await page.screenshot(path=screenshot_path)

    return {
        "success": True,
        "status": "stepper_ended",
        "message": "Processed available Easy Apply steps.",
        "screenshot": screenshot_path
    }
