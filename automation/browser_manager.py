"""
automation/browser_manager.py — Playwright Browser Lifecycle & Stealth Setup
Provides robust async browser management with realistic user-agent,
fingerprint masking, persistent LinkedIn session management, and graceful cleanup.
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any, Callable
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

DEFAULT_LINKEDIN_SESSION_PATH = "data/linkedin_session.json"


class BrowserManager:
    def __init__(
        self,
        headless: bool = True,
        slow_mo_ms: int = 50,
        storage_state_path: Optional[str] = DEFAULT_LINKEDIN_SESSION_PATH
    ):
        self.headless = headless
        self.slow_mo_ms = slow_mo_ms
        self.storage_state_path = storage_state_path
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def start(self) -> BrowserContext:
        """Start Playwright and create an anti-detection browser context."""
        if not self._playwright:
            self._playwright = await async_playwright().start()

        if not self._browser:
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo_ms,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage"
                ]
            )

        context_kwargs: Dict[str, Any] = {
            "user_agent": DEFAULT_USER_AGENT,
            "viewport": {"width": 1280, "height": 800},
            "locale": "en-US",
            "timezone_id": "America/New_York"
        }

        # Load persistent session if available and authenticated
        if self.storage_state_path and os.path.exists(self.storage_state_path):
            context_kwargs["storage_state"] = self.storage_state_path

        self._context = await self._browser.new_context(**context_kwargs)

        # Inject stealth scripts to avoid webdriver detection
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        return self._context

    async def new_page(self) -> Page:
        """Create and return a new page in the managed context."""
        if not self._context:
            await self.start()
        return await self._context.new_page()

    async def close(self):
        """Safely close context, browser, and playwright instance."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._context = None
            self._browser = None
            self._playwright = None

    @classmethod
    def is_linkedin_authenticated(cls, session_path: str = DEFAULT_LINKEDIN_SESSION_PATH) -> bool:
        """Check if a valid LinkedIn storage state file exists with the li_at session cookie."""
        if not os.path.exists(session_path):
            return False
        try:
            with open(session_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cookies = data.get("cookies", [])
            return any(c.get("name") == "li_at" and bool(c.get("value")) for c in cookies)
        except Exception:
            return False

    @classmethod
    def clear_linkedin_session(cls, session_path: str = DEFAULT_LINKEDIN_SESSION_PATH) -> bool:
        """Remove saved session file."""
        if os.path.exists(session_path):
            try:
                os.remove(session_path)
                return True
            except Exception:
                return False
        return False


async def interactive_linkedin_login(
    session_path: str = DEFAULT_LINKEDIN_SESSION_PATH,
    timeout_seconds: int = 180,
    on_progress: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    Launch a visible browser window for the user to log into LinkedIn.
    Safely detects login completion (via li_at cookie or feed URL),
    persists storage state to disk, and closes browser cleanly.
    """
    os.makedirs(os.path.dirname(session_path), exist_ok=True)
    pw = None
    browser = None
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=False,
            slow_mo=50,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ]
        )

        existing_state = session_path if os.path.exists(session_path) else None
        context_args: Dict[str, Any] = {
            "user_agent": DEFAULT_USER_AGENT,
            "viewport": {"width": 1280, "height": 850}
        }
        if existing_state:
            context_args["storage_state"] = existing_state

        context = await browser.new_context(**context_args)

        # Add anti-bot stealth
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = await context.new_page()
        if on_progress:
            on_progress("🌐 Opening LinkedIn login page in browser window...")
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        start_time = asyncio.get_event_loop().time()
        logged_in = False

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            try:
                cookies = await context.cookies()
                has_li_at = any(c.get("name") == "li_at" and bool(c.get("value")) for c in cookies)
                current_url = page.url.lower()

                if has_li_at or any(k in current_url for k in ["/feed", "/mynetwork", "/jobs", "/in/"]):
                    logged_in = True
                    if on_progress:
                        on_progress("🔐 Authentication detected! Finalizing session cookies...")
                    await asyncio.sleep(2.5) # Settle session tokens
                    break
            except Exception:
                pass

            await asyncio.sleep(1.0)

        if logged_in:
            await context.storage_state(path=session_path)
            return {
                "success": True,
                "status": "authenticated",
                "session_path": session_path,
                "message": f"LinkedIn session successfully authenticated and saved to '{session_path}'."
            }
        else:
            return {
                "success": False,
                "status": "timeout",
                "session_path": session_path,
                "message": f"Authentication timed out after {timeout_seconds}s. Please try again."
            }

    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "session_path": session_path,
            "message": f"Interactive login encountered an error: {e}"
        }
    finally:
        try:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()
        except Exception:
            pass
