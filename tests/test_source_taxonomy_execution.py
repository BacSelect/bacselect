from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import pytest

from bacselect import source_chromosome_integrity
from bacselect.source_post_sequence_eligibility import (
    TAXONOMY_PASS,
    TAXONOMY_UNRESOLVED,
    TaxonomyDecision,
)
from bacselect.source_taxonomy import Taxonomy
import bacselect.source_taxonomy_execution as module
from bacselect.source_taxonomy_execution import (
    STAGE3_DECISION_FIELDS,
    Stage3Population,
    Stage4CandidateEvaluation,
    Stage4ExecutionError,
    SourceTaxidBundle,
    build_decision_rows,
    evaluate_taxonomy_population,
    load_source_taxids,
    load_stage3_population,
)


def sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def stage3_row(
    accession: str,
    *,
    status: str = source_chromosome_integrity.PASS,
    reason: str = "NO_CHROMOSOME_INTEGRITY_TRIGGER",
) -> dict[str, str]:
    return {
        "canonical_genbank_assembly_accession":
            accession,
        "source_evidence_sha256":
            "a" * 64,
        "stage2_status":
            "CONTINUE",
        "chromosome_component_count":
            "1",
        "closure_supported_chromosome_count":
            "1",
        "closure_unsupported_chromosome_count":
            "0",
        "chromosome_integrity_triggered":
            "0",
        "historical_adjudication_reused":
            "0",
        "stage3_status":
            status,
        "stage3_reason":
            reason,
    }


def write_stage3(
    path: Path,
    rows,
) -> str:
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=STAGE3_DECISION_FIELDS,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(
            rows
        )

    return sha256_file(
        path
    )


def expected_counts(
    rows,
):
    return (
        dict(
            sorted(
                Counter(
                    row["stage3_status"]
                    for row in rows
                ).items()
            )
        ),
        dict(
            sorted(
                Counter(
                    row["stage3_reason"]
                    for row in rows
                ).items()
            )
        ),
    )


def load_synthetic_stage3(
    path: Path,
    rows,
):
    digest = write_stage3(
        path,
        rows,
    )

    status_counts, reason_counts = expected_counts(
        rows
    )

    pass_count = sum(
        row["stage3_status"]
        == source_chromosome_integrity.PASS
        for row in rows
    )

    return load_stage3_population(
        path,
        expected_sha256=digest,
        expected_total=len(
            rows
        ),
        expected_pass=pass_count,
        expected_status_counts=status_counts,
        expected_reason_counts=reason_counts,
    )


def write_raw(
    path: Path,
    records,
) -> str:
    path.write_text(
        "".join(
            json.dumps(
                record,
                sort_keys=True,
            )
            + "\n"
            for record in records
        ),
        encoding="utf-8",
    )

    return sha256_file(
        path
    )


def raw_record(
    accession: str,
    taxid=12,
):
    return {
        "accession":
            accession,
        "organism": {
            "organism_name":
                "Synthetic organism",
            "tax_id":
                taxid,
        },
        "checkmInfo": {
            "checkmSpeciesTaxId":
                999999,
        },
    }


def write_taxonomy(
    root: Path,
    *,
    nodes: str,
    merged: str = "",
    deleted: str = "",
) -> Taxonomy:
    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    nodes_path = root / "nodes.dmp"
    merged_path = root / "merged.dmp"
    delnodes_path = root / "delnodes.dmp"

    nodes_path.write_text(
        nodes,
        encoding="utf-8",
    )

    merged_path.write_text(
        merged,
        encoding="utf-8",
    )

    delnodes_path.write_text(
        deleted,
        encoding="utf-8",
    )

    return Taxonomy(
        nodes_path=nodes_path,
        merged_path=merged_path,
        delnodes_path=delnodes_path,
    )


def base_nodes():
    return (
        "1\t|\t1\t|\tno rank\t|\n"
        "2\t|\t1\t|\tsuperkingdom\t|\n"
        "10\t|\t2\t|\tgenus\t|\n"
        "11\t|\t10\t|\tspecies\t|\n"
        "12\t|\t11\t|\tstrain\t|\n"
        "13\t|\t11\t|\tsubspecies\t|\n"
    )


