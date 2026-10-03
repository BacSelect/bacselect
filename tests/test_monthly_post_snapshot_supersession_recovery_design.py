import json
from pathlib import Path


METHOD = Path(
    "validation/selector-v1/"
    "prospective-monthly-post-snapshot-"
    "supersession-recovery.md"
)

METHOD_JSON = Path(
    "validation/selector-v1/"
    "prospective-monthly-post-snapshot-"
    "supersession-recovery.json"
)


def load_payload():
    return json.loads(
        METHOD_JSON.read_text(
            encoding="utf-8"
        )
    )


def test_design_is_explicitly_prospective_for_recovery():
    text = METHOD.read_text(
        encoding="utf-8"
    )

    payload = load_payload()

    assert (
        "**Prospective recovery correction.**"
        in text
    )

    assert (
        payload["failure_class_already_observed"]
        is True
    )

    assert (
        payload["real_recovery_execution"]
        is False
    )

    assert (
        payload["selector_outcome_generated"]
        is False
    )


def test_trigger_requires_snapshot_current_then_acquisition_previous():
    payload = load_payload()

    trigger = payload[
        "trigger"
    ]

    assert (
        trigger[
            "frozen_snapshot_assembly_status"
        ]
        == "current"
    )

    assert (
        trigger[
            "frozen_snapshot_current_accession_equals_target"
        ]
        is True
    )

    assert (
        trigger[
            "acquisition_assembly_status"
        ]
        == "previous"
    )

    assert (
        trigger[
            "acquisition_current_accession_differs_from_target"
        ]
        is True
    )

    assert (
        trigger[
            "frozen_snapshot_assembly_level"
        ]
        == "Complete Genome"
    )

    assert (
        trigger[
            "acquisition_assembly_level"
        ]
        == "Complete Genome"
    )


def test_frozen_accession_is_never_substituted():
    text = METHOD.read_text(
        encoding="utf-8"
    ).lower()

    payload = load_payload()

    assert (
        payload[
            "successor_substitution_permitted"
        ]
        is False
    )

    assert (
        payload[
            "paired_refseq_substitution_permitted"
        ]
        is False
    )

    assert (
        "the successor accession is recorded "
        "but is never substituted"
        in text
    )


def test_source_and_target_identity_remain_frozen():
    payload = load_payload()

    assert (
        payload[
            "source_execution_modified"
        ]
        is False
    )

    assert (
        payload[
            "source_partial_modified"
        ]
        is False
    )

    assert (
        payload[
            "target_set_changed"
        ]
        is False
    )

    assert (
        payload[
            "fresh_target_manifest_changed"
        ]
        is False
    )

    assert (
        payload[
            "source_snapshot_changed"
        ]
        is False
    )


def test_recovery_reuses_generic_authority_without_changing_summary_schema():
    text = METHOD.read_text(
        encoding="utf-8"
    )

    payload = load_payload()

    assert (
        payload[
            "recovery_authority_reused"
        ]
        is True
    )

    assert (
        payload[
            "recovery_authority_source_class"
        ]
        == "fresh-recovery"
    )

    assert (
        payload[
            "cause_specific_evidence_separate_from_authority_summary"
        ]
        is True
    )

    assert (
        "generic `recovery-summary.json` remains "
        "the exact cause-agnostic schema"
        in text
    )


def test_supersession_is_not_sequence_ineligibility():
    payload = load_payload()

    assert (
        payload[
            "classification_is_sequence_ineligibility"
        ]
        is False
    )

    assert (
        "sequence_ineligibility_classification"
        in payload[
            "explicitly_prohibited"
        ]
    )


def test_design_contains_no_incident_specific_identifiers():
    text = (
        METHOD.read_text(
            encoding="utf-8"
        )
        + "\n"
        + METHOD_JSON.read_text(
            encoding="utf-8"
        )
    )

    for token in (
        "GCA_",
        "GCF_",
        "SAMN",
        "batch-00118",
        "batch-00130",
        "055419085",
        "059637575",
        "059640795",
    ):
        assert token not in text
