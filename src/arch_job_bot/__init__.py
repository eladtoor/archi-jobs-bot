"""Architecture job-alert bot for Beer Sheva / South Israel.

Scans Israeli job boards for new architecture (אדריכלות) openings in the Beer Sheva
commuter area, matches with a recall-first Hebrew classifier, de-duplicates, and
pushes a Hebrew summary to Telegram. See the plan in .claude/plans/.
"""

__version__ = "0.1.0"