def synthetic_population(
    *accessions: str,
) -> Stage3Population:
    ordered = tuple(
        sorted(
            accessions
        )
    )

    return Stage3Population(
        all_accessions=ordered,
        pass_accessions=ordered,
        all_membership_sha256=(
            module.accession_membership_sha256(
                ordered
            )
        ),
        pass_membership_sha256=(
            module.accession_membership_sha256(
                ordered
            )
        ),
        status_counts={
            source_chromosome_integrity.PASS:
                len(
                    ordered
                ),
        },
        reason_counts={
            "NO_CHROMOSOME_INTEGRITY_TRIGGER":
                len(
                    ordered
                ),
        },
        decision_artifact_sha256="a" * 64,
    )


def synthetic_source(
    values,
) -> SourceTaxidBundle:
    ordered = dict(
        sorted(
            values.items()
        )
    )

    return SourceTaxidBundle(
        taxid_by_accession=ordered,
        source_record_count=len(
            ordered
        ),
        source_sha256="b" * 64,
        unique_selected_taxid_count=len(
            set(
                ordered.values()
            )
        ),
    )


def test_stage3_pass_filtering_and_terminal_short_circuit(
    tmp_path,
):
    rows = [
        stage3_row(
            "GCA_000000001.1"
        ),
        stage3_row(
            "GCA_000000002.1",
            status=(
                source_chromosome_integrity.EXCLUDE
            ),
            reason=(
                "HISTORICAL_FRAGMENTED_CHROMOSOME_SET"
            ),
        ),
        stage3_row(
            "GCA_000000003.1",
            status=(
                source_chromosome_integrity.UNRESOLVED
            ),
            reason="HISTORICAL_UNRESOLVED",
        ),
        stage3_row(
            "GCA_000000004.1"
        ),
    ]

    observed = load_synthetic_stage3(
        tmp_path / "stage3.tsv",
        rows,
    )

    assert observed.all_accessions == (
        "GCA_000000001.1",
        "GCA_000000002.1",
        "GCA_000000003.1",
        "GCA_000000004.1",
    )

    assert observed.pass_accessions == (
        "GCA_000000001.1",
        "GCA_000000004.1",
    )


def test_stage3_duplicate_accession_rejected(
    tmp_path,
):
    rows = [
        stage3_row(
            "GCA_000000001.1"
        ),
        stage3_row(
            "GCA_000000001.1"
        ),
    ]

    path = tmp_path / "stage3.tsv"
    digest = write_stage3(
        path,
        rows,
    )

    status_counts, reason_counts = expected_counts(
        rows
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="duplicate accession",
    ):
        load_stage3_population(
            path,
            expected_sha256=digest,
            expected_total=2,
            expected_pass=2,
            expected_status_counts=status_counts,
            expected_reason_counts=reason_counts,
        )


def test_unknown_stage3_status_rejected(
    tmp_path,
):
    rows = [
        stage3_row(
            "GCA_000000001.1",
            status="UNKNOWN",
            reason="SYNTHETIC",
        )
    ]

    path = tmp_path / "stage3.tsv"
    digest = write_stage3(
        path,
        rows,
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="unexpected Stage 3 status",
    ):
        load_stage3_population(
            path,
            expected_sha256=digest,
            expected_total=1,
            expected_pass=1,
            expected_status_counts={
                "UNKNOWN": 1,
            },
            expected_reason_counts={
                "SYNTHETIC": 1,
            },
        )


def test_stage3_exact_aggregate_accounting_required(
    tmp_path,
):
    rows = [
        stage3_row(
            "GCA_000000001.1"
        ),
        stage3_row(
            "GCA_000000002.1"
        ),
    ]

    path = tmp_path / "stage3.tsv"
    digest = write_stage3(
        path,
        rows,
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="status accounting",
    ):
        load_stage3_population(
            path,
            expected_sha256=digest,
            expected_total=2,
            expected_pass=2,
            expected_status_counts={
                source_chromosome_integrity.PASS:
                    1,
            },
            expected_reason_counts={
                "NO_CHROMOSOME_INTEGRITY_TRIGGER":
                    2,
            },
        )


