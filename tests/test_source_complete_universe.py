from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from bacselect import source_chromosome_integrity
from bacselect import source_complete_universe as module
from bacselect import source_truth
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    BIOSAMPLE_NONREPRESENTATIVE,
    BIOSAMPLE_UNRESOLVED,
    ELIGIBLE,
    EXCLUDED,
    NONREPRESENTATIVE,
    TAXONOMY_PASS,
    TAXONOMY_UNRESOLVED,
    WITHHELD_UNRESOLVED,
    BioSampleDecision,
    TaxonomyDecision,
)


def accession(number: int) -> str:
    return f"GCA_{number:09d}.1"


def chromosome_decision(
    status: str,
    reason: str,
):
    """Construct only the fields consumed by the frozen composition primitive."""

    cls = (
        source_chromosome_integrity
        .ChromosomeIntegrityDecision
    )

    value = object.__new__(
        cls
    )

    object.__setattr__(
        value,
        "status",
        status,
    )

    object.__setattr__(
        value,
        "reason",
        reason,
    )

    return value


def eligible_input(
    number: int,
    *,
    species_taxid: int,
) -> module.CandidateCompositionInput:
    return module.CandidateCompositionInput(
        accession=accession(number),
        source_truth_status=source_truth.SUITABLE,
        source_truth_reason="SOURCE_TRUTH_SUITABLE",
        biosample=BioSampleDecision(
            status=BIOSAMPLE_CONTINUE,
            reason="BIOSAMPLE_SINGLETON",
        ),
        chromosome=chromosome_decision(
            source_chromosome_integrity.PASS,
            "CHROMOSOME_INTEGRITY_PASS",
        ),
        taxonomy=TaxonomyDecision(
            status=TAXONOMY_PASS,
            reason="TAXONOMY_SPECIES_RESOLVED",
            normalized_taxid=species_taxid,
            species_taxid=species_taxid,
        ),
    )


def test_exact_tsv_field_contracts():
    assert module.TERMINAL_COMPOSITION_FIELDS == (
        "canonical_genbank_assembly_accession",
        "final_disposition",
        "terminal_layer",
        "terminal_status",
        "terminal_reason",
        "species_taxid",
    )

    assert module.COMPLETE_UNIVERSE_FIELDS == (
        "canonical_genbank_assembly_accession",
        "species_taxid",
    )


def test_source_truth_exclusion_has_precedence():
    observed = module.compose_terminal_record(
        module.CandidateCompositionInput(
            accession=accession(1),
            source_truth_status=source_truth.EXCLUDE,
            source_truth_reason="SOURCE_TRUTH_BAD",
            biosample=BioSampleDecision(
                status="IMPOSSIBLE_LATER_STATUS",
                reason="MUST_NOT_BE_READ",
            ),
        )
    )

    assert observed.final_disposition == EXCLUDED
    assert observed.terminal_layer == "source_truth"
    assert observed.terminal_status == source_truth.EXCLUDE
    assert observed.terminal_reason == "SOURCE_TRUTH_BAD"
    assert observed.species_taxid is None


def test_source_truth_unresolved_preserves_reason():
    observed = module.compose_terminal_record(
        module.CandidateCompositionInput(
            accession=accession(2),
            source_truth_status=source_truth.UNRESOLVED,
            source_truth_reason="SOURCE_TRUTH_UNRESOLVED_REASON",
        )
    )

    assert (
        observed.final_disposition
        == WITHHELD_UNRESOLVED
    )
    assert observed.terminal_layer == "source_truth"
    assert (
        observed.terminal_reason
        == "SOURCE_TRUTH_UNRESOLVED_REASON"
    )


def test_biosample_nonrepresentative_precedes_later_layers():
    observed = module.compose_terminal_record(
        module.CandidateCompositionInput(
            accession=accession(3),
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="SOURCE_TRUTH_SUITABLE",
            biosample=BioSampleDecision(
                status=BIOSAMPLE_NONREPRESENTATIVE,
                reason=(
                    "BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE"
                ),
            ),
        )
    )

    assert (
        observed.final_disposition
        == NONREPRESENTATIVE
    )
    assert observed.terminal_layer == "repeated_biosample"
    assert observed.species_taxid is None


