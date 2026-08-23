"""Coverage metrics for BacSelect selector validation."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from typing import Hashable, Sequence

import numpy as np
import numpy.typing as npt


MEDIAN = Fraction(1, 2)
P95 = Fraction(19, 20)


@dataclass(frozen=True)
class CoverageSummary:
    """Pre-specified BacSelect coverage metrics for one panel."""

    weighted_mean: float
    weighted_median: float
    weighted_p95: float
    unweighted_max: float
    median_species_mean: float
    p95_species_mean: float
    max_species_mean: float
    median_species_max: float
    p95_species_max: float
    max_species_max: float


def _validate_quantile(q: Fraction) -> None:
    """Require a quantile strictly within the closed unit interval."""
    if not isinstance(q, Fraction):
        raise TypeError("q must be a fractions.Fraction")

    if q < 0 or q > 1:
        raise ValueError("q must be between 0 and 1")


def _validate_distances(
    distances: Sequence[float] | npt.NDArray[np.floating],
) -> npt.NDArray[np.float64]:
    """Validate one vector of nearest-panel distances."""
    array = np.asarray(distances, dtype=np.float64)

    if array.ndim != 1:
        raise ValueError("distances must be one-dimensional")

    if array.size == 0:
        raise ValueError("distances must not be empty")

    if not np.all(np.isfinite(array)):
        raise ValueError("distances must contain only finite values")

    if np.any(array < 0.0):
        raise ValueError("distances must not contain negative values")

    return array


def _validate_species(
    species_ids: Sequence[Hashable],
    expected_rows: int,
) -> list[Hashable]:
    """Validate species assignments for metric evaluation."""
    species = list(species_ids)

    if len(species) != expected_rows:
        raise ValueError(
            "distances and species_ids must contain the same number of rows"
        )

    if any(item is None or item == "" for item in species):
        raise ValueError("species_ids must not contain missing values")

    return species


def _stable_mean(values: Sequence[float]) -> float:
    """Return an input-order-independent binary64 arithmetic mean."""
    ordered = sorted(float(value) for value in values)

    if not ordered:
        raise ValueError("mean input must not be empty")

    return math.fsum(ordered) / len(ordered)


def nearest_panel_distances(
    coordinates: Sequence[Sequence[float]] | npt.NDArray[np.floating],
    panel_indices: Sequence[int] | npt.NDArray[np.integer],
) -> npt.NDArray[np.float64]:
    """Return nearest-panel Euclidean distance for every genome."""
    matrix = np.asarray(coordinates, dtype=np.float64)

    if matrix.ndim != 2:
        raise ValueError("coordinates must be a two-dimensional matrix")

    if matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError("coordinates must not be empty")

    if not np.all(np.isfinite(matrix)):
        raise ValueError("coordinates must contain only finite values")

    raw_indices = list(panel_indices)

    if not raw_indices:
        raise ValueError("panel_indices must not be empty")

    if any(
        isinstance(index, (bool, np.bool_))
        or not isinstance(index, (int, np.integer))
        for index in raw_indices
    ):
        raise TypeError("panel_indices must contain only integers")

    indices = np.asarray(raw_indices, dtype=np.int64)

    if np.any(indices < 0) or np.any(indices >= matrix.shape[0]):
        raise ValueError("panel_indices contain an out-of-range index")

    if np.unique(indices).size != indices.size:
        raise ValueError("panel_indices must be unique")

    nearest_squared = np.full(
        matrix.shape[0],
        np.inf,
        dtype=np.float64,
    )

    for index in indices:
        differences = matrix - matrix[index]

        squared = np.einsum(
            "ij,ij->i",
            differences,
            differences,
        )

        nearest_squared = np.minimum(
            nearest_squared,
            squared,
        )

    nearest_squared[indices] = 0.0

    return np.sqrt(nearest_squared)


def inverse_ecdf_quantile(
    values: Sequence[float] | npt.NDArray[np.floating],
    q: Fraction,
) -> float:
    """Return the unweighted inverse-ECDF quantile without interpolation."""
    _validate_quantile(q)

    array = _validate_distances(values)
    ordered = np.sort(array)

    if q == 0:
        return float(ordered[0])

    target_rank = (
        q.numerator * ordered.size
        + q.denominator
        - 1
    ) // q.denominator

    return float(ordered[target_rank - 1])


def species_balanced_weighted_quantile(
    distances: Sequence[float] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
    q: Fraction,
) -> float:
    """Return an exact-weight species-balanced inverse-ECDF quantile.

    Every genome in species ``s`` receives weight ``1 / n_s``. Species
    weights are converted to exact integer units using the least common
    multiple of the observed species sizes, so the quantile threshold
    comparison requires no floating-point weight accumulation.
    """
    _validate_quantile(q)

    array = _validate_distances(distances)
    species = _validate_species(species_ids, array.size)

    counts = Counter(species)
    common_denominator = math.lcm(*counts.values())

    weight_units = {
        species_id: common_denominator // count
        for species_id, count in counts.items()
    }

    total_units = common_denominator * len(counts)

    if q == 0:
        return float(np.min(array))

    target_left = q.numerator * total_units
    target_denominator = q.denominator

    order = np.argsort(array, kind="stable")
    cumulative_units = 0

    for index in order:
        cumulative_units += weight_units[species[int(index)]]

        if cumulative_units * target_denominator >= target_left:
            return float(array[int(index)])

    raise RuntimeError("weighted quantile threshold was not reached")


def species_distance_statistics(
    distances: Sequence[float] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Return per-species mean and maximum nearest-panel distances."""
    array = _validate_distances(distances)
    species = _validate_species(species_ids, array.size)

    groups: dict[Hashable, list[float]] = {}

    for distance, species_id in zip(array, species):
        groups.setdefault(species_id, []).append(float(distance))

    means = np.fromiter(
        (
            _stable_mean(values)
            for values in groups.values()
        ),
        dtype=np.float64,
        count=len(groups),
    )

    maxima = np.fromiter(
        (
            max(values)
            for values in groups.values()
        ),
        dtype=np.float64,
        count=len(groups),
    )

    return means, maxima


def species_balanced_weighted_mean(
    distances: Sequence[float] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
) -> float:
    """Return the species-balanced weighted mean nearest-panel distance."""
    means, _ = species_distance_statistics(
        distances,
        species_ids,
    )

    return _stable_mean(means)


def coverage_summary(
    distances: Sequence[float] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
) -> CoverageSummary:
    """Return all pre-specified deterministic coverage metrics."""
    array = _validate_distances(distances)
    species = _validate_species(species_ids, array.size)

    species_means, species_maxima = species_distance_statistics(
        array,
        species,
    )

    return CoverageSummary(
        weighted_mean=species_balanced_weighted_mean(
            array,
            species,
        ),
        weighted_median=species_balanced_weighted_quantile(
            array,
            species,
            MEDIAN,
        ),
        weighted_p95=species_balanced_weighted_quantile(
            array,
            species,
            P95,
        ),
        unweighted_max=float(np.max(array)),
        median_species_mean=inverse_ecdf_quantile(
            species_means,
            MEDIAN,
        ),
        p95_species_mean=inverse_ecdf_quantile(
            species_means,
            P95,
        ),
        max_species_mean=float(np.max(species_means)),
        median_species_max=inverse_ecdf_quantile(
            species_maxima,
            MEDIAN,
        ),
        p95_species_max=inverse_ecdf_quantile(
            species_maxima,
            P95,
        ),
        max_species_max=float(np.max(species_maxima)),
    )
