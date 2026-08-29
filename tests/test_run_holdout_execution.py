from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


REPO = Path(
    __file__
).resolve().parents[1]

WRAPPER_PATH = (
    REPO
    / "validation"
    / "selector-v1"
    / "run_holdout_execution.py"
)

SPEC = importlib.util.spec_from_file_location(
    "run_holdout_execution",
    WRAPPER_PATH,
)

assert SPEC is not None
assert SPEC.loader is not None

module = importlib.util.module_from_spec(
    SPEC
)

sys.modules[
    SPEC.name
] = module

SPEC.loader.exec_module(
    module
)


def accession(
    value: int,
) -> str:
    return f"GCA_{value:09d}.1"


def sha(
    text: str,
) -> str:
    return hashlib.sha256(
        text.encode(
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

        for row in rows:
            writer.writerow(
                row
            )

    return module.sha256_file(
        path
    )


def valid_metadata_record(
    value: int,
):
    value_accession = accession(
        value
    )

    return {
        "accession":
            value_accession,
        "current_accession":
            value_accession,
        "source_database":
            "SOURCE_DATABASE_GENBANK",
        "assembly_info": {
            "assembly_status":
                "current",
            "assembly_level":
                "Complete Genome",
            "biosample": {
                "accession":
                    f"SAMN{100000 + value}",
            },
        },
    }


def write_jsonl(
    path: Path,
    records,
):
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

    return module.sha256_file(
        path
    )


def synthetic_fixture(
    tmp_path: Path,
):
    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir()

    stage5a_dir = (
        tmp_path
        / "stage5a"
    )

    stage5a_dir.mkdir()

    universe_rows = [
        {
            "canonical_genbank_assembly_accession":
                accession(2),
            "species_taxid":
                "10",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(4),
            "species_taxid":
                "20",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(6),
            "species_taxid":
                "30",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(8),
            "species_taxid":
                "40",
        },
    ]

    universe_path = (
        stage5a_dir
        / "complete-eligible-fresh-universe.tsv"
    )

    universe_sha = write_tsv(
        universe_path,
        module.COMPLETE_UNIVERSE_FIELDS,
        universe_rows,
    )

    content_manifest = (
        stage5a_dir
        / "stage5a-content-manifest.tsv"
    )

    content_manifest.write_text(
        "path\tsize_bytes\tsha256\n"
        "synthetic\t1\t"
        + sha(
            "synthetic"
        )
        + "\n",
        encoding="utf-8",
    )

    execution_provenance = (
        stage5a_dir
        / "stage5a-execution-provenance.json"
    )

    execution_provenance.write_text(
        json.dumps(
            {
                "schema_version":
                    1,
                "status":
                    "STAGE5A_COMPLETE_UNIVERSE_COMPLETE",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    raw_source = (
        tmp_path
        / "raw.jsonl"
    )

    raw_sha = write_jsonl(
        raw_source,
        [
            valid_metadata_record(
                value
            )
            for value in (
                1,
                2,
                3,
                4,
                5,
                6,
            )
        ],
    )

    baseline = (
        tmp_path
        / "baseline.tsv"
    )

    baseline_sha = write_tsv(
        baseline,
        (
            "batch",
            "canonical_genbank_assembly_accession",
            "feature",
        ),
        [
            {
                "batch":
                    "b",
                "canonical_genbank_assembly_accession":
                    accession(
                        value
                    ),
                "feature":
                    "1",
            }
            for value in (
                1,
                2,
                3,
                99,
            )
        ],
    )

    universe_membership = (
        accession_membership_sha256(
            (
                accession(2),
                accession(4),
                accession(6),
                accession(8),
            )
        )
    )

    identities = module.InputIdentities(
        complete_universe=(
            universe_sha
        ),
        stage5a_content_manifest=(
            module.sha256_file(
                content_manifest
            )
        ),
        stage5a_execution_provenance=(
            module.sha256_file(
                execution_provenance
            )
        ),
        raw_source=(
            raw_sha
        ),
        baseline_matrix=(
            baseline_sha
        ),
    )

    stage5a_expectations = (
        module.Stage5AExpectations(
            complete_universe_count=4,
            complete_universe_species_count=4,
            complete_universe_membership_sha256=(
                universe_membership
            ),
        )
    )

    historical_expectations = (
        module.HistoricalExpectations(
            raw_records=6,
            metadata_retained=6,
            metadata_excluded=0,
            metadata_unresolved=0,
            baseline_accessions=4,
            retained_present_in_baseline=3,
            retained_absent_from_baseline=3,
            baseline_not_in_metadata_retained=1,
        )
    )

    return {
        "repo":
            repo,
        "paths":
            module.InputPaths(
                stage5a_execution_dir=(
                    stage5a_dir
                ),
                raw_source=(
                    raw_source
                ),
                baseline_matrix=(
                    baseline
                ),
            ),
        "identities":
            identities,
        "stage5a_expectations":
            stage5a_expectations,
        "historical_expectations":
            historical_expectations,
        "output_root":
            tmp_path
            / "output",
    }


def execute_fixture(
    fixture,
    *,
    commit="a" * 40,
):
    return module.execute_to_scratch(
        repo=fixture[
            "repo"
        ],
        expected_commit=commit,
        expected_wrapper_sha256=sha(
            "wrapper"
        ),
        expected_wrapper_test_sha256=sha(
            "tests"
        ),
        output_root=fixture[
            "output_root"
        ],
        input_paths=fixture[
            "paths"
        ],
        input_identities=fixture[
            "identities"
        ],
        stage5a_expectations=fixture[
            "stage5a_expectations"
        ],
        historical_expectations=fixture[
            "historical_expectations"
        ],
        frozen_repo_sha256={},
    )


def test_successful_synthetic_historical_reconstruction(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    summary = json.loads(
        (
            final_dir
            / "stage5b-aggregate-summary.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert summary[
        "historical_reconstruction"
    ] == {
        "baseline_accessions":
            4,
        "metadata_retained":
            6,
        "retained_present_in_baseline":
            3,
        "retained_absent_from_baseline":
            3,
        "baseline_not_in_metadata_retained":
            1,
    }


def test_successful_synthetic_complete_universe_intersection(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    rows = module.read_tsv_exact(
        final_dir
        / "external-decision-holdout.tsv",
        module.source_holdout.EXTERNAL_HOLDOUT_FIELDS,
        label="synthetic holdout",
    )

    assert rows == [
        {
            "canonical_genbank_assembly_accession":
                accession(4),
            "species_taxid":
                "20",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(6),
            "species_taxid":
                "30",
        },
    ]


def test_execute_writes_exact_seven_final_files(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    assert {
        path.name
        for path in final_dir.iterdir()
    } == {
        "stage5b-predecision-provenance.json",
        "reconstructed-retained-absent-from-baseline.tsv",
        "external-decision-holdout.tsv",
        "stage5b-input-evidence-manifest.tsv",
        "stage5b-execution-provenance.json",
        "stage5b-aggregate-summary.json",
        "stage5b-content-manifest.tsv",
    }


def test_predecision_exists_before_metadata_parser_invocation(
    tmp_path,
    monkeypatch,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    original = module._load_metadata_retained

    def guarded(
        path,
        *,
        expectations,
    ):
        partial = (
            fixture[
                "output_root"
            ]
            / (
                "."
                + "b" * 40
                + ".partial"
            )
        )

        assert (
            partial
            / "stage5b-predecision-provenance.json"
        ).is_file()

        return original(
            path,
            expectations=expectations,
        )

    monkeypatch.setattr(
        module,
        "_load_metadata_retained",
        guarded,
    )

    execute_fixture(
        fixture,
        commit="b" * 40,
    )


def test_predecision_exists_before_baseline_loader_invocation(
    tmp_path,
    monkeypatch,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    original = module._load_baseline

    def guarded(
        path,
        *,
        expected_sha256,
        expectations,
    ):
        partial = (
            fixture[
                "output_root"
            ]
            / (
                "."
                + "c" * 40
                + ".partial"
            )
        )

        assert (
            partial
            / "stage5b-predecision-provenance.json"
        ).is_file()

        return original(
            path,
            expected_sha256=expected_sha256,
            expectations=expectations,
        )

    monkeypatch.setattr(
        module,
        "_load_baseline",
        guarded,
    )

    execute_fixture(
        fixture,
        commit="c" * 40,
    )


def test_predecision_exists_before_complete_universe_parsing(
    tmp_path,
    monkeypatch,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    original = module._load_complete_universe

    def guarded(
        path,
        *,
        expectations,
    ):
        partial = (
            fixture[
                "output_root"
            ]
            / (
                "."
                + "d" * 40
                + ".partial"
            )
        )

        assert (
            partial
            / "stage5b-predecision-provenance.json"
        ).is_file()

        return original(
            path,
            expectations=expectations,
        )

    monkeypatch.setattr(
        module,
        "_load_complete_universe",
        guarded,
    )

    execute_fixture(
        fixture,
        commit="d" * 40,
    )


def test_predecision_survives_later_metadata_parse_failure(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    fixture[
        "paths"
    ].raw_source.write_text(
        "not-json\n",
        encoding="utf-8",
    )

    fixture[
        "identities"
    ] = module.InputIdentities(
        complete_universe=fixture[
            "identities"
        ].complete_universe,
        stage5a_content_manifest=fixture[
            "identities"
        ].stage5a_content_manifest,
        stage5a_execution_provenance=fixture[
            "identities"
        ].stage5a_execution_provenance,
        raw_source=module.sha256_file(
            fixture[
                "paths"
            ].raw_source
        ),
        baseline_matrix=fixture[
            "identities"
        ].baseline_matrix,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
    ):
        execute_fixture(
            fixture,
            commit="e" * 40,
        )

    assert (
        fixture[
            "output_root"
        ]
        / (
            "."
            + "e" * 40
            + ".partial"
        )
        / "stage5b-predecision-provenance.json"
    ).is_file()


def test_predecision_survives_later_baseline_parse_failure(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    fixture[
        "paths"
    ].baseline_matrix.write_text(
        "bad\theader\nx\ty\n",
        encoding="utf-8",
    )

    fixture[
        "identities"
    ] = module.InputIdentities(
        complete_universe=fixture[
            "identities"
        ].complete_universe,
        stage5a_content_manifest=fixture[
            "identities"
        ].stage5a_content_manifest,
        stage5a_execution_provenance=fixture[
            "identities"
        ].stage5a_execution_provenance,
        raw_source=fixture[
            "identities"
        ].raw_source,
        baseline_matrix=module.sha256_file(
            fixture[
                "paths"
            ].baseline_matrix
        ),
    )

    with pytest.raises(
        module.Stage5BWrapperError,
    ):
        execute_fixture(
            fixture,
            commit="f" * 40,
        )

    assert (
        fixture[
            "output_root"
        ]
        / (
            "."
            + "f" * 40
            + ".partial"
        )
        / "stage5b-predecision-provenance.json"
    ).is_file()


def test_wrong_raw_source_sha_fails_before_parser(
    tmp_path,
    monkeypatch,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr(
        module,
        "_load_metadata_retained",
        forbidden,
    )

    fixture[
        "identities"
    ] = module.InputIdentities(
        complete_universe=fixture[
            "identities"
        ].complete_universe,
        stage5a_content_manifest=fixture[
            "identities"
        ].stage5a_content_manifest,
        stage5a_execution_provenance=fixture[
            "identities"
        ].stage5a_execution_provenance,
        raw_source="0" * 64,
        baseline_matrix=fixture[
            "identities"
        ].baseline_matrix,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="SHA256 mismatch",
    ):
        execute_fixture(
            fixture
        )

    assert called is False


def test_wrong_baseline_sha_fails_before_parser(
    tmp_path,
    monkeypatch,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr(
        module,
        "_load_baseline",
        forbidden,
    )

    fixture[
        "identities"
    ] = module.InputIdentities(
        complete_universe=fixture[
            "identities"
        ].complete_universe,
        stage5a_content_manifest=fixture[
            "identities"
        ].stage5a_content_manifest,
        stage5a_execution_provenance=fixture[
            "identities"
        ].stage5a_execution_provenance,
        raw_source=fixture[
            "identities"
        ].raw_source,
        baseline_matrix="0" * 64,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="SHA256 mismatch",
    ):
        execute_fixture(
            fixture
        )

    assert called is False


def test_wrong_stage5a_universe_artifact_sha_fails_before_parsing(
    tmp_path,
    monkeypatch,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr(
        module,
        "_load_complete_universe",
        forbidden,
    )

    fixture[
        "identities"
    ] = module.InputIdentities(
        complete_universe="0" * 64,
        stage5a_content_manifest=fixture[
            "identities"
        ].stage5a_content_manifest,
        stage5a_execution_provenance=fixture[
            "identities"
        ].stage5a_execution_provenance,
        raw_source=fixture[
            "identities"
        ].raw_source,
        baseline_matrix=fixture[
            "identities"
        ].baseline_matrix,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="SHA256 mismatch",
    ):
        execute_fixture(
            fixture
        )

    assert called is False


def test_stage5a_universe_membership_mismatch_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    fixture[
        "stage5a_expectations"
    ] = module.Stage5AExpectations(
        complete_universe_count=4,
        complete_universe_species_count=4,
        complete_universe_membership_sha256="0" * 64,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="validation failed closed",
    ):
        execute_fixture(
            fixture
        )


def test_stage5a_universe_count_mismatch_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    fixture[
        "stage5a_expectations"
    ] = module.Stage5AExpectations(
        complete_universe_count=5,
        complete_universe_species_count=4,
        complete_universe_membership_sha256=fixture[
            "stage5a_expectations"
        ].complete_universe_membership_sha256,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="validation failed closed",
    ):
        execute_fixture(
            fixture
        )


def test_stage5a_universe_species_count_mismatch_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    fixture[
        "stage5a_expectations"
    ] = module.Stage5AExpectations(
        complete_universe_count=4,
        complete_universe_species_count=3,
        complete_universe_membership_sha256=fixture[
            "stage5a_expectations"
        ].complete_universe_membership_sha256,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="validation failed closed",
    ):
        execute_fixture(
            fixture
        )


def test_historical_aggregate_mismatch_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    fixture[
        "historical_expectations"
    ] = module.HistoricalExpectations(
        raw_records=6,
        metadata_retained=6,
        metadata_excluded=0,
        metadata_unresolved=0,
        baseline_accessions=4,
        retained_present_in_baseline=4,
        retained_absent_from_baseline=2,
        baseline_not_in_metadata_retained=0,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="reconstruction failed closed",
    ):
        execute_fixture(
            fixture
        )


def test_duplicate_metadata_accession_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    write_jsonl(
        fixture[
            "paths"
        ].raw_source,
        [
            valid_metadata_record(1),
            valid_metadata_record(1),
            valid_metadata_record(3),
            valid_metadata_record(4),
            valid_metadata_record(5),
            valid_metadata_record(6),
        ],
    )

    fixture[
        "identities"
    ] = module.InputIdentities(
        complete_universe=fixture[
            "identities"
        ].complete_universe,
        stage5a_content_manifest=fixture[
            "identities"
        ].stage5a_content_manifest,
        stage5a_execution_provenance=fixture[
            "identities"
        ].stage5a_execution_provenance,
        raw_source=module.sha256_file(
            fixture[
                "paths"
            ].raw_source
        ),
        baseline_matrix=fixture[
            "identities"
        ].baseline_matrix,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="metadata parsing failed closed",
    ):
        execute_fixture(
            fixture
        )


def test_duplicate_baseline_accession_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    write_tsv(
        fixture[
            "paths"
        ].baseline_matrix,
        (
            "batch",
            "canonical_genbank_assembly_accession",
            "feature",
        ),
        [
            {
                "batch":
                    "b",
                "canonical_genbank_assembly_accession":
                    accession(value),
                "feature":
                    "1",
            }
            for value in (
                1,
                2,
                2,
                99,
            )
        ],
    )

    fixture[
        "identities"
    ] = module.InputIdentities(
        complete_universe=fixture[
            "identities"
        ].complete_universe,
        stage5a_content_manifest=fixture[
            "identities"
        ].stage5a_content_manifest,
        stage5a_execution_provenance=fixture[
            "identities"
        ].stage5a_execution_provenance,
        raw_source=fixture[
            "identities"
        ].raw_source,
        baseline_matrix=module.sha256_file(
            fixture[
                "paths"
            ].baseline_matrix
        ),
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="baseline parsing failed closed",
    ):
        execute_fixture(
            fixture
        )


def test_duplicate_complete_universe_accession_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    rows = [
        {
            "canonical_genbank_assembly_accession":
                accession(2),
            "species_taxid":
                "10",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(2),
            "species_taxid":
                "20",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(6),
            "species_taxid":
                "30",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(8),
            "species_taxid":
                "40",
        },
    ]

    write_tsv(
        fixture[
            "paths"
        ].complete_universe,
        module.COMPLETE_UNIVERSE_FIELDS,
        rows,
    )

    fixture[
        "identities"
    ] = module.InputIdentities(
        complete_universe=module.sha256_file(
            fixture[
                "paths"
            ].complete_universe
        ),
        stage5a_content_manifest=fixture[
            "identities"
        ].stage5a_content_manifest,
        stage5a_execution_provenance=fixture[
            "identities"
        ].stage5a_execution_provenance,
        raw_source=fixture[
            "identities"
        ].raw_source,
        baseline_matrix=fixture[
            "identities"
        ].baseline_matrix,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="validation failed closed",
    ):
        execute_fixture(
            fixture
        )


def test_noncanonical_complete_universe_accession_fails_closed(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    rows = module.read_tsv_exact(
        fixture[
            "paths"
        ].complete_universe,
        module.COMPLETE_UNIVERSE_FIELDS,
        label="synthetic universe",
    )

    rows[0][
        "canonical_genbank_assembly_accession"
    ] = "GCF_000000002.1"

    write_tsv(
        fixture[
            "paths"
        ].complete_universe,
        module.COMPLETE_UNIVERSE_FIELDS,
        rows,
    )

    fixture[
        "identities"
    ] = module.InputIdentities(
        complete_universe=module.sha256_file(
            fixture[
                "paths"
            ].complete_universe
        ),
        stage5a_content_manifest=fixture[
            "identities"
        ].stage5a_content_manifest,
        stage5a_execution_provenance=fixture[
            "identities"
        ].stage5a_execution_provenance,
        raw_source=fixture[
            "identities"
        ].raw_source,
        baseline_matrix=fixture[
            "identities"
        ].baseline_matrix,
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="validation failed closed",
    ):
        execute_fixture(
            fixture
        )


def test_holdout_is_exact_intersection(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    rows = module.read_tsv_exact(
        final_dir
        / "external-decision-holdout.tsv",
        module.source_holdout.EXTERNAL_HOLDOUT_FIELDS,
        label="holdout",
    )

    assert {
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in rows
    } == {
        accession(4),
        accession(6),
    }


def test_holdout_preserves_stage5a_species_taxid(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    rows = module.read_tsv_exact(
        final_dir
        / "external-decision-holdout.tsv",
        module.source_holdout.EXTERNAL_HOLDOUT_FIELDS,
        label="holdout",
    )

    assert rows == [
        {
            "canonical_genbank_assembly_accession":
                accession(4),
            "species_taxid":
                "20",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(6),
            "species_taxid":
                "30",
        },
    ]


def test_holdout_performs_no_downsampling(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    summary = json.loads(
        (
            final_dir
            / "stage5b-aggregate-summary.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert summary[
        "external_holdout_count"
    ] == 2


def test_reconstructed_absence_rows_are_sorted(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    rows = module.read_tsv_exact(
        final_dir
        / "reconstructed-retained-absent-from-baseline.tsv",
        module.source_holdout.RECONSTRUCTED_ABSENCE_FIELDS,
        label="absence",
    )

    assert [
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in rows
    ] == [
        accession(4),
        accession(5),
        accession(6),
    ]


def test_holdout_rows_are_sorted(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    rows = module.read_tsv_exact(
        final_dir
        / "external-decision-holdout.tsv",
        module.source_holdout.EXTERNAL_HOLDOUT_FIELDS,
        label="holdout",
    )

    assert [
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in rows
    ] == [
        accession(4),
        accession(6),
    ]


def test_membership_fingerprints_match_frozen_primitive(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    summary = json.loads(
        (
            final_dir
            / "stage5b-aggregate-summary.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert summary[
        "reconstructed_absence_membership_sha256"
    ] == accession_membership_sha256(
        (
            accession(4),
            accession(5),
            accession(6),
        )
    )

    assert summary[
        "external_holdout_membership_sha256"
    ] == accession_membership_sha256(
        (
            accession(4),
            accession(6),
        )
    )


def test_adequacy_passes_at_exact_threshold():
    members = tuple(
        module.source_holdout.HoldoutMember(
            accession=accession(
                value
            ),
            species_taxid=(
                (
                    value - 1
                )
                % 200
            )
            + 1,
        )
        for value in range(
            1,
            1001,
        )
    )

    result = module.source_holdout.evaluate_adequacy(
        members
    )

    assert result.status == (
        module.source_holdout.ADEQUACY_PASS
    )


def test_adequacy_fails_below_genome_threshold():
    members = tuple(
        module.source_holdout.HoldoutMember(
            accession=accession(
                value
            ),
            species_taxid=(
                (
                    value - 1
                )
                % 200
            )
            + 1,
        )
        for value in range(
            1,
            1000,
        )
    )

    result = module.source_holdout.evaluate_adequacy(
        members
    )

    assert result.status == (
        module.source_holdout.ADEQUACY_FAIL
    )


def test_adequacy_fails_below_species_threshold():
    members = tuple(
        module.source_holdout.HoldoutMember(
            accession=accession(
                value
            ),
            species_taxid=(
                (
                    value - 1
                )
                % 199
            )
            + 1,
        )
        for value in range(
            1,
            1001,
        )
    )

    result = module.source_holdout.evaluate_adequacy(
        members
    )

    assert result.status == (
        module.source_holdout.ADEQUACY_FAIL
    )


def test_output_root_inside_repo_rejected(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="outside repository",
    ):
        module.execute_to_scratch(
            repo=fixture[
                "repo"
            ],
            expected_commit="1" * 40,
            expected_wrapper_sha256=sha(
                "wrapper"
            ),
            expected_wrapper_test_sha256=sha(
                "tests"
            ),
            output_root=(
                fixture[
                    "repo"
                ]
                / "output"
            ),
            input_paths=fixture[
                "paths"
            ],
            input_identities=fixture[
                "identities"
            ],
            stage5a_expectations=fixture[
                "stage5a_expectations"
            ],
            historical_expectations=fixture[
                "historical_expectations"
            ],
            frozen_repo_sha256={},
        )


def test_preexisting_final_directory_rejected(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final = (
        fixture[
            "output_root"
        ]
        / (
            "2"
            * 40
        )
    )

    final.mkdir(
        parents=True
    )

    with pytest.raises(
        module.Stage5BWrapperError,
        match="already exists",
    ):
        execute_fixture(
            fixture,
            commit="2" * 40,
        )


def test_content_manifest_contains_exactly_six_other_artifacts(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    rows = module.read_tsv_exact(
        final_dir
        / "stage5b-content-manifest.tsv",
        module.CONTENT_MANIFEST_FIELDS,
        label="content manifest",
    )

    assert len(
        rows
    ) == 6

    assert {
        row[
            "path"
        ]
        for row in rows
    } == {
        "stage5b-predecision-provenance.json",
        "reconstructed-retained-absent-from-baseline.tsv",
        "external-decision-holdout.tsv",
        "stage5b-input-evidence-manifest.tsv",
        "stage5b-execution-provenance.json",
        "stage5b-aggregate-summary.json",
    }


def test_content_manifest_excludes_itself(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    text = (
        final_dir
        / "stage5b-content-manifest.tsv"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "stage5b-content-manifest.tsv"
        not in text
    )


def test_stdout_contains_aggregate_and_fingerprints_only(
    tmp_path,
    capsys,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    execute_fixture(
        fixture
    )

    output = capsys.readouterr()

    assert "external_holdout_count=" in output.out
    assert "external_holdout_species_count=" in output.out
    assert "external_holdout_membership_sha256=" in output.out
    assert "adequacy_status=" in output.out


def test_stdout_and_stderr_contain_no_accession(
    tmp_path,
    capsys,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    execute_fixture(
        fixture
    )

    output = capsys.readouterr()

    assert "GCA_" not in output.out
    assert "GCA_" not in output.err
    assert "SAMN" not in output.out
    assert "SAMN" not in output.err


def test_predecision_false_states_are_exact(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    payload = json.loads(
        (
            final_dir
            / "stage5b-predecision-provenance.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    for field in (
        "complete_universe_rows_parsed",
        "raw_source_records_parsed",
        "baseline_matrix_rows_parsed",
        "historical_absence_membership_reconstructed",
        "holdout_membership_generated",
        "adequacy_gate_evaluated",
        "structural_features_calculated",
        "selector_outcomes_calculated",
    ):
        assert payload[
            field
        ] is False


def test_execution_provenance_records_only_stage5b_work(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    payload = json.loads(
        (
            final_dir
            / "stage5b-execution-provenance.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    for field in (
        "complete_universe_rows_parsed",
        "raw_source_records_parsed",
        "baseline_matrix_rows_parsed",
        "historical_absence_membership_reconstructed",
        "holdout_membership_generated",
        "adequacy_gate_evaluated",
    ):
        assert payload[
            field
        ] is True

    assert payload[
        "structural_features_calculated"
    ] is False

    assert payload[
        "selector_outcomes_calculated"
    ] is False


def test_partial_directory_removed_after_success(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    execute_fixture(
        fixture,
        commit="3" * 40,
    )

    assert not (
        fixture[
            "output_root"
        ]
        / (
            "."
            + "3" * 40
            + ".partial"
        )
    ).exists()


def test_input_manifest_records_fingerprints_without_parsing_rows(
    tmp_path,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    final_dir = execute_fixture(
        fixture
    )

    rows = module.read_tsv_exact(
        final_dir
        / "stage5b-input-evidence-manifest.tsv",
        module.INPUT_EVIDENCE_FIELDS,
        label="input manifest",
    )

    labels = {
        row[
            "label"
        ]
        for row in rows
    }

    assert "stage5a_complete_universe" in labels
    assert "historical_raw_source" in labels
    assert "baseline_matrix" in labels


def test_wrapper_imports_no_downstream_modules():
    source = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    imports = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imports.update(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module is not None:
                imports.add(
                    node.module
                )

    prohibited = (
        "structural_feature",
        "coverage",
        "selector",
        "distance",
    )

    for imported in imports:
        assert not any(
            token in imported
            for token in prohibited
        ), imported


def test_wrapper_contains_no_hardcoded_production_path():
    text = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    assert "/NGS/" not in text


def test_cli_requires_all_identity_bearing_input_locations():
    args = module.parse_args(
        [
            "--repo",
            "/tmp/repo",
            "--expected-commit",
            "a" * 40,
            "--expected-wrapper-sha256",
            "b" * 64,
            "--expected-wrapper-test-sha256",
            "c" * 64,
            "--stage5a-execution-dir",
            "/tmp/stage5a",
            "--raw-source",
            "/tmp/raw",
            "--baseline-matrix",
            "/tmp/baseline",
            "--output-root",
            "/tmp/output",
        ]
    )

    assert args.stage5a_execution_dir == Path(
        "/tmp/stage5a"
    )
    assert args.raw_source == Path(
        "/tmp/raw"
    )
    assert args.baseline_matrix == Path(
        "/tmp/baseline"
    )


def test_main_error_output_is_identity_safe(
    monkeypatch,
    capsys,
):
    def fail(*args, **kwargs):
        raise module.Stage5BWrapperError(
            "GCA_999999999.9 SAMN999999"
        )

    monkeypatch.setattr(
        module,
        "preflight_repository",
        fail,
    )

    observed = module.main(
        [
            "--repo",
            "/tmp/repo",
            "--expected-commit",
            "a" * 40,
            "--expected-wrapper-sha256",
            "b" * 64,
            "--expected-wrapper-test-sha256",
            "c" * 64,
            "--stage5a-execution-dir",
            "/tmp/stage5a",
            "--raw-source",
            "/tmp/raw",
            "--baseline-matrix",
            "/tmp/baseline",
            "--output-root",
            "/tmp/output",
        ]
    )

    assert observed == 1

    output = capsys.readouterr()

    assert "GCA_" not in output.err
    assert "SAMN" not in output.err
    assert (
        output.err.strip()
        == "ERROR | Stage 5B execution failed closed"
    )