def test_biosample_unresolved_precedes_later_layers():
    observed = module.compose_terminal_record(
        module.CandidateCompositionInput(
            accession=accession(4),
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="SOURCE_TRUTH_SUITABLE",
            biosample=BioSampleDecision(
                status=BIOSAMPLE_UNRESOLVED,
                reason="BIOSAMPLE_FINGERPRINTS_DIFFER",
            ),
        )
    )

    assert (
        observed.final_disposition
        == WITHHELD_UNRESOLVED
    )
    assert observed.terminal_layer == "repeated_biosample"
    assert (
        observed.terminal_reason
        == "BIOSAMPLE_FINGERPRINTS_DIFFER"
    )


def test_chromosome_exclusion_precedes_taxonomy():
    observed = module.compose_terminal_record(
        module.CandidateCompositionInput(
            accession=accession(5),
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="SOURCE_TRUTH_SUITABLE",
            biosample=BioSampleDecision(
                status=BIOSAMPLE_CONTINUE,
                reason="BIOSAMPLE_SINGLETON",
            ),
            chromosome=chromosome_decision(
                source_chromosome_integrity.EXCLUDE,
                "CHROMOSOME_FRAGMENTED",
            ),
        )
    )

    assert observed.final_disposition == EXCLUDED
    assert (
        observed.terminal_layer
        == "chromosome_integrity"
    )
    assert (
        observed.terminal_reason
        == "CHROMOSOME_FRAGMENTED"
    )
    assert observed.species_taxid is None


def test_chromosome_unresolved_precedes_taxonomy():
    observed = module.compose_terminal_record(
        module.CandidateCompositionInput(
            accession=accession(6),
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="SOURCE_TRUTH_SUITABLE",
            biosample=BioSampleDecision(
                status=BIOSAMPLE_CONTINUE,
                reason="BIOSAMPLE_SINGLETON",
            ),
            chromosome=chromosome_decision(
                source_chromosome_integrity.UNRESOLVED,
                "CHROMOSOME_UNRESOLVED",
            ),
        )
    )

    assert (
        observed.final_disposition
        == WITHHELD_UNRESOLVED
    )
    assert (
        observed.terminal_layer
        == "chromosome_integrity"
    )
    assert (
        observed.terminal_reason
        == "CHROMOSOME_UNRESOLVED"
    )


def test_taxonomy_unresolved_is_terminal():
    observed = module.compose_terminal_record(
        module.CandidateCompositionInput(
            accession=accession(7),
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="SOURCE_TRUTH_SUITABLE",
            biosample=BioSampleDecision(
                status=BIOSAMPLE_CONTINUE,
                reason="BIOSAMPLE_SINGLETON",
            ),
            chromosome=chromosome_decision(
                source_chromosome_integrity.PASS,
                "CHROMOSOME_INTEGRITY_PASS",
            ),
            taxonomy=TaxonomyDecision(
                status=TAXONOMY_UNRESOLVED,
                reason="TAXONOMY_NORMALIZE_DELETED",
                normalized_taxid=None,
                species_taxid=None,
            ),
        )
    )

    assert (
        observed.final_disposition
        == WITHHELD_UNRESOLVED
    )
    assert observed.terminal_layer == "taxonomy"
    assert (
        observed.terminal_reason
        == "TAXONOMY_NORMALIZE_DELETED"
    )


def test_eligible_candidate_preserves_species_taxid():
    observed = module.compose_terminal_record(
        eligible_input(
            8,
            species_taxid=1234,
        )
    )

    assert observed.final_disposition == ELIGIBLE
    assert observed.terminal_layer == "eligible"
    assert observed.terminal_status == "PASS"
    assert (
        observed.terminal_reason
        == "POST_SEQUENCE_ELIGIBLE"
    )
    assert observed.species_taxid == 1234


def test_finalize_terminal_composition_is_sorted():
    observed = module.finalize_terminal_composition(
        [
            eligible_input(
                3,
                species_taxid=30,
            ),
            eligible_input(
                1,
                species_taxid=10,
            ),
            eligible_input(
                2,
                species_taxid=20,
            ),
        ]
    )

    assert [
        item.accession
        for item in observed
    ] == [
        accession(1),
        accession(2),
        accession(3),
    ]