def test_stage3_exact_schema_required(
    tmp_path,
):
    path = tmp_path / "stage3.tsv"

    path.write_text(
        "canonical_genbank_assembly_accession\tstage3_status\n"
        "GCA_000000001.1\tPASS\n",
        encoding="utf-8",
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="schema",
    ):
        load_stage3_population(
            path,
            expected_sha256=sha256_file(
                path
            ),
            expected_total=1,
            expected_pass=1,
            expected_status_counts={
                source_chromosome_integrity.PASS:
                    1,
            },
            expected_reason_counts={
                "x": 1,
            },
        )


def test_raw_source_sha_binding(
    tmp_path,
):
    path = tmp_path / "raw.jsonl"

    write_raw(
        path,
        [
            raw_record(
                "GCA_000000001.1"
            )
        ],
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="SHA256 mismatch",
    ):
        load_source_taxids(
            path,
            expected_sha256="0" * 64,
            expected_record_count=1,
            wanted_accessions=(
                "GCA_000000001.1",
            ),
        )


def test_raw_source_mapping_uses_only_tax_id(
    tmp_path,
):
    path = tmp_path / "raw.jsonl"

    record = raw_record(
        "GCA_000000001.1",
        taxid=12,
    )

    record["organism"][
        "organism_name"
    ] = "Misleading species name"

    record["checkmInfo"][
        "checkmSpeciesTaxId"
    ] = 777777

    digest = write_raw(
        path,
        [
            record
        ],
    )

    observed = load_source_taxids(
        path,
        expected_sha256=digest,
        expected_record_count=1,
        wanted_accessions=(
            "GCA_000000001.1",
        ),
    )

    assert observed.taxid_by_accession == {
        "GCA_000000001.1": 12,
    }


def test_raw_source_duplicate_accession_rejected(
    tmp_path,
):
    path = tmp_path / "raw.jsonl"

    records = [
        raw_record(
            "GCA_000000001.1"
        ),
        raw_record(
            "GCA_000000001.1"
        ),
    ]

    digest = write_raw(
        path,
        records,
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="duplicate accession",
    ):
        load_source_taxids(
            path,
            expected_sha256=digest,
            expected_record_count=2,
            wanted_accessions=(
                "GCA_000000001.1",
            ),
        )


def test_raw_source_invalid_accession_rejected(
    tmp_path,
):
    path = tmp_path / "raw.jsonl"

    digest = write_raw(
        path,
        [
            raw_record(
                "NOT_GCA"
            )
        ],
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="invalid canonical GCA",
    ):
        load_source_taxids(
            path,
            expected_sha256=digest,
            expected_record_count=1,
            wanted_accessions=(
                "GCA_000000001.1",
            ),
        )


def test_raw_source_missing_organism_rejected(
    tmp_path,
):
    path = tmp_path / "raw.jsonl"

    digest = write_raw(
        path,
        [
            {
                "accession":
                    "GCA_000000001.1",
            }
        ],
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="organism must be an object",
    ):
        load_source_taxids(
            path,
            expected_sha256=digest,
            expected_record_count=1,
            wanted_accessions=(
                "GCA_000000001.1",
            ),
        )


def test_raw_source_missing_taxid_rejected(
    tmp_path,
):
    path = tmp_path / "raw.jsonl"

    digest = write_raw(
        path,
        [
            {
                "accession":
                    "GCA_000000001.1",
                "organism": {
                    "organism_name":
                        "Synthetic",
                },
            }
        ],
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="organism.tax_id is absent",
    ):
        load_source_taxids(
            path,
            expected_sha256=digest,
            expected_record_count=1,
            wanted_accessions=(
                "GCA_000000001.1",
            ),
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        "12",
        0,
        -1,
        1.5,
        None,
    ],
)
def test_raw_source_invalid_taxid_rejected(
    tmp_path,
    value,
):
    path = tmp_path / "raw.jsonl"

    digest = write_raw(
        path,
        [
            raw_record(
                "GCA_000000001.1",
                taxid=value,
            )
        ],
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="positive integer",
    ):
        load_source_taxids(
            path,
            expected_sha256=digest,
            expected_record_count=1,
            wanted_accessions=(
                "GCA_000000001.1",
            ),
        )


