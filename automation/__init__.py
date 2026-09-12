"""
automation package
"""
from automation.browser_manager import BrowserManager, interactive_linkedin_login
from automation.apply_engine import ApplyEngine, detect_platform
from automation.screening_agent import ScreeningAgent

__all__ = [
    "BrowserManager",
    "interactive_linkedin_login",
    "ApplyEngine",
    "detect_platform",
    "ScreeningAgent"
]
