"""
Engagement actions: like, comment, follow (with bio check), skip.
Niche-based decide_action with hourly limits.
"""
import asyncio
import random
import time
from playwright.async_api import Page

from config import (
    NICHE_LIKE_PROBABILITY,
    NICHE_COMMENT_PROBABILITY,
    NICHE_FOLLOW_PROBABILITY,
    MAX_LIKES_PER_HOUR,
    MAX_COMMENTS_PER_HOUR,
    MAX_FOLLOWS_PER_HOUR,
    BIO_KEYWORDS_FOR_FOLLOW,
    USERNAME_NICHE_KEYWORDS,
)
from utils.logger import (
    logger,
    log_liked,
    log_comment_posted,
    log_followed,
    log_skipped,
    log_skipped_follow_bio,
)
from bot.reels_scroller import close_comment_panel

# Hourly rate limits
likes_this_hour = 0
comments_this_hour = 0
follows_this_hour = 0
hour_start_time = time.time()

# Usernames we've already followed this session — skip when picking commenters
_followed_this_session: set[str] = set()


def _norm_username(u: str | None) -> str:
    """Normalize for comparison: lowercase, no leading @."""
    if not u:
        return ""
    return (u.strip().lstrip("@")).lower()


def _reset_hourly_if_needed() -> None:
    global likes_this_hour, comments_this_hour, follows_this_hour, hour_start_time
    if time.time() - hour_start_time >= 3600:
        likes_this_hour = 0
        comments_this_hour = 0
        follows_this_hour = 0
        hour_start_time = time.time()


