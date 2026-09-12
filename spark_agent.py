"""
spark_agent.py — Autonomous Job Hunt & Application Agent for Gemini Spark
Runs the complete job search, ATS matching, LinkedIn post scanning,
referral finding, auto-apply, and Excel synchronization autonomously.
"""

import os
import sys
import argparse
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from core.profile import load_candidate_profile, CandidateProfile
from core.resume_parser import extract_text_from_pdf_file, generate_resume_pdf
from core.scorer import score_job_with_gemini, calculate_ats_match
from scrapers.job_scraper import JobScraper
from networking.post_scanner import LinkedInPostScanner
from networking.referral_finder import ReferralFinder
from networking.emailer import generate_cold_email_draft, send_cold_email
from automation.apply_engine import ApplyEngine
from storage.database import Database
from storage.excel_tracker import export_tracker_xlsx


console = Console()


class SparkJobAgent:
    def __init__(
        self,
        profile_path: str = "config/candidate_profile.yaml",
        resume_pdf_path: Optional[str] = None,
        db_path: str = "data/job_hunt.db",
        excel_path: str = "data/Job_Hunt_Tracker.xlsx",
        dry_run: bool = True,
        headless: bool = True
    ):
        self.profile = load_candidate_profile(profile_path)
        self.resume_pdf_path = resume_pdf_path
        if not self.resume_pdf_path:
            if os.path.exists("data/resumes/CV_RAVI_SHANKAR.pdf"):
                self.resume_pdf_path = "data/resumes/CV_RAVI_SHANKAR.pdf"
            elif os.path.exists("data/resumes/Candidate_Resume.pdf"):
                self.resume_pdf_path = "data/resumes/Candidate_Resume.pdf"
            elif os.path.exists("data/resumes"):
                pdfs = [os.path.join("data/resumes", f) for f in os.listdir("data/resumes") if f.endswith(".pdf")]
                if pdfs:
                    self.resume_pdf_path = pdfs[0]

        self.db = Database(db_path)
        self.excel_path = excel_path
        self.dry_run = dry_run
        self.headless = headless

        self.scraper = JobScraper()
        self.post_scanner = LinkedInPostScanner()
        self.referral_finder = ReferralFinder()
        self.apply_engine = ApplyEngine(self.profile, headless=self.headless, dry_run=self.dry_run)

        # Resume text buffer
        self.resume_text = ""
        if self.resume_pdf_path and os.path.exists(self.resume_pdf_path):
            try:
                self.resume_text = extract_text_from_pdf_file(self.resume_pdf_path)
                console.print(f"[bold green]✓ Ingested Resume PDF: {self.resume_pdf_path} ({len(self.resume_text)} chars)[/bold green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not extract resume PDF: {e}[/yellow]")

        if not self.resume_text:
            # Construct synthetic resume text from profile data
            self.resume_text = (
                f"{self.profile.name}\n{self.profile.headline}\n"
                f"Skills: {', '.join(self.profile.all_skills)}\n"
                f"Experience: {self.profile.experience}"
            )

    def run_discovery(
        self,
        role: Optional[str] = None,
        location: Optional[str] = None,
        limit_per_platform: int = 15,
        is_remote: bool = False
    ) -> List[Dict[str, Any]]:
        """Phase 1: Discover and score new jobs across platforms."""
        target_role = role or self.profile.primary_role
        target_loc = location or (self.profile.acceptable_locations[0] if self.profile.acceptable_locations else "Remote")

        console.print(f"[bold cyan]🔍 Discovering jobs for '{target_role}' in '{target_loc}'...[/bold cyan]")
        jobs = self.scraper.scrape(
            search_term=target_role,
            location=target_loc,
            results_wanted=limit_per_platform,
            is_remote=is_remote
        )
        console.print(f"[green]✓ Discovered {len(jobs)} total jobs across platforms[/green]")

        # Score jobs
        scored_jobs = []
        for j in jobs:
            score_res = score_job_with_gemini(
                resume_text=self.resume_text,
                job_title=j["title"],
                company=j["company"],
                job_description=j.get("description", ""),
                candidate_skills=self.profile.all_skills
            )
            j["match_score"] = score_res["match_score"]
            j["matched_keywords"] = score_res["matched_keywords"]
            j["missing_keywords"] = score_res["missing_keywords"]
            j["status"] = "shortlisted" if j["match_score"] >= 65.0 else "new"

            self.db.upsert_job(j)
            scored_jobs.append(j)

        return scored_jobs

    def run_post_scanning(self, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Phase 2: Monitor LinkedIn for live hiring posts and recruiter emails."""
        target_role = role or self.profile.primary_role
        console.print(f"[bold cyan]📢 Scanning LinkedIn posts for hiring announcements ({target_role})...[/bold cyan]")
        posts = self.post_scanner.scan_posts(
            target_role=target_role,
            target_skills=self.profile.core_skills
        )
        console.print(f"[green]✓ Found {len(posts)} relevant hiring posts[/green]")

        for p in posts:
            self.db.insert_linkedin_post(p)

        return posts

    def run_referral_search(self, company: str, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Phase 3: Search for top company employees on LinkedIn for referrals."""
        target_role = role or self.profile.primary_role
        console.print(f"[bold cyan]🤝 Searching referral contacts at {company}...[/bold cyan]")
        profiles = self.referral_finder.find_top_profiles(company=company, role=target_role)

        for prof in profiles:
            pitch_data = self.referral_finder.generate_outreach_pitch(
                contact_name=prof["name"],
                company=company,
                target_role=target_role,
                candidate_name=self.profile.name,
                candidate_summary=f"{self.profile.headline} with expertise in {', '.join(self.profile.core_skills[:3])}"
            )
            prof["connection_note"] = pitch_data["connection_note"]
            prof["referral_pitch"] = pitch_data["referral_message"]
            self.db.insert_referral_contact(prof)

        console.print(f"[green]✓ Saved {len(profiles)} referral contacts for {company}[/green]")
        return profiles

    async def run_auto_apply_top_jobs(self, top_n: int = 3, min_score: float = 70.0) -> List[Dict[str, Any]]:
        """Phase 4: Auto-apply to top shortlisted jobs using Playwright."""
        eligible_jobs = self.db.get_all_jobs(min_score=min_score, status="shortlisted")
        if not eligible_jobs:
            eligible_jobs = self.db.get_all_jobs(min_score=min_score)

        top_jobs = eligible_jobs[:top_n]
        if not top_jobs:
            console.print("[yellow]No eligible jobs above score threshold to apply.[/yellow]")
            return []

        console.print(f"[bold magenta]🚀 Starting automated application flow for {len(top_jobs)} jobs...[/bold magenta]")
        results = []

        # Ensure PDF resume exists for uploads
        pdf_path = self.resume_pdf_path
        if not pdf_path or not os.path.exists(pdf_path):
            pdf_path = "data/resumes/Candidate_Resume.pdf"
            generate_resume_pdf(self.resume_text, pdf_path, candidate_name=self.profile.name, target_role=self.profile.primary_role)

        for job in top_jobs:
            console.print(f"[cyan]Applying to {job['title']} @ {job['company']} (Score: {job['match_score']}%)...[/cyan]")
            apply_res = await self.apply_engine.apply_to_job(
                job_url=job["job_url"],
                resume_pdf_path=pdf_path,
                dry_run=self.dry_run
            )

            status = "submitted" if apply_res.get("status") == "submitted" else "pending_review"
            self.db.record_application(
                job_id=job["id"],
                company=job["company"],
                title=job["title"],
                applied_to=job["job_url"],
                apply_method=apply_res.get("platform", "web"),
                status=status,
                screenshot_path=apply_res.get("screenshot", ""),
                notes=apply_res.get("message", "")
            )
            results.append({"job": job, "result": apply_res})

        return results

    def sync_to_excel(self) -> str:
        """Phase 5: Synchronize all data into multi-tab formatted Excel tracker."""
        console.print(f"[bold cyan]📊 Syncing database to Excel ({self.excel_path})...[/bold cyan]")
        out_path = export_tracker_xlsx(self.excel_path, self.db)
        console.print(f"[bold green]✓ Excel Workbook updated: {out_path}[/bold green]")
        return out_path

    async def run_full_pipeline(self, role: Optional[str] = None, location: Optional[str] = None):
        """Execute complete end-to-end autonomous pipeline without manual intervention."""
        console.print(Panel.fit(
            f"[bold green]AutoJobPilot — Autonomous Spark Agent Pipeline[/bold green]\n"
            f"Candidate: [bold]{self.profile.name}[/bold] | Role: [bold]{role or self.profile.primary_role}[/bold]\n"
            f"Dry Run Mode: [bold]{self.dry_run}[/bold] (Set --live to enable real submissions)",
            title="AutoJobPilot"
        ))

        # 1. Discover and score
        jobs = self.run_discovery(role=role, location=location)

        # 2. LinkedIn Post Monitor
        self.run_post_scanning(role=role)

        # 3. Referral Finder for top 3 unique companies
        top_companies = list(dict.fromkeys([j["company"] for j in jobs if j.get("match_score", 0) >= 70]))[:3]
        for comp in top_companies:
            self.run_referral_search(company=comp, role=role)

        # 4. Auto Apply to top matching opportunities
        await self.run_auto_apply_top_jobs(top_n=3, min_score=70.0)

        # 5. Sync to Excel
        self.sync_to_excel()

        # Display summary table
        metrics = self.db.get_metrics()
        table = Table(title="Execution Summary", border_style="cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="green")
        table.add_row("Total Jobs Discovered", str(metrics["total_jobs"]))
        table.add_row("Shortlisted Jobs (Score >= 65%)", str(metrics["shortlisted_jobs"]))
        table.add_row("Applications Prepared / Submitted", str(metrics["applied_jobs"]))
        table.add_row("LinkedIn Hiring Leads", str(metrics["linkedin_leads"]))
        table.add_row("Referral Contacts Mapped", str(metrics["referral_contacts"]))
        table.add_row("Average Match Score", f"{metrics['avg_match_score']}%")
        table.add_row("Excel Tracker File", self.excel_path)
        console.print(table)


def main():
    parser = argparse.ArgumentParser(description="AutoJobPilot Autonomous Agent for Gemini Spark")
    parser.add_argument("--run-all", action="store_true", help="Run full pipeline autonomously")
    parser.add_argument("--search-only", action="store_true", help="Only discover and score jobs")
    parser.add_argument("--scan-posts", action="store_true", help="Only scan LinkedIn hiring posts")
    parser.add_argument("--find-referrals", type=str, help="Find referral contacts for a specific company")
    parser.add_argument("--apply-top", type=int, default=0, help="Apply to top N scored jobs")
    parser.add_argument("--role", type=str, default=None, help="Target job role")
    parser.add_argument("--location", type=str, default=None, help="Target location")
    parser.add_argument("--resume", type=str, default=None, help="Path to resume PDF")
    parser.add_argument("--live", action="store_true", help="Disable dry-run mode (enable live submissions)")
    parser.add_argument("--sync-excel", action="store_true", help="Sync database to Excel workbook")

    args = parser.parse_args()

    agent = SparkJobAgent(
        resume_pdf_path=args.resume,
        dry_run=not args.live
    )

    if args.run_all or len(sys.argv) == 1:
        asyncio.run(agent.run_full_pipeline(role=args.role, location=args.location))
    elif args.search_only:
        agent.run_discovery(role=args.role, location=args.location)
        agent.sync_to_excel()
    elif args.scan_posts:
        agent.run_post_scanning(role=args.role)
        agent.sync_to_excel()
    elif args.find_referrals:
        agent.run_referral_search(company=args.find_referrals, role=args.role)
        agent.sync_to_excel()
    elif args.apply_top > 0:
        asyncio.run(agent.run_auto_apply_top_jobs(top_n=args.apply_top))
        agent.sync_to_excel()
    elif args.sync_excel:
        agent.sync_to_excel()


if __name__ == "__main__":
    main()
