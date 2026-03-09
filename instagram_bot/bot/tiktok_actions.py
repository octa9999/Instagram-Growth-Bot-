"""
TikTok-specific engagement actions.

WARNING: TikTok explicitly bans most automation. This module keeps
per-hour limits conservative and adds extra idle after bursts of comments.
"""
import asyncio
import random
import time

from playwright.async_api import Page

from config import (
    TIKTOK_LIKE_BUTTON,
    TIKTOK_COMMENT_BUTTON,
    TIKTOK_COMMENT_INPUT,
    TIKTOK_SHARE_BUTTON,
    TIKTOK_LIKE_PROBABILITY,
    TIKTOK_COMMENT_PROBABILITY,
    TIKTOK_FOLLOW_PROBABILITY,
    TIKTOK_COPYLINK_PROBABILITY,
    TIKTOK_MAX_LIKES_PER_HOUR,
    TIKTOK_MAX_COMMENTS_PER_HOUR,
    TIKTOK_MAX_FOLLOWS_PER_HOUR,
    TIKTOK_MAX_COPYLINKS_PER_HOUR,
    TIKTOK_COMMENT_IDLE_AFTER_N,
    TIKTOK_COMMENT_IDLE_MIN,
    TIKTOK_COMMENT_IDLE_MAX,
)
from utils.logger import logger

likes_this_hour = 0
comments_this_hour = 0
follows_this_hour = 0
copylinks_this_hour = 0
hour_start_time = time.time()
comments_since_idle = 0


def _reset_hour_if_needed() -> None:
    global likes_this_hour, comments_this_hour, follows_this_hour, copylinks_this_hour, hour_start_time, comments_since_idle
    if time.time() - hour_start_time >= 3600:
        likes_this_hour = 0
        comments_this_hour = 0
        follows_this_hour = 0
        copylinks_this_hour = 0
        comments_since_idle = 0
        hour_start_time = time.time()


async def _idle_after_comments_if_needed() -> None:
    global comments_since_idle
    if comments_since_idle >= TIKTOK_COMMENT_IDLE_AFTER_N:
        wait = random.uniform(TIKTOK_COMMENT_IDLE_MIN, TIKTOK_COMMENT_IDLE_MAX)
        logger.info("TikTok: long idle after comments (%.1fs)", wait)
        await asyncio.sleep(wait)
        comments_since_idle = 0


def decide_tiktok_action(is_niche_match: bool) -> str:
    """Weighted random choice for TikTok actions; returns one of like/comment/follow/copylink/skip."""
    if not is_niche_match:
        return "skip"
    _reset_hour_if_needed()
    weights = [
        TIKTOK_LIKE_PROBABILITY if likes_this_hour < TIKTOK_MAX_LIKES_PER_HOUR else 0,
        TIKTOK_COMMENT_PROBABILITY if comments_this_hour < TIKTOK_MAX_COMMENTS_PER_HOUR else 0,
        TIKTOK_FOLLOW_PROBABILITY if follows_this_hour < TIKTOK_MAX_FOLLOWS_PER_HOUR else 0,
        TIKTOK_COPYLINK_PROBABILITY if copylinks_this_hour < TIKTOK_MAX_COPYLINKS_PER_HOUR else 0,
    ]
    total = sum(weights)
    if total <= 0:
        return "skip"
    r = random.random() * total
    if r < weights[0]:
        return "like"
    if r < weights[0] + weights[1]:
        return "comment"
    if r < weights[0] + weights[1] + weights[2]:
        return "follow"
    if r < weights[0] + weights[1] + weights[2] + weights[3]:
        return "copylink"
    return "skip"


async def perform_tiktok_like(page: Page) -> None:
    """Click like on TikTok video."""
    global likes_this_hour
    _reset_hour_if_needed()
    if likes_this_hour >= TIKTOK_MAX_LIKES_PER_HOUR:
        return
    try:
        btn = page.locator(TIKTOK_LIKE_BUTTON).first
        if await btn.count() > 0:
            await btn.click(timeout=4000)
            likes_this_hour += 1
            logger.info("TikTok: liked video")
    except Exception as e:
        logger.warning("TikTok like failed: %s", e)


async def perform_tiktok_comment(page: Page, text: str) -> None:
    """Post a comment on TikTok video."""
    global comments_this_hour, comments_since_idle
    _reset_hour_if_needed()
    if comments_this_hour >= TIKTOK_MAX_COMMENTS_PER_HOUR:
        return
    if not text or not text.strip():
        return
    try:
        btn = page.locator(TIKTOK_COMMENT_BUTTON).first
        if await btn.count() > 0:
            await btn.click(timeout=5000)
            await asyncio.sleep(1.0)
        box = page.locator(TIKTOK_COMMENT_INPUT).first
        if await box.count() > 0:
            await box.click(timeout=4000)
            await box.fill(text[:200], timeout=5000)
            await asyncio.sleep(0.3)
            await page.keyboard.press("Enter")
            comments_this_hour += 1
            comments_since_idle += 1
            logger.info("TikTok: commented")
            await asyncio.sleep(1.2)
        await _idle_after_comments_if_needed()
    except Exception as e:
        logger.warning("TikTok comment failed: %s", e)


async def perform_tiktok_follow(page: Page, author_username: str) -> None:
    """
    Best-effort follow: go to profile URL and click Follow button.
    """
    global follows_this_hour
    _reset_hour_if_needed()
    if follows_this_hour >= TIKTOK_MAX_FOLLOWS_PER_HOUR:
        return
    if not author_username:
        return
    try:
        url = f"https://www.tiktok.com/@{author_username}"
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2.0)
        # TikTok follow button often reads "Follow" with role=button
        btn = page.get_by_role("button", name="Follow").first
        if await btn.count() == 0:
            btn = page.locator('button:has-text("Follow")').first
        if await btn.count() > 0:
            await btn.click(timeout=5000)
            follows_this_hour += 1
            logger.info("TikTok: followed @%s", author_username)
    except Exception as e:
        logger.warning("TikTok follow failed: %s", e)


async def perform_tiktok_copy_link(page: Page) -> None:
    """Open the share menu and click 'Copy link'."""
    global copylinks_this_hour
    _reset_hour_if_needed()
    if copylinks_this_hour >= TIKTOK_MAX_COPYLINKS_PER_HOUR:
        return
    try:
        btn = page.locator(TIKTOK_SHARE_BUTTON).first
        if await btn.count() > 0:
            await btn.click(timeout=5000)
            await asyncio.sleep(0.8)
            copy_btn = page.get_by_text("Copy link").first
            if await copy_btn.count() > 0:
                await copy_btn.click(timeout=5000)
                copylinks_this_hour += 1
                logger.info("TikTok: copied link")
                await asyncio.sleep(0.8)
    except Exception as e:
        logger.warning("TikTok copy link failed: %s", e)

