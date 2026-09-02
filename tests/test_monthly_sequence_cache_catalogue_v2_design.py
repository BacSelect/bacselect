from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

DESIGN_JSON = (
    ROOT
    / "validation"
    / "selector-v1"
    / "prospective-monthly-sequence-cache-catalogue-v2.json"
)

DESIGN_MD = (
    ROOT
    / "validation"
    / "selector-v1"
    / "prospective-monthly-sequence-cache-catalogue-v2.md"
)


def load():
    return json.loads(
        DESIGN_JSON.read_text(
            encoding="utf-8"
        )
    )


def test_design_identity():
    value = load()

    assert value["schema_version"] == (
        "bacselect-prospective-monthly-"
        "sequence-cache-catalogue-v2-design-v1"
    )

    assert value["status"] == (
        "PROSPECTIVE_FROZEN_DESIGN"
    )


def test_v1_is_explicitly_immutable():
    value = load()

    assert (
        value["boundaries"][
            "cache_v1_must_not_be_modified"
        ]
        is True
    )

    assert value["implementation"][
        "v1_core_must_remain_unchanged"
    ].endswith(
        "monthly_sequence_cache_catalogue.py"
    )

    assert value["implementation"][
        "planned_v2_core"
    ].endswith(
        "monthly_sequence_cache_catalogue_v2.py"
    )


def test_completion_v2_is_the_only_current_completion_contract():
    value = load()

    contract = value[
        "catalogue_contract"
    ]

    assert contract[
        "completion_schema"
    ] == (
        "bacselect-monthly-sequence-"
        "acquisition-completion-v2"
    )

    assert contract[
        "completion_artifact_name"
    ] == (
        "sequence-acquisition-completion-v2.json"
    )


def test_authority_is_independently_resolved():
    value = load()

    authority = value[
        "authority"
    ]

    assert authority[
        "cache_wrapper_must_resolve_authority_independently"
    ] is True

    assert authority[
        "completion_is_required_evidence_but_not_provider_authority"
    ] is True

    assert authority[
        "resolver"
    ] == (
        "resolve_authoritative_sequence_batches"
    )

    assert authority[
        "fresh_provider"
    ] == (
        "audit_completed_transport_provider"
    )

    assert authority[
        "recovery_provider"
    ] == (
        "audit_authoritative_recovery_provider"
    )


def test_commit_identities_are_separate():
    value = load()

    assert value[
        "catalogue_contract"
    ][
        "commit_identities"
    ] == [
        "source_production_commit",
        "completion_execution_commit",
        "cache_execution_commit",
    ]


def test_normalized_evidence_fields_are_exact():
    value = load()

    assert value[
        "normalized_current_batch_evidence"
    ][
        "fields"
    ] == [
        "batch_id",
        "source_class",
        "recovery_class",
        "provider_summary_name",
        "provider_summary_payload",
        "candidate_audit_payload",
        "component_audit_payload",
        "package_manifest_name",
        "package_manifest_payload",
        "source_partial_name",
        "recovery_commit",
        "source_batch_sha256",
        "source_package_sha256",
        "recovery_package_sha256",
        "recovery_summary_sha256",
        "cause_evidence_sha256",
        "transport_record_sha256",
    ]

    assert value[
        "normalized_current_batch_evidence"
    ][
        "must_not_contain_absolute_paths"
    ] is True


def test_provider_names_and_path_classes_are_not_conflated():
    value = load()

    providers = value[
        "provider_contracts"
    ]

    assert providers[
        "fresh"
    ][
        "provider_summary_name"
    ] == "batch-summary.json"

    assert providers[
        "fresh"
    ][
        "package_manifest_name"
    ] == "package-files.tsv"

    assert providers[
        "fresh-recovery"
    ][
        "provider_summary_name"
    ] == "recovery-summary.json"

    assert providers[
        "fresh-recovery"
    ][
        "package_manifest_name"
    ] == "recovery-package-files.tsv"

    paths = value[
        "logical_paths"
    ]

    assert paths[
        "fresh_provider_prefix"
    ].startswith(
        "sequence-acquisition/"
    )

    assert paths[
        "recovery_provider_prefix"
    ].startswith(
        "sequence-acquisition-recovery/"
    )

    assert paths[
        "must_not_project_recovery_into_sequence_acquisition"
    ] is True


