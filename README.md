# ⚡ AutoJobPilot: Autonomous AI Job Hunt & Application Suite

**AutoJobPilot** is a state-of-the-art autonomous career intelligence and application automation agent designed for **Gemini Spark** and automated execution. It integrates multi-board job scraping, ATS keyword optimization, LinkedIn hiring post scanning, referral networking, Playwright form auto-filling, and formatted Excel tracking.

---

## 🌟 Key Features

1. **Multi-Platform Job Discovery (Powered by JobSpy)**:
   - Scrapes **LinkedIn, Indeed, Glassdoor, ZipRecruiter, and Google Jobs** concurrently without paid API keys.
   - Intelligent deduplication using canonical job hashing (`hash(company + title + location)`).
   - Extracts salary intervals, direct apply links, remote status, and contact emails.

2. **ATS Keyword Matching & Gemini Fit Scorer**:
   - Analyzes candidate resumes against target job descriptions.
   - Highlights **Matched Keywords**, **Missing Requirements**, and calculated match percentage (0–100%).
   - Generates tailored elevator pitches and interview positioning points.

3. **LinkedIn Hiring Radar & Direct Cold Emailer**:
   - Searches real-time public LinkedIn posts for *"we're hiring"*, *"join our team"*, and *"DM me"* calls.
   - Extracts hiring manager and recruiter email addresses directly from post content.
   - Automatically drafts and queues high-converting cold email outreach templates via SMTP.

4. **Referral Finder & LinkedIn Networking**:
   - Maps Engineering Managers, Tech Leads, and Technical Recruiters at target companies.
   - Synthesizes strict **≤ 300-character LinkedIn connection notes** tailored to your background.
   - Generates warm referral request messages ready to send upon connection.

5. **Playwright Intelligent Auto-Apply Engine**:
   - **LinkedIn Easy Apply**: Stepper automation navigating through contact details, resume uploads, and experience questionnaires.
   - **Greenhouse & Lever ATS**: Prefills name, contact info, LinkedIn URL, custom questions, and uploads resume PDF.
   - **Generic ATS & Ashby**: Smart DOM inspection matching labels to candidate profile fields.
   - **Dry-Run Safety Mode**: Fills every form and pauses before final submission, capturing screenshot evidence.

6. **Formatted Multi-Sheet Excel (.xlsx) Tracker**:
   - Continuously exports to `data/Job_Hunt_Tracker.xlsx` using `openpyxl`.
   - Formatted with styled header bars, status color codes, and automatic column widths.
   - **5 Dedicated Sheets**:
     1. `All Jobs`: Comprehensive list of discovered jobs with match scores and direct links.
     2. `Applications`: History of submitted/prefilled applications with notes and dates.
     3. `LinkedIn Post Leads`: Direct hiring manager post snippets and emails.
     4. `Referral Network`: Mapped company employees with custom connection notes.
     5. `Dashboard KPIs`: High-level recruitment metrics and conversion rates.

---

## 🚀 Quickstart

### 1. Installation
```bash
# Clone or navigate to the repository
cd AutoJobApply

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 2. Configure Candidate Profile
Edit `config/candidate_profile.yaml` to add your contact details, target roles, education, experience, and core skills.

---

## 🤖 Running with Gemini Spark (Zero Manual Work)

You can give this workspace directly to **Gemini Spark** or run it headless from the terminal:

### Full Autonomous Run
```bash
python spark_agent.py --run-all
```
*Discovers jobs → Scores with ATS → Scans LinkedIn hiring calls → Maps company referrals → Auto-applies via Playwright → Syncs to `Job_Hunt_Tracker.xlsx`.*

### Autonomous Run with Live Submission
```bash
python spark_agent.py --run-all --live
```

### Targeted Job Search
```bash
python spark_agent.py --search-only --role "Full Stack Engineer" --location "Remote"
```

### Scan LinkedIn Hiring Posts Only
```bash
python spark_agent.py --scan-posts --role "AI Engineer"
```

### Find Referral Contacts at a Target Company
```bash
python spark_agent.py --find-referrals "Stripe"
```

---

## 🖥️ Modern Web Dashboard

Launch the interactive UI:
```bash
streamlit run app.py
```

### Dashboard Tabs:
- 💼 **Job Discovery Hub**: Search multi-board, filter by score, inspect job descriptions.
- 🤖 **Auto-Apply Center**: 1-click Playwright execution with screenshot review.
- 📢 **LinkedIn Hiring Radar**: View real-time hiring posts and send recruiter cold emails.
- 🤝 **Referral Network**: View top contacts and copy custom 300-char connection notes.
- 🎯 **Resume & ATS Auditor**: Ingest PDF resume, parse skills, and audit match score against any JD.
- 📊 **Master Tracker & Excel**: Live relational view and 1-click download of `Job_Hunt_Tracker.xlsx`.

---

## 🔒 Safety & External Action Policy
- **Dry-Run by Default**: Forms are filled and verified without submitting unless `--live` or autonomous submit toggle is active.
- **No Hallucination Guarantee**: Answers to screening questions strictly adhere to facts evidenced in `candidate_profile.yaml`.
- **Zero API Lock-in**: Works out of the box with deterministic NLP heuristics; automatically upgrades to Gemini models when `GEMINI_API_KEY` is provided.
