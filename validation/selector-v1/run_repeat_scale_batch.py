#!/usr/bin/env python3
"""Compute the frozen selector-v1 alternative-k repeat grid for one batch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

from bacselect.repeat_concordance import (
    REFERENCE_FEATURES,
    compare_reference_features,
)
from bacselect.repeat_scale import (
    K_GRID,
    REPEAT_FEATURE_FAMILIES,
)


REPO = Path(__file__).resolve().parents[2]

VENDOR_DIR = (
    REPO
    / "vendor"
    / "project-finch"
    / "experiment-0"
)

FINCH_DRIVER = (
    VENDOR_DIR
    / "compute_structural_features.py"
)

FINCH_BASIC = (
    VENDOR_DIR
    / "basic_structural_features.py"
)

ENGINE_SOURCE = (
    VENDOR_DIR
    / "structural_features_fast.cpp"
)

REPEAT_SCALE_MODULE = (
    REPO
    / "src"
    / "bacselect"
    / "repeat_scale.py"
)

CONCORDANCE_MODULE = (
    REPO
    / "src"
    / "bacselect"
    / "repeat_concordance.py"
)

ENV_LOCK = (
    REPO
    / "envs"
    / "bacselect-repeat-linux-64.lock"
)

METHOD = (
    REPO
    / "validation"
    / "selector-v1"
    / "repeat-scale-method.md"
)

WORKER = Path(__file__).resolve()

EXPECTED_TARGET_SHA256 = (
    "bc4acba1384524f956887d02d2f54aa7"
    "e501a2c23e2930b779a4e6520d8fcee1"
)

EXPECTED_MATRIX_SHA256 = (
    "fd264bedda627d737a647de601c8b835"
    "f53baeca246724e9aafb73fd50c9d656"
)

EXPECTED_FINCH_DRIVER_SHA256 = (
    "e4d76a44731000dc8330d6f3289aca7"
    "6ce6562329dd371f6f63ec090ab42db50"
)

EXPECTED_FINCH_BASIC_SHA256 = (
    "30bc3f52fdf68cf7b6433262935b3ed"
    "2bb189b256672687bea56f3a4f4cc043a"
)

EXPECTED_ENGINE_SOURCE_SHA256 = (
    "bea979167a353c41e51bb96c83acebfb"
    "8e8136269d2902d99142c0780bf46925"
)

EXPECTED_ENV_LOCK_SHA256 = (
    "aa6984b17e86f7d0627379e295fabed8"
    "37cf7d43cc6a9fd80f32b7092ac5f64f"
)

EXPECTED_CONCORDANCE_SHA256 = (
    "6dc25a2d382ebdf0a5c6327b211bb4da"
    "e064363727b42864a725b626bb325a51"
)

EXPECTED_TOTAL_TARGETS = 55306
EXPECTED_BATCHES = 111

EXPECTED_K_GRID = (
    50,
    75,
    100,
    150,
    200,
    300,
    400,
    600,
    800,
    1200,
    1600,
    2400,
    3200,
)

EXPECTED_REPEAT_FEATURE_FAMILIES = (
    "non_unique_fraction",
    "maximum_multiplicity",
    "inter_replicon_shared_fraction",
)

EXPECTED_REFERENCE_FEATURES = (
    "06_non_unique_canonical_150mer_fraction",
    "07_non_unique_canonical_400mer_fraction",
    "08_maximum_canonical_150mer_multiplicity",
    "09_maximum_canonical_400mer_multiplicity",
    "11_inter_replicon_shared_canonical_150mer_fraction",
    "12_inter_replicon_shared_canonical_400mer_fraction",
)

ACCESSION_COLUMN = (
    "canonical_genbank_assembly_accession"
)

TARGET_COLUMNS = (
    "batch",
    "batch_index",
    ACCESSION_COLUMN,
    "total_sequence_length",
    "primary_assembly_records",
    "topology_circular_records",
    "topology_linear_records",
)

ENGINE_FEATURE_FIELDS = (
    "valid_start_count",
    "non_unique_start_count",
    "non_unique_fraction",
    "maximum_multiplicity",
    "inter_replicon_shared_start_count",
    "inter_replicon_shared_fraction",
)

RESULT_FIELDS = (
    "position",
    "batch_index",
    "accession",
    "output_file",
    "output_sha256",
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    if not path.is_file():
        fail(
            f"{label} missing: {path}"
        )

    observed = sha256_file(path)

    if observed != expected:
        fail(
            f"{label} SHA256 mismatch: "
            f"expected {expected}, observed {observed}"
        )

    return observed


def git_head() -> str:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(REPO),
            "rev-parse",
            "HEAD",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    return completed.stdout.strip()


def validate_frozen_constants() -> None:
    if tuple(K_GRID) != EXPECTED_K_GRID:
        fail(
            "repeat-scale K_GRID differs from the "
            "prospectively frozen grid"
        )

    if (
        tuple(REPEAT_FEATURE_FAMILIES)
        != EXPECTED_REPEAT_FEATURE_FAMILIES
    ):
        fail(
            "repeat-scale feature families differ from "
            "the prospectively frozen definition"
        )

    if tuple(REFERENCE_FEATURES) != (
        EXPECTED_REFERENCE_FEATURES
    ):
        fail(
            "reference-concordance feature set differs "
            "from the frozen 150/400 anchor definition"
        )


def load_finch_driver():
    require_sha256(
        FINCH_DRIVER,
        EXPECTED_FINCH_DRIVER_SHA256,
        "vendored Finch driver",
    )

    require_sha256(
        FINCH_BASIC,
        EXPECTED_FINCH_BASIC_SHA256,
        "vendored Finch basic module",
    )

    spec = importlib.util.spec_from_file_location(
        "bacselect_frozen_finch_repeat_scale_driver",
        FINCH_DRIVER,
    )

    if spec is None or spec.loader is None:
        fail(
            f"cannot load vendored Finch driver: "
            f"{FINCH_DRIVER}"
        )

    module = importlib.util.module_from_spec(
        spec
    )
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def read_targets(
    path: Path,
    batch: str,
) -> tuple[
    list[dict[str, str]],
    tuple[str, ...],
]:
    require_sha256(
        path,
        EXPECTED_TARGET_SHA256,
        "repeat-scale target manifest",
    )

    expected_batches = {
        f"batch-{index:03d}"
        for index in range(
            1,
            EXPECTED_BATCHES + 1,
        )
    }

    if batch not in expected_batches:
        fail(
            f"invalid batch identifier: {batch}"
        )

    rows: list[dict[str, str]] = []
    all_accessions: list[str] = []
    observed_batches: set[str] = set()
    seen_accessions: set[str] = set()

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        fieldnames = tuple(
            reader.fieldnames or ()
        )

        missing = [
            column
            for column in TARGET_COLUMNS
            if column not in fieldnames
        ]

        if missing:
            fail(
                "target manifest missing columns: "
                + ",".join(missing)
            )

        for line_number, row in enumerate(
            reader,
            start=2,
        ):
            accession = row[
                ACCESSION_COLUMN
            ]
            row_batch = row["batch"]

            if not accession:
                fail(
                    f"target line {line_number}: "
                    "missing accession"
                )

            if accession in seen_accessions:
                fail(
                    f"duplicate target accession: "
                    f"{accession}"
                )

            seen_accessions.add(accession)
            all_accessions.append(accession)

            if row_batch not in expected_batches:
                fail(
                    f"{accession}: unexpected batch "
                    f"{row_batch!r}"
                )

            observed_batches.add(row_batch)

            try:
                int(row["batch_index"])
                total_length = int(
                    row["total_sequence_length"]
                )
                replicons = int(
                    row["primary_assembly_records"]
                )
                circular = int(
                    row["topology_circular_records"]
                )
                linear = int(
                    row["topology_linear_records"]
                )
            except Exception as exc:
                fail(
                    f"{accession}: invalid target "
                    f"numeric field: {exc}"
                )

            if total_length <= 0:
                fail(
                    f"{accession}: non-positive "
                    "target genome length"
                )

            if replicons <= 0:
                fail(
                    f"{accession}: non-positive "
                    "target replicon count"
                )

            if circular < 0 or linear < 0:
                fail(
                    f"{accession}: negative topology count"
                )

            if circular + linear != replicons:
                fail(
                    f"{accession}: topology counts do not "
                    "equal primary_assembly_records"
                )

            if row_batch == batch:
                rows.append(row)

    if (
        len(all_accessions)
        != EXPECTED_TOTAL_TARGETS
    ):
        fail(
            "target manifest row count mismatch: "
            f"expected {EXPECTED_TOTAL_TARGETS}, "
            f"observed {len(all_accessions)}"
        )

    if observed_batches != expected_batches:
        fail(
            "target manifest batch set mismatch"
        )

    if not rows:
        fail(
            f"target batch is empty: {batch}"
        )

    return rows, tuple(all_accessions)


def read_reference_matrix(
    path: Path,
) -> dict[
    str,
    dict[str, str],
]:
    require_sha256(
        path,
        EXPECTED_MATRIX_SHA256,
        "frozen reference matrix",
    )

    rows: dict[
        str,
        dict[str, str],
    ] = {}

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        fieldnames = tuple(
            reader.fieldnames or ()
        )

        required = (
            ACCESSION_COLUMN,
            *REFERENCE_FEATURES,
        )

        missing = [
            column
            for column in required
            if column not in fieldnames
        ]

        if missing:
            fail(
                "reference matrix missing columns: "
                + ",".join(missing)
            )

        for row in reader:
            accession = row[
                ACCESSION_COLUMN
            ]

            if accession in rows:
                fail(
                    f"duplicate reference accession: "
                    f"{accession}"
                )

            rows[accession] = {
                feature: row[feature]
                for feature in REFERENCE_FEATURES
            }

    if len(rows) != EXPECTED_TOTAL_TARGETS:
        fail(
            "reference matrix row count mismatch: "
            f"expected {EXPECTED_TOTAL_TARGETS}, "
            f"observed {len(rows)}"
        )

    return rows


def validate_target_reference_alignment(
    target_accessions: tuple[str, ...],
    reference: Mapping[
        str,
        Mapping[str, str],
    ],
) -> None:
    target_set = set(target_accessions)
    reference_set = set(reference)

    if len(target_set) != len(
        target_accessions
    ):
        fail(
            "target accessions are not unique"
        )

    if target_set != reference_set:
        missing = sorted(
            target_set - reference_set
        )
        unexpected = sorted(
            reference_set - target_set
        )

        fail(
            "target/reference accession mismatch; "
            f"missing_reference={missing[:10]!r}; "
            f"unexpected_reference={unexpected[:10]!r}"
        )


def write_json_atomic(
    path: Path,
    value: Mapping[str, Any],
) -> str:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        tmp = Path(handle.name)
        json.dump(
            value,
            handle,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")

    try:
        tmp.replace(path)
    except Exception:
        tmp.unlink(
            missing_ok=True
        )
        raise

    return sha256_file(path)


def write_tsv_atomic(
    path: Path,
    rows: list[Mapping[str, object]],
) -> str:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        tmp = Path(handle.name)
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                RESULT_FIELDS
            ),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    try:
        tmp.replace(path)
    except Exception:
        tmp.unlink(
            missing_ok=True
        )
        raise

    return sha256_file(path)


def build_engine_command(
    engine: Path,
    input_path: Path,
    k_values: tuple[int, ...] = EXPECTED_K_GRID,
) -> list[str]:
    command = [
        str(engine),
        "--input",
        str(input_path),
    ]

    for k in k_values:
        command.extend(
            [
                "--k",
                str(k),
            ]
        )

    return command


def _parse_integer(
    value: object,
    label: str,
) -> int:
    if isinstance(value, bool):
        fail(
            f"{label} must be an integer"
        )

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass

    fail(
        f"{label} must be an integer: "
        f"{value!r}"
    )


def _parse_float(
    value: object,
    label: str,
) -> float:
    if isinstance(value, bool):
        fail(
            f"{label} must be numeric"
        )

    try:
        result = float(value)
    except (TypeError, ValueError):
        fail(
            f"{label} must be numeric: "
            f"{value!r}"
        )

    if not math.isfinite(result):
        fail(
            f"{label} must be finite: "
            f"{value!r}"
        )

    return result


def normalize_engine_feature_row(
    row: Mapping[str, object],
    *,
    k: int,
    exact_keys: bool,
) -> dict[str, int | float]:
    if exact_keys and set(row) != set(
        ENGINE_FEATURE_FIELDS
    ):
        fail(
            f"k={k}: feature field set mismatch"
        )

    missing = [
        field
        for field in ENGINE_FEATURE_FIELDS
        if field not in row
    ]

    if missing:
        fail(
            f"k={k}: missing engine fields: "
            + ",".join(missing)
        )

    valid = _parse_integer(
        row["valid_start_count"],
        f"k={k} valid_start_count",
    )
    non_unique = _parse_integer(
        row["non_unique_start_count"],
        f"k={k} non_unique_start_count",
    )
    maximum = _parse_integer(
        row["maximum_multiplicity"],
        f"k={k} maximum_multiplicity",
    )
    shared = _parse_integer(
        row[
            "inter_replicon_shared_start_count"
        ],
        (
            f"k={k} "
            "inter_replicon_shared_start_count"
        ),
    )

    non_unique_fraction = _parse_float(
        row["non_unique_fraction"],
        f"k={k} non_unique_fraction",
    )
    shared_fraction = _parse_float(
        row[
            "inter_replicon_shared_fraction"
        ],
        (
            f"k={k} "
            "inter_replicon_shared_fraction"
        ),
    )

    if min(
        valid,
        non_unique,
        maximum,
        shared,
    ) < 0:
        fail(
            f"k={k}: negative repeat count"
        )

    if not (
        0.0 <= non_unique_fraction <= 1.0
    ):
        fail(
            f"k={k}: non_unique_fraction "
            "outside [0,1]"
        )

    if not (
        0.0 <= shared_fraction <= 1.0
    ):
        fail(
            f"k={k}: "
            "inter_replicon_shared_fraction "
            "outside [0,1]"
        )

    if non_unique > valid:
        fail(
            f"k={k}: non_unique_start_count "
            "exceeds valid_start_count"
        )

    if shared > valid:
        fail(
            f"k={k}: "
            "inter_replicon_shared_start_count "
            "exceeds valid_start_count"
        )

    if shared > non_unique:
        fail(
            f"k={k}: inter-replicon shared "
            "starts exceed non-unique starts"
        )

    if maximum > valid:
        fail(
            f"k={k}: maximum multiplicity "
            "exceeds valid_start_count"
        )

    if valid == 0:
        if (
            non_unique != 0
            or maximum != 0
            or shared != 0
            or non_unique_fraction != 0.0
            or shared_fraction != 0.0
        ):
            fail(
                f"k={k}: non-zero repeat values "
                "with zero valid starts"
            )
    else:
        if maximum < 1:
            fail(
                f"k={k}: maximum multiplicity "
                "must be at least one"
            )

        expected_non_unique = (
            non_unique / valid
        )
        expected_shared = (
            shared / valid
        )

        if not math.isclose(
            non_unique_fraction,
            expected_non_unique,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            fail(
                f"k={k}: non_unique_fraction "
                "does not match count/denominator"
            )

        if not math.isclose(
            shared_fraction,
            expected_shared,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            fail(
                f"k={k}: "
                "inter_replicon_shared_fraction "
                "does not match count/denominator"
            )

    return {
        "valid_start_count": valid,
        "non_unique_start_count": non_unique,
        "non_unique_fraction": (
            non_unique_fraction
        ),
        "maximum_multiplicity": maximum,
        "inter_replicon_shared_start_count": (
            shared
        ),
        "inter_replicon_shared_fraction": (
            shared_fraction
        ),
    }


def parse_engine_output(
    text: str,
    k_values: tuple[int, ...] = EXPECTED_K_GRID,
) -> tuple[
    dict[int, dict[str, str]],
    dict[int, dict[str, int | float]],
]:
    reader = csv.DictReader(
        text.splitlines(),
        delimiter="\t",
    )

    fieldnames = tuple(
        reader.fieldnames or ()
    )

    required = (
        "k",
        *ENGINE_FEATURE_FIELDS,
    )

    missing = [
        field
        for field in required
        if field not in fieldnames
    ]

    if missing:
        fail(
            "repeat engine output missing fields: "
            + ",".join(missing)
        )

    raw_rows: dict[
        int,
        dict[str, str],
    ] = {}
    numeric_rows: dict[
        int,
        dict[str, int | float],
    ] = {}

    for row in reader:
        try:
            k = int(row["k"])
        except Exception as exc:
            fail(
                f"invalid repeat engine k value: "
                f"{exc}"
            )

        if k in raw_rows:
            fail(
                f"duplicate repeat engine row "
                f"for k={k}"
            )

        if k not in k_values:
            fail(
                f"unexpected repeat engine k={k}"
            )

        raw_rows[k] = dict(row)

        numeric_rows[k] = (
            normalize_engine_feature_row(
                row,
                k=k,
                exact_keys=False,
            )
        )

    if len(raw_rows) != len(k_values):
        fail(
            "repeat engine row count mismatch: "
            f"expected {len(k_values)}, "
            f"observed {len(raw_rows)}"
        )

    observed = set(raw_rows)
    expected = set(k_values)

    if observed != expected:
        fail(
            "repeat engine k set mismatch; "
            f"missing={sorted(expected - observed)!r}; "
            f"unexpected={sorted(observed - expected)!r}"
        )

    return raw_rows, numeric_rows


def run_repeat_scale_engine(
    engine: Path,
    replicons,
) -> tuple[
    dict[int, dict[str, str]],
    dict[int, dict[str, int | float]],
]:
    if not engine.is_file():
        fail(
            f"repeat engine missing: {engine}"
        )

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        prefix="bacselect-repeat-scale-",
        suffix=".tsv",
        delete=False,
    ) as handle:
        input_path = Path(handle.name)

        writer = csv.writer(
            handle,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writerow(
            [
                "name",
                "topology",
                "sequence",
            ]
        )

        for replicon in replicons:
            writer.writerow(
                [
                    replicon.name,
                    replicon.topology,
                    replicon.sequence,
                ]
            )

    command = build_engine_command(
        engine,
        input_path,
    )

    try:
        completed = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (
            exc.stderr or ""
        ).strip()
        fail(
            "repeat engine failed "
            f"(exit={exc.returncode}): "
            f"{stderr[-2000:]}"
        )
    finally:
        input_path.unlink(
            missing_ok=True
        )

    return parse_engine_output(
        completed.stdout
    )


def candidate_source_path(
    batch_source: Path,
    accession: str,
) -> Path:
    return (
        batch_source
        / "package"
        / "ncbi_dataset"
        / "data"
        / accession
    )


def anchor_features_from_numeric(
    features_by_k: Mapping[
        str,
        Mapping[str, object],
    ],
) -> dict[str, int | float]:
    row150 = features_by_k["150"]
    row400 = features_by_k["400"]

    return {
        (
            "06_non_unique_canonical_"
            "150mer_fraction"
        ): float(
            row150[
                "non_unique_fraction"
            ]
        ),
        (
            "07_non_unique_canonical_"
            "400mer_fraction"
        ): float(
            row400[
                "non_unique_fraction"
            ]
        ),
        (
            "08_maximum_canonical_"
            "150mer_multiplicity"
        ): int(
            row150[
                "maximum_multiplicity"
            ]
        ),
        (
            "09_maximum_canonical_"
            "400mer_multiplicity"
        ): int(
            row400[
                "maximum_multiplicity"
            ]
        ),
        (
            "11_inter_replicon_shared_"
            "canonical_150mer_fraction"
        ): float(
            row150[
                "inter_replicon_shared_fraction"
            ]
        ),
        (
            "12_inter_replicon_shared_"
            "canonical_400mer_fraction"
        ): float(
            row400[
                "inter_replicon_shared_fraction"
            ]
        ),
    }


def normalize_features_by_k(
    value: object,
) -> dict[
    str,
    dict[str, int | float],
]:
    if not isinstance(value, dict):
        fail(
            "features_by_k is not an object"
        )

    expected_keys = {
        str(k)
        for k in EXPECTED_K_GRID
    }

    if set(value) != expected_keys:
        fail(
            "features_by_k k set mismatch"
        )

    normalized: dict[
        str,
        dict[str, int | float],
    ] = {}

    for k in EXPECTED_K_GRID:
        key = str(k)
        row = value[key]

        if not isinstance(row, dict):
            fail(
                f"k={k}: stored feature row "
                "is not an object"
            )

        normalized[key] = (
            normalize_engine_feature_row(
                row,
                k=k,
                exact_keys=True,
            )
        )

    return normalized


def build_run_identity(
    *,
    batch: str,
    engine: Path,
    production_inputs_manifest: Path,
    source_audit_manifest: Path,
) -> dict[str, object]:
    require_sha256(
        FINCH_DRIVER,
        EXPECTED_FINCH_DRIVER_SHA256,
        "vendored Finch driver",
    )
    require_sha256(
        FINCH_BASIC,
        EXPECTED_FINCH_BASIC_SHA256,
        "vendored Finch basic module",
    )
    require_sha256(
        ENGINE_SOURCE,
        EXPECTED_ENGINE_SOURCE_SHA256,
        "repeat engine source",
    )
    require_sha256(
        ENV_LOCK,
        EXPECTED_ENV_LOCK_SHA256,
        "repeat environment lock",
    )
    require_sha256(
        CONCORDANCE_MODULE,
        EXPECTED_CONCORDANCE_SHA256,
        "repeat concordance module",
    )

    if not REPEAT_SCALE_MODULE.is_file():
        fail(
            f"repeat-scale module missing: "
            f"{REPEAT_SCALE_MODULE}"
        )

    if not METHOD.is_file():
        fail(
            f"repeat-scale method missing: {METHOD}"
        )

    if not production_inputs_manifest.is_file():
        fail(
            "production input hash manifest missing: "
            f"{production_inputs_manifest}"
        )

    if not source_audit_manifest.is_file():
        fail(
            "source snapshot audit manifest missing: "
            f"{source_audit_manifest}"
        )

    if not engine.is_file():
        fail(
            f"compiled repeat engine missing: "
            f"{engine}"
        )

    return {
        "schema_version": 1,
        "analysis": (
            "selector-v1-repeat-scale-grid"
        ),
        "batch": batch,
        "git_head": git_head(),
        "target_manifest_sha256": (
            EXPECTED_TARGET_SHA256
        ),
        "reference_matrix_sha256": (
            EXPECTED_MATRIX_SHA256
        ),
        "worker_sha256": (
            sha256_file(WORKER)
        ),
        "repeat_scale_module_sha256": (
            sha256_file(
                REPEAT_SCALE_MODULE
            )
        ),
        "repeat_concordance_module_sha256": (
            EXPECTED_CONCORDANCE_SHA256
        ),
        "repeat_scale_method_sha256": (
            sha256_file(METHOD)
        ),
        "finch_driver_sha256": (
            EXPECTED_FINCH_DRIVER_SHA256
        ),
        "finch_basic_sha256": (
            EXPECTED_FINCH_BASIC_SHA256
        ),
        "engine_source_sha256": (
            EXPECTED_ENGINE_SOURCE_SHA256
        ),
        "engine_sha256": (
            sha256_file(engine)
        ),
        "environment_lock_sha256": (
            EXPECTED_ENV_LOCK_SHA256
        ),
        "production_inputs_manifest_sha256": (
            sha256_file(
                production_inputs_manifest
            )
        ),
        "source_audit_manifest_sha256": (
            sha256_file(
                source_audit_manifest
            )
        ),
        "k_values": list(
            EXPECTED_K_GRID
        ),
        "repeat_feature_families": list(
            EXPECTED_REPEAT_FEATURE_FAMILIES
        ),
    }


def ensure_run_provenance(
    path: Path,
    expected: Mapping[str, Any],
    candidate_output: Path,
) -> str:
    if path.exists():
        try:
            observed = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as exc:
            fail(
                "existing run provenance is invalid: "
                f"{exc}"
            )

        if observed != expected:
            fail(
                "existing run provenance does not "
                "match current computational state"
            )

    else:
        existing_candidates = list(
            candidate_output.glob(
                "*.repeat-scale.json"
            )
        )

        sibling_outputs = [
            path.parent / "candidate-results.tsv",
            path.parent / "batch-summary.json",
        ]

        if (
            existing_candidates
            or any(
                sibling.exists()
                for sibling in sibling_outputs
            )
        ):
            fail(
                "repeat-scale outputs exist without "
                "matching run provenance"
            )

        write_json_atomic(
            path,
            expected,
        )

    return sha256_file(path)


def load_candidate_source(
    *,
    target: dict[str, str],
    candidate_source: Path,
    candidate_audit: Path,
    component_audit: Path,
    finch,
):
    accession = target[
        ACCESSION_COLUMN
    ]

    (
        loaded_accession,
        replicons,
        fasta_path,
        sequence_report_path,
    ) = finch.load_replicons(
        candidate_source,
        candidate_audit,
        component_audit,
    )

    if loaded_accession != accession:
        fail(
            f"{accession}: loaded accession mismatch"
        )

    expected_replicons = int(
        target[
            "primary_assembly_records"
        ]
    )

    if len(replicons) != expected_replicons:
        fail(
            f"{accession}: loaded replicon count "
            "mismatch"
        )

    observed_length = sum(
        len(replicon.sequence)
        for replicon in replicons
    )
    expected_length = int(
        target["total_sequence_length"]
    )

    if observed_length != expected_length:
        fail(
            f"{accession}: loaded genome length "
            "mismatch"
        )

    observed_circular = sum(
        replicon.topology == "circular"
        for replicon in replicons
    )
    observed_linear = sum(
        replicon.topology == "linear"
        for replicon in replicons
    )

    if observed_circular + observed_linear != (
        len(replicons)
    ):
        fail(
            f"{accession}: loaded replicon topology "
            "is not fully circular/linear"
        )

    if observed_circular != int(
        target[
            "topology_circular_records"
        ]
    ):
        fail(
            f"{accession}: circular topology "
            "count mismatch"
        )

    if observed_linear != int(
        target[
            "topology_linear_records"
        ]
    ):
        fail(
            f"{accession}: linear topology "
            "count mismatch"
        )

    source = {
        "genomic_fasta_file": (
            fasta_path.name
        ),
        "genomic_fasta_sha256": (
            sha256_file(
                fasta_path
            )
        ),
        "sequence_report_file": (
            sequence_report_path.name
        ),
        "sequence_report_sha256": (
            sha256_file(
                sequence_report_path
            )
        ),
        "primary_assembly_records": (
            len(replicons)
        ),
        "total_sequence_length": (
            observed_length
        ),
        "topology_circular_records": (
            observed_circular
        ),
        "topology_linear_records": (
            observed_linear
        ),
    }

    return replicons, source


def candidate_record(
    *,
    batch: str,
    target: dict[str, str],
    expected: dict[str, str],
    engine: Path,
    replicons,
    source: dict[str, object],
) -> dict[str, object]:
    accession = target[
        ACCESSION_COLUMN
    ]

    (
        _raw_rows,
        numeric_rows,
    ) = run_repeat_scale_engine(
        engine,
        replicons,
    )

    features_by_k = {
        str(k): numeric_rows[k]
        for k in EXPECTED_K_GRID
    }

    anchor_observed = (
        anchor_features_from_numeric(
            features_by_k
        )
    )

    anchor_result = (
        compare_reference_features(
            anchor_observed,
            expected,
        )
    )

    if not anchor_result.passed:
        fail(
            f"{accession}: 150/400 reference "
            "anchor failed: "
            + ",".join(
                anchor_result.mismatches
            )
        )

    record = {
        "schema_version": 1,
        "analysis": (
            "selector-v1-repeat-scale-grid"
        ),
        "batch": batch,
        "batch_index": int(
            target["batch_index"]
        ),
        ACCESSION_COLUMN: accession,
        "k_values": list(
            EXPECTED_K_GRID
        ),
        "repeat_feature_families": list(
            EXPECTED_REPEAT_FEATURE_FAMILIES
        ),
        "features_by_k": features_by_k,
        "reference_anchor": {
            "k_values": [
                150,
                400,
            ],
            "passed": True,
            "mismatches": [],
            "observed": anchor_observed,
        },
        "source": source,
    }

    return record

def validate_existing_candidate(
    path: Path,
    *,
    batch: str,
    target: dict[str, str],
    expected: dict[str, str],
    source: dict[str, object],
) -> str:
    try:
        record = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        fail(
            f"invalid existing candidate output "
            f"{path}: {exc}"
        )

    accession = target[
        ACCESSION_COLUMN
    ]

    expected_metadata = {
        "schema_version": 1,
        "analysis": (
            "selector-v1-repeat-scale-grid"
        ),
        "batch": batch,
        "batch_index": int(
            target["batch_index"]
        ),
        ACCESSION_COLUMN: accession,
        "k_values": list(
            EXPECTED_K_GRID
        ),
        "repeat_feature_families": list(
            EXPECTED_REPEAT_FEATURE_FAMILIES
        ),
    }

    for key, expected_value in (
        expected_metadata.items()
    ):
        if record.get(key) != expected_value:
            fail(
                f"{accession}: existing {key} "
                "mismatch"
            )

    features_by_k = (
        normalize_features_by_k(
            record.get(
                "features_by_k"
            )
        )
    )

    anchor_observed = (
        anchor_features_from_numeric(
            features_by_k
        )
    )

    anchor_result = (
        compare_reference_features(
            anchor_observed,
            expected,
        )
    )

    if not anchor_result.passed:
        fail(
            f"{accession}: existing 150/400 "
            "reference anchor failed: "
            + ",".join(
                anchor_result.mismatches
            )
        )

    stored_anchor = record.get(
        "reference_anchor"
    )

    if not isinstance(
        stored_anchor,
        dict,
    ):
        fail(
            f"{accession}: existing reference "
            "anchor is missing"
        )

    if stored_anchor.get("k_values") != [
        150,
        400,
    ]:
        fail(
            f"{accession}: existing anchor "
            "k-values mismatch"
        )

    if stored_anchor.get("passed") is not True:
        fail(
            f"{accession}: existing anchor "
            "is not PASS"
        )

    if stored_anchor.get("mismatches") != []:
        fail(
            f"{accession}: existing anchor "
            "mismatch list is not empty"
        )

    stored_observed = stored_anchor.get(
        "observed"
    )

    if stored_observed != anchor_observed:
        fail(
            f"{accession}: stored anchor "
            "observations do not match "
            "features_by_k"
        )

    stored_source = record.get("source")

    if stored_source != source:
        fail(
            f"{accession}: existing source "
            "identity differs from the frozen "
            "snapshot payload"
        )

    return sha256_file(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--snapshot-root",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--targets",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--reference-matrix",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--batch",
        required=True,
    )
    parser.add_argument(
        "--engine",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output-root",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--production-inputs-manifest",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--source-audit-manifest",
        required=True,
        type=Path,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    validate_frozen_constants()

    if not args.snapshot_root.is_dir():
        fail(
            f"snapshot root not found: "
            f"{args.snapshot_root}"
        )

    if not args.engine.is_file():
        fail(
            f"repeat engine not found: "
            f"{args.engine}"
        )

    (
        targets,
        target_accessions,
    ) = read_targets(
        args.targets,
        args.batch,
    )

    reference = read_reference_matrix(
        args.reference_matrix
    )

    validate_target_reference_alignment(
        target_accessions,
        reference,
    )

    batch_source = (
        args.snapshot_root
        / args.batch
    )

    if not batch_source.is_dir():
        fail(
            f"snapshot batch not found: "
            f"{batch_source}"
        )

    candidate_audit = (
        batch_source
        / "candidate-sequence-audit.tsv"
    )
    component_audit = (
        batch_source
        / "component-sequence-audit.tsv"
    )

    if not candidate_audit.is_file():
        fail(
            f"candidate audit missing: "
            f"{candidate_audit}"
        )

    if not component_audit.is_file():
        fail(
            f"component audit missing: "
            f"{component_audit}"
        )

    batch_output = (
        args.output_root
        / args.batch
    )
    candidate_output = (
        batch_output
        / "candidates"
    )
    candidate_output.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_identity = build_run_identity(
        batch=args.batch,
        engine=args.engine,
        production_inputs_manifest=(
            args.production_inputs_manifest
        ),
        source_audit_manifest=(
            args.source_audit_manifest
        ),
    )

    provenance_path = (
        batch_output
        / "run-provenance.json"
    )

    provenance_sha256 = (
        ensure_run_provenance(
            provenance_path,
            run_identity,
            candidate_output,
        )
    )

    finch = load_finch_driver()

    result_rows: list[
        dict[str, object]
    ] = []

    computed = 0
    reused = 0

    for position, target in enumerate(
        targets,
        start=1,
    ):
        accession = target[
            ACCESSION_COLUMN
        ]

        if accession not in reference:
            fail(
                f"{accession}: missing frozen "
                "reference row"
            )

        candidate_source = (
            candidate_source_path(
                batch_source,
                accession,
            )
        )

        if not candidate_source.is_dir():
            fail(
                f"{accession}: source candidate "
                f"directory missing: "
                f"{candidate_source}"
            )

        (
            replicons,
            source,
        ) = load_candidate_source(
            target=target,
            candidate_source=(
                candidate_source
            ),
            candidate_audit=(
                candidate_audit
            ),
            component_audit=(
                component_audit
            ),
            finch=finch,
        )

        output_path = (
            candidate_output
            / (
                accession
                + ".repeat-scale.json"
            )
        )

        if output_path.exists():
            output_sha256 = (
                validate_existing_candidate(
                    output_path,
                    batch=args.batch,
                    target=target,
                    expected=reference[
                        accession
                    ],
                    source=source,
                )
            )
            reused += 1

        else:
            record = candidate_record(
                batch=args.batch,
                target=target,
                expected=reference[
                    accession
                ],
                engine=args.engine,
                replicons=replicons,
                source=source,
            )

            output_sha256 = (
                write_json_atomic(
                    output_path,
                    record,
                )
            )
            computed += 1

        result_rows.append(
            {
                "position": position,
                "batch_index": int(
                    target[
                        "batch_index"
                    ]
                ),
                "accession": accession,
                "output_file": (
                    output_path.name
                ),
                "output_sha256": (
                    output_sha256
                ),
            }
        )

    expected_output_names = {
        (
            target[
                ACCESSION_COLUMN
            ]
            + ".repeat-scale.json"
        )
        for target in targets
    }

    observed_output_names = {
        path.name
        for path in candidate_output.glob(
            "*.repeat-scale.json"
        )
    }

    if (
        observed_output_names
        != expected_output_names
    ):
        missing = sorted(
            expected_output_names
            - observed_output_names
        )
        extra = sorted(
            observed_output_names
            - expected_output_names
        )

        fail(
            f"{args.batch}: candidate output "
            "set mismatch; "
            f"missing={missing[:10]!r}; "
            f"extra={extra[:10]!r}"
        )

    results_path = (
        batch_output
        / "candidate-results.tsv"
    )

    results_sha256 = write_tsv_atomic(
        results_path,
        result_rows,
    )

    summary = {
        "schema_version": 1,
        "analysis": (
            "selector-v1-repeat-scale-grid"
        ),
        "batch": args.batch,
        "all_pass": True,
        "target_count": len(targets),
        "reference_anchor_pass_count": (
            len(targets)
        ),
        "candidate_results_sha256": (
            results_sha256
        ),
        "run_provenance_sha256": (
            provenance_sha256
        ),
        "k_values": list(
            EXPECTED_K_GRID
        ),
        "repeat_feature_families": list(
            EXPECTED_REPEAT_FEATURE_FAMILIES
        ),
    }

    summary_path = (
        batch_output
        / "batch-summary.json"
    )

    write_json_atomic(
        summary_path,
        summary,
    )

    print(
        "PASS | BacSelect repeat-scale batch "
        f"{args.batch} | targets={len(targets)} "
        f"| computed={computed} | reused={reused}"
    )


if __name__ == "__main__":
    main()
