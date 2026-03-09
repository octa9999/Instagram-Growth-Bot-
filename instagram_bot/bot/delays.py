"""
Human-like random delays. All ranges read from config.
"""
import asyncio
import random

from config import (
    REEL_WATCH_MIN,
    REEL_WATCH_MAX,
    SCROLL_DELAY_MIN,
    SCROLL_DELAY_MAX,
    LIKE_DELAY_MIN,
    LIKE_DELAY_MAX,
    COMMENT_DELAY_MIN,
    COMMENT_DELAY_MAX,
    FOLLOW_DELAY_MIN,
    FOLLOW_DELAY_MAX,
    RANDOM_IDLE_MIN,
    RANDOM_IDLE_MAX,
)


async def human_delay(min_sec: float, max_sec: float) -> None:
    """Sleep for a random duration between min_sec and max_sec."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def watch_reel_delay() -> None:
    """Simulate watching the whole reel before engaging (human-like)."""
    await human_delay(REEL_WATCH_MIN, REEL_WATCH_MAX)


async def scroll_delay() -> None:
    await human_delay(SCROLL_DELAY_MIN, SCROLL_DELAY_MAX)


async def like_delay() -> None:
    await human_delay(LIKE_DELAY_MIN, LIKE_DELAY_MAX)


async def comment_delay() -> None:
    await human_delay(COMMENT_DELAY_MIN, COMMENT_DELAY_MAX)


async def follow_delay() -> None:
    await human_delay(FOLLOW_DELAY_MIN, FOLLOW_DELAY_MAX)


async def random_idle() -> None:
    """Extra random pause to simulate reading (e.g. between reels)."""
    await human_delay(RANDOM_IDLE_MIN, RANDOM_IDLE_MAX)
