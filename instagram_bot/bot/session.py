"""
Session management: load/save cookies, login. Reuse cookies to avoid logging in every run.
"""
import asyncio
import json
from pathlib import Path

from playwright.async_api import BrowserContext, Page

from config import COOKIE_FILE, INSTAGRAM_USER, INSTAGRAM_PASS
from utils.logger import logger

INSTAGRAM_LOGIN_URL = "https://www.instagram.com/accounts/login/"
INSTAGRAM_HOME = "https://www.instagram.com/"


async def load_cookies(context: BrowserContext) -> bool:
    """Load cookies from file into context. Return True if file existed and was loaded."""
    if not COOKIE_FILE.exists():
        return False
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        return True
    except Exception as e:
        logger.warning("Failed to load cookies: %s", e)
        return False


async def save_cookies(context: BrowserContext) -> None:
    """Save context cookies to file after successful login."""
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        cookies = await context.cookies()
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)
        logger.info("Session cookies saved")
    except Exception as e:
        logger.warning("Failed to save cookies: %s", e)


async def login(context: BrowserContext, page: Page, username: str, password: str) -> bool:
    """
    Navigate to Instagram login, fill credentials, submit.
    On success save cookies and return True. On 2FA/challenge we return False (document in comments).
    """
    if not username or not password:
        logger.error("INSTAGRAM_USER and INSTAGRAM_PASS must be set in .env")
        return False
    try:
        await page.goto(INSTAGRAM_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_load_state("load", timeout=20000)
        await asyncio.sleep(1.5)
        # Username: try multiple selectors (Instagram DOM varies)
        username_sel = 'input[name="username"], input[autocomplete="username"], input[aria-label*="username"], input[aria-label*="Phone"], input[placeholder*="username"], input[placeholder*="Phone"]'
        await page.wait_for_selector(username_sel, timeout=20000)
        username_input = page.locator(username_sel).first
        await username_input.click()
        await asyncio.sleep(0.3)
        await username_input.fill(username, timeout=5000)
        await asyncio.sleep(0.3)
        # Password
        password_sel = 'input[name="password"], input[type="password"], input[autocomplete="current-password"], input[aria-label*="Password"]'
        await page.wait_for_selector(password_sel, timeout=5000)
        password_input = page.locator(password_sel).first
        await password_input.click()
        await asyncio.sleep(0.3)
        await password_input.fill(password, timeout=5000)
        await asyncio.sleep(0.5)
        # Wait for submit button to be visible and enabled, then click (no .count() - avoid async count)
        submit_clicked = False
        for _ in range(3):
            try:
                submit_btn = page.locator('button[type="submit"]').first
                await submit_btn.wait_for(state="visible", timeout=3000)
                await asyncio.sleep(0.3)
                await submit_btn.click(timeout=5000)
                submit_clicked = True
                break
            except Exception:
                pass
            try:
                submit_btn = page.get_by_role("button", name="Log in").first
                await submit_btn.wait_for(state="visible", timeout=3000)
                await asyncio.sleep(0.3)
                await submit_btn.click(timeout=5000)
                submit_clicked = True
                break
            except Exception:
                pass
            try:
                submit_btn = page.locator('div[role="button"]').filter(has_text="Log in").first
                await submit_btn.wait_for(state="visible", timeout=3000)
                await asyncio.sleep(0.3)
                await submit_btn.click(timeout=5000)
                submit_clicked = True
                break
            except Exception:
                pass
            await asyncio.sleep(0.5)
        if not submit_clicked:
            logger.warning("Could not find or click Log in button")
            return False
        # Wait for navigation away from login (longer timeout; page may load slowly)
        try:
            await page.wait_for_url(
                lambda u: "accounts/login" not in u or "challenge" in u or "two_factor" in u,
                timeout=25000
            )
        except Exception:
            pass
        await asyncio.sleep(2)
        current = page.url
        # Do NOT bypass verification: if on challenge/2FA/verify page, WAIT for user to complete it
        verification_url_parts = ("challenge", "two_factor", "checkpoint", "verify", "verification", "confirm", "recovery")
        if any(part in current.lower() for part in verification_url_parts):
            logger.info(
                "Verification/2FA detected. Complete it in the browser now (enter code etc.). "
                "Waiting up to 2 minutes..."
            )
            for _ in range(24):
                await asyncio.sleep(5)
                current = page.url
                if not any(part in current.lower() for part in verification_url_parts) and "/accounts/" not in current:
                    logger.info("Verification completed, saving cookies.")
                    await save_cookies(context)
                    return True
            logger.warning("Verification not completed in time. Run the bot again and complete the code step.")
            return False
        if "accounts/login" in current:
            logger.warning("Still on login page after submit; login may have failed")
            return False
        # Only consider logged in if we're on main app (feed/reels) not a sub-page of accounts
        if "/accounts/" in current:
            logger.warning("Still on an accounts page; login may be incomplete")
            return False
        # Optional: detect verification content on page (e.g. "Enter security code") -> wait for user
        try:
            body_text = await page.locator("body").inner_text()
            body_lower = (body_text or "").lower()
            if any(
                phrase in body_lower
                for phrase in (
                    "enter security code",
                    "verification code",
                    "confirm your identity",
                    "check your email",
                    "send code",
                    "enter code",
                )
            ):
                logger.info(
                    "Verification step detected. Enter the code in the browser. Waiting up to 2 minutes..."
                )
                for _ in range(24):
                    await asyncio.sleep(5)
                    body_text = await page.locator("body").inner_text()
                    body_lower = (body_text or "").lower()
                    if not any(
                        phrase in body_lower
                        for phrase in (
                            "enter security code",
                            "verification code",
                            "confirm your identity",
                            "enter code",
                        )
                    ):
                        if "accounts/login" not in page.url and "/accounts/login" not in page.url:
                            logger.info("Verification completed, saving cookies.")
                            await save_cookies(context)
                            return True
                        break
                logger.warning("Verification not completed in time. Run the bot again.")
                return False
        except Exception:
            pass
        await save_cookies(context)
        return True
    except Exception as e:
        logger.warning("Login failed: %s", e)
        return False


async def _is_really_logged_in(page: Page) -> bool:
    """Return True only if page shows logged-in state (no 'Log in' / 'Open app' prompt)."""
    try:
        # If "Log in" link/button is visible, we're not logged in
        login_btn = page.get_by_role("link", name="Log in").first
        if (await login_btn.count()) > 0:
            try:
                if await login_btn.is_visible():
                    return False
            except Exception:
                pass
        login_btn2 = page.locator('a[href="/accounts/login/"]').first
        if (await login_btn2.count()) > 0:
            try:
                if await login_btn2.is_visible():
                    return False
            except Exception:
                pass
        # If "Watch this reel in the app" or "Open Instagram" modal is visible, not logged in
        body_text = await page.locator("body").inner_text()
        body_lower = (body_text or "").lower()
        if "watch this reel in the app" in body_lower or "open instagram" in body_lower:
            return False
        if "log in" in body_lower and "open app" in body_lower:
            return False
        return True
    except Exception:
        return False


async def ensure_logged_in(context: BrowserContext, page: Page) -> bool:
    """
    Try loading cookies first; navigate to Instagram. If not logged in, run login.
    Return True only when session is actually valid (page shows logged-in state).
    """
    loaded = await load_cookies(context)
    await page.goto(INSTAGRAM_HOME, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_load_state("load", timeout=25000)
    await asyncio.sleep(2)
    # URL check: explicit login page
    if "accounts/login" in page.url:
        return await login(context, page, INSTAGRAM_USER, INSTAGRAM_PASS)
    # Content check: even if URL is not login, page might show "Log in" / "Open app" when session is invalid
    if not await _is_really_logged_in(page):
        logger.info("Session invalid or expired (Log in / Open app visible). Logging in with credentials...")
        return await login(context, page, INSTAGRAM_USER, INSTAGRAM_PASS)
    return True
