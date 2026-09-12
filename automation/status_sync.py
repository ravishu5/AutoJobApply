"""
automation/status_sync.py — LinkedIn Applied Jobs & Recruiter Activity Sync
Navigates to the member's applied jobs tracker on LinkedIn to detect real-time recruiter actions:
'Application viewed', 'Resume downloaded', 'In review', or 'Submitted'.
"""

import asyncio
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from automation.browser_manager import BrowserManager, DEFAULT_LINKEDIN_SESSION_PATH
from storage.database import Database
from storage.excel_tracker import export_tracker_xlsx


class LinkedInStatusSync:
    APPLIED_JOBS_URL = "https://www.linkedin.com/my-items/applied-jobs/"

    def __init__(self, db: Optional[Database] = None, session_path: str = DEFAULT_LINKEDIN_SESSION_PATH):
        self.db = db or Database()
        self.session_path = session_path

    async def sync_applications(self, headless: bool = True) -> Dict[str, Any]:
        """
        Scrape LinkedIn applied jobs history and update application records with recruiter feedback signals.
        """
        if not BrowserManager.is_linkedin_authenticated(self.session_path):
            return {
                "success": False,
                "status": "not_authenticated",
                "message": "LinkedIn session not active. Please authenticate first."
            }

        browser_mgr = BrowserManager(headless=headless, storage_state_path=self.session_path)
        synced_records = []

        try:
            page = await browser_mgr.new_page()
            await page.goto(self.APPLIED_JOBS_URL, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3.0)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            # Extract list items in applied jobs
            items = soup.select(".entity-result, [data-chameleon-result-urn], .scaffold-layout__list-item, li")

            for item in items:
                title_el = item.select_one(".entity-result__title-text a, a[href*='/jobs/view/'], strong")
                company_el = item.select_one(".entity-result__primary-subtitle, .artdeco-entity-lockup__subtitle")
                badge_el = item.select_one(".entity-result__badge, .entity-result__badge-text, [class*='badge'], span")

                if not title_el or not company_el:
                    continue

                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True)
                badge_text = badge_el.get_text(strip=True) if badge_el else "Applied"

                # Check for recruiter signals in the whole item text
                full_text = item.get_text(" ", strip=True)
                recruiter_signal = "Applied"
                if "downloaded" in full_text.lower():
                    recruiter_signal = "Resume Downloaded by Recruiter"
                elif "viewed" in full_text.lower():
                    recruiter_signal = "Application Viewed by Recruiter"
                elif "in review" in full_text.lower():
                    recruiter_signal = "In Review"

                # Update in database
                updated = self.db.update_application_recruiter_status(
                    company=company,
                    title=title,
                    recruiter_status=recruiter_signal
                )

                synced_records.append({
                    "title": title,
                    "company": company,
                    "recruiter_status": recruiter_signal,
                    "db_updated": updated
                })

            # Update Excel tracker
            export_tracker_xlsx("data/Job_Hunt_Tracker.xlsx", self.db)

            return {
                "success": True,
                "status": "synced",
                "total_found": len(synced_records),
                "records": synced_records,
                "message": f"Successfully synced {len(synced_records)} LinkedIn applications with recruiter activity."
            }

        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Failed to sync applied jobs: {e}"
            }
        finally:
            await browser_mgr.close()
