"""Synthetic tests for deterministic blinded Stage 7 artifacts."""

from fractions import Fraction
import json

import numpy as np
import pytest

from bacselect.selector_resolution import (
    PANEL_SIZES,
)
from bacselect.selector_resolution_artifacts import (
    SCIENTIFIC_ARTIFACT_NAMES,
    SELECTORS,
    anonymous_holdout_row_keys,
    canonical_blinded_json_bytes,
    serialize_analysis_summary,
    serialize_descriptive_diagnostics,
    serialize_exact_products,
    serialize_nearest_panel_distances,
    serialize_primary_metrics,
    serialize_projected_coordinates,
    sha256_bytes,
)


def synthetic_distance_mapping(
    row_count: int = 2,
):
    return {
        (
            selector,
            panel_size,
        ):
            np.asarray(
                [
                    (
                        selector_index
                        + panel_index / 1000.0
                        + row_index / 10000.0
                    )
                    for row_index in range(
                        row_count
                    )
                ],
                dtype=np.float64,
            )
        for selector_index, selector
        in enumerate(
            SELECTORS,
            start=1,
        )
        for panel_index, panel_size
        in enumerate(
            PANEL_SIZES,
            start=1,
        )
    }


def synthetic_metric_mapping():
    return {
        (
            selector,
            panel_size,
        ):
            float(
                selector_index
                + panel_index / 10.0
            )
        for selector_index, selector
        in enumerate(
            SELECTORS,
            start=1,
        )
        for panel_index, panel_size
        in enumerate(
            PANEL_SIZES,
            start=1,
        )
    }


def test_scientific_artifact_contract_has_exact_six_names() -> None:
    assert SCIENTIFIC_ARTIFACT_NAMES == (
        "blinded-holdout-projected-coordinates.tsv",
        "blinded-holdout-nearest-panel-distances.tsv",
        "selector-primary-metrics.tsv",
        "selector-descriptive-diagnostics.json",
        "selector-exact-products.json",
        "selector-resolution-analysis-summary.json",
    )


def test_anonymous_row_keys_are_canonical_and_fixed_width() -> None:
    assert anonymous_holdout_row_keys(
        3
    ) == (
        "H00000001",
        "H00000002",
        "H00000003",
    )


def test_anonymous_row_keys_reject_zero() -> None:
    with pytest.raises(
        ValueError,
        match="positive integer",
    ):
        anonymous_holdout_row_keys(
            0
        )


def test_projected_coordinate_serialization_is_exact() -> None:
    observed = serialize_projected_coordinates(
        np.asarray(
            [
                [
                    0.1,
                    0.5,
                ],
                [
                    1.0,
                    0.0,
                ],
            ],
            dtype=np.float64,
        ),
        [
            "F01",
            "F02",
        ],
    )

    expected = (
        "holdout_row_key\tF01\tF02\n"
        "H00000001\t0.10000000000000001\t0.5\n"
        "H00000002\t1\t0\n"
    ).encode(
        "utf-8"
    )

    assert observed == expected


def test_projected_coordinate_serialization_rejects_identity_field() -> None:
    with pytest.raises(
        ValueError,
        match="identity-bearing",
    ):
        serialize_projected_coordinates(
            [
                [
                    0.5,
                ],
            ],
            [
                "species_taxid",
            ],
        )


def test_projected_coordinate_serialization_rejects_column_mismatch() -> None:
    with pytest.raises(
        ValueError,
        match="match coordinate columns",
    ):
        serialize_projected_coordinates(
            [
                [
                    0.1,
                    0.2,
                ],
            ],
            [
                "F01",
            ],
        )


def test_distance_serialization_has_canonical_selector_n_row_order() -> None:
    payload = serialize_nearest_panel_distances(
        synthetic_distance_mapping(
            row_count=2,
        )
    )

    lines = payload.decode(
        "utf-8"
    ).splitlines()

    assert lines[0] == (
        "holdout_row_key\tselector\tN\tnearest_panel_distance"
    )

    assert lines[1].startswith(
        "H00000001\tOPS\t10\t"
    )

    assert lines[2].startswith(
        "H00000002\tOPS\t10\t"
    )

    assert lines[3].startswith(
        "H00000001\tOPS\t20\t"
    )

    assert lines[-2].startswith(
        "H00000001\tSR\t500\t"
    )

    assert lines[-1].startswith(
        "H00000002\tSR\t500\t"
    )

    assert len(
        lines
    ) == (
        1
        + 2
        * len(
            SELECTORS
        )
        * len(
            PANEL_SIZES
        )
    )


def test_distance_serialization_is_insertion_order_independent() -> None:
    mapping = synthetic_distance_mapping()

    reversed_mapping = dict(
        reversed(
            list(
                mapping.items()
            )
        )
    )

    assert (
        serialize_nearest_panel_distances(
            mapping
        )
        == serialize_nearest_panel_distances(
            reversed_mapping
        )
    )


def test_distance_serialization_requires_all_twelve_vectors() -> None:
    mapping = synthetic_distance_mapping()

    del mapping[
        (
            "OPS",
            10,
        )
    ]

    with pytest.raises(
        ValueError,
        match="exactly",
    ):
        serialize_nearest_panel_distances(
            mapping
        )


def test_distance_serialization_rejects_negative_distance() -> None:
    mapping = synthetic_distance_mapping()

    mapping[
        (
            "OPS",
            10,
        )
    ] = np.asarray(
        [
            -1.0,
            0.0,
        ]
    )

    with pytest.raises(
        ValueError,
        match="non-negative",
    ):
        serialize_nearest_panel_distances(
            mapping
        )


