"""
Reels navigation: open reels feed, hashtag reels, follower reels; scroll; extract caption, hashtags, author.
Instagram selectors may need updates when the site changes.
"""
import asyncio
import re
from urllib.parse import quote

from playwright.async_api import Page

from config import REELS_URL, TARGET_HASHTAGS, COMPETITOR_ACCOUNTS
from bot.delays import scroll_delay

# Selectors (centralized for maintenance when Instagram DOM changes)
REEL_CONTAINER = "section main"
CAPTION_SELECTOR = "[data-ad-preview='message']"  # or span in reel overlay
AUTHOR_LINK_SELECTOR = "header a[href^='/']"  # first profile link in reel header
HASHTAG_IN_CAPTION = "a[href^='/explore/tags/']"


async def close_comment_panel(page: Page) -> None:
    """Dismiss the comment sheet: many Escapes, then tap backdrop (dimmed area above sheet), then Close button."""
    for _ in range(10):
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.25)
        except Exception:
            pass
    for x, y in [(195, 180), (100, 220), (280, 200)]:
        try:
            await page.mouse.click(x, y)
            await asyncio.sleep(0.2)
        except Exception:
            pass
    for _ in range(5):
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
        except Exception:
            pass
    try:
        close_btn = page.locator('[aria-label="Close"], [aria-label="close"]').first
        if await close_btn.count() > 0:
            await close_btn.click(timeout=1000)
    except Exception:
        pass
    await asyncio.sleep(0.3)


async def is_comment_panel_open(page: Page) -> bool:
    """True if the comment sheet is open (e.g. 'Add a comment' input visible)."""
    try:
        inp = page.locator('textarea[placeholder*="Add a comment"], textarea[placeholder*="comment"], input[placeholder*="comment"]').first
        if await inp.count() > 0:
            return await inp.is_visible()
    except Exception:
        pass
    return False


async def dismiss_notification_modal(page: Page) -> bool:
    """If 'Turn on Notifications' (or similar) modal is open, click 'Not Now' to close. Returns True if dismissed."""
    try:
        not_now = page.get_by_role("button", name="Not Now")
        if await not_now.count() > 0 and await not_now.first.is_visible():
            await not_now.first.click(timeout=3000)
            await asyncio.sleep(0.3)
            return True
    except Exception:
        pass
    try:
        not_now = page.locator('button:has-text("Not Now"), [role="button"]:has-text("Not Now"), a:has-text("Not Now")').first
        if await not_now.count() > 0 and await not_now.is_visible():
            await not_now.click(timeout=3000)
            await asyncio.sleep(0.3)
            return True
    except Exception:
        pass
    try:
        if "Turn on Notifications" in await page.content():
            btn = page.get_by_text("Not Now", exact=True).first
            if await btn.count() > 0:
                await btn.click(timeout=3000)
                await asyncio.sleep(0.3)
                return True
    except Exception:
        pass
    return False


async def open_reels(page: Page) -> None:
    """Navigate to main Reels feed and wait for reel container."""
    await page.goto(REELS_URL, wait_until="domcontentloaded", timeout=30000)
    await dismiss_notification_modal(page)
    await page.wait_for_selector(REEL_CONTAINER, timeout=15000)
    await asyncio.sleep(2)


async def open_hashtag_reels(page: Page, tag: str) -> None:
    """Navigate to hashtag explore page. Reels tab may need to be clicked if present."""
    url = f"https://www.instagram.com/explore/tags/{quote(tag)}/"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await dismiss_notification_modal(page)
    await asyncio.sleep(2)
    # Try to click Reels tab if visible
    reels_tab = page.locator('a[href*="/reels/"]').first
    if await reels_tab.count() > 0:
        try:
            await reels_tab.click(timeout=3000)
            await asyncio.sleep(2)
        except Exception:
            pass
    await page.wait_for_selector(REEL_CONTAINER, timeout=15000)


