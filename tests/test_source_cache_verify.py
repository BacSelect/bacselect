from pathlib import Path
import ast
import csv
import hashlib
import json

import pytest

from bacselect.source_cache_verify import (
    ACCESSION_FIELDS,
    ALLOWED_SNAPSHOT_SCRIPT_SHA256,
    EXPECTED_HISTORICAL_ACCESSIONS,
    EXPECTED_HISTORICAL_BATCHES,
    EXPECTED_PACKAGE_MANIFEST_ROWS,
    HISTORICAL_DATASETS_VERSION,
    HISTORICAL_ENV_LOCK_SHA256,
    aggregate_verifications,
    path_scope,
    resolve_manifest_path,
    sha256_file,
    verify_batch,
    verify_manifest_row,
    write_batch_verification,
)


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def write_tsv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def make_batch(
    root,
    name="batch-001",
    accessions=("GCA_000000001.1", "GCA_000000002.1"),
):
    batch = root / name
    package = batch / "package"
    package.mkdir(parents=True)

    (batch / "accessions.txt").write_text(
        "".join(f"{accession}\n" for accession in accessions),
        encoding="utf-8",
    )

    write_tsv(
        batch / "candidate-sequence-audit.tsv",
        ["canonical_genbank_assembly_accession"],
        [
            {"canonical_genbank_assembly_accession": accession}
            for accession in accessions
        ],
    )

    write_tsv(
        batch / "component-sequence-audit.tsv",
        ["canonical_genbank_assembly_accession", "component"],
        [
            {
                "canonical_genbank_assembly_accession": accession,
                "component": f"COMP{index}",
            }
            for index, accession in enumerate(accessions, 1)
        ],
    )

    files = []

    common = package / "ncbi_dataset" / "data" / "assembly_data_report.jsonl"
    common.parent.mkdir(parents=True, exist_ok=True)
    common.write_bytes(b"common\n")
    files.append(
        {
            "path": "ncbi_dataset/data/assembly_data_report.jsonl",
            "size_bytes": str(common.stat().st_size),
            "sha256": sha256_file(common),
        }
    )

    for accession in accessions:
        accession_dir = package / "ncbi_dataset" / "data" / accession
        accession_dir.mkdir(parents=True)

        for suffix, payload in (
            ("genomic.fna", f">{accession}\nACGT\n".encode()),
            ("genomic.gbff", f"LOCUS {accession}\n".encode()),
            ("sequence_report.jsonl", b"{}\n"),
        ):
            path = accession_dir / suffix
            path.write_bytes(payload)
            files.append(
                {
                    "path": (
                        f"ncbi_dataset/data/{accession}/{suffix}"
                    ),
                    "size_bytes": str(path.stat().st_size),
                    "sha256": sha256_file(path),
                }
            )

    write_tsv(
        batch / "package-files.tsv",
        ["path", "size_bytes", "sha256"],
        files,
    )

    (batch / "dehydrated.zip").write_bytes(b"zip\n")
    (batch / "attempt-origin.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    summary = {
        "datasets_version": HISTORICAL_DATASETS_VERSION,
        "environment_explicit_sha256": HISTORICAL_ENV_LOCK_SHA256,
        "snapshot_script_sha256": sorted(
            ALLOWED_SNAPSHOT_SCRIPT_SHA256
        )[0],
    }

    for field, filename in (
        ("accessions_sha256", "accessions.txt"),
        (
            "candidate_sequence_audit_sha256",
            "candidate-sequence-audit.tsv",
        ),
        (
            "component_sequence_audit_sha256",
            "component-sequence-audit.tsv",
        ),
        ("package_files_sha256", "package-files.tsv"),
        ("dehydrated_zip_sha256", "dehydrated.zip"),
        ("attempt_origin_sha256", "attempt-origin.json"),
    ):
        summary[field] = sha256_file(batch / filename)

    (batch / "batch-summary.json").write_text(
        json.dumps(summary) + "\n",
        encoding="utf-8",
    )

    return batch


def test_frozen_historical_constants():
    assert EXPECTED_HISTORICAL_BATCHES == 111
    assert EXPECTED_HISTORICAL_ACCESSIONS == 55426
    assert EXPECTED_PACKAGE_MANIFEST_ROWS == 166844
    assert HISTORICAL_DATASETS_VERSION == "18.35.0"
    assert len(ALLOWED_SNAPSHOT_SCRIPT_SHA256) == 4