def test_missing_stage4_accession_mapping_rejected(
    tmp_path,
):
    path = tmp_path / "raw.jsonl"

    digest = write_raw(
        path,
        [
            raw_record(
                "GCA_000000001.1"
            )
        ],
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="absent from frozen source mapping",
    ):
        load_source_taxids(
            path,
            expected_sha256=digest,
            expected_record_count=1,
            wanted_accessions=(
                "GCA_000000002.1",
            ),
        )


def evaluate_one(
    tmp_path,
    *,
    taxid,
    nodes=None,
    merged="",
    deleted="",
):
    taxonomy = write_taxonomy(
        tmp_path / "taxonomy",
        nodes=(
            base_nodes()
            if nodes is None
            else nodes
        ),
        merged=merged,
        deleted=deleted,
    )

    stage3 = synthetic_population(
        "GCA_000000001.1"
    )

    source = synthetic_source(
        {
            "GCA_000000001.1":
                taxid,
        }
    )

    return evaluate_taxonomy_population(
        stage3=stage3,
        source=source,
        taxonomy=taxonomy,
    )[0]


def test_current_taxid_resolution(
    tmp_path,
):
    observed = evaluate_one(
        tmp_path,
        taxid=12,
    )

    assert observed.decision == TaxonomyDecision(
        status=TAXONOMY_PASS,
        reason="TAXONOMY_SPECIES_RESOLVED",
        normalized_taxid=12,
        species_taxid=11,
    )


def test_single_step_merged_taxid(
    tmp_path,
):
    observed = evaluate_one(
        tmp_path,
        taxid=20,
        merged="20\t|\t12\t|\n",
    )

    assert observed.decision.normalized_taxid == 12
    assert observed.decision.species_taxid == 11


def test_multi_step_merged_taxid(
    tmp_path,
):
    observed = evaluate_one(
        tmp_path,
        taxid=20,
        merged=(
            "20\t|\t21\t|\n"
            "21\t|\t12\t|\n"
        ),
    )

    assert observed.decision.normalized_taxid == 12
    assert observed.decision.species_taxid == 11


def test_merged_cycle_is_candidate_unresolved(
    tmp_path,
):
    observed = evaluate_one(
        tmp_path,
        taxid=20,
        merged=(
            "20\t|\t21\t|\n"
            "21\t|\t20\t|\n"
        ),
    )

    assert observed.decision == TaxonomyDecision(
        status=TAXONOMY_UNRESOLVED,
        reason="TAXONOMY_NORMALIZE_MERGED_CYCLE",
        normalized_taxid=None,
        species_taxid=None,
    )


def test_deleted_taxid_is_candidate_unresolved(
    tmp_path,
):
    observed = evaluate_one(
        tmp_path,
        taxid=30,
        deleted="30\t|\n",
    )

    assert observed.decision.reason == (
        "TAXONOMY_NORMALIZE_DELETED"
    )


def test_missing_taxid_is_candidate_unresolved(
    tmp_path,
):
    observed = evaluate_one(
        tmp_path,
        taxid=999,
    )

    assert observed.decision.reason == (
        "TAXONOMY_NORMALIZE_MISSING"
    )


def test_species_resolves_to_itself(
    tmp_path,
):
    observed = evaluate_one(
        tmp_path,
        taxid=11,
    )

    assert observed.decision.normalized_taxid == 11
    assert observed.decision.species_taxid == 11


def test_descendant_resolves_to_first_exact_species(
    tmp_path,
):
    observed = evaluate_one(
        tmp_path,
        taxid=13,
    )

    assert observed.decision.species_taxid == 11


def test_species_rank_must_be_exact(
    tmp_path,
):
    nodes = (
        "1\t|\t1\t|\tno rank\t|\n"
        "2\t|\t1\t|\tsuperkingdom\t|\n"
        "10\t|\t2\t|\tspecies group\t|\n"
        "11\t|\t10\t|\tstrain\t|\n"
    )

    observed = evaluate_one(
        tmp_path,
        taxid=11,
        nodes=nodes,
    )

    assert observed.decision.reason == (
        "TAXONOMY_SPECIES_NO_SPECIES_ANCESTOR"
    )


