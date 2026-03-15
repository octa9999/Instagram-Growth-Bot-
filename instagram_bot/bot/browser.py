"""
Playwright browser lifecycle: launch, create context, ensure logged in.
"""
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import USE_DESKTOP_VIEW, TIKTOK_PROFILE_DIR
from bot.session import ensure_logged_in


async def _create_context(browser: Browser) -> BrowserContext:
    """
    Create a mobile-like context by default; desktop when USE_DESKTOP_VIEW is true.
    Shared between Instagram and TikTok launchers.
    """
    if USE_DESKTOP_VIEW:
        return await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
    return await browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        is_mobile=True,
        has_touch=True,
        device_scale_factor=3,
    )


async def create_browser(headless: bool = False) -> tuple[Browser, BrowserContext, Page]:
    """
    Launch Chromium, create a context and one page, and ensure Instagram session is valid.
    Returns (browser, context, page). Caller must close browser on exit.
    """
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.launch(headless=headless, channel="chrome")
    except Exception:
        browser = await playwright.chromium.launch(headless=headless)
    context = await _create_context(browser)
    page = await context.new_page()
    ok = await ensure_logged_in(context, page)
    if not ok:
        await browser.close()
        raise RuntimeError("Failed to log in to Instagram (check credentials or 2FA)")
    return browser, context, page


async def create_browser_no_login(headless: bool = False) -> tuple[Browser, BrowserContext, Page]:
    """
    Launch Chromium and create a context/page without performing any login.
    Used for TikTok mode (which does not reuse Instagram cookies).
    """
    playwright = await async_playwright().start()
    # Persistent context so TikTok cookies (manual login) are reused across runs
    try:
        context = await playwright.chromium.launch_persistent_context(
            str(TIKTOK_PROFILE_DIR),
            headless=headless,
            channel="chrome",
        )
    except Exception:
        context = await playwright.chromium.launch_persistent_context(
            str(TIKTOK_PROFILE_DIR),
            headless=headless,
        )
    browser = context.browser
    page = await context.new_page()
    # viewport for this persistent context
    try:
        if USE_DESKTOP_VIEW:
            await page.set_viewport_size({"width": 1280, "height": 720})
        else:
            await page.set_viewport_size({"width": 390, "height": 844})
    except Exception:
        # Some Playwright / browser combos may not support changing viewport; ignore.
        pass
    return browser, context, page


