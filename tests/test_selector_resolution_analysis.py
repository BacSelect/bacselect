"""Synthetic tests for the pure in-memory Stage 7 analysis."""

import json

import numpy as np
import pytest

from bacselect.geometry import (
    species_balanced_percentile_matrix,
)
from bacselect.selector_resolution import (
    PANEL_SIZES,
    cross_matrix_nearest_panel_distances,
    format_binary64,
    project_matrix_through_baseline,
)
from bacselect.selector_resolution_analysis import (
    build_blinded_analysis_artifacts,
)
from bacselect.selector_resolution_artifacts import (
    SCIENTIFIC_ARTIFACT_NAMES,
    sha256_bytes,
)


def synthetic_inputs():
    row_count = 520
    feature_count = 12

    row = np.arange(
        row_count,
        dtype=np.float64,
    )

    baseline = np.column_stack(
        [
            (
                row
                * float(
                    feature_index + 1
                )
                + (
                    row
                    % float(
                        feature_index + 3
                    )
                )
                / float(
                    feature_index + 5
                )
            )
            for feature_index in range(
                feature_count
            )
        ]
    )

    baseline_species = [
        f"B{index // 2:03d}"
        for index in range(
            row_count
        )
    ]

    holdout = np.asarray(
        baseline[
            [
                5,
                50,
                150,
                250,
                350,
                450,
            ]
        ],
        dtype=np.float64,
    ).copy()

    holdout += 0.25

    holdout[
        0,
        0,
    ] = -1_000_000.0

    holdout[
        -1,
        1,
    ] = 1_000_000.0

    holdout_species = [
        "B001",
        "NOVEL_A",
        "NOVEL_A",
        "B100",
        "NOVEL_B",
        "B200",
    ]

    features = tuple(
        f"F{index:02d}"
        for index in range(
            1,
            feature_count + 1,
        )
    )

    ladders = {
        "OPS":
            np.arange(
                500,
                dtype=np.int64,
            ),
        "SR":
            np.arange(
                519,
                19,
                -1,
                dtype=np.int64,
            ),
    }

    return (
        baseline,
        baseline_species,
        ladders,
        holdout,
        holdout_species,
        features,
    )


def build_once(
    *,
    ladders=None,
    chunk_size=2,
):
    (
        baseline,
        baseline_species,
        default_ladders,
        holdout,
        holdout_species,
        features,
    ) = synthetic_inputs()

    return build_blinded_analysis_artifacts(
        baseline_raw_features=baseline,
        baseline_species_ids=baseline_species,
        verified_ladders=(
            default_ladders
            if ladders is None
            else ladders
        ),
        holdout_raw_features=holdout,
        holdout_species_ids=holdout_species,
        feature_names=features,
        distance_chunk_size=chunk_size,
    )


def test_analysis_returns_exact_six_artifacts() -> None:
    artifacts = build_once()

    assert tuple(
        artifacts
    ) == SCIENTIFIC_ARTIFACT_NAMES

    assert len(
        artifacts
    ) == 6


def test_analysis_is_byte_deterministic_on_repeat_build() -> None:
    first = build_once()
    second = build_once()

    assert first == second


def test_analysis_is_chunk_size_invariant() -> None:
    first = build_once(
        chunk_size=1
    )

    second = build_once(
        chunk_size=1024
    )

    assert first == second


def test_ladder_mapping_insertion_order_does_not_change_artifacts() -> None:
    (
        _,
        _,
        ladders,
        _,
        _,
        _,
    ) = synthetic_inputs()

    reversed_ladders = dict(
        reversed(
            list(
                ladders.items()
            )
        )
    )

    assert (
        build_once(
            ladders=ladders
        )
        == build_once(
            ladders=reversed_ladders
        )
    )


def test_projected_artifact_is_blinded_and_has_canonical_keys() -> None:
    artifacts = build_once()

    text = artifacts[
        "blinded-holdout-projected-coordinates.tsv"
    ].decode(
        "utf-8"
    )

    lines = text.splitlines()

    assert lines[0].startswith(
        "holdout_row_key\tF01\tF02"
    )

    assert lines[1].startswith(
        "H00000001\t"
    )

    assert lines[-1].startswith(
        "H00000006\t"
    )

    assert len(
        lines
    ) == 7

    assert "B001" not in text
    assert "NOVEL_A" not in text
    assert "NOVEL_B" not in text


def test_distance_artifact_has_twelve_vectors_for_each_holdout_row() -> None:
    artifacts = build_once()

    lines = artifacts[
        "blinded-holdout-nearest-panel-distances.tsv"
    ].decode(
        "utf-8"
    ).splitlines()

    assert len(
        lines
    ) == (
        1
        + 6
        * 2
        * 6
    )

    assert lines[1].startswith(
        "H00000001\tOPS\t10\t"
    )

    assert lines[6].startswith(
        "H00000006\tOPS\t10\t"
    )

    assert lines[7].startswith(
        "H00000001\tOPS\t20\t"
    )

    assert lines[-1].startswith(
        "H00000006\tSR\t500\t"
    )