def test_lineage_cycle_is_candidate_unresolved(
    tmp_path,
):
    nodes = (
        "1\t|\t1\t|\tno rank\t|\n"
        "20\t|\t21\t|\tstrain\t|\n"
        "21\t|\t20\t|\tgenus\t|\n"
    )

    observed = evaluate_one(
        tmp_path,
        taxid=20,
        nodes=nodes,
    )

    assert observed.decision.reason == (
        "TAXONOMY_SPECIES_LINEAGE_CYCLE"
    )


def test_missing_lineage_node_is_candidate_unresolved(
    tmp_path,
):
    nodes = (
        "1\t|\t1\t|\tno rank\t|\n"
        "20\t|\t999\t|\tstrain\t|\n"
    )

    observed = evaluate_one(
        tmp_path,
        taxid=20,
        nodes=nodes,
    )

    assert observed.decision.reason == (
        "TAXONOMY_SPECIES_MISSING_NODE"
    )


def test_no_species_ancestor_is_candidate_unresolved(
    tmp_path,
):
    observed = evaluate_one(
        tmp_path,
        taxid=2,
    )

    assert observed.decision.reason == (
        "TAXONOMY_SPECIES_NO_SPECIES_ANCESTOR"
    )


class FakeTaxonomy:
    def __init__(
        self,
        normalize_result,
        species_result,
    ):
        self.normalize_result = normalize_result
        self.species_result = species_result
        self.normalize_calls = []
        self.species_calls = []

    def normalize(
        self,
        taxid,
    ):
        self.normalize_calls.append(
            taxid
        )

        return self.normalize_result

    def species_ancestor(
        self,
        taxid,
    ):
        self.species_calls.append(
            taxid
        )

        return self.species_result


def test_unknown_taxonomy_status_fails_closed():
    taxonomy = FakeTaxonomy(
        (
            None,
            "UNKNOWN",
            0,
        ),
        (
            None,
            "NO_SPECIES_ANCESTOR",
        ),
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="failed closed",
    ):
        evaluate_taxonomy_population(
            stage3=synthetic_population(
                "GCA_000000001.1"
            ),
            source=synthetic_source(
                {
                    "GCA_000000001.1":
                        12,
                }
            ),
            taxonomy=taxonomy,
        )


def test_internally_inconsistent_taxonomy_fails_closed():
    taxonomy = FakeTaxonomy(
        (
            12,
            "DELETED",
            0,
        ),
        (
            None,
            "NO_SPECIES_ANCESTOR",
        ),
    )

    with pytest.raises(
        Stage4ExecutionError,
        match="failed closed",
    ):
        evaluate_taxonomy_population(
            stage3=synthetic_population(
                "GCA_000000001.1"
            ),
            source=synthetic_source(
                {
                    "GCA_000000001.1":
                        12,
                }
            ),
            taxonomy=taxonomy,
        )


def test_repeated_taxid_is_resolved_once_per_run():
    taxonomy = FakeTaxonomy(
        (
            12,
            "PASS",
            0,
        ),
        (
            11,
            "PASS",
        ),
    )

    stage3 = synthetic_population(
        "GCA_000000002.1",
        "GCA_000000001.1",
    )

    source = synthetic_source(
        {
            "GCA_000000001.1":
                12,
            "GCA_000000002.1":
                12,
        }
    )

    observed = evaluate_taxonomy_population(
        stage3=stage3,
        source=source,
        taxonomy=taxonomy,
    )

    assert len(
        observed
    ) == 2

    assert taxonomy.normalize_calls == [
        12
    ]

    assert taxonomy.species_calls == [
        12
    ]


def test_source_membership_must_match_stage4_membership():
    with pytest.raises(
        Stage4ExecutionError,
        match="membership differs",
    ):
        evaluate_taxonomy_population(
            stage3=synthetic_population(
                "GCA_000000001.1"
            ),
            source=synthetic_source(
                {
                    "GCA_000000002.1":
                        12,
                }
            ),
            taxonomy=FakeTaxonomy(
                (
                    12,
                    "PASS",
                    0,
                ),
                (
                    11,
                    "PASS",
                ),
            ),
        )


