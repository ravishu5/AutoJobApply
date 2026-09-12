"""
core/scorer.py — ATS Keyword Matching and Semantic Fit Scorer
Calculates match score between candidate profile/resume and job descriptions,
identifying matched skills, missing keywords, and recommendations using Gemini or NLP.
"""

import os
import re
import json
from typing import Dict, Any, List, Set, Tuple, Optional


COMMON_TECH_SKILLS = {
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "golang", "rust",
    "ruby", "php", "swift", "kotlin", "scala", "react", "react.js", "next.js", "vue",
    "vue.js", "angular", "node", "node.js", "express", "fastapi", "django", "flask",
    "spring", "spring boot", "graphql", "rest", "restful", "api", "apis", "microservices",
    "sql", "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis", "elasticsearch",
    "dynamodb", "cassandra", "aws", "azure", "gcp", "docker", "kubernetes", "k8s", "terraform",
    "ansible", "ci/cd", "github actions", "jenkins", "git", "linux", "unix", "bash", "shell",
    "machine learning", "deep learning", "nlp", "llm", "llms", "langchain", "llamaindex",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy", "playwright", "selenium",
    "puppeteer", "html", "css", "tailwind", "styled-components", "distributed systems",
    "system design", "agile", "scrum", "jira", "tdd", "unit testing", "integration testing"
}


def extract_keywords_from_text(text: str) -> Set[str]:
    """Extract known technical and domain keywords from text."""
    lower_text = text.lower()
    found = set()
    # Normalize punctuation
    normalized = re.sub(r"[^\w\s\.\+#/-]", " ", lower_text)

    for skill in COMMON_TECH_SKILLS:
        pattern = r"(?:\b|_)" + re.escape(skill) + r"(?:\b|_)"
        if re.search(pattern, normalized):
            found.add(skill)

    # Also detect word n-grams that look like requirements (e.g. 5+ years, bachelor's)
    if "bachelor" in lower_text or "b.tech" in lower_text or "bs" in lower_text:
        found.add("bachelor degree")
    if "master" in lower_text or "m.tech" in lower_text or "ms" in lower_text:
        found.add("master degree")

    return found


def calculate_ats_match(resume_text: str, job_description: str, candidate_skills: List[str] = None) -> Dict[str, Any]:
    """
    Deterministic ATS keyword matching algorithm.
    Compares resume text and candidate skills with JD requirements.
    """
    if not job_description or not resume_text:
        return {
            "match_score": 50.0,
            "matched_keywords": [],
            "missing_keywords": [],
            "explanation": "Insufficient job description or resume text provided."
        }

    jd_keywords = extract_keywords_from_text(job_description)
    resume_keywords = extract_keywords_from_text(resume_text)

    if candidate_skills:
        for s in candidate_skills:
            if s.lower() in COMMON_TECH_SKILLS or s.lower() in job_description.lower():
                resume_keywords.add(s.lower())

    if not jd_keywords:
        # If JD has few technical words, fallback to general word overlap
        jd_words = set(re.findall(r"\b[a-z]{4,}\b", job_description.lower()))
        resume_words = set(re.findall(r"\b[a-z]{4,}\b", resume_text.lower()))
        overlap = jd_words.intersection(resume_words)
        score = min(100.0, max(20.0, (len(overlap) / max(1, len(jd_words))) * 120))
        return {
            "match_score": round(score, 1),
            "matched_keywords": list(overlap)[:10],
            "missing_keywords": list(jd_words - resume_words)[:10],
            "explanation": f"Basic text similarity score based on {len(overlap)} shared terms."
        }

    matched = sorted(list(jd_keywords.intersection(resume_keywords)))
    missing = sorted(list(jd_keywords - resume_keywords))

    score_ratio = len(matched) / max(1, len(jd_keywords))
    # Calibrate curve: 70%+ match is an excellent candidate
    calculated_score = min(98.0, max(15.0, score_ratio * 105.0))

    return {
        "match_score": round(calculated_score, 1),
        "matched_keywords": matched,
        "missing_keywords": missing,
        "explanation": f"Matched {len(matched)} of {len(jd_keywords)} detected key skills ({round(score_ratio*100)}%)."
    }


def score_job_with_gemini(
    resume_text: str,
    job_title: str,
    company: str,
    job_description: str,
    candidate_skills: List[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Score a job using Google Gemini API if key is present; otherwise falls back to deterministic ATS match.
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")

    # If no Gemini API key, use the robust deterministic matcher
    if not api_key:
        ats = calculate_ats_match(resume_text, job_description, candidate_skills)
        return {
            "match_score": ats["match_score"],
            "matched_keywords": ats["matched_keywords"],
            "missing_keywords": ats["missing_keywords"],
            "summary": f"ATS Match for {job_title} at {company}: {ats['explanation']}",
            "tailored_pitch": f"Experienced software professional with demonstrated hands-on mastery in {', '.join(ats['matched_keywords'][:4])}."
        }

    prompt = f"""You are an expert technical recruiter and ATS evaluation engine.
Evaluate how well this candidate matches the following job posting.

Candidate Resume Excerpt:
{resume_text[:2500]}

Candidate Skills: {', '.join(candidate_skills or [])}

Target Job Title: {job_title}
Target Company: {company}
Job Description:
{job_description[:3000]}

Return STRICTLY a JSON object with the following schema:
{{
  "match_score": <number between 0 and 100 representing fit percentage>,
  "matched_keywords": [<list of strings of skills matched>],
  "missing_keywords": [<list of strings of required skills the candidate lacks>],
  "summary": "<2-sentence objective assessment of the match>",
  "tailored_pitch": "<2-3 sentence elevator pitch highlighting candidate's top relevant achievements for this role>"
}}
Do NOT wrap in markdown formatting, return pure JSON.
"""

    try:
        # Try google.genai or google.generativeai
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            raw_text = response.text
        except Exception:
            import google.generativeai as gai
            gai.configure(api_key=api_key)
            model = gai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            raw_text = response.text

        clean_json = re.sub(r"^```json\s*", "", raw_text.strip())
        clean_json = re.sub(r"^```\s*", "", clean_json)
        clean_json = re.sub(r"\s*```$", "", clean_json).strip()
        data = json.loads(clean_json)
        return {
            "match_score": float(data.get("match_score", 50.0)),
            "matched_keywords": data.get("matched_keywords", []),
            "missing_keywords": data.get("missing_keywords", []),
            "summary": data.get("summary", ""),
            "tailored_pitch": data.get("tailored_pitch", "")
        }
    except Exception as e:
        # Graceful fallback to deterministic ATS
        ats = calculate_ats_match(resume_text, job_description, candidate_skills)
        ats["summary"] = f"Deterministic ATS fallback (LLM note: {str(e)[:50]}...)"
        ats["tailored_pitch"] = f"Candidate with strong background in {', '.join(ats['matched_keywords'][:4])}."
        return ats