def test_distance_artifact_uses_literal_frozen_style_prefix() -> None:
    (
        baseline,
        baseline_species,
        ladders,
        holdout,
        _,
        _,
    ) = synthetic_inputs()

    baseline_coordinates = (
        species_balanced_percentile_matrix(
            baseline,
            baseline_species,
        )
    )

    projected = (
        project_matrix_through_baseline(
            baseline,
            baseline_species,
            holdout,
        )
    )

    expected = (
        cross_matrix_nearest_panel_distances(
            projected,
            baseline_coordinates[
                ladders[
                    "OPS"
                ][
                    :10
                ]
            ],
            chunk_size=2,
        )
    )

    artifacts = build_once()

    lines = artifacts[
        "blinded-holdout-nearest-panel-distances.tsv"
    ].decode(
        "utf-8"
    ).splitlines()

    observed = [
        line.split(
            "\t"
        )[3]
        for line in lines[
            1:7
        ]
    ]

    assert observed == [
        format_binary64(
            float(
                value
            )
        )
        for value in expected
    ]


def test_primary_metric_table_has_exact_twelve_rows() -> None:
    artifacts = build_once()

    lines = artifacts[
        "selector-primary-metrics.tsv"
    ].decode(
        "utf-8"
    ).splitlines()

    assert len(
        lines
    ) == 13

    assert lines[0] == (
        "selector\tN\tweighted_p95"
    )

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


def test_exact_product_artifact_contains_products_but_no_decision() -> None:
    artifacts = build_once()

    payload = json.loads(
        artifacts[
            "selector-exact-products.json"
        ]
    )

    assert set(
        payload[
            "selectors"
        ]
    ) == {
        "OPS",
        "SR",
    }

    for selector in (
        "OPS",
        "SR",
    ):
        assert set(
            payload[
                "selectors"
            ][
                selector
            ]
        ) == {
            "denominator",
            "numerator",
        }

    text = artifacts[
        "selector-exact-products.json"
    ].decode(
        "utf-8"
    )

    assert "winner" not in text
    assert "selector_outcome" not in text
    assert "resolved_selector" not in text


def test_diagnostics_are_aggregate_only() -> None:
    artifacts = build_once()

    payload = json.loads(
        artifacts[
            "selector-descriptive-diagnostics.json"
        ]
    )

    assert payload[
        "baseline_genome_count"
    ] == 520

    assert payload[
        "baseline_species_count"
    ] == 260

    assert payload[
        "holdout_genome_count"
    ] == 6

    assert payload[
        "holdout_species_count"
    ] == 5

    assert payload[
        "holdout_species_represented_in_baseline_count"
    ] == 3

    assert payload[
        "holdout_species_absent_from_baseline_count"
    ] == 2

    assert payload[
        "holdout_genomes_in_represented_species_count"
    ] == 3

    assert payload[
        "holdout_genomes_in_absent_species_count"
    ] == 3

    assert payload[
        "coordinate_range_counts"
    ][0][
        "below_baseline_minimum"
    ] == 1

    assert payload[
        "coordinate_range_counts"
    ][1][
        "above_baseline_maximum"
    ] == 1

    assert set(
        payload[
            "selectors"
        ]
    ) == {
        "OPS",
        "SR",
    }

    for selector in (
        "OPS",
        "SR",
    ):
        # Diagnostics use canonical JSON with sort_keys=True.
        # Per-N object keys are therefore serialized in deterministic
        # lexicographic string order, not numeric insertion order.
        assert tuple(
            payload[
                "selectors"
            ][
                selector
            ]
        ) == tuple(
            sorted(
                str(
                    panel_size
                )
                for panel_size in PANEL_SIZES
            )
        )

        for panel_size in PANEL_SIZES:
            assert set(
                payload[
                    "selectors"
                ][
                    selector
                ][
                    str(
                        panel_size
                    )
                ]
            ) == {
                "unweighted_max",
                "weighted_mean",
                "weighted_median",
            }

    text = artifacts[
        "selector-descriptive-diagnostics.json"
    ].decode(
        "utf-8"
    )

    assert "weighted_p95" not in text
    assert "B001" not in text
    assert "NOVEL_A" not in text
    assert "NOVEL_B" not in text
    assert "winner" not in text


def test_analysis_summary_binds_other_five_artifacts() -> None:
    artifacts = build_once()

    summary = json.loads(
        artifacts[
            "selector-resolution-analysis-summary.json"
        ]
    )

    assert (
        summary[
            "projected_coordinates_sha256"
        ]
        == sha256_bytes(
            artifacts[
                "blinded-holdout-projected-coordinates.tsv"
            ]
        )
    )

    assert (
        summary[
            "nearest_panel_distances_sha256"
        ]
        == sha256_bytes(
            artifacts[
                "blinded-holdout-nearest-panel-distances.tsv"
            ]
        )
    )

    assert (
        summary[
            "primary_metric_table_sha256"
        ]
        == sha256_bytes(
            artifacts[
                "selector-primary-metrics.tsv"
            ]
        )
    )

    assert (
        summary[
            "descriptive_diagnostics_sha256"
        ]
        == sha256_bytes(
            artifacts[
                "selector-descriptive-diagnostics.json"
            ]
        )
    )

    assert (
        summary[
            "selector_exact_products_sha256"
        ]
        == sha256_bytes(
            artifacts[
                "selector-exact-products.json"
            ]
        )
    )


