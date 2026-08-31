from pathlib import Path
from types import SimpleNamespace

import pytest

import bacselect.monthly_sequence_plan as module
from bacselect.monthly_sequence_plan import (
    CACHE_METADATA_MISMATCH,
    CACHE_NOT_CURRENT,
    FRESH_BATCH_SIZE,
    NO_VERIFIED_CACHE,
    VerifiedMonthlyCacheEvidence,
    accession_manifest_bytes,
    accession_manifest_sha256,
    batch_accessions,
    blinded_plan_summary,
    build_monthly_sequence_plan,
)
from bacselect.source_eligibility import (
    EXCLUDE,
    RETAIN,
)


SNAPSHOT = "source-snapshot-20260901T001700Z"


def assessment(
    accession: str,
    biosample: str,
    decision: str = RETAIN,
):
    return SimpleNamespace(
        accession=accession,
        biosample=biosample,
        decision=decision,
    )


def cache_evidence(
    accession: str,
    biosample: str,
    *,
    snapshot: str = SNAPSHOT,
):
    return VerifiedMonthlyCacheEvidence(
        canonical_genbank_assembly_accession=(
            accession
        ),
        biosample=biosample,
        verified_source_snapshot_id=snapshot,
        component_identity_sha256="1" * 64,
        assembly_fingerprint="2" * 64,
        source_evidence_sha256="3" * 64,
        package_manifest_sha256="4" * 64,
        verification_record_sha256="5" * 64,
    )


def test_first_monthly_release_empty_cache_is_all_fresh():
    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
            assessment(
                "GCA_000000002.1",
                "SAMN00000002",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    assert plan.cache_reuse_accessions == ()
    assert plan.fresh_acquisition_accessions == (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )
    assert plan.fresh_reasons == (
        (
            "GCA_000000001.1",
            NO_VERIFIED_CACHE,
        ),
        (
            "GCA_000000002.1",
            NO_VERIFIED_CACHE,
        ),
    )


def test_current_verified_cache_is_reused():
    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (
            cache_evidence(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        source_snapshot_id=SNAPSHOT,
    )

    assert plan.cache_reuse_accessions == (
        "GCA_000000001.1",
    )
    assert plan.fresh_acquisition_accessions == ()


def test_stale_cache_proof_forces_fresh_acquisition():
    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (
            cache_evidence(
                "GCA_000000001.1",
                "SAMN00000001",
                snapshot=(
                    "source-snapshot-20260801T001700Z"
                ),
            ),
        ),
        source_snapshot_id=SNAPSHOT,
    )

    assert plan.cache_reuse_accessions == ()
    assert plan.fresh_reasons == (
        (
            "GCA_000000001.1",
            CACHE_NOT_CURRENT,
        ),
    )


def test_cache_metadata_change_forces_fresh_acquisition():
    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000002",
            ),
        ),
        (
            cache_evidence(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        source_snapshot_id=SNAPSHOT,
    )

    assert plan.cache_reuse_accessions == ()
    assert plan.fresh_reasons == (
        (
            "GCA_000000001.1",
            CACHE_METADATA_MISMATCH,
        ),
    )


def test_malformed_cache_identity_fails_closed():
    evidence = cache_evidence(
        "GCA_000000001.1",
        "SAMN00000001",
    )

    evidence = VerifiedMonthlyCacheEvidence(
        **{
            **evidence.__dict__,
            "assembly_fingerprint": "bad",
        }
    )

    with pytest.raises(
        ValueError,
        match="assembly fingerprint",
    ):
        build_monthly_sequence_plan(
            (
                assessment(
                    "GCA_000000001.1",
                    "SAMN00000001",
                ),
            ),
            (evidence,),
            source_snapshot_id=SNAPSHOT,
        )


def test_duplicate_cache_accession_fails_closed():
    evidence = cache_evidence(
        "GCA_000000001.1",
        "SAMN00000001",
    )

    with pytest.raises(
        ValueError,
        match="duplicate accession",
    ):
        build_monthly_sequence_plan(
            (
                assessment(
                    "GCA_000000001.1",
                    "SAMN00000001",
                ),
            ),
            (
                evidence,
                evidence,
            ),
            source_snapshot_id=SNAPSHOT,
        )


def test_duplicate_retained_accession_fails_closed():
    rows = (
        assessment(
            "GCA_000000001.1",
            "SAMN00000001",
        ),
        assessment(
            "GCA_000000001.1",
            "SAMN00000001",
        ),
    )

    with pytest.raises(
        ValueError,
        match="duplicate metadata-retained",
    ):
        build_monthly_sequence_plan(
            rows,
            (),
            source_snapshot_id=SNAPSHOT,
        )


def test_only_metadata_retained_records_enter_plan():
    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
            assessment(
                "GCA_000000002.1",
                "SAMN00000002",
                EXCLUDE,
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    assert plan.retained_accessions == (
        "GCA_000000001.1",
    )


def test_batching_is_dynamic_not_historical_count_bound():
    accessions = tuple(
        f"GCA_{number:09d}.1"
        for number in range(
            1,
            1202,
        )
    )

    batches = batch_accessions(
        accessions
    )

    assert FRESH_BATCH_SIZE == 500
    assert tuple(
        len(batch)
        for batch in batches
    ) == (
        500,
        500,
        201,
    )


def test_manifest_bytes_and_sha_are_deterministic():
    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )

    payload = accession_manifest_bytes(
        accessions
    )

    assert payload == (
        b"GCA_000000001.1\n"
        b"GCA_000000002.1\n"
    )

    assert (
        accession_manifest_sha256(
            accessions
        )
        == accession_manifest_sha256(
            accessions
        )
    )


def test_blinded_summary_contains_dynamic_counts_only():
    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
            assessment(
                "GCA_000000002.1",
                "SAMN00000002",
            ),
        ),
        (
            cache_evidence(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        source_snapshot_id=SNAPSHOT,
    )

    assert blinded_plan_summary(
        plan
    ) == {
        "metadata_retained": 2,
        "cache_reuse": 1,
        "fresh_acquisition": 1,
        "fresh_batch_size": 500,
        "fresh_batches": 1,
    }


def test_monthly_planner_has_no_historical_execution_bindings():
    text = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "/NGS/",
        "Rhys_wkdir",
        "finch-ncbi-datasets",
        "Project Finch",
        "70_477",
        "55_151",
        "15_326",
        "EXPECTED_TARGETS",
        "EXPECTED_BATCHES",
        "SOURCE_SNAPSHOT_COMMIT",
        "SOURCE_RAW_SHA256",
    )

    for token in forbidden:
        assert token not in text


def test_monthly_planner_has_no_network_execution_surface():
    text = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "subprocess",
        "requests",
        "urllib.request",
        "http.client",
    ):
        assert token not in text
