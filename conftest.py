"""Pytest bootstrap: put src/ on the import path so `import arch_job_bot` works."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
