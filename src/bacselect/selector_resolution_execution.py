"""Fail-closed filesystem execution adapter for selector-v1 Stage 7."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import struct
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt
import scipy

from bacselect.selector_resolution_analysis import (
    build_blinded_analysis_artifacts,
)
from bacselect.selector_resolution_artifacts import (
    SCIENTIFIC_ARTIFACT_NAMES,
    sha256_bytes,
)
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

POSITIVE_INTEGER_TEXT_RE = re.compile(
    r"^[1-9][0-9]*$"
)

EXECUTION_MODES = (
    "production",
    "independent_rebuild",
)

STAGE7_PROVENANCE_FILES = (
    "stage7-predecision-provenance.json",
    "stage7-execution-provenance.json",
    "stage7-content-manifest.tsv",
)

STAGE7_FINAL_FILES = (
    *SCIENTIFIC_ARTIFACT_NAMES,
    *STAGE7_PROVENANCE_FILES,
)

CONTENT_COVERED_FILES = (
    "stage7-predecision-provenance.json",
    *SCIENTIFIC_ARTIFACT_NAMES,
    "stage7-execution-provenance.json",
)

CONTENT_MANIFEST_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
)


class Stage7ExecutionError(RuntimeError):
    """Raised when Stage 7 execution cannot satisfy its frozen contract."""


class FoundationLike(Protocol):
    """Minimum frozen-baseline interface consumed by this adapter."""

    raw: npt.NDArray[np.float64]
    coordinates: npt.NDArray[np.float64]
    species_ids: list[str]
    accessions: list[str]


@dataclass(frozen=True)
class Stage6MatrixExpectations:
    """Frozen identity and composition of the Stage 6 matrix."""

    artifact_sha256: str
    numeric_array_sha256: str
    membership_sha256: str
    row_count: int
    species_count: int


@dataclass(frozen=True)
class Stage7FrozenBindings:
    """Identity-only provenance frozen before Stage 7 data access."""

    stage7_method_sha256: str
    selector_resolution_design_sha256: str
    stage6_completion_evidence_sha256: str
    environment_lock_sha256: str
    baseline_bindings: Mapping[str, str]
    implementation_bindings: Mapping[str, str]
    final_ladder_sha256: Mapping[str, str]


@dataclass(frozen=True)
class VerifiedStage6Matrix:
    """Verified Stage 6 holdout matrix held only in memory."""

    raw: npt.NDArray[np.float64]
    species_ids: list[str]
    accessions: list[str]
    artifact_sha256: str
    numeric_array_sha256: str
    membership_sha256: str


def _validate_sha256(
    value: object,
    *,
    label: str,
) -> str:
    text = str(
        value
    ).strip()

    if LOWER_SHA256_RE.fullmatch(
        text
    ) is None:
        raise Stage7ExecutionError(
            f"{label} is not a lowercase SHA256"
        )

    return text


def _validate_frozen_bindings(
    bindings: Stage7FrozenBindings,
) -> None:
    _validate_sha256(
        bindings.stage7_method_sha256,
        label="Stage 7 method SHA256",
    )

    _validate_sha256(
        bindings.selector_resolution_design_sha256,
        label="selector-resolution design SHA256",
    )

    _validate_sha256(
        bindings.stage6_completion_evidence_sha256,
        label="Stage 6 completion-evidence SHA256",
    )

    _validate_sha256(
        bindings.environment_lock_sha256,
        label="environment-lock SHA256",
    )

    if not bindings.baseline_bindings:
        raise Stage7ExecutionError(
            "baseline bindings must not be empty"
        )

    if not bindings.implementation_bindings:
        raise Stage7ExecutionError(
            "implementation bindings must not be empty"
        )

    for label, value in bindings.baseline_bindings.items():
        if not isinstance(
            label,
            str,
        ) or not label:
            raise Stage7ExecutionError(
                "baseline binding key invalid"
            )

        _validate_sha256(
            value,
            label=f"baseline binding {label}",
        )

    for label, value in bindings.implementation_bindings.items():
        if not isinstance(
            label,
            str,
        ) or not label:
            raise Stage7ExecutionError(
                "implementation binding key invalid"
            )

        _validate_sha256(
            value,
            label=f"implementation binding {label}",
        )

    if set(
        bindings.final_ladder_sha256
    ) != {
        "OPS",
        "SR",
    }:
        raise Stage7ExecutionError(
            "final ladder bindings must contain exactly OPS and SR"
        )

    for selector in (
        "OPS",
        "SR",
    ):
        _validate_sha256(
            bindings.final_ladder_sha256[
                selector
            ],
            label=f"{selector} final ladder SHA256",
        )


def _validate_stage6_expectations(
    expectations: Stage6MatrixExpectations,
) -> None:
    _validate_sha256(
        expectations.artifact_sha256,
        label="Stage 6 matrix artifact SHA256",
    )

    _validate_sha256(
        expectations.numeric_array_sha256,
        label="Stage 6 matrix numeric-array SHA256",
    )

    _validate_sha256(
        expectations.membership_sha256,
        label="Stage 6 matrix membership SHA256",
    )

    if expectations.row_count <= 0:
        raise Stage7ExecutionError(
            "Stage 6 matrix row count must be positive"
        )

    if expectations.species_count <= 0:
        raise Stage7ExecutionError(
            "Stage 6 matrix species count must be positive"
        )

    if expectations.species_count > expectations.row_count:
        raise Stage7ExecutionError(
            "Stage 6 species count exceeds row count"
        )


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        for chunk in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def write_bytes_atomic(
    path: Path,
    payload: bytes,
) -> str:
    path = Path(
        path
    )

    temporary = path.with_name(
        "."
        + path.name
        + ".tmp"
    )

    if temporary.exists():
        raise Stage7ExecutionError(
            "temporary byte-output path already exists"
        )

    try:
        temporary.write_bytes(
            payload
        )

        os.replace(
            temporary,
            path,
        )
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise

    return sha256_file(
        path
    )


def _canonical_json_bytes(
    payload: object,
) -> bytes:
    try:
        return (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode(
            "utf-8"
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise Stage7ExecutionError(
            "provenance payload is not canonical JSON"
        ) from exc


def write_json_atomic(
    path: Path,
    payload: object,
) -> str:
    return write_bytes_atomic(
        path,
        _canonical_json_bytes(
            payload
        ),
    )


def write_tsv_atomic(
    path: Path,
    fields: Sequence[str],
    rows: Sequence[
        Mapping[str, object]
    ],
) -> str:
    buffer = io.StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        buffer,
        fieldnames=list(
            fields
        ),
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )

    writer.writeheader()

    for row in rows:
        if set(
            row
        ) != set(
            fields
        ):
            raise Stage7ExecutionError(
                "TSV row field set mismatch"
            )

        writer.writerow(
            row
        )

    return write_bytes_atomic(
        path,
        buffer.getvalue().encode(
            "utf-8"
        ),
    )


def _ensure_output_root_outside_repo(
    output_root: Path,
    repo: Path,
) -> Path:
    root = Path(
        output_root
    ).resolve()

    repository = Path(
        repo
    ).resolve()

    if (
        root == repository
        or repository in root.parents
    ):
        raise Stage7ExecutionError(
            "Stage 7 output root must be outside repository"
        )

    return root


def _numeric_array_sha256(
    matrix: npt.NDArray[np.float64],
) -> str:
    if (
        matrix.ndim != 2
        or not np.all(
            np.isfinite(
                matrix
            )
        )
    ):
        raise Stage7ExecutionError(
            "Stage 7 numeric matrix invalid"
        )

    digest = hashlib.sha256()

    for row in matrix:
        for value in row:
            digest.update(
                struct.pack(
                    "<d",
                    float(
                        value
                    ),
                )
            )

    return digest.hexdigest()


def load_verified_stage6_matrix(
    path: Path,
    *,
    expectations: Stage6MatrixExpectations,
    feature_names: Sequence[str],
) -> VerifiedStage6Matrix:
    """Open and fail-closed verify one frozen Stage 6 matrix."""
    _validate_stage6_expectations(
        expectations
    )

    current = Path(
        path
    )

    if (
        not current.is_file()
        or current.is_symlink()
    ):
        raise Stage7ExecutionError(
            "Stage 6 matrix is not a regular non-symlink file"
        )

    payload = current.read_bytes()

    artifact_sha = hashlib.sha256(
        payload
    ).hexdigest()

    if (
        artifact_sha
        != expectations.artifact_sha256
    ):
        raise Stage7ExecutionError(
            "Stage 6 matrix artifact SHA256 mismatch"
        )

    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise Stage7ExecutionError(
            "Stage 6 matrix is not UTF-8"
        ) from exc

    reader = csv.DictReader(
        io.StringIO(
            text,
            newline="",
        ),
        delimiter="\t",
    )

    expected_header = (
        "canonical_genbank_assembly_accession",
        "species_taxid",
        *tuple(
            feature_names
        ),
    )

    if tuple(
        reader.fieldnames or ()
    ) != expected_header:
        raise Stage7ExecutionError(
            "Stage 6 matrix schema changed"
        )

    accessions: list[str] = []
    species_ids: list[str] = []
    raw_rows: list[
        list[float]
    ] = []

    for row in reader:
        if set(
            row
        ) != set(
            expected_header
        ):
            raise Stage7ExecutionError(
                "Stage 6 matrix row schema changed"
            )

        accession = str(
            row[
                "canonical_genbank_assembly_accession"
            ]
        ).strip()

        species_taxid = str(
            row[
                "species_taxid"
            ]
        ).strip()

        if POSITIVE_INTEGER_TEXT_RE.fullmatch(
            species_taxid
        ) is None:
            raise Stage7ExecutionError(
                "Stage 6 matrix species TaxID is not "
                "canonical positive integer text"
            )

        values = []

        for feature in feature_names:
            try:
                value = float(
                    row[
                        feature
                    ]
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise Stage7ExecutionError(
                    "Stage 6 matrix feature is not numeric"
                ) from exc

            if not math.isfinite(
                value
            ):
                raise Stage7ExecutionError(
                    "Stage 6 matrix feature is non-finite"
                )

            values.append(
                value
            )

        accessions.append(
            accession
        )

        species_ids.append(
            species_taxid
        )

        raw_rows.append(
            values
        )

    if len(
        raw_rows
    ) != expectations.row_count:
        raise Stage7ExecutionError(
            "Stage 6 matrix row count mismatch"
        )

    if accessions != sorted(
        accessions
    ):
        raise Stage7ExecutionError(
            "Stage 6 matrix row order is not canonical accession order"
        )

    try:
        membership_sha = (
            accession_membership_sha256(
                accessions
            )
        )
    except ValueError as exc:
        raise Stage7ExecutionError(
            "Stage 6 matrix accession membership invalid"
        ) from exc

    if (
        membership_sha
        != expectations.membership_sha256
    ):
        raise Stage7ExecutionError(
            "Stage 6 matrix membership SHA256 mismatch"
        )

    observed_species_count = len(
        set(
            species_ids
        )
    )

    if (
        observed_species_count
        != expectations.species_count
    ):
        raise Stage7ExecutionError(
            "Stage 6 matrix species count mismatch"
        )

    raw = np.asarray(
        raw_rows,
        dtype=np.float64,
    )

    expected_shape = (
        expectations.row_count,
        len(
            feature_names
        ),
    )

    if raw.shape != expected_shape:
        raise Stage7ExecutionError(
            "Stage 6 matrix numeric shape mismatch"
        )

    numeric_sha = _numeric_array_sha256(
        raw
    )

    if (
        numeric_sha
        != expectations.numeric_array_sha256
    ):
        raise Stage7ExecutionError(
            "Stage 6 matrix numeric-array SHA256 mismatch"
        )

    return VerifiedStage6Matrix(
        raw=raw,
        species_ids=species_ids,
        accessions=accessions,
        artifact_sha256=artifact_sha,
        numeric_array_sha256=numeric_sha,
        membership_sha256=membership_sha,
    )


def _content_manifest_rows(
    partial_dir: Path,
) -> tuple[
    dict[str, str],
    ...,
]:
    rows = []

    for name in sorted(
        CONTENT_COVERED_FILES
    ):
        path = (
            partial_dir
            / name
        )

        if (
            not path.is_file()
            or path.is_symlink()
        ):
            raise Stage7ExecutionError(
                "Stage 7 content-manifest input missing"
            )

        rows.append(
            {
                "path":
                    name,
                "size_bytes":
                    str(
                        path.stat().st_size
                    ),
                "sha256":
                    sha256_file(
                        path
                    ),
            }
        )

    return tuple(
        rows
    )


def _verify_ladders(
    *,
    foundation: FoundationLike,
    ladders: Mapping[
        str,
        npt.NDArray[np.integer],
    ],
    expected_hashes: Mapping[str, str],
    sequence_hasher: Callable[
        [
            str,
            list[str],
        ],
        str,
    ],
) -> dict[
    str,
    npt.NDArray[np.int64],
]:
    if set(
        ladders
    ) != {
        "OPS",
        "SR",
    }:
        raise Stage7ExecutionError(
            "candidate ladders must contain exactly OPS and SR"
        )

    if set(
        expected_hashes
    ) != {
        "OPS",
        "SR",
    }:
        raise Stage7ExecutionError(
            "expected ladder hashes must contain exactly OPS and SR"
        )

    verified = {}

    for selector in (
        "OPS",
        "SR",
    ):
        source = np.asarray(
            ladders[
                selector
            ]
        )

        if (
            source.ndim != 1
            or source.size != 500
        ):
            raise Stage7ExecutionError(
                f"{selector} ladder must contain exactly 500 indices"
            )

        if not np.issubdtype(
            source.dtype,
            np.integer,
        ):
            raise Stage7ExecutionError(
                f"{selector} ladder indices must be integers"
            )

        ladder = source.astype(
            np.int64,
            copy=False,
        )

        if np.unique(
            ladder
        ).size != 500:
            raise Stage7ExecutionError(
                f"{selector} ladder contains duplicate indices"
            )

        if (
            np.any(
                ladder < 0
            )
            or np.any(
                ladder >= len(
                    foundation.accessions
                )
            )
        ):
            raise Stage7ExecutionError(
                f"{selector} ladder index outside baseline foundation"
            )

        values = [
            foundation.accessions[
                int(
                    index
                )
            ]
            for index in ladder
        ]

        observed_hash = sequence_hasher(
            (
                "BacSelect-selector-v1|"
                "final300-2400|"
                f"{selector}|ladder|N=500"
            ),
            values,
        )

        expected_hash = _validate_sha256(
            expected_hashes[
                selector
            ],
            label=f"{selector} final ladder SHA256",
        )

        if observed_hash != expected_hash:
            raise Stage7ExecutionError(
                f"{selector} final ladder fingerprint mismatch"
            )

        verified[
            selector
        ] = ladder

    return verified


def execute_stage7_analysis(
    *,
    repo: Path,
    expected_commit: str,
    execution_mode: str,
    output_root: Path,
    stage6_matrix_path: Path,
    stage6_expectations: Stage6MatrixExpectations,
    frozen_bindings: Stage7FrozenBindings,
    feature_names: Sequence[str],
    baseline_loader: Callable[
        [],
        FoundationLike,
    ],
    ladder_builder: Callable[
        [
            FoundationLike,
        ],
        Mapping[
            str,
            npt.NDArray[np.integer],
        ],
    ],
    sequence_hasher: Callable[
        [
            str,
            list[str],
        ],
        str,
    ],
    matrix_loader: Callable[..., VerifiedStage6Matrix] = (
        load_verified_stage6_matrix
    ),
) -> Path:
    """Execute one production-style or rebuild-style blinded Stage 7 run.

    The predecision checkpoint is finalized before ``matrix_loader`` is called.
    This function never resolves OPS versus SR.
    """
    _validate_frozen_bindings(
        frozen_bindings
    )

    _validate_stage6_expectations(
        stage6_expectations
    )

    if execution_mode not in EXECUTION_MODES:
        raise Stage7ExecutionError(
            "invalid Stage 7 execution mode"
        )

    if not re.fullmatch(
        r"[0-9a-f]{40}",
        str(
            expected_commit
        ),
    ):
        raise Stage7ExecutionError(
            "expected Stage 7 execution commit malformed"
        )

    if not feature_names:
        raise Stage7ExecutionError(
            "Stage 7 feature list must not be empty"
        )

    if len(
        set(
            feature_names
        )
    ) != len(
        feature_names
    ):
        raise Stage7ExecutionError(
            "Stage 7 feature names must be unique"
        )

    root = _ensure_output_root_outside_repo(
        output_root,
        repo,
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_dir = (
        root
        / expected_commit
    )

    partial_dir = (
        root
        / (
            "."
            + expected_commit
            + ".partial"
        )
    )

    if final_dir.exists():
        raise Stage7ExecutionError(
            "final Stage 7 output directory already exists"
        )

    if partial_dir.exists():
        raise Stage7ExecutionError(
            "partial Stage 7 output directory already exists"
        )

    partial_dir.mkdir()

    predecision_path = (
        partial_dir
        / "stage7-predecision-provenance.json"
    )

    predecision = {
        "schema_version":
            1,
        "status":
            "STAGE7_PREDECISION_FROZEN",
        "bacselect_git_commit":
            expected_commit,
        "execution_mode":
            execution_mode,
        "stage7_method_sha256":
            frozen_bindings.stage7_method_sha256,
        "selector_resolution_design_sha256":
            frozen_bindings.selector_resolution_design_sha256,
        "stage6_completion_evidence_sha256":
            frozen_bindings.stage6_completion_evidence_sha256,
        "stage6_raw_feature_matrix_artifact_sha256":
            stage6_expectations.artifact_sha256,
        "stage6_raw_feature_matrix_numeric_array_sha256":
            stage6_expectations.numeric_array_sha256,
        "external_holdout_count":
            stage6_expectations.row_count,
        "external_holdout_species_count":
            stage6_expectations.species_count,
        "external_holdout_membership_sha256":
            stage6_expectations.membership_sha256,
        "baseline_bindings":
            dict(
                sorted(
                    frozen_bindings.baseline_bindings.items()
                )
            ),
        "final_ladder_sha256":
            {
                selector:
                    frozen_bindings.final_ladder_sha256[
                        selector
                    ]
                for selector in (
                    "OPS",
                    "SR",
                )
            },
        "implementation_bindings":
            dict(
                sorted(
                    frozen_bindings.implementation_bindings.items()
                )
            ),
        "environment_lock_sha256":
            frozen_bindings.environment_lock_sha256,
        "software_versions":
            {
                "python":
                    platform.python_version(),
                "numpy":
                    np.__version__,
                "scipy":
                    scipy.__version__,
            },
        "holdout_raw_feature_matrix_opened":
            False,
        "holdout_percentile_coordinates_calculated":
            False,
        "ops_sr_distances_calculated":
            False,
        "primary_metrics_calculated":
            False,
        "exact_selector_products_calculated":
            False,
        "selector_outcome_generated":
            False,
    }

    predecision_sha = write_json_atomic(
        predecision_path,
        predecision,
    )

    # Baseline verification and final-ladder reconstruction are permitted
    # only after the predecision checkpoint exists.
    try:
        foundation = baseline_loader()
    except Exception:
        raise Stage7ExecutionError(
            "frozen baseline verification failed closed"
        ) from None

    if len(
        foundation.raw
    ) != len(
        foundation.species_ids
    ) or len(
        foundation.raw
    ) != len(
        foundation.accessions
    ):
        raise Stage7ExecutionError(
            "baseline foundation row alignment changed"
        )

    try:
        candidate_ladders = ladder_builder(
            foundation
        )
    except Exception:
        raise Stage7ExecutionError(
            "final ladder reconstruction failed closed"
        ) from None

    verified_ladders = _verify_ladders(
        foundation=foundation,
        ladders=candidate_ladders,
        expected_hashes=(
            frozen_bindings.final_ladder_sha256
        ),
        sequence_hasher=sequence_hasher,
    )

    # The Stage 6 raw-feature matrix is opened only here, after predecision,
    # baseline verification and final ladder verification all succeeded.
    try:
        holdout = matrix_loader(
            stage6_matrix_path,
            expectations=stage6_expectations,
            feature_names=feature_names,
        )
    except Stage7ExecutionError:
        raise
    except Exception:
        raise Stage7ExecutionError(
            "Stage 6 matrix verification failed closed"
        ) from None

    if (
        holdout.artifact_sha256
        != stage6_expectations.artifact_sha256
        or holdout.numeric_array_sha256
        != stage6_expectations.numeric_array_sha256
        or holdout.membership_sha256
        != stage6_expectations.membership_sha256
    ):
        raise Stage7ExecutionError(
            "verified Stage 6 matrix identity mismatch"
        )

    try:
        scientific_artifacts = (
            build_blinded_analysis_artifacts(
                baseline_raw_features=foundation.raw,
                baseline_species_ids=foundation.species_ids,
                verified_ladders=verified_ladders,
                holdout_raw_features=holdout.raw,
                holdout_species_ids=holdout.species_ids,
                feature_names=feature_names,
            )
        )
    except Exception:
        raise Stage7ExecutionError(
            "Stage 7 blinded scientific analysis failed closed"
        ) from None

    if tuple(
        scientific_artifacts
    ) != SCIENTIFIC_ARTIFACT_NAMES:
        raise Stage7ExecutionError(
            "Stage 7 scientific artifact contract changed"
        )

    scientific_sha256 = {}

    for name in SCIENTIFIC_ARTIFACT_NAMES:
        payload = scientific_artifacts[
            name
        ]

        path = (
            partial_dir
            / name
        )

        observed = write_bytes_atomic(
            path,
            payload,
        )

        expected = sha256_bytes(
            payload
        )

        if observed != expected:
            raise Stage7ExecutionError(
                "Stage 7 scientific artifact write mismatch"
            )

        scientific_sha256[
            name
        ] = observed

    execution_provenance_path = (
        partial_dir
        / "stage7-execution-provenance.json"
    )

    execution_provenance = {
        "schema_version":
            1,
        "status":
            "STAGE7_BLINDED_ANALYSIS_COMPLETE",
        "bacselect_git_commit":
            expected_commit,
        "execution_mode":
            execution_mode,
        "predecision_provenance_sha256":
            predecision_sha,
        "stage7_method_sha256":
            frozen_bindings.stage7_method_sha256,
        "selector_resolution_design_sha256":
            frozen_bindings.selector_resolution_design_sha256,
        "stage6_completion_evidence_sha256":
            frozen_bindings.stage6_completion_evidence_sha256,
        "stage6_raw_feature_matrix_artifact_sha256":
            holdout.artifact_sha256,
        "stage6_raw_feature_matrix_numeric_array_sha256":
            holdout.numeric_array_sha256,
        "external_holdout_count":
            len(
                holdout.accessions
            ),
        "external_holdout_species_count":
            len(
                set(
                    holdout.species_ids
                )
            ),
        "external_holdout_membership_sha256":
            holdout.membership_sha256,
        "baseline_bindings":
            dict(
                sorted(
                    frozen_bindings.baseline_bindings.items()
                )
            ),
        "final_ladder_sha256":
            {
                selector:
                    frozen_bindings.final_ladder_sha256[
                        selector
                    ]
                for selector in (
                    "OPS",
                    "SR",
                )
            },
        "implementation_bindings":
            dict(
                sorted(
                    frozen_bindings.implementation_bindings.items()
                )
            ),
        "environment_lock_sha256":
            frozen_bindings.environment_lock_sha256,
        "software_versions":
            {
                "python":
                    platform.python_version(),
                "numpy":
                    np.__version__,
                "scipy":
                    scipy.__version__,
            },
        "scientific_artifact_sha256":
            dict(
                sorted(
                    scientific_sha256.items()
                )
            ),
        "baseline_geometry_verified":
            True,
        "final_ladders_verified":
            True,
        "holdout_raw_feature_matrix_opened":
            True,
        "holdout_percentile_coordinates_calculated":
            True,
        "ops_sr_distances_calculated":
            True,
        "primary_metrics_calculated":
            True,
        "exact_selector_products_calculated":
            True,
        "selector_outcome_generated":
            False,
    }

    execution_provenance_sha = (
        write_json_atomic(
            execution_provenance_path,
            execution_provenance,
        )
    )

    content_manifest_path = (
        partial_dir
        / "stage7-content-manifest.tsv"
    )

    content_manifest_sha = (
        write_tsv_atomic(
            content_manifest_path,
            CONTENT_MANIFEST_FIELDS,
            _content_manifest_rows(
                partial_dir
            ),
        )
    )

    observed_files = {
        path.name
        for path in partial_dir.iterdir()
        if path.is_file()
    }

    if observed_files != set(
        STAGE7_FINAL_FILES
    ):
        raise Stage7ExecutionError(
            "Stage 7 final artifact set mismatch"
        )

    if final_dir.exists():
        raise Stage7ExecutionError(
            "final Stage 7 directory appeared before finalization"
        )

    os.replace(
        partial_dir,
        final_dir,
    )

    print(
        "PASS | Stage 7 blinded analysis execution complete"
    )

    print(
        f"execution_mode={execution_mode}"
    )

    print(
        f"predecision_provenance_sha256={predecision_sha}"
    )

    print(
        "execution_provenance_sha256="
        f"{execution_provenance_sha}"
    )

    print(
        f"content_manifest_sha256={content_manifest_sha}"
    )

    print(
        f"execution_dir={final_dir}"
    )

    return final_dir