def test_finalize_terminal_composition_rejects_duplicate():
    with pytest.raises(
        module.CompleteUniverseError,
        match="duplicate candidate accession",
    ):
        module.finalize_terminal_composition(
            [
                eligible_input(
                    1,
                    species_taxid=10,
                ),
                eligible_input(
                    1,
                    species_taxid=10,
                ),
            ]
        )


def test_invalid_canonical_accession_rejected():
    evidence = eligible_input(
        1,
        species_taxid=10,
    )

    invalid = module.CandidateCompositionInput(
        accession="GCF_000000001.1",
        source_truth_status=evidence.source_truth_status,
        source_truth_reason=evidence.source_truth_reason,
        biosample=evidence.biosample,
        chromosome=evidence.chromosome,
        taxonomy=evidence.taxonomy,
    )

    with pytest.raises(
        module.CompleteUniverseError,
        match="versioned GCA",
    ):
        module.compose_terminal_record(
            invalid
        )


def test_impossible_disposition_layer_rejected():
    record = module.TerminalCompositionRecord(
        accession=accession(1),
        final_disposition=NONREPRESENTATIVE,
        terminal_layer="taxonomy",
        terminal_status=BIOSAMPLE_NONREPRESENTATIVE,
        terminal_reason="IMPOSSIBLE",
        species_taxid=None,
    )

    with pytest.raises(
        module.CompleteUniverseError,
        match="impossible disposition/terminal-layer",
    ):
        module.validate_terminal_composition(
            [record]
        )


def test_noneligible_species_taxid_rejected():
    record = module.TerminalCompositionRecord(
        accession=accession(1),
        final_disposition=EXCLUDED,
        terminal_layer="source_truth",
        terminal_status=source_truth.EXCLUDE,
        terminal_reason="SOURCE_TRUTH_BAD",
        species_taxid=123,
    )

    with pytest.raises(
        module.CompleteUniverseError,
        match="non-eligible record contains species TaxID",
    ):
        module.validate_terminal_composition(
            [record]
        )


def test_disposition_summary_is_identity_safe_and_exact():
    records = module.finalize_terminal_composition(
        [
            eligible_input(
                1,
                species_taxid=10,
            ),
            module.CandidateCompositionInput(
                accession=accession(2),
                source_truth_status=source_truth.EXCLUDE,
                source_truth_reason="SOURCE_TRUTH_BAD",
            ),
            module.CandidateCompositionInput(
                accession=accession(3),
                source_truth_status=source_truth.UNRESOLVED,
                source_truth_reason="SOURCE_TRUTH_UNKNOWN",
            ),
            module.CandidateCompositionInput(
                accession=accession(4),
                source_truth_status=source_truth.SUITABLE,
                source_truth_reason="SOURCE_TRUTH_SUITABLE",
                biosample=BioSampleDecision(
                    status=BIOSAMPLE_NONREPRESENTATIVE,
                    reason=(
                        "BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE"
                    ),
                ),
            ),
        ]
    )

    summary = module.disposition_summary(
        records
    )

    assert summary.as_dict() == {
        "total": 4,
        "ELIGIBLE": 1,
        "EXCLUDED": 1,
        "WITHHELD_UNRESOLVED": 1,
        "NONREPRESENTATIVE": 1,
    }

    assert "GCA_" not in repr(
        summary.as_dict()
    )


def test_require_expected_accounting_accepts_exact_summary():
    summary = module.DispositionSummary(
        total=68480,
        eligible=67957,
        excluded=154,
        withheld_unresolved=363,
        nonrepresentative=6,
    )

    module.require_expected_accounting(
        summary,
        expected_total=68480,
        expected_eligible=67957,
        expected_excluded=154,
        expected_withheld_unresolved=363,
        expected_nonrepresentative=6,
    )


def test_require_expected_accounting_rejects_mismatch():
    summary = module.DispositionSummary(
        total=4,
        eligible=1,
        excluded=1,
        withheld_unresolved=1,
        nonrepresentative=1,
    )

    with pytest.raises(
        module.CompleteUniverseError,
        match="differs from frozen expectation",
    ):
        module.require_expected_accounting(
            summary,
            expected_total=4,
            expected_eligible=2,
            expected_excluded=1,
            expected_withheld_unresolved=0,
            expected_nonrepresentative=1,
        )


