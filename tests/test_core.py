"""
tests/test_core.py — Unit Tests for Profile, Resume Parser, and ATS Scorer
"""

import unittest
from core.profile import CandidateProfile, CandidateContact, load_candidate_profile
from core.resume_parser import extract_contact_info
from core.scorer import calculate_ats_match, extract_keywords_from_text


class TestCoreSubsystem(unittest.TestCase):
    def test_candidate_profile_properties(self):
        contact = CandidateContact(
            phone="+1234567890",
            email="test@example.com",
            links=[{"platform": "linkedin", "url": "https://linkedin.com/in/testuser"}]
        )
        profile = CandidateProfile(
            name="Test User",
            contact=contact,
            technical_skills={"core": ["Python", "FastAPI"], "supporting": ["Docker"]},
            constraints_and_preferences={"target_roles": ["Software Engineer", "Backend Developer"]}
        )

        self.assertEqual(profile.name, "Test User")
        self.assertEqual(profile.contact.linkedin_url, "https://linkedin.com/in/testuser")
        self.assertIn("Python", profile.core_skills)
        self.assertEqual(profile.primary_role, "Software Engineer")

    def test_contact_extraction_from_resume_text(self):
        sample_text = """
        John Doe
        Email: john.doe@techmail.org
        Phone: (555) 123-4567
        LinkedIn: https://www.linkedin.com/in/johndoe
        GitHub: https://github.com/johndoe
        """
        extracted = extract_contact_info(sample_text)
        self.assertEqual(extracted["email"], "john.doe@techmail.org")
        self.assertEqual(extracted["linkedin"], "https://www.linkedin.com/in/johndoe")
        self.assertEqual(extracted["github"], "https://github.com/johndoe")

    def test_ats_keyword_scoring(self):
        resume_text = "Experienced Senior Python Engineer with skills in FastAPI, PostgreSQL, Docker, and AWS."
        jd_text = "We are seeking a Python Engineer with hands-on experience in FastAPI, Kubernetes, Docker, and AWS."

        res = calculate_ats_match(resume_text, jd_text, candidate_skills=["Python", "FastAPI", "Docker", "AWS"])

        self.assertGreater(res["match_score"], 60.0)
        self.assertIn("python", res["matched_keywords"])
        self.assertIn("docker", res["matched_keywords"])
        self.assertIn("kubernetes", res["missing_keywords"])


if __name__ == "__main__":
    unittest.main()
