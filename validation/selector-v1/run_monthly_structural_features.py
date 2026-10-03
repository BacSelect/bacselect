#!/usr/bin/env python3
"""Monthly Stage 10 raw structural-feature execution wrapper.

Stage 10 consumes the closed monthly complete universe and emits only raw
structural features plus per-accession provenance.

This wrapper deliberately does not calculate:

* percentile coordinates;
* OPS values;
* representative selections; or
* nested panels.

The raw-feature science lives in the frozen
``bacselect.monthly_structural_features`` core. Package/cache reconstruction
is supplied separately so it can reuse the established recovery-aware
monthly source-evidence path.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Callable, Mapping

from bacselect import monthly_structural_features as monthly
from bacselect import source_structural_feature_execution as structural


STAGE_NAME = "structural-features"
PARTIAL_NAME = "structural-features.partial"

MATRIX_NAME = (
    "structural-feature-matrix-300-2400.tsv"
)

PROVENANCE_NAME = (
    "structural-feature-provenance.tsv"
)

RECORD_NAME = (
    "monthly-structural-feature-record.json"
)

COMPLETION_NAME = (
    "structural-features-completion-v1.json"
)

COMPLETION_TEMP_NAME = (
    "structural-features-completion-v1.json.partial"
)

STAGE_FILES = frozenset(
    {
        MATRIX_NAME,
        PROVENANCE_NAME,
        RECORD_NAME,
    }
)

RECORD_SCHEMA = (
    "bacselect-monthly-structural-feature-record-v1"
)

RECORD_STATUS = (
    "MONTHLY_RAW_STRUCTURAL_FEATURES_COMPLETE"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-structural-feature-completion-v1"
)

COMPLETION_STATUS = (
    "MONTHLY_RAW_STRUCTURAL_FEATURES_COMPLETE"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

RELEASE_RE = re.compile(
    r"^[0-9]{4}\.(0[1-9]|1[0-2])$"
)


# ---------------------------------------------------------------------------
# Frozen implementation identities
# ---------------------------------------------------------------------------

EXPECTED_CORE_SHA256 = (
    "f520deabe78312bfe3316bdc49daf63870772002cc65941c68901bab85244428"
)

EXPECTED_MONTHLY_CACHE_SHA256 = (
    "4a2ba0c142663a933ee0df25d69f82fdeb3b6a694154ceafbd3e2e9103b3ef7c"
)

EXPECTED_SOURCE_STRUCTURAL_FEATURES_SHA256 = (
    "80970d76fe3c36429eaecb3b35aed4814695b08f68237417e1c44049fb0bc669"
)

EXPECTED_SOURCE_FEATURE_EXECUTION_SHA256 = (
    "9b92d4869eac338f10499011006cec29ea4e55f05ce9cdc17c5543f70e21fae1"
)

EXPECTED_FINCH_DRIVER_SHA256 = (
    "e4d76a44731000dc8330d6f3289aca76ce6562329dd371f6f63ec090ab42db50"
)

EXPECTED_FINCH_BASIC_SHA256 = (
    "30bc3f52fdf68cf7b6433262935b3ed2bb189b256672687bea56f3a4f4cc043a"
)

EXPECTED_FINCH_REFERENCE_SHA256 = (
    "c1e7388ba7db82d1b937a16e1a1be9e8c65d8779ce8691a2f0097cb5b6af6786"
)

EXPECTED_REPEAT_SOURCE_SHA256 = (
    "bea979167a353c41e51bb96c83acebfb8e8136269d2902d99142c0780bf46925"
)

EXPECTED_REPEAT_LOCK_SHA256 = (
    "aa6984b17e86f7d0627379e295fabed837cf7d43cc6a9fd80f32b7092ac5f64f"
)


# ---------------------------------------------------------------------------
# Frozen September Stage9 authority
# ---------------------------------------------------------------------------

EXPECTED_STAGE9_UNIVERSE_SHA256 = (
    "62c7a92c40f53dbccf41744d80a8f780a203ffffdc36d50026ee8b7f17b7b96e"
)

EXPECTED_STAGE9_RECORD_SHA256 = (
    "22a2a94a32c0c7979f39fb1109258b07d84bdcdb259b1af13f23e358a65f9cef"
)

EXPECTED_STAGE9_COMPLETION_SHA256 = (
    "1b98522334a50a6e5a0b67e6ee8f8a6fd42e5e5a4df1fae4d5709a2bfc9321a4"
)


# ---------------------------------------------------------------------------
# Frozen cache authorities
# ---------------------------------------------------------------------------

EXPECTED_TIER1_MATRIX_SHA256 = (
    "86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948"
)

EXPECTED_TIER1_ROW_AUDIT_SHA256 = (
    "2155a672c676f99e546909ab4bedf1245c953ccadf82276be75303bcf121fcc7"
)

EXPECTED_TIER2_MATRIX_SHA256 = (
    "8bb29e3b8cb98be1f21fe31fb5774b47a36835ebe75ef05fc59c7fe097b7eaf5"
)

EXPECTED_TIER2_CANDIDATE_SHA256 = (
    "05dc8155ef9aa70459c5da865930d20c0aef1db6e6d7cc80103569531f6e1a89"
)

EXPECTED_TIER2_INPUT_MANIFEST_SHA256 = (
    "cad18edfb5083051bfa26cbc3b47288b0d9dbb4586b7105afc6b7c0ab7c9f302"
)

EXPECTED_TIER2_EXECUTION_PROVENANCE_SHA256 = (
    "b7a2741e724ba43fcd94ec1a0a5206a6d8037c48b8356df85dba6cf68a8b78f5"
)


# ---------------------------------------------------------------------------
# Frozen September partition
# ---------------------------------------------------------------------------

EXPECTED_TOTAL_COUNT = 68164
EXPECTED_TIER1_COUNT = 54969
EXPECTED_TIER2_COUNT = 12862
EXPECTED_REUSE_COUNT = 67831
EXPECTED_COMPUTE_COUNT = 333

EXPECTED_MEMBERSHIP_SHA256 = (
    "6e6b44bd598bf472ea2a74686aaabcd23058832938279fb13a4d8ae6cdf7607d"
)

EXPECTED_TIER1_MEMBERSHIP_SHA256 = (
    "7f24e48c3d3578a8afb7042c1df1c90c95c45700973bed4f51f0565d4c4135a0"
)

EXPECTED_TIER2_MEMBERSHIP_SHA256 = (
    "652a84235d257865ab96ea60f8df19c030a38f786a5aa3df43fdb9c8c4dd2a98"
)

EXPECTED_REUSE_MEMBERSHIP_SHA256 = (
    "1487b7d7a38ab6c89e7a81386fbce49f39de9843020bcedf03fa95b7dc536a00"
)

EXPECTED_COMPUTE_MEMBERSHIP_SHA256 = (
    "8eaead6f7ad348864b63d2574fc1e4fa590ac698c123bf2aa9e498e2e382b4c5"
)

EXPECTED_PARTITION_MAPPING_SHA256 = (
    "fed7be0fc10e4f158828af129c03555a462bc94c304d0077b096d8c83e26e4a6"
)

EXPECTED_COMPONENT_IDENTITY_MAPPING_SHA256 = (
    "6467e9252d1f3080a7fc6b1d3d11eca6df744c912779d49e81c2867d4b140ec0"
)

FORCED_COMPUTE_ACCESSION = (
    "GCA_024207115.1"
)

EXPECTED_TIER2_TAXONOMY_RELABELS = (
    "GCA_052938085.1",
    "GCA_056688935.1",
)


class MonthlyStructuralFeatureExecutionError(
    RuntimeError
):
    """Monthly Stage 10 execution failed closed."""


@dataclass(
    frozen=True,
)
class Stage9Authority:
    universe: tuple[
        monthly.MonthlyUniverseMember,
        ...
    ]
    species_by_accession: Mapping[
        str,
        str,
    ]
    universe_sha256: str
    record_sha256: str
    completion_sha256: str


@dataclass(
    frozen=True,
)
class Stage10ExecutionInputs:
    current_component_identity_by_accession: Mapping[
        str,
        str,
    ]
    tier1_cache: Mapping[
        str,
        monthly.CachedFeatureRow,
    ]
    tier2_cache: Mapping[
        str,
        monthly.CachedFeatureRow,
    ]
    computed_rows: Mapping[
        str,
        structural.Stage6FeatureRecord,
    ]


@dataclass(
    frozen=True,
)
class MonthlyStructuralFeatureExecutionResult:
    stage_path: Path
    completion_path: Path
    matrix_sha256: str
    provenance_sha256: str
    record_sha256: str
    completion_sha256: str
    total_count: int
    tier1_count: int
    tier2_count: int
    reuse_count: int
    compute_count: int
    numeric_array_sha256: str


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        for block in iter(
            lambda:
                handle.read(
                    8
                    * 1024
                    * 1024
                ),
            b"",
        ):
            digest.update(
                block
            )

    return digest.hexdigest()


def _sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyStructuralFeatureExecutionError(
            f"{label} is not a lowercase SHA256"
        )

    return value


def _commit(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "execution commit is invalid"
        )

    return value


def _release(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or RELEASE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "release ID is invalid"
        )

    return value


def _canonical_json(
    value: Mapping[
        str,
        object,
    ],
) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    if (
        value.is_symlink()
        or not value.is_file()
    ):
        raise MonthlyStructuralFeatureExecutionError(
            f"{label} is not a regular file"
        )

    return value


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    if (
        value.is_symlink()
        or not value.is_dir()
    ):
        raise MonthlyStructuralFeatureExecutionError(
            f"{label} is not a real directory"
        )

    return value


def _git(
    repo: Path,
    *args: str,
) -> str:
    result = subprocess.run(
        (
            "git",
            *args,
        ),
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return result.stdout.strip()


def repository_preflight(
    repo: Path,
    *,
    execution_commit: str,
) -> Path:
    root = (
        Path(
            repo
        ).resolve()
    )

    _require_real_directory(
        root,
        label="repository root",
    )

    commit = _commit(
        execution_commit
    )

    if _git(
        root,
        "rev-parse",
        "HEAD",
    ) != commit:
        raise MonthlyStructuralFeatureExecutionError(
            "HEAD differs from execution commit"
        )

    if _git(
        root,
        "status",
        "--porcelain",
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "repository working tree is not clean"
        )

    return root


def verify_frozen_dependencies(
    repo: Path,
) -> None:
    expected = {
        "src/bacselect/monthly_structural_features.py":
            EXPECTED_CORE_SHA256,
        "src/bacselect/monthly_cache_verification.py":
            EXPECTED_MONTHLY_CACHE_SHA256,
        "src/bacselect/source_structural_features.py":
            EXPECTED_SOURCE_STRUCTURAL_FEATURES_SHA256,
        "src/bacselect/source_structural_feature_execution.py":
            EXPECTED_SOURCE_FEATURE_EXECUTION_SHA256,
        "vendor/project-finch/experiment-0/compute_structural_features.py":
            EXPECTED_FINCH_DRIVER_SHA256,
        "vendor/project-finch/experiment-0/basic_structural_features.py":
            EXPECTED_FINCH_BASIC_SHA256,
        "vendor/project-finch/experiment-0/structural_features.py":
            EXPECTED_FINCH_REFERENCE_SHA256,
        "vendor/project-finch/experiment-0/structural_features_fast.cpp":
            EXPECTED_REPEAT_SOURCE_SHA256,
        "envs/bacselect-repeat-linux-64.lock":
            EXPECTED_REPEAT_LOCK_SHA256,
    }

    for relative, expected_sha in (
        expected.items()
    ):
        path = _require_regular_file(
            repo
            / relative,
            label=(
                "frozen Stage10 dependency "
                + relative
            ),
        )

        if sha256_file(
            path
        ) != expected_sha:
            raise MonthlyStructuralFeatureExecutionError(
                "frozen Stage10 dependency SHA256 changed: "
                + relative
            )


def authenticate_stage9(
    stage1_root: Path,
) -> Stage9Authority:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    stage = _require_real_directory(
        stage1
        / "complete-universe",
        label="Stage 9 complete-universe stage",
    )

    universe_path = _require_regular_file(
        stage
        / "complete-universe.tsv",
        label="Stage 9 complete universe",
    )

    record_path = _require_regular_file(
        stage
        / "monthly-complete-universe-record.json",
        label="Stage 9 complete-universe record",
    )

    completion_path = _require_regular_file(
        stage1
        / "complete-universe-completion-v1.json",
        label="Stage 9 completion receipt",
    )

    universe_sha = sha256_file(
        universe_path
    )

    record_sha = sha256_file(
        record_path
    )

    completion_sha = sha256_file(
        completion_path
    )

    if universe_sha != (
        EXPECTED_STAGE9_UNIVERSE_SHA256
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "Stage 9 complete universe SHA256 changed"
        )

    if record_sha != (
        EXPECTED_STAGE9_RECORD_SHA256
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "Stage 9 record SHA256 changed"
        )

    if completion_sha != (
        EXPECTED_STAGE9_COMPLETION_SHA256
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "Stage 9 completion SHA256 changed"
        )

    with universe_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        if tuple(
            reader.fieldnames
            or ()
        ) != (
            "canonical_genbank_assembly_accession",
            "species_taxid",
        ):
            raise MonthlyStructuralFeatureExecutionError(
                "Stage 9 universe schema changed"
            )

        rows = list(
            reader
        )

    universe = tuple(
        monthly.MonthlyUniverseMember(
            accession=row[
                "canonical_genbank_assembly_accession"
            ],
            species_taxid=row[
                "species_taxid"
            ],
        )
        for row in rows
    )

    species = {
        row[
            "canonical_genbank_assembly_accession"
        ]:
            row[
                "species_taxid"
            ]
        for row in rows
    }

    if (
        len(
            universe
        )
        != EXPECTED_TOTAL_COUNT
        or len(
            species
        )
        != EXPECTED_TOTAL_COUNT
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "Stage 9 universe count changed"
        )

    membership = (
        monthly
        .accession_membership_sha256(
            tuple(
                species
            )
        )
    )

    if membership != (
        EXPECTED_MEMBERSHIP_SHA256
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "Stage 9 universe membership changed"
        )

    return Stage9Authority(
        universe=universe,
        species_by_accession=species,
        universe_sha256=universe_sha,
        record_sha256=record_sha,
        completion_sha256=completion_sha,
    )


def audit_cache_authority_files(
    *,
    tier1_matrix: Path,
    tier1_row_audit: Path,
    tier2_matrix: Path,
    tier2_candidate_evidence: Path,
    tier2_input_manifest: Path,
    tier2_execution_provenance: Path,
) -> None:
    expected = (
        (
            tier1_matrix,
            EXPECTED_TIER1_MATRIX_SHA256,
            "Tier 1 feature matrix",
        ),
        (
            tier1_row_audit,
            EXPECTED_TIER1_ROW_AUDIT_SHA256,
            "Tier 1 row audit",
        ),
        (
            tier2_matrix,
            EXPECTED_TIER2_MATRIX_SHA256,
            "Tier 2 feature matrix",
        ),
        (
            tier2_candidate_evidence,
            EXPECTED_TIER2_CANDIDATE_SHA256,
            "Tier 2 candidate evidence",
        ),
        (
            tier2_input_manifest,
            EXPECTED_TIER2_INPUT_MANIFEST_SHA256,
            "Tier 2 input manifest",
        ),
        (
            tier2_execution_provenance,
            EXPECTED_TIER2_EXECUTION_PROVENANCE_SHA256,
            "Tier 2 execution provenance",
        ),
    )

    for path, expected_sha, label in (
        expected
    ):
        observed = _require_regular_file(
            path,
            label=label,
        )

        if sha256_file(
            observed
        ) != expected_sha:
            raise MonthlyStructuralFeatureExecutionError(
                f"{label} SHA256 changed"
            )


def _reuse_membership_sha256(
    build: monthly.MonthlyStructuralFeatureBuild,
) -> str:
    values = tuple(
        build.tier1_accessions
    ) + tuple(
        build.tier2_accessions
    )

    return (
        monthly
        .accession_membership_sha256(
            values
        )
    )


def audit_frozen_partition(
    build: monthly.MonthlyStructuralFeatureBuild,
) -> None:
    if not isinstance(
        build,
        monthly.MonthlyStructuralFeatureBuild,
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "Stage 10 build has wrong type"
        )

    counts = {
        "total":
            len(
                build.rows
            ),
        "tier1":
            len(
                build.tier1_accessions
            ),
        "tier2":
            len(
                build.tier2_accessions
            ),
        "reuse":
            len(
                build.tier1_accessions
            )
            + len(
                build.tier2_accessions
            ),
        "compute":
            len(
                build.computed_accessions
            ),
    }

    expected_counts = {
        "total":
            EXPECTED_TOTAL_COUNT,
        "tier1":
            EXPECTED_TIER1_COUNT,
        "tier2":
            EXPECTED_TIER2_COUNT,
        "reuse":
            EXPECTED_REUSE_COUNT,
        "compute":
            EXPECTED_COMPUTE_COUNT,
    }

    if counts != expected_counts:
        raise MonthlyStructuralFeatureExecutionError(
            "Stage 10 frozen partition counts changed"
        )

    expected_hashes = {
        "membership":
            EXPECTED_MEMBERSHIP_SHA256,
        "tier1":
            EXPECTED_TIER1_MEMBERSHIP_SHA256,
        "tier2":
            EXPECTED_TIER2_MEMBERSHIP_SHA256,
        "reuse":
            EXPECTED_REUSE_MEMBERSHIP_SHA256,
        "compute":
            EXPECTED_COMPUTE_MEMBERSHIP_SHA256,
        "partition":
            EXPECTED_PARTITION_MAPPING_SHA256,
    }

    observed_hashes = {
        "membership":
            build.membership_sha256,
        "tier1":
            build.tier1_membership_sha256,
        "tier2":
            build.tier2_membership_sha256,
        "reuse":
            _reuse_membership_sha256(
                build
            ),
        "compute":
            build.computed_membership_sha256,
        "partition":
            build.partition_mapping_sha256,
    }

    if (
        observed_hashes
        != expected_hashes
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "Stage 10 frozen partition identity changed"
        )

    if FORCED_COMPUTE_ACCESSION not in (
        build.computed_accessions
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "topology-revised accession is no longer COMPUTE"
        )


def component_identity_mapping_sha256(
    mapping: Mapping[
        str,
        str,
    ],
) -> str:
    payload = "".join(
        accession
        + "\t"
        + _sha256(
            mapping[
                accession
            ],
            label=(
                "component identity"
            ),
        )
        + "\n"
        for accession in sorted(
            mapping
        )
    ).encode(
        "ascii"
    )

    return hashlib.sha256(
        payload
    ).hexdigest()


def build_execution_record(
    *,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    build: monthly.MonthlyStructuralFeatureBuild,
    stage9: Stage9Authority,
    current_component_identity_sha256: str,
    matrix_sha256: str,
    provenance_sha256: str,
) -> bytes:
    audit_frozen_partition(
        build
    )

    current_identity_sha = _sha256(
        current_component_identity_sha256,
        label=(
            "current component-identity mapping SHA256"
        ),
    )

    if current_identity_sha != (
        EXPECTED_COMPONENT_IDENTITY_MAPPING_SHA256
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "September component-identity mapping changed"
        )

    payload = {
        "schema_version":
            RECORD_SCHEMA,
        "status":
            RECORD_STATUS,
        "release_id":
            _release(
                release_id
            ),
        "source_snapshot_id":
            source_snapshot_id,
        "execution_commit":
            _commit(
                execution_commit
            ),
        "complete_universe_sha256":
            stage9.universe_sha256,
        "complete_universe_record_sha256":
            stage9.record_sha256,
        "complete_universe_completion_sha256":
            stage9.completion_sha256,
        "component_identity_mapping_sha256":
            current_identity_sha,
        "membership_sha256":
            build.membership_sha256,
        "tier1_membership_sha256":
            build.tier1_membership_sha256,
        "tier2_membership_sha256":
            build.tier2_membership_sha256,
        "reuse_membership_sha256":
            _reuse_membership_sha256(
                build
            ),
        "compute_membership_sha256":
            build.computed_membership_sha256,
        "partition_mapping_sha256":
            build.partition_mapping_sha256,
        "numeric_array_sha256":
            build.numeric_array_sha256,
        "matrix_sha256":
            _sha256(
                matrix_sha256,
                label="Stage 10 matrix SHA256",
            ),
        "provenance_sha256":
            _sha256(
                provenance_sha256,
                label="Stage 10 provenance SHA256",
            ),
        "total_count":
            len(
                build.rows
            ),
        "tier1_reuse_count":
            len(
                build.tier1_accessions
            ),
        "tier2_reuse_count":
            len(
                build.tier2_accessions
            ),
        "total_reuse_count":
            len(
                build.tier1_accessions
            )
            + len(
                build.tier2_accessions
            ),
        "fresh_compute_count":
            len(
                build.computed_accessions
            ),
        "percentile_coordinates_calculated":
            False,
        "selector_outcomes_calculated":
            False,
        "nested_panels_calculated":
            False,
        "monthly_structural_feature_core_sha256":
            EXPECTED_CORE_SHA256,
        "source_structural_feature_execution_sha256":
            EXPECTED_SOURCE_FEATURE_EXECUTION_SHA256,
        "finch_driver_sha256":
            EXPECTED_FINCH_DRIVER_SHA256,
        "finch_basic_sha256":
            EXPECTED_FINCH_BASIC_SHA256,
        "finch_semantic_reference_sha256":
            EXPECTED_FINCH_REFERENCE_SHA256,
        "repeat_engine_source_sha256":
            EXPECTED_REPEAT_SOURCE_SHA256,
        "repeat_environment_lock_sha256":
            EXPECTED_REPEAT_LOCK_SHA256,
    }

    return _canonical_json(
        payload
    )


def build_completion_receipt(
    *,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    stage9: Stage9Authority,
    build: monthly.MonthlyStructuralFeatureBuild,
    matrix_sha256: str,
    provenance_sha256: str,
    record_sha256: str,
) -> bytes:
    audit_frozen_partition(
        build
    )

    payload = {
        "schema_version":
            COMPLETION_SCHEMA,
        "status":
            COMPLETION_STATUS,
        "release_id":
            _release(
                release_id
            ),
        "source_snapshot_id":
            source_snapshot_id,
        "execution_commit":
            _commit(
                execution_commit
            ),
        "complete_universe_sha256":
            stage9.universe_sha256,
        "complete_universe_record_sha256":
            stage9.record_sha256,
        "complete_universe_completion_sha256":
            stage9.completion_sha256,
        "membership_sha256":
            build.membership_sha256,
        "tier1_membership_sha256":
            build.tier1_membership_sha256,
        "tier2_membership_sha256":
            build.tier2_membership_sha256,
        "reuse_membership_sha256":
            _reuse_membership_sha256(
                build
            ),
        "compute_membership_sha256":
            build.computed_membership_sha256,
        "partition_mapping_sha256":
            build.partition_mapping_sha256,
        "numeric_array_sha256":
            build.numeric_array_sha256,
        "matrix_sha256":
            _sha256(
                matrix_sha256,
                label="matrix SHA256",
            ),
        "provenance_sha256":
            _sha256(
                provenance_sha256,
                label="provenance SHA256",
            ),
        "record_sha256":
            _sha256(
                record_sha256,
                label="record SHA256",
            ),
        "total_count":
            len(
                build.rows
            ),
        "total_reuse_count":
            len(
                build.tier1_accessions
            )
            + len(
                build.tier2_accessions
            ),
        "fresh_compute_count":
            len(
                build.computed_accessions
            ),
    }

    return _canonical_json(
        payload
    )


def write_no_clobber(
    path: Path,
    payload: bytes,
) -> None:
    value = Path(
        path
    )

    try:
        with value.open(
            "xb"
        ) as handle:
            handle.write(
                payload
            )

            handle.flush()

            os.fsync(
                handle.fileno()
            )

    except FileExistsError as exc:
        raise MonthlyStructuralFeatureExecutionError(
            f"refusing to overwrite file: {value}"
        ) from exc


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


def audit_stage_directory(
    stage: Path,
    *,
    matrix_payload: bytes,
    provenance_payload: bytes,
    record_payload: bytes,
) -> None:
    directory = _require_real_directory(
        stage,
        label="Stage 10 stage",
    )

    observed_names = {
        item.name
        for item in directory.iterdir()
    }

    if observed_names != STAGE_FILES:
        raise MonthlyStructuralFeatureExecutionError(
            "Stage 10 stage inventory changed"
        )

    expected = {
        MATRIX_NAME:
            matrix_payload,
        PROVENANCE_NAME:
            provenance_payload,
        RECORD_NAME:
            record_payload,
    }

    for name, payload in (
        expected.items()
    ):
        path = _require_regular_file(
            directory
            / name,
            label=(
                "Stage 10 artifact "
                + name
            ),
        )

        if path.read_bytes() != payload:
            raise MonthlyStructuralFeatureExecutionError(
                "Stage 10 artifact readback changed: "
                + name
            )


def publish_stage(
    *,
    stage1_root: Path,
    matrix_payload: bytes,
    provenance_payload: bytes,
    record_payload: bytes,
    stability_check: Callable[
        [],
        None,
    ],
) -> Path:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    partial = (
        stage1
        / PARTIAL_NAME
    )

    final = (
        stage1
        / STAGE_NAME
    )

    for path, label in (
        (
            partial,
            "partial Stage 10 stage",
        ),
        (
            final,
            "canonical Stage 10 stage",
        ),
    ):
        if os.path.lexists(
            path
        ):
            raise MonthlyStructuralFeatureExecutionError(
                f"{label} already exists"
            )

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    try:
        write_no_clobber(
            partial
            / MATRIX_NAME,
            matrix_payload,
        )

        write_no_clobber(
            partial
            / PROVENANCE_NAME,
            provenance_payload,
        )

        write_no_clobber(
            partial
            / RECORD_NAME,
            record_payload,
        )

        _fsync_directory(
            partial
        )

        audit_stage_directory(
            partial,
            matrix_payload=(
                matrix_payload
            ),
            provenance_payload=(
                provenance_payload
            ),
            record_payload=(
                record_payload
            ),
        )

        stability_check()

        os.rename(
            partial,
            final,
        )

        _fsync_directory(
            stage1
        )

        audit_stage_directory(
            final,
            matrix_payload=(
                matrix_payload
            ),
            provenance_payload=(
                provenance_payload
            ),
            record_payload=(
                record_payload
            ),
        )

        stability_check()

    except Exception:
        if (
            partial.exists()
            and not partial.is_symlink()
            and partial.is_dir()
        ):
            shutil.rmtree(
                partial
            )

        if (
            final.exists()
            and not final.is_symlink()
            and final.is_dir()
        ):
            shutil.rmtree(
                final
            )

        raise

    return final


def publish_completion(
    *,
    stage1_root: Path,
    payload: bytes,
    stability_check: Callable[
        [],
        None,
    ],
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

    if (
        os.path.lexists(
            final
        )
        or os.path.lexists(
            temporary
        )
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "Stage 10 completion path already exists"
        )

    write_no_clobber(
        temporary,
        payload,
    )

    _fsync_directory(
        stage1
    )

    try:
        if (
            temporary.read_bytes()
            != payload
        ):
            raise MonthlyStructuralFeatureExecutionError(
                "temporary Stage 10 completion changed"
            )

        stability_check()

        os.link(
            temporary,
            final,
        )

        _fsync_directory(
            stage1
        )

        if (
            final.read_bytes()
            != payload
        ):
            raise MonthlyStructuralFeatureExecutionError(
                "published Stage 10 completion changed"
            )

        stability_check()

        temporary.unlink()

        _fsync_directory(
            stage1
        )

    except Exception:
        if (
            final.exists()
            and not final.is_symlink()
            and final.is_file()
        ):
            final.unlink()

        if (
            temporary.exists()
            and not temporary.is_symlink()
            and temporary.is_file()
        ):
            temporary.unlink()

        raise

    return final


def execute_monthly_structural_features(
    *,
    repo: Path,
    stage1_root: Path,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    inputs: Stage10ExecutionInputs,
    stability_check: Callable[
        [],
        None,
    ] | None = None,
) -> MonthlyStructuralFeatureExecutionResult:
    root = repository_preflight(
        repo,
        execution_commit=(
            execution_commit
        ),
    )

    verify_frozen_dependencies(
        root
    )

    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    for path, label in (
        (
            stage1
            / STAGE_NAME,
            "canonical Stage 10 stage",
        ),
        (
            stage1
            / PARTIAL_NAME,
            "partial Stage 10 stage",
        ),
        (
            stage1
            / COMPLETION_NAME,
            "Stage 10 completion",
        ),
        (
            stage1
            / COMPLETION_TEMP_NAME,
            "Stage 10 completion temporary artifact",
        ),
    ):
        if os.path.lexists(
            path
        ):
            raise MonthlyStructuralFeatureExecutionError(
                f"{label} already exists"
            )

    stage9 = authenticate_stage9(
        stage1
    )

    identity_sha = (
        component_identity_mapping_sha256(
            inputs
            .current_component_identity_by_accession
        )
    )

    if identity_sha != (
        EXPECTED_COMPONENT_IDENTITY_MAPPING_SHA256
    ):
        raise MonthlyStructuralFeatureExecutionError(
            "current component-identity mapping changed"
        )

    build = (
        monthly
        .build_monthly_structural_features(
            stage9.universe,
            current_component_identity_by_accession=(
                inputs
                .current_component_identity_by_accession
            ),
            tier1_cache=(
                inputs.tier1_cache
            ),
            tier2_cache=(
                inputs.tier2_cache
            ),
            computed_rows=(
                inputs.computed_rows
            ),
        )
    )

    audit_frozen_partition(
        build
    )

    matrix_payload = (
        monthly
        .serialize_monthly_structural_feature_matrix(
            build
        )
    )

    provenance_payload = (
        monthly
        .serialize_monthly_structural_feature_provenance(
            build
        )
    )

    matrix_sha = hashlib.sha256(
        matrix_payload
    ).hexdigest()

    provenance_sha = hashlib.sha256(
        provenance_payload
    ).hexdigest()

    record_payload = build_execution_record(
        release_id=release_id,
        source_snapshot_id=(
            source_snapshot_id
        ),
        execution_commit=(
            execution_commit
        ),
        build=build,
        stage9=stage9,
        current_component_identity_sha256=(
            identity_sha
        ),
        matrix_sha256=matrix_sha,
        provenance_sha256=(
            provenance_sha
        ),
    )

    record_sha = hashlib.sha256(
        record_payload
    ).hexdigest()

    completion_payload = (
        build_completion_receipt(
            release_id=release_id,
            source_snapshot_id=(
                source_snapshot_id
            ),
            execution_commit=(
                execution_commit
            ),
            stage9=stage9,
            build=build,
            matrix_sha256=(
                matrix_sha
            ),
            provenance_sha256=(
                provenance_sha
            ),
            record_sha256=(
                record_sha
            ),
        )
    )

    completion_sha = hashlib.sha256(
        completion_payload
    ).hexdigest()

    check = (
        stability_check
        if stability_check
        is not None
        else lambda:
            None
    )

    stage_path = publish_stage(
        stage1_root=stage1,
        matrix_payload=(
            matrix_payload
        ),
        provenance_payload=(
            provenance_payload
        ),
        record_payload=(
            record_payload
        ),
        stability_check=check,
    )

    completion_path = (
        publish_completion(
            stage1_root=stage1,
            payload=(
                completion_payload
            ),
            stability_check=check,
        )
    )

    return (
        MonthlyStructuralFeatureExecutionResult(
            stage_path=(
                stage_path
            ),
            completion_path=(
                completion_path
            ),
            matrix_sha256=(
                matrix_sha
            ),
            provenance_sha256=(
                provenance_sha
            ),
            record_sha256=(
                record_sha
            ),
            completion_sha256=(
                completion_sha
            ),
            total_count=(
                len(
                    build.rows
                )
            ),
            tier1_count=(
                len(
                    build.tier1_accessions
                )
            ),
            tier2_count=(
                len(
                    build.tier2_accessions
                )
            ),
            reuse_count=(
                len(
                    build.tier1_accessions
                )
                + len(
                    build.tier2_accessions
                )
            ),
            compute_count=(
                len(
                    build.computed_accessions
                )
            ),
            numeric_array_sha256=(
                build.numeric_array_sha256
            ),
        )
    )
