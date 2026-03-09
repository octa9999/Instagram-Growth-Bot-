"""
Niche-specific comments: simple lists per niche + OpenRouter AI.
Comments are under 8 words, natural, no spam. Tracks recent comments to avoid repeats.
"""
import random
import requests

from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_URL,
    OPENROUTER_MODEL,
    SIMPLE_COMMENTS_DESIGNER,
    SIMPLE_COMMENTS_FOUNDER,
    SIMPLE_COMMENTS_BUILDER,
)
from ai.niche_classifier import NICHE_DESIGNER, NICHE_FOUNDER, NICHE_BUILDER
from utils.logger import logger

NICHE_NAMES = {
    NICHE_DESIGNER: "Designer",
    NICHE_FOUNDER: "Founder",
    NICHE_BUILDER: "Developer/Builder",
}

SIMPLE_COMMENTS_BY_NICHE = {
    NICHE_DESIGNER: SIMPLE_COMMENTS_DESIGNER,
    NICHE_FOUNDER: SIMPLE_COMMENTS_FOUNDER,
    NICHE_BUILDER: SIMPLE_COMMENTS_BUILDER,
}

# Avoid repeating same comment: keep last N used (normalized to lowercase for comparison)
_RECENT_COMMENTS_MAX = 20
_recent_comments: list[str] = []


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def get_simple_comment(niche: int, avoid: list[str] | None = None) -> str:
    """Return a random simple comment for the given niche; skip any in avoid list."""
    comments = list(SIMPLE_COMMENTS_BY_NICHE.get(niche, SIMPLE_COMMENTS_DESIGNER))
    avoid_set = {_normalize(x) for x in (avoid or [])}
    allowed = [c for c in comments if _normalize(c) not in avoid_set]
    if not allowed:
        allowed = comments
    return random.choice(allowed)


def generate_ai_comment(caption: str, niche: int, avoid_phrases: list[str] | None = None) -> str:
    """
    Generate a short Instagram comment. Must sound like a real person.
    Complies with Instagram Community Standards: no spam, no high-volume patterns.
    """
    niche_name = NICHE_NAMES.get(niche, "Creator")
    avoid = avoid_phrases or []
    avoid_line = ""
    if avoid:
        avoid_line = f"\nDo NOT use these exact or very similar phrases: {', '.join(avoid[:15])}."
    prompt = (
        "Write ONE short Instagram comment as a real person in the "
        f"{niche_name} space. Reply naturally to the reel—one observation, one short question, or one genuine reaction. "
        "Stay within Instagram Community Standards (no spam).\n\n"
        "STRICT RULES:\n"
        "- Under 8 words. One short sentence only.\n"
        "- Sound like a normal human. No scripts, no marketing language.\n"
        "- NEVER use: 'curiosity hook', 'share the reel caption', 'craft', 'ready when you are', "
        "'please share', 'link in bio', 'follow me', 'check my page', or any request to the creator.\n"
        "- No self-promo, no all-caps, max 1 emoji if any.\n"
        "- Be specific to the content when possible; avoid generic or repeated phrases.\n"
        "- Each comment must be different and feel human."
        f"{avoid_line}\n\n"
        f"Reel caption (context only): {(caption or '')[:300]}"
    )
    if not OPENROUTER_API_KEY:
        return get_simple_comment(niche, avoid)
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        text = (content or "").strip()
        if text:
            return text[:100]
    except Exception as e:
        logger.warning("AI comment generation failed: %s", e)
    return get_simple_comment(niche, avoid)


def get_comment(caption: str, niche: int, use_ai: bool = True) -> str:
    """Unified API: AI or simple comment for the given niche. Avoids repeating recent comments."""
    global _recent_comments
    avoid = list(_recent_comments)
    if use_ai:
        text = generate_ai_comment(caption, niche, avoid_phrases=avoid)
    else:
        text = get_simple_comment(niche, avoid=avoid)
    _recent_comments.append(_normalize(text))
    if len(_recent_comments) > _RECENT_COMMENTS_MAX:
        _recent_comments = _recent_comments[-_RECENT_COMMENTS_MAX:]
    return text
