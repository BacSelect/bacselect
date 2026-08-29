from __future__ import annotations

from collections import Counter
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from bacselect import source_chromosome_integrity
from bacselect.source_taxonomy_execution import (
    STAGE3_DECISION_FIELDS,
    accession_membership_sha256,
)


REPO = Path(
    __file__
).resolve().parents[1]

WRAPPER = (
    REPO
    / "validation/selector-v1/"
    "run_taxonomy_resolution_execution.py"
)


def load_wrapper():
    name = (
        "_bacselect_test_stage4_"
        "taxonomy_resolution_wrapper"
    )

    spec = importlib.util.spec_from_file_location(
        name,
        WRAPPER,
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


def sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write_tsv(
    path: Path,
    fields,
    rows,
):
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
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


def stage3_row(
    accession: str,
    *,
    status=source_chromosome_integrity.PASS,
    reason="NO_CHROMOSOME_INTEGRITY_TRIGGER",
    source_char="a",
):
    if status == source_chromosome_integrity.PASS:
        chromosome_count = "1"
        supported = "1"
        unsupported = "0"
        triggered = "0"
        reused = "0"

    else:
        chromosome_count = "2"
        supported = "1"
        unsupported = "1"
        triggered = "1"
        reused = "1"

    return {
        "canonical_genbank_assembly_accession":
            accession,
        "source_evidence_sha256":
            source_char * 64,
        "stage2_status":
            "CONTINUE",
        "chromosome_component_count":
            chromosome_count,
        "closure_supported_chromosome_count":
            supported,
        "closure_unsupported_chromosome_count":
            unsupported,
        "chromosome_integrity_triggered":
            triggered,
        "historical_adjudication_reused":
            reused,
        "stage3_status":
            status,
        "stage3_reason":
            reason,
    }


def write_raw(
    path: Path,
    records,
):
    path.write_text(
        "".join(
            json.dumps(
                row,
                sort_keys=True,
            )
            + "\n"
            for row in records
        ),
        encoding="utf-8",
    )


def raw_record(
    accession: str,
    taxid: int,
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
                999999999,
        },
    }


def write_taxonomy(
    root: Path,
):
    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    nodes = (
        "1\t|\t1\t|\tno rank\t|\n"
        "2\t|\t1\t|\tsuperkingdom\t|\n"
        "10\t|\t2\t|\tgenus\t|\n"
        "11\t|\t10\t|\tspecies\t|\n"
        "12\t|\t11\t|\tstrain\t|\n"
        "13\t|\t11\t|\tstrain\t|\n"
        "20\t|\t10\t|\tspecies\t|\n"
        "21\t|\t20\t|\tstrain\t|\n"
    )

    (root / "nodes.dmp").write_text(
        nodes,
        encoding="utf-8",
    )

    (root / "merged.dmp").write_text(
        "",
        encoding="utf-8",
    )

    (root / "delnodes.dmp").write_text(
        "",
        encoding="utf-8",
    )

    return {
        "nodes":
            sha256_file(
                root / "nodes.dmp"
            ),
        "merged":
            sha256_file(
                root / "merged.dmp"
            ),
        "delnodes":
            sha256_file(
                root / "delnodes.dmp"
            ),
    }


