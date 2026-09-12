"""
core/profile.py — Candidate Profile Manager
Loads, validates, and provides structured access to the candidate's profile.
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class CandidateContact:
    phone: str = ""
    email: str = ""
    links: List[Dict[str, str]] = field(default_factory=list)

    @property
    def linkedin_url(self) -> str:
        for link in self.links:
            if "linkedin.com" in link.get("url", "").lower() or link.get("platform") == "linkedin":
                return link.get("url", "")
        return ""

    @property
    def github_url(self) -> str:
        for link in self.links:
            if "github.com" in link.get("url", "").lower() or link.get("platform") == "github":
                return link.get("url", "")
        return ""

    @property
    def portfolio_url(self) -> str:
        for link in self.links:
            if link.get("platform") in ("portfolio", "website", "other"):
                return link.get("url", "")
        return ""


@dataclass
class CandidateProfile:
    name: str = ""
    headline: str = ""
    location: str = ""
    contact: CandidateContact = field(default_factory=CandidateContact)
    education: List[Dict[str, Any]] = field(default_factory=list)
    experience: List[Dict[str, Any]] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    technical_skills: Dict[str, List[str]] = field(default_factory=dict)
    constraints_and_preferences: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def core_skills(self) -> List[str]:
        return self.technical_skills.get("core", [])

    @property
    def all_skills(self) -> List[str]:
        skills = []
        for category in ["core", "strong_supporting", "supporting", "tools"]:
            skills.extend(self.technical_skills.get(category, []))
        return list(dict.fromkeys(skills))

    @property
    def target_roles(self) -> List[str]:
        return self.constraints_and_preferences.get("target_roles", [])

    @property
    def acceptable_locations(self) -> List[str]:
        return self.constraints_and_preferences.get("acceptable_locations", [])

    @property
    def primary_role(self) -> str:
        roles = self.target_roles
        return roles[0] if roles else "Software Engineer"


def load_candidate_profile(config_path: str = "config/candidate_profile.yaml") -> CandidateProfile:
    """Load candidate profile from YAML file with fallback to defaults."""
    if not os.path.exists(config_path):
        # Return sensible fallback if file doesn't exist yet
        return CandidateProfile(
            name="Candidate",
            headline="Software Professional",
            location="Remote",
            constraints_and_preferences={"target_roles": ["Software Engineer"]}
        )

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    cand_data = data.get("candidate", {})
    contact_data = cand_data.get("contact", {})
    contact = CandidateContact(
        phone=contact_data.get("phone", ""),
        email=contact_data.get("email", ""),
        links=contact_data.get("links", [])
    )

    return CandidateProfile(
        name=cand_data.get("name", ""),
        headline=cand_data.get("headline", ""),
        location=cand_data.get("location", ""),
        contact=contact,
        education=data.get("education", []),
        experience=data.get("experience", []),
        projects=data.get("projects", []),
        technical_skills=data.get("technical_skills", {}),
        constraints_and_preferences=data.get("constraints_and_preferences", {}),
        raw_data=data
    )


def save_candidate_profile(profile: CandidateProfile, config_path: str = "config/candidate_profile.yaml"):
    """Persist candidate profile to YAML file."""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    payload = {
        "candidate": {
            "name": profile.name,
            "headline": profile.headline,
            "location": profile.location,
            "contact": {
                "phone": profile.contact.phone,
                "email": profile.contact.email,
                "links": profile.contact.links
            }
        },
        "education": profile.education,
        "experience": profile.experience,
        "projects": profile.projects,
        "technical_skills": profile.technical_skills,
        "constraints_and_preferences": profile.constraints_and_preferences
    }
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False)
