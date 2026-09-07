from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from bacselect import monthly_geometry
from bacselect.monthly_structural_features import (
    accession_membership_sha256,
)
from bacselect.tie import tie_key


PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "run_monthly_species_representatives.py"
)

SPEC = importlib.util.spec_from_file_location(
    "_monthly_species_representatives_test",
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


def sha(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def canonical(
    payload: dict,
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )


def synthetic_stage11(
    tmp_path: Path,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    stage = (
        stage1
        / module.STAGE11_STAGE_NAME
    )

    stage.mkdir(
        parents=True
    )

    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
        "GCA_000000003.1",
        "GCA_000000004.1",
    )

    species = (
        "10",
        "10",
        "10",
        "20",
    )

    base = np.asarray(
        [
            0.0,
            0.1,
            0.4,
            0.8,
        ],
        dtype=np.float64,
    )

    coordinates = np.column_stack(
        [
            base
            for _ in range(
                12
            )
        ]
    )

    build = (
        monthly_geometry
        .MonthlyGeometryBuild(
            rows=tuple(
                monthly_geometry
                .MonthlyGeometryRow(
                    accession=(
                        accessions[index]
                    ),
                    species_taxid=(
                        species[index]
                    ),
                    coordinates={
                        field:
                            float(
                                coordinates[
                                    index,
                                    column,
                                ]
                            )
                        for column, field
                        in enumerate(
                            monthly_geometry
                            .FEATURE_FIELDS
                        )
                    },
                )
                for index in range(
                    len(
                        accessions
                    )
                )
            ),
            species_count=2,
            membership_sha256=(
                accession_membership_sha256(
                    accessions
                )
            ),
            species_mapping_sha256=(
                monthly_geometry
                ._species_mapping_sha256(
                    accessions,
                    species,
                )
            ),
            raw_numeric_array_sha256=(
                "0" * 64
            ),
            percentile_numeric_array_sha256=(
                monthly_geometry
                ._numeric_array_sha256(
                    coordinates
                )
            ),
        )
    )

    matrix_payload = (
        monthly_geometry
        .serialize_monthly_geometry_matrix(
            build
        )
    )

    matrix_sha = sha(
        matrix_payload
    )

    membership_sha = (
        build.membership_sha256
    )

    species_mapping_sha = (
        build.species_mapping_sha256
    )

    percentile_array_sha = (
        build.percentile_numeric_array_sha256
    )

    execution_commit = (
        "a" * 40
    )

    record = {
        "status":
            "MONTHLY_SPECIES_BALANCED_PERCENTILE_GEOMETRY_COMPLETE",
        "release_id":
            "2026.09",
        "source_snapshot_id":
            "synthetic-snapshot",
        "execution_commit":
            execution_commit,
        "percentile_matrix_sha256":
            matrix_sha,
        "membership_sha256":
            membership_sha,
        "species_mapping_sha256":
            species_mapping_sha,
        "percentile_numeric_array_sha256":
            percentile_array_sha,
        "total_count":
            4,
        "species_count":
            2,
        "feature_count":
            12,
        "species_representatives_constructed":
            False,
        "ops_ladder_constructed":
            False,
        "selector_outcomes_calculated":
            False,
        "panels_generated":
            False,
        "coverage_generated":
            False,
    }

    record_payload = canonical(
        record
    )

    record_sha = sha(
        record_payload
    )

    completion = {
        "status":
            "MONTHLY_SPECIES_BALANCED_PERCENTILE_GEOMETRY_COMPLETE",
        "release_id":
            "2026.09",
        "source_snapshot_id":
            "synthetic-snapshot",
        "execution_commit":
            execution_commit,
        "percentile_matrix_sha256":
            matrix_sha,
        "record_sha256":
            record_sha,
        "membership_sha256":
            membership_sha,
        "species_mapping_sha256":
            species_mapping_sha,
        "percentile_numeric_array_sha256":
            percentile_array_sha,
        "total_count":
            4,
        "species_count":
            2,
        "feature_count":
            12,
    }

    completion_payload = canonical(
        completion
    )

    completion_sha = sha(
        completion_payload
    )

    (
        stage
        / module.STAGE11_MATRIX_NAME
    ).write_bytes(
        matrix_payload
    )

    (
        stage
        / module.STAGE11_RECORD_NAME
    ).write_bytes(
        record_payload
    )

    (
        stage1
        / module.STAGE11_COMPLETION_NAME
    ).write_bytes(
        completion_payload
    )

    expectations = (
        module.Stage11Expectations(
            release_id="2026.09",
            source_snapshot_id=(
                "synthetic-snapshot"
            ),
            execution_commit=(
                execution_commit
            ),
            matrix_sha256=(
                matrix_sha
            ),
            record_sha256=(
                record_sha
            ),
            completion_sha256=(
                completion_sha
            ),
            membership_sha256=(
                membership_sha
            ),
            species_mapping_sha256=(
                species_mapping_sha
            ),
            percentile_array_sha256=(
                percentile_array_sha
            ),
            total_count=4,
            species_count=2,
            feature_count=12,
        )
    )

    return (
        stage1,
        expectations,
        accessions,
        species,
        coordinates,
    )


def test_authenticates_synthetic_stage11(
    tmp_path,
):
    (
        stage1,
        expectations,
        accessions,
        species,
        coordinates,
    ) = synthetic_stage11(
        tmp_path
    )

    authority = (
        module.authenticate_stage11(
            stage1,
            expectations=expectations,
        )
    )

    assert (
        authority.accessions
        == accessions
    )

    assert (
        authority.species_ids
        == species
    )

    np.testing.assert_array_equal(
        authority.coordinates,
        coordinates,
    )


def test_stage11_matrix_hash_change_rejected(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage11(
        tmp_path
    )

    path = (
        stage1
        / module.STAGE11_STAGE_NAME
        / module.STAGE11_MATRIX_NAME
    )

    path.write_bytes(
        path.read_bytes()
        + b"x"
    )

    with pytest.raises(
        module.MonthlyRepresentativeError,
        match="Stage 11 matrix SHA256 changed",
    ):
        module.authenticate_stage11(
            stage1,
            expectations=expectations,
        )


def test_representative_is_nearest_species_centroid(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage11(
        tmp_path
    )

    authority = (
        module.authenticate_stage11(
            stage1,
            expectations=expectations,
        )
    )

    build = (
        module.build_representatives(
            authority
        )
    )

    selected = {
        row.species_taxid:
            row.accession
        for row in build.rows
    }

    assert (
        selected["10"]
        == "GCA_000000002.1"
    )

    assert (
        selected["20"]
        == "GCA_000000004.1"
    )


def test_exact_representative_tie_uses_frozen_hash():
    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
        "GCA_000000003.1",
    )

    species = (
        "10",
        "10",
        "20",
    )

    base = np.asarray(
        [
            0.0,
            1.0,
            0.5,
        ],
        dtype=np.float64,
    )

    coordinates = np.column_stack(
        [
            base
            for _ in range(
                12
            )
        ]
    )

    authority = (
        module.Stage11Authority(
            accessions=accessions,
            species_ids=species,
            coordinates=coordinates,
            matrix_sha256=(
                "1" * 64
            ),
            record_sha256=(
                "2" * 64
            ),
            completion_sha256=(
                "3" * 64
            ),
            membership_sha256=(
                accession_membership_sha256(
                    accessions
                )
            ),
            species_mapping_sha256=(
                monthly_geometry
                ._species_mapping_sha256(
                    accessions,
                    species,
                )
            ),
            percentile_array_sha256=(
                monthly_geometry
                ._numeric_array_sha256(
                    coordinates
                )
            ),
            species_count=2,
        )
    )

    build = (
        module.build_representatives(
            authority
        )
    )

    selected = {
        row.species_taxid:
            row.accession
        for row in build.rows
    }

    expected = min(
        accessions[
            :2
        ],
        key=tie_key,
    )

    assert (
        selected["10"]
        == expected
    )


def test_representatives_are_input_order_invariant(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage11(
        tmp_path
    )

    authority = (
        module.authenticate_stage11(
            stage1,
            expectations=expectations,
        )
    )

    baseline = (
        module.build_representatives(
            authority
        )
    )

    permutation = np.asarray(
        [
            3,
            1,
            0,
            2,
        ]
    )

    permuted = (
        module.Stage11Authority(
            accessions=tuple(
                authority.accessions[
                    int(index)
                ]
                for index
                in permutation
            ),
            species_ids=tuple(
                authority.species_ids[
                    int(index)
                ]
                for index
                in permutation
            ),
            coordinates=(
                authority.coordinates[
                    permutation
                ]
            ),
            matrix_sha256=(
                authority.matrix_sha256
            ),
            record_sha256=(
                authority.record_sha256
            ),
            completion_sha256=(
                authority.completion_sha256
            ),
            membership_sha256=(
                authority.membership_sha256
            ),
            species_mapping_sha256=(
                "4" * 64
            ),
            percentile_array_sha256=(
                authority.percentile_array_sha256
            ),
            species_count=(
                authority.species_count
            ),
        )
    )

    observed = (
        module.build_representatives(
            permuted
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
        observed.representative_sequence_sha256
        == baseline.representative_sequence_sha256
    )


def test_representative_sequence_fingerprint_uses_frozen_namespace(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage11(
        tmp_path
    )

    authority = (
        module.authenticate_stage11(
            stage1,
            expectations=expectations,
        )
    )

    build = (
        module.build_representatives(
            authority
        )
    )

    accessions = [
        row.accession
        for row in build.rows
    ]

    expected = hashlib.sha256(
        (
            "BacSelect-selector-v1|OPS|representatives"
            + "\n"
            + "\n".join(
                accessions
            )
            + "\n"
        ).encode(
            "utf-8"
        )
    ).hexdigest()

    assert (
        build.representative_sequence_sha256
        == expected
    )


def test_representative_table_roundtrips(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage11(
        tmp_path
    )

    authority = (
        module.authenticate_stage11(
            stage1,
            expectations=expectations,
        )
    )

    build = (
        module.build_representatives(
            authority
        )
    )

    payload = (
        module.serialize_representative_table(
            build
        )
    )

    module._validate_roundtrip(
        build,
        payload,
    )


def test_record_explicitly_stops_before_stage13(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage11(
        tmp_path
    )

    authority = (
        module.authenticate_stage11(
            stage1,
            expectations=expectations,
        )
    )

    build = (
        module.build_representatives(
            authority
        )
    )

    table_payload = (
        module.serialize_representative_table(
            build
        )
    )

    record = json.loads(
        module.build_execution_record(
            release_id="2026.09",
            source_snapshot_id=(
                "synthetic-snapshot"
            ),
            execution_commit=(
                "b" * 40
            ),
            stage11=authority,
            build=build,
            table_sha256=(
                sha(
                    table_payload
                )
            ),
        )
    )

    assert record[
        "selector_decision"
    ] == "OPS"

    assert (
        record[
            "incumbency_preference_used"
        ]
        is False
    )

    assert (
        record[
            "previous_panel_membership_used"
        ]
        is False
    )

    assert (
        record[
            "ops_ladder_constructed"
        ]
        is False
    )

    assert (
        record[
            "sr_executed"
        ]
        is False
    )

    assert (
        record[
            "ag_executed"
        ]
        is False
    )

    assert (
        record[
            "selector_resolution_rerun"
        ]
        is False
    )

    assert (
        record[
            "panels_generated"
        ]
        is False
    )

    assert (
        record[
            "coverage_generated"
        ]
        is False
    )


def test_completion_binds_table_and_record(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage11(
        tmp_path
    )

    authority = (
        module.authenticate_stage11(
            stage1,
            expectations=expectations,
        )
    )

    build = (
        module.build_representatives(
            authority
        )
    )

    table_payload = (
        module.serialize_representative_table(
            build
        )
    )

    table_sha = sha(
        table_payload
    )

    record_payload = (
        module.build_execution_record(
            release_id="2026.09",
            source_snapshot_id=(
                "synthetic-snapshot"
            ),
            execution_commit=(
                "b" * 40
            ),
            stage11=authority,
            build=build,
            table_sha256=(
                table_sha
            ),
        )
    )

    record_sha = sha(
        record_payload
    )

    completion = json.loads(
        module.build_completion_receipt(
            release_id="2026.09",
            source_snapshot_id=(
                "synthetic-snapshot"
            ),
            execution_commit=(
                "b" * 40
            ),
            stage11=authority,
            build=build,
            table_sha256=(
                table_sha
            ),
            record_sha256=(
                record_sha
            ),
        )
    )

    assert (
        completion[
            "representative_table_sha256"
        ]
        == table_sha
    )

    assert (
        completion[
            "record_sha256"
        ]
        == record_sha
    )


def test_atomic_stage_publication(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    stage1.mkdir()

    final = (
        module.publish_stage(
            stage1_root=stage1,
            table_payload=b"table\n",
            record_payload=b"record\n",
            stability_check=lambda: None,
        )
    )

    assert (
        final
        == stage1
        / module.STAGE_NAME
    )

    assert set(
        path.name
        for path in final.iterdir()
    ) == module.STAGE_FILES

    assert not (
        stage1
        / module.PARTIAL_NAME
    ).exists()


def test_stage_publication_refuses_existing(
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
        module.MonthlyRepresentativeError,
        match="already exists",
    ):
        module.publish_stage(
            stage1_root=stage1,
            table_payload=b"table\n",
            record_payload=b"record\n",
            stability_check=lambda: None,
        )


def test_atomic_completion_publication(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    stage1.mkdir()

    final = (
        module.publish_completion(
            stage1_root=stage1,
            payload=b"completion\n",
            stability_check=lambda: None,
        )
    )

    assert (
        final.read_bytes()
        == b"completion\n"
    )

    assert not (
        stage1
        / module.COMPLETION_TEMP_NAME
    ).exists()


def test_frozen_dependencies_match_repository():
    repo = (
        Path(__file__)
        .resolve()
        .parents[1]
    )

    observed = (
        module.verify_frozen_dependencies(
            repo
        )
    )

    assert observed == dict(
        sorted(
            module
            .FROZEN_REPO_FILES
            .items()
        )
    )

    decision = (
        module.verify_selector_decision(
            repo
        )
    )

    assert (
        decision[
            "decision"
        ]
        == "OPS"
    )


def test_production_sha_bindings_are_exact_and_canonical():
    expected = {
        "EXPECTED_STAGE11_MATRIX_SHA256":
            "cb3c8d14e8d0bd4982de4a92219a7a4bd307663bf22d9e4234690d34367f0935",
        "EXPECTED_STAGE11_RECORD_SHA256":
            "d7e231455a3208d8cf4a48bf105d6c608e766b42273795577a1daf2f900411be",
        "EXPECTED_STAGE11_COMPLETION_SHA256":
            "901508c9bf074e3d557c93d9636e8f2c3fee98f51ba78e3a5bc8a070dbc4ba87",
        "EXPECTED_MEMBERSHIP_SHA256":
            "6e6b44bd598bf472ea2a74686aaabcd23058832938279fb13a4d8ae6cdf7607d",
        "EXPECTED_SPECIES_MAPPING_SHA256":
            "103c0539c4e55863f43e756e64c3d9c30ab2c49ef205e12cc640bb53a92e68d8",
        "EXPECTED_PERCENTILE_ARRAY_SHA256":
            "da76cc78da56c06524923c1977bbc671d31f5149ea9f9f103b2fc52d051cfc78",
        "EXPECTED_OPS_SHA256":
            "eb6c1b8edab3e694b0f3825bb5ab0eaf44fdd95fdbb6a6e3e41439c18c828c0f",
        "EXPECTED_OPS_TEST_SHA256":
            "7eec19ebcfda97a3423b9c1c8b50ed220bcbd81f79f5f38ca865359269307f58",
        "EXPECTED_TIE_SHA256":
            "a5746d3d40e3d267398f80eb83ab2f4b1ee84808f3d9a7715dade7fc0824f73e",
        "EXPECTED_TIE_TEST_SHA256":
            "b08954d007af923eebd44c4ca4909f104d49e389069deb24398f6ec13f6af192",
        "EXPECTED_MONTHLY_GEOMETRY_SHA256":
            "ac8bbc94a2bacae8c8e80de1f5a9d65be886d59a2e72386ce82de8a5da23297e",
        "EXPECTED_ENVIRONMENT_LOCK_SHA256":
            "f6f4a19c44a759705682ba4199207eaef5c2435e1b6feeddc1e4654686bc2a8c",
        "EXPECTED_SELECTOR_DECISION_SHA256":
            "d0cf63ad4d933194e3e782912a2a2a3c617353758d2c87c1b1198681a75869e2",
    }

    for name, frozen in (
        expected.items()
    ):
        observed = getattr(
            module,
            name,
        )

        assert observed == frozen
        assert len(
            observed
        ) == 64

        assert all(
            character
            in "0123456789abcdef"
            for character in observed
        )


def test_wrapper_contains_no_later_stage_dispatch():
    text = PATH.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "ops_ladder(",
        "sr_ladder(",
        "ag_ladder(",
        "official_panels",
        "generate_panels(",
        "selector-resolution",
    )

    for token in forbidden:
        assert token not in text