def decide_action(is_niche_match: bool) -> str:
    """
    If not niche match return "skip". Else weighted random draw from like/comment/follow/skip.
    If chosen action is at hourly limit, fallback to skip.
    """
    if not is_niche_match:
        return "skip"
    _reset_hourly_if_needed()
    # Weighted choice: like, comment, follow, skip (rest)
    weights = [
        NICHE_LIKE_PROBABILITY if likes_this_hour < MAX_LIKES_PER_HOUR else 0,
        NICHE_COMMENT_PROBABILITY if comments_this_hour < MAX_COMMENTS_PER_HOUR else 0,
        NICHE_FOLLOW_PROBABILITY if follows_this_hour < MAX_FOLLOWS_PER_HOUR else 0,
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
    return "skip"


async def _click_like_or_comment(page: Page, kind: str) -> bool:
    """Click Like or Comment icon. Uses wait + normal click; falls back to force click if element not stable. Returns True if clicked."""
    label = "Like" if kind == "like" else "Comment"
    selectors = [
        f'[aria-label="{label}"]',
        f'svg[aria-label="{label}"]',
        f'button[aria-label="{label}"]',
    ]
    await asyncio.sleep(0.4)
    for sel in selectors:
        loc = page.locator(sel).first
        if await loc.count() == 0:
            continue
        try:
            await loc.wait_for(state="visible", timeout=3000)
            await asyncio.sleep(0.3)
            await loc.click(timeout=5000)
            return True
        except Exception:
            try:
                await loc.click(force=True, timeout=3000)
                return True
            except Exception:
                pass
    return False


async def perform_like(page: Page) -> None:
    """Click like on current reel; increment counter and log."""
    global likes_this_hour
    if await _click_like_or_comment(page, "like"):
        likes_this_hour += 1
        log_liked()


async def perform_comment(page: Page, text: str) -> None:
    """Open comment box, fill text, submit. Increment counter and log."""
    global comments_this_hour
    if not text or not text.strip():
        return
    try:
        if not await _click_like_or_comment(page, "comment"):
            raise RuntimeError("Comment button not clickable")
        await asyncio.sleep(0.6)
        comment_input = page.locator('textarea[placeholder*="Add a comment"], textarea[placeholder*="comment"], input[placeholder*="comment"]').first
        if await comment_input.count() > 0:
            await comment_input.fill(text[:300], timeout=4000)
            await asyncio.sleep(0.2)
            await page.keyboard.press("Enter")
            comments_this_hour += 1
            log_comment_posted()
            await asyncio.sleep(1.0)
            await close_comment_panel(page)
    except Exception as e:
        logger.warning("Comment failed: %s", e)
        try:
            await close_comment_panel(page)
        except Exception:
            pass


async def get_author_bio(page: Page, username: str) -> str:
    """Navigate to profile and read bio text. Return empty on failure."""
    try:
        await page.goto(f"https://www.instagram.com/{username}/", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_load_state("load", timeout=10000)
        # Bio is often in a div with class containing -bio or in header
        bio_el = page.locator("header -section div", has_text="").first
        for sel in [
            "header div.-vDIg span",
            "header section div span",
            "div.-vDIg span",
        ]:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                t = await loc.text_content()
                if t and len(t.strip()) > 0 and len(t.strip()) < 500:
                    return t.strip().lower()
    except Exception:
        pass
    return ""


def _bio_has_niche_keywords(bio: str) -> bool:
    """Return True if bio contains any of BIO_KEYWORDS_FOR_FOLLOW."""
    bio_lower = (bio or "").lower()
    return any(kw in bio_lower for kw in BIO_KEYWORDS_FOR_FOLLOW)


async def perform_follow(page: Page, author_username: str, skip_bio_check: bool = False) -> None:
    """
    Follow user. When skip_bio_check=True (e.g. niche reel creator), follow without bio check.
    When False (e.g. commenter), only follow if bio has niche keywords.
    Never opens DM: we only click the Follow button, never Message.
    """
    global follows_this_hour
    if not author_username:
        return
    profile_url = f"https://www.instagram.com/{author_username}/"
    try:
        if not skip_bio_check:
            bio = await get_author_bio(page, author_username)
            if not _bio_has_niche_keywords(bio):
                log_skipped_follow_bio()
                return
        else:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1)
        if "/direct/" in page.url:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(0.8)
        if "/direct/" in page.url:
            return
        follow_btn = None
        for loc in [
            page.get_by_role("button", name="Follow").first,
            page.locator('button[aria-label="Follow"]').first,
            page.locator('button:has-text("Follow")').first,
        ]:
            if await loc.count() == 0:
                continue
            node = loc.first
            aria = await node.get_attribute("aria-label") or ""
            if "message" in aria.lower() or "msg" in aria.lower():
                continue
            text = await node.text_content()
            if text and "Message" in text and "Follow" not in text:
                continue
            if text and "Follow" in text:
                follow_btn = node
                break
            if aria and "follow" in aria.lower():
                follow_btn = node
                break
        if follow_btn:
            await follow_btn.click(timeout=5000)
            follows_this_hour += 1
            _followed_this_session.add(_norm_username(author_username))
            log_followed()
    except Exception as e:
        logger.warning("Follow failed: %s", e)


async def perform_skip() -> None:
    """Log skip only."""
    log_skipped()


async def like_random_comments(page: Page, max_likes: int = 2) -> int:
    """
    Open comments, like 1–2 random commenters' comments (for traction), close panel.
    Returns number of comment likes done. Does not count toward likes_this_hour.
    """
    try:
        if not await _click_like_or_comment(page, "comment"):
            return 0
        await asyncio.sleep(1.2)
        like_icons = page.locator('[aria-label="Like"]')
        n = await like_icons.count()
        if n < 2:
            await close_comment_panel(page)
            return 0
        done = 0
        indices = list(range(1, min(n, 6)))
        random.shuffle(indices)
        for i in indices[:max_likes]:
            try:
                await like_icons.nth(i).click(timeout=2000)
                done += 1
                await asyncio.sleep(0.5)
            except Exception:
                pass
        await close_comment_panel(page)
        if done:
            logger.info("Liked %d comment(s)", done)
        return done
    except Exception as e:
        logger.warning("Like comment failed: %s", e)
        try:
            await close_comment_panel(page)
        except Exception:
            pass
        return 0


def can_follow_more() -> bool:
    """True if under hourly follow limit."""
    _reset_hourly_if_needed()
    return follows_this_hour < MAX_FOLLOWS_PER_HOUR


def _username_looks_niche(username: str) -> bool:
    """True if username contains any USERNAME_NICHE_KEYWORDS (designer/founder/builder vibe)."""
    if not username:
        return False
    un = username.lower()
    return any(kw in un for kw in USERNAME_NICHE_KEYWORDS)


async def try_follow_random_commenter(page: Page) -> tuple[bool, str | None]:
    """
    Open comments, get commenters. Prefer niche-looking usernames; else pick random.
    Follow with bio check. Returns (True, username) if we followed, (False, None) otherwise.
    """
    from bot.reels_scroller import get_commenters_from_reel
    global follows_this_hour
    _reset_hourly_if_needed()
    if follows_this_hour >= MAX_FOLLOWS_PER_HOUR:
        return False, None
    commenters = await get_commenters_from_reel(page)
    if not commenters:
        return False, None
    not_followed = [u for u in commenters if _norm_username(u) not in _followed_this_session]
    if not not_followed:
        return False, None
    niche_commenters = [u for u in not_followed if _username_looks_niche(u)]
    username = random.choice(niche_commenters) if niche_commenters else random.choice(not_followed)
    logger.info("Following commenter: @%s", username)
    before = follows_this_hour
    await perform_follow(page, username, skip_bio_check=True)
    if follows_this_hour > before:
        return True, username
    return False, None
