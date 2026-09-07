#!/usr/bin/env python3
"""Monthly Stage 11 species-balanced percentile geometry.

This wrapper authenticates the completed monthly Stage 10 raw structural
feature space, recomputes species-balanced percentile coordinates over the
complete current monthly universe using the frozen BacSelect geometry
primitive, and atomically publishes Stage 11 evidence.

It does not construct species representatives, run OPS, generate panels,
calculate coverage, or perform selector-resolution analysis.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
from typing import Callable, Mapping

import numpy as np
import numpy.typing as npt

from bacselect import monthly_geometry
from bacselect.monthly_structural_features import (
    FEATURE_FIELDS,
    accession_membership_sha256,
)


RELEASE_ID = "2026.09"

SOURCE_SNAPSHOT_ID = (
    "bacselect-source-2026.09-20260901T021652Z"
)

REMOTE_BRANCH = (
    "origin/recovery/monthly-missing-datasets-gbff"
)

STAGE10_STAGE_NAME = "structural-features"

STAGE10_MATRIX_NAME = (
    "structural-feature-matrix-300-2400.tsv"
)

STAGE10_PROVENANCE_NAME = (
    "structural-feature-provenance.tsv"
)

STAGE10_RECORD_NAME = (
    "monthly-structural-feature-record.json"
)

STAGE10_COMPLETION_NAME = (
    "structural-features-completion-v1.json"
)

STAGE_NAME = "percentile-geometry"
PARTIAL_NAME = "percentile-geometry.partial"

MATRIX_NAME = (
    "species-balanced-percentile-feature-matrix-300-2400.tsv"
)

RECORD_NAME = (
    "monthly-percentile-geometry-record.json"
)

COMPLETION_NAME = (
    "percentile-geometry-completion-v1.json"
)

COMPLETION_TEMP_NAME = (
    "percentile-geometry-completion-v1.json.partial"
)

STAGE_FILES = frozenset(
    {
        MATRIX_NAME,
        RECORD_NAME,
    }
)

RECORD_SCHEMA = (
    "bacselect-monthly-percentile-geometry-record-v1"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-percentile-geometry-completion-v1"
)

STATUS = (
    "MONTHLY_SPECIES_BALANCED_PERCENTILE_GEOMETRY_COMPLETE"
)

EXPECTED_STAGE10_EXECUTION_COMMIT = (
    "2fa4e990f9c9f31d010e270b02b0f44e25684e93"
)

EXPECTED_STAGE10_MATRIX_SHA256 = (
    "36d17d35bf245d43d0b1884db5311354"
    "b63383dbef5062ef6ea1aab1d48dab0a"
)

EXPECTED_STAGE10_PROVENANCE_SHA256 = (
    "316e9f0c5e9a3e8e69cd7ecc9c2273c"
    "d2b43b3ae4b5af00d2e3c2699e1a584fd"
)

EXPECTED_STAGE10_RECORD_SHA256 = (
    "683d1b8d7d879f525ea9f5d68144fca0"
    "dbb54660e67c72ad8f1682d037605db0"
)

EXPECTED_STAGE10_COMPLETION_SHA256 = (
    "9c40b8eda35be55280cc16034980701a3"
    "2c2521767fc4a8203d654a8884e32fe"
)

EXPECTED_STAGE10_RAW_NUMERIC_ARRAY_SHA256 = (
    "c7049f056a839a0aee24d57c3d4f4109"
    "e16a8eb659d8c2a9b904b1ae9cd8fc36"
)

EXPECTED_MEMBERSHIP_SHA256 = (
    "6e6b44bd598bf472ea2a74686aaabcd23"
    "058832979fb13a4d8ae6cdf7607d"
)

EXPECTED_TOTAL_COUNT = 68164
EXPECTED_SPECIES_COUNT = 16223
EXPECTED_FEATURE_COUNT = 12

EXPECTED_MONTHLY_GEOMETRY_CORE_SHA256 = (
    "ac8bbc94a2bacae8c8e80de1f5a9d65b"
    "e886d59a2e72386ce82de8a5da23297e"
)

EXPECTED_MONTHLY_GEOMETRY_TEST_SHA256 = (
    "17d7f94e54b2b778d0774617fe5d7285d"
    "4c5a394e704306a84b67e917a615595"
)

EXPECTED_GEOMETRY_SHA256 = (
    "fbebf436d049be063817b717878330f38"
    "e09b3e7cb79f9dbc1b8f704af6a0d69"
)

EXPECTED_GEOMETRY_TEST_SHA256 = (
    "8c215ea881985a8d7fd83b59ee3a9ce4"
    "e1ebe5a0ffe64352d2077f098ecedec1"
)

EXPECTED_ENVIRONMENT_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207eaef"
    "5c2435e1b6feeddc1e4654686bc2a8c"
)

FROZEN_REPO_FILES: Mapping[str, str] = {
    "src/bacselect/monthly_geometry.py":
        EXPECTED_MONTHLY_GEOMETRY_CORE_SHA256,
    "tests/test_monthly_geometry.py":
        EXPECTED_MONTHLY_GEOMETRY_TEST_SHA256,
    "src/bacselect/geometry.py":
        EXPECTED_GEOMETRY_SHA256,
    "tests/test_geometry.py":
        EXPECTED_GEOMETRY_TEST_SHA256,
    "envs/bacselect-dev-linux-64.lock":
        EXPECTED_ENVIRONMENT_LOCK_SHA256,
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


class MonthlyGeometryWrapperError(RuntimeError):
    """Raised when monthly Stage 11 execution cannot be authenticated."""


@dataclass(frozen=True)
class Stage10Expectations:
    release_id: str
    source_snapshot_id: str
    execution_commit: str
    matrix_sha256: str
    provenance_sha256: str
    record_sha256: str
    completion_sha256: str
    raw_numeric_array_sha256: str
    membership_sha256: str
    total_count: int
    species_count: int


PRODUCTION_EXPECTATIONS = Stage10Expectations(
    release_id=RELEASE_ID,
    source_snapshot_id=SOURCE_SNAPSHOT_ID,
    execution_commit=EXPECTED_STAGE10_EXECUTION_COMMIT,
    matrix_sha256=EXPECTED_STAGE10_MATRIX_SHA256,
    provenance_sha256=EXPECTED_STAGE10_PROVENANCE_SHA256,
    record_sha256=EXPECTED_STAGE10_RECORD_SHA256,
    completion_sha256=EXPECTED_STAGE10_COMPLETION_SHA256,
    raw_numeric_array_sha256=(
        EXPECTED_STAGE10_RAW_NUMERIC_ARRAY_SHA256
    ),
    membership_sha256=EXPECTED_MEMBERSHIP_SHA256,
    total_count=EXPECTED_TOTAL_COUNT,
    species_count=EXPECTED_SPECIES_COUNT,
)


@dataclass(frozen=True)
class Stage10Authority:
    accessions: tuple[str, ...]
    species_ids: tuple[str, ...]
    raw: npt.NDArray[np.float64]
    matrix_sha256: str
    provenance_sha256: str
    record_sha256: str
    completion_sha256: str
    raw_numeric_array_sha256: str
    membership_sha256: str
    species_count: int


@dataclass(frozen=True)
class MonthlyGeometryExecutionResult:
    stage_path: Path
    completion_path: Path
    matrix_sha256: str
    record_sha256: str
    completion_sha256: str
    raw_numeric_array_sha256: str
    percentile_numeric_array_sha256: str
    membership_sha256: str
    species_mapping_sha256: str
    total_count: int
    species_count: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def _require_sha(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or _SHA_RE.fullmatch(value) is None
    ):
        raise MonthlyGeometryWrapperError(
            f"{label} is not a lowercase SHA256"
        )

    return value


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
        raise MonthlyGeometryWrapperError(
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

    if _COMMIT_RE.fullmatch(execution_commit) is None:
        raise MonthlyGeometryWrapperError(
            "Stage 11 execution commit is malformed"
        )

    if _git(root, "rev-parse", "HEAD") != execution_commit:
        raise MonthlyGeometryWrapperError(
            "repository HEAD differs from Stage 11 execution commit"
        )

    if (
        _git(
            root,
            "rev-parse",
            REMOTE_BRANCH,
        )
        != execution_commit
    ):
        raise MonthlyGeometryWrapperError(
            "remote Stage 11 branch differs from execution commit"
        )

    if _git(root, "status", "--porcelain"):
        raise MonthlyGeometryWrapperError(
            "repository working tree is not clean"
        )

    return root


def verify_frozen_dependencies(
    repo: Path,
) -> Mapping[str, str]:
    observed: dict[str, str] = {}

    for relative, expected in FROZEN_REPO_FILES.items():
        path = repo / relative

        if (
            not path.is_file()
            or path.is_symlink()
        ):
            raise MonthlyGeometryWrapperError(
                f"frozen Stage 11 dependency missing: {relative}"
            )

        digest = sha256_file(path)

        if digest != expected:
            raise MonthlyGeometryWrapperError(
                f"frozen Stage 11 dependency changed: {relative}"
            )

        observed[relative] = digest

    return dict(sorted(observed.items()))


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
        raise MonthlyGeometryWrapperError(
            f"{label} missing: {path}"
        )

    observed = sha256_file(path)

    if observed != expected_sha256:
        raise MonthlyGeometryWrapperError(
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
        raise MonthlyGeometryWrapperError(
            f"cannot parse {label}"
        ) from exc

    if not isinstance(payload, dict):
        raise MonthlyGeometryWrapperError(
            f"{label} must be a JSON object"
        )

    return payload


def _validate_stage10_record(
    record: Mapping[str, object],
    expectations: Stage10Expectations,
) -> None:
    required = {
        "status":
            "MONTHLY_RAW_STRUCTURAL_FEATURES_COMPLETE",
        "release_id":
            expectations.release_id,
        "source_snapshot_id":
            expectations.source_snapshot_id,
        "execution_commit":
            expectations.execution_commit,
        "matrix_sha256":
            expectations.matrix_sha256,
        "provenance_sha256":
            expectations.provenance_sha256,
        "membership_sha256":
            expectations.membership_sha256,
        "numeric_array_sha256":
            expectations.raw_numeric_array_sha256,
        "total_count":
            expectations.total_count,
        "percentile_coordinates_calculated":
            False,
        "selector_outcomes_calculated":
            False,
        "nested_panels_calculated":
            False,
    }

    for key, expected in required.items():
        if record.get(key) != expected:
            raise MonthlyGeometryWrapperError(
                f"Stage 10 record {key} mismatch"
            )


def _validate_stage10_completion(
    completion: Mapping[str, object],
    expectations: Stage10Expectations,
) -> None:
    required = {
        "status":
            "MONTHLY_RAW_STRUCTURAL_FEATURES_COMPLETE",
        "release_id":
            expectations.release_id,
        "source_snapshot_id":
            expectations.source_snapshot_id,
        "execution_commit":
            expectations.execution_commit,
        "matrix_sha256":
            expectations.matrix_sha256,
        "provenance_sha256":
            expectations.provenance_sha256,
        "record_sha256":
            expectations.record_sha256,
        "membership_sha256":
            expectations.membership_sha256,
        "numeric_array_sha256":
            expectations.raw_numeric_array_sha256,
        "total_count":
            expectations.total_count,
    }

    for key, expected in required.items():
        if completion.get(key) != expected:
            raise MonthlyGeometryWrapperError(
                f"Stage 10 completion {key} mismatch"
            )


def _parse_stage10_matrix(
    path: Path,
    *,
    expectations: Stage10Expectations,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    npt.NDArray[np.float64],
]:
    try:
        with path.open(
            newline="",
            encoding="ascii",
        ) as handle:
            reader = csv.DictReader(
                handle,
                delimiter="\t",
            )

            fields = tuple(
                reader.fieldnames
                or ()
            )

            if fields != monthly_geometry.MATRIX_FIELDS:
                raise MonthlyGeometryWrapperError(
                    "Stage 10 matrix header changed"
                )

            rows = list(reader)
    except UnicodeDecodeError as exc:
        raise MonthlyGeometryWrapperError(
            "Stage 10 matrix is not ASCII"
        ) from exc

    if len(rows) != expectations.total_count:
        raise MonthlyGeometryWrapperError(
            "Stage 10 matrix row count changed"
        )

    accessions: list[str] = []
    species_ids: list[str] = []
    numeric_rows: list[list[float]] = []

    seen: set[str] = set()

    for row in rows:
        accession = row.get(
            monthly_geometry.ACCESSION_FIELD,
            "",
        )

        species_taxid = row.get(
            monthly_geometry.SPECIES_FIELD,
            "",
        )

        if (
            not isinstance(accession, str)
            or _GCA_RE.fullmatch(accession) is None
        ):
            raise MonthlyGeometryWrapperError(
                "Stage 10 matrix contains malformed accession"
            )

        if accession in seen:
            raise MonthlyGeometryWrapperError(
                "Stage 10 matrix contains duplicate accession"
            )

        seen.add(accession)

        if (
            not isinstance(species_taxid, str)
            or _TAXID_RE.fullmatch(species_taxid) is None
        ):
            raise MonthlyGeometryWrapperError(
                "Stage 10 matrix contains malformed species TaxID"
            )

        try:
            numeric = [
                float(
                    row[field]
                )
                for field in FEATURE_FIELDS
            ]
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise MonthlyGeometryWrapperError(
                "Stage 10 matrix contains malformed feature value"
            ) from exc

        if not all(
            math.isfinite(value)
            for value in numeric
        ):
            raise MonthlyGeometryWrapperError(
                "Stage 10 matrix contains non-finite feature value"
            )

        accessions.append(accession)
        species_ids.append(species_taxid)
        numeric_rows.append(numeric)

    raw = np.asarray(
        numeric_rows,
        dtype=np.float64,
    )

    expected_shape = (
        expectations.total_count,
        EXPECTED_FEATURE_COUNT,
    )

    if raw.shape != expected_shape:
        raise MonthlyGeometryWrapperError(
            "Stage 10 numeric matrix shape changed"
        )

    return (
        tuple(accessions),
        tuple(species_ids),
        raw,
    )


def authenticate_stage10(
    stage1_root: Path,
    *,
    expectations: Stage10Expectations = PRODUCTION_EXPECTATIONS,
) -> Stage10Authority:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    stage = stage1 / STAGE10_STAGE_NAME

    if (
        not stage.is_dir()
        or stage.is_symlink()
    ):
        raise MonthlyGeometryWrapperError(
            "canonical Stage 10 directory missing"
        )

    matrix_path = (
        stage
        / STAGE10_MATRIX_NAME
    )

    provenance_path = (
        stage
        / STAGE10_PROVENANCE_NAME
    )

    record_path = (
        stage
        / STAGE10_RECORD_NAME
    )

    completion_path = (
        stage1
        / STAGE10_COMPLETION_NAME
    )

    matrix_sha = _require_artifact(
        matrix_path,
        expectations.matrix_sha256,
        label="Stage 10 matrix",
    )

    provenance_sha = _require_artifact(
        provenance_path,
        expectations.provenance_sha256,
        label="Stage 10 provenance",
    )

    record_sha = _require_artifact(
        record_path,
        expectations.record_sha256,
        label="Stage 10 record",
    )

    completion_sha = _require_artifact(
        completion_path,
        expectations.completion_sha256,
        label="Stage 10 completion",
    )

    record = _load_json(
        record_path,
        label="Stage 10 record",
    )

    completion = _load_json(
        completion_path,
        label="Stage 10 completion",
    )

    _validate_stage10_record(
        record,
        expectations,
    )

    _validate_stage10_completion(
        completion,
        expectations,
    )

    (
        accessions,
        species_ids,
        raw,
    ) = _parse_stage10_matrix(
        matrix_path,
        expectations=expectations,
    )

    membership_sha = (
        accession_membership_sha256(
            accessions
        )
    )

    if membership_sha != expectations.membership_sha256:
        raise MonthlyGeometryWrapperError(
            "Stage 10 matrix membership changed"
        )

    species_count = len(
        set(
            species_ids
        )
    )

    if species_count != expectations.species_count:
        raise MonthlyGeometryWrapperError(
            "Stage 10 matrix species count changed"
        )

    raw_numeric_sha = (
        monthly_geometry
        ._numeric_array_sha256(
            raw
        )
    )

    if (
        raw_numeric_sha
        != expectations.raw_numeric_array_sha256
    ):
        raise MonthlyGeometryWrapperError(
            "Stage 10 raw numeric array changed"
        )

    return Stage10Authority(
        accessions=accessions,
        species_ids=species_ids,
        raw=raw,
        matrix_sha256=matrix_sha,
        provenance_sha256=provenance_sha,
        record_sha256=record_sha,
        completion_sha256=completion_sha,
        raw_numeric_array_sha256=raw_numeric_sha,
        membership_sha256=membership_sha,
        species_count=species_count,
    )


def build_geometry(
    stage10: Stage10Authority,
) -> monthly_geometry.MonthlyGeometryBuild:
    build = (
        monthly_geometry
        .build_monthly_geometry(
            stage10.accessions,
            stage10.species_ids,
            stage10.raw,
        )
    )

    if (
        len(build.rows)
        != len(stage10.accessions)
    ):
        raise MonthlyGeometryWrapperError(
            "Stage 11 row count changed"
        )

    if build.species_count != stage10.species_count:
        raise MonthlyGeometryWrapperError(
            "Stage 11 species count changed"
        )

    if build.membership_sha256 != stage10.membership_sha256:
        raise MonthlyGeometryWrapperError(
            "Stage 11 membership changed"
        )

    if (
        build.raw_numeric_array_sha256
        != stage10.raw_numeric_array_sha256
    ):
        raise MonthlyGeometryWrapperError(
            "Stage 11 raw numeric input changed"
        )

    return build


def _validate_roundtrip(
    build: monthly_geometry.MonthlyGeometryBuild,
    matrix_payload: bytes,
) -> None:
    (
        accessions,
        species_ids,
        coordinates,
    ) = (
        monthly_geometry
        .parse_monthly_geometry_matrix(
            matrix_payload
        )
    )

    expected_accessions = tuple(
        row.accession
        for row in build.rows
    )

    expected_species = tuple(
        row.species_taxid
        for row in build.rows
    )

    if accessions != expected_accessions:
        raise MonthlyGeometryWrapperError(
            "written Stage 11 accession order changed"
        )

    if species_ids != expected_species:
        raise MonthlyGeometryWrapperError(
            "written Stage 11 species mapping changed"
        )

    observed_array_sha = (
        monthly_geometry
        ._numeric_array_sha256(
            coordinates
        )
    )

    if (
        observed_array_sha
        != build.percentile_numeric_array_sha256
    ):
        raise MonthlyGeometryWrapperError(
            "written Stage 11 percentile array changed"
        )


def build_execution_record(
    *,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    stage10: Stage10Authority,
    build: monthly_geometry.MonthlyGeometryBuild,
    matrix_sha256: str,
) -> bytes:
    _require_sha(
        matrix_sha256,
        label="Stage 11 percentile matrix SHA256",
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
        "stage10_matrix_sha256":
            stage10.matrix_sha256,
        "stage10_provenance_sha256":
            stage10.provenance_sha256,
        "stage10_record_sha256":
            stage10.record_sha256,
        "stage10_completion_sha256":
            stage10.completion_sha256,
        "raw_numeric_array_sha256":
            build.raw_numeric_array_sha256,
        "membership_sha256":
            build.membership_sha256,
        "species_mapping_sha256":
            build.species_mapping_sha256,
        "percentile_matrix_sha256":
            matrix_sha256,
        "percentile_numeric_array_sha256":
            build.percentile_numeric_array_sha256,
        "total_count":
            len(build.rows),
        "species_count":
            build.species_count,
        "feature_count":
            len(FEATURE_FIELDS),
        "monthly_geometry_core_sha256":
            EXPECTED_MONTHLY_GEOMETRY_CORE_SHA256,
        "geometry_primitive_sha256":
            EXPECTED_GEOMETRY_SHA256,
        "geometry_primitive_test_sha256":
            EXPECTED_GEOMETRY_TEST_SHA256,
        "environment_lock_sha256":
            EXPECTED_ENVIRONMENT_LOCK_SHA256,
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

    return _canonical_json(
        payload
    )


def build_completion_receipt(
    *,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    stage10: Stage10Authority,
    build: monthly_geometry.MonthlyGeometryBuild,
    matrix_sha256: str,
    record_sha256: str,
) -> bytes:
    _require_sha(
        matrix_sha256,
        label="Stage 11 percentile matrix SHA256",
    )

    _require_sha(
        record_sha256,
        label="Stage 11 record SHA256",
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
        "stage10_matrix_sha256":
            stage10.matrix_sha256,
        "stage10_record_sha256":
            stage10.record_sha256,
        "stage10_completion_sha256":
            stage10.completion_sha256,
        "raw_numeric_array_sha256":
            build.raw_numeric_array_sha256,
        "membership_sha256":
            build.membership_sha256,
        "species_mapping_sha256":
            build.species_mapping_sha256,
        "percentile_matrix_sha256":
            matrix_sha256,
        "percentile_numeric_array_sha256":
            build.percentile_numeric_array_sha256,
        "record_sha256":
            record_sha256,
        "total_count":
            len(build.rows),
        "species_count":
            build.species_count,
        "feature_count":
            len(FEATURE_FIELDS),
    }

    return _canonical_json(
        payload
    )


def _fsync_directory(path: Path) -> None:
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
    if os.path.lexists(path):
        raise MonthlyGeometryWrapperError(
            f"refusing to overwrite existing artifact: {path}"
        )

    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def publish_stage(
    *,
    stage1_root: Path,
    matrix_payload: bytes,
    record_payload: bytes,
    stability_check: Callable[[], None],
) -> Path:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    final = stage1 / STAGE_NAME
    partial = stage1 / PARTIAL_NAME

    if os.path.lexists(final):
        raise MonthlyGeometryWrapperError(
            "canonical Stage 11 directory already exists"
        )

    if os.path.lexists(partial):
        raise MonthlyGeometryWrapperError(
            "partial Stage 11 directory already exists"
        )

    partial.mkdir()

    _write_fresh(
        partial / MATRIX_NAME,
        matrix_payload,
    )

    _write_fresh(
        partial / RECORD_NAME,
        record_payload,
    )

    observed = {
        path.name
        for path in partial.iterdir()
    }

    if observed != STAGE_FILES:
        raise MonthlyGeometryWrapperError(
            "partial Stage 11 artifact inventory changed"
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

    if os.path.lexists(final):
        raise MonthlyGeometryWrapperError(
            "Stage 11 completion already exists"
        )

    if os.path.lexists(temporary):
        raise MonthlyGeometryWrapperError(
            "Stage 11 completion temporary artifact already exists"
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


def execute_monthly_geometry(
    *,
    repo: Path,
    stage1_root: Path,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    stability_check: Callable[[], None] | None = None,
) -> MonthlyGeometryExecutionResult:
    root = repository_preflight(
        repo,
        execution_commit=execution_commit,
    )

    verify_frozen_dependencies(
        root
    )

    if release_id != RELEASE_ID:
        raise MonthlyGeometryWrapperError(
            "unexpected monthly release ID"
        )

    if source_snapshot_id != SOURCE_SNAPSHOT_ID:
        raise MonthlyGeometryWrapperError(
            "unexpected monthly source snapshot"
        )

    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    for path, label in (
        (
            stage1 / STAGE_NAME,
            "canonical Stage 11 stage",
        ),
        (
            stage1 / PARTIAL_NAME,
            "partial Stage 11 stage",
        ),
        (
            stage1 / COMPLETION_NAME,
            "Stage 11 completion",
        ),
        (
            stage1 / COMPLETION_TEMP_NAME,
            "Stage 11 completion temporary artifact",
        ),
    ):
        if os.path.lexists(path):
            raise MonthlyGeometryWrapperError(
                f"{label} already exists"
            )

    stage10 = authenticate_stage10(
        stage1
    )

    build = build_geometry(
        stage10
    )

    matrix_payload = (
        monthly_geometry
        .serialize_monthly_geometry_matrix(
            build
        )
    )

    _validate_roundtrip(
        build,
        matrix_payload,
    )

    matrix_sha = hashlib.sha256(
        matrix_payload
    ).hexdigest()

    record_payload = (
        build_execution_record(
            release_id=release_id,
            source_snapshot_id=source_snapshot_id,
            execution_commit=execution_commit,
            stage10=stage10,
            build=build,
            matrix_sha256=matrix_sha,
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
            stage10=stage10,
            build=build,
            matrix_sha256=matrix_sha,
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
        matrix_payload=matrix_payload,
        record_payload=record_payload,
        stability_check=check,
    )

    completion_path = (
        publish_completion(
            stage1_root=stage1,
            payload=completion_payload,
            stability_check=check,
        )
    )

    return MonthlyGeometryExecutionResult(
        stage_path=stage_path,
        completion_path=completion_path,
        matrix_sha256=matrix_sha,
        record_sha256=record_sha,
        completion_sha256=completion_sha,
        raw_numeric_array_sha256=(
            build.raw_numeric_array_sha256
        ),
        percentile_numeric_array_sha256=(
            build.percentile_numeric_array_sha256
        ),
        membership_sha256=(
            build.membership_sha256
        ),
        species_mapping_sha256=(
            build.species_mapping_sha256
        ),
        total_count=len(
            build.rows
        ),
        species_count=(
            build.species_count
        ),
    )
