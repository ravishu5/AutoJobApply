"""
networking/connection_sender.py — LinkedIn 1-Click Connection Request Sender
Safely connects with hiring managers and referral contacts with personalized <= 300-character notes,
enforcing strict daily quotas (max 15/day) and human-like typing jitter to protect account health.
"""

import os
import asyncio
import random
from typing import Dict, Any, Optional
from automation.browser_manager import BrowserManager
from storage.database import Database


class ConnectionSender:
    def __init__(self, db: Optional[Database] = None, max_daily_connections: int = 15):
        self.db = db or Database()
        self.max_daily_connections = max_daily_connections

    async def send_connection_request(
        self,
        profile_url: str,
        note: str,
        name: str = "Contact",
        company: str = "",
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        Navigate to a LinkedIn profile and send a connection request with a personalized note.
        Enforces daily rate limits and natural delays.
        """
        if not profile_url:
            return {"success": False, "status": "invalid_url", "message": "No profile URL provided."}

        # 1. Enforce safety limit
        if not self.db.can_send_connection(max_daily=self.max_daily_connections):
            sent_count = self.db.get_daily_connection_count()
            return {
                "success": False,
                "status": "rate_limited",
                "message": f"Daily safety limit reached ({sent_count}/{self.max_daily_connections}). Try again tomorrow to keep your account safe."
            }

        # 2. Check LinkedIn authentication
        if not BrowserManager.is_linkedin_authenticated():
            return {
                "success": False,
                "status": "not_authenticated",
                "message": "No active LinkedIn session found. Please log in first via the dashboard or 'python spark_agent.py --login-linkedin'."
            }

        # Sanitize note (LinkedIn strictly limits to 300 characters for personal notes)
        clean_note = note.strip()
        if len(clean_note) > 300:
            clean_note = clean_note[:297] + "..."

        browser_mgr = BrowserManager(headless=headless)
        try:
            page = await browser_mgr.new_page()
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(random.uniform(2.5, 4.0)) # Human pause

            # Check if already connected or invitation pending
            pending_badge = await page.query_selector("button:has-text('Pending'), button[aria-label*='Pending']")
            if pending_badge:
                return {
                    "success": True,
                    "status": "already_pending",
                    "message": f"Connection invitation to {name} is already pending."
                }

            # 3. Locate the Connect button
            connect_btn = await page.query_selector(
                "button.pvs-profile-actions__action:has-text('Connect'), "
                "button[aria-label*='Invite'][aria-label*='to connect'], "
                "main button:has-text('Connect')"
            )

            # If not directly visible, check the 'More' dropdown
            if not connect_btn:
                more_btn = await page.query_selector(
                    "button[aria-label='More actions'], "
                    "button:has-text('More'), "
                    ".pvs-profile-actions button:has-text('More')"
                )
                if more_btn:
                    await more_btn.click()
                    await asyncio.sleep(1.0)
                    connect_btn = await page.query_selector(
                        "div[role='button']:has-text('Connect'), "
                        "span:has-text('Connect'), "
                        "[aria-label*='Invite'][aria-label*='to connect']"
                    )

            if not connect_btn:
                return {
                    "success": False,
                    "status": "button_not_found",
                    "message": f"Could not locate 'Connect' button on {name}'s profile (may require InMail or email)."
                }

            # Click Connect
            await connect_btn.click()
            await asyncio.sleep(random.uniform(1.5, 2.5))

            # 4. Handle "Add a note" modal
            add_note_btn = await page.query_selector(
                "button[aria-label='Add a note'], "
                "button:has-text('Add a note')"
            )

            if add_note_btn and clean_note:
                await add_note_btn.click()
                await asyncio.sleep(1.0)

                textarea = await page.query_selector("textarea[name='message'], #custom-message, textarea")
                if textarea:
                    # Simulate human typing jitter
                    await textarea.fill(clean_note)
                    await asyncio.sleep(random.uniform(1.0, 2.0))

            # 5. Click Send invitation
            send_btn = await page.query_selector(
                "button[aria-label='Send invitation'], "
                "button[aria-label='Send now'], "
                "button:has-text('Send invitation'), "
                "button:has-text('Send')"
            )

            if send_btn:
                await send_btn.click()
                await asyncio.sleep(2.5)

                # Record in database
                self.db.record_sent_connection(
                    profile_url=profile_url,
                    name=name,
                    company=company,
                    note=clean_note,
                    status="sent"
                )

                screenshot_path = f"data/screenshots/connection_{random.randint(1000, 9999)}.png"
                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                try:
                    await page.screenshot(path=screenshot_path)
                except Exception:
                    screenshot_path = ""

                return {
                    "success": True,
                    "status": "sent",
                    "message": f"Connection invitation with personalized note sent to {name}!",
                    "screenshot": screenshot_path,
                    "remaining_today": self.max_daily_connections - self.db.get_daily_connection_count()
                }

            return {
                "success": False,
                "status": "modal_error",
                "message": "Connection modal was opened, but 'Send' button was not accessible."
            }

        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Failed to send connection request: {e}"
            }
        finally:
            await browser_mgr.close()
