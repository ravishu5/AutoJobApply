"""
scrapers/job_scraper.py — Unified Multi-Board Job Scraper
Orchestrates JobSpy (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google)
with fallback to direct scraping endpoints.
"""

import hashlib
import re
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from scrapers.guest_linkedin import GuestLinkedInScraper


def generate_canonical_id(company: str, title: str, location: str = "") -> str:
    """Generate a stable, deterministic ID for deduplication."""
    norm_comp = re.sub(r"[^a-z0-9]", "", (company or "").lower())
    norm_title = re.sub(r"[^a-z0-9]", "", (title or "").lower())
    norm_loc = re.sub(r"[^a-z0-9]", "", (location or "").lower())[:10]
    raw = f"{norm_comp}:{norm_title}:{norm_loc}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


class JobScraper:
    def __init__(self, verbose: int = 0):
        self.verbose = verbose
        self.guest_linkedin = GuestLinkedInScraper()

    def scrape(
        self,
        search_term: str,
        location: str = "Remote",
        results_wanted: int = 20,
        platforms: Optional[List[str]] = None,
        is_remote: bool = False,
        country_indeed: str = "usa",
        hours_old: int = 72
    ) -> List[Dict[str, Any]]:
        """
        Scrape jobs across multiple boards.
        Tries python-jobspy first, falls back to direct guest scrapers.
        """
        if not platforms:
            platforms = ["linkedin", "indeed", "glassdoor", "zip_recruiter", "google"]

        jobs: List[Dict[str, Any]] = []

        # Strategy 1: Attempt JobSpy
        try:
            from jobspy import scrape_jobs
            df = scrape_jobs(
                site_name=platforms,
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed=country_indeed,
                is_remote=is_remote,
                linkedin_fetch_description=True,
                verbose=self.verbose
            )

            if isinstance(df, pd.DataFrame) and not df.empty:
                for _, row in df.iterrows():
                    comp = str(row.get("company") or "Unknown")
                    titl = str(row.get("title") or search_term)
                    loc = str(row.get("location") or location)
                    job_url = str(row.get("job_url") or "")
                    desc = str(row.get("description") or "")
                    salary_min = row.get("min_amount")
                    salary_max = row.get("max_amount")
                    emails = str(row.get("emails") or "")

                    canon_id = generate_canonical_id(comp, titl, loc)

                    jobs.append({
                        "id": canon_id,
                        "title": titl,
                        "company": comp,
                        "location": loc,
                        "job_url": job_url,
                        "description": desc,
                        "salary_min": float(salary_min) if pd.notna(salary_min) else None,
                        "salary_max": float(salary_max) if pd.notna(salary_max) else None,
                        "currency": str(row.get("currency") or "USD"),
                        "interval": str(row.get("interval") or "yearly"),
                        "source": str(row.get("site") or "jobspy"),
                        "date_posted": str(row.get("date_posted") or datetime.utcnow().strftime("%Y-%m-%d")),
                        "emails": emails if emails != "None" else "",
                        "is_remote": bool(row.get("is_remote", is_remote)),
                        "status": "new"
                    })

                return jobs
        except Exception:
            # Fallback to direct scrapers if JobSpy is missing or fails
            pass

        # Strategy 2: Direct public guest LinkedIn scraper fallback
        if "linkedin" in platforms or not jobs:
            try:
                li_jobs = self.guest_linkedin.search_jobs(
                    keywords=search_term,
                    location=location,
                    limit=results_wanted,
                    is_remote=is_remote
                )
                for j in li_jobs:
                    canon_id = generate_canonical_id(j["company"], j["title"], j["location"])
                    jobs.append({
                        "id": canon_id,
                        "title": j["title"],
                        "company": j["company"],
                        "location": j["location"],
                        "job_url": j["job_url"],
                        "description": j["description"],
                        "salary_min": None,
                        "salary_max": None,
                        "currency": "USD",
                        "interval": "yearly",
                        "source": "linkedin",
                        "date_posted": j["date_posted"] or datetime.utcnow().strftime("%Y-%m-%d"),
                        "emails": "",
                        "is_remote": is_remote,
                        "status": "new"
                    })
            except Exception:
                pass

        return jobs
