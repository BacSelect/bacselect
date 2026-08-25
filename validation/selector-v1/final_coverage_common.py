"""Shared prospective protocol for final selector-v1 coverage validation."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
from dataclasses import fields
from pathlib import Path

import numpy as np

from bacselect.metrics import (
    CoverageSummary,
    coverage_summary,
    nearest_panel_distances,
)
from bacselect.ops import ops_ladder
from bacselect.sr import sr_ladder

from final_geometry_common import (
    EXPECTED_GENOMES,
    EXPECTED_SPECIES,
    FinalFoundation,
    load_final_foundation,
)


PANEL_SIZES = (
    10,
    20,
    50,
    100,
    200,
    500,
)
MAX_N = max(PANEL_SIZES)

METRIC_NAMES = tuple(
    field.name
    for field in fields(CoverageSummary)
)

PRIMARY_METRIC = "weighted_p95"

EXPECTED_BASELINE_SUMMARY_SHA256 = (
    "e5181e9c0dcd729553c3f357034a4c58"
    "b7e620334adeef8db9fdb89b83fdeb06"
)

BASELINE_SUMMARY_PATH = Path(
    "validation/selector-v1/results/"
    "final300-2400-geometry-baselines-summary.json"
)

EXPECTED_OPS_LADDER_SHA256 = (
    "ab5d75b2d35b9577bcf84acceb8e10d8"
    "47e983e04a8e4aa5859fd0bde1ae2834"
)

EXPECTED_SR_LADDER_SHA256 = (
    "080cbaf23d9259610d59fc1ef5a316432"
    "9e0bbbe9016b21590c0b34ad2da1b97"
)

EXPECTED_RANDOM_LADDER_SET_SHA256 = (
    "9394a26ded92fb2baafea0101b837335"
    "e9d434f4cd3d8c6484ef61bbf0741719"
)

EXPECTED_ENV_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207eae"
    "f5c2435e1b6feeddc1e4654686bc2a8c"
)

ENV_LOCK = Path(
    "envs/bacselect-dev-linux-64.lock"
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)


def file_sha256(path: Path) -> str:
    """Return streaming SHA256 for one file."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def text_sha256(text: str) -> str:
    """Return SHA256 for deterministic UTF-8 text."""
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def git_stdout(
    repo: Path,
    *args: str,
) -> str:
    """Return stripped stdout for one Git command."""
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return completed.stdout.strip()


def verify_repository(repo: Path) -> str:
    """Require clean HEAD == origin/main == explicit full commit."""
    expected = os.environ.get(
        "BACSELECT_EXPECTED_COMMIT",
        "",
    )

    if not COMMIT_RE.fullmatch(expected):
        raise AssertionError(
            "BACSELECT_EXPECTED_COMMIT must be the "
            "full 40-character analysis commit"
        )

    head = git_stdout(
        repo,
        "rev-parse",
        "HEAD",
    )
    origin = git_stdout(
        repo,
        "rev-parse",
        "origin/main",
    )
    status = git_stdout(
        repo,
        "status",
        "--porcelain",
    )

    if head != expected:
        raise AssertionError(
            "HEAD does not match "
            "BACSELECT_EXPECTED_COMMIT"
        )

    if origin != expected:
        raise AssertionError(
            "origin/main does not match "
            "BACSELECT_EXPECTED_COMMIT"
        )

    if status:
        raise AssertionError(
            "BacSelect working tree is not clean"
        )

    return expected


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    """Require one exact SHA256."""
    if not path.is_file():
        raise AssertionError(
            f"{label} missing: {path}"
        )

    observed = file_sha256(path)

    if observed != expected:
        raise AssertionError(
            f"{label} SHA256 changed: "
            f"expected {expected}, observed {observed}"
        )

    return observed


def verify_protocol_inputs() -> dict[str, object]:
    """Verify frozen geometry baseline and software environment."""
    require_sha256(
        BASELINE_SUMMARY_PATH,
        EXPECTED_BASELINE_SUMMARY_SHA256,
        "final geometry baseline summary",
    )

    summary = json.loads(
        BASELINE_SUMMARY_PATH.read_text(
            encoding="utf-8"
        )
    )

    if summary.get("analysis") != (
        "selector-v1-final-300-2400-"
        "geometry-baselines"
    ):
        raise AssertionError(
            "geometry baseline analysis identity changed"
        )

    if summary.get(
        "coverage_decision_evaluated"
    ) is not False:
        raise AssertionError(
            "baseline unexpectedly contains "
            "a coverage decision"
        )

    if summary.get("genomes") != EXPECTED_GENOMES:
        raise AssertionError(
            "baseline genome count changed"
        )

    if summary.get("species") != EXPECTED_SPECIES:
        raise AssertionError(
            "baseline species count changed"
        )

    if (
        summary["ops"]["ladder_sha256"]
        != EXPECTED_OPS_LADDER_SHA256
    ):
        raise AssertionError(
            "frozen OPS ladder identity changed"
        )

    if (
        summary["sr"]["ladder_sha256"]
        != EXPECTED_SR_LADDER_SHA256
    ):
        raise AssertionError(
            "frozen SR ladder identity changed"
        )

    if (
        summary["random"]["ladder_set_sha256"]
        != EXPECTED_RANDOM_LADDER_SET_SHA256
    ):
        raise AssertionError(
            "frozen random ladder identity changed"
        )

    require_sha256(
        ENV_LOCK,
        EXPECTED_ENV_LOCK_SHA256,
        "bacselect-dev environment lock",
    )

    return summary


