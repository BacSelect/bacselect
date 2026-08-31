#!/usr/bin/env python3
"""Fail-closed checks for BacSelect production infrastructure portability."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]

WORKFLOW = ROOT / ".github" / "workflows" / "monthly-release.yml"

FORBIDDEN_WORKFLOW_TOKENS = (
    "runs-on: self-hosted",
    "sbatch",
    "srun",
    "SLURM_",
    "/NGS/",
    "jynx",
    "site.env",
)

REQUIRED_WORKFLOW_TOKENS = (
    "runs-on: ubuntu-latest",
    "cron: '17 0 1 * *'",
    "contents: read",
    "persist-credentials: false",
    "uses: actions/setup-python@v6",
    "python-version: '3.11'",
    "python -m pip install -e '.[test]'",
    "python -m pytest -q",
)


def die(message: str) -> None:
    raise SystemExit(f"FAIL | {message}")


if not WORKFLOW.is_file():
    die(f"missing production workflow: {WORKFLOW.relative_to(ROOT)}")

text = WORKFLOW.read_text(encoding="utf-8")

for token in FORBIDDEN_WORKFLOW_TOKENS:
    if token in text:
        die(
            "production workflow contains forbidden infrastructure binding: "
            f"{token!r}"
        )

for token in REQUIRED_WORKFLOW_TOKENS:
    if token not in text:
        die(
            "production workflow is missing required portable binding: "
            f"{token!r}"
        )

print(
    "PASS | BacSelect monthly workflow is bound to portable "
    "GitHub-hosted infrastructure only"
)
