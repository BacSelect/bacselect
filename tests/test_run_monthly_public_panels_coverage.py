from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from bacselect.metrics import (
    coverage_summary,
    nearest_panel_distances,
)
from bacselect.official_panels import (
    MEMBERSHIP_MANIFEST_FILENAME,
    PANEL_FILENAMES,
    PANEL_SIZES,
)


PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "run_monthly_public_panels_coverage.py"
)

SPEC = importlib.util.spec_from_file_location(
    "_monthly_stage14_test",
    PATH,
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


def synthetic_authorities():
    count = 500

    accessions = tuple(
        f"GCA_{800000000 + index:09d}.1"
        for index
        in range(
            1,
            count + 1,
        )
    )

    species = tuple(
        str(
            10000 + index
        )
        for index
        in range(
            count
        )
    )

    x = np.linspace(
        0.0,
        1.0,
        count,
        dtype=np.float64,
    )

    coordinates = np.column_stack(
        (
            x,
            1.0 - x,
        )
    )

    stage11 = module.Stage11Authority(
        accessions=accessions,
        species_ids=species,
        coordinates=coordinates,
    )

    stage12 = module.Stage12Authority(
        species_ids=species,
        accessions=accessions,
    )

    order = tuple(
        reversed(
            range(
                count
            )
        )
    )

    stage13 = module.Stage13Authority(
        species_ids=tuple(
            species[
                index
            ]
            for index
            in order
        ),
        accessions=tuple(
            accessions[
                index
            ]
            for index
            in order
        ),
    )

    return (
        stage11,
        stage12,
        stage13,
    )


def relax_production_counts(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "EXPECTED_REPRESENTATIVE_COUNT",
        500,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_FEATURE_COUNT",
        2,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_PANEL_ACCESSION_LIST_SHA256",
        {
            panel_size:
                hashlib.sha256(
                    (
                        "\n".join(
                            synthetic_authorities()[
                                2
                            ].accessions[
                                :panel_size
                            ]
                        )
                        + "\n"
                    ).encode(
                        "ascii"
                    )
                ).hexdigest()
            for panel_size
            in PANEL_SIZES
        },
    )


def test_representative_geometry_is_exact_stage12_subset(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    (
        stage11,
        stage12,
        stage13,
    ) = synthetic_authorities()

    geometry = (
        module.build_representative_geometry(
            stage11,
            stage12,
            stage13,
        )
    )

    assert geometry.accessions == (
        stage12.accessions
    )

    assert geometry.species_ids == (
        stage12.species_ids
    )

    np.testing.assert_array_equal(
        geometry.coordinates,
        stage11.coordinates,
    )


def test_stage13_membership_change_is_refused(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    (
        stage11,
        stage12,
        stage13,
    ) = synthetic_authorities()

    broken = module.Stage13Authority(
        species_ids=stage13.species_ids,
        accessions=(
            "GCA_999999999.1",
            *stage13.accessions[
                1:
            ],
        ),
    )

    with pytest.raises(
        module.MonthlyPublicPanelsCoverageError,
        match="membership differs",
    ):
        module.build_representative_geometry(
            stage11,
            stage12,
            broken,
        )


def test_six_panels_are_exact_stage13_prefixes(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    stage13 = (
        synthetic_authorities()[
            2
        ]
    )

    payloads = (
        module.build_panel_payloads(
            stage13
        )
    )

    assert set(
        payloads
    ) == set(
        PANEL_SIZES
    )

    for panel_size in PANEL_SIZES:
        assert (
            payloads[
                panel_size
            ]
            .decode(
                "ascii"
            )
            .splitlines()
            == list(
                stage13.accessions[
                    :panel_size
                ]
            )
        )


def test_panel_membership_is_nested(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    stage13 = (
        synthetic_authorities()[
            2
        ]
    )

    payloads = (
        module.build_panel_payloads(
            stage13
        )
    )

    previous: set[str] = set()

    for panel_size in PANEL_SIZES:
        observed = set(
            payloads[
                panel_size
            ].decode(
                "ascii"
            ).splitlines()
        )

        assert previous <= observed

        previous = observed


def test_coverage_matches_frozen_metrics_directly(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    (
        stage11,
        stage12,
        stage13,
    ) = synthetic_authorities()

    geometry = (
        module.build_representative_geometry(
            stage11,
            stage12,
            stage13,
        )
    )

    (
        distances,
        summaries,
    ) = module.evaluate_structural_coverage(
        geometry,
        stage13,
    )

    local = {
        accession:
            index
        for index, accession
        in enumerate(
            geometry.accessions
        )
    }

    for panel_size in PANEL_SIZES:
        indices = [
            local[
                accession
            ]
            for accession
            in stage13.accessions[
                :panel_size
            ]
        ]

        direct_distances = (
            nearest_panel_distances(
                geometry.coordinates,
                indices,
            )
        )

        np.testing.assert_array_equal(
            distances[
                panel_size
            ],
            direct_distances,
        )

        assert summaries[
            panel_size
        ] == coverage_summary(
            direct_distances,
            geometry.species_ids,
        )


def test_panel_members_have_zero_distance(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    (
        stage11,
        stage12,
        stage13,
    ) = synthetic_authorities()

    geometry = (
        module.build_representative_geometry(
            stage11,
            stage12,
            stage13,
        )
    )

    distances, _ = (
        module.evaluate_structural_coverage(
            geometry,
            stage13,
        )
    )

    local = {
        accession:
            index
        for index, accession
        in enumerate(
            geometry.accessions
        )
    }

    for panel_size in PANEL_SIZES:
        indices = [
            local[
                accession
            ]
            for accession
            in stage13.accessions[
                :panel_size
            ]
        ]

        assert np.all(
            distances[
                panel_size
            ][
                indices
            ]
            == 0.0
        )


def test_coverage_summary_serialization_has_all_frozen_metrics(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    (
        stage11,
        stage12,
        stage13,
    ) = synthetic_authorities()

    geometry = (
        module.build_representative_geometry(
            stage11,
            stage12,
            stage13,
        )
    )

    _, summaries = (
        module.evaluate_structural_coverage(
            geometry,
            stage13,
        )
    )

    panel_payloads = (
        module.build_panel_payloads(
            stage13
        )
    )

    payload = (
        module.serialize_coverage_summary(
            summaries,
            panel_payloads,
        )
    )

    header = payload.decode(
        "ascii"
    ).splitlines()[
        0
    ].split("\t")

    assert header[
        :3
    ] == [
        "panel_size",
        "member_count",
        "accession_list_sha256",
    ]

    assert tuple(
        header[
            3:
        ]
    ) == module.METRIC_NAMES

    assert len(
        payload.decode(
            "ascii"
        ).splitlines()
    ) == 7


def test_distance_table_preserves_current_representative_population(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    (
        stage11,
        stage12,
        stage13,
    ) = synthetic_authorities()

    geometry = (
        module.build_representative_geometry(
            stage11,
            stage12,
            stage13,
        )
    )

    distances, _ = (
        module.evaluate_structural_coverage(
            geometry,
            stage13,
        )
    )

    payload = (
        module.serialize_coverage_distances(
            geometry,
            distances,
        )
    )

    lines = payload.decode(
        "ascii"
    ).splitlines()

    assert len(
        lines
    ) == 501

    assert lines[
        0
    ].split("\t") == [
        "species_taxid",
        "canonical_genbank_assembly_accession",
        "nearest_distance_n10",
        "nearest_distance_n20",
        "nearest_distance_n50",
        "nearest_distance_n100",
        "nearest_distance_n200",
        "nearest_distance_n500",
    ]

    assert [
        line.split("\t")[
            1
        ]
        for line in lines[
            1:
        ]
    ] == list(
        stage12.accessions
    )


def test_complete_stage14_artifact_inventory(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    build = module.build_stage14_artifacts(
        *synthetic_authorities()
    )

    assert set(
        build.artifacts
    ) == set(
        module.SCIENTIFIC_ARTIFACT_NAMES
    )

    for panel_size in PANEL_SIZES:
        assert PANEL_FILENAMES[
            panel_size
        ] in build.artifacts

    assert (
        MEMBERSHIP_MANIFEST_FILENAME
        in build.artifacts
    )

    assert (
        module.COVERAGE_SUMMARY_NAME
        in build.artifacts
    )

    assert (
        module.COVERAGE_DISTANCES_NAME
        in build.artifacts
    )


def test_record_explicitly_forbids_selector_rerun_and_percentage(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    build = module.build_stage14_artifacts(
        *synthetic_authorities()
    )

    payload = module.build_execution_record(
        execution_commit="a" * 40,
        build=build,
    )

    record = json.loads(
        payload
    )

    assert record[
        "panel_definition"
    ] == "complete_OPS_ladder[0:N]"

    assert record[
        "ops_rerun"
    ] is False

    assert record[
        "sr_executed"
    ] is False

    assert record[
        "ag_executed"
    ] is False

    assert record[
        "selector_resolution_rerun"
    ] is False

    assert record[
        "coverage_percentage_reported"
    ] is False

    assert record[
        "coverage_evaluation_population"
    ] == (
        "current_monthly_species_representatives"
    )

    assert record[
        "release_packaging_generated"
    ] is False


def test_record_reports_required_three_coverage_metrics(
    monkeypatch,
):
    relax_production_counts(
        monkeypatch
    )

    build = module.build_stage14_artifacts(
        *synthetic_authorities()
    )

    record = json.loads(
        module.build_execution_record(
            execution_commit="a" * 40,
            build=build,
        )
    )

    assert set(
        record[
            "required_coverage_metrics"
        ]
    ) == {
        str(
            value
        )
        for value in PANEL_SIZES
    }

    for values in record[
        "required_coverage_metrics"
    ].values():
        assert set(
            values
        ) == {
            "median_nearest_panel_distance",
            "p95_nearest_panel_distance",
            "maximum_nearest_panel_distance",
        }


def test_atomic_stage_publication(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    stage1.mkdir()

    artifacts = {
        name:
            (
                name
                + "\n"
            ).encode(
                "ascii"
            )
        for name
        in module.SCIENTIFIC_ARTIFACT_NAMES
    }

    result = module.publish_stage(
        stage1_root=stage1,
        artifacts=artifacts,
        record_payload=b"record\n",
        stability_check=lambda: None,
    )

    assert result == (
        stage1
        / module.STAGE_NAME
    )

    assert not (
        stage1
        / module.PARTIAL_NAME
    ).exists()

    assert {
        path.name
        for path in result.iterdir()
    } == module.STAGE_FILES


def test_atomic_completion_publication(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    stage1.mkdir()

    result = module.publish_completion(
        stage1_root=stage1,
        payload=b"completion\n",
        stability_check=lambda: None,
    )

    assert (
        result.read_bytes()
        == b"completion\n"
    )

    assert not (
        stage1
        / module.COMPLETION_TEMP_NAME
    ).exists()


def test_existing_stage_is_refused(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    stage1.mkdir()

    (
        stage1
        / module.STAGE_NAME
    ).mkdir()

    with pytest.raises(
        module.MonthlyPublicPanelsCoverageError,
        match="already exists",
    ):
        module.publish_stage(
            stage1_root=stage1,
            artifacts={
                name:
                    b"x\n"
                for name
                in module.SCIENTIFIC_ARTIFACT_NAMES
            },
            record_payload=b"record\n",
            stability_check=lambda: None,
        )


def test_production_sha_bindings_are_exact_and_canonical():
    single_names = (
        "EXPECTED_STAGE13_WRAPPER_SHA256",
        "EXPECTED_STAGE13_TABLE_SHA256",
        "EXPECTED_STAGE13_RECORD_SHA256",
        "EXPECTED_STAGE13_COMPLETION_SHA256",
        "EXPECTED_COMPLETE_LADDER_SHA256",
        "EXPECTED_REPRESENTATIVE_MEMBERSHIP_SHA256",
        "EXPECTED_N500_PREFIX_SHA256",
        "EXPECTED_METRICS_SHA256",
        "EXPECTED_METRICS_TEST_SHA256",
        "EXPECTED_OFFICIAL_PANELS_SHA256",
        "EXPECTED_OFFICIAL_PANELS_TEST_SHA256",
        "EXPECTED_FINAL_COVERAGE_COMMON_SHA256",
        "EXPECTED_ENVIRONMENT_LOCK_SHA256",
    )

    for name in single_names:
        observed = getattr(
            module,
            name,
        )

        assert len(
            observed
        ) == 64

        assert all(
            character
            in "0123456789abcdef"
            for character
            in observed
        )

    assert set(
        module.EXPECTED_PANEL_ACCESSION_LIST_SHA256
    ) == set(
        PANEL_SIZES
    )

    for observed in (
        module
        .EXPECTED_PANEL_ACCESSION_LIST_SHA256
        .values()
    ):
        assert len(
            observed
        ) == 64

        assert all(
            character
            in "0123456789abcdef"
            for character
            in observed
        )


def test_wrapper_does_not_rerun_selector():
    text = PATH.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "ops_ladder(",
        "sr_ladder(",
        "ag_ladder(",
        "build_final_ladders(",
        "selector_resolution_execution",
    )

    for token in forbidden:
        assert token not in text


def test_wrapper_does_not_use_historical_reference_artifact_builder():
    tree = ast.parse(
        PATH.read_text(
            encoding="utf-8"
        )
    )

    forbidden = {
        "build_reference_panel_artifacts",
        "serialize_generation_summary",
    }

    imported_names: set[str] = set()
    called_names: set[str] = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.ImportFrom,
        ):
            imported_names.update(
                alias.name
                for alias in node.names
            )

        if isinstance(
            node,
            ast.Call,
        ):
            function = node.func

            if isinstance(
                function,
                ast.Name,
            ):
                called_names.add(
                    function.id
                )

            elif isinstance(
                function,
                ast.Attribute,
            ):
                called_names.add(
                    function.attr
                )

    assert not (
        forbidden
        & imported_names
    )

    assert not (
        forbidden
        & called_names
    )
