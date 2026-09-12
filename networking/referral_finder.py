"""
networking/referral_finder.py — LinkedIn Referral & Top Profile Finder
Discovers relevant company contacts (Engineering Managers, Tech Leads, Recruiters)
and generates tailored <= 300-char LinkedIn connection notes & referral pitches.
(Inspired by agentic-job-search and JobHunt Spark patterns)
"""

import os
import re
import json
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional


class ReferralFinder:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    def find_top_profiles(
        self,
        company: str,
        role: str = "Software Engineer",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for high-relevance employees at the target company on LinkedIn.
        """
        results = []
        if not company or company.lower() in ("unknown", "various"):
            return results

        queries = [
            f'site:linkedin.com/in/ "{company}" "engineering manager" OR "lead engineer" OR "tech lead"',
            f'site:linkedin.com/in/ "{company}" "technical recruiter" OR "talent acquisition"'
        ]

        with httpx.Client(headers=self.HEADERS, timeout=self.timeout, follow_redirects=True) as client:
            for q in queries:
                try:
                    resp = client.get("https://html.duckduckgo.com/html/", params={"q": q})
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

                            # Parse name and headline: e.g. "Sarah Chen - Senior Engineering Manager at Stripe | LinkedIn"
                            clean_title = re.sub(r"\s*\|\s*LinkedIn.*$", "", title_text)
                            parts = clean_title.split(" - ", 1)
                            name = parts[0].strip() if len(parts) > 0 else "Colleague"
                            headline = parts[1].strip() if len(parts) > 1 else f"Professional at {company}"

                            # Deduplicate
                            if not any(r["linkedin_url"] == raw_href for r in results):
                                results.append({
                                    "name": name,
                                    "headline": headline,
                                    "company": company,
                                    "linkedin_url": raw_href,
                                    "snippet": snippet_el.get_text(strip=True) if snippet_el else ""
                                })

                            if len(results) >= limit:
                                break
                    if len(results) >= limit:
                        break
                except Exception:
                    continue

        # If live web results are limited, synthesize top stakeholder search personas with direct LinkedIn search links
        if not results:
            stakeholder_roles = [
                f"Technical Talent Acquisition Lead",
                f"Senior Engineering Manager",
                f"Lead Software Engineer / Alumni"
            ]
            for s_role in stakeholder_roles:
                encoded_kw = urllib.parse.quote(f"{company} {s_role}")
                direct_search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_kw}"
                results.append({
                    "name": f"{s_role.split()[0]} Recruiter / Lead",
                    "headline": f"{s_role} at {company}",
                    "company": company,
                    "linkedin_url": direct_search_url,
                    "snippet": f"Key technical hiring stakeholder for {role} roles at {company}."
                })

        return results

    def generate_outreach_pitch(
        self,
        contact_name: str,
        company: str,
        target_role: str,
        candidate_name: str,
        candidate_summary: str,
        api_key: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate strict <= 300-char LinkedIn connection note and a longer referral request DM.
        """
        api_key = api_key or os.environ.get("GEMINI_API_KEY")

        if api_key:
            prompt = f"""You are an elite career agent. Write a personalized, high-conversion LinkedIn outreach package.
Target Person: {contact_name}
Target Company: {company}
Target Role: {target_role}
Candidate Name: {candidate_name}
Candidate Background: {candidate_summary}

Generate:
1. Strict 300-character-limit LinkedIn connection note. It MUST be <= 300 characters including spaces.
2. A warm, concise 100-word referral request message for when they accept the connection.

Return JSON:
{{
  "connection_note": "string under 300 chars",
  "referral_message": "string under 120 words"
}}
Return only JSON.
"""
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                clean_json = re.sub(r"^```json\s*", "", resp.text.strip())
                clean_json = re.sub(r"^```\s*", "", clean_json)
                clean_json = re.sub(r"\s*```$", "", clean_json).strip()
                data = json.loads(clean_json)
                note = data.get("connection_note", "")
                if len(note) > 300:
                    note = note[:297] + "..."
                return {
                    "connection_note": note,
                    "referral_message": data.get("referral_message", "")
                }
            except Exception:
                pass

        # High-converting default templates
        first_name = contact_name.split()[0] if contact_name else "there"
        connection_note = (
            f"Hi {first_name}, noticed your impactful work at {company}. As a {target_role.split()[0]} "
            f"engineer passionate about scaling robust systems, I'd love to connect and follow your team's journey."
        )
        if len(connection_note) > 300:
            connection_note = connection_note[:297] + "..."

        referral_message = (
            f"Hi {first_name}, thank you for connecting!\n\n"
            f"I've been closely following {company}'s tech innovations and saw the open {target_role} position. "
            f"With my background in building high-throughput systems and AI-driven platforms, I'd love to see if "
            f"my skills align with what your team needs. Would you be open to sharing a referral or pointing me "
            f"to the hiring manager?\n\nBest regards,\n{candidate_name}"
        )

        return {
            "connection_note": connection_note,
            "referral_message": referral_message
        }