def sequence_sha256(
    namespace: str,
    values: list[str],
) -> str:
    """Return deterministic fingerprint of an ordered accession sequence."""
    payload = (
        namespace
        + "\n"
        + "\n".join(values)
        + "\n"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def validate_ladder_hash(
    selector: str,
    ladder: np.ndarray,
    accessions: list[str],
    expected_hash: str,
) -> str:
    """Require one candidate ladder to match its frozen identity."""
    values = [
        accessions[int(index)]
        for index in ladder
    ]

    observed = sequence_sha256(
        (
            "BacSelect-selector-v1|"
            f"{selector}|ladder|N=500"
        ),
        values,
    )

    if observed != expected_hash:
        raise AssertionError(
            f"{selector} ladder fingerprint changed: "
            f"expected {expected_hash}, observed {observed}"
        )

    return observed


def load_verified_final_foundation() -> FinalFoundation:
    """Load final geometry and verify frozen selector ladders."""
    verify_protocol_inputs()

    foundation = load_final_foundation(
        recompute_coordinates=True,
    )

    ops = ops_ladder(
        foundation.coordinates,
        foundation.species_ids,
        foundation.accessions,
        max_n=MAX_N,
    )

    validate_ladder_hash(
        "OPS",
        ops,
        foundation.accessions,
        EXPECTED_OPS_LADDER_SHA256,
    )

    sr = sr_ladder(
        foundation.coordinates,
        foundation.species_ids,
        foundation.accessions,
        max_n=MAX_N,
    )

    validate_ladder_hash(
        "SR",
        sr,
        foundation.accessions,
        EXPECTED_SR_LADDER_SHA256,
    )

    return foundation


def candidate_ladders(
    foundation: FinalFoundation,
) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct and verify the frozen OPS and SR ladders."""
    ops = ops_ladder(
        foundation.coordinates,
        foundation.species_ids,
        foundation.accessions,
        max_n=MAX_N,
    )

    validate_ladder_hash(
        "OPS",
        ops,
        foundation.accessions,
        EXPECTED_OPS_LADDER_SHA256,
    )

    sr = sr_ladder(
        foundation.coordinates,
        foundation.species_ids,
        foundation.accessions,
        max_n=MAX_N,
    )

    validate_ladder_hash(
        "SR",
        sr,
        foundation.accessions,
        EXPECTED_SR_LADDER_SHA256,
    )

    return ops, sr


def evaluate_ladder(
    coordinates: np.ndarray,
    species_ids: list[str],
    ladder: np.ndarray,
) -> dict[int, CoverageSummary]:
    """Calculate all pre-specified coverage metrics at each frozen N."""
    summaries: dict[
        int,
        CoverageSummary,
    ] = {}

    for panel_size in PANEL_SIZES:
        distances = nearest_panel_distances(
            coordinates,
            ladder[:panel_size],
        )

        summaries[panel_size] = coverage_summary(
            distances,
            species_ids,
        )

    return summaries


def format_metric(value: float) -> str:
    """Return deterministic high-precision binary64 text."""
    return format(
        float(value),
        ".17g",
    )


def primary_status(
    winners: list[str],
) -> tuple[str, str | None]:
    """Apply only the prospectively frozen primary automatic-winner rule."""
    expected_count = len(PANEL_SIZES)

    if len(winners) != expected_count:
        raise AssertionError(
            "primary winner count changed"
        )

    allowed = {
        "OPS",
        "SR",
        "TIE",
    }

    if any(
        winner not in allowed
        for winner in winners
    ):
        raise AssertionError(
            "invalid primary winner label"
        )

    if all(
        winner == "OPS"
        for winner in winners
    ):
        return (
            "OPS_LOWER_AT_ALL_SIX_N",
            "OPS",
        )

    if all(
        winner == "SR"
        for winner in winners
    ):
        return (
            "SR_LOWER_AT_ALL_SIX_N",
            "SR",
        )

    if all(
        winner == "TIE"
        for winner in winners
    ):
        return (
            "PRIMARY_TIE_AT_ALL_SIX_N",
            None,
        )

    return (
        "PRIMARY_CURVES_NOT_UNIFORMLY_ORDERED",
        None,
    )


def write_hash_manifest(
    paths: list[Path],
    manifest_path: Path,
) -> None:
    """Write SHA256 manifest using basenames only."""
    lines = [
        (
            f"{file_sha256(path)}  "
            f"{path.name}"
        )
        for path in paths
    ]

    manifest_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def verify_hash_manifest(
    manifest_path: Path,
) -> dict[str, str]:
    """Verify a local basename-based SHA256 manifest."""
    result: dict[str, str] = {}
    root = manifest_path.parent

    with manifest_path.open(
        encoding="utf-8"
    ) as handle:
        for line_number, raw in enumerate(
            handle,
            start=1,
        ):
            line = raw.rstrip("\n")

            if not line:
                continue

            try:
                expected, name = line.split(
                    "  ",
                    1,
                )
            except ValueError as exc:
                raise AssertionError(
                    "invalid SHA256 manifest row "
                    f"{line_number}"
                ) from exc

            path = root / name
            observed = require_sha256(
                path,
                expected,
                f"manifest artifact {name}",
            )

            result[name] = observed

    if not result:
        raise AssertionError(
            "SHA256 manifest is empty"
        )

    return result


def read_tsv(
    path: Path,
) -> list[dict[str, str]]:
    """Read one tab-separated table."""
    with path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        return list(
            csv.DictReader(
                handle,
                delimiter="\t",
            )
        )
