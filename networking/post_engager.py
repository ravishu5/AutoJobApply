"""
networking/post_engager.py — LinkedIn Hiring Post Comment & Engagement Assistant
Synthesizes professional, high-converting comments for hiring posts and provides
1-click automated comment publishing via authenticated Playwright session.
"""

import os
import asyncio
import random
from typing import Dict, Any, Optional
from automation.browser_manager import BrowserManager, DEFAULT_LINKEDIN_SESSION_PATH
from core.profile import CandidateProfile, load_candidate_profile
from storage.database import Database


def generate_tailored_post_comment(
    candidate_name: str,
    candidate_headline: str,
    target_role: str,
    company: str,
    core_skills: list
) -> str:
    """
    Synthesize a high-converting, professional comment for a hiring post.
    """
    first_skills = ", ".join(core_skills[:3]) if core_skills else "Python, LangGraph & RAG"
    comments = [
        f"Hi! I'm very interested in this {target_role} opportunity at {company}. My background centers on {candidate_headline.split('|')[0].strip()} with hands-on work in {first_skills}. I've sent over a connection request and would love to chat!",
        f"Exciting opportunity! I specialize in {first_skills} and enterprise automation systems. Would love to connect and share how my background aligns with {company}'s goals.",
        f"Hi team, this role aligns directly with my engineering focus in {first_skills}. Sending a direct note with my portfolio details—looking forward to connecting!"
    ]
    return random.choice(comments)


class PostEngager:
    def __init__(self, db: Optional[Database] = None, session_path: str = DEFAULT_LINKEDIN_SESSION_PATH):
        self.db = db or Database()
        self.session_path = session_path

    async def publish_comment(
        self,
        post_url: str,
        comment_text: str,
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        Navigate to a public LinkedIn post and publish a comment using authenticated session.
        """
        if not post_url:
            return {"success": False, "status": "invalid_url", "message": "No post URL provided."}

        if not BrowserManager.is_linkedin_authenticated(self.session_path):
            return {
                "success": False,
                "status": "not_authenticated",
                "message": "LinkedIn session not active. Please authenticate first."
            }

        browser_mgr = BrowserManager(headless=headless, storage_state_path=self.session_path)
        try:
            page = await browser_mgr.new_page()
            await page.goto(post_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3.0)

            # Locate comment button to activate comment box if needed
            comment_trigger = await page.query_selector("button[aria-label*='Comment'], button:has-text('Comment')")
            if comment_trigger:
                await comment_trigger.click()
                await asyncio.sleep(1.5)

            # Find comment input editor (contenteditable div or textarea)
            editor = await page.query_selector(
                ".editor-content div[contenteditable='true'], "
                "div[role='textbox'], "
                ".comments-comment-box__editor, "
                "textarea[name='message']"
            )

            if not editor:
                return {
                    "success": False,
                    "status": "editor_not_found",
                    "message": "Could not locate comment editor on post (comments may be disabled or restricted)."
                }

            await editor.click()
            await asyncio.sleep(0.5)
            await editor.fill(comment_text)
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Submit comment button
            submit_btn = await page.query_selector(
                "button.comments-comment-box__submit-button, "
                "button[type='submit']:has-text('Post'), "
                "button:has-text('Post')"
            )

            if submit_btn:
                await submit_btn.click()
                await asyncio.sleep(2.5)

                return {
                    "success": True,
                    "status": "published",
                    "message": "Comment successfully published to LinkedIn hiring post!",
                    "comment_text": comment_text
                }

            return {
                "success": False,
                "status": "submit_not_found",
                "message": "Comment filled, but 'Post' button was not accessible."
            }

        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Failed to publish comment: {e}"
            }
        finally:
            await browser_mgr.close()
