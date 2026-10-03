from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from bacselect import source_complete_universe


ROOT = Path(__file__).resolve().parents[1]

WRAPPER = (
    ROOT
    / "validation/selector-v1/"
      "run_monthly_complete_universe.py"
)

spec = importlib.util.spec_from_file_location(
    "_test_monthly_complete_universe",
    WRAPPER,
)

assert spec is not None
assert spec.loader is not None

module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def stage8_decisions() -> bytes:
    return (
        "canonical_genbank_assembly_accession\t"
        "organism_taxid\t"
        "normalized_organism_taxid\t"
        "species_taxid\t"
        "taxonomy_status\t"
        "taxonomy_reason\n"
        "GCA_000000001.1\t11\t11\t10\tPASS\t"
        "TAXONOMY_SPECIES_RESOLVED\n"
        "GCA_000000002.1\t22\t\t\tREVIEW_UNRESOLVED\t"
        "TAXONOMY_NORMALIZE_DELETED\n"
        "GCA_000000003.1\t33\t33\t30\tPASS\t"
        "TAXONOMY_SPECIES_RESOLVED\n"
    ).encode("utf-8")


def authenticated_stage8():
    decisions = stage8_decisions()

    completion = {
        "decision_count": 3,
        "pass_count": 2,
        "unresolved_count": 1,
        "resolved_distinct_species_taxid_count": 2,
    }

    record = {
        "release_id": "2026.09",
        "source_snapshot_id": "source",
        "taxonomy_snapshot_id": "taxonomy",
    }

    return module.AuthenticatedStage8(
        upstream=object(),
        decisions_payload=decisions,
        record_payload=b"{}\n",
        completion_payload=b"{}\n",
        record=record,
        completion=completion,
        decisions_sha256=hashlib.sha256(
            decisions
        ).hexdigest(),
        record_sha256="1" * 64,
        completion_sha256="2" * 64,
        identity=("x",),
    )


def expected_universe():
    return (
        source_complete_universe
        .CompleteUniverseRecord(
            accession="GCA_000000001.1",
            species_taxid=10,
        ),
        source_complete_universe
        .CompleteUniverseRecord(
            accession="GCA_000000003.1",
            species_taxid=30,
        ),
    )


def test_mapping_sha_is_sorted_headerless_mapping():
    universe = expected_universe()

    expected = hashlib.sha256(
        (
            "GCA_000000001.1\t10\n"
            "GCA_000000003.1\t30\n"
        ).encode("ascii")
    ).hexdigest()

    assert (
        module.accession_species_mapping_sha256(
            universe
        )
        == expected
    )


def test_stage9_uses_only_stage8_pass_rows():
    authenticated = authenticated_stage8()

    universe = expected_universe()

    membership = (
        source_complete_universe
        .complete_universe_membership_sha256(
            universe
        )
    )

    mapping = (
        module.accession_species_mapping_sha256(
            universe
        )
    )

    observed = module.build_monthly_universe(
        authenticated,
        expected_membership_sha256=membership,
        expected_mapping_sha256=mapping,
    )

    assert observed.universe == universe
    assert observed.universe_count == 2
    assert observed.species_count == 2

    assert observed.stage8_status_counts == {
        "PASS": 2,
        "REVIEW_UNRESOLVED": 1,
    }


def test_stage9_rejects_wrong_membership_identity():
    authenticated = authenticated_stage8()

    universe = expected_universe()

    mapping = (
        module.accession_species_mapping_sha256(
            universe
        )
    )

    with pytest.raises(
        module.MonthlyCompleteUniverseError,
        match="membership differs",
    ):
        module.build_monthly_universe(
            authenticated,
            expected_membership_sha256="f" * 64,
            expected_mapping_sha256=mapping,
        )


def test_stage9_rejects_wrong_mapping_identity():
    authenticated = authenticated_stage8()

    universe = expected_universe()

    membership = (
        source_complete_universe
        .complete_universe_membership_sha256(
            universe
        )
    )

    with pytest.raises(
        module.MonthlyCompleteUniverseError,
        match="mapping differs",
    ):
        module.build_monthly_universe(
            authenticated,
            expected_membership_sha256=membership,
            expected_mapping_sha256="f" * 64,
        )


