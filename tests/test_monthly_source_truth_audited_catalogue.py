from __future__ import annotations

from bacselect import monthly_source_truth as monthly


RELEASE = "2026.09"

SNAPSHOT = (
    "bacselect-source-2026.09-20260901T021652Z"
)

COMMIT = "a" * 40
CATALOGUE_SHA = "b" * 64
ENTRIES_SHA = "c" * 64

ACCESSION = "GCA_000000001.1"
BIOSAMPLE = "SAMN00000001"


def audited_catalogue_record():
    return {
        "release_id":
            RELEASE,
        "source_snapshot_id":
            SNAPSHOT,
        "origin_git_commit":
            COMMIT,
        "entries_sha256":
            ENTRIES_SHA,
        "entries": [
            {
                "canonical_genbank_assembly_accession":
                    ACCESSION,
                "biosample":
                    BIOSAMPLE,
                "origin_sequence_eligibility":
                    monthly.SEQUENCE_ELIGIBLE,
            },
        ],
    }


def test_population_from_audited_catalogue_bypasses_v1_parser(
    monkeypatch,
):
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "cache-v1 byte auditor must not be called"
        )

    monkeypatch.setattr(
        monthly.catalogue_contract,
        "audit_sequence_cache_catalogue",
        forbidden,
    )

    observed = (
        monthly
        .build_monthly_source_truth_population_from_audited_catalogue(
            audited_catalogue_record(),
            catalogue_sha256=(
                CATALOGUE_SHA
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
            release_id=(
                RELEASE
            ),
            source_snapshot_id=(
                SNAPSHOT
            ),
            origin_git_commit=(
                COMMIT
            ),
        )
    )

    assert observed.release_id == RELEASE
    assert observed.source_snapshot_id == SNAPSHOT
    assert observed.origin_git_commit == COMMIT

    assert (
        observed.sequence_cache_catalogue_sha256
        == CATALOGUE_SHA
    )

    assert (
        observed.sequence_cache_entries_sha256
        == ENTRIES_SHA
    )

    assert observed.retained_accessions == (
        ACCESSION,
    )

    assert (
        observed.sequence_eligible_accessions
        == (
            ACCESSION,
        )
    )

    assert (
        observed.sequence_ineligible_accessions
        == ()
    )


def test_record_auditor_from_audited_catalogue_bypasses_v1_parser(
    monkeypatch,
):
    record = audited_catalogue_record()

    sentinel_population = object()
    seen = {}

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "cache-v1 population path must not be called"
        )

    monkeypatch.setattr(
        monthly,
        "build_monthly_source_truth_population",
        forbidden,
    )

    def fake_population(
        catalogue_record,
        **kwargs,
    ):
        seen["catalogue_record"] = (
            catalogue_record
        )
        seen["population_kwargs"] = (
            kwargs
        )
        return sentinel_population

    monkeypatch.setattr(
        monthly,
        (
            "build_monthly_source_truth_population_"
            "from_audited_catalogue"
        ),
        fake_population,
    )

    monkeypatch.setattr(
        monthly,
        "audit_monthly_source_truth_decisions",
        lambda payload:
            (),
    )

    monkeypatch.setattr(
        monthly,
        "audit_monthly_source_truth_relations",
        lambda payload:
            (),
    )

    expected = {
        "decision_count":
            0,
        "retained_count":
            0,
        "schema_version":
            monthly.MONTHLY_SOURCE_TRUTH_RECORD_SCHEMA,
        "sequence_eligible_count":
            0,
        "sequence_ineligible_count":
            0,
        "status":
            monthly.MONTHLY_SOURCE_TRUTH_STATUS,
    }

    def fake_record_from_rows(
        population,
        **kwargs,
    ):
        assert population is sentinel_population
        seen["record_kwargs"] = kwargs
        return expected

    monkeypatch.setattr(
        monthly,
        "_record_from_rows",
        fake_record_from_rows,
    )

    payload = monthly._canonical_json_bytes(
        expected
    )

    observed = (
        monthly
        .audit_monthly_source_truth_record_from_audited_catalogue(
            payload,
            catalogue_record=(
                record
            ),
            catalogue_sha256=(
                CATALOGUE_SHA
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
            release_id=(
                RELEASE
            ),
            source_snapshot_id=(
                SNAPSHOT
            ),
            origin_git_commit=(
                COMMIT
            ),
            metadata_record_sha256=(
                "d" * 64
            ),
            metadata_completion_sha256=(
                "e" * 64
            ),
            decisions_payload=b"",
            relations_payload=b"",
        )
    )

    assert observed == expected

    assert (
        seen["catalogue_record"]
        is record
    )

    assert (
        seen[
            "population_kwargs"
        ][
            "catalogue_sha256"
        ]
        == CATALOGUE_SHA
    )
