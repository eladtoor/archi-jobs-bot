"""Text normalization shared by the classifier, geo matcher, and sub-field deriver.

Matching is substring-based on the *normalized* form of both the posting text and
the configured keywords, so both sides must be normalized the same way.
"""

from __future__ import annotations

import re

# Hebrew combining marks (niqqud, cantillation) — stripped so "אֲדֲרִיכָל" == "אדריכל".
_NIQQUD = re.compile("[֑-ׇ]")
_WS = re.compile(r"\s+")

# Punctuation that varies between postings → fold to ASCII so keywords match.
_TRANSLATE = {
    ord("׳"): "'",   # ׳ Hebrew geresh   → '
    ord("״"): '"',   # ״ Hebrew gershayim → "
    ord("‘"): "'",   # ' left single quote
    ord("’"): "'",   # ' right single quote
    ord("“"): '"',   # " left double quote
    ord("”"): '"',   # " right double quote
    ord("–"): "-",   # – en dash
    ord("—"): "-",   # — em dash
    ord("ך"): "כ",   # final kaf  → fold Hebrew final letters so gender/combined
    ord("ם"): "מ",   # final mem    forms match (e.g. "מתכנן/ת" → "מתכננת")
    ord("ן"): "נ",   # final nun
    ord("ף"): "פ",   # final pe
    ord("ץ"): "צ",   # final tsadi
    ord(" "): " ",   # non-breaking space
}


def normalize(text: str | None) -> str:
    """Lower-case (affects Latin only), strip Hebrew diacritics, fold punctuation,
    collapse the gender slash, and collapse whitespace. Idempotent.

    The slash is dropped so gender-combined forms match keyword variants:
    "בודק/ת תכניות" → "בודקת תכניות", "מתכנן/ת ערים" → "מתכננת ערים"."""
    if not text:
        return ""
    text = text.translate(_TRANSLATE)
    text = _NIQQUD.sub("", text)
    text = text.replace("/", "")
    text = text.lower()
    text = _WS.sub(" ", text)
    return text.strip()