def test_stage9_rejects_species_on_unresolved_row():
    authenticated = authenticated_stage8()

    changed = (
        authenticated.decisions_payload
        .replace(
            b"\t22\t\t\tREVIEW_UNRESOLVED\t",
            b"\t22\t\t22\tREVIEW_UNRESOLVED\t",
        )
    )

    broken = module.AuthenticatedStage8(
        upstream=authenticated.upstream,
        decisions_payload=changed,
        record_payload=authenticated.record_payload,
        completion_payload=authenticated.completion_payload,
        record=authenticated.record,
        completion=authenticated.completion,
        decisions_sha256=hashlib.sha256(
            changed
        ).hexdigest(),
        record_sha256=authenticated.record_sha256,
        completion_sha256=authenticated.completion_sha256,
        identity=authenticated.identity,
    )

    universe = expected_universe()

    with pytest.raises(
        module.MonthlyCompleteUniverseError,
        match="unresolved row contains species",
    ):
        module.build_monthly_universe(
            broken,
            expected_membership_sha256=(
                source_complete_universe
                .complete_universe_membership_sha256(
                    universe
                )
            ),
            expected_mapping_sha256=(
                module.accession_species_mapping_sha256(
                    universe
                )
            ),
        )


def test_universe_serialization_is_canonical():
    authenticated = authenticated_stage8()

    universe = expected_universe()

    build = module.build_monthly_universe(
        authenticated,
        expected_membership_sha256=(
            source_complete_universe
            .complete_universe_membership_sha256(
                universe
            )
        ),
        expected_mapping_sha256=(
            module.accession_species_mapping_sha256(
                universe
            )
        ),
    )

    payload = module.serialize_universe(
        build
    )

    assert payload == (
        b"canonical_genbank_assembly_accession\tspecies_taxid\n"
        b"GCA_000000001.1\t10\n"
        b"GCA_000000003.1\t30\n"
    )


def test_completion_is_deterministic():
    record = {
        "schema_version":
            module.RECORD_SCHEMA,
        "status":
            module.RECORD_STATUS,
        "release_id":
            "2026.09",
        "source_snapshot_id":
            "source",
        "source_production_commit":
            "a" * 40,
        "taxonomy_snapshot_id":
            "taxonomy",
        "taxonomy_execution_commit":
            "b" * 40,
        "taxonomy_resolution_execution_commit":
            "c" * 40,
        "complete_universe_execution_commit":
            "d" * 40,
        "taxonomy_resolution_completion_sha256":
            "1" * 64,
        "complete_universe_count":
            2,
        "complete_universe_species_count":
            2,
        "complete_universe_membership_sha256":
            "2" * 64,
        "accession_species_mapping_sha256":
            "3" * 64,
    }

    record_payload = module._canonical_json(
        record
    )

    universe_payload = b"x\n"

    first = module.build_completion_receipt(
        record_payload=record_payload,
        universe_payload=universe_payload,
    )

    second = module.build_completion_receipt(
        record_payload=record_payload,
        universe_payload=universe_payload,
    )

    assert first == second

    module.audit_completion_receipt(
        first,
        record_payload=record_payload,
        universe_payload=universe_payload,
    )


def test_frozen_complete_universe_primitive_identity():
    primitive = (
        ROOT
        / "src/bacselect/source_complete_universe.py"
    )

    test = (
        ROOT
        / "tests/test_source_complete_universe.py"
    )

    assert hashlib.sha256(
        primitive.read_bytes()
    ).hexdigest() == (
        module.COMPLETE_UNIVERSE_PRIMITIVE_SHA256
    )

    assert hashlib.sha256(
        test.read_bytes()
    ).hexdigest() == (
        module.COMPLETE_UNIVERSE_TEST_SHA256
    )


def test_stage9_has_no_baseline_holdout_or_terminal_reconstruction():
    source = WRAPPER.read_text(
        encoding="utf-8"
    )

    assert "run_complete_universe_execution.py" not in source
    assert "derive_complete_universe(" not in source
    assert "finalize_terminal_composition(" not in source
    assert "source_holdout" not in source


def test_main_requires_explicit_real_execution_authorization(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda argv=None:
            SimpleNamespace(
                authorize_real_execution=False
            ),
    )

    with pytest.raises(
        module.MonthlyCompleteUniverseError,
        match="explicit authorization",
    ):
        module.main([])
