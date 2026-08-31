from pathlib import Path
import json
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
    fresh_target_manifest_bytes,
    fresh_target_manifest_sha256,
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


def test_plan_preserves_source_snapshot_identity():
    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    assert plan.source_snapshot_id == SNAPSHOT


def test_fresh_target_preserves_expected_biosample_and_reason():
    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    assert len(
        plan.fresh_acquisition_targets
    ) == 1

    target = (
        plan.fresh_acquisition_targets[0]
    )

    assert (
        target.canonical_genbank_assembly_accession
        == "GCA_000000001.1"
    )
    assert (
        target.source_biosample
        == "SAMN00000001"
    )
    assert (
        target.acquisition_reason
        == NO_VERIFIED_CACHE
    )


def test_fresh_target_manifest_bytes_are_exact_and_deterministic():
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

    observed = fresh_target_manifest_bytes(
        plan
    )

    assert observed == (
        b"canonical_genbank_assembly_accession"
        b"\tsource_biosample"
        b"\tacquisition_reason\n"
        b"GCA_000000001.1"
        b"\tSAMN00000001"
        b"\tno_verified_cache\n"
        b"GCA_000000002.1"
        b"\tSAMN00000002"
        b"\tno_verified_cache\n"
    )

    assert (
        fresh_target_manifest_sha256(
            plan
        )
        == fresh_target_manifest_sha256(
            plan
        )
    )


def test_fresh_target_manifest_tracks_current_metadata_after_cache_mismatch():
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

    target = (
        plan.fresh_acquisition_targets[0]
    )

    assert (
        target.source_biosample
        == "SAMN00000002"
    )
    assert (
        target.acquisition_reason
        == CACHE_METADATA_MISMATCH
    )


def test_sequence_plan_record_binds_source_snapshot_and_manifest():
    from bacselect.monthly_sequence_plan import (
        audit_monthly_sequence_plan_record,
        fresh_target_manifest_bytes,
        serialize_monthly_sequence_plan_record,
    )

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

    snapshot_record_sha = (
        "a" * 64
    )

    payload = (
        serialize_monthly_sequence_plan_record(
            plan,
            source_snapshot_record_sha256=(
                snapshot_record_sha
            ),
        )
    )

    record = audit_monthly_sequence_plan_record(
        payload,
        source_snapshot_id=SNAPSHOT,
        source_snapshot_record_sha256=(
            snapshot_record_sha
        ),
        fresh_target_manifest=(
            fresh_target_manifest_bytes(
                plan
            )
        ),
    )

    assert record[
        "source_snapshot_id"
    ] == SNAPSHOT

    assert record[
        "source_snapshot_record_sha256"
    ] == snapshot_record_sha

    assert record[
        "fresh_acquisition_count"
    ] == 2

    assert record[
        "fresh_batch_count"
    ] == 1


def test_sequence_plan_record_is_canonical_and_deterministic():
    from bacselect.monthly_sequence_plan import (
        serialize_monthly_sequence_plan_record,
    )

    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    first = serialize_monthly_sequence_plan_record(
        plan,
        source_snapshot_record_sha256=(
            "b" * 64
        ),
    )

    second = serialize_monthly_sequence_plan_record(
        plan,
        source_snapshot_record_sha256=(
            "b" * 64
        ),
    )

    assert first == second
    assert first.endswith(
        b"\n"
    )


