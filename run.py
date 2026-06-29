"""Run wrapper so the bot works without installing the package.

    python run.py --dry-run --once
    python run.py --seed
    python run.py                 # loop on the poll schedule
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))

from arch_job_bot.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
