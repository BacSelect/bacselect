from pathlib import Path
import csv
import hashlib
import json

import pytest

import bacselect.source_acquisition_manifest as module
from bacselect.source_acquisition_manifest import (
    EXPECTED_CACHE_VERIFICATION_SHA256,
    EXPECTED_RAW_SOURCE_SHA256,
    _bool01,
    _reuse_failure_reason,
    sha256_file,
)
from bacselect.source_sequence_plan import SequencePlan


def test_frozen_input_hashes():
    assert EXPECTED_RAW_SOURCE_SHA256 == (
        "b1b016891ae4e976d03606dfb2f35f74b03d21cf3ec82832f77f4d113bd622d5"
    )
    assert EXPECTED_CACHE_VERIFICATION_SHA256 == (
        "7b2fa38ff2c1f43fc0536cabfa68091fdde9d4d3677092d49405bbac113fd752"
    )


def test_expected_counts_are_frozen():
    assert module.EXPECTED_SOURCE_RECORDS == 70850
    assert module.EXPECTED_HISTORICAL_BATCHES == 111
    assert module.EXPECTED_HISTORICAL_ACCESSIONS == 55426
    assert module.EXPECTED_LAST_FRESH_BATCH_SIZE == 326


def test_bool01():
    assert _bool01("1", field="x") is True
    assert _bool01("0", field="x") is False

    with pytest.raises(ValueError, match="expected 0 or 1"):
        _bool01("true", field="x")


def historical_row():
    return {
        "canonical_genbank_assembly_accession": "GCA_000000001.1",
        "current_accession": "GCA_000000001.1",
        "assembly_status": "current",
        "assembly_level": "Complete Genome",
        "expected_biosample": "SAMN00000001",
        "observed_biosample": "SAMN00000001",
        "sequence_eligibility": "eligible",
        "exclusion_reasons": "none",
    }


def verification(**updates):
    values = dict(
        batch="batch-001",
        package_file_count=3,
        accession_package_files_pass=True,
        batch_common_provenance_pass=True,
        cache_content_verification="pass",
    )
    values.update(updates)
    return module.CacheVerification(**values)


def test_reuse_reason_content_failure():
    assert _reuse_failure_reason(
        "SAMN00000001",
        historical_row(),
        verification(cache_content_verification="fallback_to_fresh"),
    ) == "cache_content_not_verified"


def test_reuse_reason_current_accession_mismatch():
    row = historical_row()
    row["current_accession"] = "GCA_000000002.1"

    assert _reuse_failure_reason(
        "SAMN00000001",
        row,
        verification(),
    ) == "historical_current_accession_mismatch"


def test_reuse_reason_biosample_mismatch():
    assert _reuse_failure_reason(
        "SAMN99999999",
        historical_row(),
        verification(),
    ) == "fresh_historical_expected_biosample_mismatch"


def test_write_manifests_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "EXPECTED_METADATA_RETAINED", 3)
    monkeypatch.setattr(module, "EXPECTED_CACHE_CANDIDATES", 1)
    monkeypatch.setattr(module, "EXPECTED_UNCACHED", 2)
    monkeypatch.setattr(module, "EXPECTED_FRESH_BATCHES", 1)
    monkeypatch.setattr(module, "EXPECTED_LAST_FRESH_BATCH_SIZE", 2)

    build = module.AcquisitionBuild(
        plan=SequencePlan(
            cache_candidates=("GCA_000000001.1",),
            fresh_downloads=(
                "GCA_000000002.1",
                "GCA_000000003.1",
            ),
        ),
        cache_rows=(
            {
                "canonical_genbank_assembly_accession": "GCA_000000001.1",
                "fresh_biosample": "SAMN00000001",
                "historical_batch": "batch-001",
                "historical_sequence_eligibility": "eligible",
                "historical_exclusion_reasons": "none",
            },
        ),
        fresh_rows=(
            {
                "canonical_genbank_assembly_accession": "GCA_000000002.1",
                "fresh_biosample": "SAMN00000002",
                "acquisition_reason": "not_in_historical_cache",
            },
            {
                "canonical_genbank_assembly_accession": "GCA_000000003.1",
                "fresh_biosample": "SAMN00000003",
                "acquisition_reason": "not_in_historical_cache",
            },
        ),
        source_record_count=3,
        candidate_audit_hashes=(("batch-001", "a" * 64),),
    )

    out1 = tmp_path / "one"
    out2 = tmp_path / "two"

    summary1 = module.write_acquisition_manifests(build, out1)
    summary2 = module.write_acquisition_manifests(build, out2)

    assert summary1 == summary2

    for name in (
        "cache-reuse-accessions.txt",
        "fresh-download-accessions.txt",
        "cache-reuse-manifest.tsv",
        "fresh-download-manifest.tsv",
        "historical-candidate-audits-sha256.tsv",
        "fresh-batch-index.tsv",
        "acquisition-plan-summary.json",
    ):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes()


def test_output_directory_must_be_new(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "EXPECTED_METADATA_RETAINED", 1)
    monkeypatch.setattr(module, "EXPECTED_CACHE_CANDIDATES", 0)
    monkeypatch.setattr(module, "EXPECTED_UNCACHED", 1)
    monkeypatch.setattr(module, "EXPECTED_FRESH_BATCHES", 1)
    monkeypatch.setattr(module, "EXPECTED_LAST_FRESH_BATCH_SIZE", 1)

    build = module.AcquisitionBuild(
        plan=SequencePlan(
            cache_candidates=(),
            fresh_downloads=("GCA_000000001.1",),
        ),
        cache_rows=(),
        fresh_rows=(
            {
                "canonical_genbank_assembly_accession": "GCA_000000001.1",
                "fresh_biosample": "SAMN00000001",
                "acquisition_reason": "not_in_historical_cache",
            },
        ),
        source_record_count=1,
        candidate_audit_hashes=(),
    )

    out = tmp_path / "existing"
    out.mkdir()

    with pytest.raises(FileExistsError):
        module.write_acquisition_manifests(build, out)


def test_cli_has_no_baseline_input():
    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "--baseline" not in source
    assert "source_membership" not in source


def test_module_has_no_network_library_import():
    source = Path(module.__file__).read_text(encoding="utf-8")

    for token in (
        "import requests",
        "import urllib",
        "import httpx",
        "import aiohttp",
    ):
        assert token not in source


def test_module_does_not_consume_selector_outputs():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()

    for token in (
        "ops",
        "panel_identity",
        "selector_distance",
        "coverage.tsv",
    ):
        assert token not in source


def test_sha256_file(tmp_path):
    path = tmp_path / "value"
    path.write_bytes(b"abc")

    assert sha256_file(path) == hashlib.sha256(b"abc").hexdigest()
