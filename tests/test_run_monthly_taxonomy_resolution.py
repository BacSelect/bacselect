from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from bacselect import source_taxonomy_execution


ROOT = Path(__file__).resolve().parents[1]

WRAPPER = (
    ROOT
    / "validation/selector-v1/"
      "run_monthly_taxonomy_resolution.py"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


spec = importlib.util.spec_from_file_location(
    "_test_monthly_taxonomy_resolution",
    WRAPPER,
)

assert spec is not None
assert spec.loader is not None

module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def chromosome_payload() -> bytes:
    fields = (
        "canonical_genbank_assembly_accession",
        "source_evidence_sha256",
        "biosample_status",
        "primary_component_count",
        "chromosome_component_count",
        "closure_supported_chromosome_count",
        "closure_unsupported_chromosome_count",
        "chromosome_integrity_triggered",
        "historical_adjudication_reused",
        "chromosome_integrity_status",
        "chromosome_integrity_reason",
    )

    rows = (
        (
            "GCA_000000001.1",
            "a" * 64,
            "CONTINUE",
            "1",
            "1",
            "1",
            "0",
            "0",
            "0",
            "PASS",
            "NO_CHROMOSOME_INTEGRITY_TRIGGER",
        ),
        (
            "GCA_000000002.1",
            "b" * 64,
            "CONTINUE",
            "2",
            "2",
            "1",
            "1",
            "1",
            "0",
            "REVIEW_UNRESOLVED",
            "NOT_HISTORICAL_PROJECT_FINCH_PACKAGE",
        ),
    )

    return (
        "\t".join(fields)
        + "\n"
        + "\n".join(
            "\t".join(row)
            for row in rows
        )
        + "\n"
    ).encode("utf-8")


def stage6_completion(payload: bytes):
    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )

    return {
        "decision_count": 2,
        "continue_count": 2,
        "continue_accessions_sha256":
            (
                source_taxonomy_execution
                .accession_membership_sha256(
                    accessions
                )
            ),
        "pass_count": 1,
        "excluded_count": 0,
        "unresolved_count": 1,
        "decisions_sha256":
            hashlib.sha256(payload).hexdigest(),
    }


def test_stage8_adapter_uses_only_stage6_pass():
    payload = chromosome_payload()

    observed = module.build_stage8_population(
        payload,
        stage6_completion_record=(
            stage6_completion(payload)
        ),
    )

    population = (
        observed.compatibility_population
    )

    assert population.all_accessions == (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )

    assert population.pass_accessions == (
        "GCA_000000001.1",
    )

    assert observed.status_counts == {
        "PASS": 1,
        "REVIEW_UNRESOLVED": 1,
    }


def test_stage8_adapter_rejects_changed_stage6_sha():
    payload = chromosome_payload()

    completion = stage6_completion(payload)
    completion["decisions_sha256"] = "f" * 64

    with pytest.raises(
        module.MonthlyTaxonomyResolutionError,
        match="decisions SHA256",
    ):
        module.build_stage8_population(
            payload,
            stage6_completion_record=completion,
        )


def test_stage8_adapter_rejects_changed_counts():
    payload = chromosome_payload()

    completion = stage6_completion(payload)
    completion["pass_count"] = 2
    completion["unresolved_count"] = 0

    with pytest.raises(
        module.MonthlyTaxonomyResolutionError,
        match="status accounting",
    ):
        module.build_stage8_population(
            payload,
            stage6_completion_record=completion,
        )


