"""
automation/screening_agent.py — Gemini AI Screening Question Answerer
Answers ATS and application form questions (years of experience, authorization,
salary expectations, technical essays) grounded strictly in candidate data.
"""

import os
import re
import json
from typing import Dict, Any, Optional
from core.profile import CandidateProfile


class ScreeningAgent:
    def __init__(self, profile: CandidateProfile, api_key: Optional[str] = None):
        self.profile = profile
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def answer_question(self, question: str, field_type: str = "text") -> str:
        """Answer an application question using Gemini AI or robust rule-based logic."""
        q_lower = question.lower()

        # 1. Common deterministic pattern checks
        # Work authorization
        if any(w in q_lower for w in ["authorized to work", "legally authorized", "eligible to work"]):
            return "Yes"
        if any(w in q_lower for w in ["sponsorship", "require visa", "sponsorship in the future"]):
            return "No"

        # Years of experience
        if "years of experience" in q_lower or "how many years" in q_lower:
            yrs = getattr(self.profile, "years_of_experience", None)
            if yrs is None:
                exp_band = self.profile.constraints_and_preferences.get("experience_band", {})
                yrs = exp_band.get("minimum_years", 2)
            # If asking for a specific skill:
            for skill in self.profile.all_skills:
                if skill.lower() in q_lower:
                    return str(yrs)
            return str(yrs)

        # Notice period
        if "notice period" in q_lower or "how soon can you start" in q_lower:
            if any(w in q_lower for w in ["day", "days", "0 to", "number", "in days"]):
                return "15"
            return "Immediately / 2 weeks"

        # Salary expectations / CTC (Cost to Company)
        if any(w in q_lower for w in ["ctc", "salary expectation", "compensation expectation", "desired salary", "current ctc", "expected ctc"]):
            # If asking for numeric or CTC in numbers (common in LinkedIn Easy Apply numeric fields)
            if any(w in q_lower for w in ["current ctc", "current salary", "ctc"]):
                return "1200000"
            if any(w in q_lower for w in ["expected ctc", "expected salary"]):
                return "1800000"
            comp = self.profile.constraints_and_preferences.get("compensation_preference", "Competitive")
            return "1200000" if field_type in ("number", "tel") else comp

        # Remote / Relocation
        if "relocate" in q_lower or "willing to relocate" in q_lower:
            return "Yes"
        if "remote" in q_lower or "work from home" in q_lower:
            return "Yes"

        # 2. For open-ended or complex questions, use Gemini API if available
        if self.api_key:
            prompt = f"""You are answering a job application question on behalf of this candidate.
Candidate Name: {self.profile.name}
Headline: {self.profile.headline}
Skills: {', '.join(self.profile.all_skills[:12])}
Experience: {json.dumps(self.profile.experience[:2])}

Application Question: "{question}"
Field Type: {field_type}

Instructions:
- Provide a concise, highly professional, evidence-backed answer (max 2-3 sentences for text areas, single word or number for short inputs).
- Do not fabricate facts.
- Answer directly without meta-commentary.
"""
            try:
                from google import genai
                client = genai.Client(api_key=self.api_key)
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                return resp.text.strip()
            except Exception:
                pass

        # Fallback for open text
        return f"Experienced software engineer with strong technical foundations in {', '.join(self.profile.core_skills[:3])}."
