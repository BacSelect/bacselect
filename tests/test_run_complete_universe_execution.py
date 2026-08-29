from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from bacselect import source_chromosome_integrity
from bacselect import source_truth
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    BIOSAMPLE_NONREPRESENTATIVE,
    BIOSAMPLE_UNRESOLVED,
    TAXONOMY_PASS,
    TAXONOMY_UNRESOLVED,
)
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


WRAPPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "run_complete_universe_execution.py"
)


def load_wrapper():
    name = (
        "_bacselect_stage5a_wrapper_synthetic_test"
    )

    spec = importlib.util.spec_from_file_location(
        name,
        WRAPPER_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


module = load_wrapper()


def accession(
    number: int,
) -> str:
    return f"GCA_{number:09d}.1"


def sha(
    token: str,
) -> str:
    return hashlib.sha256(
        token.encode(
            "utf-8"
        )
    ).hexdigest()


def write_tsv(
    path: Path,
    fields,
    rows,
):
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def synthetic_fixture(
    tmp_path: Path,
):
    # Nine candidates cover every frozen terminal class:
    #
    # 1 source exclusion
    # 2 source unresolved
    # 3 repeated-BioSample nonrepresentative
    # 4 repeated-BioSample unresolved
    # 5 chromosome exclusion
    # 6 chromosome unresolved
    # 7 taxonomy unresolved
    # 8 eligible species A
    # 9 eligible species B

    all_accessions = tuple(
        accession(
            value
        )
        for value in range(
            1,
            10,
        )
    )

    stage1_suitable = tuple(
        accession(
            value
        )
        for value in range(
            3,
            10,
        )
    )

    stage2_continue = tuple(
        accession(
            value
        )
        for value in range(
            5,
            10,
        )
    )

    stage3_pass = (
        accession(7),
        accession(8),
        accession(9),
    )

    stage4_pass = (
        accession(8),
        accession(9),
    )

    common_source_sha = sha(
        "source"
    )

    common_sequence_sha = sha(
        "sequence"
    )

    common_fingerprint = sha(
        "fingerprint"
    )

    stage1_rows = []

    for value in range(
        1,
        10,
    ):
        if value == 1:
            status = source_truth.EXCLUDE
            reason = "SOURCE_TRUTH_EXCLUDED"

        elif value == 2:
            status = source_truth.UNRESOLVED
            reason = "SOURCE_TRUTH_UNRESOLVED"

        else:
            status = source_truth.SUITABLE
            reason = "SOURCE_TRUTH_SUITABLE"

        stage1_rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession(value),
                "source_evidence_sha256":
                    common_source_sha,
                "sequence_set_sha256":
                    common_sequence_sha,
                "duplicate_relation_count":
                    "0",
                "containment_relation_count":
                    "0",
                "source_truth_status":
                    status,
                "source_truth_reason":
                    reason,
            }
        )

    stage2_rows = []

    for value in range(
        3,
        10,
    ):
        if value == 3:
            status = BIOSAMPLE_NONREPRESENTATIVE
            reason = (
                "BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE"
            )

        elif value == 4:
            status = BIOSAMPLE_UNRESOLVED
            reason = "BIOSAMPLE_FINGERPRINTS_DIFFER"

        else:
            status = BIOSAMPLE_CONTINUE
            reason = "BIOSAMPLE_SINGLETON"

        stage2_rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession(value),
                "biosample":
                    f"SAMN{value:08d}",
                "source_evidence_sha256":
                    common_source_sha,
                "assembly_fingerprint":
                    common_fingerprint,
                "stage2_status":
                    status,
                "stage2_reason":
                    reason,
            }
        )

    stage3_rows = []

    for value in range(
        5,
        10,
    ):
        if value == 5:
            status = source_chromosome_integrity.EXCLUDE
            reason = "CHROMOSOME_EXCLUDED"

        elif value == 6:
            status = source_chromosome_integrity.UNRESOLVED
            reason = "CHROMOSOME_UNRESOLVED"

        else:
            status = source_chromosome_integrity.PASS
            reason = "CHROMOSOME_INTEGRITY_PASS"

        stage3_rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession(value),
                "source_evidence_sha256":
                    common_source_sha,
                "stage2_status":
                    BIOSAMPLE_CONTINUE,
                "chromosome_component_count":
                    "1",
                "closure_supported_chromosome_count":
                    "1",
                "closure_unsupported_chromosome_count":
                    "0",
                "chromosome_integrity_triggered":
                    "false",
                "historical_adjudication_reused":
                    "false",
                "stage3_status":
                    status,
                "stage3_reason":
                    reason,
            }
        )

    stage4_rows = [
        {
            "canonical_genbank_assembly_accession":
                accession(7),
            "organism_taxid":
                "700",
            "normalized_organism_taxid":
                "",
            "species_taxid":
                "",
            "stage4_status":
                TAXONOMY_UNRESOLVED,
            "stage4_reason":
                "TAXONOMY_NORMALIZE_DELETED",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(8),
            "organism_taxid":
                "800",
            "normalized_organism_taxid":
                "800",
            "species_taxid":
                "80",
            "stage4_status":
                TAXONOMY_PASS,
            "stage4_reason":
                "TAXONOMY_SPECIES_RESOLVED",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(9),
            "organism_taxid":
                "900",
            "normalized_organism_taxid":
                "900",
            "species_taxid":
                "90",
            "stage4_status":
                TAXONOMY_PASS,
            "stage4_reason":
                "TAXONOMY_SPECIES_RESOLVED",
        },
    ]

    paths = module.DecisionPaths(
        stage1=tmp_path / "stage1.tsv",
        stage2=tmp_path / "stage2.tsv",
        stage3=tmp_path / "stage3.tsv",
        stage4=tmp_path / "stage4.tsv",
    )

    write_tsv(
        paths.stage1,
        module.STAGE1_DECISION_FIELDS,
        stage1_rows,
    )

    write_tsv(
        paths.stage2,
        module.STAGE2_DECISION_FIELDS,
        stage2_rows,
    )

    write_tsv(
        paths.stage3,
        module.STAGE3_DECISION_FIELDS,
        stage3_rows,
    )

    write_tsv(
        paths.stage4,
        module.STAGE4_DECISION_FIELDS,
        stage4_rows,
    )

    identities = module.DecisionArtifactIdentities(
        stage1=module.sha256_file(
            paths.stage1
        ),
        stage2=module.sha256_file(
            paths.stage2
        ),
        stage3=module.sha256_file(
            paths.stage3
        ),
        stage4=module.sha256_file(
            paths.stage4
        ),
    )

    expectations = module.Stage5AExpectations(
        stage1_total=9,
        stage1_suitable=7,
        stage1_excluded=1,
        stage1_unresolved=1,
        stage2_total=7,
        stage2_continue=5,
        stage2_nonrepresentative=1,
        stage2_unresolved=1,
        stage3_total=5,
        stage3_pass=3,
        stage3_excluded=1,
        stage3_unresolved=1,
        stage4_total=3,
        stage4_pass=2,
        stage4_unresolved=1,
        complete_species_count=2,
        stage1_membership_sha256=(
            accession_membership_sha256(
                all_accessions
            )
        ),
        stage2_input_membership_sha256=(
            accession_membership_sha256(
                stage1_suitable
            )
        ),
        stage3_input_membership_sha256=(
            accession_membership_sha256(
                stage2_continue
            )
        ),
        stage4_input_membership_sha256=(
            accession_membership_sha256(
                stage3_pass
            )
        ),
    )

    return {
        "paths":
            paths,
        "identities":
            identities,
        "expectations":
            expectations,
        "complete_membership":
            accession_membership_sha256(
                stage4_pass
            ),
    }


