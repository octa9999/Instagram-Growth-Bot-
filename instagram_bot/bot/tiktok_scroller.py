"""
TikTok navigation and watch-time logic.

TikTok automation is high-risk. This module focuses on:
- conservative watch times
- minimal selectors (2026 web layout)
- basic search priming
"""
import asyncio
import random
from urllib.parse import quote

from playwright.async_api import Page

from config import (
    TIKTOK_BASE_URL,
    TIKTOK_SEARCH_KEYWORDS,
    TIKTOK_VIDEO_CONTAINER,
    TIKTOK_LIKE_BUTTON,
    TIKTOK_COMMENT_BUTTON,
    TIKTOK_COMMENT_INPUT,
    TIKTOK_AUTHOR_USERNAME,
    TIKTOK_VIDEO_CAPTION,
    TIKTOK_WATCH_NICHE_MIN,
    TIKTOK_WATCH_NICHE_MAX,
    TIKTOK_WATCH_NON_NICHE_MIN,
    TIKTOK_WATCH_NON_NICHE_MAX,
    TIKTOK_SCROLL_DELAY_MIN,
    TIKTOK_SCROLL_DELAY_MAX,
)


async def open_tiktok(page: Page) -> None:
    """Open TikTok home page."""
    await page.goto(TIKTOK_BASE_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)


async def _scroll_delay() -> None:
    delay = random.uniform(TIKTOK_SCROLL_DELAY_MIN, TIKTOK_SCROLL_DELAY_MAX)
    await asyncio.sleep(delay)


async def scroll_to_next_video(page: Page) -> None:
    """Scroll to the next TikTok video using ArrowDown."""
    try:
        await page.keyboard.press("ArrowDown")
        await asyncio.sleep(0.15)
        await page.keyboard.press("ArrowDown")
    except Exception:
        # Fallback: small wheel scroll
        try:
            await page.mouse.wheel(0, 600)
        except Exception:
            pass
    await _scroll_delay()


async def watch_video(page: Page, is_niche: bool) -> None:
    """
    Simulate watching the current video.

    For niche videos, watch longer; for non-niche, short watch before scroll.
    """
    if is_niche:
        duration = random.uniform(TIKTOK_WATCH_NICHE_MIN, TIKTOK_WATCH_NICHE_MAX)
    else:
        duration = random.uniform(TIKTOK_WATCH_NON_NICHE_MIN, TIKTOK_WATCH_NON_NICHE_MAX)
    steps = max(1, int(duration / 2))
    for _ in range(steps):
        try:
            await page.mouse.move(random.randint(120, 520), random.randint(160, 640))
        except Exception:
            pass
        await asyncio.sleep(2)


async def get_current_caption(page: Page) -> str:
    """Return caption text for the current video (best-effort)."""
    try:
        loc = page.locator(TIKTOK_VIDEO_CAPTION).first
        if await loc.count() > 0:
            text = await loc.text_content(timeout=3000)
            if text:
                return text.strip()[:1000]
    except Exception:
        pass
    return ""


async def get_current_author_username(page: Page) -> str:
    """Return username for current video author, without leading @."""
    try:
        loc = page.locator(TIKTOK_AUTHOR_USERNAME).first
        if await loc.count() > 0:
            text = await loc.text_content(timeout=3000)
            if text:
                return text.strip().lstrip("@").split()[0]
    except Exception:
        pass
    return ""


async def get_current_video_url(page: Page) -> str:
    """Return the current page URL (TikTok video URL)."""
    return page.url


async def open_search_and_prime(page: Page) -> None:
    """
    Simple priming: pick one keyword, open search results, watch 3 videos quickly.
    """
    if not TIKTOK_SEARCH_KEYWORDS:
        return
    keyword = random.choice(TIKTOK_SEARCH_KEYWORDS)
    url = f"{TIKTOK_BASE_URL}search?q={quote(keyword)}"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    # Try to click the first few videos and watch briefly
    for _ in range(3):
        try:
            container = page.locator(TIKTOK_VIDEO_CONTAINER).first
            if await container.count() > 0:
                await container.click(timeout=5000)
                await watch_video(page, is_niche=True)
                await scroll_to_next_video(page)
            else:
                break
        except Exception:
            break

