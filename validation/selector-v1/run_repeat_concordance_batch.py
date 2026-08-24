#!/usr/bin/env python3
"""Recalculate one selector-v1 k=150/400 concordance batch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from bacselect.repeat_concordance import (
    REFERENCE_FEATURES,
    compare_reference_features,
    extract_reference_features,
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

EXPECTED_TOTAL_TARGETS = 55306
EXPECTED_BATCHES = 111

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
            f"{label} SHA-256 mismatch: "
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
        "bacselect_frozen_finch_concordance_driver",
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
) -> list[dict[str, str]]:
    require_sha256(
        path,
        EXPECTED_TARGET_SHA256,
        "concordance target manifest",
    )

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        if tuple(
            reader.fieldnames or ()
        ) != TARGET_COLUMNS:
            fail(
                "unexpected concordance target columns"
            )

        all_rows = list(reader)

    if len(all_rows) != EXPECTED_TOTAL_TARGETS:
        fail(
            f"expected {EXPECTED_TOTAL_TARGETS} targets; "
            f"observed {len(all_rows)}"
        )

    accessions = [
        row[ACCESSION_COLUMN]
        for row in all_rows
    ]

    if len(set(accessions)) != len(accessions):
        fail(
            "concordance targets contain duplicate accessions"
        )

    batches = {
        row["batch"]
        for row in all_rows
    }

    if len(batches) != EXPECTED_BATCHES:
        fail(
            f"expected {EXPECTED_BATCHES} batches; "
            f"observed {len(batches)}"
        )

    rows = [
        row
        for row in all_rows
        if row["batch"] == batch
    ]

    if not rows:
        fail(
            f"no concordance targets for {batch}"
        )

    return rows


def read_reference_matrix(
    path: Path,
    batch: str,
) -> dict[str, dict[str, str]]:
    require_sha256(
        path,
        EXPECTED_MATRIX_SHA256,
        "corrected structural feature matrix",
    )

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        fields = set(
            reader.fieldnames or ()
        )

        required = {
            "batch",
            "batch_index",
            ACCESSION_COLUMN,
            *REFERENCE_FEATURES,
        }

        missing = required - fields

        if missing:
            fail(
                f"reference matrix missing columns: "
                f"{sorted(missing)!r}"
            )

        all_rows = list(reader)

    if len(all_rows) != EXPECTED_TOTAL_TARGETS:
        fail(
            f"expected {EXPECTED_TOTAL_TARGETS} "
            f"reference rows; observed {len(all_rows)}"
        )

    result: dict[
        str,
        dict[str, str],
    ] = {}

    for row in all_rows:
        if row["batch"] != batch:
            continue

        accession = row[
            ACCESSION_COLUMN
        ]

        if accession in result:
            fail(
                f"duplicate reference accession: "
                f"{accession}"
            )

        result[accession] = row

    if not result:
        fail(
            f"no reference rows for {batch}"
        )

    return result


def validate_target_reference_alignment(
    targets: list[dict[str, str]],
    reference: dict[str, dict[str, str]],
) -> None:
    target_accessions = [
        row[ACCESSION_COLUMN]
        for row in targets
    ]

    if set(target_accessions) != set(reference):
        fail(
            "target/reference accession sets differ "
            "within batch"
        )

    for target in targets:
        accession = target[
            ACCESSION_COLUMN
        ]

        expected = reference[
            accession
        ]

        if (
            target["batch_index"]
            != expected["batch_index"]
        ):
            fail(
                f"{accession}: target/reference "
                "batch_index mismatch"
            )

        if (
            int(
                target[
                    "total_sequence_length"
                ]
            )
            != int(
                expected[
                    "01_total_genome_length"
                ]
            )
        ):
            fail(
                f"{accession}: target/reference "
                "genome length mismatch"
            )

        if (
            int(
                target[
                    "primary_assembly_records"
                ]
            )
            != int(
                expected[
                    "03_replicon_count"
                ]
            )
        ):
            fail(
                f"{accession}: target/reference "
                "replicon count mismatch"
            )


def write_json_atomic(
    path: Path,
    record: dict,
) -> str:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = (
        tempfile.mkstemp(
            prefix=path.name + ".",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )
    )

    temporary = Path(
        temporary_name
    )

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                record,
                handle,
                indent=2,
                sort_keys=True,
            )

            handle.write("\n")
            handle.flush()
            os.fsync(
                handle.fileno()
            )

        temporary.replace(path)

    except Exception:
        temporary.unlink(
            missing_ok=True
        )
        raise

    return sha256_file(path)


def write_tsv_atomic(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, object]],
) -> str:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = (
        tempfile.mkstemp(
            prefix=path.name + ".",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )
    )

    temporary = Path(
        temporary_name
    )

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                delimiter="\t",
                lineterminator="\n",
            )

            writer.writeheader()
            writer.writerows(rows)

            handle.flush()
            os.fsync(
                handle.fileno()
            )

        temporary.replace(path)

    except Exception:
        temporary.unlink(
            missing_ok=True
        )
        raise

    return sha256_file(path)


def build_run_identity(
    *,
    batch: str,
    engine: Path,
    candidate_audit: Path,
    component_audit: Path,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "analysis": "selector-v1-repeat-reference-concordance",
        "batch": batch,
        "git_head": git_head(),
        "target_manifest_sha256": EXPECTED_TARGET_SHA256,
        "reference_matrix_sha256": EXPECTED_MATRIX_SHA256,
        "worker_sha256": sha256_file(WORKER),
        "repeat_concordance_module_sha256": sha256_file(
            CONCORDANCE_MODULE
        ),
        "finch_driver_sha256": require_sha256(
            FINCH_DRIVER,
            EXPECTED_FINCH_DRIVER_SHA256,
            "vendored Finch driver",
        ),
        "finch_basic_sha256": require_sha256(
            FINCH_BASIC,
            EXPECTED_FINCH_BASIC_SHA256,
            "vendored Finch basic module",
        ),
        "engine_source_sha256": require_sha256(
            ENGINE_SOURCE,
            EXPECTED_ENGINE_SOURCE_SHA256,
            "repeat engine source",
        ),
        "engine_sha256": sha256_file(engine),
        "environment_lock_sha256": require_sha256(
            ENV_LOCK,
            EXPECTED_ENV_LOCK_SHA256,
            "repeat environment lock",
        ),
        "candidate_audit_sha256": sha256_file(
            candidate_audit
        ),
        "component_audit_sha256": sha256_file(
            component_audit
        ),
        "k_values": [
            150,
            400,
        ],
    }


def ensure_run_provenance(
    path: Path,
    expected: dict[str, object],
    candidate_dir: Path,
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
                f"existing run provenance invalid: {exc}"
            )

        if observed != expected:
            fail(
                "existing run provenance does not match "
                "current computational state"
            )

    else:
        existing = list(
            candidate_dir.glob(
                "*.repeat-concordance.json"
            )
        )

        if existing:
            fail(
                "candidate outputs exist without matching "
                "run provenance"
            )

        write_json_atomic(
            path,
            expected,
        )

    return sha256_file(path)


def candidate_record(
    *,
    batch: str,
    target: dict[str, str],
    expected: dict[str, str],
    candidate_source: Path,
    candidate_audit: Path,
    component_audit: Path,
    engine: Path,
    finch,
) -> dict:
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

    if (
        len(replicons)
        != int(
            target[
                "primary_assembly_records"
            ]
        )
    ):
        fail(
            f"{accession}: loaded replicon count mismatch"
        )

    engine_rows = finch.run_repeat_engine(
        engine,
        replicons,
    )

    observed = extract_reference_features(
        engine_rows
    )

    result = compare_reference_features(
        observed,
        expected,
    )

    record = {
        "schema_version": 1,
        "analysis": "selector-v1-repeat-reference-concordance",
        "batch": batch,
        "batch_index": int(
            target["batch_index"]
        ),
        ACCESSION_COLUMN: accession,
        "k_values": [
            150,
            400,
        ],
        "observed": observed,
        "passed": result.passed,
        "mismatches": list(
            result.mismatches
        ),
        "source": {
            "genomic_fasta_file": (
                fasta_path.name
            ),
            "sequence_report_file": (
                sequence_report_path.name
            ),
            "primary_assembly_records": (
                len(replicons)
            ),
        },
    }

    return record


def validate_existing_candidate(
    path: Path,
    *,
    batch: str,
    target: dict[str, str],
    expected: dict[str, str],
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

    if record.get("schema_version") != 1:
        fail(
            f"{accession}: existing schema mismatch"
        )

    if (
        record.get("analysis")
        != "selector-v1-repeat-reference-concordance"
    ):
        fail(
            f"{accession}: existing analysis mismatch"
        )

    if record.get("batch") != batch:
        fail(
            f"{accession}: existing batch mismatch"
        )

    if (
        record.get("batch_index")
        != int(
            target["batch_index"]
        )
    ):
        fail(
            f"{accession}: existing batch_index mismatch"
        )

    if (
        record.get(
            ACCESSION_COLUMN
        )
        != accession
    ):
        fail(
            f"{accession}: existing accession mismatch"
        )

    if record.get("k_values") != [
        150,
        400,
    ]:
        fail(
            f"{accession}: existing k-value mismatch"
        )

    observed = record.get(
        "observed"
    )

    if not isinstance(
        observed,
        dict,
    ):
        fail(
            f"{accession}: existing observed features missing"
        )

    result = compare_reference_features(
        observed,
        expected,
    )

    if not result.passed:
        fail(
            f"{accession}: existing candidate no longer "
            f"matches frozen reference: "
            + ",".join(
                result.mismatches
            )
        )

    if record.get("passed") is not True:
        fail(
            f"{accession}: existing candidate is not PASS"
        )

    if record.get("mismatches") != []:
        fail(
            f"{accession}: existing mismatch list is not empty"
        )

    return sha256_file(path)


def main() -> None:
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

    args = parser.parse_args()

    if not args.snapshot_root.is_dir():
        fail(
            f"snapshot root missing: "
            f"{args.snapshot_root}"
        )

    if not args.engine.is_file():
        fail(
            f"repeat engine missing: {args.engine}"
        )

    targets = read_targets(
        args.targets,
        args.batch,
    )

    reference = read_reference_matrix(
        args.reference_matrix,
        args.batch,
    )

    validate_target_reference_alignment(
        targets,
        reference,
    )

    batch_source = (
        args.snapshot_root
        / args.batch
    )

    if not batch_source.is_dir():
        fail(
            f"source batch missing: "
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
        candidate_audit=candidate_audit,
        component_audit=component_audit,
    )

    provenance_path = (
        batch_output
        / "run-provenance.json"
    )

    provenance_sha = (
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

        output_path = (
            candidate_output
            / (
                accession
                + ".repeat-concordance.json"
            )
        )

        expected = reference[
            accession
        ]

        if output_path.exists():
            output_sha = (
                validate_existing_candidate(
                    output_path,
                    batch=args.batch,
                    target=target,
                    expected=expected,
                )
            )

            reused += 1

        else:
            source = (
                batch_source
                / "package"
                / "ncbi_dataset"
                / "data"
                / accession
            )

            record = candidate_record(
                batch=args.batch,
                target=target,
                expected=expected,
                candidate_source=source,
                candidate_audit=candidate_audit,
                component_audit=component_audit,
                engine=args.engine,
                finch=finch,
            )

            output_sha = write_json_atomic(
                output_path,
                record,
            )

            computed += 1

            if record["passed"] is not True:
                fail(
                    f"{accession}: reference concordance "
                    f"FAILED: "
                    + ",".join(
                        record["mismatches"]
                    )
                )

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
                "output_sha256": output_sha,
            }
        )

    results_path = (
        batch_output
        / "candidate-results.tsv"
    )

    results_sha = write_tsv_atomic(
        results_path,
        [
            "position",
            "batch_index",
            "accession",
            "output_file",
            "output_sha256",
        ],
        result_rows,
    )

    summary = {
        "schema_version": 1,
        "analysis": "selector-v1-repeat-reference-concordance",
        "batch": args.batch,
        "target_count": len(targets),
        "all_pass": True,
        "run_provenance_sha256": provenance_sha,
        "candidate_results_sha256": results_sha,
    }

    summary_path = (
        batch_output
        / "batch-summary.json"
    )

    summary_sha = write_json_atomic(
        summary_path,
        summary,
    )

    print(
        "PASS | repeat reference concordance batch"
    )
    print(
        f"batch\t{args.batch}"
    )
    print(
        f"targets\t{len(targets)}"
    )
    print(
        f"computed\t{computed}"
    )
    print(
        f"reused\t{reused}"
    )
    print(
        f"candidate_results_sha256\t{results_sha}"
    )
    print(
        f"batch_summary_sha256\t{summary_sha}"
    )


if __name__ == "__main__":
    main()
