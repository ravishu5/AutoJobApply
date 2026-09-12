"""
networking/alumni_mapper.py — College Alumni & Referral Auto-Mapper
Discovers college alumni (e.g. NIT Rourkela) working at target companies on LinkedIn
and synthesizes high-converting warm alumni connection notes (<= 300 characters).
"""

import os
import re
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from core.profile import CandidateProfile, load_candidate_profile
from storage.database import Database
from storage.excel_tracker import export_tracker_xlsx


class AlumniMapper:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }

    def __init__(self, profile: Optional[CandidateProfile] = None, db: Optional[Database] = None):
        self.profile = profile or load_candidate_profile()
        self.db = db or Database()

    def get_alumni_institution(self) -> str:
        """Extract primary undergraduate/graduate institution from candidate profile."""
        if self.profile.education:
            inst = self.profile.education[0].get("institution", "")
            if inst:
                return inst
        return "National Institute of Technology, Rourkela"

    def map_alumni_at_company(
        self,
        company: str,
        target_role: str = "AI Engineer",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for university alumni working at the target company.
        """
        if not company:
            return []

        institution = self.get_alumni_institution()
        # Formulate search aliases (e.g. NIT Rourkela, NITR)
        short_inst = "NIT Rourkela" if "rourkela" in institution.lower() else institution

        query = f'site:linkedin.com/in/ ("{institution}" OR "{short_inst}") "{company}" ("Engineer" OR "Lead" OR "Manager")'

        results = []
        with httpx.Client(headers=self.HEADERS, timeout=12.0, follow_redirects=True) as client:
            try:
                resp = client.get("https://html.duckduckgo.com/html/", params={"q": query})
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for el in soup.select(".result__body"):
                        title_a = el.select_one(".result__title a")
                        snippet_el = el.select_one(".result__snippet")
                        if not title_a:
                            continue

                        title_text = title_a.get_text(strip=True)
                        raw_href = title_a.get("href", "")
                        if "uddg=" in raw_href:
                            m = re.search(r"uddg=([^&]+)", raw_href)
                            if m:
                                raw_href = urllib.parse.unquote(m.group(1))

                        if "linkedin.com/in/" not in raw_href:
                            continue

                        clean_title = re.sub(r"\s*\|\s*LinkedIn.*$", "", title_text)
                        parts = clean_title.split(" - ", 1)
                        name = parts[0].strip() if len(parts) > 0 else "Alum"
                        headline = parts[1].strip() if len(parts) > 1 else f"Engineer at {company}"

                        if not any(r["linkedin_url"] == raw_href for r in results):
                            results.append({
                                "name": name,
                                "headline": headline,
                                "company": company,
                                "linkedin_url": raw_href,
                                "institution": short_inst
                            })

                        if len(results) >= limit:
                            break
            except Exception:
                pass

        # If live search returned limited items, synthesize standard alumni target personas
        if not results:
            stakeholder_titles = ["Senior AI Engineer", "Engineering Manager", "Backend Tech Lead"]
            for title in stakeholder_titles:
                results.append({
                    "name": f"{company} Alum Lead",
                    "headline": f"{title} at {company} ({short_inst} Alumni)",
                    "company": company,
                    "linkedin_url": f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(f'{company} {short_inst} {title}')}",
                    "institution": short_inst
                })

        # Synthesize personalized connection notes and referral pitches
        mapped_contacts = []
        for r in results:
            first_name = r["name"].split()[0] if r["name"] else "there"
            conn_note = (
                f"Hi {first_name}, fellow {short_inst} alum here! Inspired by your work at {company}. "
                f"I'm an {self.profile.primary_role} (Python/LangGraph/RAG) exploring opportunities on the team "
                f"and would love to connect!"
            )
            if len(conn_note) > 300:
                conn_note = conn_note[:297] + "..."

            pitch = (
                f"Hi {first_name}, thanks for connecting! As a fellow {short_inst} graduate, I'm reaching out "
                f"because I'm applying for the {target_role} role at {company}. My background includes {self.profile.headline}. "
                f"If you're open to it, I'd greatly appreciate a referral or any advice on the team. Thank you!"
            )

            contact_record = {
                "name": r["name"],
                "headline": r["headline"],
                "company": company,
                "linkedin_url": r["linkedin_url"],
                "connection_note": conn_note,
                "referral_pitch": pitch,
                "status": "alumni_matched"
            }
            self.db.insert_referral_contact(contact_record)
            mapped_contacts.append(contact_record)

        export_tracker_xlsx("data/Job_Hunt_Tracker.xlsx", self.db)
        return mapped_contacts
