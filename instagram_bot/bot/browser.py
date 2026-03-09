"""
Playwright browser lifecycle: launch, create context, ensure logged in.
"""
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import USE_DESKTOP_VIEW
from bot.session import ensure_logged_in


async def create_browser(headless: bool = False) -> tuple[Browser, BrowserContext, Page]:
    """
    Launch Chromium, create a context and one page. Ensure Instagram session is valid.
    Returns (browser, context, page). Caller must close browser on exit.
    """
    playwright = await async_playwright().start()
    # Use Chrome if installed (better video codec support); fallback to Chromium
    try:
        browser = await playwright.chromium.launch(headless=headless, channel="chrome")
    except Exception:
        browser = await playwright.chromium.launch(headless=headless)
    # Desktop viewport often fixes "trouble playing this video"; set USE_DESKTOP_VIEW=true in .env to try
    if USE_DESKTOP_VIEW:
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
    else:
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
        )
    page = await context.new_page()
    ok = await ensure_logged_in(context, page)
    if not ok:
        await browser.close()
        raise RuntimeError("Failed to log in to Instagram (check credentials or 2FA)")
    return browser, context, page
