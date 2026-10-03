from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from bacselect import monthly_geometry
from bacselect.monthly_structural_features import (
    FEATURE_FIELDS,
    accession_membership_sha256,
)


PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "run_monthly_geometry.py"
)

SPEC = importlib.util.spec_from_file_location(
    "_monthly_geometry_wrapper_test",
    PATH,
)

assert SPEC is not None
assert SPEC.loader is not None

module = importlib.util.module_from_spec(
    SPEC
)

sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def sha(payload: bytes) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def canonical(payload: dict) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def synthetic_stage10(
    tmp_path: Path,
):
    stage1 = tmp_path / "stage1"
    stage = (
        stage1
        / module.STAGE10_STAGE_NAME
    )

    stage.mkdir(
        parents=True
    )

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

    raw = np.asarray(
        [
            [
                1.0 + column
                for column in range(
                    len(
                        FEATURE_FIELDS
                    )
                )
            ],
            [
                3.0 + column
                for column in range(
                    len(
                        FEATURE_FIELDS
                    )
                )
            ],
            [
                9.0 + column
                for column in range(
                    len(
                        FEATURE_FIELDS
                    )
                )
            ],
        ],
        dtype=np.float64,
    )

    output = io.StringIO(
        newline=""
    )

    writer = csv.writer(
        output,
        delimiter="\t",
        lineterminator="\n",
    )

    writer.writerow(
        monthly_geometry.MATRIX_FIELDS
    )

    for index in range(
        len(
            accessions
        )
    ):
        writer.writerow(
            (
                accessions[index],
                species[index],
                *(
                    format(
                        value,
                        ".17g",
                    )
                    for value in raw[
                        index
                    ]
                ),
            )
        )

    matrix_payload = (
        output.getvalue()
        .encode("ascii")
    )

    matrix_sha = sha(
        matrix_payload
    )

    provenance_payload = (
        b"synthetic-stage10-provenance\n"
    )

    provenance_sha = sha(
        provenance_payload
    )

    membership_sha = (
        accession_membership_sha256(
            accessions
        )
    )

    raw_numeric_sha = (
        monthly_geometry
        ._numeric_array_sha256(
            raw
        )
    )

    execution_commit = (
        "a" * 40
    )

    record = {
        "status":
            "MONTHLY_RAW_STRUCTURAL_FEATURES_COMPLETE",
        "release_id":
            "2026.09",
        "source_snapshot_id":
            "synthetic-snapshot",
        "execution_commit":
            execution_commit,
        "matrix_sha256":
            matrix_sha,
        "provenance_sha256":
            provenance_sha,
        "membership_sha256":
            membership_sha,
        "numeric_array_sha256":
            raw_numeric_sha,
        "total_count":
            3,
        "percentile_coordinates_calculated":
            False,
        "selector_outcomes_calculated":
            False,
        "nested_panels_calculated":
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
            "MONTHLY_RAW_STRUCTURAL_FEATURES_COMPLETE",
        "release_id":
            "2026.09",
        "source_snapshot_id":
            "synthetic-snapshot",
        "execution_commit":
            execution_commit,
        "matrix_sha256":
            matrix_sha,
        "provenance_sha256":
            provenance_sha,
        "record_sha256":
            record_sha,
        "membership_sha256":
            membership_sha,
        "numeric_array_sha256":
            raw_numeric_sha,
        "total_count":
            3,
    }

    completion_payload = canonical(
        completion
    )

    completion_sha = sha(
        completion_payload
    )

    (
        stage
        / module.STAGE10_MATRIX_NAME
    ).write_bytes(
        matrix_payload
    )

    (
        stage
        / module.STAGE10_PROVENANCE_NAME
    ).write_bytes(
        provenance_payload
    )

    (
        stage
        / module.STAGE10_RECORD_NAME
    ).write_bytes(
        record_payload
    )

    (
        stage1
        / module.STAGE10_COMPLETION_NAME
    ).write_bytes(
        completion_payload
    )

    expectations = (
        module.Stage10Expectations(
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
            provenance_sha256=(
                provenance_sha
            ),
            record_sha256=(
                record_sha
            ),
            completion_sha256=(
                completion_sha
            ),
            raw_numeric_array_sha256=(
                raw_numeric_sha
            ),
            membership_sha256=(
                membership_sha
            ),
            total_count=3,
            species_count=2,
        )
    )

    return (
        stage1,
        expectations,
        accessions,
        species,
        raw,
    )


