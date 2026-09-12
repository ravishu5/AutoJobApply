"""
automation/apply_engine.py — Central Application Dispatcher
Identifies job application platform (Greenhouse, Lever, LinkedIn, Ashby, Generic),
orchestrates stealth browser automation, pre-fills forms, and records results.
"""

import os
from typing import Dict, Any, Optional
from automation.browser_manager import BrowserManager
from automation.screening_agent import ScreeningAgent
from automation.ats_handlers.greenhouse import handle_greenhouse_application
from automation.ats_handlers.lever import handle_lever_application
from automation.ats_handlers.linkedin_easy_apply import handle_linkedin_easy_apply
from automation.ats_handlers.generic_ats import handle_generic_application
from core.profile import CandidateProfile


def detect_platform(job_url: str) -> str:
    """Detect ATS system from job posting URL."""
    url_lower = (job_url or "").lower()
    if "greenhouse.io" in url_lower or "gh_jid=" in url_lower or "gh_src=" in url_lower:
        return "greenhouse"
    if "lever.co" in url_lower:
        return "lever"
    if "linkedin.com" in url_lower:
        return "linkedin_easy_apply"
    if "ashbyhq.com" in url_lower:
        return "ashby"
    if "bamboohr.com" in url_lower:
        return "bamboohr"
    return "generic"


class ApplyEngine:
    def __init__(self, profile: CandidateProfile, headless: bool = True, dry_run: bool = True):
        self.profile = profile
        self.headless = headless
        self.dry_run = dry_run
        self.screening_agent = ScreeningAgent(profile)

    async def apply_to_job(
        self,
        job_url: str,
        resume_pdf_path: Optional[str] = None,
        dry_run: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Apply to a single job URL using the appropriate ATS handler."""
        if not job_url:
            return {"success": False, "status": "invalid_url", "message": "No job URL provided."}

        is_dry_run = self.dry_run if dry_run is None else dry_run
        platform = detect_platform(job_url)

        browser_mgr = BrowserManager(headless=self.headless)
        try:
            page = await browser_mgr.new_page()

            if platform == "greenhouse":
                res = await handle_greenhouse_application(
                    page=page,
                    job_url=job_url,
                    profile=self.profile,
                    screening_agent=self.screening_agent,
                    resume_pdf_path=resume_pdf_path or "",
                    dry_run=is_dry_run
                )
            elif platform == "lever":
                res = await handle_lever_application(
                    page=page,
                    job_url=job_url,
                    profile=self.profile,
                    screening_agent=self.screening_agent,
                    resume_pdf_path=resume_pdf_path or "",
                    dry_run=is_dry_run
                )
            elif platform == "linkedin_easy_apply":
                res = await handle_linkedin_easy_apply(
                    page=page,
                    job_url=job_url,
                    profile=self.profile,
                    screening_agent=self.screening_agent,
                    resume_pdf_path=resume_pdf_path or "",
                    dry_run=is_dry_run
                )
            else:
                res = await handle_generic_application(
                    page=page,
                    job_url=job_url,
                    profile=self.profile,
                    screening_agent=self.screening_agent,
                    resume_pdf_path=resume_pdf_path or "",
                    dry_run=is_dry_run
                )

            res["platform"] = platform
            return res

        except Exception as e:
            return {
                "success": False,
                "status": "exception",
                "platform": platform,
                "message": f"Automation error: {str(e)}"
            }
        finally:
            await browser_mgr.close()
