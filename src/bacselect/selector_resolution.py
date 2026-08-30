"""Pure scientific primitives for blinded selector-v1 resolution."""

from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from fractions import Fraction
import math
from collections.abc import Hashable, Mapping, Sequence

import numpy as np
import numpy.typing as npt

from bacselect.metrics import (
    P95,
    species_balanced_weighted_quantile,
)


PANEL_SIZES: tuple[int, ...] = (
    10,
    20,
    50,
    100,
    200,
    500,
)


def _validate_vector(
    values: Sequence[float] | npt.NDArray[np.floating],
    *,
    name: str,
) -> npt.NDArray[np.float64]:
    """Return one finite, non-empty binary64 vector."""
    array = np.asarray(
        values,
        dtype=np.float64,
    )

    if array.ndim != 1:
        raise ValueError(
            f"{name} must be one-dimensional"
        )

    if array.size == 0:
        raise ValueError(
            f"{name} must not be empty"
        )

    if not np.all(
        np.isfinite(array)
    ):
        raise ValueError(
            f"{name} must contain only finite values"
        )

    return array


def _validate_matrix(
    values: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    *,
    name: str,
) -> npt.NDArray[np.float64]:
    """Return one finite, non-empty binary64 matrix."""
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
        np.isfinite(matrix)
    ):
        raise ValueError(
            f"{name} must contain only finite values"
        )

    return matrix


def _validate_species(
    species_ids: Sequence[Hashable],
    expected_rows: int,
) -> list[Hashable]:
    """Return species IDs after exact row-count validation."""
    species = list(
        species_ids
    )

    if len(species) != expected_rows:
        raise ValueError(
            "species_ids and baseline rows must "
            "contain the same number of rows"
        )

    if not species:
        raise ValueError(
            "species_ids must not be empty"
        )

    try:
        Counter(
            species
        )
    except TypeError as exc:
        raise TypeError(
            "species_ids must be hashable"
        ) from exc

    return species


def project_values_through_baseline(
    baseline_values: Sequence[float]
    | npt.NDArray[np.floating],
    baseline_species_ids: Sequence[Hashable],
    query_values: Sequence[float]
    | npt.NDArray[np.floating],
) -> npt.NDArray[np.float64]:
    """Project unseen values through one frozen baseline distribution.

    Baseline species each contribute total weight one. A baseline
    genome in species ``s`` receives exact weight ``1 / n_s``.

    For unseen value ``x``:

        p(x) = [W_less(x) + 0.5 * W_equal(x)] / S

    where only the frozen baseline contributes to ``W_less``,
    ``W_equal`` and total species weight ``S``.

    No interpolation is performed between observed baseline values.
    """
    baseline = _validate_vector(
        baseline_values,
        name="baseline_values",
    )

    query = _validate_vector(
        query_values,
        name="query_values",
    )

    species = _validate_species(
        baseline_species_ids,
        baseline.size,
    )

    counts = Counter(
        species
    )

    species_count = len(
        counts
    )

    common_denominator = math.lcm(
        *counts.values()
    )

    weight_units = {
        species_id:
            common_denominator
            // count
        for species_id, count
        in counts.items()
    }

    total_units = (
        common_denominator
        * species_count
    )

    order = sorted(
        range(
            baseline.size
        ),
        key=lambda index: (
            baseline[index],
            index,
        ),
    )

    group_values: list[float] = []
    less_units: list[int] = []
    equal_units: list[int] = []

    cumulative_units = 0
    start = 0

    while start < baseline.size:
        value = float(
            baseline[
                order[start]
            ]
        )

        stop = start
        group_units = 0

        while (
            stop < baseline.size
            and baseline[
                order[stop]
            ] == value
        ):
            group_units += (
                weight_units[
                    species[
                        order[stop]
                    ]
                ]
            )
            stop += 1

        group_values.append(
            value
        )

        less_units.append(
            cumulative_units
        )

        equal_units.append(
            group_units
        )

        cumulative_units += (
            group_units
        )

        start = stop

    if cumulative_units != total_units:
        raise RuntimeError(
            "baseline species-balanced weights "
            "do not sum to species count"
        )

    result = np.empty(
        query.size,
        dtype=np.float64,
    )

    for output_index, raw_value in enumerate(
        query
    ):
        value = float(
            raw_value
        )

        position = bisect_left(
            group_values,
            value,
        )

        if position == len(
            group_values
        ):
            coordinate = Fraction(
                1,
                1,
            )

        elif (
            group_values[
                position
            ]
            == value
        ):
            coordinate = Fraction(
                (
                    2
                    * less_units[
                        position
                    ]
                    + equal_units[
                        position
                    ]
                ),
                2 * total_units,
            )

        elif position == 0:
            coordinate = Fraction(
                0,
                1,
            )

        else:
            coordinate = Fraction(
                less_units[
                    position
                ],
                total_units,
            )

        result[
            output_index
        ] = float(
            coordinate
        )

    return result


