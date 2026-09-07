#!/usr/bin/env python3
"""Monthly Stage 12 species-representative construction for BacSelect.

This wrapper authenticates the completed monthly Stage 11 percentile geometry
and reruns the frozen selector-v1 OPS species-representative rule over the
complete current monthly universe.

It publishes exactly one representative per current species.

It does not construct the OPS ladder, run SR or AG, rerun selector resolution,
generate public panels, or calculate structural coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Callable, Iterable, Mapping

import numpy as np
import numpy.typing as npt

from bacselect import monthly_geometry
from bacselect.monthly_structural_features import (
    accession_membership_sha256,
)
from bacselect.ops import (
    ops_species_representatives,
)
from bacselect.tie import tie_key


RELEASE_ID = "2026.09"

SOURCE_SNAPSHOT_ID = (
    "bacselect-source-2026.09-20260901T021652Z"
)

REMOTE_BRANCH = (
    "origin/recovery/monthly-missing-datasets-gbff"
)

STAGE11_STAGE_NAME = "percentile-geometry"

STAGE11_MATRIX_NAME = (
    "species-balanced-percentile-feature-matrix-300-2400.tsv"
)

STAGE11_RECORD_NAME = (
    "monthly-percentile-geometry-record.json"
)

STAGE11_COMPLETION_NAME = (
    "percentile-geometry-completion-v1.json"
)

STAGE_NAME = "species-representatives"

PARTIAL_NAME = (
    "species-representatives.partial"
)

TABLE_NAME = (
    "species-representatives.tsv"
)

RECORD_NAME = (
    "monthly-species-representative-record.json"
)

COMPLETION_NAME = (
    "species-representatives-completion-v1.json"
)

COMPLETION_TEMP_NAME = (
    "species-representatives-completion-v1.json.partial"
)

STAGE_FILES = frozenset(
    {
        TABLE_NAME,
        RECORD_NAME,
    }
)

TABLE_FIELDS = (
    "species_taxid",
    "canonical_genbank_assembly_accession",
)

RECORD_SCHEMA = (
    "bacselect-monthly-species-representative-record-v1"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-species-representative-completion-v1"
)

STATUS = (
    "MONTHLY_SPECIES_REPRESENTATIVES_COMPLETE"
)

REPRESENTATIVE_NAMESPACE = (
    "BacSelect-selector-v1|OPS|representatives"
)

EXPECTED_STAGE11_EXECUTION_COMMIT = (
    "add30c92a95f1c12cef630676e7f419614d34684"
)

EXPECTED_STAGE11_MATRIX_SHA256 = (
    "cb3c8d14e8d0bd4982de4a92219a7a4b"
    "d307663bf22d9e4234690d34367f0935"
)

EXPECTED_STAGE11_RECORD_SHA256 = (
    "d7e231455a3208d8cf4a48bf105d6c60"
    "8e766b42273795577a1daf2f900411be"
)

EXPECTED_STAGE11_COMPLETION_SHA256 = (
    "901508c9bf074e3d557c93d9636e8f2c"
    "3fee98f51ba78e3a5bc8a070dbc4ba87"
)

EXPECTED_MEMBERSHIP_SHA256 = (
    "6e6b44bd598bf472ea2a74686aaabcd23"
    "058832938279fb13a4d8ae6cdf7607d"
)

EXPECTED_SPECIES_MAPPING_SHA256 = (
    "103c0539c4e55863f43e756e64c3d9c3"
    "0ab2c49ef205e12cc640bb53a92e68d8"
)

EXPECTED_PERCENTILE_ARRAY_SHA256 = (
    "da76cc78da56c06524923c1977bbc671"
    "d31f5149ea9f9f103b2fc52d051cfc78"
)

EXPECTED_TOTAL_COUNT = 68164
EXPECTED_SPECIES_COUNT = 16223
EXPECTED_FEATURE_COUNT = 12

EXPECTED_OPS_SHA256 = (
    "eb6c1b8edab3e694b0f3825bb5ab0eaf"
    "44fdd95fdbb6a6e3e41439c18c828c0f"
)

EXPECTED_OPS_TEST_SHA256 = (
    "7eec19ebcfda97a3423b9c1c8b50ed22"
    "0bcbd81f79f5f38ca865359269307f58"
)

EXPECTED_TIE_SHA256 = (
    "a5746d3d40e3d267398f80eb83ab2f4b"
    "1ee84808f3d9a7715dade7fc0824f73e"
)

EXPECTED_TIE_TEST_SHA256 = (
    "b08954d007af923eebd44c4ca4909f10"
    "4d49e389069deb24398f6ec13f6af192"
)

EXPECTED_MONTHLY_GEOMETRY_SHA256 = (
    "ac8bbc94a2bacae8c8e80de1f5a9d65b"
    "e886d59a2e72386ce82de8a5da23297e"
)

EXPECTED_ENVIRONMENT_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207eaef"
    "5c2435e1b6feeddc1e4654686bc2a8c"
)

EXPECTED_SELECTOR_DECISION_SHA256 = (
    "d0cf63ad4d933194e3e782912a2a2a3c"
    "617353758d2c87c1b1198681a75869e2"
)

FROZEN_REPO_FILES: Mapping[str, str] = {
    "src/bacselect/ops.py":
        EXPECTED_OPS_SHA256,
    "tests/test_ops.py":
        EXPECTED_OPS_TEST_SHA256,
    "src/bacselect/tie.py":
        EXPECTED_TIE_SHA256,
    "tests/test_tie.py":
        EXPECTED_TIE_TEST_SHA256,
    "src/bacselect/monthly_geometry.py":
        EXPECTED_MONTHLY_GEOMETRY_SHA256,
    "envs/bacselect-dev-linux-64.lock":
        EXPECTED_ENVIRONMENT_LOCK_SHA256,
    "validation/selector-v1/stage7-selector-decision-record.json":
        EXPECTED_SELECTOR_DECISION_SHA256,
}

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


class MonthlyRepresentativeError(RuntimeError):
    """Raised when monthly Stage 12 execution cannot be authenticated."""


@dataclass(frozen=True)
class Stage11Expectations:
    release_id: str
    source_snapshot_id: str
    execution_commit: str
    matrix_sha256: str
    record_sha256: str
    completion_sha256: str
    membership_sha256: str
    species_mapping_sha256: str
    percentile_array_sha256: str
    total_count: int
    species_count: int
    feature_count: int


PRODUCTION_EXPECTATIONS = Stage11Expectations(
    release_id=RELEASE_ID,
    source_snapshot_id=SOURCE_SNAPSHOT_ID,
    execution_commit=EXPECTED_STAGE11_EXECUTION_COMMIT,
    matrix_sha256=EXPECTED_STAGE11_MATRIX_SHA256,
    record_sha256=EXPECTED_STAGE11_RECORD_SHA256,
    completion_sha256=EXPECTED_STAGE11_COMPLETION_SHA256,
    membership_sha256=EXPECTED_MEMBERSHIP_SHA256,
    species_mapping_sha256=EXPECTED_SPECIES_MAPPING_SHA256,
    percentile_array_sha256=EXPECTED_PERCENTILE_ARRAY_SHA256,
    total_count=EXPECTED_TOTAL_COUNT,
    species_count=EXPECTED_SPECIES_COUNT,
    feature_count=EXPECTED_FEATURE_COUNT,
)


@dataclass(frozen=True)
class Stage11Authority:
    accessions: tuple[str, ...]
    species_ids: tuple[str, ...]
    coordinates: npt.NDArray[np.float64]
    matrix_sha256: str
    record_sha256: str
    completion_sha256: str
    membership_sha256: str
    species_mapping_sha256: str
    percentile_array_sha256: str
    species_count: int


@dataclass(frozen=True)
class RepresentativeRow:
    species_taxid: str
    accession: str
    source_index: int


@dataclass(frozen=True)
class RepresentativeBuild:
    rows: tuple[RepresentativeRow, ...]
    representative_sequence_sha256: str
    representative_membership_sha256: str
    representative_count: int


@dataclass(frozen=True)
class MonthlyRepresentativeExecutionResult:
    stage_path: Path
    completion_path: Path
    table_sha256: str
    record_sha256: str
    completion_sha256: str
    representative_sequence_sha256: str
    representative_membership_sha256: str
    representative_count: int


def sha256_file(path: Path) -> str:
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


def sequence_sha256(
    namespace: str,
    values: Iterable[str],
) -> str:
    payload = (
        namespace
        + "\n"
        + "\n".join(values)
        + "\n"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def _canonical_json(
    payload: Mapping[str, object],
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


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
        or _SHA_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyRepresentativeError(
            f"{label} is not a lowercase SHA256"
        )

    return value


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    resolved = Path(
        path
    ).resolve()

    if (
        not resolved.is_dir()
        or resolved.is_symlink()
    ):
        raise MonthlyRepresentativeError(
            f"{label} is not a real directory: {resolved}"
        )

    return resolved


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
        raise MonthlyRepresentativeError(
            "Stage 12 execution commit is malformed"
        )

    if (
        _git(
            root,
            "rev-parse",
            "HEAD",
        )
        != execution_commit
    ):
        raise MonthlyRepresentativeError(
            "repository HEAD differs from Stage 12 execution commit"
        )

    if (
        _git(
            root,
            "rev-parse",
            REMOTE_BRANCH,
        )
        != execution_commit
    ):
        raise MonthlyRepresentativeError(
            "remote Stage 12 branch differs from execution commit"
        )

    if _git(
        root,
        "status",
        "--porcelain",
    ):
        raise MonthlyRepresentativeError(
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
            raise MonthlyRepresentativeError(
                f"frozen Stage 12 dependency missing: {relative}"
            )

        digest = sha256_file(
            path
        )

        if digest != expected:
            raise MonthlyRepresentativeError(
                f"frozen Stage 12 dependency changed: {relative}"
            )

        observed[
            relative
        ] = digest

    return dict(
        sorted(
            observed.items()
        )
    )


def verify_selector_decision(
    repo: Path,
) -> Mapping[str, object]:
    path = (
        repo
        / "validation"
        / "selector-v1"
        / "stage7-selector-decision-record.json"
    )

    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise MonthlyRepresentativeError(
            "selector decision record missing"
        )

    if (
        sha256_file(
            path
        )
        != EXPECTED_SELECTOR_DECISION_SHA256
    ):
        raise MonthlyRepresentativeError(
            "selector decision record SHA256 changed"
        )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise MonthlyRepresentativeError(
            "selector decision record is not an object"
        )

    if (
        payload.get(
            "status"
        )
        != "STAGE7_SELECTOR_DECISION_FINALIZED"
    ):
        raise MonthlyRepresentativeError(
            "selector decision status changed"
        )

    if payload.get(
        "decision"
    ) != "OPS":
        raise MonthlyRepresentativeError(
            "production selector is not OPS"
        )

    bindings = payload.get(
        "analysis_implementation_bindings"
    )

    if (
        not isinstance(
            bindings,
            dict,
        )
        or bindings.get(
            "ops_sha256"
        )
        != EXPECTED_OPS_SHA256
    ):
        raise MonthlyRepresentativeError(
            "selector decision OPS binding changed"
        )

    return payload


def _require_artifact(
    path: Path,
    expected_sha256: str,
    *,
    label: str,
) -> str:
    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise MonthlyRepresentativeError(
            f"{label} missing: {path}"
        )

    observed = sha256_file(
        path
    )

    if observed != expected_sha256:
        raise MonthlyRepresentativeError(
            f"{label} SHA256 changed"
        )

    return observed


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
        raise MonthlyRepresentativeError(
            f"cannot parse {label}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise MonthlyRepresentativeError(
            f"{label} must be a JSON object"
        )

    return payload


def _validate_stage11_record(
    record: Mapping[str, object],
    expectations: Stage11Expectations,
) -> None:
    required = {
        "status":
            "MONTHLY_SPECIES_BALANCED_PERCENTILE_GEOMETRY_COMPLETE",
        "release_id":
            expectations.release_id,
        "source_snapshot_id":
            expectations.source_snapshot_id,
        "execution_commit":
            expectations.execution_commit,
        "percentile_matrix_sha256":
            expectations.matrix_sha256,
        "membership_sha256":
            expectations.membership_sha256,
        "species_mapping_sha256":
            expectations.species_mapping_sha256,
        "percentile_numeric_array_sha256":
            expectations.percentile_array_sha256,
        "total_count":
            expectations.total_count,
        "species_count":
            expectations.species_count,
        "feature_count":
            expectations.feature_count,
        "species_representatives_constructed":
            False,
        "ops_ladder_constructed":
            False,
        "selector_outcomes_calculated":
            False,
        "panels_generated":
            False,
        "coverage_generated":
            False,
    }

    for key, expected in (
        required.items()
    ):
        if record.get(
            key
        ) != expected:
            raise MonthlyRepresentativeError(
                f"Stage 11 record {key} mismatch"
            )


def _validate_stage11_completion(
    completion: Mapping[str, object],
    expectations: Stage11Expectations,
) -> None:
    required = {
        "status":
            "MONTHLY_SPECIES_BALANCED_PERCENTILE_GEOMETRY_COMPLETE",
        "release_id":
            expectations.release_id,
        "source_snapshot_id":
            expectations.source_snapshot_id,
        "execution_commit":
            expectations.execution_commit,
        "percentile_matrix_sha256":
            expectations.matrix_sha256,
        "record_sha256":
            expectations.record_sha256,
        "membership_sha256":
            expectations.membership_sha256,
        "species_mapping_sha256":
            expectations.species_mapping_sha256,
        "percentile_numeric_array_sha256":
            expectations.percentile_array_sha256,
        "total_count":
            expectations.total_count,
        "species_count":
            expectations.species_count,
        "feature_count":
            expectations.feature_count,
    }

    for key, expected in (
        required.items()
    ):
        if completion.get(
            key
        ) != expected:
            raise MonthlyRepresentativeError(
                f"Stage 11 completion {key} mismatch"
            )


def authenticate_stage11(
    stage1_root: Path,
    *,
    expectations: Stage11Expectations = (
        PRODUCTION_EXPECTATIONS
    ),
) -> Stage11Authority:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    stage = (
        stage1
        / STAGE11_STAGE_NAME
    )

    if (
        not stage.is_dir()
        or stage.is_symlink()
    ):
        raise MonthlyRepresentativeError(
            "canonical Stage 11 directory missing"
        )

    matrix_path = (
        stage
        / STAGE11_MATRIX_NAME
    )

    record_path = (
        stage
        / STAGE11_RECORD_NAME
    )

    completion_path = (
        stage1
        / STAGE11_COMPLETION_NAME
    )

    matrix_sha = _require_artifact(
        matrix_path,
        expectations.matrix_sha256,
        label="Stage 11 matrix",
    )

    record_sha = _require_artifact(
        record_path,
        expectations.record_sha256,
        label="Stage 11 record",
    )

    completion_sha = _require_artifact(
        completion_path,
        expectations.completion_sha256,
        label="Stage 11 completion",
    )

    record = _load_json(
        record_path,
        label="Stage 11 record",
    )

    completion = _load_json(
        completion_path,
        label="Stage 11 completion",
    )

    _validate_stage11_record(
        record,
        expectations,
    )

    _validate_stage11_completion(
        completion,
        expectations,
    )

    (
        accessions,
        species_ids,
        coordinates,
    ) = (
        monthly_geometry
        .parse_monthly_geometry_matrix(
            matrix_path.read_bytes()
        )
    )

    if len(
        accessions
    ) != expectations.total_count:
        raise MonthlyRepresentativeError(
            "Stage 11 matrix row count changed"
        )

    if (
        coordinates.shape
        != (
            expectations.total_count,
            expectations.feature_count,
        )
    ):
        raise MonthlyRepresentativeError(
            "Stage 11 coordinate matrix shape changed"
        )

    if len(
        set(
            species_ids
        )
    ) != expectations.species_count:
        raise MonthlyRepresentativeError(
            "Stage 11 species count changed"
        )

    membership_sha = (
        accession_membership_sha256(
            accessions
        )
    )

    if (
        membership_sha
        != expectations.membership_sha256
    ):
        raise MonthlyRepresentativeError(
            "Stage 11 membership changed"
        )

    species_mapping_sha = (
        monthly_geometry
        ._species_mapping_sha256(
            accessions,
            species_ids,
        )
    )

    if (
        species_mapping_sha
        != expectations.species_mapping_sha256
    ):
        raise MonthlyRepresentativeError(
            "Stage 11 species mapping changed"
        )

    percentile_array_sha = (
        monthly_geometry
        ._numeric_array_sha256(
            coordinates
        )
    )

    if (
        percentile_array_sha
        != expectations.percentile_array_sha256
    ):
        raise MonthlyRepresentativeError(
            "Stage 11 percentile array changed"
        )

    return Stage11Authority(
        accessions=accessions,
        species_ids=species_ids,
        coordinates=coordinates,
        matrix_sha256=matrix_sha,
        record_sha256=record_sha,
        completion_sha256=completion_sha,
        membership_sha256=membership_sha,
        species_mapping_sha256=species_mapping_sha,
        percentile_array_sha256=percentile_array_sha,
        species_count=expectations.species_count,
    )


def build_representatives(
    stage11: Stage11Authority,
) -> RepresentativeBuild:
    indices = (
        ops_species_representatives(
            stage11.coordinates,
            stage11.species_ids,
            stage11.accessions,
        )
    )

    if indices.shape != (
        stage11.species_count,
    ):
        raise MonthlyRepresentativeError(
            "OPS representative count changed"
        )

    if (
        np.unique(
            indices
        ).size
        != stage11.species_count
    ):
        raise MonthlyRepresentativeError(
            "OPS representatives contain duplicate indices"
        )

    if np.any(
        indices < 0
    ) or np.any(
        indices
        >= len(
            stage11.accessions
        )
    ):
        raise MonthlyRepresentativeError(
            "OPS representative index outside Stage 11 universe"
        )

    rows = tuple(
        RepresentativeRow(
            species_taxid=(
                stage11.species_ids[
                    int(index)
                ]
            ),
            accession=(
                stage11.accessions[
                    int(index)
                ]
            ),
            source_index=int(
                index
            ),
        )
        for index in indices
    )

    representative_species = {
        row.species_taxid
        for row in rows
    }

    if len(
        representative_species
    ) != stage11.species_count:
        raise MonthlyRepresentativeError(
            "OPS did not choose exactly one representative per species"
        )

    if representative_species != set(
        stage11.species_ids
    ):
        raise MonthlyRepresentativeError(
            "OPS representative species set changed"
        )

    accessions = tuple(
        row.accession
        for row in rows
    )

    if len(
        set(
            accessions
        )
    ) != stage11.species_count:
        raise MonthlyRepresentativeError(
            "OPS representative accessions are not unique"
        )

    expected_order = tuple(
        sorted(
            accessions,
            key=tie_key,
        )
    )

    if accessions != expected_order:
        raise MonthlyRepresentativeError(
            "OPS representative ordering changed"
        )

    return RepresentativeBuild(
        rows=rows,
        representative_sequence_sha256=(
            sequence_sha256(
                REPRESENTATIVE_NAMESPACE,
                accessions,
            )
        ),
        representative_membership_sha256=(
            accession_membership_sha256(
                accessions
            )
        ),
        representative_count=len(
            rows
        ),
    )


def serialize_representative_table(
    build: RepresentativeBuild,
) -> bytes:
    if not isinstance(
        build,
        RepresentativeBuild,
    ):
        raise TypeError(
            "representative build has wrong type"
        )

    output = [
        "\t".join(
            TABLE_FIELDS
        )
        + "\n"
    ]

    for row in build.rows:
        output.append(
            "\t".join(
                (
                    row.species_taxid,
                    row.accession,
                )
            )
            + "\n"
        )

    return "".join(
        output
    ).encode(
        "ascii"
    )


def parse_representative_table(
    payload: bytes,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
]:
    try:
        text = payload.decode(
            "ascii"
        )
    except UnicodeDecodeError as exc:
        raise MonthlyRepresentativeError(
            "representative table is not ASCII"
        ) from exc

    lines = text.splitlines()

    if not lines:
        raise MonthlyRepresentativeError(
            "representative table is empty"
        )

    if tuple(
        lines[0].split(
            "\t"
        )
    ) != TABLE_FIELDS:
        raise MonthlyRepresentativeError(
            "representative table header changed"
        )

    species_ids: list[str] = []
    accessions: list[str] = []

    for line in lines[
        1:
    ]:
        fields = line.split(
            "\t"
        )

        if len(
            fields
        ) != 2:
            raise MonthlyRepresentativeError(
                "representative table row width changed"
            )

        species_taxid, accession = fields

        if (
            _TAXID_RE.fullmatch(
                species_taxid
            )
            is None
        ):
            raise MonthlyRepresentativeError(
                "representative table contains malformed species TaxID"
            )

        if (
            _GCA_RE.fullmatch(
                accession
            )
            is None
        ):
            raise MonthlyRepresentativeError(
                "representative table contains malformed accession"
            )

        species_ids.append(
            species_taxid
        )

        accessions.append(
            accession
        )

    if len(
        species_ids
    ) != len(
        set(
            species_ids
        )
    ):
        raise MonthlyRepresentativeError(
            "representative table contains duplicate species"
        )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlyRepresentativeError(
            "representative table contains duplicate accessions"
        )

    return (
        tuple(
            species_ids
        ),
        tuple(
            accessions
        ),
    )


def _validate_roundtrip(
    build: RepresentativeBuild,
    table_payload: bytes,
) -> None:
    (
        species_ids,
        accessions,
    ) = parse_representative_table(
        table_payload
    )

    if species_ids != tuple(
        row.species_taxid
        for row in build.rows
    ):
        raise MonthlyRepresentativeError(
            "written representative species order changed"
        )

    if accessions != tuple(
        row.accession
        for row in build.rows
    ):
        raise MonthlyRepresentativeError(
            "written representative accession order changed"
        )

    observed_sequence_sha = (
        sequence_sha256(
            REPRESENTATIVE_NAMESPACE,
            accessions,
        )
    )

    if (
        observed_sequence_sha
        != build.representative_sequence_sha256
    ):
        raise MonthlyRepresentativeError(
            "written representative sequence identity changed"
        )

    observed_membership_sha = (
        accession_membership_sha256(
            accessions
        )
    )

    if (
        observed_membership_sha
        != build.representative_membership_sha256
    ):
        raise MonthlyRepresentativeError(
            "written representative membership changed"
        )


def build_execution_record(
    *,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    stage11: Stage11Authority,
    build: RepresentativeBuild,
    table_sha256: str,
) -> bytes:
    _require_sha(
        table_sha256,
        label="Stage 12 representative table SHA256",
    )

    payload = {
        "schema_version":
            RECORD_SCHEMA,
        "status":
            STATUS,
        "release_id":
            release_id,
        "source_snapshot_id":
            source_snapshot_id,
        "execution_commit":
            execution_commit,
        "stage11_matrix_sha256":
            stage11.matrix_sha256,
        "stage11_record_sha256":
            stage11.record_sha256,
        "stage11_completion_sha256":
            stage11.completion_sha256,
        "membership_sha256":
            stage11.membership_sha256,
        "species_mapping_sha256":
            stage11.species_mapping_sha256,
        "percentile_numeric_array_sha256":
            stage11.percentile_array_sha256,
        "selector_version":
            "1.0.0",
        "selector_decision":
            "OPS",
        "selector_decision_record_sha256":
            EXPECTED_SELECTOR_DECISION_SHA256,
        "ops_sha256":
            EXPECTED_OPS_SHA256,
        "ops_test_sha256":
            EXPECTED_OPS_TEST_SHA256,
        "tie_sha256":
            EXPECTED_TIE_SHA256,
        "tie_test_sha256":
            EXPECTED_TIE_TEST_SHA256,
        "environment_lock_sha256":
            EXPECTED_ENVIRONMENT_LOCK_SHA256,
        "representative_count":
            build.representative_count,
        "species_count":
            stage11.species_count,
        "representative_sequence_sha256":
            build.representative_sequence_sha256,
        "representative_membership_sha256":
            build.representative_membership_sha256,
        "representative_table_sha256":
            table_sha256,
        "incumbency_preference_used":
            False,
        "previous_panel_membership_used":
            False,
        "ops_ladder_constructed":
            False,
        "sr_executed":
            False,
        "ag_executed":
            False,
        "selector_resolution_rerun":
            False,
        "panels_generated":
            False,
        "coverage_generated":
            False,
    }

    return _canonical_json(
        payload
    )


def build_completion_receipt(
    *,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    stage11: Stage11Authority,
    build: RepresentativeBuild,
    table_sha256: str,
    record_sha256: str,
) -> bytes:
    _require_sha(
        table_sha256,
        label="Stage 12 representative table SHA256",
    )

    _require_sha(
        record_sha256,
        label="Stage 12 record SHA256",
    )

    payload = {
        "schema_version":
            COMPLETION_SCHEMA,
        "status":
            STATUS,
        "release_id":
            release_id,
        "source_snapshot_id":
            source_snapshot_id,
        "execution_commit":
            execution_commit,
        "stage11_matrix_sha256":
            stage11.matrix_sha256,
        "stage11_record_sha256":
            stage11.record_sha256,
        "stage11_completion_sha256":
            stage11.completion_sha256,
        "membership_sha256":
            stage11.membership_sha256,
        "species_mapping_sha256":
            stage11.species_mapping_sha256,
        "percentile_numeric_array_sha256":
            stage11.percentile_array_sha256,
        "representative_count":
            build.representative_count,
        "species_count":
            stage11.species_count,
        "representative_sequence_sha256":
            build.representative_sequence_sha256,
        "representative_membership_sha256":
            build.representative_membership_sha256,
        "representative_table_sha256":
            table_sha256,
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
        raise MonthlyRepresentativeError(
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
    table_payload: bytes,
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
        raise MonthlyRepresentativeError(
            "canonical Stage 12 directory already exists"
        )

    if os.path.lexists(
        partial
    ):
        raise MonthlyRepresentativeError(
            "partial Stage 12 directory already exists"
        )

    partial.mkdir()

    _write_fresh(
        partial
        / TABLE_NAME,
        table_payload,
    )

    _write_fresh(
        partial
        / RECORD_NAME,
        record_payload,
    )

    observed = {
        path.name
        for path in partial.iterdir()
    }

    if observed != STAGE_FILES:
        raise MonthlyRepresentativeError(
            "partial Stage 12 artifact inventory changed"
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
        raise MonthlyRepresentativeError(
            "Stage 12 completion already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlyRepresentativeError(
            "Stage 12 completion temporary artifact already exists"
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


def execute_monthly_species_representatives(
    *,
    repo: Path,
    stage1_root: Path,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    stability_check: Callable[[], None] | None = None,
) -> MonthlyRepresentativeExecutionResult:
    root = repository_preflight(
        repo,
        execution_commit=execution_commit,
    )

    verify_frozen_dependencies(
        root
    )

    verify_selector_decision(
        root
    )

    if release_id != RELEASE_ID:
        raise MonthlyRepresentativeError(
            "unexpected monthly release ID"
        )

    if (
        source_snapshot_id
        != SOURCE_SNAPSHOT_ID
    ):
        raise MonthlyRepresentativeError(
            "unexpected monthly source snapshot"
        )

    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    for path, label in (
        (
            stage1
            / STAGE_NAME,
            "canonical Stage 12 stage",
        ),
        (
            stage1
            / PARTIAL_NAME,
            "partial Stage 12 stage",
        ),
        (
            stage1
            / COMPLETION_NAME,
            "Stage 12 completion",
        ),
        (
            stage1
            / COMPLETION_TEMP_NAME,
            "Stage 12 completion temporary artifact",
        ),
    ):
        if os.path.lexists(
            path
        ):
            raise MonthlyRepresentativeError(
                f"{label} already exists"
            )

    stage11 = authenticate_stage11(
        stage1
    )

    build = build_representatives(
        stage11
    )

    table_payload = (
        serialize_representative_table(
            build
        )
    )

    _validate_roundtrip(
        build,
        table_payload,
    )

    table_sha = hashlib.sha256(
        table_payload
    ).hexdigest()

    record_payload = (
        build_execution_record(
            release_id=release_id,
            source_snapshot_id=source_snapshot_id,
            execution_commit=execution_commit,
            stage11=stage11,
            build=build,
            table_sha256=table_sha,
        )
    )

    record_sha = hashlib.sha256(
        record_payload
    ).hexdigest()

    completion_payload = (
        build_completion_receipt(
            release_id=release_id,
            source_snapshot_id=source_snapshot_id,
            execution_commit=execution_commit,
            stage11=stage11,
            build=build,
            table_sha256=table_sha,
            record_sha256=record_sha,
        )
    )

    completion_sha = hashlib.sha256(
        completion_payload
    ).hexdigest()

    check = (
        stability_check
        if stability_check is not None
        else lambda: None
    )

    stage_path = publish_stage(
        stage1_root=stage1,
        table_payload=table_payload,
        record_payload=record_payload,
        stability_check=check,
    )

    completion_path = publish_completion(
        stage1_root=stage1,
        payload=completion_payload,
        stability_check=check,
    )

    return MonthlyRepresentativeExecutionResult(
        stage_path=stage_path,
        completion_path=completion_path,
        table_sha256=table_sha,
        record_sha256=record_sha,
        completion_sha256=completion_sha,
        representative_sequence_sha256=(
            build.representative_sequence_sha256
        ),
        representative_membership_sha256=(
            build.representative_membership_sha256
        ),
        representative_count=(
            build.representative_count
        ),
    )
