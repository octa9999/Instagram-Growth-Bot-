"""
Niche classification: keyword detection + OpenRouter AI fallback.
Returns 1=Designer, 2=Founder, 3=Builder, 4=Other. Main loop engages only on 1/2/3.
"""
import re
import requests

from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_URL,
    OPENROUTER_MODEL,
    NICHE_KEYWORDS_DESIGN,
    NICHE_KEYWORDS_FOUNDER,
    NICHE_KEYWORDS_DEVELOPER,
    ENABLE_TIKTOK_OCR,
)
from utils.logger import logger

# Niche constants for callers
NICHE_DESIGNER = 1
NICHE_FOUNDER = 2
NICHE_BUILDER = 3
NICHE_OTHER = 4


def detect_niche_from_keywords(caption: str, hashtags: list[str]) -> int | None:
    """
    Check caption + hashtags for niche keywords. Return 1/2/3 or None if no match.
    If multiple niches match, return the first found (design -> founder -> developer).
    """
    combined = (caption or "").lower()
    for tag in hashtags or []:
        combined += " " + (tag or "").lower()

    for kw in NICHE_KEYWORDS_DESIGN:
        if kw.lower() in combined:
            return NICHE_DESIGNER
    for kw in NICHE_KEYWORDS_FOUNDER:
        if kw.lower() in combined:
            return NICHE_FOUNDER
    for kw in NICHE_KEYWORDS_DEVELOPER:
        if kw.lower() in combined:
            return NICHE_BUILDER
    return None


def classify_niche_with_ai(caption: str) -> int:
    """
    Call OpenRouter to classify caption. Return 1/2/3/4.
    On API or parse error return 4 (Other) so reel is skipped.
    """
    if not OPENROUTER_API_KEY or not caption.strip():
        return NICHE_OTHER

    prompt = (
        "Classify this Instagram reel caption. Return only one category: "
        "1 = Designer, 2 = Founder/Startup, 3 = Developer/Builder, 4 = Other. "
        f"Caption: {caption[:500]}"
    )
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
        # Parse first digit 1-4
        match = re.search(r"[1-4]", content)
        if match:
            return int(match.group())
    except Exception as e:
        logger.warning("Niche AI classification failed: %s", e)
    return NICHE_OTHER


def get_niche(caption: str, hashtags: list[str]) -> int:
    """
    Public API: try keyword detection first; if no match, use AI.
    Return 1/2/3 (engage) or 4 (skip). Default to NICHE_DESIGNER when unclear so we don't skip niche reels.
    """
    combined_caption = (caption or "").strip()
    tag_list = hashtags or []

    niche = detect_niche_from_keywords(combined_caption, tag_list)
    if niche is not None:
        return niche

    # No caption / no hashtags or very short text → assume niche (engage)
    if not combined_caption and not tag_list:
        return NICHE_DESIGNER
    if len(combined_caption) < 20:
        return NICHE_DESIGNER

    # Substantial caption but no keyword match: try AI
    result = classify_niche_with_ai(combined_caption)
    if result != NICHE_OTHER:
        return result
    # AI said Other or failed → still engage as designer to avoid skipping niche reels
    return NICHE_DESIGNER


def get_niche_with_extra_text(caption: str, hashtags: list[str], extra_text: str) -> int:
    """
    Same logic as get_niche, but allows appending extra text (e.g. OCR from TikTok
    on-screen hooks) to the caption before classification.
    """
    merged_caption = f"{caption or ''} {extra_text or ''}".strip()
    return get_niche(merged_caption, hashtags)


async def extract_tiktok_ocr_text(page) -> str:
    """
    Optional OCR helper for TikTok videos.

    If ENABLE_TIKTOK_OCR is False or pytesseract/Tesseract are not available,
    this returns an empty string so callers can safely ignore it.
    """
    if not ENABLE_TIKTOK_OCR:
        return ""
    try:
        import pytesseract  # type: ignore
        from PIL import Image
    except Exception:
        logger.warning("TikTok OCR requested but pytesseract/Pillow not available; skipping.")
        return ""
    try:
        # Take a screenshot of the viewport and crop center region where text overlays usually are.
        png_bytes = await page.screenshot(full_page=False)
        from io import BytesIO

        img = Image.open(BytesIO(png_bytes))
        w, h = img.size
        left = int(w * 0.15)
        right = int(w * 0.85)
        top = int(h * 0.25)
        bottom = int(h * 0.75)
        crop = img.crop((left, top, right, bottom))
        text = pytesseract.image_to_string(crop)
        return (text or "").strip()
    except Exception as e:
        logger.warning("TikTok OCR failed: %s", e)
        return ""