def project_matrix_through_baseline(
    baseline_values: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    baseline_species_ids: Sequence[Hashable],
    query_values: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
) -> npt.NDArray[np.float64]:
    """Project each unseen feature through its frozen baseline feature."""
    baseline = _validate_matrix(
        baseline_values,
        name="baseline_values",
    )

    query = _validate_matrix(
        query_values,
        name="query_values",
    )

    if (
        baseline.shape[1]
        != query.shape[1]
    ):
        raise ValueError(
            "baseline and query matrices must "
            "contain the same number of features"
        )

    species = _validate_species(
        baseline_species_ids,
        baseline.shape[0],
    )

    columns = [
        project_values_through_baseline(
            baseline[
                :,
                column,
            ],
            species,
            query[
                :,
                column,
            ],
        )
        for column in range(
            baseline.shape[1]
        )
    ]

    return np.column_stack(
        columns
    )


def projection_out_of_range_counts(
    baseline_values: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    query_values: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
) -> tuple[
    tuple[int, ...],
    tuple[int, ...],
]:
    """Return per-feature below-minimum and above-maximum query counts."""
    baseline = _validate_matrix(
        baseline_values,
        name="baseline_values",
    )

    query = _validate_matrix(
        query_values,
        name="query_values",
    )

    if (
        baseline.shape[1]
        != query.shape[1]
    ):
        raise ValueError(
            "baseline and query matrices must "
            "contain the same number of features"
        )

    minima = np.min(
        baseline,
        axis=0,
    )

    maxima = np.max(
        baseline,
        axis=0,
    )

    below = tuple(
        int(value)
        for value in np.sum(
            query < minima,
            axis=0,
        )
    )

    above = tuple(
        int(value)
        for value in np.sum(
            query > maxima,
            axis=0,
        )
    )

    return (
        below,
        above,
    )


def cross_matrix_nearest_panel_distances(
    query_coordinates: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    panel_coordinates: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    *,
    chunk_size: int = 1024,
) -> npt.NDArray[np.float64]:
    """Return Euclidean distance from each query to its nearest panel row.

    Query and panel rows belong to different matrices. The panel is
    fixed and is never augmented with a query row.
    """
    query = _validate_matrix(
        query_coordinates,
        name="query_coordinates",
    )

    panel = _validate_matrix(
        panel_coordinates,
        name="panel_coordinates",
    )

    if (
        query.shape[1]
        != panel.shape[1]
    ):
        raise ValueError(
            "query and panel matrices must "
            "contain the same number of dimensions"
        )

    if (
        not isinstance(
            chunk_size,
            int,
        )
        or isinstance(
            chunk_size,
            bool,
        )
        or chunk_size <= 0
    ):
        raise ValueError(
            "chunk_size must be a positive integer"
        )

    result = np.empty(
        query.shape[0],
        dtype=np.float64,
    )

    for start in range(
        0,
        query.shape[0],
        chunk_size,
    ):
        stop = min(
            query.shape[0],
            start + chunk_size,
        )

        chunk = query[
            start:stop
        ]

        delta = (
            chunk[
                :,
                np.newaxis,
                :,
            ]
            - panel[
                np.newaxis,
                :,
                :,
            ]
        )

        squared = np.sum(
            delta * delta,
            axis=2,
            dtype=np.float64,
        )

        distances = np.sqrt(
            squared
        )

        result[
            start:stop
        ] = np.min(
            distances,
            axis=1,
        )

    return result


def holdout_weighted_p95(
    distances: Sequence[float]
    | npt.NDArray[np.floating],
    holdout_species_ids: Sequence[Hashable],
) -> float:
    """Return the frozen species-balanced holdout weighted p95."""
    return species_balanced_weighted_quantile(
        distances,
        holdout_species_ids,
        P95,
    )


def exact_six_size_product(
    values_by_n: Mapping[int, float],
) -> Fraction:
    """Return the exact product of six stored binary64 primary metrics."""
    observed_keys = set(
        values_by_n
    )

    expected_keys = set(
        PANEL_SIZES
    )

    if observed_keys != expected_keys:
        raise ValueError(
            "values_by_n must contain exactly "
            "N=10,20,50,100,200,500"
        )

    result = Fraction(
        1,
        1,
    )

    for panel_size in PANEL_SIZES:
        value = float(
            values_by_n[
                panel_size
            ]
        )

        if (
            not math.isfinite(
                value
            )
            or value < 0.0
        ):
            raise ValueError(
                "selector primary metrics must "
                "be finite and non-negative"
            )

        result *= Fraction.from_float(
            value
        )

    return result


def resolve_exact_products(
    ops_product: Fraction,
    sr_product: Fraction,
) -> str:
    """Resolve OPS versus SR using exact rational products only."""
    if not isinstance(
        ops_product,
        Fraction,
    ):
        raise TypeError(
            "ops_product must be a Fraction"
        )

    if not isinstance(
        sr_product,
        Fraction,
    ):
        raise TypeError(
            "sr_product must be a Fraction"
        )

    if ops_product < sr_product:
        return "OPS"

    if sr_product < ops_product:
        return "SR"

    return "UNRESOLVED"


def format_binary64(
    value: float,
) -> str:
    """Return deterministic high-precision binary64 text."""
    numeric = float(
        value
    )

    if not math.isfinite(
        numeric
    ):
        raise ValueError(
            "value must be finite"
        )

    return format(
        numeric,
        ".17g",
    )
