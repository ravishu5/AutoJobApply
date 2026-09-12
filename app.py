"""
app.py — AutoJobPilot Web Dashboard
Modern, rich UI for autonomous job hunting, ATS scoring,
multi-board search, Playwright auto-apply, and Excel tracking.
"""

import streamlit as st
import os
import asyncio
import pandas as pd
from datetime import datetime

# Initialize page configuration
st.set_page_config(
    page_title="AutoJobPilot — Autonomous AI Job Hunter",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-End Styling (Glassmorphism, Vibrant Dark Mode Accents, Modern Typography)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }

    /* Metric Cards */
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 700;
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        margin-bottom: 16px;
    }

    /* Gradient Hero Header */
    .hero-container {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 27, 75, 0.8) 100%);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 20px;
        padding: 28px 36px;
        margin-bottom: 28px;
        box-shadow: 0 10px 40px -10px rgba(79, 70, 229, 0.3);
    }
    .hero-title {
        font-size: 2.3rem;
        font-weight: 700;
        background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1.05rem;
    }

    /* Job Card Styling */
    .job-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 14px;
        padding: 18px 24px;
        margin-bottom: 14px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .job-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        transform: translateY(-2px);
    }

    /* Badge Tags */
    .badge-score-high {
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.3);
        padding: 3px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-score-med {
        background: rgba(234, 179, 8, 0.15);
        color: #facc15;
        border: 1px solid rgba(234, 179, 8, 0.3);
        padding: 3px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-platform {
        background: rgba(99, 102, 241, 0.15);
        color: #818cf8;
        border: 1px solid rgba(99, 102, 241, 0.3);
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
    }

    /* Code & Output Blocks */
    .code-box {
        font-family: 'JetBrains Mono', monospace;
        background: #0f172a;
        color: #e2e8f0;
        padding: 14px;
        border-radius: 10px;
        border: 1px solid #334155;
        font-size: 0.88rem;
    }
</style>
""", unsafe_allow_html=True)

# Imports of Application Modules
from core.profile import load_candidate_profile, save_candidate_profile, CandidateProfile
from core.resume_parser import extract_text_from_pdf_bytes, generate_resume_pdf
from core.scorer import score_job_with_gemini, calculate_ats_match
from scrapers.job_scraper import JobScraper
from scrapers.auth_linkedin_scraper import AuthenticatedLinkedInScraper
from scrapers.contact_finder import find_hiring_contact
from networking.post_scanner import LinkedInPostScanner
from networking.referral_finder import ReferralFinder
from networking.alumni_mapper import AlumniMapper
from networking.emailer import generate_cold_email_draft, send_cold_email
from networking.connection_sender import ConnectionSender
from networking.post_engager import generate_tailored_post_comment, PostEngager
from automation.apply_engine import ApplyEngine, detect_platform
from automation.browser_manager import BrowserManager, interactive_linkedin_login
from automation.status_sync import LinkedInStatusSync
from storage.database import Database
from storage.excel_tracker import export_tracker_xlsx

# State Initialization
if "db" not in st.session_state:
    st.session_state.db = Database()
if "profile" not in st.session_state:
    st.session_state.profile = load_candidate_profile()
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "apply_results" not in st.session_state:
    st.session_state.apply_results = {}

db = st.session_state.db
profile = st.session_state.profile

# --- Sidebar ---
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/lightning-bolt.png", width=64)
    st.markdown("### **AutoJobPilot**")
    st.caption("Autonomous AI Job Hunter & Application Suite")
    st.divider()

    # Active Candidate Badge
    st.markdown(f"**Candidate:** `{profile.name}`")
    st.markdown(f"**Target Role:** `{profile.primary_role}`")
    st.caption(f"📍 {profile.location}")
    st.divider()

    # Execution Mode Toggles
    st.markdown("#### ⚙️ Automation Settings")
    dry_run_mode = st.toggle("Dry Run Safety Mode", value=True, help="When enabled, Playwright fills forms but halts before final submission.")
    headless_mode = st.toggle("Headless Browser", value=True, help="Run Playwright invisibly in the background.")
    api_key_input = st.text_input("Gemini API Key (Optional)", value=os.environ.get("GEMINI_API_KEY", ""), type="password")
    if api_key_input:
        os.environ["GEMINI_API_KEY"] = api_key_input

    st.divider()

    # Quick Metrics
    metrics = db.get_metrics()
    st.metric("Discovered Jobs", metrics["total_jobs"])
    st.metric("Applications Submitted", metrics["applied_jobs"])
    st.metric("LinkedIn Leads", metrics["linkedin_leads"])
    st.metric("Avg Match Score", f"{metrics['avg_match_score']}%")

    st.divider()
    # Excel Download Shortcut
    if st.button("📥 Generate & Download Excel Tracker", use_container_width=True, type="primary"):
        excel_file = export_tracker_xlsx("data/Job_Hunt_Tracker.xlsx", db)
        with open(excel_file, "rb") as f:
            st.download_button(
                label="⬇️ Save Job_Hunt_Tracker.xlsx",
                data=f.read(),
                file_name="Job_Hunt_Tracker.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )


# --- Hero Header ---
st.markdown("""
<div class="hero-container">
    <div class="hero-title">AutoJobPilot — Autonomous Career Agent</div>
    <div class="hero-subtitle">Multi-Platform Job Search • ATS Keyword Optimizer • Playwright Auto-Apply • LinkedIn Hiring Radar • Excel Sync</div>
</div>
""", unsafe_allow_html=True)


# --- Navigation Tabs ---
tab_jobs, tab_apply, tab_posts, tab_referrals, tab_profile, tab_excel = st.tabs([
    "💼 Job Discovery",
    "🤖 Auto-Apply Center",
    "📢 LinkedIn Hiring Radar",
    "🤝 Referral Network",
    "🎯 Resume & ATS Auditor",
    "📊 Master Tracker & Excel"
])


# =============================================================================
# TAB 1: JOB DISCOVERY
# =============================================================================
with tab_jobs:
    st.subheader("Multi-Board Job Discovery")
    st.caption("Scrape LinkedIn, Indeed, Glassdoor, ZipRecruiter, and Google concurrently with ATS keyword scoring.")

    col1, col2, col3, col4 = st.columns([3, 2, 2, 1.5])
    with col1:
        search_query = st.text_input("Target Role / Title", value=profile.primary_role)
    with col2:
        search_loc = st.text_input("Location", value=profile.location or "Remote")
    with col3:
        platforms_selected = st.multiselect(
            "Platforms",
            ["linkedin", "indeed", "glassdoor", "zip_recruiter", "google"],
            default=["linkedin", "indeed", "glassdoor"]
        )
    with col4:
        st.write("")
        st.write("")
        trigger_search = st.button("🔍 Search Jobs", use_container_width=True, type="primary")

    is_li_auth = BrowserManager.is_linkedin_authenticated()
    col_eb1, col_eb2 = st.columns([2.5, 1.5])
    with col_eb2:
        trigger_early_bird = st.button(
            "⚡ Early-Bird LinkedIn (<10 Applicants)",
            disabled=not is_li_auth,
            help="Member-only search: Easy Apply & <10 applicants.",
            use_container_width=True
        )

    if trigger_early_bird and search_query:
        with st.status(f"Scanning member-only early applicant roles (<10 applicants) for '{search_query}'...", expanded=True) as status:
            auth_scraper = AuthenticatedLinkedInScraper()
            jobs = asyncio.run(auth_scraper.search_early_bird_jobs(
                keywords=search_query,
                location=search_loc,
                easy_apply_only=True,
                under_10_applicants=True,
                is_remote="remote" in search_loc.lower(),
                limit=15
            ))
            st.write(f"Discovered {len(jobs)} early-bird jobs. Scoring with ATS engine...")
            resume_text = st.session_state.resume_text or f"{profile.name} {profile.headline} {', '.join(profile.all_skills)}"
            for j in jobs:
                res = score_job_with_gemini(
                    resume_text=resume_text,
                    job_title=j["title"],
                    company=j["company"],
                    job_description=j.get("description", ""),
                    candidate_skills=profile.all_skills
                )
                j["match_score"] = res["match_score"]
                j["matched_keywords"] = res["matched_keywords"]
                j["missing_keywords"] = res["missing_keywords"]
                db.upsert_job(j)
            export_tracker_xlsx("data/Job_Hunt_Tracker.xlsx", db)
            status.update(label=f"✅ Ingested {len(jobs)} early-bird jobs with ATS fit scores!", state="complete")
            st.rerun()

    if trigger_search and search_query:
        with st.status(f"Searching for '{search_query}' across {len(platforms_selected)} platforms...", expanded=True) as status:
            scraper = JobScraper()
            jobs = scraper.scrape(
                search_term=search_query,
                location=search_loc,
                results_wanted=15,
                platforms=platforms_selected,
                is_remote="remote" in search_loc.lower()
            )

            st.write(f"Scraped {len(jobs)} jobs. Scoring with ATS engine...")
            resume_text = st.session_state.resume_text or f"{profile.name} {profile.headline} {', '.join(profile.all_skills)}"

            scored_count = 0
            for j in jobs:
                res = score_job_with_gemini(
                    resume_text=resume_text,
                    job_title=j["title"],
                    company=j["company"],
                    job_description=j.get("description", ""),
                    candidate_skills=profile.all_skills
                )
                j["match_score"] = res["match_score"]
                j["matched_keywords"] = res["matched_keywords"]
                j["missing_keywords"] = res["missing_keywords"]
                j["status"] = "shortlisted" if j["match_score"] >= 65.0 else "new"
                db.upsert_job(j)
                scored_count += 1

            status.update(label=f"✅ Discovered & scored {scored_count} opportunities!", state="complete")
            export_tracker_xlsx("data/Job_Hunt_Tracker.xlsx", db)
            st.rerun()

    st.divider()

    # Filters and Job Cards
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        min_score_filter = st.slider("Minimum Match Score (%)", min_value=0, max_value=100, value=50, step=5)
    with col_f2:
        status_filter = st.selectbox("Status Filter", ["All", "new", "shortlisted", "applied"])
    with col_f3:
        st.caption("Live Filtered Results")

    filter_status_val = None if status_filter == "All" else status_filter
    displayed_jobs = db.get_all_jobs(min_score=float(min_score_filter), status=filter_status_val)

    if not displayed_jobs:
        st.info("No jobs found matching the selected filters. Click 'Search Jobs' to find fresh opportunities.")
    else:
        st.markdown(f"**Found {len(displayed_jobs)} matching opportunities:**")
        for j in displayed_jobs:
            score = j.get("match_score", 0.0)
            score_badge = f'<span class="badge-score-high">🟢 {score:.0f}% Match</span>' if score >= 70 else (
                f'<span class="badge-score-med">🟡 {score:.0f}% Match</span>' if score >= 50 else f'<span class="badge-platform">⚪ {score:.0f}% Match</span>'
            )
            platform_badge = f'<span class="badge-platform">{j.get("source", "web").upper()}</span>'

            with st.expander(f"{j['title']} @ {j['company']} — {j.get('location', 'Remote')} ({score:.0f}%)", expanded=False):
                col_c1, col_c2 = st.columns([3, 1])
                with col_c1:
                    st.markdown(f"{score_badge} &nbsp; {platform_badge} &nbsp; **Status:** `{j.get('status', 'new').upper()}`", unsafe_allow_html=True)
                    st.markdown(f"**Company:** {j['company']} | **Location:** {j.get('location', 'Remote')}")
                    if j.get("job_url"):
                        st.markdown(f"🔗 [Open Original Posting]({j['job_url']})")

                    matched_kws = j.get("matched_keywords", [])
                    if matched_kws:
                        st.markdown("**Matched Skills:** " + " ".join([f"`{k}`" for k in matched_kws[:8]]))

                    missing_kws = j.get("missing_keywords", [])
                    if missing_kws:
                        st.markdown("**Missing Skills / Gaps:** " + " ".join([f"`{k}`" for k in missing_kws[:6]]))

                    desc = j.get("description", "")
                    if desc:
                        with st.expander("View Job Description"):
                            st.write(desc[:1500] + ("..." if len(desc) > 1500 else ""))

                with col_c2:
                    if st.button("🚀 Auto-Apply", key=f"btn_apply_{j['id']}", use_container_width=True, type="primary"):
                        st.session_state["target_apply_job"] = j
                        st.success(f"Job queued for Auto-Apply. Switch to the 'Auto-Apply Center' tab!")


# =============================================================================
# TAB 2: AUTO-APPLY CENTER
# =============================================================================
with tab_apply:
    st.subheader("Playwright Intelligent Auto-Apply Engine")
    st.caption("Autonomously handles LinkedIn Easy Apply, Greenhouse, Lever, Ashby, and generic ATS application forms.")

    # -------------------------------------------------------------------------
    # LinkedIn Session Authentication Status Card
    # -------------------------------------------------------------------------
    is_li_auth = BrowserManager.is_linkedin_authenticated()
    with st.container():
        col_li_stat, col_li_btn = st.columns([2.2, 1.8])
        with col_li_stat:
            if is_li_auth:
                st.markdown("🟢 **LinkedIn Authentication:** `CONNECTED & PERSISTED` &nbsp;*(Active session ready for Easy Apply)*")
            else:
                st.markdown("🟡 **LinkedIn Authentication:** `NOT CONNECTED` &nbsp;*(Sign-in required for automated Easy Apply)*")
        with col_li_btn:
            col_b1, col_b2 = st.columns([1.2, 0.8] if is_li_auth else [1, 0.01])
            with col_b1:
                btn_label = "🔄 Refresh Session" if is_li_auth else "🔑 1-Click Log In to LinkedIn"
                if st.button(btn_label, use_container_width=True, type="primary" if not is_li_auth else "secondary"):
                    with st.status("🌐 Launching interactive browser for LinkedIn login...", expanded=True) as login_status:
                        st.write("A browser window is opening. Please complete your login and any 2FA/CAPTCHA challenges.")
                        res = asyncio.run(interactive_linkedin_login())
                        if res["success"]:
                            login_status.update(label="✅ LinkedIn Session Successfully Saved!", state="complete")
                            st.success(res["message"])
                            st.rerun()
                        else:
                            login_status.update(label="❌ Login Timed Out or Failed", state="error")
                            st.error(res["message"])
            with col_b2:
                if is_li_auth:
                    if st.button("❌ Disconnect", use_container_width=True):
                        BrowserManager.clear_linkedin_session()
                        st.success("Cleared saved LinkedIn session.")
                        st.rerun()

    st.divider()

    shortlisted_jobs = db.get_all_jobs(min_score=50.0)

    if not shortlisted_jobs:
        st.warning("No shortlisted jobs in database yet. Search jobs in Tab 1 first.")
    else:
        col_a1, col_a2 = st.columns([2, 1])
        with col_a1:
            job_options = {f"{j['title']} @ {j['company']} ({j.get('match_score', 0):.0f}%) — {j.get('source','').upper()}": j['id'] for j in shortlisted_jobs}
            selected_label = st.selectbox("Select Target Job to Apply", list(job_options.keys()))
            selected_job_id = job_options[selected_label]
            target_job = next(j for j in shortlisted_jobs if j["id"] == selected_job_id)

        with col_a2:
            st.markdown(f"**Detected ATS:** `{detect_platform(target_job.get('job_url', '')).upper()}`")
            st.markdown(f"**Mode:** `{'DRY RUN (Safe)' if dry_run_mode else 'AUTONOMOUS SUBMIT'}`")
            apply_now_btn = st.button("⚡ Execute Application", use_container_width=True, type="primary")

        st.divider()

        # Job details preview
        col_d1, col_d2 = st.columns([2, 1])
        with col_d1:
            st.markdown(f"### {target_job['title']}")
            st.markdown(f"**Company:** {target_job['company']} &nbsp;|&nbsp; **Location:** {target_job.get('location', 'Remote')}")
            st.markdown(f"**URL:** [Apply Page Link]({target_job.get('job_url', '#')})")

        with col_d2:
            st.markdown("#### Candidate Credentials")
            st.write(f"👤 **Name:** {profile.name}")
            st.write(f"📧 **Email:** {profile.contact.email}")
            st.write(f"📱 **Phone:** {profile.contact.phone}")
            st.write(f"🔗 **LinkedIn:** {profile.contact.linkedin_url}")

        # Prepare resume PDF path
        pdf_path = "data/resumes/candidate_resume.pdf"
        if not os.path.exists(pdf_path):
            pdf_path = "data/resumes/Candidate_Resume.pdf"
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        if not os.path.exists(pdf_path):
            resume_content = st.session_state.resume_text or f"{profile.name}\n{profile.headline}\n{profile.experience}"
            generate_resume_pdf(resume_content, pdf_path, candidate_name=profile.name, target_role=target_job["title"], company_name=target_job["company"])

        if apply_now_btn:
            with st.status(f"Automating application for {target_job['title']} @ {target_job['company']}...", expanded=True) as status:
                apply_engine = ApplyEngine(profile=profile, headless=headless_mode, dry_run=dry_run_mode)
                st.write(f"🌐 Launching Playwright browser in {'dry-run' if dry_run_mode else 'live'} mode...")
                apply_res = asyncio.run(apply_engine.apply_to_job(
                    job_url=target_job["job_url"],
                    resume_pdf_path=pdf_path,
                    dry_run=dry_run_mode
                ))

                st.session_state[f"job_apply_res_{target_job['id']}"] = apply_res

                # Record in database
                app_status = "submitted" if apply_res.get("status") == "submitted" else "prefilled"
                db.record_application(
                    job_id=target_job["id"],
                    company=target_job["company"],
                    title=target_job["title"],
                    applied_to=target_job["job_url"],
                    apply_method=apply_res.get("platform", "web"),
                    status=app_status,
                    screenshot_path=apply_res.get("screenshot", ""),
                    notes=apply_res.get("message", "")
                )
                export_tracker_xlsx("data/Job_Hunt_Tracker.xlsx", db)

                if apply_res.get("success"):
                    status.update(label="✅ Application workflow completed!", state="complete")
                else:
                    status.update(label="⚠️ Application encountered an issue", state="error")

        # Persistent Application Result & Action Card
        active_res = st.session_state.get(f"job_apply_res_{target_job['id']}")
        if active_res:
            st.divider()
            if active_res.get("success"):
                if active_res.get("status") == "submitted":
                    st.success(f"🎉 **Application Submitted Live!** {active_res.get('message')}")
                    if active_res.get("screenshot") and os.path.exists(active_res["screenshot"]):
                        st.image(active_res["screenshot"], caption="Submission Confirmation Screenshot", use_container_width=True)
                elif active_res.get("status") == "dry_run_completed":
                    st.success(f"📋 **Form Prefilled (Dry-Run Mode):** {active_res.get('message')}")
                    if active_res.get("screenshot") and os.path.exists(active_res["screenshot"]):
                        st.image(active_res["screenshot"], caption="Prefill Verification Screenshot", use_container_width=True)

                    st.info("💡 **Dry Run Verified:** All form fields, phone, resume, and screening questions have been validated above.")
                    col_sub1, col_sub2 = st.columns([1, 1])
                    with col_sub1:
                        if st.button("🚀 Confirm & Submit Application Now (Live)", key=f"btn_live_submit_{target_job['id']}", type="primary", use_container_width=True):
                            with st.status(f"Submitting live application to {target_job['company']}...", expanded=True) as live_status:
                                live_engine = ApplyEngine(profile=profile, headless=headless_mode, dry_run=False)
                                st.write("🌐 Opening browser in live submission mode...")
                                live_res = asyncio.run(live_engine.apply_to_job(
                                    job_url=target_job["job_url"],
                                    resume_pdf_path=pdf_path,
                                    dry_run=False
                                ))
                                st.session_state[f"job_apply_res_{target_job['id']}"] = live_res

                                if live_res.get("success") and live_res.get("status") == "submitted":
                                    live_status.update(label="🎉 Application submitted successfully!", state="complete")
                                    db.record_application(
                                        job_id=target_job["id"],
                                        company=target_job["company"],
                                        title=target_job["title"],
                                        applied_to=target_job["job_url"],
                                        apply_method=live_res.get("platform", "web"),
                                        status="submitted",
                                        screenshot_path=live_res.get("screenshot", ""),
                                        notes=live_res.get("message", "")
                                    )
                                    export_tracker_xlsx("data/Job_Hunt_Tracker.xlsx", db)
                                    st.rerun()
                                else:
                                    live_status.update(label="⚠️ Live submission response", state="error")
                                    st.error(f"**Error:** {live_res.get('message')}")
                                    st.rerun()
                    with col_sub2:
                        if st.button("🔄 Reset / Clear Prefill", key=f"btn_reset_{target_job['id']}", use_container_width=True):
                            st.session_state.pop(f"job_apply_res_{target_job['id']}", None)
                            st.rerun()
                else:
                    st.info(f"**Status:** {active_res.get('message')}")
                    if active_res.get("screenshot") and os.path.exists(active_res["screenshot"]):
                        st.image(active_res["screenshot"], caption="Stepper Progress Screenshot", use_container_width=True)
            else:
                st.error(f"**Error:** {active_res.get('message')}")
                if active_res.get("screenshot") and os.path.exists(active_res["screenshot"]):
                    st.image(active_res["screenshot"], caption="Error State Screenshot", use_container_width=True)


# =============================================================================
# TAB 3: LINKEDIN HIRING RADAR
# =============================================================================
with tab_posts:
    st.subheader("LinkedIn Hiring Post Scanner & Direct Recruiter Outreach")
    st.caption("Scans active LinkedIn posts for hiring announcements, extracts recruiter emails, and drafts cold outreach.")

    col_p1, col_p2 = st.columns([3, 1])
    with col_p1:
        post_scan_role = st.text_input("Role to Monitor", value=profile.primary_role, key="post_scan_role")
    with col_p2:
        st.write("")
        st.write("")
        scan_posts_btn = st.button("📡 Scan LinkedIn Posts", use_container_width=True, type="primary")

    if scan_posts_btn:
        with st.spinner("Scanning LinkedIn discussions and public posts for hiring calls..."):
            post_scanner = LinkedInPostScanner()
            posts = post_scanner.scan_posts(target_role=post_scan_role, target_skills=profile.core_skills)
            for p in posts:
                db.insert_linkedin_post(p)
            export_tracker_xlsx("data/Job_Hunt_Tracker.xlsx", db)
            st.success(f"Found {len(posts)} new hiring leads from LinkedIn posts!")
            st.rerun()

    posts = db.get_all_linkedin_posts()
    if not posts:
        st.info("No hiring posts scanned yet. Click 'Scan LinkedIn Posts' to discover live recruiter postings.")
    else:
        st.markdown(f"**Discovered {len(posts)} Recruiter Hiring Posts:**")
        for p in posts:
            with st.container():
                st.markdown(f"""
                <div class="job-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0; color: #60a5fa;">{p.get('author', 'Hiring Manager')} &nbsp;<span style="font-size: 0.85rem; color: #94a3b8;">({p.get('company', 'Tech Team')})</span></h4>
                        <span class="badge-platform">{p.get('date_found', '')}</span>
                    </div>
                    <p style="color: #cbd5e1; margin-top: 8px; font-size: 0.95rem;">{p.get('snippet', '')}</p>
                </div>
                """, unsafe_allow_html=True)

                col_b1, col_b2 = st.columns([2, 1])
                with col_b1:
                    if p.get("email"):
                        st.markdown(f"📧 **Extracted Contact Email:** `{p['email']}`")
                    if p.get("post_url"):
                        st.markdown(f"🔗 [View LinkedIn Post]({p['post_url']})")

                with col_b2:
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        if p.get("email"):
                            with st.popover("✉️ Cold Email"):
                                draft = generate_cold_email_draft(
                                    candidate_name=profile.name,
                                    candidate_role=profile.primary_role,
                                    candidate_skills=profile.core_skills,
                                    company=p.get("company", "Your Team"),
                                    job_title=p.get("role", "Software Engineer"),
                                    recipient_name=p.get("author", "")
                                )
                                subj = st.text_input("Subject", value=draft["subject"], key=f"subj_{p['id']}")
                                body = st.text_area("Body", value=draft["body"], height=200, key=f"body_{p['id']}")
                                if st.button("Send Email", key=f"send_{p['id']}", type="primary"):
                                    st.info("Simulated email send. In live mode, connect your Gmail App Password in config/settings.yaml.")
                    with col_p2:
                        if p.get("post_url"):
                            with st.popover("💬 Post Comment"):
                                comment_draft = generate_tailored_post_comment(
                                    candidate_name=profile.name,
                                    candidate_headline=profile.headline,
                                    target_role=p.get("role", profile.primary_role),
                                    company=p.get("company", "Your Team"),
                                    core_skills=profile.core_skills
                                )
                                comm_val = st.text_area("Tailored Comment", value=comment_draft, height=120, key=f"comm_{p['id']}")
                                can_pub = BrowserManager.is_linkedin_authenticated()
                                if st.button("🚀 Publish", key=f"pub_{p['id']}", disabled=not can_pub, type="primary"):
                                    with st.status("Publishing comment via authenticated browser...", expanded=True) as pub_st:
                                        eng = PostEngager(db=db)
                                        pub_r = asyncio.run(eng.publish_comment(post_url=p["post_url"], comment_text=comm_val))
                                        if pub_r["success"]:
                                            pub_st.update(label="✅ Comment Published!", state="complete")
                                            st.success(pub_r["message"])
                                        else:
                                            pub_st.update(label="❌ Failed to publish", state="error")
                                            st.error(pub_r["message"])


# =============================================================================
# TAB 4: REFERRAL NETWORK
# =============================================================================
with tab_referrals:
    st.subheader("LinkedIn Referral Finder & Connection Note Generator")
    st.caption("Locate Engineering Managers, Leads, and Recruiters at target companies and generate tailored 300-char connection requests.")

    col_r1, col_r2, col_r3, col_r4 = st.columns([2.5, 2, 1.2, 1.2])
    with col_r1:
        target_company = st.text_input("Target Company Name", value="Stripe", placeholder="e.g. Stripe, Google, Datadog")
    with col_r2:
        target_ref_role = st.text_input("Role to Pitch", value=profile.primary_role, key="ref_role")
    with col_r3:
        st.write("")
        st.write("")
        find_refs_btn = st.button("🔍 Find Leaders", use_container_width=True, type="primary")
    with col_r4:
        st.write("")
        st.write("")
        find_alumni_btn = st.button("🎓 Find Alumni", use_container_width=True, help="Discovers alumni from your university (e.g. NIT Rourkela) at target company.")

    if find_alumni_btn and target_company:
        with st.spinner(f"Mapping college alumni at {target_company}..."):
            alumni_mapper = AlumniMapper(profile=profile, db=db)
            alumni = alumni_mapper.map_alumni_at_company(company=target_company, target_role=target_ref_role)
            st.success(f"Discovered {len(alumni)} university alumni at {target_company}!")
            st.rerun()

    if find_refs_btn and target_company:
        with st.spinner(f"Mapping key technical stakeholders at {target_company}..."):
            ref_finder = ReferralFinder()
            profiles = ref_finder.find_top_profiles(company=target_company, role=target_ref_role)
            for prof in profiles:
                pitch = ref_finder.generate_outreach_pitch(
                    contact_name=prof["name"],
                    company=target_company,
                    target_role=target_ref_role,
                    candidate_name=profile.name,
                    candidate_summary=f"{profile.headline} with skills in {', '.join(profile.core_skills[:3])}"
                )
                prof["connection_note"] = pitch["connection_note"]
                prof["referral_pitch"] = pitch["referral_message"]
                db.insert_referral_contact(prof)

            export_tracker_xlsx("data/Job_Hunt_Tracker.xlsx", db)
            st.success(f"Discovered {len(profiles)} key referral contacts at {target_company}!")
            st.rerun()

    contacts = db.get_all_referral_contacts()
    if not contacts:
        st.info("No referral contacts discovered yet. Enter a target company above to find recruiters and engineering managers.")
    else:
        st.markdown(f"**Saved Referral Contacts ({len(contacts)}):**")
        for c in contacts:
            with st.container():
                st.markdown(f"""
                <div class="job-card">
                    <div style="display: flex; justify-content: space-between;">
                        <h4 style="margin: 0; color: #818cf8;">{c.get('name', 'Contact')} &nbsp;<span style="font-size: 0.9rem; color: #94a3b8;">• {c.get('headline', '')}</span></h4>
                        <span class="badge-platform">{c.get('company', '')}</span>
                    </div>
                    <div style="margin-top: 10px;">
                        <a href="{c.get('linkedin_url', '#')}" target="_blank" style="color: #38bdf8; text-decoration: none;">🔗 Open LinkedIn Profile ↗</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_n1, col_n2 = st.columns([1, 1])
                with col_n1:
                    st.markdown("**Personalized 300-Char Connection Note:**")
                    st.code(c.get("connection_note", ""), language="text")
                with col_n2:
                    st.markdown("**Referral Request InMail / Message:**")
                    st.code(c.get("referral_pitch", ""), language="text")

                daily_sent = db.get_daily_connection_count()
                can_send = db.can_send_connection(max_daily=15) and BrowserManager.is_linkedin_authenticated()
                if st.button(f"🚀 Send Connection Request ({daily_sent}/15 sent today)", key=f"btn_send_conn_{c['id']}", disabled=not can_send, type="primary"):
                    with st.status(f"Sending personalized connection request to {c.get('name')}...", expanded=True) as conn_status:
                        cs = ConnectionSender(db=db)
                        conn_res = asyncio.run(cs.send_connection_request(
                            profile_url=c.get("linkedin_url", ""),
                            note=c.get("connection_note", ""),
                            name=c.get("name", "Contact"),
                            company=c.get("company", "")
                        ))
                        if conn_res["success"]:
                            conn_status.update(label=f"✅ {conn_res['message']}", state="complete")
                            st.success(conn_res["message"])
                            st.rerun()
                        else:
                            conn_status.update(label=f"❌ {conn_res['message']}", state="error")
                            st.error(conn_res["message"])


# =============================================================================
# TAB 5: RESUME & ATS AUDITOR
# =============================================================================
with tab_profile:
    st.subheader("Candidate Profile, Resume Upload & ATS Match Auditor")
    st.caption("Upload your PDF resume, parse skills, and test ATS match scores against any target Job Description.")

    col_u1, col_u2 = st.columns([1.5, 1])
    with col_u1:
        uploaded_resume = st.file_uploader("Upload Resume (PDF format)", type=["pdf"])
        if uploaded_resume:
            bytes_data = uploaded_resume.read()
            parsed_text = extract_text_from_pdf_bytes(bytes_data)
            st.session_state.resume_text = parsed_text
            # Save file to disk
            os.makedirs("data/resumes", exist_ok=True)
            with open("data/resumes/Candidate_Resume.pdf", "wb") as f:
                f.write(bytes_data)
            st.success(f"✅ Successfully ingested resume ({len(parsed_text)} characters extracted)!")

    with col_u2:
        st.markdown("#### Candidate Summary")
        st.write(f"**Name:** {profile.name}")
        st.write(f"**Headline:** {profile.headline}")
        st.write(f"**Email:** {profile.contact.email}")
        st.write(f"**Phone:** {profile.contact.phone}")
        st.write(f"**Core Skills:** {', '.join(profile.core_skills[:6])}")

    st.divider()

    # Interactive ATS Keyword Match Simulator
    st.subheader("🎯 Live ATS Keyword Match Simulator")
    st.caption("Paste any target Job Description below to audit keyword alignment and identify missing skills.")

    sample_jd = st.text_area(
        "Target Job Description",
        height=180,
        placeholder="Paste full job description text here..."
    )

    if st.button("⚡ Audit ATS Score", type="primary"):
        if not sample_jd:
            st.error("Please paste a job description first.")
        else:
            resume_content = st.session_state.resume_text or f"{profile.name} {profile.headline} {', '.join(profile.all_skills)}"
            with st.spinner("Analyzing keyword density and semantic fit..."):
                audit_res = score_job_with_gemini(
                    resume_text=resume_content,
                    job_title=profile.primary_role,
                    company="Target Employer",
                    job_description=sample_jd,
                    candidate_skills=profile.all_skills
                )

                score = audit_res["match_score"]
                col_s1, col_s2, col_s3 = st.columns([1, 1.5, 1.5])
                with col_s1:
                    st.metric("Overall ATS Score", f"{score:.0f}%")
                with col_s2:
                    st.markdown("**Matched Keywords:**")
                    st.write(", ".join([f"`{k}`" for k in audit_res.get("matched_keywords", [])]) or "None detected")
                with col_s3:
                    st.markdown("**Missing / High-Priority Gaps:**")
                    st.write(", ".join([f"`{k}`" for k in audit_res.get("missing_keywords", [])]) or "None")

                if audit_res.get("tailored_pitch"):
                    st.info(f"💡 **Recommended Pitch:** {audit_res['tailored_pitch']}")


# =============================================================================
# TAB 6: TRACKER & EXCEL EXPORTER
# =============================================================================
with tab_excel:
    st.subheader("Database Master Tracker & Excel (.xlsx) Synchronization")
    st.caption("View unified relational tables and download the styled 5-sheet master spreadsheet.")

    # KPI summary cards
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Total Jobs", metrics["total_jobs"])
    kpi2.metric("Shortlisted", metrics["shortlisted_jobs"])
    kpi3.metric("Applied", metrics["applied_jobs"])
    kpi4.metric("LinkedIn Leads", metrics["linkedin_leads"])
    kpi5.metric("Referrals", metrics["referral_contacts"])

    st.divider()

    # Actions: Excel Download & LinkedIn Status Sync
    col_t1, col_t2 = st.columns([1.5, 1])
    with col_t1:
        excel_path = "data/Job_Hunt_Tracker.xlsx"
        export_tracker_xlsx(excel_path, db)
        with open(excel_path, "rb") as f:
            st.download_button(
                label="📥 Download Master Spreadsheet (Job_Hunt_Tracker.xlsx)",
                data=f.read(),
                file_name="Job_Hunt_Tracker.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
    with col_t2:
        is_li_auth = BrowserManager.is_linkedin_authenticated()
        if st.button("🔄 Sync LinkedIn Recruiter Status", disabled=not is_li_auth, use_container_width=True, help="Scrapes LinkedIn applied tracker for 'Viewed' and 'Downloaded' signals."):
            with st.status("Syncing applied jobs history and recruiter views...", expanded=True) as sync_status:
                syncer = LinkedInStatusSync(db=db)
                sync_res = asyncio.run(syncer.sync_applications())
                if sync_res["success"]:
                    sync_status.update(label=f"✅ {sync_res['message']}", state="complete")
                    st.success(sync_res["message"])
                    st.rerun()
                else:
                    sync_status.update(label=f"❌ {sync_res['message']}", state="error")
                    st.error(sync_res["message"])

    st.write("")
    table_view = st.radio("Select View", ["All Jobs", "Applications Log", "LinkedIn Post Leads", "Referrals Network"], horizontal=True)

    if table_view == "All Jobs":
        all_j = db.get_all_jobs()
        if all_j:
            df = pd.DataFrame(all_j)[["id", "title", "company", "location", "source", "match_score", "status", "date_posted", "job_url"]]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No jobs recorded yet.")
    elif table_view == "Applications Log":
        all_a = db.get_all_applications()
        if all_a:
            st.dataframe(pd.DataFrame(all_a), use_container_width=True)
        else:
            st.info("No applications submitted yet.")
    elif table_view == "LinkedIn Post Leads":
        all_p = db.get_all_linkedin_posts()
        if all_p:
            st.dataframe(pd.DataFrame(all_p), use_container_width=True)
        else:
            st.info("No LinkedIn post leads found yet.")
    elif table_view == "Referrals Network":
        all_r = db.get_all_referral_contacts()
        if all_r:
            st.dataframe(pd.DataFrame(all_r), use_container_width=True)
        else:
            st.info("No referral contacts mapped yet.")
