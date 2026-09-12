"""
tests/test_automation.py — Unit Tests for ATS Detection, Canonical ID, and Screening Agent
"""

import unittest
from scrapers.job_scraper import generate_canonical_id
from automation.apply_engine import detect_platform
from automation.screening_agent import ScreeningAgent
from core.profile import CandidateProfile, CandidateContact


class TestAutomationSubsystem(unittest.TestCase):
    def test_canonical_id_determinism(self):
        id1 = generate_canonical_id("Google LLC", "Senior Software Engineer", "Mountain View, CA")
        id2 = generate_canonical_id("google llc", "senior software engineer", "Mountain View, CA")
        id3 = generate_canonical_id("Microsoft", "Senior Software Engineer", "Seattle, WA")

        self.assertEqual(id1, id2)
        self.assertNotEqual(id1, id3)

    def test_ats_platform_detection(self):
        self.assertEqual(detect_platform("https://boards.greenhouse.io/stripe/jobs/12345"), "greenhouse")
        self.assertEqual(detect_platform("https://jobs.lever.co/netflix/67890"), "lever")
        self.assertEqual(detect_platform("https://www.linkedin.com/jobs/view/12345678"), "linkedin_easy_apply")
        self.assertEqual(detect_platform("https://jobs.ashbyhq.com/scale/456"), "ashby")
        self.assertEqual(detect_platform("https://unknown-startup.com/careers/role-1"), "generic")

    def test_screening_agent_rule_fallback(self):
        profile = CandidateProfile(
            name="Alice Walker",
            technical_skills={"core": ["Python", "FastAPI"]},
            constraints_and_preferences={
                "experience_band": {"minimum_years": 5},
                "compensation_preference": "$160,000 / year"
            }
        )
        agent = ScreeningAgent(profile)

        # Work authorization
        self.assertEqual(agent.answer_question("Are you legally authorized to work in the US?"), "Yes")
        self.assertEqual(agent.answer_question("Will you now or in the future require visa sponsorship?"), "No")

        # Years of experience
        self.assertEqual(agent.answer_question("How many years of experience do you have with Python?"), "5")

        # Notice period
        self.assertIn("2 weeks", agent.answer_question("What is your expected notice period?"))

        # Salary expectations
        self.assertEqual(agent.answer_question("What are your salary expectations?"), "$160,000 / year")


if __name__ == "__main__":
    unittest.main()