def synthetic_fixture(
    tmp_path: Path,
):
    module = load_wrapper()

    rows = (
        stage3_row(
            "GCA_000000001.1",
            source_char="1",
        ),
        stage3_row(
            "GCA_000000002.1",
            status=(
                source_chromosome_integrity.EXCLUDE
            ),
            reason=(
                "HISTORICAL_FRAGMENTED_CHROMOSOME_SET"
            ),
            source_char="2",
        ),
        stage3_row(
            "GCA_000000003.1",
            status=(
                source_chromosome_integrity.UNRESOLVED
            ),
            reason="HISTORICAL_UNRESOLVED",
            source_char="3",
        ),
        stage3_row(
            "GCA_000000004.1",
            source_char="4",
        ),
    )

    stage3_path = (
        tmp_path
        / "stage3-decisions.tsv"
    )

    write_tsv(
        stage3_path,
        STAGE3_DECISION_FIELDS,
        rows,
    )

    stage3_sha = sha256_file(
        stage3_path
    )

    status_counts = dict(
        Counter(
            row[
                "stage3_status"
            ]
            for row in rows
        )
    )

    reason_counts = dict(
        Counter(
            row[
                "stage3_reason"
            ]
            for row in rows
        )
    )

    stage3_completion = {
        "schema_version":
            1,
        "status":
            "STAGE3_CHROMOSOME_INTEGRITY_COMPLETE",
        "execution_git_commit":
            "1" * 40,
        "decision_row_count":
            4,
        "stage3_input_candidate_count":
            4,
        "pass_count":
            2,
        "status_counts":
            status_counts,
        "reason_counts":
            reason_counts,
        "artifacts_sha256": {
            "stage3-chromosome-integrity-decisions.tsv":
                stage3_sha,
        },
        "later_stage": {
            "chromosome_integrity_generated":
                True,
            "complete_universe_generated":
                False,
            "holdout_membership_generated":
                False,
            "selector_outcomes_calculated":
                False,
            "structural_features_calculated":
                False,
            "taxonomy_resolution_generated":
                False,
        },
    }

    stage3_completion_path = (
        tmp_path
        / "stage3-completion.json"
    )

    stage3_completion_path.write_text(
        json.dumps(
            stage3_completion,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    raw_source_path = (
        tmp_path
        / "raw-source.jsonl"
    )

    write_raw(
        raw_source_path,
        (
            raw_record(
                "GCA_000000001.1",
                12,
            ),
            raw_record(
                "GCA_000000002.1",
                13,
            ),
            raw_record(
                "GCA_000000003.1",
                21,
            ),
            raw_record(
                "GCA_000000004.1",
                21,
            ),
            raw_record(
                "GCA_000000005.1",
                20,
            ),
        ),
    )

    raw_sha = sha256_file(
        raw_source_path
    )

    taxonomy_root = (
        tmp_path
        / "taxonomy"
    )

    taxonomy_hashes = write_taxonomy(
        taxonomy_root
    )

    snapshot_record_path = (
        taxonomy_root
        / "taxonomy-snapshot-freeze.json"
    )

    snapshot_record_path.write_text(
        json.dumps(
            {
                "synthetic":
                    True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot_record_sha = sha256_file(
        snapshot_record_path
    )

    taxonomy_freeze = {
        "bound_source_snapshot_id":
            "synthetic-source-snapshot",
        "bound_source_raw_report_sha256":
            raw_sha,
        "taxonomy_snapshot_id":
            "synthetic-taxonomy-snapshot",
        "archive_sha256":
            "a" * 64,
        "nodes_sha256":
            taxonomy_hashes[
                "nodes"
            ],
        "merged_sha256":
            taxonomy_hashes[
                "merged"
            ],
        "delnodes_sha256":
            taxonomy_hashes[
                "delnodes"
            ],
        "taxonomy_snapshot_freeze_record_sha256":
            snapshot_record_sha,
    }

    taxonomy_freeze_path = (
        tmp_path
        / "taxonomy-acquisition-freeze.json"
    )

    taxonomy_freeze_path.write_text(
        json.dumps(
            taxonomy_freeze,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "module":
            module,
        "rows":
            rows,
        "stage3_path":
            stage3_path,
        "stage3_sha":
            stage3_sha,
        "stage3_completion":
            stage3_completion,
        "stage3_completion_path":
            stage3_completion_path,
        "raw_source_path":
            raw_source_path,
        "raw_sha":
            raw_sha,
        "taxonomy_root":
            taxonomy_root,
        "taxonomy_freeze":
            taxonomy_freeze,
        "taxonomy_freeze_path":
            taxonomy_freeze_path,
    }


def test_import_is_side_effect_free():
    module = load_wrapper()

    assert module.EXPECTED_STAGE4_TOTAL == 68175
    assert module.EXPECTED_RAW_SOURCE_RECORDS == 70850


def test_frozen_pre_wrapper_repo_identities_are_exact():
    module = load_wrapper()

    observed = module.verify_frozen_repo_files(
        REPO
    )

    assert observed[
        str(
            module.STAGE4_METHOD_RELATIVE
        )
    ] == module.EXPECTED_STAGE4_METHOD_SHA256

    assert observed[
        str(
            module.STAGE4_EXECUTION_RELATIVE
        )
    ] == module.EXPECTED_STAGE4_EXECUTION_SHA256


def test_real_blinded_stage3_completion_checkpoint_loads():
    module = load_wrapper()

    payload = module.load_stage3_completion(
        REPO
        / module.STAGE3_COMPLETION_RELATIVE
    )

    assert payload[
        "pass_count"
    ] == 68175

    assert payload[
        "artifacts_sha256"
    ][
        "stage3-chromosome-integrity-decisions.tsv"
    ] == module.EXPECTED_STAGE3_DECISIONS_SHA256


def test_real_taxonomy_acquisition_freeze_loads_without_snapshot():
    module = load_wrapper()

    payload = module.load_taxonomy_freeze(
        REPO
        / module.TAXONOMY_ACQUISITION_FREEZE_RELATIVE
    )

    assert payload[
        "taxonomy_snapshot_id"
    ] == module.EXPECTED_TAXONOMY_SNAPSHOT_ID

    assert payload[
        "candidate_taxids_read"
    ] is False


def test_stage3_completion_loader_rejects_wrong_hash(
    tmp_path,
):
    module = load_wrapper()

    path = (
        tmp_path
        / "completion.json"
    )

    path.write_text(
        "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        module.Stage4WrapperError,
        match="SHA256 mismatch",
    ):
        module.load_stage3_completion(
            path,
            expected_sha256="0" * 64,
        )


def test_taxonomy_freeze_loader_rejects_changed_boundary(
    tmp_path,
):
    module = load_wrapper()

    source = json.loads(
        (
            REPO
            / module.TAXONOMY_ACQUISITION_FREEZE_RELATIVE
        ).read_text(
            encoding="utf-8"
        )
    )

    source[
        "taxonomy_resolution_performed"
    ] = True

    path = (
        tmp_path
        / "freeze.json"
    )

    path.write_text(
        json.dumps(
            source,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        module.Stage4WrapperError,
        match="taxonomy acquisition freeze mismatch",
    ):
        module.load_taxonomy_freeze(
            path,
            expected_sha256=(
                sha256_file(
                    path
                )
            ),
        )


def test_output_root_inside_repository_fails_closed():
    module = load_wrapper()

    with pytest.raises(
        module.Stage4WrapperError,
        match="outside the repository",
    ):
        module._ensure_output_root_outside_repo(
            REPO
            / "synthetic-stage4-output",
            REPO,
        )


def test_predecision_precedes_candidate_taxids_and_taxonomy_parse(
    tmp_path,
    monkeypatch,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    module = fixture[
        "module"
    ]

    output_root = (
        tmp_path
        / "outside"
    )

    expected_commit = "2" * 40

    wrapper_sha = sha256_file(
        WRAPPER
    )

    wrapper_test_sha = sha256_file(
        Path(
            __file__
        )
    )

    observed = {
        "source_checked":
            False,
        "taxonomy_checked":
            False,
    }

    original_source_loader = (
        module.load_source_taxids
    )

    original_taxonomy = (
        module.Taxonomy
    )

    def checked_source_loader(
        *args,
        **kwargs,
    ):
        predecision = (
            output_root
            / (
                expected_commit
                + ".partial"
            )
            / "stage4-predecision-provenance.json"
        )

        assert predecision.is_file()

        payload = json.loads(
            predecision.read_text(
                encoding="utf-8"
            )
        )

        assert payload[
            "candidate_taxids_read"
        ] is False

        assert payload[
            "taxonomy_resolution_generated"
        ] is False

        assert payload[
            "complete_eligible_universe_generated"
        ] is False

        observed[
            "source_checked"
        ] = True

        return original_source_loader(
            *args,
            **kwargs,
        )

    class CheckedTaxonomy:
        def __new__(
            cls,
            *args,
            **kwargs,
        ):
            predecision = (
                output_root
                / (
                    expected_commit
                    + ".partial"
                )
                / "stage4-predecision-provenance.json"
            )

            assert predecision.is_file()

            observed[
                "taxonomy_checked"
            ] = True

            return original_taxonomy(
                *args,
                **kwargs,
            )

    monkeypatch.setattr(
        module,
        "load_source_taxids",
        checked_source_loader,
    )

    monkeypatch.setattr(
        module,
        "Taxonomy",
        CheckedTaxonomy,
    )

    final_dir = module.execute_to_scratch(
        repo=REPO,
        expected_commit=expected_commit,
        expected_wrapper_sha256=wrapper_sha,
        expected_wrapper_test_sha256=wrapper_test_sha,
        output_root=output_root,
        stage3_completion_path=(
            fixture[
                "stage3_completion_path"
            ]
        ),
        stage3_completion=(
            fixture[
                "stage3_completion"
            ]
        ),
        stage3_decisions_path=(
            fixture[
                "stage3_path"
            ]
        ),
        raw_source_path=(
            fixture[
                "raw_source_path"
            ]
        ),
        taxonomy_acquisition_freeze_path=(
            fixture[
                "taxonomy_freeze_path"
            ]
        ),
        taxonomy_freeze=(
            fixture[
                "taxonomy_freeze"
            ]
        ),
        taxonomy_root=(
            fixture[
                "taxonomy_root"
            ]
        ),
        frozen_repo_sha256={},
        expected_stage3_decisions_sha256=(
            fixture[
                "stage3_sha"
            ]
        ),
        expected_stage3_total=4,
        expected_stage4_total=2,
        expected_raw_source_records=5,
    )

    assert observed[
        "source_checked"
    ]

    assert observed[
        "taxonomy_checked"
    ]

    assert final_dir.is_dir()


def test_end_to_end_synthetic_finalization_and_blinding(
    tmp_path,
    capsys,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    module = fixture[
        "module"
    ]

    output_root = (
        tmp_path
        / "outside"
    )

    expected_commit = "3" * 40

    final_dir = module.execute_to_scratch(
        repo=REPO,
        expected_commit=expected_commit,
        expected_wrapper_sha256=(
            sha256_file(
                WRAPPER
            )
        ),
        expected_wrapper_test_sha256=(
            sha256_file(
                Path(
                    __file__
                )
            )
        ),
        output_root=output_root,
        stage3_completion_path=(
            fixture[
                "stage3_completion_path"
            ]
        ),
        stage3_completion=(
            fixture[
                "stage3_completion"
            ]
        ),
        stage3_decisions_path=(
            fixture[
                "stage3_path"
            ]
        ),
        raw_source_path=(
            fixture[
                "raw_source_path"
            ]
        ),
        taxonomy_acquisition_freeze_path=(
            fixture[
                "taxonomy_freeze_path"
            ]
        ),
        taxonomy_freeze=(
            fixture[
                "taxonomy_freeze"
            ]
        ),
        taxonomy_root=(
            fixture[
                "taxonomy_root"
            ]
        ),
        frozen_repo_sha256={
            "synthetic":
                "f" * 64,
        },
        expected_stage3_decisions_sha256=(
            fixture[
                "stage3_sha"
            ]
        ),
        expected_stage3_total=4,
        expected_stage4_total=2,
        expected_raw_source_records=5,
    )

    assert final_dir == (
        output_root
        / expected_commit
    )

    assert not (
        output_root
        / (
            expected_commit
            + ".partial"
        )
    ).exists()

    expected_names = {
        "stage4-input-evidence-manifest.tsv",
        "stage4-predecision-provenance.json",
        "stage4-taxonomy-decisions.tsv",
        "stage4-execution-provenance.json",
        "stage4-aggregate-summary.json",
        "stage4-content-manifest.tsv",
    }

    assert {
        path.name
        for path in final_dir.iterdir()
    } == expected_names

    decisions = (
        final_dir
        / "stage4-taxonomy-decisions.tsv"
    ).read_text(
        encoding="utf-8"
    )

    assert "GCA_000000001.1" in decisions
    assert "GCA_000000004.1" in decisions
    assert "GCA_000000002.1" not in decisions
    assert "GCA_000000003.1" not in decisions

    summary = json.loads(
        (
            final_dir
            / "stage4-aggregate-summary.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert summary[
        "decision_count"
    ] == 2

    assert sum(
        summary[
            "status_counts"
        ].values()
    ) == 2

    assert summary[
        "unique_frozen_organism_taxid_count"
    ] == 2

    assert summary[
        "resolved_distinct_species_taxid_count"
    ] == 2

    assert summary[
        "taxonomy_resolution_generated"
    ] is True

    assert summary[
        "complete_eligible_universe_generated"
    ] is False

    summary_text = json.dumps(
        summary,
        sort_keys=True,
    )

    for identity in (
        "GCA_000000001.1",
        "GCA_000000004.1",
        "987654321",
        "7654321",
    ):
        assert identity not in summary_text

    provenance = json.loads(
        (
            final_dir
            / "stage4-execution-provenance.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert provenance[
        "taxonomy_resolution_generated"
    ] is True

    assert provenance[
        "holdout_membership_generated"
    ] is False

    assert provenance[
        "structural_features_calculated"
    ] is False

    assert provenance[
        "selector_outcomes_calculated"
    ] is False

    content_manifest = (
        final_dir
        / "stage4-content-manifest.tsv"
    ).read_text(
        encoding="utf-8"
    )

    for name in (
        "stage4-taxonomy-decisions.tsv",
        "stage4-input-evidence-manifest.tsv",
        "stage4-predecision-provenance.json",
        "stage4-execution-provenance.json",
        "stage4-aggregate-summary.json",
    ):
        assert name in content_manifest

    captured = capsys.readouterr()

    assert "GCA_" not in captured.out
    assert "GCA_" not in captured.err


def test_failed_resolution_preserves_partial_predecision(
    tmp_path,
    monkeypatch,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    module = fixture[
        "module"
    ]

    output_root = (
        tmp_path
        / "outside"
    )

    expected_commit = "4" * 40

    def fail_resolution(
        *args,
        **kwargs,
    ):
        raise module.Stage4WrapperError(
            "synthetic failure"
        )

    monkeypatch.setattr(
        module,
        "evaluate_taxonomy_population",
        fail_resolution,
    )

    with pytest.raises(
        module.Stage4WrapperError,
        match="synthetic failure",
    ):
        module.execute_to_scratch(
            repo=REPO,
            expected_commit=expected_commit,
            expected_wrapper_sha256=(
                sha256_file(
                    WRAPPER
                )
            ),
            expected_wrapper_test_sha256=(
                sha256_file(
                    Path(
                        __file__
                    )
                )
            ),
            output_root=output_root,
            stage3_completion_path=(
                fixture[
                    "stage3_completion_path"
                ]
            ),
            stage3_completion=(
                fixture[
                    "stage3_completion"
                ]
            ),
            stage3_decisions_path=(
                fixture[
                    "stage3_path"
                ]
            ),
            raw_source_path=(
                fixture[
                    "raw_source_path"
                ]
            ),
            taxonomy_acquisition_freeze_path=(
                fixture[
                    "taxonomy_freeze_path"
                ]
            ),
            taxonomy_freeze=(
                fixture[
                    "taxonomy_freeze"
                ]
            ),
            taxonomy_root=(
                fixture[
                    "taxonomy_root"
                ]
            ),
            frozen_repo_sha256={},
            expected_stage3_decisions_sha256=(
                fixture[
                    "stage3_sha"
                ]
            ),
            expected_stage3_total=4,
            expected_stage4_total=2,
            expected_raw_source_records=5,
        )

    partial = (
        output_root
        / (
            expected_commit
            + ".partial"
        )
    )

    assert partial.is_dir()

    assert (
        partial
        / "stage4-predecision-provenance.json"
    ).is_file()

    assert not (
        output_root
        / expected_commit
    ).exists()

    assert not (
        partial
        / "stage4-taxonomy-decisions.tsv"
    ).exists()


@pytest.mark.parametrize(
    "existing_kind",
    [
        "final",
        "partial",
    ],
)
def test_atomic_finalization_rejects_existing_output_state(
    tmp_path,
    existing_kind,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    module = fixture[
        "module"
    ]

    output_root = (
        tmp_path
        / "outside"
    )

    output_root.mkdir()

    expected_commit = "5" * 40

    if existing_kind == "final":
        existing = (
            output_root
            / expected_commit
        )
    else:
        existing = (
            output_root
            / (
                expected_commit
                + ".partial"
            )
        )

    existing.mkdir()

    expected_message = (
        "final Stage 4 output directory already exists"
        if existing_kind == "final"
        else
        "partial Stage 4 output directory already exists"
    )

    with pytest.raises(
        module.Stage4WrapperError,
        match=expected_message,
    ):
        module.execute_to_scratch(
            repo=REPO,
            expected_commit=expected_commit,
            expected_wrapper_sha256=(
                sha256_file(
                    WRAPPER
                )
            ),
            expected_wrapper_test_sha256=(
                sha256_file(
                    Path(
                        __file__
                    )
                )
            ),
            output_root=output_root,
            stage3_completion_path=(
                fixture[
                    "stage3_completion_path"
                ]
            ),
            stage3_completion=(
                fixture[
                    "stage3_completion"
                ]
            ),
            stage3_decisions_path=(
                fixture[
                    "stage3_path"
                ]
            ),
            raw_source_path=(
                fixture[
                    "raw_source_path"
                ]
            ),
            taxonomy_acquisition_freeze_path=(
                fixture[
                    "taxonomy_freeze_path"
                ]
            ),
            taxonomy_freeze=(
                fixture[
                    "taxonomy_freeze"
                ]
            ),
            taxonomy_root=(
                fixture[
                    "taxonomy_root"
                ]
            ),
            frozen_repo_sha256={},
            expected_stage3_decisions_sha256=(
                fixture[
                    "stage3_sha"
                ]
            ),
            expected_stage3_total=4,
            expected_stage4_total=2,
            expected_raw_source_records=5,
        )


def test_source_sha_mismatch_fails_before_candidate_resolution(
    tmp_path,
    monkeypatch,
):
    fixture = synthetic_fixture(
        tmp_path
    )

    module = fixture[
        "module"
    ]

    fixture[
        "taxonomy_freeze"
    ][
        "bound_source_raw_report_sha256"
    ] = "0" * 64

    called = {
        "value":
            False,
    }

    def poison(
        *args,
        **kwargs,
    ):
        called[
            "value"
        ] = True
        raise AssertionError(
            "candidate resolution must not begin"
        )

    monkeypatch.setattr(
        module,
        "load_source_taxids",
        poison,
    )

    with pytest.raises(
        module.Stage4WrapperError,
        match="SHA256 mismatch",
    ):
        module.execute_to_scratch(
            repo=REPO,
            expected_commit="6" * 40,
            expected_wrapper_sha256=(
                sha256_file(
                    WRAPPER
                )
            ),
            expected_wrapper_test_sha256=(
                sha256_file(
                    Path(
                        __file__
                    )
                )
            ),
            output_root=(
                tmp_path
                / "outside"
            ),
            stage3_completion_path=(
                fixture[
                    "stage3_completion_path"
                ]
            ),
            stage3_completion=(
                fixture[
                    "stage3_completion"
                ]
            ),
            stage3_decisions_path=(
                fixture[
                    "stage3_path"
                ]
            ),
            raw_source_path=(
                fixture[
                    "raw_source_path"
                ]
            ),
            taxonomy_acquisition_freeze_path=(
                fixture[
                    "taxonomy_freeze_path"
                ]
            ),
            taxonomy_freeze=(
                fixture[
                    "taxonomy_freeze"
                ]
            ),
            taxonomy_root=(
                fixture[
                    "taxonomy_root"
                ]
            ),
            frozen_repo_sha256={},
            expected_stage3_decisions_sha256=(
                fixture[
                    "stage3_sha"
                ]
            ),
            expected_stage3_total=4,
            expected_stage4_total=2,
            expected_raw_source_records=5,
        )

    assert called[
        "value"
    ] is False


def test_wrapper_contains_no_later_stage_runtime_dependencies():
    source = WRAPPER.read_text(
        encoding="utf-8"
    ).lower()

    prohibited = (
        "from bacselect.source_membership import",
        "import bacselect.source_membership",
        "validate_ops",
        "validate_sr",
        "compare_ops_sr",
        "build_300_2400_feature_space",
        "import requests",
        "import httpx",
        "import aiohttp",
    )

    for token in prohibited:
        assert token not in source


def test_main_hides_internal_error_details(
    monkeypatch,
    capsys,
):
    module = load_wrapper()

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda argv=None:
            type(
                "Args",
                (),
                {
                    "repo":
                        REPO,
                    "expected_commit":
                        "7" * 40,
                    "expected_wrapper_sha256":
                        "a" * 64,
                    "expected_wrapper_test_sha256":
                        "b" * 64,
                    "stage3_decisions":
                        Path(
                            "/synthetic/stage3"
                        ),
                    "raw_source":
                        Path(
                            "/synthetic/raw"
                        ),
                    "taxonomy_root":
                        Path(
                            "/synthetic/taxonomy"
                        ),
                    "output_root":
                        Path(
                            "/synthetic/output"
                        ),
                },
            )(),
    )

    monkeypatch.setattr(
        module,
        "verify_repo_state",
        lambda *args, **kwargs:
            (_ for _ in ()).throw(
                RuntimeError(
                    "GCA_999999999.9 taxid 987654321"
                )
            ),
    )

    assert module.main([]) == 1

    captured = capsys.readouterr()

    assert (
        captured.err
        == "ERROR | Stage 4 taxonomy execution failed closed\n"
    )

    assert "GCA_" not in captured.err
    assert "987654321" not in captured.err


def test_synthetic_tests_contain_no_production_data_paths():
    source = Path(
        __file__
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        (
            "/NGS/scratch/EXT/",
            "Rhys_wkdir/",
        ),
        (
            "13d66c0febb809d30",
            "862d30eff0b419c",
        ),
        (
            "b1b016891ae4e976",
            "d03606dfb2f35f74",
        ),
    )

    for parts in forbidden:
        assert "".join(
            parts
        ) not in source