def test_production_constants_match_frozen_audit():
    assert (
        module.EXPECTED_STAGE1_COMPLETION_SHA256
        == "b459801d832137fb0399bc34dfe361163"
        "6ca1ffc0339c802a16a6216f9595dd2"
    )

    assert (
        module.EXPECTED_STAGE2_COMPLETION_SHA256
        == "d00801b1833c6c3cdee44a8c981d9eb1"
        "fc900f6becabc6d59e996877462d76a6"
    )

    assert (
        module.EXPECTED_STAGE3_COMPLETION_SHA256
        == "c5aff0e1e5cca6202688198a49069b1a"
        "e3e7b35d19f4939538d7c3f01ff562d2"
    )

    assert (
        module.EXPECTED_STAGE4_COMPLETION_SHA256
        == "b878dd9f20c01867b87265b9d35c23db"
        "5ad556621c5750a0193d9e1f2b5960ad"
    )

    assert (
        module.PRODUCTION_EXPECTATIONS.stage1_total
        == 68480
    )

    assert (
        module.PRODUCTION_EXPECTATIONS.stage4_pass
        == 67957
    )

    assert (
        module.PRODUCTION_EXPECTATIONS.complete_species_count
        == 16144
    )


def test_exact_output_schemas():
    assert (
        module.source_complete_universe
        .TERMINAL_COMPOSITION_FIELDS
    ) == (
        "canonical_genbank_assembly_accession",
        "final_disposition",
        "terminal_layer",
        "terminal_status",
        "terminal_reason",
        "species_taxid",
    )

    assert (
        module.source_complete_universe
        .COMPLETE_UNIVERSE_FIELDS
    ) == (
        "canonical_genbank_assembly_accession",
        "species_taxid",
    )


