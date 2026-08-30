"""Pure in-memory blinded Stage 7 selector-resolution analysis."""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Mapping, Sequence

import numpy as np
import numpy.typing as npt

from bacselect.geometry import (
    species_balanced_percentile_matrix,
)
from bacselect.metrics import (
    coverage_summary,
)
from bacselect.selector_resolution import (
    PANEL_SIZES,
    cross_matrix_nearest_panel_distances,
    exact_six_size_product,
    holdout_weighted_p95,
    project_matrix_through_baseline,
    projection_out_of_range_counts,
)
from bacselect.selector_resolution_artifacts import (
    SCIENTIFIC_ARTIFACT_NAMES,
    SELECTORS,
    serialize_analysis_summary,
    serialize_descriptive_diagnostics,
    serialize_exact_products,
    serialize_nearest_panel_distances,
    serialize_primary_metrics,
    serialize_projected_coordinates,
    sha256_bytes,
)


def _validate_matrix(
    values: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    *,
    name: str,
) -> npt.NDArray[np.float64]:
    """Return one finite non-empty binary64 matrix."""
    matrix = np.asarray(
        values,
        dtype=np.float64,
    )

    if matrix.ndim != 2:
        raise ValueError(
            f"{name} must be two-dimensional"
        )

    if (
        matrix.shape[0] == 0
        or matrix.shape[1] == 0
    ):
        raise ValueError(
            f"{name} must not be empty"
        )

    if not np.all(
        np.isfinite(
            matrix
        )
    ):
        raise ValueError(
            f"{name} must contain only finite values"
        )

    return matrix


def _validate_species(
    species_ids: Sequence[Hashable],
    row_count: int,
    *,
    name: str,
) -> list[Hashable]:
    """Return hashable species labels matching matrix row count."""
    species = list(
        species_ids
    )

    if len(
        species
    ) != row_count:
        raise ValueError(
            f"{name} and matrix must contain "
            "the same number of rows"
        )

    if not species:
        raise ValueError(
            f"{name} must not be empty"
        )

    try:
        Counter(
            species
        )
    except TypeError as exc:
        raise TypeError(
            f"{name} values must be hashable"
        ) from exc

    return species


def _validate_feature_names(
    feature_names: Sequence[str],
    feature_count: int,
) -> tuple[str, ...]:
    """Return the exact ordered feature-name sequence."""
    features = tuple(
        feature_names
    )

    if len(
        features
    ) != feature_count:
        raise ValueError(
            "feature_names must match matrix columns"
        )

    if len(
        set(
            features
        )
    ) != feature_count:
        raise ValueError(
            "feature_names must be unique"
        )

    return features


def _validate_ladders(
    ladders: Mapping[
        str,
        Sequence[int]
        | npt.NDArray[np.integer],
    ],
    baseline_row_count: int,
) -> dict[
    str,
    npt.NDArray[np.int64],
]:
    """Validate already verified frozen-style N=500 ladder indices."""
    if set(
        ladders
    ) != set(
        SELECTORS
    ):
        raise ValueError(
            "ladders must contain exactly OPS and SR"
        )

    max_n = max(
        PANEL_SIZES
    )

    result: dict[
        str,
        npt.NDArray[np.int64],
    ] = {}

    for selector in SELECTORS:
        source = np.asarray(
            ladders[
                selector
            ]
        )

        if source.ndim != 1:
            raise ValueError(
                f"{selector} ladder must be one-dimensional"
            )

        if source.size != max_n:
            raise ValueError(
                f"{selector} ladder must contain exactly "
                f"{max_n} rows"
            )

        if not np.issubdtype(
            source.dtype,
            np.integer,
        ):
            raise TypeError(
                f"{selector} ladder indices must be integers"
            )

        ladder = source.astype(
            np.int64,
            copy=False,
        )

        if np.unique(
            ladder
        ).size != max_n:
            raise ValueError(
                f"{selector} ladder indices must be unique"
            )

        if (
            np.any(
                ladder < 0
            )
            or np.any(
                ladder >= baseline_row_count
            )
        ):
            raise ValueError(
                f"{selector} ladder index outside baseline matrix"
            )

        result[
            selector
        ] = ladder

    return result