def test_sequence_plan_record_refuses_wrong_source_snapshot():
    from bacselect.monthly_sequence_plan import (
        audit_monthly_sequence_plan_record,
        fresh_target_manifest_bytes,
        serialize_monthly_sequence_plan_record,
    )

    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    payload = (
        serialize_monthly_sequence_plan_record(
            plan,
            source_snapshot_record_sha256=(
                "c" * 64
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="source snapshot changed",
    ):
        audit_monthly_sequence_plan_record(
            payload,
            source_snapshot_id=(
                "different-source-snapshot"
            ),
            source_snapshot_record_sha256=(
                "c" * 64
            ),
            fresh_target_manifest=(
                fresh_target_manifest_bytes(
                    plan
                )
            ),
        )


def test_sequence_plan_record_refuses_wrong_stage1_record_sha():
    from bacselect.monthly_sequence_plan import (
        audit_monthly_sequence_plan_record,
        fresh_target_manifest_bytes,
        serialize_monthly_sequence_plan_record,
    )

    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    payload = (
        serialize_monthly_sequence_plan_record(
            plan,
            source_snapshot_record_sha256=(
                "d" * 64
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="source-snapshot record fingerprint changed",
    ):
        audit_monthly_sequence_plan_record(
            payload,
            source_snapshot_id=SNAPSHOT,
            source_snapshot_record_sha256=(
                "e" * 64
            ),
            fresh_target_manifest=(
                fresh_target_manifest_bytes(
                    plan
                )
            ),
        )


def test_sequence_plan_record_refuses_wrong_fresh_manifest():
    from bacselect.monthly_sequence_plan import (
        audit_monthly_sequence_plan_record,
        serialize_monthly_sequence_plan_record,
    )

    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    payload = (
        serialize_monthly_sequence_plan_record(
            plan,
            source_snapshot_record_sha256=(
                "f" * 64
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="fresh-target manifest fingerprint changed",
    ):
        audit_monthly_sequence_plan_record(
            payload,
            source_snapshot_id=SNAPSHOT,
            source_snapshot_record_sha256=(
                "f" * 64
            ),
            fresh_target_manifest=(
                b"canonical_genbank_assembly_accession"
                b"\tsource_biosample"
                b"\tacquisition_reason\n"
            ),
        )


def test_sequence_plan_record_contains_no_historical_population_constant():
    from bacselect.monthly_sequence_plan import (
        serialize_monthly_sequence_plan_record,
    )

    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    payload = (
        serialize_monthly_sequence_plan_record(
            plan,
            source_snapshot_record_sha256=(
                "1" * 64
            ),
        )
    )

    assert b"15326" not in payload
    assert b"31" not in payload


def test_sequence_plan_record_refuses_fresh_count_not_matching_manifest():
    from bacselect.monthly_sequence_plan import (
        audit_monthly_sequence_plan_record,
        fresh_target_manifest_bytes,
        serialize_monthly_sequence_plan_record,
    )

    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    payload = serialize_monthly_sequence_plan_record(
        plan,
        source_snapshot_record_sha256=(
            "2" * 64
        ),
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    record[
        "fresh_acquisition_count"
    ] = 2

    mutated = (
        json.dumps(
            record,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )

    with pytest.raises(
        ValueError,
        match="fresh count does not match",
    ):
        audit_monthly_sequence_plan_record(
            mutated,
            source_snapshot_id=SNAPSHOT,
            source_snapshot_record_sha256=(
                "2" * 64
            ),
            fresh_target_manifest=(
                fresh_target_manifest_bytes(
                    plan
                )
            ),
        )


def test_sequence_plan_record_refuses_fresh_accession_sha_not_matching_manifest():
    from bacselect.monthly_sequence_plan import (
        audit_monthly_sequence_plan_record,
        fresh_target_manifest_bytes,
        serialize_monthly_sequence_plan_record,
    )

    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    payload = serialize_monthly_sequence_plan_record(
        plan,
        source_snapshot_record_sha256=(
            "3" * 64
        ),
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    record[
        "fresh_acquisition_accessions_sha256"
    ] = "0" * 64

    mutated = (
        json.dumps(
            record,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )

    with pytest.raises(
        ValueError,
        match="fresh accession fingerprint",
    ):
        audit_monthly_sequence_plan_record(
            mutated,
            source_snapshot_id=SNAPSHOT,
            source_snapshot_record_sha256=(
                "3" * 64
            ),
            fresh_target_manifest=(
                fresh_target_manifest_bytes(
                    plan
                )
            ),
        )


def test_sequence_plan_record_refuses_reason_counts_not_matching_manifest():
    from bacselect.monthly_sequence_plan import (
        audit_monthly_sequence_plan_record,
        fresh_target_manifest_bytes,
        serialize_monthly_sequence_plan_record,
    )

    plan = build_monthly_sequence_plan(
        (
            assessment(
                "GCA_000000001.1",
                "SAMN00000001",
            ),
        ),
        (),
        source_snapshot_id=SNAPSHOT,
    )

    payload = serialize_monthly_sequence_plan_record(
        plan,
        source_snapshot_record_sha256=(
            "4" * 64
        ),
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    record[
        "fresh_acquisition_reason_counts"
    ] = {
        "cache_metadata_mismatch":
            1,
    }

    mutated = (
        json.dumps(
            record,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )

    with pytest.raises(
        ValueError,
        match="acquisition-reason counts",
    ):
        audit_monthly_sequence_plan_record(
            mutated,
            source_snapshot_id=SNAPSHOT,
            source_snapshot_record_sha256=(
                "4" * 64
            ),
            fresh_target_manifest=(
                fresh_target_manifest_bytes(
                    plan
                )
            ),
        )
