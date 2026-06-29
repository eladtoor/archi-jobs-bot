"""Derive a posting's architecture sub-field for the alert message.

Ordered rules — first match wins; default is "אדריכלות כללית".
"""

from __future__ import annotations

from .normalize import normalize

# (label, trigger terms). Order = priority.
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("רישוי והיתרים", ("רישוי", "היתר", "בקשה להיתר", "גרמושקה", "עורך בקשה", "בודק היתרים", "בודק תכניות")),
    ("תכנון ערים", ("תכנון ערים", "מתכנן ער", "מתכננת ער", "תכנון מרחבי", "תכנון עירוני", "סטטוטורי", 'תב"ע', "urban planner", "town planner")),
    ("אדריכלות נוף", ("אדריכלות נוף", "אדריכל נוף", "אדריכלית נוף", "landscape")),
    ("עיצוב פנים", ("עיצוב פנים", "מעצב פנים", "מעצבת פנים", "interior")),
    ("שרטוט והנדסאי", ("שרטט", "שרטוט", "הנדסאי", "הנדסאית", "draftsman", "draftsperson", "bim", "מידול", "revit", "רוויט")),
    ("ניהול פרויקטים", ("ניהול פרויקט", "מנהל פרויקט", "מנהלת פרויקט", "פרויקטים", "project manager")),
]

_DEFAULT = "אדריכלות כללית"


def derive_subfield(text: str) -> str:
    t = normalize(text)
    for label, triggers in _RULES:
        if any(normalize(trig) in t for trig in triggers):
            return label
    return _DEFAULT
