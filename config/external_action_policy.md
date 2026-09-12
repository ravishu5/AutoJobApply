# External Action Policy & Autonomous Safety Boundaries

This policy governs the autonomous behavior of **AutoJobPilot** and the **Gemini Spark Agent**.

## 1. Core Principles
1. **Zero Hallucination / Zero Fabrication**: The agent must NEVER invent work experience, skills, metrics, degrees, or contact information not present in the candidate's verified profile or uploaded resume.
2. **Approved Outbound Boundaries**:
   - **Form Auto-fill**: Allowed automatically.
   - **Form Submission**: In `Autonomous Mode` (dry_run=False), applications with a match score >= threshold will submit and log proof (screenshot + confirmation URL). In `Dry-Run Mode`, forms will be prefilled and left on the review/submit step.
   - **Cold Email Outreach**: By default, drafted in the database and Excel tracker. If `send_email_automatically: true`, limited strictly to `daily_max_emails` (max 10/day) with valid MX records and legitimate recruiter contacts.
   - **LinkedIn DMs / Connection Requests**: Generated as ready-to-use 300-char notes; the user copies and sends them manually or through approved browser session.
3. **Data Integrity**:
   - Tracker rows and history in SQLite and Excel (`Job_Hunt_Tracker.xlsx`) are append-only or update-in-place with canonical job IDs.
   - No duplicate applications to the same job posting.