def test_analysis_summary_contains_no_primary_or_product_values() -> None:
    artifacts = build_once()

    text = artifacts[
        "selector-resolution-analysis-summary.json"
    ].decode(
        "utf-8"
    )

    assert "weighted_p95" not in text
    assert '"numerator"' not in text
    assert '"denominator"' not in text
    assert '"winner"' not in text
    assert '"selector_outcome"' not in text


def test_rejects_missing_selector_ladder() -> None:
    (
        baseline,
        baseline_species,
        ladders,
        holdout,
        holdout_species,
        features,
    ) = synthetic_inputs()

    del ladders[
        "SR"
    ]

    with pytest.raises(
        ValueError,
        match="exactly OPS and SR",
    ):
        build_blinded_analysis_artifacts(
            baseline_raw_features=baseline,
            baseline_species_ids=baseline_species,
            verified_ladders=ladders,
            holdout_raw_features=holdout,
            holdout_species_ids=holdout_species,
            feature_names=features,
        )


def test_rejects_ladder_not_exactly_500_rows() -> None:
    (
        baseline,
        baseline_species,
        ladders,
        holdout,
        holdout_species,
        features,
    ) = synthetic_inputs()

    ladders[
        "OPS"
    ] = ladders[
        "OPS"
    ][
        :-1
    ]

    with pytest.raises(
        ValueError,
        match="exactly 500",
    ):
        build_blinded_analysis_artifacts(
            baseline_raw_features=baseline,
            baseline_species_ids=baseline_species,
            verified_ladders=ladders,
            holdout_raw_features=holdout,
            holdout_species_ids=holdout_species,
            feature_names=features,
        )


def test_rejects_duplicate_ladder_indices() -> None:
    (
        baseline,
        baseline_species,
        ladders,
        holdout,
        holdout_species,
        features,
    ) = synthetic_inputs()

    ladders[
        "OPS"
    ] = ladders[
        "OPS"
    ].copy()

    ladders[
        "OPS"
    ][
        -1
    ] = ladders[
        "OPS"
    ][0]

    with pytest.raises(
        ValueError,
        match="unique",
    ):
        build_blinded_analysis_artifacts(
            baseline_raw_features=baseline,
            baseline_species_ids=baseline_species,
            verified_ladders=ladders,
            holdout_raw_features=holdout,
            holdout_species_ids=holdout_species,
            feature_names=features,
        )


def test_rejects_out_of_range_ladder_index() -> None:
    (
        baseline,
        baseline_species,
        ladders,
        holdout,
        holdout_species,
        features,
    ) = synthetic_inputs()

    ladders[
        "OPS"
    ] = ladders[
        "OPS"
    ].copy()

    ladders[
        "OPS"
    ][
        -1
    ] = baseline.shape[0]

    with pytest.raises(
        ValueError,
        match="outside baseline",
    ):
        build_blinded_analysis_artifacts(
            baseline_raw_features=baseline,
            baseline_species_ids=baseline_species,
            verified_ladders=ladders,
            holdout_raw_features=holdout,
            holdout_species_ids=holdout_species,
            feature_names=features,
        )


def test_rejects_noninteger_ladder_indices() -> None:
    (
        baseline,
        baseline_species,
        ladders,
        holdout,
        holdout_species,
        features,
    ) = synthetic_inputs()

    ladders[
        "OPS"
    ] = ladders[
        "OPS"
    ].astype(
        np.float64
    )

    with pytest.raises(
        TypeError,
        match="integers",
    ):
        build_blinded_analysis_artifacts(
            baseline_raw_features=baseline,
            baseline_species_ids=baseline_species,
            verified_ladders=ladders,
            holdout_raw_features=holdout,
            holdout_species_ids=holdout_species,
            feature_names=features,
        )


def test_rejects_holdout_species_row_mismatch() -> None:
    (
        baseline,
        baseline_species,
        ladders,
        holdout,
        holdout_species,
        features,
    ) = synthetic_inputs()

    with pytest.raises(
        ValueError,
        match="same number of rows",
    ):
        build_blinded_analysis_artifacts(
            baseline_raw_features=baseline,
            baseline_species_ids=baseline_species,
            verified_ladders=ladders,
            holdout_raw_features=holdout,
            holdout_species_ids=holdout_species[:-1],
            feature_names=features,
        )


def test_rejects_feature_dimension_mismatch() -> None:
    (
        baseline,
        baseline_species,
        ladders,
        holdout,
        holdout_species,
        features,
    ) = synthetic_inputs()

    with pytest.raises(
        ValueError,
        match="same number of features",
    ):
        build_blinded_analysis_artifacts(
            baseline_raw_features=baseline,
            baseline_species_ids=baseline_species,
            verified_ladders=ladders,
            holdout_raw_features=holdout[
                :,
                :-1
            ],
            holdout_species_ids=holdout_species,
            feature_names=features,
        )
