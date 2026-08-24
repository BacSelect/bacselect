"""Tests for the selector-v1 repeat-concordance batch worker."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]

WORKER = (
    REPO
    / "validation"
    / "selector-v1"
    / "run_repeat_concordance_batch.py"
)


def load_worker():
    spec = importlib.util.spec_from_file_location(
        "bacselect_repeat_concordance_worker_test",
        WORKER,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"cannot load worker: {WORKER}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


worker = load_worker()


def reference_row() -> dict[str, str]:
    return {
        "batch": "batch-001",
        "batch_index": "7",
        "canonical_genbank_assembly_accession": "TEST_000001.1",
        "01_total_genome_length": "1000",
        "03_replicon_count": "1",
        "06_non_unique_canonical_150mer_fraction": "0.125",
        "07_non_unique_canonical_400mer_fraction": "0.0625",
        "08_maximum_canonical_150mer_multiplicity": "7",
        "09_maximum_canonical_400mer_multiplicity": "3",
        "11_inter_replicon_shared_canonical_150mer_fraction": "0.25",
        "12_inter_replicon_shared_canonical_400mer_fraction": "0.125",
    }


def target_row() -> dict[str, str]:
    return {
        "batch": "batch-001",
        "batch_index": "7",
        "canonical_genbank_assembly_accession": "TEST_000001.1",
        "total_sequence_length": "1000",
        "primary_assembly_records": "1",
        "topology_circular_records": "1",
        "topology_linear_records": "0",
    }


def passing_candidate_record() -> dict:
    return {
        "schema_version": 1,
        "analysis": "selector-v1-repeat-reference-concordance",
        "batch": "batch-001",
        "batch_index": 7,
        "canonical_genbank_assembly_accession": "TEST_000001.1",
        "k_values": [
            150,
            400,
        ],
        "observed": {
            "06_non_unique_canonical_150mer_fraction": 0.125,
            "07_non_unique_canonical_400mer_fraction": 0.0625,
            "08_maximum_canonical_150mer_multiplicity": 7,
            "09_maximum_canonical_400mer_multiplicity": 3,
            "11_inter_replicon_shared_canonical_150mer_fraction": 0.25,
            "12_inter_replicon_shared_canonical_400mer_fraction": 0.125,
        },
        "passed": True,
        "mismatches": [],
        "source": {
            "genomic_fasta_file": "synthetic.fna",
            "sequence_report_file": "sequence_report.jsonl",
            "primary_assembly_records": 1,
        },
    }


def test_existing_pass_candidate_is_reusable(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "TEST_000001.1.repeat-concordance.json"
    )

    worker.write_json_atomic(
        path,
        passing_candidate_record(),
    )

    observed_sha = worker.validate_existing_candidate(
        path,
        batch="batch-001",
        target=target_row(),
        expected=reference_row(),
    )

    assert observed_sha == worker.sha256_file(path)


def test_existing_binary64_mismatch_fails(
    tmp_path: Path,
) -> None:
    record = passing_candidate_record()

    record["observed"][
        "06_non_unique_canonical_150mer_fraction"
    ] = float.fromhex(
        "0x1.0000000000001p-3"
    )

    record["passed"] = False
    record["mismatches"] = [
        "06_non_unique_canonical_150mer_fraction"
    ]

    path = (
        tmp_path
        / "TEST_000001.1.repeat-concordance.json"
    )

    worker.write_json_atomic(
        path,
        record,
    )

    with pytest.raises(
        RuntimeError,
        match="no longer matches frozen reference",
    ):
        worker.validate_existing_candidate(
            path,
            batch="batch-001",
            target=target_row(),
            expected=reference_row(),
        )


def test_existing_false_pass_flag_fails(
    tmp_path: Path,
) -> None:
    record = passing_candidate_record()
    record["passed"] = False

    path = (
        tmp_path
        / "TEST_000001.1.repeat-concordance.json"
    )

    worker.write_json_atomic(
        path,
        record,
    )

    with pytest.raises(
        RuntimeError,
        match="existing candidate is not PASS",
    ):
        worker.validate_existing_candidate(
            path,
            batch="batch-001",
            target=target_row(),
            expected=reference_row(),
        )


def test_existing_nonempty_mismatch_list_fails(
    tmp_path: Path,
) -> None:
    record = passing_candidate_record()
    record["mismatches"] = ["unexpected"]

    path = (
        tmp_path
        / "TEST_000001.1.repeat-concordance.json"
    )

    worker.write_json_atomic(
        path,
        record,
    )

    with pytest.raises(
        RuntimeError,
        match="existing mismatch list is not empty",
    ):
        worker.validate_existing_candidate(
            path,
            batch="batch-001",
            target=target_row(),
            expected=reference_row(),
        )


def test_atomic_tsv_is_independent_of_execution_disposition(
    tmp_path: Path,
) -> None:
    # The canonical result table deliberately contains no
    # computed/reused field. It depends only on the candidate
    # identity and immutable output hash.
    rows = [
        {
            "position": 1,
            "batch_index": 7,
            "accession": "TEST_000001.1",
            "output_file": (
                "TEST_000001.1.repeat-concordance.json"
            ),
            "output_sha256": "a" * 64,
        }
    ]

    fields = [
        "position",
        "batch_index",
        "accession",
        "output_file",
        "output_sha256",
    ]

    first = tmp_path / "first.tsv"
    second = tmp_path / "second.tsv"

    first_sha = worker.write_tsv_atomic(
        first,
        fields,
        rows,
    )

    second_sha = worker.write_tsv_atomic(
        second,
        fields,
        rows,
    )

    assert first.read_bytes() == second.read_bytes()
    assert first_sha == second_sha
