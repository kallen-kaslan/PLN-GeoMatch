"""Run worker integration regressions against isolated fixtures, never the live database."""

import subprocess
import sys
from pathlib import Path


def run_tests() -> None:
    """Verify redelivery, failures, history, and custom mapping with pytest."""
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_worker_foundations.py",
         "tests/test_upload_performance.py", "-v"],
        cwd=Path(__file__).resolve().parent,
        check=True,
    )


if __name__ == "__main__":
    run_tests()
