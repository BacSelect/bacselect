from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from bacselect.monthly_structural_features import (
    accession_membership_sha256,
)
from bacselect.ops import ops_ladder
from bacselect.tie import tie_key


PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "run_monthly_ops_ladder.py"
)

SPEC = importlib.util.spec_from_file_location(
    "_monthly_ops_ladder_test",
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
    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
        "GCA_000000003.1",
        "GCA_000000004.1",
        "GCA_000000005.1",
    )

    species = (
        "10",
        "20",
        "30",
        "40",
        "50",
    )

    base = np.asarray(
        [
            0.0,
            0.2,
            0.5,
            0.8,
            1.0,
        ],
        dtype=np.float64,
    )

    coordinates = np.column_stack(
        [
            base
            for _ in range(12)
        ]
    )

    stage11 = module.Stage11Authority(
        accessions=accessions,
        species_ids=species,
        coordinates=coordinates,
    )

    stage12 = module.Stage12Authority(
        species_ids=tuple(
            species[index]
            for index in (
                4,
                2,
                0,
                3,
                1,
            )
        ),
        accessions=tuple(
            accessions[index]
            for index in (
                4,
                2,
                0,
                3,
                1,
            )
        ),
    )

    return stage11, stage12


def test_complete_ladder_ranks_every_representative(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "EXPECTED_REPRESENTATIVE_COUNT",
        5,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_SPECIES_COUNT",
        5,
    )

    stage11, stage12 = (
        synthetic_authorities()
    )

    build = (
        module.build_complete_ops_ladder(
            stage11,
            stage12,
        )
    )

    assert len(
        build.rows
    ) == 5

    assert {
        row.accession
        for row in build.rows
    } == set(
        stage12.accessions
    )

    assert {
        row.species_taxid
        for row in build.rows
    } == set(
        stage12.species_ids
    )


def test_complete_ladder_matches_frozen_ops_semantics(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "EXPECTED_REPRESENTATIVE_COUNT",
        5,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_SPECIES_COUNT",
        5,
    )

    stage11, stage12 = (
        synthetic_authorities()
    )

    build = (
        module.build_complete_ops_ladder(
            stage11,
            stage12,
        )
    )

    observed = [
        row.accession
        for row in build.rows
    ]

    index_by_accession = {
        accession: index
        for index, accession
        in enumerate(
            stage11.accessions
        )
    }

    representative_indices = np.asarray(
        [
            index_by_accession[
                accession
            ]
            for accession
            in stage12.accessions
        ],
        dtype=np.int64,
    )

    direct_indices = ops_ladder(
        stage11.coordinates[
            representative_indices
        ],
        stage12.species_ids,
        stage12.accessions,
        max_n=5,
    )

    expected = [
        stage12.accessions[
            int(index)
        ]
        for index
        in direct_indices
    ]

    assert observed == expected


def test_complete_ladder_is_input_order_invariant(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "EXPECTED_REPRESENTATIVE_COUNT",
        5,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_SPECIES_COUNT",
        5,
    )

    stage11, stage12 = (
        synthetic_authorities()
    )

    baseline = (
        module.build_complete_ops_ladder(
            stage11,
            stage12,
        )
    )

    permutation = np.asarray(
        [
            3,
            0,
            4,
            1,
            2,
        ]
    )

    permuted11 = (
        module.Stage11Authority(
            accessions=tuple(
                stage11.accessions[
                    int(index)
                ]
                for index in permutation
            ),
            species_ids=tuple(
                stage11.species_ids[
                    int(index)
                ]
                for index in permutation
            ),
            coordinates=(
                stage11.coordinates[
                    permutation
                ]
            ),
        )
    )

    reverse = tuple(
        reversed(
            range(5)
        )
    )

    permuted12 = (
        module.Stage12Authority(
            species_ids=tuple(
                stage12.species_ids[
                    index
                ]
                for index in reverse
            ),
            accessions=tuple(
                stage12.accessions[
                    index
                ]
                for index in reverse
            ),
        )
    )

    observed = (
        module.build_complete_ops_ladder(
            permuted11,
            permuted12,
        )
    )

    assert [
        row.accession
        for row in observed.rows
    ] == [
        row.accession
        for row in baseline.rows
    ]

    assert (
        observed.complete_ladder_sha256
        == baseline.complete_ladder_sha256
    )