def test_derive_complete_universe_uses_only_eligible():
    records = module.finalize_terminal_composition(
        [
            eligible_input(
                3,
                species_taxid=30,
            ),
            module.CandidateCompositionInput(
                accession=accession(2),
                source_truth_status=source_truth.EXCLUDE,
                source_truth_reason="SOURCE_TRUTH_BAD",
            ),
            eligible_input(
                1,
                species_taxid=10,
            ),
        ]
    )

    observed = module.derive_complete_universe(
        records
    )

    assert observed == (
        module.CompleteUniverseRecord(
            accession=accession(1),
            species_taxid=10,
        ),
        module.CompleteUniverseRecord(
            accession=accession(3),
            species_taxid=30,
        ),
    )


def test_require_complete_universe_checks_count_and_species():
    universe = (
        module.CompleteUniverseRecord(
            accession=accession(2),
            species_taxid=20,
        ),
        module.CompleteUniverseRecord(
            accession=accession(1),
            species_taxid=10,
        ),
        module.CompleteUniverseRecord(
            accession=accession(3),
            species_taxid=20,
        ),
    )

    observed = module.require_complete_universe(
        universe,
        expected_count=3,
        expected_species_count=2,
    )

    assert [
        item.accession
        for item in observed
    ] == [
        accession(1),
        accession(2),
        accession(3),
    ]


def test_membership_sha_is_sorted_newline_delimited_ascii():
    universe = (
        module.CompleteUniverseRecord(
            accession=accession(3),
            species_taxid=30,
        ),
        module.CompleteUniverseRecord(
            accession=accession(1),
            species_taxid=10,
        ),
        module.CompleteUniverseRecord(
            accession=accession(2),
            species_taxid=20,
        ),
    )

    expected_payload = (
        f"{accession(1)}\n"
        f"{accession(2)}\n"
        f"{accession(3)}\n"
    ).encode(
        "ascii"
    )

    expected = hashlib.sha256(
        expected_payload
    ).hexdigest()

    assert (
        module.complete_universe_membership_sha256(
            universe
        )
        == expected
    )


def test_terminal_rows_are_sorted_and_species_blank_for_noneligible():
    records = (
        module.TerminalCompositionRecord(
            accession=accession(2),
            final_disposition=EXCLUDED,
            terminal_layer="source_truth",
            terminal_status=source_truth.EXCLUDE,
            terminal_reason="SOURCE_TRUTH_BAD",
            species_taxid=None,
        ),
        module.TerminalCompositionRecord(
            accession=accession(1),
            final_disposition=ELIGIBLE,
            terminal_layer="eligible",
            terminal_status="PASS",
            terminal_reason="POST_SEQUENCE_ELIGIBLE",
            species_taxid=10,
        ),
    )

    rows = module.terminal_composition_rows(
        records
    )

    assert rows[0][
        "canonical_genbank_assembly_accession"
    ] == accession(1)

    assert rows[0]["species_taxid"] == "10"
    assert rows[1]["species_taxid"] == ""


def test_complete_universe_rows_are_sorted():
    rows = module.complete_universe_rows(
        [
            module.CompleteUniverseRecord(
                accession=accession(2),
                species_taxid=20,
            ),
            module.CompleteUniverseRecord(
                accession=accession(1),
                species_taxid=10,
            ),
        ]
    )

    assert rows == (
        {
            "canonical_genbank_assembly_accession":
                accession(1),
            "species_taxid": "10",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(2),
            "species_taxid": "20",
        },
    )


def test_stage5a_helper_has_no_baseline_or_downstream_imports():
    source = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    imported = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imported.update(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module is not None:
                imported.add(
                    node.module
                )

    prohibited_fragments = (
        "source_membership",
        "structural_feature",
        "coverage",
        "selector",
        "distance",
    )

    for imported_name in imported:
        assert not any(
            fragment in imported_name
            for fragment in prohibited_fragments
        ), imported_name
