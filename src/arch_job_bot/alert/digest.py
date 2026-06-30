"""Weekly digest — a Sunday recap to Karin, built from the bot's own dedup history.

The dedup store counts a posting as 'seen' once (first_seen), so a 7-day window over
seen_jobs is the accurate count of genuinely-new jobs (re-bumps already filtered).
"""

from __future__ import annotations

from . import formatter


def format_weekly_digest(counts: dict) -> str:
    """counts = SeenStore.digest_counts(): {days, total, by_subfield, by_source}."""
    days = counts.get("days", 7)
    total = counts.get("total", 0)

    if total == 0:
        return ("📊 <b>סיכום שבועי — משרות אדריכלות</b>\n\n"
                f"לא נמצאו משרות חדשות ב-{days} הימים האחרונים. הבוט ממשיך לסרוק 🟢")

    lines = ["📊 <b>סיכום שבועי — משרות אדריכלות בבאר שבע והסביבה</b>",
             "",
             f"סה\"כ <b>{total}</b> משרות חדשות ב-{days} הימים האחרונים."]

    by_sub = counts.get("by_subfield") or {}
    if by_sub:
        lines.append("\n🗂️ לפי תחום:")
        for sub, n in by_sub.items():
            lines.append(f"• {sub}: {n}")

    by_src = counts.get("by_source") or {}
    if by_src:
        lines.append("\n🛰️ לפי מקור:")
        for src, n in by_src.items():
            lines.append(f"• {formatter.source_label(src)}: {n}")

    return "\n".join(lines)