def test_synthetic_chain_memberships_are_exact(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    chain = module.load_decision_chain(
        fixture[
            "paths"
        ],
        identities=fixture[
            "identities"
        ],
        expectations=fixture[
            "expectations"
        ],
    )

    assert (
        chain.stage1.suitable_membership_sha256
        == fixture[
            "expectations"
        ].stage2_input_membership_sha256
    )

    assert (
        chain.stage2.continue_membership_sha256
        == fixture[
            "expectations"
        ].stage3_input_membership_sha256
    )

    assert (
        chain.stage3.pass_membership_sha256
        == fixture[
            "expectations"
        ].stage4_input_membership_sha256
    )

    assert (
        chain.stage4.pass_membership_sha256
        == fixture[
            "complete_membership"
        ]
    )


def test_synthetic_composition_covers_all_terminal_classes(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    chain = module.load_decision_chain(
        fixture["paths"],
        identities=fixture["identities"],
        expectations=fixture["expectations"],
    )

    records = module.compose_terminal_population(
        chain,
        expectations=fixture["expectations"],
    )

    summary = (
        module.source_complete_universe
        .disposition_summary(
            records
        )
    )

    assert summary.as_dict() == {
        "total": 9,
        "ELIGIBLE": 2,
        "EXCLUDED": 2,
        "WITHHELD_UNRESOLVED": 4,
        "NONREPRESENTATIVE": 1,
    }

    assert {
        record.terminal_layer
        for record in records
    } == {
        "source_truth",
        "repeated_biosample",
        "chromosome_integrity",
        "taxonomy",
        "eligible",
    }


def test_synthetic_universe_equals_stage4_pass(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    chain = module.load_decision_chain(
        fixture["paths"],
        identities=fixture["identities"],
        expectations=fixture["expectations"],
    )

    records = module.compose_terminal_population(
        chain,
        expectations=fixture["expectations"],
    )

    universe, membership = (
        module.derive_and_validate_universe(
            records,
            expectations=fixture["expectations"],
            expected_membership_sha256=(
                chain.stage4.pass_membership_sha256
            ),
        )
    )

    assert [
        item.accession
        for item in universe
    ] == [
        accession(8),
        accession(9),
    ]

    assert membership == fixture[
        "complete_membership"
    ]


def test_stage_membership_chain_mismatch_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    rows = module.read_tsv_exact(
        fixture["paths"].stage2,
        module.STAGE2_DECISION_FIELDS,
        label="synthetic Stage 2",
    )

    rows[0][
        "canonical_genbank_assembly_accession"
    ] = accession(99)

    write_tsv(
        fixture["paths"].stage2,
        module.STAGE2_DECISION_FIELDS,
        rows,
    )

    identities = module.DecisionArtifactIdentities(
        stage1=fixture["identities"].stage1,
        stage2=module.sha256_file(
            fixture["paths"].stage2
        ),
        stage3=fixture["identities"].stage3,
        stage4=fixture["identities"].stage4,
    )

    with pytest.raises(
        module.Stage5AWrapperError,
    ):
        module.load_decision_chain(
            fixture["paths"],
            identities=identities,
            expectations=fixture["expectations"],
        )


def test_duplicate_accession_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    rows = module.read_tsv_exact(
        fixture["paths"].stage1,
        module.STAGE1_DECISION_FIELDS,
        label="synthetic Stage 1",
    )

    rows[1][
        "canonical_genbank_assembly_accession"
    ] = rows[0][
        "canonical_genbank_assembly_accession"
    ]

    write_tsv(
        fixture["paths"].stage1,
        module.STAGE1_DECISION_FIELDS,
        rows,
    )

    with pytest.raises(
        module.Stage5AWrapperError,
        match="duplicate Stage 1 accession",
    ):
        module._load_stage1(
            fixture["paths"].stage1,
            expected_sha256=module.sha256_file(
                fixture["paths"].stage1
            ),
            expectations=fixture["expectations"],
        )


def test_stage4_species_count_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    rows = module.read_tsv_exact(
        fixture["paths"].stage4,
        module.STAGE4_DECISION_FIELDS,
        label="synthetic Stage 4",
    )

    rows[2][
        "species_taxid"
    ] = "80"

    write_tsv(
        fixture["paths"].stage4,
        module.STAGE4_DECISION_FIELDS,
        rows,
    )

    with pytest.raises(
        module.Stage5AWrapperError,
        match="resolved species count mismatch",
    ):
        module._load_stage4(
            fixture["paths"].stage4,
            expected_sha256=module.sha256_file(
                fixture["paths"].stage4
            ),
            expectations=fixture["expectations"],
        )


def test_execute_writes_exact_six_file_final_artifact_set(
    tmp_path,
    capsys,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    repo = tmp_path / "repo"
    repo.mkdir()

    output_root = (
        tmp_path
        / "scratch"
    )

    completion_sha256 = {
        "stage1": sha("completion-stage1"),
        "stage2": sha("completion-stage2"),
        "stage3": sha("completion-stage3"),
        "stage4": sha("completion-stage4"),
    }

    final_dir = module.execute_to_scratch(
        repo=repo,
        expected_commit="a" * 40,
        expected_wrapper_sha256=sha(
            "wrapper"
        ),
        expected_wrapper_test_sha256=sha(
            "wrapper-tests"
        ),
        output_root=output_root,
        decision_paths=fixture["paths"],
        decision_identities=fixture["identities"],
        completion_sha256=completion_sha256,
        expectations=fixture["expectations"],
        frozen_repo_sha256={
            "synthetic":
                sha("synthetic")
        },
    )

    assert final_dir.is_dir()

    assert {
        path.name
        for path in final_dir.iterdir()
    } == {
        "stage5a-predecision-provenance.json",
        "stage5-terminal-composition.tsv",
        "complete-eligible-fresh-universe.tsv",
        "stage5a-execution-provenance.json",
        "stage5a-aggregate-summary.json",
        "stage5a-content-manifest.tsv",
    }

    assert not (
        output_root
        / ("." + "a" * 40 + ".partial")
    ).exists()

    output = capsys.readouterr()

    assert "GCA_" not in output.out
    assert "GCA_" not in output.err


def test_predecision_records_no_candidate_rows_parsed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    repo = tmp_path / "repo"
    repo.mkdir()

    output_root = tmp_path / "scratch"

    final_dir = module.execute_to_scratch(
        repo=repo,
        expected_commit="b" * 40,
        expected_wrapper_sha256=sha("wrapper"),
        expected_wrapper_test_sha256=sha(
            "wrapper-tests"
        ),
        output_root=output_root,
        decision_paths=fixture["paths"],
        decision_identities=fixture["identities"],
        completion_sha256={
            "stage1": sha("c1"),
            "stage2": sha("c2"),
            "stage3": sha("c3"),
            "stage4": sha("c4"),
        },
        expectations=fixture["expectations"],
        frozen_repo_sha256={},
    )

    predecision = json.loads(
        (
            final_dir
            / "stage5a-predecision-provenance.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert (
        predecision[
            "stage1_candidate_rows_parsed"
        ]
        is False
    )

    assert (
        predecision[
            "stage2_candidate_rows_parsed"
        ]
        is False
    )

    assert (
        predecision[
            "stage3_candidate_rows_parsed"
        ]
        is False
    )

    assert (
        predecision[
            "stage4_candidate_rows_parsed"
        ]
        is False
    )

    assert (
        predecision[
            "baseline_membership_consulted"
        ]
        is False
    )


def test_predecision_survives_postcheckpoint_parse_failure(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    fixture[
        "paths"
    ].stage1.write_text(
        "not\ta\tvalid\tstage1\n",
        encoding="utf-8",
    )

    identities = module.DecisionArtifactIdentities(
        stage1=module.sha256_file(
            fixture["paths"].stage1
        ),
        stage2=fixture["identities"].stage2,
        stage3=fixture["identities"].stage3,
        stage4=fixture["identities"].stage4,
    )

    repo = tmp_path / "repo"
    repo.mkdir()

    output_root = tmp_path / "scratch"

    with pytest.raises(
        module.Stage5AWrapperError,
    ):
        module.execute_to_scratch(
            repo=repo,
            expected_commit="c" * 40,
            expected_wrapper_sha256=sha("wrapper"),
            expected_wrapper_test_sha256=sha(
                "wrapper-tests"
            ),
            output_root=output_root,
            decision_paths=fixture["paths"],
            decision_identities=identities,
            completion_sha256={
                "stage1": sha("c1"),
                "stage2": sha("c2"),
                "stage3": sha("c3"),
                "stage4": sha("c4"),
            },
            expectations=fixture["expectations"],
            frozen_repo_sha256={},
        )

    partial = (
        output_root
        / ("." + "c" * 40 + ".partial")
    )

    assert partial.is_dir()

    assert (
        partial
        / "stage5a-predecision-provenance.json"
    ).is_file()

    assert not (
        output_root
        / ("c" * 40)
    ).exists()


def test_output_root_inside_repo_rejected(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(
        module.Stage5AWrapperError,
        match="outside repository",
    ):
        module.execute_to_scratch(
            repo=repo,
            expected_commit="d" * 40,
            expected_wrapper_sha256=sha("wrapper"),
            expected_wrapper_test_sha256=sha(
                "wrapper-tests"
            ),
            output_root=repo / "output",
            decision_paths=fixture["paths"],
            decision_identities=fixture["identities"],
            completion_sha256={
                "stage1": sha("c1"),
                "stage2": sha("c2"),
                "stage3": sha("c3"),
                "stage4": sha("c4"),
            },
            expectations=fixture["expectations"],
            frozen_repo_sha256={},
        )


def test_content_manifest_covers_five_pre_manifest_artifacts(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    repo = tmp_path / "repo"
    repo.mkdir()

    final_dir = module.execute_to_scratch(
        repo=repo,
        expected_commit="e" * 40,
        expected_wrapper_sha256=sha("wrapper"),
        expected_wrapper_test_sha256=sha(
            "wrapper-tests"
        ),
        output_root=tmp_path / "scratch",
        decision_paths=fixture["paths"],
        decision_identities=fixture["identities"],
        completion_sha256={
            "stage1": sha("c1"),
            "stage2": sha("c2"),
            "stage3": sha("c3"),
            "stage4": sha("c4"),
        },
        expectations=fixture["expectations"],
        frozen_repo_sha256={},
    )

    rows = module.read_tsv_exact(
        final_dir
        / "stage5a-content-manifest.tsv",
        module.CONTENT_MANIFEST_FIELDS,
        label="Stage 5A content manifest",
    )

    assert len(
        rows
    ) == 5

    assert {
        row["path"]
        for row in rows
    } == {
        "stage5a-predecision-provenance.json",
        "stage5-terminal-composition.tsv",
        "complete-eligible-fresh-universe.tsv",
        "stage5a-execution-provenance.json",
        "stage5a-aggregate-summary.json",
    }


def test_terminal_species_taxid_blank_for_noneligible(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    chain = module.load_decision_chain(
        fixture["paths"],
        identities=fixture["identities"],
        expectations=fixture["expectations"],
    )

    records = module.compose_terminal_population(
        chain,
        expectations=fixture["expectations"],
    )

    rows = (
        module.source_complete_universe
        .terminal_composition_rows(
            records
        )
    )

    for row in rows:
        if (
            row["final_disposition"]
            != "ELIGIBLE"
        ):
            assert (
                row["species_taxid"]
                == ""
            )


def test_universe_rows_are_deterministically_sorted(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    chain = module.load_decision_chain(
        fixture["paths"],
        identities=fixture["identities"],
        expectations=fixture["expectations"],
    )

    records = module.compose_terminal_population(
        chain,
        expectations=fixture["expectations"],
    )

    universe, _ = (
        module.derive_and_validate_universe(
            records,
            expectations=fixture["expectations"],
            expected_membership_sha256=(
                chain.stage4.pass_membership_sha256
            ),
        )
    )

    rows = (
        module.source_complete_universe
        .complete_universe_rows(
            reversed(
                universe
            )
        )
    )

    assert [
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in rows
    ] == [
        accession(8),
        accession(9),
    ]


def test_wrapper_imports_no_stage5b_or_downstream_modules():
    source = WRAPPER_PATH.read_text(
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

    prohibited = (
        "source_membership",
        "source_eligibility",
        "structural_feature",
        "coverage",
        "selector",
        "distance",
    )

    for imported_name in imported:
        assert not any(
            token in imported_name
            for token in prohibited
        ), imported_name
