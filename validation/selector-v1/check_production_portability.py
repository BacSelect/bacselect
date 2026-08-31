#!/usr/bin/env python3
"""Fail-closed checks for BacSelect production infrastructure portability."""

from hashlib import sha256
from pathlib import Path
import re


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

SOURCE_ENVIRONMENT = (
    ROOT
    / "environments"
    / "ncbi-datasets-linux-64.explicit.txt"
)

RECONSTRUCTION_ENVIRONMENT = (
    ROOT
    / "environments"
    / "ncbi-datasets-linux-64.reconstruction.explicit.txt"
)

EXPECTED_SOURCE_ENVIRONMENT_SHA256 = (
    "6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd"
)

EXPECTED_RECONSTRUCTION_ENVIRONMENT_SHA256 = (
    "5e3b5008cf773689459acfe1ecfe0ce45bf89374f1dc3ebedd5cc3ff0f59c0e1"
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
    (
        "uses: mamba-org/setup-micromamba@"
        "f457c30a868e4760d3a6fcea5f25dc655b8edf39"
    ),
    "micromamba-version: '2.8.1-0'",
    (
        "environment-file: "
        "environments/ncbi-datasets-linux-64.reconstruction.explicit.txt"
    ),
    "environment-name: bacselect-ncbi-datasets-runtime",
    "cache-environment: false",
    "cache-downloads: false",
    "datasets version: 18.35.0",
    (
        'EXPECTED_SOURCE_ENV_SHA="'
        + EXPECTED_SOURCE_ENVIRONMENT_SHA256
        + '"'
    ),
    (
        'EXPECTED_RECON_ENV_SHA="'
        + EXPECTED_RECONSTRUCTION_ENVIRONMENT_SHA256
        + '"'
    ),
)

REQUIRED_MONTHLY_WRAPPER_TOKENS = (
    "--production-root",
    "--datasets-executable",
    'EXPECTED_DATASETS_VERSION = "18.35.0"',
    "EXPECTED_DATASETS_ENVIRONMENT_SHA256 = (",
    '"environments/ncbi-datasets-linux-64.explicit.txt"',
)


def die(message: str) -> None:
    raise SystemExit(
        f"FAIL | {message}"
    )


def sha256_file(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def explicit_packages(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.startswith("https://")
    ]


for path in (
    WORKFLOW,
    MONTHLY_WRAPPER,
    SOURCE_ENVIRONMENT,
    RECONSTRUCTION_ENVIRONMENT,
):
    if not path.is_file():
        die(
            "missing production file: "
            f"{path.relative_to(ROOT)}"
        )


if (
    sha256_file(
        SOURCE_ENVIRONMENT
    )
    != EXPECTED_SOURCE_ENVIRONMENT_SHA256
):
    die(
        "frozen scientific NCBI environment SHA256 changed"
    )


if (
    sha256_file(
        RECONSTRUCTION_ENVIRONMENT
    )
    != EXPECTED_RECONSTRUCTION_ENVIRONMENT_SHA256
):
    die(
        "checksum-authenticated reconstruction manifest SHA256 changed"
    )


source_packages = explicit_packages(
    SOURCE_ENVIRONMENT
)

reconstruction_packages = explicit_packages(
    RECONSTRUCTION_ENVIRONMENT
)

if len(source_packages) != 2:
    die(
        "frozen scientific NCBI environment must contain exactly two packages"
    )

if len(reconstruction_packages) != 2:
    die(
        "NCBI reconstruction manifest must contain exactly two packages"
    )


reconstruction_urls: list[str] = []

for package in reconstruction_packages:
    if "#" not in package:
        die(
            "NCBI reconstruction package lacks checksum"
        )

    url, checksum = package.rsplit(
        "#",
        1,
    )

    if re.fullmatch(
        r"[0-9a-f]{32}",
        checksum,
    ) is None:
        die(
            "NCBI reconstruction package checksum is not canonical MD5"
        )

    reconstruction_urls.append(
        url
    )


if reconstruction_urls != source_packages:
    die(
        "NCBI reconstruction package identities differ "
        "from frozen scientific environment"
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
    "are bound to portable GitHub-hosted infrastructure only; "
    "NCBI reconstruction manifest is checksum-authenticated "
    "against the frozen scientific environment"
)
