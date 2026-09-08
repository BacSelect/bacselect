#!/usr/bin/env python3
"""Monthly Stage 14 public panels and structural coverage for BacSelect.

Stage 14 consumes only already-closed monthly authorities:

- Stage 11 species-balanced percentile geometry;
- Stage 12 current species representatives;
- Stage 13 complete OPS ladder.

Preset panels are exact Stage 13 prefixes at N=10,20,50,100,200,500.
OPS is never rerun.

Structural coverage is evaluated over the current Stage 12 representative
population with the frozen BacSelect nearest-panel Euclidean-distance and
coverage-summary implementation.

This is a monthly serializer. It deliberately does not reuse the historical
reference-panel summary/provenance serializer, whose scientific identity and
``monthly_release_assigned`` semantics are specific to the frozen validation
reference panel.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Callable, Mapping

import numpy as np
import numpy.typing as npt

from bacselect.metrics import (
    CoverageSummary,
    coverage_summary,
    nearest_panel_distances,
)
from bacselect.official_panels import (
    MEMBERSHIP_MANIFEST_FILENAME,
    PANEL_FILENAMES,
    PANEL_SIZES,
    serialize_custom_accession_list,
    serialize_membership_manifest,
)


RELEASE_ID = "2026.09"

SOURCE_SNAPSHOT_ID = (
    "bacselect-source-2026.09-20260901T021652Z"
)

REMOTE_BRANCH = (
    "origin/recovery/monthly-missing-datasets-gbff"
)

STAGE13_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_ops_ladder.py"
)

EXPECTED_STAGE13_WRAPPER_SHA256 = (
    "37fba1ac5ab938137b5d95e812e4335f"
    "2b572964d80a10bfacf962fb8986440f"
)

EXPECTED_STAGE13_EXECUTION_COMMIT = (
    "5357e28a6bc154126619010fdc508f6ccf39846d"
)

EXPECTED_STAGE13_TABLE_SHA256 = (
    "4600ad608082540d7ff129878fbc757e"
    "9e9f1abc4c0a3be9cb9d766ec0e0031d"
)

EXPECTED_STAGE13_RECORD_SHA256 = (
    "aa84576798375289049e3eb05594124d"
    "429985b60c08433e34199af93631281b"
)

EXPECTED_STAGE13_COMPLETION_SHA256 = (
    "507a6c7a02bddab4edc1d69808a47a9e"
    "d820f4225b1b7e61b08eb5cf85eeb98d"
)

EXPECTED_COMPLETE_LADDER_SHA256 = (
    "a220059087527c3e722e628814175202"
    "01f3fcd384a809138328dc29e80be7f0"
)

EXPECTED_REPRESENTATIVE_MEMBERSHIP_SHA256 = (
    "bbeb032ba83561d4b02c1ec582691ec9"
    "aab690828b2e23def9a5be679cf70052"
)

EXPECTED_N500_PREFIX_SHA256 = (
    "77611f2200983ab5c25498f2260c7528"
    "822bcbe6b330695c26a9c400348636f9"
)

EXPECTED_REPRESENTATIVE_COUNT = 16223
EXPECTED_FEATURE_COUNT = 12

EXPECTED_PANEL_ACCESSION_LIST_SHA256: Mapping[int, str] = {
    10:
        "1f9e6c91ffc98d318e7d945acb5b039b02e9486150238f535be937a633317305",
    20:
        "78382b9e360219f35d588b2691fdc0c6d4a767492d340558a0544cd43e7008eb",
    50:
        "c1551a37399362d79a33a06ca277dcfe9f920b375bf69a4342b9e3e749cc4a2b",
    100:
        "e089b4796a24f6b1375d4ffe830cd621f5ac99d68f5136a054554af1397c16c5",
    200:
        "e3e491dbb3f8feb06ceb8431fe6f109a77ae541531d5d615343bcb01e84a2385",
    500:
        "6b566648d9fe4fe37f4bcc0e480c787ff0cb1e7b64134871370f675c19c735c1",
}

EXPECTED_METRICS_SHA256 = (
    "c83219404c627c71c900aafbb165e0a8"
    "dead27f3f04f073dbb7ce86437bb3af2"
)

EXPECTED_METRICS_TEST_SHA256 = (
    "80b4a8f111af9c1ebd739fd99adfb9a6"
    "b656e014bf5239f767f73ae599b036ad"
)

EXPECTED_OFFICIAL_PANELS_SHA256 = (
    "01859f21d7d8653e8ff671f1c5d74a94"
    "69a251470258d742edc9b09c14448356"
)

EXPECTED_OFFICIAL_PANELS_TEST_SHA256 = (
    "491f0f0ee237583c04ef3357ad7b9118"
    "ae1cc028fde8f2ce49748224dfcbbecc"
)

EXPECTED_FINAL_COVERAGE_COMMON_SHA256 = (
    "c5f10b13158704d25e9bf48988695b17"
    "20ad776871869adfeb542919e23ed808"
)

EXPECTED_ENVIRONMENT_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207eae"
    "f5c2435e1b6feeddc1e4654686bc2a8c"
)

FROZEN_REPO_FILES: Mapping[str, str] = {
    str(STAGE13_WRAPPER_RELATIVE):
        EXPECTED_STAGE13_WRAPPER_SHA256,
    "src/bacselect/metrics.py":
        EXPECTED_METRICS_SHA256,
    "tests/test_metrics.py":
        EXPECTED_METRICS_TEST_SHA256,
    "src/bacselect/official_panels.py":
        EXPECTED_OFFICIAL_PANELS_SHA256,
    "tests/test_official_panels.py":
        EXPECTED_OFFICIAL_PANELS_TEST_SHA256,
    "validation/selector-v1/final_coverage_common.py":
        EXPECTED_FINAL_COVERAGE_COMMON_SHA256,
    "envs/bacselect-dev-linux-64.lock":
        EXPECTED_ENVIRONMENT_LOCK_SHA256,
}

STAGE_NAME = "public-panels-and-coverage"
PARTIAL_NAME = "public-panels-and-coverage.partial"

COVERAGE_SUMMARY_NAME = (
    "structural-coverage-summary.tsv"
)

COVERAGE_DISTANCES_NAME = (
    "structural-coverage-distances.tsv"
)

RECORD_NAME = (
    "monthly-public-panels-coverage-record.json"
)

COMPLETION_NAME = (
    "public-panels-and-coverage-completion-v1.json"
)

COMPLETION_TEMP_NAME = (
    "public-panels-and-coverage-completion-v1.json.partial"
)

RECORD_SCHEMA = (
    "bacselect-monthly-public-panels-coverage-record-v1"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-public-panels-coverage-completion-v1"
)

STATUS = (
    "MONTHLY_PUBLIC_PANELS_AND_COVERAGE_COMPLETE"
)

METRIC_NAMES = tuple(
    field.name
    for field in fields(
        CoverageSummary
    )
)

SCIENTIFIC_ARTIFACT_NAMES = (
    *(
        PANEL_FILENAMES[
            panel_size
        ]
        for panel_size in PANEL_SIZES
    ),
    MEMBERSHIP_MANIFEST_FILENAME,
    COVERAGE_SUMMARY_NAME,
    COVERAGE_DISTANCES_NAME,
)

STAGE_FILES = frozenset(
    (
        *SCIENTIFIC_ARTIFACT_NAMES,
        RECORD_NAME,
    )
)

_GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

_TAXID_RE = re.compile(
    r"^[1-9][0-9]*$"
)

_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_SHA_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class MonthlyPublicPanelsCoverageError(
    RuntimeError
):
    """Raised when monthly Stage 14 fails closed."""


@dataclass(frozen=True)
class Stage11Authority:
    accessions: tuple[str, ...]
    species_ids: tuple[str, ...]
    coordinates: npt.NDArray[np.float64]


@dataclass(frozen=True)
class Stage12Authority:
    species_ids: tuple[str, ...]
    accessions: tuple[str, ...]


@dataclass(frozen=True)
class Stage13Authority:
    species_ids: tuple[str, ...]
    accessions: tuple[str, ...]


@dataclass(frozen=True)
class RepresentativeGeometry:
    species_ids: tuple[str, ...]
    accessions: tuple[str, ...]
    coordinates: npt.NDArray[np.float64]


@dataclass(frozen=True)
class Stage14Build:
    artifacts: Mapping[str, bytes]
    summaries: Mapping[int, CoverageSummary]
    panel_sha256: Mapping[int, str]


@dataclass(frozen=True)
class MonthlyStage14ExecutionResult:
    stage_path: Path
    completion_path: Path
    artifact_sha256: Mapping[str, str]
    record_sha256: str
    completion_sha256: str


def sha256_bytes(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def _canonical_json(
    payload: Mapping[str, object],
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def format_binary64(
    value: float,
) -> str:
    observed = float(value)

    if not np.isfinite(
        observed
    ):
        raise MonthlyPublicPanelsCoverageError(
            "coverage value is not finite"
        )

    return format(
        observed,
        ".17g",
    )


def _git(
    repo: Path,
    *args: str,
) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    resolved = Path(path).resolve()

    if (
        not resolved.is_dir()
        or resolved.is_symlink()
    ):
        raise MonthlyPublicPanelsCoverageError(
            f"{label} is not a real directory: {resolved}"
        )

    return resolved


def _require_sha(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA_RE.fullmatch(
            value
        ) is None
    ):
        raise MonthlyPublicPanelsCoverageError(
            f"{label} is not a lowercase SHA256"
        )

    return value


def _require_artifact(
    path: Path,
    expected_sha256: str,
    *,
    label: str,
) -> None:
    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise MonthlyPublicPanelsCoverageError(
            f"{label} missing: {path}"
        )

    if sha256_file(
        path
    ) != expected_sha256:
        raise MonthlyPublicPanelsCoverageError(
            f"{label} SHA256 changed"
        )


def _load_json(
    path: Path,
    *,
    label: str,
) -> Mapping[str, object]:
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise MonthlyPublicPanelsCoverageError(
            f"cannot parse {label}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise MonthlyPublicPanelsCoverageError(
            f"{label} must be a JSON object"
        )

    return payload


def repository_preflight(
    repo: Path,
    *,
    execution_commit: str,
) -> Path:
    root = _require_real_directory(
        repo,
        label="repository",
    )

    if _COMMIT_RE.fullmatch(
        execution_commit
    ) is None:
        raise MonthlyPublicPanelsCoverageError(
            "Stage 14 execution commit is malformed"
        )

    if _git(
        root,
        "rev-parse",
        "HEAD",
    ) != execution_commit:
        raise MonthlyPublicPanelsCoverageError(
            "repository HEAD differs from Stage 14 execution commit"
        )

    if _git(
        root,
        "rev-parse",
        REMOTE_BRANCH,
    ) != execution_commit:
        raise MonthlyPublicPanelsCoverageError(
            "remote Stage 14 branch differs from execution commit"
        )

    if _git(
        root,
        "status",
        "--porcelain",
    ):
        raise MonthlyPublicPanelsCoverageError(
            "repository working tree is not clean"
        )

    return root


def verify_frozen_dependencies(
    repo: Path,
) -> Mapping[str, str]:
    observed: dict[str, str] = {}

    for relative, expected in (
        FROZEN_REPO_FILES.items()
    ):
        path = repo / relative

        if (
            not path.is_file()
            or path.is_symlink()
        ):
            raise MonthlyPublicPanelsCoverageError(
                f"frozen Stage 14 dependency missing: {relative}"
            )

        digest = sha256_file(
            path
        )

        if digest != expected:
            raise MonthlyPublicPanelsCoverageError(
                f"frozen Stage 14 dependency changed: {relative}"
            )

        observed[
            relative
        ] = digest

    return dict(
        sorted(
            observed.items()
        )
    )


def _load_module(
    path: Path,
    name: str,
) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise MonthlyPublicPanelsCoverageError(
            f"cannot construct module import: {path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        name
    ] = module

    try:
        spec.loader.exec_module(
            module
        )
    except Exception:
        sys.modules.pop(
            name,
            None,
        )

        raise

    return module


def load_stage13_wrapper(
    repo: Path,
) -> ModuleType:
    path = (
        repo
        / STAGE13_WRAPPER_RELATIVE
    )

    _require_artifact(
        path,
        EXPECTED_STAGE13_WRAPPER_SHA256,
        label="frozen Stage 13 wrapper",
    )

    return _load_module(
        path,
        "_bacselect_monthly_stage13_for_stage14",
    )


def authenticate_stage11_and_stage12(
    repo: Path,
    stage1_root: Path,
) -> tuple[
    Stage11Authority,
    Stage12Authority,
]:
    stage13 = load_stage13_wrapper(
        repo
    )

    upstream11 = (
        stage13
        .authenticate_stage11(
            stage1_root
        )
    )

    upstream12 = (
        stage13
        .authenticate_stage12(
            stage1_root
        )
    )

    return (
        Stage11Authority(
            accessions=tuple(
                upstream11.accessions
            ),
            species_ids=tuple(
                upstream11.species_ids
            ),
            coordinates=np.asarray(
                upstream11.coordinates,
                dtype=np.float64,
            ),
        ),
        Stage12Authority(
            species_ids=tuple(
                upstream12.species_ids
            ),
            accessions=tuple(
                upstream12.accessions
            ),
        ),
    )


def authenticate_stage13(
    repo: Path,
    stage1_root: Path,
) -> Stage13Authority:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    stage = (
        stage1
        / "ops-ladder"
    )

    table_path = (
        stage
        / "complete-ops-ladder.tsv"
    )

    record_path = (
        stage
        / "monthly-ops-ladder-record.json"
    )

    completion_path = (
        stage1
        / "ops-ladder-completion-v1.json"
    )

    _require_artifact(
        table_path,
        EXPECTED_STAGE13_TABLE_SHA256,
        label="Stage 13 ladder table",
    )

    _require_artifact(
        record_path,
        EXPECTED_STAGE13_RECORD_SHA256,
        label="Stage 13 record",
    )

    _require_artifact(
        completion_path,
        EXPECTED_STAGE13_COMPLETION_SHA256,
        label="Stage 13 completion",
    )

    record = _load_json(
        record_path,
        label="Stage 13 record",
    )

    completion = _load_json(
        completion_path,
        label="Stage 13 completion",
    )

    expected = {
        "status":
            "MONTHLY_COMPLETE_OPS_LADDER_COMPLETE",
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "execution_commit":
            EXPECTED_STAGE13_EXECUTION_COMMIT,
        "representative_count":
            EXPECTED_REPRESENTATIVE_COUNT,
        "ladder_count":
            EXPECTED_REPRESENTATIVE_COUNT,
        "complete_ladder_sha256":
            EXPECTED_COMPLETE_LADDER_SHA256,
        "ladder_membership_sha256":
            EXPECTED_REPRESENTATIVE_MEMBERSHIP_SHA256,
        "n500_prefix_sha256":
            EXPECTED_N500_PREFIX_SHA256,
        "ladder_table_sha256":
            EXPECTED_STAGE13_TABLE_SHA256,
    }

    for key, value in expected.items():
        if record.get(
            key
        ) != value:
            raise MonthlyPublicPanelsCoverageError(
                f"Stage 13 record {key} mismatch"
            )

        if completion.get(
            key
        ) != value:
            raise MonthlyPublicPanelsCoverageError(
                f"Stage 13 completion {key} mismatch"
            )

    stage13 = load_stage13_wrapper(
        repo
    )

    (
        ranks,
        species_ids,
        accessions,
    ) = stage13.parse_ladder_table(
        table_path.read_bytes()
    )

    if ranks != tuple(
        range(
            1,
            EXPECTED_REPRESENTATIVE_COUNT + 1,
        )
    ):
        raise MonthlyPublicPanelsCoverageError(
            "Stage 13 ladder ranks changed"
        )

    if len(
        accessions
    ) != EXPECTED_REPRESENTATIVE_COUNT:
        raise MonthlyPublicPanelsCoverageError(
            "Stage 13 ladder count changed"
        )

    if len(
        set(
            accessions
        )
    ) != EXPECTED_REPRESENTATIVE_COUNT:
        raise MonthlyPublicPanelsCoverageError(
            "Stage 13 ladder contains duplicate accessions"
        )

    if len(
        set(
            species_ids
        )
    ) != EXPECTED_REPRESENTATIVE_COUNT:
        raise MonthlyPublicPanelsCoverageError(
            "Stage 13 ladder contains duplicate species"
        )

    if (
        stage13.sequence_sha256(
            stage13.ladder_namespace(
                EXPECTED_REPRESENTATIVE_COUNT
            ),
            accessions,
        )
        != EXPECTED_COMPLETE_LADDER_SHA256
    ):
        raise MonthlyPublicPanelsCoverageError(
            "Stage 13 complete ladder identity changed"
        )

    if (
        stage13.sequence_sha256(
            stage13.ladder_namespace(500),
            accessions[:500],
        )
        != EXPECTED_N500_PREFIX_SHA256
    ):
        raise MonthlyPublicPanelsCoverageError(
            "Stage 13 N=500 prefix identity changed"
        )

    return Stage13Authority(
        species_ids=species_ids,
        accessions=accessions,
    )


def build_representative_geometry(
    stage11: Stage11Authority,
    stage12: Stage12Authority,
    stage13: Stage13Authority,
) -> RepresentativeGeometry:
    if len(
        stage12.accessions
    ) != EXPECTED_REPRESENTATIVE_COUNT:
        raise MonthlyPublicPanelsCoverageError(
            "Stage 12 representative count changed"
        )

    if len(
        set(
            stage12.accessions
        )
    ) != EXPECTED_REPRESENTATIVE_COUNT:
        raise MonthlyPublicPanelsCoverageError(
            "Stage 12 representatives are not unique"
        )

    if len(
        set(
            stage12.species_ids
        )
    ) != EXPECTED_REPRESENTATIVE_COUNT:
        raise MonthlyPublicPanelsCoverageError(
            "Stage 12 species are not unique"
        )

    if set(
        stage13.accessions
    ) != set(
        stage12.accessions
    ):
        raise MonthlyPublicPanelsCoverageError(
            "Stage 13 membership differs from Stage 12"
        )

    if set(
        stage13.species_ids
    ) != set(
        stage12.species_ids
    ):
        raise MonthlyPublicPanelsCoverageError(
            "Stage 13 species membership differs from Stage 12"
        )

    index_by_accession = {
        accession:
            index
        for index, accession
        in enumerate(
            stage11.accessions
        )
    }

    coordinates: list[
        npt.NDArray[np.float64]
    ] = []

    for species_taxid, accession in zip(
        stage12.species_ids,
        stage12.accessions,
        strict=True,
    ):
        try:
            index = index_by_accession[
                accession
            ]
        except KeyError as exc:
            raise MonthlyPublicPanelsCoverageError(
                "Stage 12 representative absent from Stage 11"
            ) from exc

        if (
            stage11.species_ids[
                index
            ]
            != species_taxid
        ):
            raise MonthlyPublicPanelsCoverageError(
                "Stage 12 representative species differs from Stage 11"
            )

        coordinates.append(
            stage11.coordinates[
                index
            ]
        )

    matrix = np.asarray(
        coordinates,
        dtype=np.float64,
    )

    if matrix.shape != (
        EXPECTED_REPRESENTATIVE_COUNT,
        EXPECTED_FEATURE_COUNT,
    ):
        raise MonthlyPublicPanelsCoverageError(
            "representative geometry shape changed"
        )

    if not np.all(
        np.isfinite(
            matrix
        )
    ):
        raise MonthlyPublicPanelsCoverageError(
            "representative geometry contains non-finite values"
        )

    return RepresentativeGeometry(
        species_ids=stage12.species_ids,
        accessions=stage12.accessions,
        coordinates=matrix,
    )


def build_panel_payloads(
    stage13: Stage13Authority,
) -> Mapping[int, bytes]:
    if len(
        stage13.accessions
    ) < 500:
        raise MonthlyPublicPanelsCoverageError(
            "fewer than 500 eligible representatives"
        )

    winning500 = (
        stage13.accessions[
            :500
        ]
    )

    result: dict[
        int,
        bytes,
    ] = {}

    for panel_size in PANEL_SIZES:
        payload = (
            serialize_custom_accession_list(
                winning500,
                panel_size,
            )
        )

        expected_sha = (
            EXPECTED_PANEL_ACCESSION_LIST_SHA256[
                panel_size
            ]
        )

        if sha256_bytes(
            payload
        ) != expected_sha:
            raise MonthlyPublicPanelsCoverageError(
                f"monthly panel N={panel_size} prefix bytes changed"
            )

        result[
            panel_size
        ] = payload

    return result


def evaluate_structural_coverage(
    geometry: RepresentativeGeometry,
    stage13: Stage13Authority,
) -> tuple[
    Mapping[int, npt.NDArray[np.float64]],
    Mapping[int, CoverageSummary],
]:
    local_index = {
        accession:
            index
        for index, accession
        in enumerate(
            geometry.accessions
        )
    }

    distances: dict[
        int,
        npt.NDArray[np.float64],
    ] = {}

    summaries: dict[
        int,
        CoverageSummary,
    ] = {}

    for panel_size in PANEL_SIZES:
        panel_accessions = (
            stage13.accessions[
                :panel_size
            ]
        )

        try:
            panel_indices = np.asarray(
                [
                    local_index[
                        accession
                    ]
                    for accession
                    in panel_accessions
                ],
                dtype=np.int64,
            )
        except KeyError as exc:
            raise MonthlyPublicPanelsCoverageError(
                "Stage 13 panel member absent from representative geometry"
            ) from exc

        observed = nearest_panel_distances(
            geometry.coordinates,
            panel_indices,
        )

        if observed.shape != (
            EXPECTED_REPRESENTATIVE_COUNT,
        ):
            raise MonthlyPublicPanelsCoverageError(
                f"coverage distance shape changed for N={panel_size}"
            )

        if not np.all(
            np.isfinite(
                observed
            )
        ):
            raise MonthlyPublicPanelsCoverageError(
                f"non-finite coverage distance for N={panel_size}"
            )

        if np.any(
            observed < 0.0
        ):
            raise MonthlyPublicPanelsCoverageError(
                f"negative coverage distance for N={panel_size}"
            )

        if not np.all(
            observed[
                panel_indices
            ]
            == 0.0
        ):
            raise MonthlyPublicPanelsCoverageError(
                f"panel members are not zero-distance at N={panel_size}"
            )

        distances[
            panel_size
        ] = observed

        summaries[
            panel_size
        ] = coverage_summary(
            observed,
            geometry.species_ids,
        )

    return (
        distances,
        summaries,
    )


def serialize_coverage_summary(
    summaries: Mapping[int, CoverageSummary],
    panel_payloads: Mapping[int, bytes],
) -> bytes:
    if set(
        summaries
    ) != set(
        PANEL_SIZES
    ):
        raise MonthlyPublicPanelsCoverageError(
            "coverage summaries do not contain exactly six preset panels"
        )

    if set(
        panel_payloads
    ) != set(
        PANEL_SIZES
    ):
        raise MonthlyPublicPanelsCoverageError(
            "panel payloads do not contain exactly six preset panels"
        )

    lines = [
        "\t".join(
            (
                "panel_size",
                "member_count",
                "accession_list_sha256",
                *METRIC_NAMES,
            )
        )
    ]

    for panel_size in PANEL_SIZES:
        summary = summaries[
            panel_size
        ]

        lines.append(
            "\t".join(
                (
                    str(
                        panel_size
                    ),
                    str(
                        panel_size
                    ),
                    sha256_bytes(
                        panel_payloads[
                            panel_size
                        ]
                    ),
                    *(
                        format_binary64(
                            getattr(
                                summary,
                                metric
                            )
                        )
                        for metric
                        in METRIC_NAMES
                    ),
                )
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode("ascii")


def serialize_coverage_distances(
    geometry: RepresentativeGeometry,
    distances: Mapping[
        int,
        npt.NDArray[np.float64],
    ],
) -> bytes:
    if set(
        distances
    ) != set(
        PANEL_SIZES
    ):
        raise MonthlyPublicPanelsCoverageError(
            "coverage distances do not contain exactly six preset panels"
        )

    for panel_size in PANEL_SIZES:
        if distances[
            panel_size
        ].shape != (
            EXPECTED_REPRESENTATIVE_COUNT,
        ):
            raise MonthlyPublicPanelsCoverageError(
                f"distance vector row count changed for N={panel_size}"
            )

    lines = [
        "\t".join(
            (
                "species_taxid",
                "canonical_genbank_assembly_accession",
                *(
                    f"nearest_distance_n{panel_size}"
                    for panel_size
                    in PANEL_SIZES
                ),
            )
        )
    ]

    for index, (
        species_taxid,
        accession,
    ) in enumerate(
        zip(
            geometry.species_ids,
            geometry.accessions,
            strict=True,
        )
    ):
        lines.append(
            "\t".join(
                (
                    species_taxid,
                    accession,
                    *(
                        format_binary64(
                            distances[
                                panel_size
                            ][
                                index
                            ]
                        )
                        for panel_size
                        in PANEL_SIZES
                    ),
                )
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode("ascii")


def build_stage14_artifacts(
    stage11: Stage11Authority,
    stage12: Stage12Authority,
    stage13: Stage13Authority,
) -> Stage14Build:
    geometry = (
        build_representative_geometry(
            stage11,
            stage12,
            stage13,
        )
    )

    panel_payloads = (
        build_panel_payloads(
            stage13
        )
    )

    (
        distances,
        summaries,
    ) = (
        evaluate_structural_coverage(
            geometry,
            stage13,
        )
    )

    artifacts: dict[
        str,
        bytes,
    ] = {}

    for panel_size in PANEL_SIZES:
        artifacts[
            PANEL_FILENAMES[
                panel_size
            ]
        ] = panel_payloads[
            panel_size
        ]

    artifacts[
        MEMBERSHIP_MANIFEST_FILENAME
    ] = serialize_membership_manifest(
        panel_payloads
    )

    artifacts[
        COVERAGE_SUMMARY_NAME
    ] = serialize_coverage_summary(
        summaries,
        panel_payloads,
    )

    artifacts[
        COVERAGE_DISTANCES_NAME
    ] = serialize_coverage_distances(
        geometry,
        distances,
    )

    if set(
        artifacts
    ) != set(
        SCIENTIFIC_ARTIFACT_NAMES
    ):
        raise MonthlyPublicPanelsCoverageError(
            "Stage 14 scientific artifact inventory changed"
        )

    panel_sha = {
        panel_size:
            sha256_bytes(
                panel_payloads[
                    panel_size
                ]
            )
        for panel_size
        in PANEL_SIZES
    }

    return Stage14Build(
        artifacts=dict(
            sorted(
                artifacts.items()
            )
        ),
        summaries=dict(
            summaries
        ),
        panel_sha256=panel_sha,
    )


def build_execution_record(
    *,
    execution_commit: str,
    build: Stage14Build,
) -> bytes:
    if _COMMIT_RE.fullmatch(
        execution_commit
    ) is None:
        raise MonthlyPublicPanelsCoverageError(
            "Stage 14 execution commit is malformed"
        )

    artifact_sha = {
        name:
            sha256_bytes(
                build.artifacts[
                    name
                ]
            )
        for name
        in sorted(
            build.artifacts
        )
    }

    required_metrics = {
        str(
            panel_size
        ): {
            "median_nearest_panel_distance":
                format_binary64(
                    build.summaries[
                        panel_size
                    ].weighted_median
                ),
            "p95_nearest_panel_distance":
                format_binary64(
                    build.summaries[
                        panel_size
                    ].weighted_p95
                ),
            "maximum_nearest_panel_distance":
                format_binary64(
                    build.summaries[
                        panel_size
                    ].unweighted_max
                ),
        }
        for panel_size
        in PANEL_SIZES
    }

    payload = {
        "schema_version":
            RECORD_SCHEMA,
        "status":
            STATUS,
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "execution_commit":
            execution_commit,
        "selector":
            "OPS",
        "selector_version":
            "1.0.0",
        "preset_panel_sizes":
            list(
                PANEL_SIZES
            ),
        "custom_n_min":
            10,
        "custom_n_max":
            500,
        "panel_definition":
            "complete_OPS_ladder[0:N]",
        "ops_rerun":
            False,
        "sr_executed":
            False,
        "ag_executed":
            False,
        "selector_resolution_rerun":
            False,
        "coverage_percentage_reported":
            False,
        "coverage_evaluation_population":
            "current_monthly_species_representatives",
        "coverage_population_count":
            EXPECTED_REPRESENTATIVE_COUNT,
        "coverage_distance":
            "euclidean_on_12_dimension_species_balanced_percentile_geometry",
        "stage13_table_sha256":
            EXPECTED_STAGE13_TABLE_SHA256,
        "stage13_record_sha256":
            EXPECTED_STAGE13_RECORD_SHA256,
        "stage13_completion_sha256":
            EXPECTED_STAGE13_COMPLETION_SHA256,
        "stage13_complete_ladder_sha256":
            EXPECTED_COMPLETE_LADDER_SHA256,
        "stage13_n500_prefix_sha256":
            EXPECTED_N500_PREFIX_SHA256,
        "stage13_membership_sha256":
            EXPECTED_REPRESENTATIVE_MEMBERSHIP_SHA256,
        "metrics_sha256":
            EXPECTED_METRICS_SHA256,
        "official_panels_sha256":
            EXPECTED_OFFICIAL_PANELS_SHA256,
        "environment_lock_sha256":
            EXPECTED_ENVIRONMENT_LOCK_SHA256,
        "panel_accession_list_sha256":
            {
                str(
                    panel_size
                ):
                    build.panel_sha256[
                        panel_size
                    ]
                for panel_size
                in PANEL_SIZES
            },
        "required_coverage_metrics":
            required_metrics,
        "scientific_artifact_sha256":
            artifact_sha,
        "release_packaging_generated":
            False,
    }

    return _canonical_json(
        payload
    )


def build_completion_receipt(
    *,
    execution_commit: str,
    build: Stage14Build,
    record_sha256: str,
) -> bytes:
    _require_sha(
        record_sha256,
        label="Stage 14 record SHA256",
    )

    artifact_sha = {
        name:
            sha256_bytes(
                build.artifacts[
                    name
                ]
            )
        for name
        in sorted(
            build.artifacts
        )
    }

    payload = {
        "schema_version":
            COMPLETION_SCHEMA,
        "status":
            STATUS,
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "execution_commit":
            execution_commit,
        "preset_panel_sizes":
            list(
                PANEL_SIZES
            ),
        "coverage_population_count":
            EXPECTED_REPRESENTATIVE_COUNT,
        "scientific_artifact_sha256":
            artifact_sha,
        "record_sha256":
            record_sha256,
    }

    return _canonical_json(
        payload
    )


def _fsync_directory(
    path: Path,
) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY,
    )

    try:
        os.fsync(
            descriptor
        )
    finally:
        os.close(
            descriptor
        )


def _write_fresh(
    path: Path,
    payload: bytes,
) -> None:
    if os.path.lexists(
        path
    ):
        raise MonthlyPublicPanelsCoverageError(
            f"refusing to overwrite existing artifact: {path}"
        )

    with path.open(
        "xb"
    ) as handle:
        handle.write(
            payload
        )
        handle.flush()
        os.fsync(
            handle.fileno()
        )


def publish_stage(
    *,
    stage1_root: Path,
    artifacts: Mapping[str, bytes],
    record_payload: bytes,
    stability_check: Callable[[], None],
) -> Path:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    final = (
        stage1
        / STAGE_NAME
    )

    partial = (
        stage1
        / PARTIAL_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlyPublicPanelsCoverageError(
            "canonical Stage 14 directory already exists"
        )

    if os.path.lexists(
        partial
    ):
        raise MonthlyPublicPanelsCoverageError(
            "partial Stage 14 directory already exists"
        )

    if set(
        artifacts
    ) != set(
        SCIENTIFIC_ARTIFACT_NAMES
    ):
        raise MonthlyPublicPanelsCoverageError(
            "Stage 14 publication artifact inventory changed"
        )

    partial.mkdir()

    for name in sorted(
        artifacts
    ):
        _write_fresh(
            partial / name,
            artifacts[
                name
            ],
        )

    _write_fresh(
        partial
        / RECORD_NAME,
        record_payload,
    )

    if {
        path.name
        for path in partial.iterdir()
    } != STAGE_FILES:
        raise MonthlyPublicPanelsCoverageError(
            "partial Stage 14 file inventory changed"
        )

    stability_check()

    _fsync_directory(
        partial
    )

    os.rename(
        partial,
        final,
    )

    _fsync_directory(
        stage1
    )

    return final


def publish_completion(
    *,
    stage1_root: Path,
    payload: bytes,
    stability_check: Callable[[], None],
) -> Path:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    final = (
        stage1
        / COMPLETION_NAME
    )

    temporary = (
        stage1
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlyPublicPanelsCoverageError(
            "Stage 14 completion already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlyPublicPanelsCoverageError(
            "Stage 14 completion temporary artifact already exists"
        )

    _write_fresh(
        temporary,
        payload,
    )

    stability_check()

    os.rename(
        temporary,
        final,
    )

    _fsync_directory(
        stage1
    )

    return final


def execute_monthly_public_panels_coverage(
    *,
    repo: Path,
    stage1_root: Path,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    stability_check: Callable[[], None] | None = None,
) -> MonthlyStage14ExecutionResult:
    root = repository_preflight(
        repo,
        execution_commit=execution_commit,
    )

    verify_frozen_dependencies(
        root
    )

    if release_id != RELEASE_ID:
        raise MonthlyPublicPanelsCoverageError(
            "unexpected monthly release ID"
        )

    if source_snapshot_id != SOURCE_SNAPSHOT_ID:
        raise MonthlyPublicPanelsCoverageError(
            "unexpected monthly source snapshot"
        )

    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    for path in (
        stage1 / STAGE_NAME,
        stage1 / PARTIAL_NAME,
        stage1 / COMPLETION_NAME,
        stage1 / COMPLETION_TEMP_NAME,
    ):
        if os.path.lexists(
            path
        ):
            raise MonthlyPublicPanelsCoverageError(
                f"Stage 14 output already exists: {path}"
            )

    (
        stage11,
        stage12,
    ) = authenticate_stage11_and_stage12(
        root,
        stage1,
    )

    stage13 = authenticate_stage13(
        root,
        stage1,
    )

    build = build_stage14_artifacts(
        stage11,
        stage12,
        stage13,
    )

    record_payload = (
        build_execution_record(
            execution_commit=execution_commit,
            build=build,
        )
    )

    record_sha = sha256_bytes(
        record_payload
    )

    completion_payload = (
        build_completion_receipt(
            execution_commit=execution_commit,
            build=build,
            record_sha256=record_sha,
        )
    )

    completion_sha = sha256_bytes(
        completion_payload
    )

    check = (
        stability_check
        if stability_check is not None
        else lambda: None
    )

    stage_path = publish_stage(
        stage1_root=stage1,
        artifacts=build.artifacts,
        record_payload=record_payload,
        stability_check=check,
    )

    completion_path = publish_completion(
        stage1_root=stage1,
        payload=completion_payload,
        stability_check=check,
    )

    return MonthlyStage14ExecutionResult(
        stage_path=stage_path,
        completion_path=completion_path,
        artifact_sha256={
            name:
                sha256_bytes(
                    payload
                )
            for name, payload
            in build.artifacts.items()
        },
        record_sha256=record_sha,
        completion_sha256=completion_sha,
    )