def test_path_scope_common():
    assert path_scope(
        "ncbi_dataset/data/assembly_data_report.jsonl"
    ) == ("batch_common", "")


def test_path_scope_single_accession_even_if_repeated():
    path = (
        "ncbi_dataset/data/GCA_000000001.1/"
        "GCA_000000001.1_genomic.fna"
    )
    assert path_scope(path) == (
        "accession",
        "GCA_000000001.1",
    )


def test_path_scope_multiple_distinct_accessions_fails():
    with pytest.raises(ValueError, match="multiple distinct"):
        path_scope(
            "GCA_000000001.1/GCA_000000002.1_genomic.fna"
        )


def test_manifest_path_rejects_parent_traversal(tmp_path):
    batch = tmp_path / "batch-001"
    batch.mkdir()

    with pytest.raises(ValueError, match="unsafe"):
        resolve_manifest_path(batch, "../escape")


def test_manifest_path_requires_exactly_one_existing_layout(tmp_path):
    batch = tmp_path / "batch-001"
    (batch / "package").mkdir(parents=True)

    with pytest.raises(ValueError, match="exactly one"):
        resolve_manifest_path(batch, "missing")


def test_manifest_row_passes(tmp_path):
    batch = tmp_path / "batch-001"
    target = (
        batch
        / "package"
        / "ncbi_dataset"
        / "data"
        / "GCA_000000001.1"
        / "genomic.fna"
    )
    target.parent.mkdir(parents=True)
    target.write_bytes(b"ACGT\n")

    row = {
        "path": (
            "ncbi_dataset/data/GCA_000000001.1/genomic.fna"
        ),
        "size_bytes": str(target.stat().st_size),
        "sha256": sha256_file(target),
    }

    result = verify_manifest_row(batch, row)

    assert result.status == "pass"
    assert result.accession == "GCA_000000001.1"


def test_manifest_row_size_mismatch_avoids_hash(tmp_path):
    batch = tmp_path / "batch-001"
    target = batch / "package" / "common.txt"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"abc")

    result = verify_manifest_row(
        batch,
        {
            "path": "common.txt",
            "size_bytes": "4",
            "sha256": sha_bytes(b"abcd"),
        },
    )

    assert result.status == "size_mismatch"
    assert result.observed_sha256 == ""


def test_manifest_row_sha_mismatch(tmp_path):
    batch = tmp_path / "batch-001"
    target = batch / "package" / "common.txt"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"abc")

    result = verify_manifest_row(
        batch,
        {
            "path": "common.txt",
            "size_bytes": "3",
            "sha256": sha_bytes(b"xyz"),
        },
    )

    assert result.status == "sha256_mismatch"


def test_complete_batch_passes(tmp_path):
    batch = make_batch(tmp_path)

    files, accessions, summary = verify_batch(batch)

    assert all(row.status == "pass" for row in files)
    assert all(
        row["cache_content_verification"] == "pass"
        for row in accessions
    )
    assert summary["cache_content_pass"] == 2
    assert summary["cache_content_fallback_to_fresh"] == 0


def test_corrupt_accession_file_only_falls_back_that_accession(tmp_path):
    batch = make_batch(tmp_path)

    target = (
        batch
        / "package"
        / "ncbi_dataset"
        / "data"
        / "GCA_000000001.1"
        / "genomic.fna"
    )
    target.write_bytes(b"X" * target.stat().st_size)

    _, accessions, summary = verify_batch(batch)

    by_accession = {
        row["canonical_genbank_assembly_accession"]:
            row["cache_content_verification"]
        for row in accessions
    }

    assert by_accession["GCA_000000001.1"] == "fallback_to_fresh"
    assert by_accession["GCA_000000002.1"] == "pass"
    assert summary["cache_content_fallback_to_fresh"] == 1


def test_corrupt_common_file_falls_back_whole_batch(tmp_path):
    batch = make_batch(tmp_path)

    target = (
        batch
        / "package"
        / "ncbi_dataset"
        / "data"
        / "assembly_data_report.jsonl"
    )
    target.write_bytes(b"XXXXXX\n")

    _, accessions, summary = verify_batch(batch)

    assert all(
        row["cache_content_verification"] == "fallback_to_fresh"
        for row in accessions
    )
    assert summary["cache_content_fallback_to_fresh"] == 2