def build_blinded_analysis_artifacts(
    *,
    baseline_raw_features: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    baseline_species_ids: Sequence[Hashable],
    verified_ladders: Mapping[
        str,
        Sequence[int]
        | npt.NDArray[np.integer],
    ],
    holdout_raw_features: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    holdout_species_ids: Sequence[Hashable],
    feature_names: Sequence[str],
    distance_chunk_size: int = 1024,
) -> dict[str, bytes]:
    """Build the six blinded scientific artifacts entirely in memory.

    ``verified_ladders`` are treated as already frozen baseline ladders.
    This function never generates, modifies or resolves a selector ladder.

    This function also does not resolve OPS versus SR. It emits exact product
    values only; selector decision finalization remains a separate gate.
    """
    baseline = _validate_matrix(
        baseline_raw_features,
        name="baseline_raw_features",
    )

    holdout = _validate_matrix(
        holdout_raw_features,
        name="holdout_raw_features",
    )

    if (
        baseline.shape[1]
        != holdout.shape[1]
    ):
        raise ValueError(
            "baseline and holdout matrices must contain "
            "the same number of features"
        )

    baseline_species = _validate_species(
        baseline_species_ids,
        baseline.shape[0],
        name="baseline_species_ids",
    )

    holdout_species = _validate_species(
        holdout_species_ids,
        holdout.shape[0],
        name="holdout_species_ids",
    )

    features = _validate_feature_names(
        feature_names,
        baseline.shape[1],
    )

    ladders = _validate_ladders(
        verified_ladders,
        baseline.shape[0],
    )

    baseline_coordinates = (
        species_balanced_percentile_matrix(
            baseline,
            baseline_species,
        )
    )

    projected_coordinates = (
        project_matrix_through_baseline(
            baseline,
            baseline_species,
            holdout,
        )
    )

    below_counts, above_counts = (
        projection_out_of_range_counts(
            baseline,
            holdout,
        )
    )

    distance_vectors: dict[
        tuple[str, int],
        npt.NDArray[np.float64],
    ] = {}

    primary_metrics: dict[
        tuple[str, int],
        float,
    ] = {}

    diagnostic_selectors: dict[
        str,
        dict[str, dict[str, float]],
    ] = {}

    for selector in SELECTORS:
        ladder = ladders[
            selector
        ]

        per_n: dict[
            str,
            dict[str, float],
        ] = {}

        for panel_size in PANEL_SIZES:
            panel_coordinates = (
                baseline_coordinates[
                    ladder[
                        :panel_size
                    ]
                ]
            )

            distances = (
                cross_matrix_nearest_panel_distances(
                    projected_coordinates,
                    panel_coordinates,
                    chunk_size=distance_chunk_size,
                )
            )

            distance_vectors[
                (
                    selector,
                    panel_size,
                )
            ] = distances

            primary_metrics[
                (
                    selector,
                    panel_size,
                )
            ] = holdout_weighted_p95(
                distances,
                holdout_species,
            )

            summary = coverage_summary(
                distances,
                holdout_species,
            )

            per_n[
                str(
                    panel_size
                )
            ] = {
                "unweighted_max":
                    float(
                        summary.unweighted_max
                    ),
                "weighted_mean":
                    float(
                        summary.weighted_mean
                    ),
                "weighted_median":
                    float(
                        summary.weighted_median
                    ),
            }

        diagnostic_selectors[
            selector
        ] = per_n

    exact_products = {
        selector:
            exact_six_size_product(
                {
                    panel_size:
                        primary_metrics[
                            (
                                selector,
                                panel_size,
                            )
                        ]
                    for panel_size in PANEL_SIZES
                }
            )
        for selector in SELECTORS
    }

    baseline_species_set = set(
        baseline_species
    )

    holdout_species_set = set(
        holdout_species
    )

    represented_species = (
        holdout_species_set
        & baseline_species_set
    )

    absent_species = (
        holdout_species_set
        - baseline_species_set
    )

    represented_genomes = sum(
        1
        for species_id in holdout_species
        if species_id in baseline_species_set
    )

    absent_genomes = (
        len(
            holdout_species
        )
        - represented_genomes
    )

    coordinate_range_counts = [
        {
            "above_baseline_maximum":
                int(
                    above_counts[
                        index
                    ]
                ),
            "below_baseline_minimum":
                int(
                    below_counts[
                        index
                    ]
                ),
            "feature":
                features[
                    index
                ],
        }
        for index in range(
            len(
                features
            )
        )
    ]

    projected_bytes = (
        serialize_projected_coordinates(
            projected_coordinates,
            features,
        )
    )

    distances_bytes = (
        serialize_nearest_panel_distances(
            distance_vectors
        )
    )

    metrics_bytes = (
        serialize_primary_metrics(
            primary_metrics
        )
    )

    diagnostics_bytes = (
        serialize_descriptive_diagnostics(
            {
                "baseline_genome_count":
                    int(
                        baseline.shape[0]
                    ),
                "baseline_species_count":
                    int(
                        len(
                            baseline_species_set
                        )
                    ),
                "coordinate_range_counts":
                    coordinate_range_counts,
                "holdout_genome_count":
                    int(
                        holdout.shape[0]
                    ),
                "holdout_genomes_in_absent_species_count":
                    int(
                        absent_genomes
                    ),
                "holdout_genomes_in_represented_species_count":
                    int(
                        represented_genomes
                    ),
                "holdout_species_absent_from_baseline_count":
                    int(
                        len(
                            absent_species
                        )
                    ),
                "holdout_species_count":
                    int(
                        len(
                            holdout_species_set
                        )
                    ),
                "holdout_species_represented_in_baseline_count":
                    int(
                        len(
                            represented_species
                        )
                    ),
                "schema_version":
                    1,
                "selectors":
                    diagnostic_selectors,
                "status":
                    "STAGE7_DIAGNOSTICS_COMPLETE",
            }
        )
    )

    products_bytes = (
        serialize_exact_products(
            exact_products
        )
    )

    summary_bytes = (
        serialize_analysis_summary(
            {
                "baseline_genome_count":
                    int(
                        baseline.shape[0]
                    ),
                "baseline_species_count":
                    int(
                        len(
                            baseline_species_set
                        )
                    ),
                "descriptive_diagnostics_sha256":
                    sha256_bytes(
                        diagnostics_bytes
                    ),
                "feature_count":
                    int(
                        baseline.shape[1]
                    ),
                "holdout_genome_count":
                    int(
                        holdout.shape[0]
                    ),
                "holdout_species_count":
                    int(
                        len(
                            holdout_species_set
                        )
                    ),
                "nearest_panel_distances_sha256":
                    sha256_bytes(
                        distances_bytes
                    ),
                "panel_sizes":
                    list(
                        PANEL_SIZES
                    ),
                "primary_metric_table_sha256":
                    sha256_bytes(
                        metrics_bytes
                    ),
                "projected_coordinates_sha256":
                    sha256_bytes(
                        projected_bytes
                    ),
                "schema_version":
                    1,
                "selector_exact_products_sha256":
                    sha256_bytes(
                        products_bytes
                    ),
                "selectors":
                    list(
                        SELECTORS
                    ),
                "status":
                    "STAGE7_ANALYSIS_COMPLETE",
            }
        )
    )

    artifacts = {
        "blinded-holdout-projected-coordinates.tsv":
            projected_bytes,
        "blinded-holdout-nearest-panel-distances.tsv":
            distances_bytes,
        "selector-primary-metrics.tsv":
            metrics_bytes,
        "selector-descriptive-diagnostics.json":
            diagnostics_bytes,
        "selector-exact-products.json":
            products_bytes,
        "selector-resolution-analysis-summary.json":
            summary_bytes,
    }

    if tuple(
        artifacts
    ) != SCIENTIFIC_ARTIFACT_NAMES:
        raise RuntimeError(
            "scientific artifact ordering differs from frozen contract"
        )

    return artifacts
