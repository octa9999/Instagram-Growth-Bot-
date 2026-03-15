"""
Instagram Reels automation bot — entry point.
Run: python main.py
Starts browser, ensures login, opens Reels, runs infinite engagement loop with niche detection and source rotation.
"""
import asyncio
import random
import sys

from dotenv import load_dotenv

from config import (
    REELS_URL,
    TARGET_HASHTAGS,
    REELS_PER_SOURCE_BEFORE_SWITCH,
    FOLLOW_COMMENTER_PROBABILITY,
    REEL_CREATOR_FOLLOW_PROBABILITY,
    LIKE_RANDOM_COMMENT_PROBABILITY,
    COMMENT_USE_AI_PROBABILITY,
    AUTHOR_MAX_ENGAGEMENTS_PER_SESSION,
    RECENT_REEL_DEDUP_MAX,
    TIKTOK_MAX_SESSION_MINUTES,
    MAX_SESSION_HOURS,
)
from bot.browser import create_browser, create_browser_no_login
from bot.reels_scroller import (
    open_reels,
    open_hashtag_reels,
    scroll_to_next,
    get_current_caption,
    get_current_hashtags,
    get_current_author_username,
    dismiss_notification_modal,
)
from bot.actions import (
    decide_action,
    perform_like,
    perform_comment,
    perform_follow,
    perform_skip,
    try_follow_random_commenter,
    like_random_comments,
    can_follow_more,
)
from bot.delays import like_delay, comment_delay, follow_delay, scroll_delay, random_idle, watch_reel_delay
from bot.tiktok_scroller import (
    open_tiktok,
    open_search_and_prime,
    scroll_to_next_video,
    watch_video as watch_tiktok_video,
    get_current_caption as get_tiktok_caption,
    get_current_author_username as get_tiktok_author,
    get_current_video_url,
)
from bot.tiktok_actions import (
    decide_tiktok_action,
    perform_tiktok_like,
    perform_tiktok_comment,
    perform_tiktok_follow,
    perform_tiktok_copy_link,
)
from ai.niche_classifier import (
    get_niche,
    get_niche_with_extra_text,
    extract_tiktok_ocr_text,
    NICHE_OTHER,
)
from ai.comment_generator import get_comment
from utils.logger import logger, log_reel_viewed, log_skipped_not_niche
from utils import session_report

load_dotenv()

_recent_reel_urls: list[str] = []
_author_engagements: dict[str, int] = {}


def _norm_reel_url(url: str) -> str:
    return (url or "").split("?")[0].strip()


def _remember_reel(url: str) -> None:
    u = _norm_reel_url(url)
    if not u:
        return
    _recent_reel_urls.append(u)
    if len(_recent_reel_urls) > RECENT_REEL_DEDUP_MAX:
        del _recent_reel_urls[:-RECENT_REEL_DEDUP_MAX]


def _seen_reel(url: str) -> bool:
    u = _norm_reel_url(url)
    return bool(u and u in _recent_reel_urls)


def _norm_user(u: str | None) -> str:
    return (u or "").strip().lstrip("@").lower()


def _can_engage_author(author: str | None) -> bool:
    a = _norm_user(author)
    if not a:
        return True
    return _author_engagements.get(a, 0) < AUTHOR_MAX_ENGAGEMENTS_PER_SESSION


def _mark_author_engagement(author: str | None) -> None:
    a = _norm_user(author)
    if not a:
        return
    _author_engagements[a] = _author_engagements.get(a, 0) + 1


def _build_sources():
    """(kind, param) where kind is 'feed' or 'hashtag', param is tag or None."""
    sources = [("feed", None)]
    for tag in TARGET_HASHTAGS:
        sources.append(("hashtag", tag))
    return sources


async def _open_current_source(page, kind: str, param) -> None:
    """Open reels for the given source type."""
    if kind == "feed":
        await open_reels(page)
    else:
        await open_hashtag_reels(page, param)


