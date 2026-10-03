import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

METHOD = (
    ROOT
    / "validation/selector-v1/"
    "prospective-monthly-missing-datasets-gbff-recovery.md"
)

CHECKPOINT = (
    ROOT
    / "validation/selector-v1/"
    "prospective-monthly-missing-datasets-gbff-recovery.json"
)

SOURCE_COMMIT = (
    "abefc3b70d7fe7e079eeb52b762542dae565edf6"
)


def load_checkpoint():
    return json.loads(
        CHECKPOINT.read_text(
            encoding="utf-8",
        )
    )


def test_recovery_checkpoint_is_prospective_and_source_preserving():
    payload = load_checkpoint()

    assert payload["schema_version"] == 1
    assert (
        payload["status"]
        == "PROSPECTIVE_RECOVERY_CORRECTION_SELECTOR_OUTCOME_BLOCKED"
    )
    assert payload["source_production_commit"] == SOURCE_COMMIT

    assert payload["trigger_identity_independent"] is True

    assert payload["source_execution_modified"] is False
    assert payload["source_partial_preserved"] is True
    assert (
        payload["recovery_root_separate_from_sequence_acquisition"]
        is True
    )

    assert payload["target_set_changed"] is False
    assert payload["ordinary_monthly_stage3a_modified"] is False

    assert payload["selector_outcome_generated"] is False
    assert payload["real_recovery_efetch_executed"] is False


def test_recovery_transport_is_explicit_and_scientifically_bounded():
    payload = load_checkpoint()

    assert (
        payload["failure_class"]
        == "datasets_manifest_omits_requested_gbff"
    )

    assert (
        payload["recovery_transport"]
        == "ncbi_efetch_nuccore_component_gbff"
    )

    assert (
        payload["recovery_component_source"]
        == "preserved_sequence_report_genbank_accessions"
    )

    assert payload["recovery_requires_genomic_fasta"] is True
    assert payload["recovery_requires_sequence_report"] is True
    assert payload["recovery_requires_zero_datasets_gbff"] is True
    assert (
        payload["recovery_requires_missing_fetch_gbff_entry"]
        is True
    )

    assert payload["recovery_verifies_component_set"] is True
    assert payload["recovery_verifies_component_lengths"] is True
    assert (
        payload["recovery_verifies_fasta_gbff_sequence_identity"]
        is True
    )

    assert payload["recovery_retains_explicit_efetch_identity"] is True


def test_recovery_authority_is_preserved_downstream():
    payload = load_checkpoint()

    assert (
        payload["completion_requires_recovery_aware_resolution"]
        is True
    )

    assert payload["cache_catalogue_requires_same_resolution"] is True

    assert payload["downstream_source_class"] == "fresh-recovery"


def test_method_contains_no_accession_specific_exception():
    text = METHOD.read_text(
        encoding="utf-8",
    )

    for token in (
        "GCA_0",
        "GCF_0",
        "SAMN",
        "SAMEA",
        "SAMD",
    ):
        assert token not in text

    assert "No accession-specific exception is permitted." in text
    assert "The trigger is defined by evidence state" in text


def test_recovery_does_not_encode_selector_outcomes():
    combined = (
        METHOD.read_text(
            encoding="utf-8",
        )
        + CHECKPOINT.read_text(
            encoding="utf-8",
        )
    ).lower()

    forbidden = (
        "selector_distance",
        "panel_identity",
        "ops_fingerprint",
        "sr_fingerprint",
    )

    for token in forbidden:
        assert token not in combined


def test_recovered_evidence_is_not_disguised_as_datasets_gbff():
    text = METHOD.read_text(
        encoding="utf-8",
    )

    assert "<GCA>_efetch_components.gbff" in text
    assert "<GCA>_efetch_components.json" in text
    assert "They must never be renamed to `genomic.gbff`." in text