def test_primary_metric_table_is_exactly_twelve_rows() -> None:
    payload = serialize_primary_metrics(
        synthetic_metric_mapping()
    )

    lines = payload.decode(
        "utf-8"
    ).splitlines()

    assert lines[0] == (
        "selector\tN\tweighted_p95"
    )

    assert len(
        lines
    ) == 13

    assert lines[1].startswith(
        "OPS\t10\t"
    )

    assert lines[6].startswith(
        "OPS\t500\t"
    )

    assert lines[7].startswith(
        "SR\t10\t"
    )

    assert lines[12].startswith(
        "SR\t500\t"
    )


def test_primary_metric_serialization_is_insertion_order_independent() -> None:
    mapping = synthetic_metric_mapping()

    reversed_mapping = dict(
        reversed(
            list(
                mapping.items()
            )
        )
    )

    assert (
        serialize_primary_metrics(
            mapping
        )
        == serialize_primary_metrics(
            reversed_mapping
        )
    )


def test_exact_product_artifact_contains_no_winner() -> None:
    payload = serialize_exact_products(
        {
            "OPS":
                Fraction(
                    1,
                    3,
                ),
            "SR":
                Fraction(
                    2,
                    5,
                ),
        }
    )

    parsed = json.loads(
        payload
    )

    assert parsed == {
        "schema_version":
            1,
        "selectors": {
            "OPS": {
                "denominator":
                    3,
                "numerator":
                    1,
            },
            "SR": {
                "denominator":
                    5,
                "numerator":
                    2,
            },
        },
        "status":
            "STAGE7_EXACT_PRODUCTS_COMPLETE",
    }

    assert b"winner" not in payload
    assert b"decision" not in payload
    assert b"selector_outcome" not in payload


def test_exact_product_serialization_is_mapping_order_independent() -> None:
    first = serialize_exact_products(
        {
            "OPS":
                Fraction(
                    1,
                    7,
                ),
            "SR":
                Fraction(
                    2,
                    9,
                ),
        }
    )

    second = serialize_exact_products(
        {
            "SR":
                Fraction(
                    2,
                    9,
                ),
            "OPS":
                Fraction(
                    1,
                    7,
                ),
        }
    )

    assert first == second


def test_exact_product_serialization_requires_fraction() -> None:
    with pytest.raises(
        TypeError,
        match="Fraction",
    ):
        serialize_exact_products(
            {
                "OPS":
                    0.1,  # type: ignore[dict-item]
                "SR":
                    Fraction(
                        1,
                        2,
                    ),
            }
        )


def test_blinded_json_rejects_accession_field_name() -> None:
    with pytest.raises(
        ValueError,
        match="identity-bearing",
    ):
        canonical_blinded_json_bytes(
            {
                "accession":
                    "anonymous",
            }
        )


def test_blinded_json_rejects_accession_like_value() -> None:
    with pytest.raises(
        ValueError,
        match="accession identity",
    ):
        canonical_blinded_json_bytes(
            {
                "note":
                    "unexpected GCA_123456789 value",
            }
        )


def test_blinded_json_allows_species_aggregate_count() -> None:
    payload = canonical_blinded_json_bytes(
        {
            "holdout_species_count":
                3542,
        }
    )

    assert json.loads(
        payload
    ) == {
        "holdout_species_count":
            3542,
    }


def test_diagnostics_reject_selector_outcome() -> None:
    with pytest.raises(
        ValueError,
        match="forbidden",
    ):
        serialize_descriptive_diagnostics(
            {
                "selector_outcome":
                    "OPS",
            }
        )


def test_analysis_summary_allows_exact_product_artifact_hash() -> None:
    payload = serialize_analysis_summary(
        {
            "selector_exact_products_sha256":
                "a" * 64,
            "primary_metric_table_sha256":
                "b" * 64,
            "status":
                "STAGE7_ANALYSIS_COMPLETE",
        }
    )

    parsed = json.loads(
        payload
    )

    assert parsed[
        "selector_exact_products_sha256"
    ] == "a" * 64


@pytest.mark.parametrize(
    "key,value",
    (
        (
            "weighted_p95",
            0.2,
        ),
        (
            "ops_product",
            "1/2",
        ),
        (
            "numerator",
            1,
        ),
        (
            "winner",
            "OPS",
        ),
        (
            "selector_outcome",
            "SR",
        ),
    ),
)
def test_analysis_summary_rejects_outcome_values(
    key,
    value,
) -> None:
    with pytest.raises(
        ValueError,
        match="forbidden",
    ):
        serialize_analysis_summary(
            {
                key:
                    value,
            }
        )


def test_sha256_bytes_is_exact_and_deterministic() -> None:
    payload = b"abc\n"

    assert sha256_bytes(
        payload
    ) == sha256_bytes(
        bytes(
            payload
        )
    )

    assert len(
        sha256_bytes(
            payload
        )
    ) == 64


def test_canonical_json_is_mapping_order_independent() -> None:
    first = canonical_blinded_json_bytes(
        {
            "b":
                2,
            "a":
                1,
        }
    )

    second = canonical_blinded_json_bytes(
        {
            "a":
                1,
            "b":
                2,
        }
    )

    assert first == second

    assert first == (
        '{\n'
        '  "a": 1,\n'
        '  "b": 2\n'
        '}\n'
    ).encode(
        "utf-8"
    )