async def open_follower_reels(page: Page, account: str, follower_username: str) -> None:
    """
    Go to competitor account -> followers -> open follower's profile -> open their reels.
    """
    profile_url = f"https://www.instagram.com/{account}/"
    await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(2)
    # Click followers link (e.g. "X followers")
    try:
        await page.click('a[href*="/followers/"]', timeout=5000)
        await asyncio.sleep(2)
    except Exception:
        # Fallback: direct to followers list
        await page.goto(f"https://www.instagram.com/{account}/followers/", timeout=30000)
        await asyncio.sleep(2)
    # Open specific follower profile (scroll to find or click by username)
    follower_profile = f"https://www.instagram.com/{follower_username}/"
    await page.goto(follower_profile, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(2)
    # Click Reels tab on profile
    reels_tab = page.locator(f'a[href="/{follower_username}/reels/"]').first
    if await reels_tab.count() > 0:
        try:
            await reels_tab.click(timeout=5000)
            await asyncio.sleep(2)
        except Exception:
            pass
    # If no reels tab, we're on profile; first reel might be in grid - click first reel
    try:
        await page.wait_for_selector(REEL_CONTAINER, timeout=10000)
    except Exception:
        pass


async def scroll_to_next(page: Page) -> None:
    """Scroll exactly one reel: close comment panel if open, then focus and scroll."""
    if await is_comment_panel_open(page):
        await close_comment_panel(page)
        await asyncio.sleep(0.5)
    try:
        await page.mouse.click(200, 400)
        await asyncio.sleep(0.15)
        for _ in range(6):
            await page.keyboard.press("ArrowDown")
            await asyncio.sleep(0.1)
        try:
            await page.mouse.wheel(0, 280)
            await asyncio.sleep(0.08)
            await page.mouse.wheel(0, 200)
        except Exception:
            pass
    except Exception:
        try:
            for _ in range(7):
                await page.keyboard.press("ArrowDown")
                await asyncio.sleep(0.1)
        except Exception:
            pass
    await scroll_delay()


# UI phrases we must not treat as reel caption (would break niche detection)
_CAPTION_UI_SKIP = frozenset({
    "reels", "reel", "comments", "comment", "like", "follow", "share", "send message",
    "add a comment", "home", "search", "profile", "more", "less", "reply", "likes",
})

def _is_likely_caption(text: str) -> bool:
    """True if text looks like a real caption, not UI or noise."""
    if not text or len(text.strip()) < 5:
        return False
    t = text.strip().lower()[:80]
    if len(t) < 15 and t in _CAPTION_UI_SKIP:
        return False
    words = set(t.split())
    if words & _CAPTION_UI_SKIP and len(words) <= 3:
        return False
    return True


async def get_current_caption(page: Page) -> str:
    """Extract caption text from current reel. Return empty if not found or if text is UI/noise."""
    try:
        for sel in [
            "[data-ad-preview='message']",
            "span._ap3a._aaco._aacu._aacx._aad7._aade",
            "header + div span[dir='auto']",
            "section article span[dir='auto']",
            "section span",
        ]:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                text = await loc.text_content(timeout=2000)
                if text:
                    text = text.strip()[:1000]
                    if _is_likely_caption(text):
                        return text
    except Exception:
        pass
    return ""


async def get_current_hashtags(page: Page) -> list[str]:
    """Parse hashtags from current reel caption area. Return list of strings without #."""
    hashtags = []
    try:
        links = page.locator(HASHTAG_IN_CAPTION)
        n = await links.count()
        for i in range(min(n, 20)):
            href = await links.nth(i).get_attribute("href")
            if href and "/explore/tags/" in href:
                tag = href.split("/explore/tags/")[-1].rstrip("/").split("?")[0]
                if tag:
                    hashtags.append(tag.lower())
        if not hashtags:
            caption = await get_current_caption(page)
            for m in re.finditer(r"#(\w+)", caption):
                hashtags.append(m.group(1).lower())
    except Exception:
        pass
    return hashtags


async def get_commenters_from_reel(page: Page, max_commenters: int = 15) -> list[str]:
    """Open comments, collect commenter usernames, close comments. Return list of unique usernames."""
    usernames = []
    try:
        comment_btn = page.locator('button[aria-label="Comment"], span[aria-label="Comment"], [aria-label="Comment"], svg[aria-label="Comment"]').first
        if await comment_btn.count() == 0:
            return []
        await comment_btn.click(timeout=3000)
        await asyncio.sleep(1.5)
        links = page.locator('a[role="link"][href^="/"]')
        n = await links.count()
        seen = set()
        for i in range(min(n, 50)):
            try:
                href = await links.nth(i).get_attribute("href")
                if not href or href in ("/", "/reels/"):
                    continue
                part = href.strip("/").split("/")[0]
                if not part or part in ("explore", "reels", "accounts", "stories", "direct"):
                    continue
                if part in seen:
                    continue
                seen.add(part)
                usernames.append(part)
                if len(usernames) >= max_commenters:
                    break
            except Exception:
                continue
    except Exception:
        pass
    await close_comment_panel(page)
    return usernames


async def get_current_author_username(page: Page) -> str:
    """Get username of the current reel author (for follow action and report)."""
    try:
        url = page.url
        m = re.search(r"instagram\.com/([^/]+)/reel/", url)
        if m:
            u = m.group(1)
            if u not in ("explore", "reels", "accounts", "stories", "direct"):
                return u
        for sel in [
            "header a[role='link'][href^='/']",
            "header a[href^='/']",
            "section a[href^='/']",
            "a[role='link'][href^='/']",
        ]:
            loc = page.locator(sel)
            n = await loc.count()
            for i in range(min(n, 8)):
                href = await loc.nth(i).get_attribute("href")
                if not href:
                    continue
                part = href.strip("/").split("/")[0]
                if not part or part in ("explore", "reels", "accounts", "stories", "direct"):
                    continue
                return part
    except Exception:
        pass
    return ""
