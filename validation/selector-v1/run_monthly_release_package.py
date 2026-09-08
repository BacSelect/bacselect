#!/usr/bin/env python3
"""Deterministic monthly Stage 15 release-package execution boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from types import ModuleType
from typing import Any

from bacselect.monthly_release_package import (
    ARCHITECTURE_SCHEMA_VERSION,
    PANEL_SIZES,
    SELECTOR,
    SELECTOR_VERSION,
    EvidenceFile,
    PublicMetadataRow,
    audit_metadata_ladder,
    canonical_json_bytes,
    first_public_panel_n,
    metadata_ladder_filename,
    panel_filename,
    panel_identity,
    serialize_evidence_manifest,
    serialize_metadata_ladder,
    serialize_panel_accessions,
    serialize_panel_tsv,
    serialize_panel_xlsx,
    serialize_sha256sums,
)


RELEASE_ID = "2026.09"

SOURCE_SNAPSHOT_ID = (
    "bacselect-source-2026.09-"
    "20260901T021652Z"
)

SOURCE_PRODUCTION_COMMIT = (
    "abefc3b70d7fe7e079eeb52b762542dae565edf6"
)

REMOTE_BRANCH = (
    "origin/recovery/monthly-missing-datasets-gbff"
)

STAGE14_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_public_panels_coverage.py"
)

PACKAGE_MODULE_RELATIVE = Path(
    "src/bacselect/monthly_release_package.py"
)

PACKAGE_SCHEMA_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-release-package-v1.md"
)

EXPECTED_STAGE14_WRAPPER_SHA256 = (
    "2260728793419a5ed2f45f933c48239c21b246226942059dc33c9c3cb345a554"
)

EXPECTED_PACKAGE_MODULE_SHA256 = (
    "481f4b867c22fd6725570b0a99076d6355864db72a63e2302571724b09ace4ff"
)

EXPECTED_PACKAGE_SCHEMA_SHA256 = (
    "c7ca02ab09ba73ba6b8c08f9d678335efa15073c1252601a497f84dd2539df20"
)

EXPECTED_SOURCE_SNAPSHOT_RECORD_SHA256 = (
    "5ea9ef9e42d5eef63d69d66ffe2cfc8b57b9692fd3707375028df61eddd00e65"
)

EXPECTED_SOURCE_RAW_SHA256 = (
    "5f9fb970f2eac5d056a1dbb166c395f15b41312f4edecf3b7589f4e17e33bccb"
)

EXPECTED_TAXONOMY_ARCHIVE_SHA256 = (
    "b8faca2006a220dd0a44d7386fbec5240182c23e0b1af357aa9038e7a953e208"
)

EXPECTED_STAGE13_EXECUTION_COMMIT = (
    "5357e28a6bc154126619010fdc508f6ccf39846d"
)

EXPECTED_STAGE14_EXECUTION_COMMIT = (
    "ede5cafe41c85ae3a4d025a5c28b0e4d1f402e2f"
)

EXPECTED_STAGE13_TABLE_SHA256 = (
    "4600ad608082540d7ff129878fbc757e9e9f1abc4c0a3be9cb9d766ec0e0031d"
)

EXPECTED_STAGE13_RECORD_SHA256 = (
    "aa84576798375289049e3eb05594124d429985b60c08433e34199af93631281b"
)

EXPECTED_STAGE13_COMPLETION_SHA256 = (
    "507a6c7a02bddab4edc1d69808a47a9ed820f4225b1b7e61b08eb5cf85eeb98d"
)

EXPECTED_COMPLETE_LADDER_SHA256 = (
    "a220059087527c3e722e62881417520201f3fcd384a809138328dc29e80be7f0"
)

EXPECTED_STAGE14_RECORD_SHA256 = (
    "1bb45f2561f337acf0f638d4947f1854276ff66e2dcbf608d1f1c30324a24fee"
)

EXPECTED_STAGE14_COMPLETION_SHA256 = (
    "cb8053e958009e443730ed4255e00805d352c2db6db5f8482e1e85e8393d508e"
)

EXPECTED_STAGE14_ARTIFACT_SHA256: Mapping[str, str] = {
    "panel-membership-manifest.tsv":
        "8a97dac1fd58f21d5273b7046b94e97c04a744f7873777d16149ced8222eccd2",
    "panel-n10.txt":
        "1f9e6c91ffc98d318e7d945acb5b039b02e9486150238f535be937a633317305",
    "panel-n20.txt":
        "78382b9e360219f35d588b2691fdc0c6d4a767492d340558a0544cd43e7008eb",
    "panel-n50.txt":
        "c1551a37399362d79a33a06ca277dcfe9f920b375bf69a4342b9e3e749cc4a2b",
    "panel-n100.txt":
        "e089b4796a24f6b1375d4ffe830cd621f5ac99d68f5136a054554af1397c16c5",
    "panel-n200.txt":
        "e3e491dbb3f8feb06ceb8431fe6f109a77ae541531d5d615343bcb01e84a2385",
    "panel-n500.txt":
        "6b566648d9fe4fe37f4bcc0e480c787ff0cb1e7b64134871370f675c19c735c1",
    "structural-coverage-distances.tsv":
        "fd1a78600875b0eac601d897416a3601ccb6b8d6501720119397bd110bec15ae",
    "structural-coverage-summary.tsv":
        "4900a02daabe51895b92eb6f94411c9c0a10c20e259da0523e21e25d019925f0",
}

EXPECTED_PUBLIC_PANEL_SHA256: Mapping[int, str] = {
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

EXPECTED_COMPLETE_UNIVERSE_COUNT = 68164
EXPECTED_SPECIES_COUNT = 16223
EXPECTED_LADDER_COUNT = 16223
EXPECTED_PUBLIC_MAX = 500

STAGE_NAME = "release-package"
PARTIAL_NAME = "release-package.partial"

RECORD_NAME = (
    "monthly-release-package-record.json"
)

COMPLETION_NAME = (
    "release-package-completion-v1.json"
)

COMPLETION_TEMP_NAME = (
    "release-package-completion-v1.json.partial"
)

EVIDENCE_MANIFEST_NAME = (
    "release-evidence-manifest.tsv"
)

RELEASE_SUMMARY_NAME = (
    "release-summary.json"
)

RELEASE_PROVENANCE_NAME = (
    "release-provenance.json"
)

CHECKSUMS_NAME = "SHA256SUMS"

RECORD_SCHEMA = (
    "bacselect-monthly-release-package-record-v1"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-release-package-completion-v1"
)

RELEASE_SUMMARY_SCHEMA = (
    "bacselect-monthly-release-summary-v1"
)

RELEASE_PROVENANCE_SCHEMA = (
    "bacselect-monthly-release-provenance-v1"
)

STATUS = (
    "MONTHLY_RELEASE_PACKAGE_COMPLETE"
)

_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


PUBLIC_DOWNLOAD_NAMES = frozenset(
    {
        metadata_ladder_filename(
            RELEASE_ID
        ),
        *(
            panel_filename(
                RELEASE_ID,
                panel_size,
                suffix,
            )
            for panel_size in PANEL_SIZES
            for suffix in (
                "txt",
                "tsv",
                "xlsx",
            )
        ),
    }
)

COPIED_RELEASE_ARTIFACT_NAMES = frozenset({
    "panel-membership-manifest.tsv",
    "complete-ops-ladder.tsv",
    "monthly-ops-ladder-record.json",
    "structural-coverage-summary.tsv",
})

GENERATED_RELEASE_ARTIFACT_NAMES = frozenset({
    EVIDENCE_MANIFEST_NAME,
    RELEASE_SUMMARY_NAME,
    RELEASE_PROVENANCE_NAME,
    CHECKSUMS_NAME,
})

PACKAGE_ARTIFACT_NAMES = frozenset(
    PUBLIC_DOWNLOAD_NAMES
    | COPIED_RELEASE_ARTIFACT_NAMES
    | GENERATED_RELEASE_ARTIFACT_NAMES
)

STAGE_FILES = frozenset(
    PACKAGE_ARTIFACT_NAMES
    | {
        RECORD_NAME,
    }
)


EVIDENCE_FILE_SPECS = (
    (
        "source_snapshot_metadata",
        "source-snapshot-record.json",
    ),
    (
        "source_snapshot_metadata",
        "assembly_data_report.raw.jsonl",
    ),
    (
        "metadata_eligibility",
        (
            "metadata-eligibility/"
            "metadata-eligibility-assessments.jsonl"
        ),
    ),
    (
        "metadata_eligibility",
        "complete-universe/complete-universe.tsv",
    ),
    (
        "source_truth_eligibility",
        "source-truth/source-truth-decisions.tsv",
    ),
    (
        "source_truth_eligibility",
        "source-truth/source-truth-relations.tsv",
    ),
    (
        "biosample_reconciliation",
        (
            "biosample-reconciliation/"
            "biosample-reconciliation-decisions.tsv"
        ),
    ),
    (
        "chromosome_integrity_review",
        (
            "chromosome-integrity/"
            "chromosome-integrity-decisions.tsv"
        ),
    ),
    (
        "taxonomy_snapshot_identity",
        (
            "taxonomy-snapshot/"
            "monthly-taxonomy-snapshot-record.json"
        ),
    ),
    (
        "taxonomy_snapshot_identity",
        "taxonomy-snapshot/new_taxdump.tar.gz",
    ),
    (
        "taxonomy_snapshot_identity",
        (
            "taxonomy-snapshot/"
            "taxonomy-content-sha256.tsv"
        ),
    ),
    (
        "species_resolution",
        (
            "taxonomy-resolution/"
            "taxonomy-resolution-decisions.tsv"
        ),
    ),
    (
        "raw_structural_features",
        (
            "structural-features/"
            "structural-feature-matrix-300-2400.tsv"
        ),
    ),
    (
        "raw_structural_features",
        (
            "structural-features/"
            "structural-feature-provenance.tsv"
        ),
    ),
    (
        "percentile_geometry",
        (
            "percentile-geometry/"
            "species-balanced-percentile-feature-matrix-300-2400.tsv"
        ),
    ),
    (
        "species_representatives",
        (
            "species-representatives/"
            "species-representatives.tsv"
        ),
    ),
    (
        "complete_diversity_ladder",
        "ops-ladder/complete-ops-ladder.tsv",
    ),
    (
        "selector_trace",
        "ops-ladder/monthly-ops-ladder-record.json",
    ),
    (
        "public_panel_coverage",
        (
            "public-panels-and-coverage/"
            "structural-coverage-summary.tsv"
        ),
    ),
    (
        "public_panel_coverage",
        (
            "public-panels-and-coverage/"
            "structural-coverage-distances.tsv"
        ),
    ),
    (
        "public_panel_coverage",
        (
            "public-panels-and-coverage/"
            "monthly-public-panels-coverage-record.json"
        ),
    ),
)


class MonthlyReleaseExecutionError(
    RuntimeError
):
    """Raised when Stage 15 monthly release packaging fails closed."""


@dataclass(
    frozen=True,
)
class SourceAuthority:
    source_snapshot_record_sha256: str
    source_raw_sha256: str
    taxonomy_archive_sha256: str
    source_universe_count: int
    species_count: int


@dataclass(
    frozen=True,
)
class Stage14Authority:
    panel_payloads: Mapping[int, bytes]
    membership_manifest_payload: bytes
    coverage_summary_payload: bytes
    coverage_distances_payload: bytes
    record: Mapping[str, object]
    completion: Mapping[str, object]


@dataclass(
    frozen=True,
)
class Stage15Build:
    metadata_rows: tuple[
        PublicMetadataRow,
        ...,
    ]
    artifacts: Mapping[
        str,
        bytes,
    ]
    evidence_manifest_sha256: str
    metadata_ladder_sha256: str
    public_download_sha256: Mapping[
        str,
        str,
    ]


@dataclass(
    frozen=True,
)
class MonthlyStage15ExecutionResult:
    stage_path: Path
    completion_path: Path
    artifact_sha256: Mapping[
        str,
        str,
    ]
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

    with path.open(
        "rb"
    ) as handle:
        for block in iter(
            lambda: handle.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(
                block
            )

    return digest.hexdigest()


def _git(
    repo: Path,
    *args: str,
) -> str:
    return subprocess.run(
        (
            "git",
            *args,
        ),
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
    resolved = path.resolve()

    if (
        not resolved.is_dir()
        or resolved.is_symlink()
    ):
        raise MonthlyReleaseExecutionError(
            f"{label} must be a real directory"
        )

    return resolved


def _require_sha(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyReleaseExecutionError(
            f"{label} must be a lowercase SHA256"
        )

    return value


def _require_artifact(
    path: Path,
    expected_sha256: str,
    *,
    label: str,
) -> Path:
    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise MonthlyReleaseExecutionError(
            f"{label} is missing or not a regular file"
        )

    observed = sha256_file(
        path
    )

    if observed != expected_sha256:
        raise MonthlyReleaseExecutionError(
            f"{label} SHA256 changed: {observed}"
        )

    return path


def _load_json(
    path: Path,
    *,
    label: str,
) -> Mapping[
    str,
    object,
]:
    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise MonthlyReleaseExecutionError(
            f"cannot parse {label}"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise MonthlyReleaseExecutionError(
            f"{label} must be a JSON object"
        )

    return value


def repository_preflight(
    repo: Path,
    *,
    execution_commit: str,
) -> Path:
    root = _require_real_directory(
        repo,
        label="repository",
    )

    if (
        _COMMIT_RE.fullmatch(
            execution_commit
        )
        is None
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 15 execution commit is malformed"
        )

    if _git(
        root,
        "rev-parse",
        "HEAD",
    ) != execution_commit:
        raise MonthlyReleaseExecutionError(
            "repository HEAD differs from Stage 15 execution commit"
        )

    if _git(
        root,
        "rev-parse",
        REMOTE_BRANCH,
    ) != execution_commit:
        raise MonthlyReleaseExecutionError(
            "remote Stage 15 branch differs from execution commit"
        )

    if _git(
        root,
        "status",
        "--porcelain",
    ):
        raise MonthlyReleaseExecutionError(
            "repository working tree is not clean"
        )

    return root


def verify_frozen_dependencies(
    repo: Path,
) -> Mapping[
    str,
    str,
]:
    expected = {
        str(
            STAGE14_WRAPPER_RELATIVE
        ):
            EXPECTED_STAGE14_WRAPPER_SHA256,
        str(
            PACKAGE_MODULE_RELATIVE
        ):
            EXPECTED_PACKAGE_MODULE_SHA256,
        str(
            PACKAGE_SCHEMA_RELATIVE
        ):
            EXPECTED_PACKAGE_SCHEMA_SHA256,
    }

    observed = {}

    for relative, digest in expected.items():
        path = repo / relative

        _require_artifact(
            path,
            digest,
            label=(
                "frozen Stage 15 dependency "
                + relative
            ),
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
        raise MonthlyReleaseExecutionError(
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


def load_stage14_wrapper(
    repo: Path,
) -> ModuleType:
    path = (
        repo
        / STAGE14_WRAPPER_RELATIVE
    )

    _require_artifact(
        path,
        EXPECTED_STAGE14_WRAPPER_SHA256,
        label="frozen Stage 14 wrapper",
    )

    return _load_module(
        path,
        "_bacselect_monthly_stage14_for_stage15",
    )


def authenticate_source_authority(
    authority_root: Path,
) -> SourceAuthority:
    root = _require_real_directory(
        authority_root,
        label="monthly authority root",
    )

    source_record_path = (
        root
        / "source-snapshot-record.json"
    )

    _require_artifact(
        source_record_path,
        EXPECTED_SOURCE_SNAPSHOT_RECORD_SHA256,
        label="monthly source snapshot record",
    )

    source_record = _load_json(
        source_record_path,
        label="monthly source snapshot record",
    )

    expected_source = {
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "raw_response_sha256":
            EXPECTED_SOURCE_RAW_SHA256,
        "expected_git_commit":
            SOURCE_PRODUCTION_COMMIT,
        "status":
            "MONTHLY_SOURCE_SNAPSHOT_ACQUIRED",
    }

    for key, expected in (
        expected_source.items()
    ):
        if source_record.get(
            key
        ) != expected:
            raise MonthlyReleaseExecutionError(
                f"source snapshot record {key} mismatch"
            )

    raw_path = (
        root
        / "assembly_data_report.raw.jsonl"
    )

    if (
        not raw_path.is_file()
        or raw_path.is_symlink()
    ):
        raise MonthlyReleaseExecutionError(
            "raw monthly NCBI response is missing"
        )

    taxonomy_archive = (
        root
        / "taxonomy-snapshot"
        / "new_taxdump.tar.gz"
    )

    _require_artifact(
        taxonomy_archive,
        EXPECTED_TAXONOMY_ARCHIVE_SHA256,
        label="monthly taxonomy archive",
    )

    taxonomy_completion = _load_json(
        root
        / "taxonomy-snapshot-completion-v3.json",
        label="taxonomy completion",
    )

    for key, expected in {
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "taxonomy_archive_sha256":
            EXPECTED_TAXONOMY_ARCHIVE_SHA256,
        "status":
            "TAXONOMY_SNAPSHOT_EXECUTION_COMPLETE",
    }.items():
        if taxonomy_completion.get(
            key
        ) != expected:
            raise MonthlyReleaseExecutionError(
                f"taxonomy completion {key} mismatch"
            )

    universe_completion = _load_json(
        root
        / "complete-universe-completion-v1.json",
        label="complete-universe completion",
    )

    for key, expected in {
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "complete_universe_count":
            EXPECTED_COMPLETE_UNIVERSE_COUNT,
        "complete_universe_species_count":
            EXPECTED_SPECIES_COUNT,
        "status":
            "COMPLETE_UNIVERSE_EXECUTION_COMPLETE",
    }.items():
        if universe_completion.get(
            key
        ) != expected:
            raise MonthlyReleaseExecutionError(
                f"complete-universe completion {key} mismatch"
            )

    return SourceAuthority(
        source_snapshot_record_sha256=(
            EXPECTED_SOURCE_SNAPSHOT_RECORD_SHA256
        ),
        source_raw_sha256=(
            EXPECTED_SOURCE_RAW_SHA256
        ),
        taxonomy_archive_sha256=(
            EXPECTED_TAXONOMY_ARCHIVE_SHA256
        ),
        source_universe_count=(
            EXPECTED_COMPLETE_UNIVERSE_COUNT
        ),
        species_count=(
            EXPECTED_SPECIES_COUNT
        ),
    )


def authenticate_stage13(
    repo: Path,
    authority_root: Path,
) -> object:
    stage14 = load_stage14_wrapper(
        repo
    )

    stage13 = stage14.authenticate_stage13(
        repo,
        authority_root,
    )

    if len(
        stage13.accessions
    ) != EXPECTED_LADDER_COUNT:
        raise MonthlyReleaseExecutionError(
            "Stage 13 ladder count changed"
        )

    if len(
        stage13.species_ids
    ) != EXPECTED_LADDER_COUNT:
        raise MonthlyReleaseExecutionError(
            "Stage 13 species count changed"
        )

    return stage13


def authenticate_stage14(
    repo: Path,
    authority_root: Path,
) -> Stage14Authority:
    root = _require_real_directory(
        authority_root,
        label="monthly authority root",
    )

    stage14_wrapper = load_stage14_wrapper(
        repo
    )

    stage = (
        root
        / "public-panels-and-coverage"
    )

    if (
        not stage.is_dir()
        or stage.is_symlink()
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 14 directory is missing"
        )

    record_path = (
        stage
        / "monthly-public-panels-coverage-record.json"
    )

    completion_path = (
        root
        / "public-panels-and-coverage-completion-v1.json"
    )

    expected_stage_files = (
        set(
            EXPECTED_STAGE14_ARTIFACT_SHA256
        )
        | {
            record_path.name,
        }
    )

    observed_stage_files = {
        path.name
        for path in stage.iterdir()
    }

    if observed_stage_files != expected_stage_files:
        raise MonthlyReleaseExecutionError(
            "Stage 14 file inventory changed"
        )

    for name, expected_sha in (
        EXPECTED_STAGE14_ARTIFACT_SHA256.items()
    ):
        _require_artifact(
            stage / name,
            expected_sha,
            label=(
                "Stage 14 artifact "
                + name
            ),
        )

    _require_artifact(
        record_path,
        EXPECTED_STAGE14_RECORD_SHA256,
        label="Stage 14 execution record",
    )

    _require_artifact(
        completion_path,
        EXPECTED_STAGE14_COMPLETION_SHA256,
        label="Stage 14 completion",
    )

    record = _load_json(
        record_path,
        label="Stage 14 execution record",
    )

    completion = _load_json(
        completion_path,
        label="Stage 14 completion",
    )

    for payload, label in (
        (
            record,
            "Stage 14 record",
        ),
        (
            completion,
            "Stage 14 completion",
        ),
    ):
        for key, expected in {
            "release_id":
                RELEASE_ID,
            "source_snapshot_id":
                SOURCE_SNAPSHOT_ID,
            "execution_commit":
                EXPECTED_STAGE14_EXECUTION_COMMIT,
            "status":
                "MONTHLY_PUBLIC_PANELS_AND_COVERAGE_COMPLETE",
            "coverage_population_count":
                EXPECTED_SPECIES_COUNT,
        }.items():
            if payload.get(
                key
            ) != expected:
                raise MonthlyReleaseExecutionError(
                    f"{label} {key} mismatch"
                )

    if record.get(
        "stage13_table_sha256"
    ) != EXPECTED_STAGE13_TABLE_SHA256:
        raise MonthlyReleaseExecutionError(
            "Stage 14 Stage13 table binding changed"
        )

    if record.get(
        "stage13_record_sha256"
    ) != EXPECTED_STAGE13_RECORD_SHA256:
        raise MonthlyReleaseExecutionError(
            "Stage 14 Stage13 record binding changed"
        )

    if record.get(
        "stage13_completion_sha256"
    ) != EXPECTED_STAGE13_COMPLETION_SHA256:
        raise MonthlyReleaseExecutionError(
            "Stage 14 Stage13 completion binding changed"
        )

    if record.get(
        "stage13_complete_ladder_sha256"
    ) != EXPECTED_COMPLETE_LADDER_SHA256:
        raise MonthlyReleaseExecutionError(
            "Stage 14 complete ladder binding changed"
        )

    expected_scientific = dict(
        sorted(
            EXPECTED_STAGE14_ARTIFACT_SHA256.items()
        )
    )

    if record.get(
        "scientific_artifact_sha256"
    ) != expected_scientific:
        raise MonthlyReleaseExecutionError(
            "Stage 14 scientific artifact map changed"
        )

    if completion.get(
        "scientific_artifact_sha256"
    ) != expected_scientific:
        raise MonthlyReleaseExecutionError(
            "Stage 14 completion artifact map changed"
        )

    panel_payloads = {}

    for panel_size in PANEL_SIZES:
        name = (
            f"panel-n{panel_size}.txt"
        )

        payload = (
            stage
            / name
        ).read_bytes()

        if sha256_bytes(
            payload
        ) != EXPECTED_PUBLIC_PANEL_SHA256[
            panel_size
        ]:
            raise MonthlyReleaseExecutionError(
                f"Stage 14 N={panel_size} panel identity changed"
            )

        panel_payloads[
            panel_size
        ] = payload

    # Reuse the frozen parser/authentication path as an additional
    # upstream semantic check without recalculating OPS or coverage.
    stage13 = (
        stage14_wrapper
        .authenticate_stage13(
            repo,
            root,
        )
    )

    if tuple(
        stage13.accessions[
            :500
        ]
    ) != tuple(
        accession
        for panel_size in (
            500,
        )
        for accession in (
            panel_payloads[
                panel_size
            ]
            .decode(
                "ascii"
            )
            .splitlines()
        )
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 14 N=500 panel differs from Stage 13 prefix"
        )

    return Stage14Authority(
        panel_payloads=dict(
            panel_payloads
        ),
        membership_manifest_payload=(
            stage
            / "panel-membership-manifest.tsv"
        ).read_bytes(),
        coverage_summary_payload=(
            stage
            / "structural-coverage-summary.tsv"
        ).read_bytes(),
        coverage_distances_payload=(
            stage
            / "structural-coverage-distances.tsv"
        ).read_bytes(),
        record=record,
        completion=completion,
    )


def build_public_metadata_rows(
    authority_root: Path,
    stage13: object,
    source: SourceAuthority,
) -> tuple[
    PublicMetadataRow,
    ...,
]:
    root = _require_real_directory(
        authority_root,
        label="monthly authority root",
    )

    if len(
        stage13.accessions
    ) < EXPECTED_PUBLIC_MAX:
        raise MonthlyReleaseExecutionError(
            "Stage 13 contains fewer than 500 representatives"
        )

    selected_accessions = tuple(
        stage13.accessions[
            :EXPECTED_PUBLIC_MAX
        ]
    )

    selected_species = tuple(
        stage13.species_ids[
            :EXPECTED_PUBLIC_MAX
        ]
    )

    if len(
        set(
            selected_accessions
        )
    ) != EXPECTED_PUBLIC_MAX:
        raise MonthlyReleaseExecutionError(
            "public Stage 13 prefix contains duplicate accessions"
        )

    if len(
        set(
            selected_species
        )
    ) != EXPECTED_PUBLIC_MAX:
        raise MonthlyReleaseExecutionError(
            "public Stage 13 prefix contains duplicate species"
        )

    wanted = set(
        selected_accessions
    )

    raw_records: dict[
        str,
        Mapping[
            str,
            Any,
        ],
    ] = {}

    raw_seen: dict[
        str,
        int,
    ] = {}

    raw_digest = hashlib.sha256()

    raw_path = (
        root
        / "assembly_data_report.raw.jsonl"
    )

    with raw_path.open(
        "rb"
    ) as handle:
        for raw_line in handle:
            raw_digest.update(
                raw_line
            )

            if not raw_line.strip():
                continue

            try:
                value = json.loads(
                    raw_line.decode(
                        "utf-8"
                    )
                )
            except Exception as exc:
                raise MonthlyReleaseExecutionError(
                    "cannot parse raw monthly NCBI response"
                ) from exc

            if not isinstance(
                value,
                dict,
            ):
                raise MonthlyReleaseExecutionError(
                    "raw NCBI response row is not an object"
                )

            accession = value.get(
                "accession"
            )

            if accession not in wanted:
                continue

            raw_seen[
                accession
            ] = (
                raw_seen.get(
                    accession,
                    0,
                )
                + 1
            )

            raw_records.setdefault(
                accession,
                value,
            )

    observed_raw_sha = (
        raw_digest.hexdigest()
    )

    if (
        observed_raw_sha
        != source.source_raw_sha256
    ):
        raise MonthlyReleaseExecutionError(
            "raw monthly NCBI response SHA256 changed"
        )

    if set(
        raw_records
    ) != wanted:
        missing = sorted(
            wanted
            - set(
                raw_records
            )
        )

        raise MonthlyReleaseExecutionError(
            "selected accessions missing from raw source metadata: "
            + repr(
                missing[
                    :10
                ]
            )
        )

    if any(
        raw_seen.get(
            accession
        ) != 1
        for accession in wanted
    ):
        raise MonthlyReleaseExecutionError(
            "selected accession does not occur exactly once in raw source metadata"
        )

    wanted_species = set(
        selected_species
    )

    species_names: dict[
        str,
        str,
    ] = {}

    taxonomy_archive = (
        root
        / "taxonomy-snapshot"
        / "new_taxdump.tar.gz"
    )

    with tarfile.open(
        taxonomy_archive,
        mode="r:gz",
    ) as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.name.endswith(
                "names.dmp"
            )
        ]

        if len(
            members
        ) != 1:
            raise MonthlyReleaseExecutionError(
                "taxonomy archive names.dmp inventory changed"
            )

        stream = archive.extractfile(
            members[
                0
            ]
        )

        if stream is None:
            raise MonthlyReleaseExecutionError(
                "cannot read taxonomy names.dmp"
            )

        for raw in stream:
            try:
                line = raw.decode(
                    "utf-8"
                )
            except UnicodeDecodeError as exc:
                raise MonthlyReleaseExecutionError(
                    "taxonomy names.dmp is not UTF-8"
                ) from exc

            parts = [
                value.strip()
                for value in line.split(
                    "|"
                )
            ]

            if len(
                parts
            ) < 4:
                continue

            taxid = parts[
                0
            ]

            if taxid not in wanted_species:
                continue

            if parts[
                3
            ] != "scientific name":
                continue

            if taxid in species_names:
                raise MonthlyReleaseExecutionError(
                    "taxonomy contains duplicate scientific name for selected species"
                )

            species_names[
                taxid
            ] = parts[
                1
            ]

    if set(
        species_names
    ) != wanted_species:
        raise MonthlyReleaseExecutionError(
            "selected species scientific-name mapping is incomplete"
        )

    rows = []

    for rank, (
        accession,
        species_taxid,
    ) in enumerate(
        zip(
            selected_accessions,
            selected_species,
            strict=True,
        ),
        start=1,
    ):
        record = raw_records[
            accession
        ]

        assembly = record.get(
            "assembly_info"
        )

        organism = record.get(
            "organism"
        )

        if not isinstance(
            assembly,
            dict,
        ):
            raise MonthlyReleaseExecutionError(
                f"{accession}: assembly_info missing"
            )

        if not isinstance(
            organism,
            dict,
        ):
            raise MonthlyReleaseExecutionError(
                f"{accession}: organism missing"
            )

        biosample = assembly.get(
            "biosample"
        )

        if not isinstance(
            biosample,
            dict,
        ):
            raise MonthlyReleaseExecutionError(
                f"{accession}: BioSample metadata missing"
            )

        values = {
            "selection_rank":
                str(
                    rank
                ),
            "first_public_panel_n":
                str(
                    first_public_panel_n(
                        rank
                    )
                ),
            "genbank_assembly_accession":
                accession,
            "biosample_accession":
                biosample.get(
                    "accession"
                ),
            "ncbi_organism_name":
                organism.get(
                    "organism_name"
                ),
            "ncbi_organism_taxid":
                organism.get(
                    "tax_id"
                ),
            "bacselect_species_name":
                species_names[
                    species_taxid
                ],
            "bacselect_species_taxid":
                species_taxid,
            "assembly_name":
                assembly.get(
                    "assembly_name"
                ),
            "submitter":
                assembly.get(
                    "submitter"
                ),
            "assembly_release_date":
                assembly.get(
                    "release_date"
                ),
            "panel_identity":
                panel_identity(
                    RELEASE_ID
                ),
            "selector":
                SELECTOR,
            "selector_version":
                SELECTOR_VERSION,
            "architecture_schema_version":
                ARCHITECTURE_SCHEMA_VERSION,
            "source_snapshot_sha256":
                source.source_raw_sha256,
            "taxonomy_snapshot_sha256":
                source.taxonomy_archive_sha256,
            "execution_git_commit":
                EXPECTED_STAGE13_EXECUTION_COMMIT,
            "ncbi_assembly_url":
                (
                    "https://www.ncbi.nlm.nih.gov/assembly/"
                    + accession
                    + "/"
                ),
        }

        normalized = {}

        for key, value in values.items():
            if value is None:
                raise MonthlyReleaseExecutionError(
                    f"{accession}: public metadata field {key} is missing"
                )

            normalized[
                key
            ] = str(
                value
            )

        rows.append(
            PublicMetadataRow(
                **normalized
            )
        )

    checked = audit_metadata_ladder(
        rows,
        release_id=RELEASE_ID,
    )

    if tuple(
        row.genbank_assembly_accession
        for row in checked
    ) != selected_accessions:
        raise MonthlyReleaseExecutionError(
            "public metadata accession order changed"
        )

    if tuple(
        row.bacselect_species_taxid
        for row in checked
    ) != selected_species:
        raise MonthlyReleaseExecutionError(
            "public metadata species order changed"
        )

    return checked


def build_evidence_manifest(
    authority_root: Path,
    *,
    known_sha256: Mapping[
        str,
        str,
    ] | None = None,
) -> bytes:
    root = _require_real_directory(
        authority_root,
        label="monthly authority root",
    )

    known = (
        {}
        if known_sha256 is None
        else dict(
            known_sha256
        )
    )

    evidence = []

    for role, relative in (
        EVIDENCE_FILE_SPECS
    ):
        path = (
            root
            / relative
        )

        if (
            not path.is_file()
            or path.is_symlink()
        ):
            raise MonthlyReleaseExecutionError(
                "required release evidence missing: "
                + relative
            )

        digest = known.get(
            relative
        )

        if digest is None:
            digest = sha256_file(
                path
            )
        else:
            _require_sha(
                digest,
                label=(
                    "known evidence SHA256"
                ),
            )

        evidence.append(
            EvidenceFile(
                role=role,
                relative_path=relative,
                sha256=digest,
                size_bytes=(
                    path.stat().st_size
                ),
            )
        )

    return serialize_evidence_manifest(
        evidence
    )


def _required_coverage_metrics(
    stage14: Stage14Authority,
) -> Mapping[
    str,
    object,
]:
    value = stage14.record.get(
        "required_coverage_metrics"
    )

    if not isinstance(
        value,
        dict,
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 14 required coverage metric map is missing"
        )

    if set(
        value
    ) != {
        str(
            panel_size
        )
        for panel_size
        in PANEL_SIZES
    }:
        raise MonthlyReleaseExecutionError(
            "Stage 14 required coverage metric panel set changed"
        )

    return value


def build_release_summary(
    *,
    source: SourceAuthority,
    stage14: Stage14Authority,
) -> bytes:
    public_downloads = {
        str(
            panel_size
        ): {
            "accessions":
                panel_filename(
                    RELEASE_ID,
                    panel_size,
                    "txt",
                ),
            "metadata_tsv":
                panel_filename(
                    RELEASE_ID,
                    panel_size,
                    "tsv",
                ),
            "metadata_xlsx":
                panel_filename(
                    RELEASE_ID,
                    panel_size,
                    "xlsx",
                ),
        }
        for panel_size
        in PANEL_SIZES
    }

    payload = {
        "schema_version":
            RELEASE_SUMMARY_SCHEMA,
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "panel_identity":
            panel_identity(
                RELEASE_ID
            ),
        "selector":
            SELECTOR,
        "selector_version":
            SELECTOR_VERSION,
        "architecture_schema_version":
            ARCHITECTURE_SCHEMA_VERSION,
        "source_universe_count":
            source.source_universe_count,
        "species_group_count":
            source.species_count,
        "complete_ladder_count":
            EXPECTED_LADDER_COUNT,
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
        "source_snapshot_sha256":
            source.source_raw_sha256,
        "taxonomy_snapshot_sha256":
            source.taxonomy_archive_sha256,
        "required_structural_coverage_metrics":
            _required_coverage_metrics(
                stage14
            ),
        "metadata_ladder_file":
            metadata_ladder_filename(
                RELEASE_ID
            ),
        "public_downloads":
            public_downloads,
        "complete_ladder_file":
            "complete-ops-ladder.tsv",
        "selector_trace_file":
            "monthly-ops-ladder-record.json",
        "panel_membership_manifest_file":
            "panel-membership-manifest.tsv",
        "structural_coverage_summary_file":
            "structural-coverage-summary.tsv",
        "evidence_manifest_file":
            EVIDENCE_MANIFEST_NAME,
    }

    return canonical_json_bytes(
        payload
    )


def build_release_provenance(
    *,
    execution_commit: str,
    source: SourceAuthority,
    evidence_manifest_payload: bytes,
    metadata_ladder_payload: bytes,
    public_download_sha256: Mapping[
        str,
        str,
    ],
    copied_artifact_sha256: Mapping[
        str,
        str,
    ],
) -> bytes:
    if (
        _COMMIT_RE.fullmatch(
            execution_commit
        )
        is None
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 15 execution commit is malformed"
        )

    payload = {
        "schema_version":
            RELEASE_PROVENANCE_SCHEMA,
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "source_production_commit":
            SOURCE_PRODUCTION_COMMIT,
        "stage13_selector_execution_commit":
            EXPECTED_STAGE13_EXECUTION_COMMIT,
        "stage14_execution_commit":
            EXPECTED_STAGE14_EXECUTION_COMMIT,
        "stage15_execution_commit":
            execution_commit,
        "stage15_serializer_sha256":
            EXPECTED_PACKAGE_MODULE_SHA256,
        "stage15_schema_sha256":
            EXPECTED_PACKAGE_SCHEMA_SHA256,
        "source_snapshot_record_sha256":
            source.source_snapshot_record_sha256,
        "source_raw_response_sha256":
            source.source_raw_sha256,
        "taxonomy_archive_sha256":
            source.taxonomy_archive_sha256,
        "stage13_table_sha256":
            EXPECTED_STAGE13_TABLE_SHA256,
        "stage13_record_sha256":
            EXPECTED_STAGE13_RECORD_SHA256,
        "stage13_completion_sha256":
            EXPECTED_STAGE13_COMPLETION_SHA256,
        "stage13_complete_ladder_sha256":
            EXPECTED_COMPLETE_LADDER_SHA256,
        "stage14_record_sha256":
            EXPECTED_STAGE14_RECORD_SHA256,
        "stage14_completion_sha256":
            EXPECTED_STAGE14_COMPLETION_SHA256,
        "stage14_scientific_artifact_sha256":
            dict(
                sorted(
                    EXPECTED_STAGE14_ARTIFACT_SHA256.items()
                )
            ),
        "evidence_manifest_sha256":
            sha256_bytes(
                evidence_manifest_payload
            ),
        "metadata_ladder_sha256":
            sha256_bytes(
                metadata_ladder_payload
            ),
        "public_download_sha256":
            dict(
                sorted(
                    public_download_sha256.items()
                )
            ),
        "copied_release_artifact_sha256":
            dict(
                sorted(
                    copied_artifact_sha256.items()
                )
            ),
    }

    return canonical_json_bytes(
        payload
    )


def build_copied_release_artifacts(
    authority_root: Path,
    stage14: Stage14Authority,
) -> Mapping[
    str,
    bytes,
]:
    root = _require_real_directory(
        authority_root,
        label="monthly authority root",
    )

    ladder_path = (
        root
        / "ops-ladder"
        / "complete-ops-ladder.tsv"
    )

    record_path = (
        root
        / "ops-ladder"
        / "monthly-ops-ladder-record.json"
    )

    _require_artifact(
        ladder_path,
        EXPECTED_STAGE13_TABLE_SHA256,
        label="Stage 13 complete OPS ladder",
    )

    _require_artifact(
        record_path,
        EXPECTED_STAGE13_RECORD_SHA256,
        label="Stage 13 selector trace",
    )

    copied = {
        "panel-membership-manifest.tsv":
            stage14.membership_manifest_payload,
        "complete-ops-ladder.tsv":
            ladder_path.read_bytes(),
        "monthly-ops-ladder-record.json":
            record_path.read_bytes(),
        "structural-coverage-summary.tsv":
            stage14.coverage_summary_payload,
    }

    expected = {
        "panel-membership-manifest.tsv":
            EXPECTED_STAGE14_ARTIFACT_SHA256[
                "panel-membership-manifest.tsv"
            ],
        "complete-ops-ladder.tsv":
            EXPECTED_STAGE13_TABLE_SHA256,
        "monthly-ops-ladder-record.json":
            EXPECTED_STAGE13_RECORD_SHA256,
        "structural-coverage-summary.tsv":
            EXPECTED_STAGE14_ARTIFACT_SHA256[
                "structural-coverage-summary.tsv"
            ],
    }

    for name, expected_sha in (
        expected.items()
    ):
        if sha256_bytes(
            copied[
                name
            ]
        ) != expected_sha:
            raise MonthlyReleaseExecutionError(
                f"copied release artifact changed: {name}"
            )

    return dict(
        copied
    )


def build_stage15_artifacts(
    *,
    execution_commit: str,
    metadata_rows: Sequence[
        PublicMetadataRow
    ],
    source: SourceAuthority,
    stage14: Stage14Authority,
    evidence_manifest_payload: bytes,
    copied_artifacts: Mapping[
        str,
        bytes,
    ],
) -> Stage15Build:
    if (
        _COMMIT_RE.fullmatch(
            execution_commit
        )
        is None
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 15 execution commit is malformed"
        )

    checked_rows = audit_metadata_ladder(
        metadata_rows,
        release_id=RELEASE_ID,
    )

    artifacts: dict[
        str,
        bytes,
    ] = {}

    metadata_name = (
        metadata_ladder_filename(
            RELEASE_ID
        )
    )

    metadata_payload = (
        serialize_metadata_ladder(
            checked_rows,
            release_id=RELEASE_ID,
        )
    )

    artifacts[
        metadata_name
    ] = metadata_payload

    public_download_sha = {
        metadata_name:
            sha256_bytes(
                metadata_payload
            )
    }

    for panel_size in PANEL_SIZES:
        txt_name = panel_filename(
            RELEASE_ID,
            panel_size,
            "txt",
        )

        tsv_name = panel_filename(
            RELEASE_ID,
            panel_size,
            "tsv",
        )

        xlsx_name = panel_filename(
            RELEASE_ID,
            panel_size,
            "xlsx",
        )

        txt_payload = (
            serialize_panel_accessions(
                checked_rows,
                release_id=RELEASE_ID,
                panel_size=panel_size,
            )
        )

        tsv_payload = (
            serialize_panel_tsv(
                checked_rows,
                release_id=RELEASE_ID,
                panel_size=panel_size,
            )
        )

        xlsx_payload = (
            serialize_panel_xlsx(
                checked_rows,
                release_id=RELEASE_ID,
                panel_size=panel_size,
            )
        )

        if (
            txt_payload
            != stage14.panel_payloads[
                panel_size
            ]
        ):
            raise MonthlyReleaseExecutionError(
                f"Stage 15 N={panel_size} accessions differ from Stage 14"
            )

        for name, payload in (
            (
                txt_name,
                txt_payload,
            ),
            (
                tsv_name,
                tsv_payload,
            ),
            (
                xlsx_name,
                xlsx_payload,
            ),
        ):
            artifacts[
                name
            ] = payload

            public_download_sha[
                name
            ] = sha256_bytes(
                payload
            )

    if set(
        copied_artifacts
    ) != set(
        COPIED_RELEASE_ARTIFACT_NAMES
    ):
        raise MonthlyReleaseExecutionError(
            "copied release artifact inventory changed"
        )

    for name in sorted(
        copied_artifacts
    ):
        payload = copied_artifacts[
            name
        ]

        if not isinstance(
            payload,
            bytes,
        ):
            raise TypeError(
                "copied release artifact payload must be bytes"
            )

        artifacts[
            name
        ] = payload

    artifacts[
        EVIDENCE_MANIFEST_NAME
    ] = evidence_manifest_payload

    summary_payload = (
        build_release_summary(
            source=source,
            stage14=stage14,
        )
    )

    artifacts[
        RELEASE_SUMMARY_NAME
    ] = summary_payload

    copied_sha = {
        name:
            sha256_bytes(
                copied_artifacts[
                    name
                ]
            )
        for name in sorted(
            copied_artifacts
        )
    }

    provenance_payload = (
        build_release_provenance(
            execution_commit=(
                execution_commit
            ),
            source=source,
            evidence_manifest_payload=(
                evidence_manifest_payload
            ),
            metadata_ladder_payload=(
                metadata_payload
            ),
            public_download_sha256=(
                public_download_sha
            ),
            copied_artifact_sha256=(
                copied_sha
            ),
        )
    )

    artifacts[
        RELEASE_PROVENANCE_NAME
    ] = provenance_payload

    checksum_input = dict(
        artifacts
    )

    artifacts[
        CHECKSUMS_NAME
    ] = serialize_sha256sums(
        checksum_input
    )

    if set(
        artifacts
    ) != set(
        PACKAGE_ARTIFACT_NAMES
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 15 package artifact inventory changed"
        )

    return Stage15Build(
        metadata_rows=tuple(
            checked_rows
        ),
        artifacts=dict(
            sorted(
                artifacts.items()
            )
        ),
        evidence_manifest_sha256=(
            sha256_bytes(
                evidence_manifest_payload
            )
        ),
        metadata_ladder_sha256=(
            sha256_bytes(
                metadata_payload
            )
        ),
        public_download_sha256=dict(
            sorted(
                public_download_sha.items()
            )
        ),
    )


def build_execution_record(
    *,
    execution_commit: str,
    build: Stage15Build,
) -> bytes:
    if (
        _COMMIT_RE.fullmatch(
            execution_commit
        )
        is None
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 15 execution commit is malformed"
        )

    artifact_sha = {
        name:
            sha256_bytes(
                build.artifacts[
                    name
                ]
            )
        for name in sorted(
            build.artifacts
        )
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
            SELECTOR,
        "selector_version":
            SELECTOR_VERSION,
        "architecture_schema_version":
            ARCHITECTURE_SCHEMA_VERSION,
        "panel_identity":
            panel_identity(
                RELEASE_ID
            ),
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
        "source_universe_count":
            EXPECTED_COMPLETE_UNIVERSE_COUNT,
        "species_group_count":
            EXPECTED_SPECIES_COUNT,
        "complete_ladder_count":
            EXPECTED_LADDER_COUNT,
        "metadata_ladder_row_count":
            500,
        "package_artifact_count":
            len(
                build.artifacts
            ),
        "package_artifact_sha256":
            artifact_sha,
        "metadata_ladder_sha256":
            build.metadata_ladder_sha256,
        "evidence_manifest_sha256":
            build.evidence_manifest_sha256,
        "public_download_sha256":
            dict(
                build.public_download_sha256
            ),
        "stage13_table_sha256":
            EXPECTED_STAGE13_TABLE_SHA256,
        "stage13_record_sha256":
            EXPECTED_STAGE13_RECORD_SHA256,
        "stage13_completion_sha256":
            EXPECTED_STAGE13_COMPLETION_SHA256,
        "stage14_record_sha256":
            EXPECTED_STAGE14_RECORD_SHA256,
        "stage14_completion_sha256":
            EXPECTED_STAGE14_COMPLETION_SHA256,
        "ops_rerun":
            False,
        "coverage_rerun":
            False,
        "production_rebuild_audit_passed":
            False,
        "publication_gate_passed":
            False,
        "release_published":
            False,
        "zenodo_published":
            False,
    }

    return canonical_json_bytes(
        payload
    )


def build_completion_receipt(
    *,
    execution_commit: str,
    build: Stage15Build,
    record_sha256: str,
) -> bytes:
    if (
        _COMMIT_RE.fullmatch(
            execution_commit
        )
        is None
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 15 execution commit is malformed"
        )

    _require_sha(
        record_sha256,
        label="Stage 15 record SHA256",
    )

    artifact_sha = {
        name:
            sha256_bytes(
                build.artifacts[
                    name
                ]
            )
        for name in sorted(
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
        "package_artifact_count":
            len(
                build.artifacts
            ),
        "package_artifact_sha256":
            artifact_sha,
        "metadata_ladder_sha256":
            build.metadata_ladder_sha256,
        "evidence_manifest_sha256":
            build.evidence_manifest_sha256,
        "record_sha256":
            record_sha256,
        "production_rebuild_audit_passed":
            False,
        "publication_gate_passed":
            False,
        "release_published":
            False,
    }

    return canonical_json_bytes(
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
        raise MonthlyReleaseExecutionError(
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
    output_root: Path,
    artifacts: Mapping[
        str,
        bytes,
    ],
    record_payload: bytes,
    stability_check: Callable[
        [],
        None,
    ],
) -> Path:
    root = _require_real_directory(
        output_root,
        label="Stage 15 output root",
    )

    final = (
        root
        / STAGE_NAME
    )

    partial = (
        root
        / PARTIAL_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlyReleaseExecutionError(
            "canonical Stage 15 package directory already exists"
        )

    if os.path.lexists(
        partial
    ):
        raise MonthlyReleaseExecutionError(
            "partial Stage 15 package directory already exists"
        )

    if set(
        artifacts
    ) != set(
        PACKAGE_ARTIFACT_NAMES
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 15 publication artifact inventory changed"
        )

    partial.mkdir()

    for name in sorted(
        artifacts
    ):
        _write_fresh(
            partial
            / name,
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
        raise MonthlyReleaseExecutionError(
            "partial Stage 15 file inventory changed"
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
        root
    )

    return final


def publish_completion(
    *,
    output_root: Path,
    payload: bytes,
    stability_check: Callable[
        [],
        None,
    ],
) -> Path:
    root = _require_real_directory(
        output_root,
        label="Stage 15 output root",
    )

    final = (
        root
        / COMPLETION_NAME
    )

    temporary = (
        root
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 15 completion already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlyReleaseExecutionError(
            "Stage 15 completion temporary artifact already exists"
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
        root
    )

    return final


def execute_monthly_release_package(
    *,
    repo: Path,
    authority_root: Path,
    output_root: Path,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    stability_check: Callable[
        [],
        None,
    ] | None = None,
) -> MonthlyStage15ExecutionResult:
    root = repository_preflight(
        repo,
        execution_commit=execution_commit,
    )

    verify_frozen_dependencies(
        root
    )

    if release_id != RELEASE_ID:
        raise MonthlyReleaseExecutionError(
            "unexpected monthly release ID"
        )

    if source_snapshot_id != SOURCE_SNAPSHOT_ID:
        raise MonthlyReleaseExecutionError(
            "unexpected monthly source snapshot"
        )

    authority = _require_real_directory(
        authority_root,
        label="monthly authority root",
    )

    output = _require_real_directory(
        output_root,
        label="Stage 15 output root",
    )

    for path in (
        output / STAGE_NAME,
        output / PARTIAL_NAME,
        output / COMPLETION_NAME,
        output / COMPLETION_TEMP_NAME,
    ):
        if os.path.lexists(
            path
        ):
            raise MonthlyReleaseExecutionError(
                f"Stage 15 output already exists: {path}"
            )

    source = authenticate_source_authority(
        authority
    )

    stage13 = authenticate_stage13(
        root,
        authority,
    )

    stage14 = authenticate_stage14(
        root,
        authority,
    )

    metadata_rows = (
        build_public_metadata_rows(
            authority,
            stage13,
            source,
        )
    )

    known_evidence_sha = {
        "source-snapshot-record.json":
            EXPECTED_SOURCE_SNAPSHOT_RECORD_SHA256,
        "assembly_data_report.raw.jsonl":
            EXPECTED_SOURCE_RAW_SHA256,
        "taxonomy-snapshot/new_taxdump.tar.gz":
            EXPECTED_TAXONOMY_ARCHIVE_SHA256,
        "ops-ladder/complete-ops-ladder.tsv":
            EXPECTED_STAGE13_TABLE_SHA256,
        "ops-ladder/monthly-ops-ladder-record.json":
            EXPECTED_STAGE13_RECORD_SHA256,
        (
            "public-panels-and-coverage/"
            "structural-coverage-summary.tsv"
        ):
            EXPECTED_STAGE14_ARTIFACT_SHA256[
                "structural-coverage-summary.tsv"
            ],
        (
            "public-panels-and-coverage/"
            "structural-coverage-distances.tsv"
        ):
            EXPECTED_STAGE14_ARTIFACT_SHA256[
                "structural-coverage-distances.tsv"
            ],
        (
            "public-panels-and-coverage/"
            "monthly-public-panels-coverage-record.json"
        ):
            EXPECTED_STAGE14_RECORD_SHA256,
    }

    evidence_manifest = (
        build_evidence_manifest(
            authority,
            known_sha256=(
                known_evidence_sha
            ),
        )
    )

    copied = (
        build_copied_release_artifacts(
            authority,
            stage14,
        )
    )

    build = build_stage15_artifacts(
        execution_commit=(
            execution_commit
        ),
        metadata_rows=(
            metadata_rows
        ),
        source=source,
        stage14=stage14,
        evidence_manifest_payload=(
            evidence_manifest
        ),
        copied_artifacts=(
            copied
        ),
    )

    record_payload = (
        build_execution_record(
            execution_commit=(
                execution_commit
            ),
            build=build,
        )
    )

    record_sha = sha256_bytes(
        record_payload
    )

    completion_payload = (
        build_completion_receipt(
            execution_commit=(
                execution_commit
            ),
            build=build,
            record_sha256=(
                record_sha
            ),
        )
    )

    completion_sha = (
        sha256_bytes(
            completion_payload
        )
    )

    check = (
        stability_check
        if stability_check is not None
        else lambda: None
    )

    stage_path = publish_stage(
        output_root=output,
        artifacts=build.artifacts,
        record_payload=record_payload,
        stability_check=check,
    )

    completion_path = (
        publish_completion(
            output_root=output,
            payload=completion_payload,
            stability_check=check,
        )
    )

    return MonthlyStage15ExecutionResult(
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
        completion_sha256=(
            completion_sha
        ),
    )
