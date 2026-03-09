"""
Structured logger for Instagram bot. Logs actions to stdout with [LEVEL] prefix.
"""
import logging

logger = logging.getLogger("instagram_bot")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)


def log_reel_viewed():
    logger.info("Reel viewed")


def log_liked():
    logger.info("Liked reel")


def log_comment_posted():
    logger.info("Comment posted")


def log_followed():
    logger.info("Followed user")


def log_skipped():
    logger.info("Skipped reel")


def log_skipped_not_niche():
    logger.info("Skipped (not niche)")


def log_skipped_follow_bio():
    logger.info("Skipped follow (bio not niche)")
