#!/usr/bin/env python3
"""Fail-closed checks for BacSelect production infrastructure portability."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "monthly-release.yml"
)

MONTHLY_WRAPPER = (
    ROOT
    / "validation"
    / "selector-v1"
    / "run_monthly_release_start.py"
)

FORBIDDEN_WORKFLOW_TOKENS = (
    "runs-on: self-hosted",
    "sbatch",
    "srun",
    "SLURM_",
    "/NGS/",
    "Rhys_wkdir",
    "jynx",
    "site.env",
)

FORBIDDEN_MONTHLY_WRAPPER_TOKENS = (
    "/NGS/",
    "Rhys_wkdir",
    "finch-ncbi-datasets",
    "sbatch",
    "srun",
    "SLURM_",
    "self-hosted",
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

REQUIRED_MONTHLY_WRAPPER_TOKENS = (
    "--production-root",
    "--datasets-executable",
    "EXPECTED_DATASETS_VERSION = \"18.35.0\"",
    (
        "EXPECTED_DATASETS_ENVIRONMENT_SHA256 = ("
    ),
    (
        '"environments/ncbi-datasets-linux-64.explicit.txt"'
    ),
)


def die(message: str) -> None:
    raise SystemExit(
        f"FAIL | {message}"
    )


for path in (
    WORKFLOW,
    MONTHLY_WRAPPER,
):
    if not path.is_file():
        die(
            "missing production file: "
            f"{path.relative_to(ROOT)}"
        )


workflow_text = WORKFLOW.read_text(
    encoding="utf-8"
)

wrapper_text = MONTHLY_WRAPPER.read_text(
    encoding="utf-8"
)


for token in FORBIDDEN_WORKFLOW_TOKENS:
    if token in workflow_text:
        die(
            "production workflow contains forbidden "
            f"infrastructure binding: {token!r}"
        )


for token in FORBIDDEN_MONTHLY_WRAPPER_TOKENS:
    if token in wrapper_text:
        die(
            "monthly source wrapper contains forbidden "
            f"infrastructure binding: {token!r}"
        )


for token in REQUIRED_WORKFLOW_TOKENS:
    if token not in workflow_text:
        die(
            "production workflow is missing required "
            f"portable binding: {token!r}"
        )


for token in REQUIRED_MONTHLY_WRAPPER_TOKENS:
    if token not in wrapper_text:
        die(
            "monthly source wrapper is missing required "
            f"portable binding: {token!r}"
        )


print(
    "PASS | BacSelect monthly workflow and Stage 1 wrapper "
    "are bound to portable GitHub-hosted infrastructure only"
)