def test_stage12_species_mismatch_rejected(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "EXPECTED_REPRESENTATIVE_COUNT",
        5,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_SPECIES_COUNT",
        5,
    )

    stage11, stage12 = (
        synthetic_authorities()
    )

    broken = module.Stage12Authority(
        species_ids=(
            "999",
            *stage12.species_ids[1:],
        ),
        accessions=(
            stage12.accessions
        ),
    )

    with pytest.raises(
        module.MonthlyOpsLadderError,
        match="species differs",
    ):
        module.build_complete_ops_ladder(
            stage11,
            broken,
        )


def test_ladder_table_roundtrips(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "EXPECTED_REPRESENTATIVE_COUNT",
        5,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_SPECIES_COUNT",
        5,
    )

    stage11, stage12 = (
        synthetic_authorities()
    )

    build = (
        module.build_complete_ops_ladder(
            stage11,
            stage12,
        )
    )

    payload = (
        module.serialize_ladder_table(
            build
        )
    )

    module._validate_roundtrip(
        build,
        payload,
    )


def test_complete_namespace_uses_actual_ladder_length():
    assert (
        module.ladder_namespace(16223)
        == (
            "BacSelect-selector-v1|"
            "final300-2400|OPS|ladder|N=16223"
        )
    )

    assert (
        module.ladder_namespace(500)
        == (
            "BacSelect-selector-v1|"
            "final300-2400|OPS|ladder|N=500"
        )
    )


def test_stage13_record_explicitly_not_limited_to_500(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "EXPECTED_REPRESENTATIVE_COUNT",
        5,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_SPECIES_COUNT",
        5,
    )

    stage11, stage12 = (
        synthetic_authorities()
    )

    build = (
        module.build_complete_ops_ladder(
            stage11,
            stage12,
        )
    )

    payload = (
        module.build_execution_record(
            execution_commit=(
                "a" * 40
            ),
            stage12=stage12,
            build=build,
            table_sha256=(
                "b" * 64
            ),
        )
    )

    record = json.loads(
        payload
    )

    assert record[
        "ranking_limited_to_500"
    ] is False

    assert record[
        "all_species_representatives_ranked"
    ] is True

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
        "panels_generated"
    ] is False

    assert record[
        "coverage_generated"
    ] is False


def test_atomic_stage_publication(
    tmp_path,
):
    stage1 = tmp_path / "stage1"
    stage1.mkdir()

    result = module.publish_stage(
        stage1_root=stage1,
        table_payload=b"table\n",
        record_payload=b"record\n",
        stability_check=lambda: None,
    )

    assert (
        result
        == stage1
        / module.STAGE_NAME
    )

    assert not (
        stage1
        / module.PARTIAL_NAME
    ).exists()


def test_atomic_completion_publication(
    tmp_path,
):
    stage1 = tmp_path / "stage1"
    stage1.mkdir()

    result = (
        module.publish_completion(
            stage1_root=stage1,
            payload=b"completion\n",
            stability_check=lambda: None,
        )
    )

    assert (
        result.read_bytes()
        == b"completion\n"
    )

    assert not (
        stage1
        / module.COMPLETION_TEMP_NAME
    ).exists()


def test_production_sha_bindings_are_exact_and_canonical():
    names = (
        "EXPECTED_STAGE11_MATRIX_SHA256",
        "EXPECTED_STAGE11_RECORD_SHA256",
        "EXPECTED_STAGE11_COMPLETION_SHA256",
        "EXPECTED_STAGE11_MEMBERSHIP_SHA256",
        "EXPECTED_STAGE11_SPECIES_MAPPING_SHA256",
        "EXPECTED_STAGE11_PERCENTILE_ARRAY_SHA256",
        "EXPECTED_STAGE12_TABLE_SHA256",
        "EXPECTED_STAGE12_RECORD_SHA256",
        "EXPECTED_STAGE12_COMPLETION_SHA256",
        "EXPECTED_REPRESENTATIVE_SEQUENCE_SHA256",
        "EXPECTED_REPRESENTATIVE_MEMBERSHIP_SHA256",
        "EXPECTED_OPS_SHA256",
        "EXPECTED_OPS_TEST_SHA256",
        "EXPECTED_TIE_SHA256",
        "EXPECTED_TIE_TEST_SHA256",
        "EXPECTED_ENVIRONMENT_LOCK_SHA256",
        "EXPECTED_SELECTOR_DECISION_SHA256",
    )

    for name in names:
        observed = getattr(
            module,
            name,
        )

        assert len(observed) == 64

        assert all(
            character
            in "0123456789abcdef"
            for character in observed
        )


def test_wrapper_contains_no_panel_generation():
    text = PATH.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "official_panels",
        "generate_panels(",
        "coverage_summary(",
        "nearest_panel_distances(",
        "sr_ladder(",
        "ag_ladder(",
    )

    for token in forbidden:
        assert token not in text
