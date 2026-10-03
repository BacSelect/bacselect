from __future__ import annotations

import numpy as np
import pytest

from bacselect.monthly_geometry import (
    FEATURE_FIELDS,
    MonthlyGeometryError,
    _numeric_array_sha256,
    build_monthly_geometry,
    parse_monthly_geometry_matrix,
    serialize_monthly_geometry_matrix,
)


def raw_matrix() -> np.ndarray:
    rows = [
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
    ]

    return np.asarray(
        rows,
        dtype=np.float64,
    )


def test_build_monthly_geometry_species_balanced():
    build = build_monthly_geometry(
        (
            "GCA_000000001.1",
            "GCA_000000002.1",
            "GCA_000000003.1",
        ),
        (
            "10",
            "10",
            "20",
        ),
        raw_matrix(),
    )

    assert len(
        build.rows
    ) == 3

    assert build.species_count == 2

    first_field = (
        FEATURE_FIELDS[0]
    )

    observed = np.asarray(
        [
            row.coordinates[
                first_field
            ]
            for row in build.rows
        ]
    )

    np.testing.assert_array_equal(
        observed,
        np.asarray(
            [
                0.125,
                0.375,
                0.75,
            ]
        ),
    )


def test_constant_feature_maps_to_half():
    raw = np.full(
        (
            3,
            len(
                FEATURE_FIELDS
            ),
        ),
        7.0,
    )

    build = build_monthly_geometry(
        (
            "GCA_000000001.1",
            "GCA_000000002.1",
            "GCA_000000003.1",
        ),
        (
            "10",
            "10",
            "20",
        ),
        raw,
    )

    for row in build.rows:
        assert set(
            row.coordinates.values()
        ) == {
            0.5
        }


def test_geometry_is_input_order_invariant():
    accessions = np.asarray(
        [
            "GCA_000000001.1",
            "GCA_000000002.1",
            "GCA_000000003.1",
        ],
        dtype=object,
    )

    species = np.asarray(
        [
            "10",
            "10",
            "20",
        ],
        dtype=object,
    )

    raw = raw_matrix()

    baseline = (
        build_monthly_geometry(
            tuple(
                accessions
            ),
            tuple(
                species
            ),
            raw,
        )
    )

    permutation = np.asarray(
        [
            2,
            0,
            1,
        ]
    )

    permuted = (
        build_monthly_geometry(
            tuple(
                accessions[
                    permutation
                ]
            ),
            tuple(
                species[
                    permutation
                ]
            ),
            raw[
                permutation
            ],
        )
    )

    baseline_by_accession = {
        row.accession:
            dict(
                row.coordinates
            )
        for row in baseline.rows
    }

    permuted_by_accession = {
        row.accession:
            dict(
                row.coordinates
            )
        for row in permuted.rows
    }

    assert (
        baseline_by_accession
        == permuted_by_accession
    )


def test_serialization_roundtrips_exact_float64():
    build = build_monthly_geometry(
        (
            "GCA_000000001.1",
            "GCA_000000002.1",
            "GCA_000000003.1",
        ),
        (
            "10",
            "10",
            "20",
        ),
        raw_matrix(),
    )

    payload = (
        serialize_monthly_geometry_matrix(
            build
        )
    )

    (
        accessions,
        species,
        matrix,
    ) = parse_monthly_geometry_matrix(
        payload
    )

    assert accessions == tuple(
        row.accession
        for row in build.rows
    )

    assert species == tuple(
        row.species_taxid
        for row in build.rows
    )

    expected = np.asarray(
        [
            [
                row.coordinates[
                    field
                ]
                for field in (
                    FEATURE_FIELDS
                )
            ]
            for row in build.rows
        ],
        dtype=np.float64,
    )

    np.testing.assert_array_equal(
        matrix,
        expected,
    )

    assert (
        _numeric_array_sha256(
            matrix
        )
        == build
        .percentile_numeric_array_sha256
    )


def test_membership_and_species_mapping_are_order_bound():
    one = build_monthly_geometry(
        (
            "GCA_000000001.1",
            "GCA_000000002.1",
            "GCA_000000003.1",
        ),
        (
            "10",
            "10",
            "20",
        ),
        raw_matrix(),
    )

    two = build_monthly_geometry(
        (
            "GCA_000000003.1",
            "GCA_000000001.1",
            "GCA_000000002.1",
        ),
        (
            "20",
            "10",
            "10",
        ),
        raw_matrix()[
            [
                2,
                0,
                1,
            ]
        ],
    )

    # BacSelect membership identity is set-like/canonical.
    assert (
        one.membership_sha256
        == two.membership_sha256
    )

    # Geometry provenance additionally binds exact row ordering.
    assert (
        one.species_mapping_sha256
        != two.species_mapping_sha256
    )


def test_duplicate_accession_rejected():
    with pytest.raises(
        MonthlyGeometryError,
        match="duplicate",
    ):
        build_monthly_geometry(
            (
                "GCA_000000001.1",
                "GCA_000000001.1",
            ),
            (
                "10",
                "20",
            ),
            np.zeros(
                (
                    2,
                    len(
                        FEATURE_FIELDS
                    ),
                )
            ),
        )


def test_malformed_accession_rejected():
    with pytest.raises(
        MonthlyGeometryError,
        match="malformed accession",
    ):
        build_monthly_geometry(
            (
                "not-an-accession",
            ),
            (
                "10",
            ),
            np.zeros(
                (
                    1,
                    len(
                        FEATURE_FIELDS
                    ),
                )
            ),
        )


def test_malformed_species_taxid_rejected():
    with pytest.raises(
        MonthlyGeometryError,
        match="species TaxID",
    ):
        build_monthly_geometry(
            (
                "GCA_000000001.1",
            ),
            (
                "",
            ),
            np.zeros(
                (
                    1,
                    len(
                        FEATURE_FIELDS
                    ),
                )
            ),
        )


def test_wrong_feature_shape_rejected():
    with pytest.raises(
        MonthlyGeometryError,
        match="shape",
    ):
        build_monthly_geometry(
            (
                "GCA_000000001.1",
            ),
            (
                "10",
            ),
            np.zeros(
                (
                    1,
                    len(
                        FEATURE_FIELDS
                    )
                    - 1,
                )
            ),
        )


def test_nonfinite_raw_value_rejected():
    raw = np.zeros(
        (
            1,
            len(
                FEATURE_FIELDS
            ),
        )
    )

    raw[
        0,
        0,
    ] = np.nan

    with pytest.raises(
        MonthlyGeometryError,
        match="non-finite",
    ):
        build_monthly_geometry(
            (
                "GCA_000000001.1",
            ),
            (
                "10",
            ),
            raw,
        )
