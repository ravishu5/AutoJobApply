"""
networking/post_scanner.py — LinkedIn Hiring Post Monitor & Email Extractor
Scans public LinkedIn posts and discussions for hiring announcements,
extracting hiring manager/recruiter posts, role details, and direct contact emails.
"""

import re
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class LinkedInPostScanner:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def scan_posts(
        self,
        target_role: str = "Software Engineer",
        target_skills: Optional[List[str]] = None,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Search for real-time hiring posts on LinkedIn.
        Extracts author, company/team, snippet, post URL, and direct email address.
        """
        posts: List[Dict[str, Any]] = []
        skills_clause = f'("{target_skills[0]}")' if target_skills else ""
        query = f'site:linkedin.com/posts/ ("we\'re hiring" OR "hiring" OR "my team is hiring" OR "DM me your resume") "{target_role}" {skills_clause}'.strip()

        with httpx.Client(headers=self.HEADERS, timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = client.get("https://html.duckduckgo.com/html/", params={"q": query})
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    results = soup.select(".result__body")

                    for r in results:
                        link_el = r.select_one(".result__title a")
                        snippet_el = r.select_one(".result__snippet")

                        if not link_el:
                            continue

                        title_text = link_el.get_text(strip=True)
                        post_url = link_el.get("href", "")
                        # DuckDuckGo redirect unwrapping
                        if "uddg=" in post_url:
                            m = re.search(r"uddg=([^&]+)", post_url)
                            if m:
                                post_url = urllib.parse.unquote(m.group(1))

                        snippet_text = snippet_el.get_text(strip=True) if snippet_el else ""
                        full_text = f"{title_text} {snippet_text}"

                        # Extract author from title (e.g. "John Doe on LinkedIn: We are hiring...")
                        author_name = "Hiring Manager"
                        if " on LinkedIn:" in title_text:
                            author_name = title_text.split(" on LinkedIn:")[0].strip()
                        elif " | LinkedIn" in title_text:
                            author_name = title_text.split(" | LinkedIn")[0].strip()

                        # Extract company name if identifiable
                        company_match = re.search(r"@\s*([A-Za-z0-9\s]+)|at\s+([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)", full_text)
                        company = ""
                        if company_match:
                            company = (company_match.group(1) or company_match.group(2) or "").strip()
                        if not company:
                            company = "Tech Company"

                        # Extract emails
                        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", full_text)
                        valid_emails = [
                            e for e in emails if not any(x in e.lower() for x in ["example", "noreply", "sentry", "wix"])
                        ]
                        contact_email = valid_emails[0] if valid_emails else ""

                        posts.append({
                            "author": author_name,
                            "company": company,
                            "role": target_role,
                            "snippet": snippet_text[:350],
                            "post_url": post_url,
                            "email": contact_email,
                            "date_found": datetime.utcnow().strftime("%Y-%m-%d"),
                            "outreach_status": "draft_ready" if contact_email else "manual_dm_needed"
                        })

                        if len(posts) >= limit:
                            break
            except Exception:
                pass

        # Strategy 2: If public web search returned few leads, query active Hacker News 'Who is Hiring' calls
        if len(posts) < limit:
            try:
                kw = urllib.parse.quote(f"hiring {target_role}")
                hn_url = f"https://hn.algolia.com/api/v1/search?tags=comment&query={kw}&hitsPerPage=10"
                with httpx.Client(timeout=8.0) as client:
                    resp = client.get(hn_url)
                    if resp.status_code == 200:
                        hits = resp.json().get("hits", [])
                        for h in hits:
                            raw_comment = h.get("comment_text", "")
                            # strip basic html tags
                            clean_text = re.sub(r"<[^>]+>", " ", raw_comment)
                            emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", clean_text)
                            author = h.get("author", "Hiring Lead")

                            # Parse company from first line e.g. "Stripe | San Francisco | Remote"
                            first_line = clean_text.splitlines()[0] if clean_text.splitlines() else ""
                            comp = first_line.split("|")[0].strip() if "|" in first_line else "Tech Startup"

                            item_id = h.get("objectID", "")
                            post_url = f"https://news.ycombinator.com/item?id={item_id}" if item_id else "https://news.ycombinator.com"

                            posts.append({
                                "author": author,
                                "company": comp[:40],
                                "role": target_role,
                                "snippet": clean_text[:350].strip(),
                                "post_url": post_url,
                                "email": emails[0] if emails else "",
                                "date_found": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                "outreach_status": "draft_ready" if emails else "manual_dm_needed"
                            })
                            if len(posts) >= limit:
                                break
            except Exception:
                pass

        return posts