async def run_loop(page, sources: list, current_index: int) -> None:
    """Single reel iteration: watch reel, niche check, decide action (like/comment/follow/skip), scroll."""
    await dismiss_notification_modal(page)
    kind, param = sources[current_index]
    url = page.url
    if "/stories/" in url:
        await open_reels(page)
        return
    if "/reel" in url and "instagram.com/reels" not in url.split("?")[0]:
        try:
            await page.goto(REELS_URL, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass
        return
    reel_url = page.url
    if _seen_reel(reel_url):
        await scroll_to_next(page)
        return
    _remember_reel(reel_url)
    log_reel_viewed()
    session_report.log_reel_viewed()
    await watch_reel_delay()
    caption = await get_current_caption(page)
    hashtags = await get_current_hashtags(page)
    niche = get_niche(caption, hashtags)
    if niche == NICHE_OTHER:
        log_skipped_not_niche()
        await scroll_to_next(page)
        return
    author = await get_current_author_username(page)
    if not author:
        await asyncio.sleep(0.5)
        author = await get_current_author_username(page)
    reel_url = page.url
    action = decide_action(is_niche_match=True)
    if not _can_engage_author(author) and action in ("like", "comment", "follow"):
        action = "skip"
    if action == "like":
        await perform_like(page)
        a = author or await get_current_author_username(page)
        session_report.log_like(reel_url, a)
        _mark_author_engagement(a)
        await like_delay()
    elif action == "comment":
        use_ai = random.random() < COMMENT_USE_AI_PROBABILITY
        text = get_comment(caption, niche, use_ai=use_ai)
        await perform_comment(page, text)
        session_report.log_comment(reel_url, author, text)
        _mark_author_engagement(author)
        await comment_delay()
    elif action == "follow":
        if author:
            await perform_follow(page, author, skip_bio_check=True)
            session_report.log_follow(author)
            _mark_author_engagement(author)
            await _open_current_source(page, kind, param)
        await follow_delay()
    else:
        await perform_skip()
    if action != "follow" and author and can_follow_more() and random.random() < REEL_CREATOR_FOLLOW_PROBABILITY:
        try:
            logger.info("Following reel creator: @%s", author)
            await perform_follow(page, author, skip_bio_check=True)
            session_report.log_follow(author)
            _mark_author_engagement(author)
            await _open_current_source(page, kind, param)
        except Exception:
            pass
    if random.random() < FOLLOW_COMMENTER_PROBABILITY:
        try:
            ok, followed_username = await try_follow_random_commenter(page)
            if ok and followed_username:
                session_report.log_follow(followed_username)
                await _open_current_source(page, kind, param)
        except Exception:
            pass
    if random.random() < LIKE_RANDOM_COMMENT_PROBABILITY:
        try:
            n = await like_random_comments(page, max_likes=2)
            if n > 0:
                session_report.log_comment_likes(n)
        except Exception:
            pass
    if random.random() < 0.3:
        try:
            await page.mouse.move(random.randint(100, 400), random.randint(100, 400))
        except Exception:
            pass
    await random_idle()
    await scroll_to_next(page)


async def main_async() -> None:
    # Determine platform from CLI args if provided; otherwise ask interactively.
    platform = None
    for arg in sys.argv[1:]:
        lower = arg.lower()
        if lower in ("--platform=tt", "--platform=tiktok", "tt", "tiktok"):
            platform = "tt"
        elif lower in ("--platform=ig", "--platform=instagram", "ig", "instagram"):
            platform = "ig"
        elif lower in ("--platform=both", "both"):
            platform = "both"

    report_path = session_report.start_session()
    print(f"Session report (live): {report_path}")

    if platform is None:
        print("Select platform to run:")
        print("  1) Instagram only")
        print("  2) TikTok only (experimental, higher ban risk)")
        print("  3) Both (Instagram then TikTok)")
        choice = input("Enter 1, 2, or 3: ").strip()
        if choice == "2":
            platform = "tt"
        elif choice == "3":
            platform = "both"
        else:
            platform = "ig"

    if platform == "tt":
        print("TikTok Bot Started (experimental, higher ban risk)")
        session_report.set_platform("tt")
        await _run_tiktok_main()
    elif platform == "both":
        print("Instagram Bot Started (part 1 of both)")
        session_report.set_platform("ig")
        await _run_instagram_main()
        print("TikTok Bot Started (part 2 of both, experimental, higher ban risk)")
        session_report.set_platform("tt")
        await _run_tiktok_main()
    else:
        print("Instagram Bot Started")
        session_report.set_platform("ig")
        await _run_instagram_main()


async def _run_instagram_main() -> None:
    sources = _build_sources()
    current_index = 0
    reels_count = 0
    browser = context = page = None
    loop = asyncio.get_event_loop()
    start_time = loop.time()
    try:
        browser, context, page = await create_browser(headless=False)
        await _open_current_source(page, "feed", None)
        while True:
            # Optional session cap for safety
            elapsed_hours = (loop.time() - start_time) / 3600.0
            if MAX_SESSION_HOURS and elapsed_hours >= MAX_SESSION_HOURS:
                logger.info("Instagram session reached max hours (%.2f), stopping.", elapsed_hours)
                break
            await run_loop(page, sources, current_index)
            reels_count += 1
            if REELS_PER_SOURCE_BEFORE_SWITCH and reels_count >= REELS_PER_SOURCE_BEFORE_SWITCH:
                current_index = (current_index + 1) % len(sources)
                reels_count = 0
                kind, param = sources[current_index]
                await _open_current_source(page, kind, param)
            await asyncio.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.exception("Error: %s", e)
        sys.exit(1)
    finally:
        if browser:
            await browser.close()


async def _run_tiktok_main() -> None:
    """
    TikTok entry flow (no login automation; user should already be logged into TikTok in this browser profile).
    """
    browser = context = page = None
    loop = asyncio.get_event_loop()
    start_time = loop.time()
    try:
        browser, context, page = await create_browser_no_login(headless=False)
        await open_tiktok(page)
        await open_search_and_prime(page)
        while True:
            elapsed_min = (loop.time() - start_time) / 60.0
            if elapsed_min >= TIKTOK_MAX_SESSION_MINUTES:
                logger.info("TikTok session reached max minutes (%.1f), stopping.", elapsed_min)
                break

            caption = await get_tiktok_caption(page)
            hashtags: list[str] = []
            ocr_text = await extract_tiktok_ocr_text(page)
            niche = get_niche_with_extra_text(caption, hashtags, ocr_text)
            is_niche = niche != NICHE_OTHER

            if is_niche:
                await watch_tiktok_video(page, is_niche=True)
                author = await get_tiktok_author(page)
                video_url = await get_current_video_url(page)
                action = decide_tiktok_action(is_niche_match=True)
                if action == "like":
                    await perform_tiktok_like(page)
                    session_report.log_like(video_url, author)
                elif action == "comment":
                    # Reuse existing IG comment generator for TikTok caption / OCR text
                    from ai.comment_generator import get_comment as get_ig_comment

                    text = get_ig_comment(caption or ocr_text, niche)
                    await perform_tiktok_comment(page, text)
                    session_report.log_comment(video_url, author, text)
                elif action == "follow":
                    await perform_tiktok_follow(page, author)
                    session_report.log_follow(author)
                elif action == "copylink":
                    await perform_tiktok_copy_link(page)
                await random_idle()
            else:
                await watch_tiktok_video(page, is_niche=False)

            await scroll_to_next_video(page)
            session_report.log_reel_viewed()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.exception("TikTok error: %s", e)
    finally:
        if browser:
            await browser.close()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