def test_shared_manifest_schema_is_frozen():
    value = load()

    contract = value[
        "manifest_contract"
    ]

    assert contract[
        "normalized_fields"
    ] == [
        "path",
        "size_bytes",
        "sha256",
    ]

    assert contract[
        "scientific_candidate_audit_schema_is_shared"
    ] is True

    assert contract[
        "scientific_component_audit_schema_is_shared"
    ] is True

    assert contract[
        "scientific_package_manifest_row_schema_is_shared"
    ] is True


def test_recovery_identity_survives_batch_provenance():
    value = load()

    provenance = value[
        "batch_provenance_v2"
    ]

    fields = set(
        provenance[
            "common_fields"
        ]
    )

    for field in (
        "source_class",
        "recovery_class",
        "recovery_commit",
        "source_batch_sha256",
        "source_package_sha256",
        "recovery_package_sha256",
        "recovery_summary_sha256",
        "cause_evidence_sha256",
        "transport_record_sha256",
    ):
        assert field in fields

    assert provenance[
        "recovery_class_must_survive_into_catalogue"
    ] is True


def test_historical_v1_chain_is_preserved_not_migrated():
    value = load()

    chain = value[
        "historical_chain"
    ]

    assert chain[
        "accepted_previous_catalogue_schemas"
    ] == [
        "bacselect-monthly-sequence-cache-catalogue-v1",
        "bacselect-monthly-sequence-cache-catalogue-v2",
    ]

    assert chain[
        "v1_previous_catalogue_must_be_audited_by_frozen_v1_auditor"
    ] is True

    assert chain[
        "carried_v1_entries_must_preserve_original_entry_sha256"
    ] is True

    assert chain[
        "carried_v1_batch_provenance_must_preserve_original_batch_provenance_sha256"
    ] is True

    assert chain[
        "no_historical_rehash_or_migration"
    ] is True


def test_population_accounting_remains_bound_to_completion():
    value = load()

    assert value[
        "catalogue_contract"
    ][
        "must_bind_current_population_to_completion_fresh_acquisition_count"
    ] is True

    assert value[
        "catalogue_v2"
    ][
        "must_preserve_current_new_replaced_carried_accounting"
    ] is True


def test_fail_closed_policy_covers_authority_and_provenance():
    value = load()

    policy = value[
        "failure_policy"
    ]

    for key in (
        "ordinary_and_recovery_provider_for_same_batch",
        "missing_provider",
        "unexpected_partial",
        "completion_provider_mismatch",
        "source_class_mismatch",
        "recovery_class_mismatch",
        "provider_summary_mismatch",
        "candidate_audit_mismatch",
        "component_audit_mismatch",
        "package_manifest_mismatch",
        "package_readback_mismatch",
        "historical_chain_ambiguity",
    ):
        assert policy[
            key
        ] == "FAIL"


def test_design_has_no_incident_specific_logic():
    json_text = DESIGN_JSON.read_text(
        encoding="utf-8"
    )

    md_text = DESIGN_MD.read_text(
        encoding="utf-8"
    )

    combined = (
        json_text
        + "\n"
        + md_text
    )

    for token in (
        "batch-00072",
        "batch-00118",
        "batch-00130",
        "GCA_030436345.2",
        "GCA_055419085.2",
        "GCA_059637575.1",
    ):
        assert token not in combined


def test_design_freeze_forbids_execution_and_network():
    value = load()

    boundaries = value[
        "boundaries"
    ]

    assert boundaries[
        "no_network"
    ] is True

    assert boundaries[
        "no_real_recovery"
    ] is True

    assert boundaries[
        "no_cache_publication_during_design_freeze"
    ] is True

    assert boundaries[
        "source_partial_must_not_be_modified"
    ] is True

    assert boundaries[
        "ordinary_final_must_not_be_modified"
    ] is True
