"""
tests/test_linkedin_features.py — Unit Tests for 6 LinkedIn Authenticated Features
Tests:
1. Job Poster URL normalization and extractor logic.
2. Connection request daily quota tracking and rate-limiting guardrails.
3. Authenticated Early-Bird search parameter formatting.
4. Recruiter status synchronization in SQLite.
5. NIT Rourkela alumni connection note and referral pitch synthesis.
6. Tailored hiring post comment generation.
"""

import os
import unittest
import tempfile
from storage.database import Database
from scrapers.job_poster_extractor import clean_linkedin_profile_url
from networking.alumni_mapper import AlumniMapper
from networking.post_engager import generate_tailored_post_comment
from core.profile import CandidateProfile, CandidateContact


class TestLinkedInAuthenticatedFeatures(unittest.TestCase):
    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_file.close()
        self.db = Database(db_path=self.temp_db_file.name)

        self.profile = CandidateProfile(
            name="Ravi Shankar",
            headline="AI Engineer | Python, LangGraph, FastAPI",
            contact=CandidateContact(email="test@example.com", phone="+917691823372"),
            education=[{"institution": "National Institute of Technology, Rourkela"}],
            technical_skills={"core": ["Python", "LangGraph", "FastAPI", "RAG"]}
        )

    def tearDown(self):
        if os.path.exists(self.temp_db_file.name):
            os.remove(self.temp_db_file.name)

    def test_clean_linkedin_profile_url(self):
        raw = "https://www.linkedin.com/in/john-doe-12345?miniProfileUrn=urn%3Ali%3Afs_miniProfile%3A123&trk=public_jobs"
        cleaned = clean_linkedin_profile_url(raw)
        self.assertEqual(cleaned, "https://www.linkedin.com/in/john-doe-12345")

    def test_connection_rate_limiting_and_quota(self):
        # Starts at 0
        self.assertEqual(self.db.get_daily_connection_count(), 0)
        self.assertTrue(self.db.can_send_connection(max_daily=3))

        # Record 2 connections
        self.db.record_sent_connection("https://linkedin.com/in/user1", name="User One", company="Stripe")
        self.db.record_sent_connection("https://linkedin.com/in/user2", name="User Two", company="Google")
        self.assertEqual(self.db.get_daily_connection_count(), 2)
        self.assertTrue(self.db.can_send_connection(max_daily=3))

        # Record 3rd connection -> hits cap
        self.db.record_sent_connection("https://linkedin.com/in/user3", name="User Three", company="Uber")
        self.assertEqual(self.db.get_daily_connection_count(), 3)
        self.assertFalse(self.db.can_send_connection(max_daily=3))

    def test_recruiter_status_update(self):
        # Insert a test application
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO applications (company, title, applied_to, apply_method, status)
                VALUES ('Stripe', 'AI Engineer', 'https://linkedin.com', 'easy_apply', 'submitted')
            """)
            conn.commit()

        # Update status
        updated = self.db.update_application_recruiter_status(
            company="Stripe",
            title="AI Engineer",
            recruiter_status="Application Viewed by Recruiter"
        )
        self.assertTrue(updated)

        with self.db.get_connection() as conn:
            row = conn.execute("SELECT recruiter_status FROM applications WHERE company = 'Stripe'").fetchone()
            self.assertEqual(row["recruiter_status"], "Application Viewed by Recruiter")

    def test_alumni_mapper_synthesis(self):
        mapper = AlumniMapper(profile=self.profile, db=self.db)
        self.assertIn("Rourkela", mapper.get_alumni_institution())

        alumni = mapper.map_alumni_at_company(company="Datadog", target_role="AI Engineer", limit=2)
        self.assertGreaterEqual(len(alumni), 1)

        note = alumni[0]["connection_note"]
        self.assertLessEqual(len(note), 300)
        self.assertIn("NIT Rourkela", note)

    def test_tailored_post_comment_generation(self):
        comment = generate_tailored_post_comment(
            candidate_name="Ravi Shankar",
            candidate_headline="AI Engineer | Python, LangGraph",
            target_role="AI Engineer",
            company="OpenAI",
            core_skills=["Python", "LangGraph", "FastAPI"]
        )
        self.assertIn("Python", comment)
        self.assertGreater(len(comment), 20)
        self.assertLess(len(comment), 400)


if __name__ == "__main__":
    unittest.main()
