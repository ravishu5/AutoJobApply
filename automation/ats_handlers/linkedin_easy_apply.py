"""
automation/ats_handlers/linkedin_easy_apply.py — LinkedIn Easy Apply Multi-Step Stepper
Handles multi-page Easy Apply modal workflows:
Phone entry, resume upload, experience questions, next/review, and submit.
Supports modern LinkedIn DOM variations (dialog elements, dynamic classes, obfuscated layouts).
"""

import asyncio
import os
from typing import Dict, Any, Optional
from playwright.async_api import Page
from core.profile import CandidateProfile
from automation.screening_agent import ScreeningAgent
from scrapers.job_poster_extractor import extract_job_poster


async def handle_linkedin_easy_apply(
    page: Page,
    job_url: str,
    profile: CandidateProfile,
    screening_agent: ScreeningAgent,
    resume_pdf_path: str,
    dry_run: bool = True
) -> Dict[str, Any]:
    """Execute LinkedIn Easy Apply stepper workflow with adaptive selector detection."""
    await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(2.0)

    # 1. Unmask and extract hiring manager/recruiter details if available
    hiring_manager = await extract_job_poster(page)

    # 2. Click Easy Apply button
    easy_btn = await page.query_selector(
        "button.jobs-apply-button, button[aria-label*='Easy Apply'], button:has-text('Easy Apply')"
    )
    if not easy_btn:
        # Check for external apply button or company website link
        external_btn = await page.query_selector(
            "a.jobs-apply-button, a[href*='apply'], a:has-text('Apply'), a:has-text('Apply on company website')"
        )
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

    # 3. Detect Easy Apply modal/dialog container
    modal_selectors = [
        "dialog",
        "[role='dialog']",
        ".artdeco-modal",
        ".jobs-easy-apply-modal",
        "[class*='easy-apply']",
        "header:has-text('Apply to')",
        "div:has-text('Apply to')",
    ]

    modal = None
    for sel in modal_selectors:
        try:
            modal = await page.wait_for_selector(sel, timeout=3000)
            if modal:
                break
        except Exception:
            continue

    if not modal:
        # Fallback heuristic: check if page body contains Easy Apply indicators
        try:
            body_text = await page.inner_text("body")
            if any(sig in body_text for sig in ["Apply to", "Contact info", "Review your application", "pages"]):
                modal = await page.query_selector("body")
        except Exception:
            pass

    if not modal:
        os.makedirs("data/screenshots", exist_ok=True)
        await page.screenshot(path="data/screenshots/linkedin_modal_error.png")
        return {
            "success": False,
            "status": "modal_error",
            "message": "Easy Apply modal did not appear. Screenshot saved to data/screenshots/linkedin_modal_error.png."
        }

    # 4. Multi-step stepper navigation (up to 8 steps)
    max_steps = 8
    for step in range(max_steps):
        await asyncio.sleep(1.5)

        # Check for final Submit button
        submit_btn = await page.query_selector(
            "button:has-text('Submit application'), button[aria-label*='Submit application'], button:has-text('Submit')"
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
                    "screenshot": screenshot_path,
                    "hiring_manager": hiring_manager
                }
            else:
                try:
                    await submit_btn.scroll_into_view_if_needed()
                    await submit_btn.click()
                except Exception:
                    await submit_btn.evaluate("el => el.click()")
                await asyncio.sleep(4.0)
                conf_shot = "data/screenshots/linkedin_easy_apply_submitted.png"
                os.makedirs(os.path.dirname(conf_shot), exist_ok=True)
                await page.screenshot(path=conf_shot)
                return {
                    "success": True,
                    "status": "submitted",
                    "message": "LinkedIn Easy Apply application submitted successfully!",
                    "screenshot": conf_shot,
                    "hiring_manager": hiring_manager
                }

        # Step-specific fills:
        # A. Fill Phone number if empty
        phone_input = await page.query_selector(
            "input[type='tel'], input[name*='phone'], input[aria-label*='phone'], input[id*='phone']"
        )
        if phone_input:
            val = await phone_input.input_value()
            if not val and profile.contact.phone:
                await phone_input.fill(profile.contact.phone)

        # B. Handle resume upload / selection if on resume step
        file_input = await page.query_selector("input[type='file']")
        if file_input and resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                # Check if a pre-uploaded resume radio is already checked
                checked_radio = await page.query_selector("input[type='radio']:checked")
                if not checked_radio:
                    await file_input.set_input_files(resume_pdf_path)
                    await asyncio.sleep(1.0)
            except Exception:
                pass

        # C. Answer open-ended, numeric, or text questions
        text_inputs = await page.query_selector_all(
            "input[type='text'], input[type='number'], textarea"
        )
        for inp in text_inputs:
            try:
                # Check if visible and empty
                is_visible = await inp.is_visible()
                if not is_visible:
                    continue
                val = await inp.input_value()
                if not val:
                    # Determine question context from aria-label, label, or surrounding text
                    q_text = await inp.get_attribute("aria-label") or ""
                    if not q_text:
                        id_ = await inp.get_attribute("id") or ""
                        if id_:
                            lbl = await page.query_selector(f"label[for='{id_}']")
                            if lbl:
                                q_text = await lbl.inner_text()
                    if not q_text:
                        # Inspect parent element text
                        q_text = await inp.evaluate("el => el.closest('div')?.innerText || ''")

                    input_type = await inp.get_attribute("type") or "text"
                    ans = screening_agent.answer_question(q_text, input_type)
                    if ans:
                        await inp.fill(ans)
            except Exception:
                pass

        # D. Answer radio button questions (e.g., Yes/No questions)
        radios = await page.query_selector_all("input[type='radio']")
        if radios:
            try:
                # Group radios by question or parent group
                groups = await page.query_selector_all("fieldset, [role='radiogroup']")
                for grp in groups:
                    legend = await grp.query_selector("legend, [class*='legend']")
                    q_text = await legend.inner_text() if legend else await grp.inner_text()
                    ans = screening_agent.answer_question(q_text, "radio")
                    grp_radios = await grp.query_selector_all("input[type='radio']")
                    for r in grp_radios:
                        lbl_text = await r.evaluate("el => el.labels ? el.labels[0]?.innerText : ''")
                        if not lbl_text:
                            lbl_text = await r.evaluate("el => el.parentElement?.innerText || ''")
                        if (ans.lower() == "yes" and "yes" in lbl_text.lower()) or \
                           (ans.lower() == "no" and "no" in lbl_text.lower()):
                            await r.check()
                            break
            except Exception:
                pass

        # E. Click Review or Next button
        nav_btn = await page.query_selector(
            "button:has-text('Review'), button[aria-label*='Review'], button:has-text('Next'), button[aria-label*='Next']"
        )
        if nav_btn:
            await nav_btn.click()
            await asyncio.sleep(2.0)
        else:
            break

    # After max steps, capture final state screenshot
    screenshot_path = "data/screenshots/linkedin_easy_apply_preview.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    await page.screenshot(path=screenshot_path)

    # Final check if Submit button became visible on the final screen
    final_submit = await page.query_selector(
        "button:has-text('Submit application'), button[aria-label*='Submit application'], button:has-text('Submit')"
    )
    if final_submit:
        if dry_run:
            return {
                "success": True,
                "status": "dry_run_completed",
                "message": "LinkedIn Easy Apply form prefilled. Paused before final submission.",
                "screenshot": screenshot_path,
                "hiring_manager": hiring_manager
            }
        else:
            try:
                await final_submit.scroll_into_view_if_needed()
                await final_submit.click()
            except Exception:
                await final_submit.evaluate("el => el.click()")
            await asyncio.sleep(4.0)
            conf_shot = "data/screenshots/linkedin_easy_apply_submitted.png"
            os.makedirs(os.path.dirname(conf_shot), exist_ok=True)
            await page.screenshot(path=conf_shot)
            return {
                "success": True,
                "status": "submitted",
                "message": "LinkedIn Easy Apply application submitted successfully!",
                "screenshot": conf_shot,
                "hiring_manager": hiring_manager
            }

    return {
        "success": True,
        "status": "stepper_ended",
        "message": "Processed available Easy Apply steps.",
        "screenshot": screenshot_path,
        "hiring_manager": hiring_manager
    }
