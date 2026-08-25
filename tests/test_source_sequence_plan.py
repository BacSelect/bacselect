import pytest

from bacselect.source_eligibility import (
    EXCLUDE,
    MetadataAssessment,
    RETAIN,
)
from bacselect.source_sequence_plan import (
    DATASETS_ENV_LOCK_SHA256,
    DATASETS_VERSION,
    DOWNLOAD_ARGS,
    EXPECTED_CACHE_CANDIDATES,
    EXPECTED_FRESH_BATCHES,
    EXPECTED_METADATA_RETAINED,
    EXPECTED_UNCACHED,
    FRESH_BATCH_SIZE,
    REHYDRATE_ARGS,
    SEQUENCE_INCLUDE,
    accession_manifest_bytes,
    batch_accessions,
    blinded_plan_summary,
    build_sequence_plan,
    cache_reuse_eligible,
    manifest_sha256,
    validate_operational_constants,
)


def assessment(accession, biosample="SAMN1", decision=RETAIN):
    return MetadataAssessment(
        accession=accession,
        biosample=biosample,
        decision=decision,
        reasons=(),
        normalized_warnings=(),
    )


def historical_row(accession="GCA_000000001.1"):
    return {
        "canonical_genbank_assembly_accession": accession,
        "current_accession": accession,
        "assembly_status": "current",
        "assembly_level": "Complete Genome",
        "expected_biosample": "SAMN1",
        "observed_biosample": "SAMN1",
        "sequence_eligibility": "eligible",
    }


def test_frozen_counts_and_constants():
    assert EXPECTED_METADATA_RETAINED == 70477
    assert EXPECTED_CACHE_CANDIDATES == 55151
    assert EXPECTED_UNCACHED == 15326
    assert FRESH_BATCH_SIZE == 500
    assert EXPECTED_FRESH_BATCHES == 31
    assert DATASETS_VERSION == "18.35.0"
    assert DATASETS_ENV_LOCK_SHA256 == (
        "6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd"
    )
    validate_operational_constants()


def test_sequence_bundle_is_exact():
    assert SEQUENCE_INCLUDE == ("genome", "gbff", "seq-report")
    assert DOWNLOAD_ARGS == (
        "download",
        "genome",
        "accession",
        "--inputfile",
        "accessions.txt",
        "--include",
        "genome,gbff,seq-report",
        "--dehydrated",
        "--no-progressbar",
        "--filename",
        "dehydrated.zip",
    )
    assert REHYDRATE_ARGS == (
        "rehydrate",
        "--directory",
        "package",
        "--max-workers",
        "10",
        "--no-progressbar",
    )


def test_partition_is_cache_membership_not_baseline_membership():
    plan = build_sequence_plan(
        [
            assessment("GCA_000000001.1"),
            assessment("GCA_000000002.1"),
            assessment("GCA_000000003.1", decision=EXCLUDE),
        ],
        [
            "GCA_000000001.1",
            "GCA_000000009.1",
        ],
        expected_retained=2,
    )

    assert plan.cache_candidates == ("GCA_000000001.1",)
    assert plan.fresh_downloads == ("GCA_000000002.1",)


def test_expected_retained_count_fails_closed():
    with pytest.raises(ValueError, match="expected 3"):
        build_sequence_plan(
            [assessment("GCA_000000001.1")],
            [],
            expected_retained=3,
        )


def test_duplicate_historical_accession_fails_closed():
    with pytest.raises(ValueError, match="duplicate canonical accession"):
        build_sequence_plan(
            [assessment("GCA_000000001.1")],
            [
                "GCA_000000001.1",
                "GCA_000000001.1",
            ],
        )


def test_fresh_batching_is_deterministic():
    accessions = tuple(
        f"GCA_{index:09d}.1"
        for index in range(1, 8)
    )

    batches = batch_accessions(
        accessions,
        batch_size=3,
    )

    assert [len(batch) for batch in batches] == [3, 3, 1]
    assert batches[0][0] == "GCA_000000001.1"
    assert batches[-1][-1] == "GCA_000000007.1"


def test_unsorted_batch_input_fails():
    with pytest.raises(ValueError, match="sorted"):
        batch_accessions(
            (
                "GCA_000000002.1",
                "GCA_000000001.1",
            )
        )


def test_manifest_bytes_are_exact():
    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )

    assert accession_manifest_bytes(accessions) == (
        b"GCA_000000001.1\n"
        b"GCA_000000002.1\n"
    )


def test_manifest_sha_is_deterministic():
    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )

    assert manifest_sha256(accessions) == manifest_sha256(accessions)


def test_blinded_summary_contains_only_counts():
    plan = build_sequence_plan(
        [
            assessment("GCA_000000001.1"),
            assessment("GCA_000000002.1"),
            assessment("GCA_000000003.1"),
        ],
        ["GCA_000000001.1"],
    )

    summary = blinded_plan_summary(
        plan,
        fresh_batch_size=2,
    )

    assert summary == {
        "metadata_retained": 3,
        "cache_candidates": 1,
        "fresh_downloads": 2,
        "fresh_batch_size": 2,
        "fresh_batches": 1,
    }

    assert "GCA_" not in repr(summary)
    assert "SAMN" not in repr(summary)


def test_cache_reuse_accepts_exact_reconciled_verified_evidence():
    assert cache_reuse_eligible(
        fresh_biosample="SAMN1",
        historical_row=historical_row(),
        package_integrity_verified=True,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("current_accession", "GCA_000000002.1"),
        ("assembly_status", "previous"),
        ("assembly_level", "Chromosome"),
        ("expected_biosample", "SAMN2"),
        ("observed_biosample", "SAMN2"),
    ],
)
def test_cache_reuse_rejects_metadata_mismatch(field, value):
    row = historical_row()
    row[field] = value

    assert not cache_reuse_eligible(
        fresh_biosample="SAMN1",
        historical_row=row,
        package_integrity_verified=True,
    )


def test_cache_reuse_rejects_unverified_package_integrity():
    assert not cache_reuse_eligible(
        fresh_biosample="SAMN1",
        historical_row=historical_row(),
        package_integrity_verified=False,
    )


def test_historical_sequence_ineligible_does_not_disable_evidence_reuse():
    row = historical_row()
    row["sequence_eligibility"] = "ineligible"

    assert cache_reuse_eligible(
        fresh_biosample="SAMN1",
        historical_row=row,
        package_integrity_verified=True,
    )