def test_authenticates_synthetic_stage10(
    tmp_path,
):
    (
        stage1,
        expectations,
        accessions,
        species,
        raw,
    ) = synthetic_stage10(
        tmp_path
    )

    authority = (
        module.authenticate_stage10(
            stage1,
            expectations=expectations,
        )
    )

    assert authority.accessions == accessions
    assert authority.species_ids == species

    np.testing.assert_array_equal(
        authority.raw,
        raw,
    )

    assert authority.species_count == 2


def test_stage10_matrix_hash_change_rejected(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage10(
        tmp_path
    )

    path = (
        stage1
        / module.STAGE10_STAGE_NAME
        / module.STAGE10_MATRIX_NAME
    )

    path.write_bytes(
        path.read_bytes()
        + b"x"
    )

    with pytest.raises(
        module.MonthlyGeometryWrapperError,
        match="Stage 10 matrix SHA256 changed",
    ):
        module.authenticate_stage10(
            stage1,
            expectations=expectations,
        )


def test_geometry_rebuilt_from_current_stage10(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage10(
        tmp_path
    )

    authority = (
        module.authenticate_stage10(
            stage1,
            expectations=expectations,
        )
    )

    build = module.build_geometry(
        authority
    )

    assert len(
        build.rows
    ) == 3

    assert build.species_count == 2

    first = FEATURE_FIELDS[0]

    np.testing.assert_array_equal(
        np.asarray(
            [
                row.coordinates[
                    first
                ]
                for row in build.rows
            ]
        ),
        np.asarray(
            [
                0.125,
                0.375,
                0.75,
            ]
        ),
    )


def test_current_species_mapping_changes_geometry(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        raw,
    ) = synthetic_stage10(
        tmp_path
    )

    authority = (
        module.authenticate_stage10(
            stage1,
            expectations=expectations,
        )
    )

    original = module.build_geometry(
        authority
    )

    changed = (
        monthly_geometry
        .build_monthly_geometry(
            authority.accessions,
            (
                "10",
                "20",
                "30",
            ),
            raw,
        )
    )

    assert (
        original.species_mapping_sha256
        != changed.species_mapping_sha256
    )

    assert (
        original.percentile_numeric_array_sha256
        != changed.percentile_numeric_array_sha256
    )


def test_stage11_matrix_roundtrip(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage10(
        tmp_path
    )

    authority = (
        module.authenticate_stage10(
            stage1,
            expectations=expectations,
        )
    )

    build = module.build_geometry(
        authority
    )

    payload = (
        monthly_geometry
        .serialize_monthly_geometry_matrix(
            build
        )
    )

    module._validate_roundtrip(
        build,
        payload,
    )


def test_record_explicitly_stops_before_stage12(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage10(
        tmp_path
    )

    authority = (
        module.authenticate_stage10(
            stage1,
            expectations=expectations,
        )
    )

    build = module.build_geometry(
        authority
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

    record = json.loads(
        module.build_execution_record(
            release_id="2026.09",
            source_snapshot_id=(
                "synthetic-snapshot"
            ),
            execution_commit=(
                "b" * 40
            ),
            stage10=authority,
            build=build,
            matrix_sha256=(
                matrix_sha
            ),
        )
    )

    assert (
        record[
            "species_representatives_constructed"
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
            "selector_outcomes_calculated"
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


def test_completion_binds_record_and_matrix(
    tmp_path,
):
    (
        stage1,
        expectations,
        _,
        _,
        _,
    ) = synthetic_stage10(
        tmp_path
    )

    authority = (
        module.authenticate_stage10(
            stage1,
            expectations=expectations,
        )
    )

    build = module.build_geometry(
        authority
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

    record_payload = (
        module.build_execution_record(
            release_id="2026.09",
            source_snapshot_id=(
                "synthetic-snapshot"
            ),
            execution_commit=(
                "b" * 40
            ),
            stage10=authority,
            build=build,
            matrix_sha256=(
                matrix_sha
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
            stage10=authority,
            build=build,
            matrix_sha256=(
                matrix_sha
            ),
            record_sha256=(
                record_sha
            ),
        )
    )

    assert (
        completion[
            "percentile_matrix_sha256"
        ]
        == matrix_sha
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
    stage1 = tmp_path / "stage1"
    stage1.mkdir()

    final = module.publish_stage(
        stage1_root=stage1,
        matrix_payload=b"matrix\n",
        record_payload=b"record\n",
        stability_check=lambda: None,
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
    stage1 = tmp_path / "stage1"
    stage1.mkdir()

    (
        stage1
        / module.STAGE_NAME
    ).mkdir()

    with pytest.raises(
        module.MonthlyGeometryWrapperError,
        match="already exists",
    ):
        module.publish_stage(
            stage1_root=stage1,
            matrix_payload=b"matrix\n",
            record_payload=b"record\n",
            stability_check=lambda: None,
        )


def test_atomic_completion_publication(
    tmp_path,
):
    stage1 = tmp_path / "stage1"
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


def test_frozen_geometry_dependencies_match_repository():
    repo = (
        Path(__file__)
        .resolve()
        .parents[1]
    )

    observed = (
        module
        .verify_frozen_dependencies(
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


def test_wrapper_contains_no_later_stage_dispatch():
    text = PATH.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "ops_ladder(",
        "ops_species_representatives(",
        "sr_ladder(",
        "ag_ladder(",
        "official_panels",
        "generate_panels(",
    )

    for token in forbidden:
        assert token not in text


def test_production_sha_bindings_are_exact_and_canonical():
    expected = {
        "EXPECTED_STAGE10_MATRIX_SHA256":
            "36d17d35bf245d43d0b1884db5311354b63383dbef5062ef6ea1aab1d48dab0a",
        "EXPECTED_STAGE10_PROVENANCE_SHA256":
            "316e9f0c5e9a3e8e69cd7ecc9c2273cd2b43b3ae4b5af00d2e3c2699e1a584fd",
        "EXPECTED_STAGE10_RECORD_SHA256":
            "683d1b8d7d879f525ea9f5d68144fca0dbb54660e67c72ad8f1682d037605db0",
        "EXPECTED_STAGE10_COMPLETION_SHA256":
            "9c40b8eda35be55280cc16034980701a32c2521767fc4a8203d654a8884e32fe",
        "EXPECTED_STAGE10_RAW_NUMERIC_ARRAY_SHA256":
            "c7049f056a839a0aee24d57c3d4f4109e16a8eb659d8c2a9b904b1ae9cd8fc36",
        "EXPECTED_MEMBERSHIP_SHA256":
            "6e6b44bd598bf472ea2a74686aaabcd23058832938279fb13a4d8ae6cdf7607d",
        "EXPECTED_MONTHLY_GEOMETRY_CORE_SHA256":
            "ac8bbc94a2bacae8c8e80de1f5a9d65be886d59a2e72386ce82de8a5da23297e",
        "EXPECTED_MONTHLY_GEOMETRY_TEST_SHA256":
            "17d7f94e54b2b778d0774617fe5d7285d4c5a394e704306a84b67e917a615595",
        "EXPECTED_GEOMETRY_SHA256":
            "fbebf436d049be063817b717878330f38e09b3e7cb79f9dbc1b8f704af6a0d69",
        "EXPECTED_GEOMETRY_TEST_SHA256":
            "8c215ea881985a8d7fd83b59ee3a9ce4e1ebe5a0ffe64352d2077f098ecedec1",
        "EXPECTED_ENVIRONMENT_LOCK_SHA256":
            "f6f4a19c44a759705682ba4199207eaef5c2435e1b6feeddc1e4654686bc2a8c",
    }

    for name, frozen in expected.items():
        observed = getattr(
            module,
            name,
        )

        assert observed == frozen
        assert len(observed) == 64
        assert observed == observed.lower()
        assert all(
            character in "0123456789abcdef"
            for character in observed
        )

    assert (
        module.PRODUCTION_EXPECTATIONS.membership_sha256
        == expected[
            "EXPECTED_MEMBERSHIP_SHA256"
        ]
    )
