"""
automation/browser_manager.py — Playwright Browser Lifecycle & Stealth Setup
Provides robust async browser management with realistic user-agent,
fingerprint masking, and graceful cleanup.
"""

import asyncio
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


class BrowserManager:
    def __init__(self, headless: bool = True, slow_mo_ms: int = 50):
        self.headless = headless
        self.slow_mo_ms = slow_mo_ms
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

        self._context = await self._browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York"
        )

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
