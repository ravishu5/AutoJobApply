"""
scrapers/guest_linkedin.py — Public LinkedIn Job Scraper
Scrapes jobs from LinkedIn's public guest search endpoints without requiring login.
"""

import re
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any


class GuestLinkedInScraper:
    BASE_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    JOB_DETAILS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def _clean_url(self, url: str) -> str:
        """Strip tracking parameters from LinkedIn job URL."""
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def search_jobs(
        self,
        keywords: str,
        location: str = "",
        limit: int = 25,
        is_remote: bool = False
    ) -> List[Dict[str, Any]]:
        """Scrape public LinkedIn job cards."""
        params = {
            "keywords": keywords,
            "location": location or "Worldwide",
            "start": 0,
        }
        if is_remote:
            params["f_WT"] = "2" # Remote filter in LinkedIn

        jobs = []
        with httpx.Client(headers=self.HEADERS, timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = client.get(self.BASE_SEARCH_URL, params=params)
                if resp.status_code != 200:
                    return []

                soup = BeautifulSoup(resp.content, "html.parser")
                cards = soup.select("li, .base-search-card")

                for card in cards:
                    title_el = card.select_one(".base-search-card__title")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)

                    company_el = card.select_one(".base-search-card__subtitle a") or card.select_one(".base-search-card__subtitle")
                    company = company_el.get_text(strip=True) if company_el else "Unknown Company"

                    location_el = card.select_one(".job-search-card__location")
                    loc = location_el.get_text(strip=True) if location_el else location

                    link_el = card.select_one("a.base-card__full-link") or card.select_one("a")
                    href = link_el.get("href", "") if link_el else ""
                    job_url = self._clean_url(href)

                    time_el = card.select_one("time")
                    date_posted = time_el.get("datetime", "") if time_el else ""

                    salary_el = card.select_one(".job-search-card__salary-info")
                    salary_text = salary_el.get_text(strip=True) if salary_el else ""

                    if job_url and title:
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": loc,
                            "job_url": job_url,
                            "source": "linkedin",
                            "salary_text": salary_text,
                            "date_posted": date_posted,
                            "description": f"{title} at {company}. Location: {loc}. {salary_text}".strip()
                        })

                    if len(jobs) >= limit:
                        break

            except Exception:
                pass

        return jobs