def test_bad_datasets_version_falls_back_whole_batch(tmp_path):
    batch = make_batch(tmp_path)

    path = batch / "batch-summary.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["datasets_version"] = "99.0.0"
    path.write_text(json.dumps(obj) + "\n", encoding="utf-8")

    _, accessions, summary = verify_batch(batch)

    assert all(
        row["cache_content_verification"] == "fallback_to_fresh"
        for row in accessions
    )
    assert "datasets_version" in summary["small_provenance_failures"]


def test_unrecognized_script_identity_falls_back_whole_batch(tmp_path):
    batch = make_batch(tmp_path)

    path = batch / "batch-summary.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["snapshot_script_sha256"] = "0" * 64
    path.write_text(json.dumps(obj) + "\n", encoding="utf-8")

    _, accessions, summary = verify_batch(batch)

    assert all(
        row["cache_content_verification"] == "fallback_to_fresh"
        for row in accessions
    )
    assert "snapshot_script_sha256" in summary["small_provenance_failures"]


def test_write_batch_verification_is_self_hashing(tmp_path):
    batch = make_batch(tmp_path / "snapshot")
    out = tmp_path / "result"

    summary = write_batch_verification(batch, out)

    assert (
        sha256_file(out / "accession-cache-verification.tsv")
        == summary["accession_cache_verification_sha256"]
    )
    assert (
        sha256_file(out / "package-file-verification.tsv")
        == summary["package_file_verification_sha256"]
    )


def test_aggregate_two_batches(tmp_path):
    snapshot = tmp_path / "snapshot"

    batch1 = make_batch(
        snapshot,
        "batch-001",
        ("GCA_000000001.1",),
    )
    batch2 = make_batch(
        snapshot,
        "batch-002",
        ("GCA_000000002.1",),
    )

    results = tmp_path / "results"
    write_batch_verification(batch1, results / "batch-001")
    write_batch_verification(batch2, results / "batch-002")

    out = tmp_path / "aggregate"

    summary = aggregate_verifications(
        [
            results / "batch-001",
            results / "batch-002",
        ],
        out,
        expected_batches=2,
        expected_accessions=2,
        expected_package_rows=8,
    )

    assert summary["batch_count"] == 2
    assert summary["accession_count"] == 2
    assert summary["cache_content_pass"] == 2


def test_aggregate_duplicate_accession_fails(tmp_path):
    snapshot = tmp_path / "snapshot"

    batch1 = make_batch(
        snapshot,
        "batch-001",
        ("GCA_000000001.1",),
    )
    batch2 = make_batch(
        snapshot,
        "batch-002",
        ("GCA_000000001.1",),
    )

    results = tmp_path / "results"
    write_batch_verification(batch1, results / "batch-001")
    write_batch_verification(batch2, results / "batch-002")

    with pytest.raises(ValueError, match="duplicate accession"):
        aggregate_verifications(
            [
                results / "batch-001",
                results / "batch-002",
            ],
            tmp_path / "aggregate",
            expected_batches=2,
            expected_accessions=None,
            expected_package_rows=None,
        )


def test_aggregate_rejects_wrong_batch_count(tmp_path):
    with pytest.raises(ValueError, match="expected 2 batch results"):
        aggregate_verifications(
            [],
            tmp_path / "aggregate",
            expected_batches=2,
            expected_accessions=None,
            expected_package_rows=None,
        )


def test_module_has_no_network_or_selector_interfaces():
    import bacselect.source_cache_verify as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_roots = set()
    argument_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", 1)[0]
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_roots.add(
                    node.module.split(".", 1)[0]
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            argument_names.update(
                arg.arg.lower()
                for arg in (
                    list(node.args.posonlyargs)
                    + list(node.args.args)
                    + list(node.args.kwonlyargs)
                )
            )

    assert imported_roots.isdisjoint(
        {"requests", "urllib", "httpx", "aiohttp"}
    )

    forbidden_arguments = {
        "ops",
        "sr",
        "selector",
        "panel_identity",
        "distance",
        "structural_features",
        "taxonomy",
        "species",
        "organism",
    }

    assert argument_names.isdisjoint(forbidden_arguments)