def test_decision_rows_are_deterministic_and_aggregate_exact():
    records = (
        Stage4CandidateEvaluation(
            accession="GCA_000000002.1",
            organism_taxid=20,
            decision=TaxonomyDecision(
                status=TAXONOMY_UNRESOLVED,
                reason=(
                    "TAXONOMY_NORMALIZE_DELETED"
                ),
                normalized_taxid=None,
                species_taxid=None,
            ),
        ),
        Stage4CandidateEvaluation(
            accession="GCA_000000001.1",
            organism_taxid=12,
            decision=TaxonomyDecision(
                status=TAXONOMY_PASS,
                reason=(
                    "TAXONOMY_SPECIES_RESOLVED"
                ),
                normalized_taxid=12,
                species_taxid=11,
            ),
        ),
        Stage4CandidateEvaluation(
            accession="GCA_000000003.1",
            organism_taxid=13,
            decision=TaxonomyDecision(
                status=TAXONOMY_PASS,
                reason=(
                    "TAXONOMY_SPECIES_RESOLVED"
                ),
                normalized_taxid=13,
                species_taxid=11,
            ),
        ),
    )

    observed = build_decision_rows(
        records,
        expected_total=3,
    )

    assert [
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in observed.rows
    ] == [
        "GCA_000000001.1",
        "GCA_000000002.1",
        "GCA_000000003.1",
    ]

    assert observed.status_counts == {
        TAXONOMY_PASS: 2,
        TAXONOMY_UNRESOLVED: 1,
    }

    assert observed.reason_counts == {
        "TAXONOMY_NORMALIZE_DELETED": 1,
        "TAXONOMY_SPECIES_RESOLVED": 2,
    }

    assert observed.unique_organism_taxid_count == 3
    assert observed.resolved_distinct_species_taxid_count == 1

    assert observed.rows[1][
        "normalized_organism_taxid"
    ] == ""

    assert observed.rows[1][
        "species_taxid"
    ] == ""


def test_species_unresolved_row_retains_normalized_taxid():
    observed = build_decision_rows(
        (
            Stage4CandidateEvaluation(
                accession="GCA_000000001.1",
                organism_taxid=12,
                decision=TaxonomyDecision(
                    status=TAXONOMY_UNRESOLVED,
                    reason=(
                        "TAXONOMY_SPECIES_NO_SPECIES_ANCESTOR"
                    ),
                    normalized_taxid=12,
                    species_taxid=None,
                ),
            ),
        ),
        expected_total=1,
    )

    assert observed.rows[0][
        "normalized_organism_taxid"
    ] == "12"

    assert observed.rows[0][
        "species_taxid"
    ] == ""


def test_decision_count_must_close_exactly():
    with pytest.raises(
        Stage4ExecutionError,
        match="record count mismatch",
    ):
        build_decision_rows(
            (
                Stage4CandidateEvaluation(
                    accession="GCA_000000001.1",
                    organism_taxid=12,
                    decision=TaxonomyDecision(
                        status=TAXONOMY_PASS,
                        reason=(
                            "TAXONOMY_SPECIES_RESOLVED"
                        ),
                        normalized_taxid=12,
                        species_taxid=11,
                    ),
                ),
            ),
            expected_total=2,
        )


def test_unresolved_decision_cannot_contain_species_taxid():
    with pytest.raises(
        Stage4ExecutionError,
        match="contains species TaxID",
    ):
        build_decision_rows(
            (
                Stage4CandidateEvaluation(
                    accession="GCA_000000001.1",
                    organism_taxid=12,
                    decision=TaxonomyDecision(
                        status=TAXONOMY_UNRESOLVED,
                        reason=(
                            "TAXONOMY_SPECIES_NO_SPECIES_ANCESTOR"
                        ),
                        normalized_taxid=12,
                        species_taxid=11,
                    ),
                ),
            ),
            expected_total=1,
        )


def test_execution_helper_has_no_prohibited_runtime_dependencies():
    source = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    ).lower()

    for token in (
        "import requests",
        "import urllib",
        "import httpx",
        "import aiohttp",
        "source_membership",
        "validate_ops",
        "validate_sr",
        "compare_ops_sr",
        "build_300_2400_feature_space",
    ):
        assert token not in source


def test_execution_helper_does_not_own_production_finalization():
    source = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert "os.replace" not in source
    assert "stage4-content-manifest.tsv" not in source
    assert "stage4-predecision-provenance.json" not in source