def test_synthetic_taxonomy_resolution_uses_frozen_core(
    tmp_path,
):
    nodes = tmp_path / "nodes.dmp"
    merged = tmp_path / "merged.dmp"
    delnodes = tmp_path / "delnodes.dmp"
    raw = tmp_path / "raw.jsonl"

    nodes.write_text(
        "1\t|\t1\t|\tno rank\t|\n"
        "11\t|\t1\t|\tspecies\t|\n",
        encoding="utf-8",
    )

    merged.write_text(
        "99\t|\t11\t|\n",
        encoding="utf-8",
    )

    delnodes.write_text(
        "",
        encoding="utf-8",
    )

    raw.write_text(
        json.dumps(
            {
                "accession":
                    "GCA_000000001.1",
                "organism":
                    {"tax_id": 11},
            }
        )
        + "\n"
        + json.dumps(
            {
                "accession":
                    "GCA_000000002.1",
                "organism":
                    {"tax_id": 99},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )

    population = (
        source_taxonomy_execution
        .Stage3Population(
            all_accessions=accessions,
            pass_accessions=accessions,
            all_membership_sha256=(
                source_taxonomy_execution
                .accession_membership_sha256(
                    accessions
                )
            ),
            pass_membership_sha256=(
                source_taxonomy_execution
                .accession_membership_sha256(
                    accessions
                )
            ),
            status_counts={"PASS": 2},
            reason_counts={
                "NO_CHROMOSOME_INTEGRITY_TRIGGER":
                    2
            },
            decision_artifact_sha256="a" * 64,
        )
    )

    raw_sha = hashlib.sha256(
        raw.read_bytes()
    ).hexdigest()

    source = (
        source_taxonomy_execution
        .load_source_taxids(
            raw,
            expected_sha256=raw_sha,
            expected_record_count=2,
            wanted_accessions=accessions,
        )
    )

    taxonomy = module.source_taxonomy.Taxonomy(
        nodes_path=nodes,
        merged_path=merged,
        delnodes_path=delnodes,
    )

    evaluations = (
        source_taxonomy_execution
        .evaluate_taxonomy_population(
            stage3=population,
            source=source,
            taxonomy=taxonomy,
        )
    )

    build = (
        source_taxonomy_execution
        .build_decision_rows(
            evaluations,
            expected_total=2,
        )
    )

    assert build.status_counts == {
        "PASS": 2
    }

    assert (
        build.resolved_distinct_species_taxid_count
        == 1
    )

    assert {
        row["species_taxid"]
        for row in build.rows
    } == {"11"}


def test_monthly_decision_schema_removes_historical_stage_number():
    evaluation = (
        source_taxonomy_execution
        .Stage4CandidateEvaluation(
            accession="GCA_000000001.1",
            organism_taxid=11,
            decision=(
                module
                .source_taxonomy_execution
                .TaxonomyDecision(
                    status="PASS",
                    reason="TAXONOMY_SPECIES_RESOLVED",
                    normalized_taxid=11,
                    species_taxid=11,
                )
            ),
        )
    )

    build = (
        source_taxonomy_execution
        .build_decision_rows(
            (evaluation,),
            expected_total=1,
        )
    )

    payload = module.serialize_decisions(
        build
    )

    header = payload.decode(
        "utf-8"
    ).splitlines()[0]

    assert "taxonomy_status" in header
    assert "taxonomy_reason" in header
    assert "stage4_status" not in header
    assert "stage4_reason" not in header


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
        "stage6_completion_sha256":
            "1" * 64,
        "taxonomy_snapshot_completion_sha256":
            "2" * 64,
        "input_candidate_count":
            2,
        "input_membership_sha256":
            "3" * 64,
        "decision_count":
            2,
        "pass_count":
            2,
        "unresolved_count":
            0,
        "resolved_distinct_species_taxid_count":
            1,
    }

    record_payload = (
        module._canonical_json(
            record
        )
    )

    decisions = b"x\n"

    first = module.build_completion_receipt(
        record_payload=record_payload,
        decisions_payload=decisions,
    )

    second = module.build_completion_receipt(
        record_payload=record_payload,
        decisions_payload=decisions,
    )

    assert first == second

    module.audit_completion_receipt(
        first,
        record_payload=record_payload,
        decisions_payload=decisions,
    )


def test_frozen_scientific_dependencies_are_exact():
    expected = {
        (
            ROOT
            / "src/bacselect/"
              "source_taxonomy_execution.py"
        ):
            module.SOURCE_TAXONOMY_EXECUTION_SHA256,
        (
            ROOT
            / "src/bacselect/"
              "source_post_sequence_eligibility.py"
        ):
            module.SOURCE_POST_SEQUENCE_SHA256,
        (
            ROOT
            / "src/bacselect/source_taxonomy.py"
        ):
            module.SOURCE_TAXONOMY_SHA256,
        (
            ROOT
            / "src/bacselect/source_eligibility.py"
        ):
            module.SOURCE_ELIGIBILITY_SHA256,
        (
            ROOT
            / "validation/selector-v1/"
              "run_monthly_taxonomy_snapshot_v3.py"
        ):
            module.STAGE7_V3_WRAPPER_SHA256,
        (
            ROOT
            / "tests/"
              "test_run_monthly_taxonomy_snapshot_v3.py"
        ):
            module.STAGE7_V3_TEST_SHA256,
    }

    for path, identity in expected.items():
        assert sha256_file(path) == identity


def test_stage8_does_not_execute_historical_stage4_wrapper():
    tree = ast.parse(
        WRAPPER.read_text(
            encoding="utf-8"
        )
    )

    source = WRAPPER.read_text(
        encoding="utf-8"
    )

    assert (
        "run_taxonomy_resolution_execution.py"
        not in source
    )

    forbidden_calls = {
        "load_stage3_population",
        "execute_to_scratch",
    }

    called = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
        elif isinstance(node.func, ast.Name):
            called.add(node.func.id)

    assert forbidden_calls.isdisjoint(
        called
    )


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
        module.MonthlyTaxonomyResolutionError,
        match="explicit authorization",
    ):
        module.main([])
