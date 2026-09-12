"""
scrapers/auth_linkedin_scraper.py — Authenticated Early-Bird & Easy Apply Job Scraper
Searches LinkedIn member-only job listings with Early Applicant (<10 applicants, f_EA=true)
and Easy Apply (f_AL=true) filters using saved session cookies.
"""

import os
import json
import urllib.parse
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from automation.browser_manager import BrowserManager, DEFAULT_USER_AGENT, DEFAULT_LINKEDIN_SESSION_PATH
from scrapers.job_scraper import generate_canonical_id


class AuthenticatedLinkedInScraper:
    BASE_URL = "https://www.linkedin.com/jobs/search/"

    def __init__(self, session_path: str = DEFAULT_LINKEDIN_SESSION_PATH):
        self.session_path = session_path

    async def search_early_bird_jobs(
        self,
        keywords: str,
        location: str = "India",
        easy_apply_only: bool = True,
        under_10_applicants: bool = True,
        is_remote: bool = False,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Search LinkedIn using authenticated Playwright browser with member-exclusive filters.
        """
        if not BrowserManager.is_linkedin_authenticated(self.session_path):
            return []

        params = {
            "keywords": keywords,
            "location": location or "Remote",
        }
        if easy_apply_only:
            params["f_AL"] = "true" # Easy Apply
        if under_10_applicants:
            params["f_EA"] = "true" # Under 10 applicants
        if is_remote:
            params["f_WT"] = "2" # Remote

        search_url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        browser_mgr = BrowserManager(headless=True, storage_state_path=self.session_path)
        jobs: List[Dict[str, Any]] = []

        try:
            page = await browser_mgr.new_page()
            await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)

            # Wait for job list container
            await page.wait_for_selector(".scaffold-layout__list, .jobs-search__results-list, [data-view-name*='job-card']", timeout=12000)

            # Scroll down to load more cards
            for _ in range(3):
                await page.mouse.wheel(0, 1000)
                await page.wait_for_timeout(800)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            # Parse job cards from authenticated DOM
            cards = soup.select(".jobs-search-results-list__list-item, .job-card-container, [data-occludable-job-id]")

            for card in cards:
                title_el = card.select_one(".job-card-list__title--link, a[class*='job-card-list__title'], strong")
                company_el = card.select_one(".artdeco-entity-lockup__subtitle, .job-card-container__primary-description")
                loc_el = card.select_one(".job-card-container__metadata-item, .artdeco-entity-lockup__caption")
                link_el = card.select_one("a[href*='/jobs/view/']")

                title = title_el.get_text(strip=True) if title_el else ""
                company = company_el.get_text(strip=True) if company_el else ""
                loc = loc_el.get_text(strip=True) if loc_el else location

                if not title or not company:
                    continue

                raw_url = link_el.get("href", "") if link_el else ""
                if raw_url.startswith("/"):
                    raw_url = f"https://www.linkedin.com{raw_url}"

                parsed_url = urllib.parse.urlparse(raw_url)
                clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"

                job_id = generate_canonical_id(company, title, loc)

                jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "job_url": clean_url,
                    "description": f"Early Applicant Easy Apply Role for {title} @ {company}.",
                    "salary_min": None,
                    "salary_max": None,
                    "source": "linkedin_early_bird",
                    "status": "new",
                    "is_early_applicant": 1
                })

                if len(jobs) >= limit:
                    break

            return jobs

        except Exception:
            return []
        finally:
            await browser_mgr.close()
