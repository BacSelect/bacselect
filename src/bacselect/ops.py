"""One-per-species selector for BacSelect selector v1."""

from __future__ import annotations

from fractions import Fraction
from typing import Hashable, Sequence

import numpy as np
import numpy.typing as npt

from bacselect.tie import tie_key


def _validate_inputs(
    coordinates: Sequence[Sequence[float]] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
    accessions: Sequence[str],
) -> tuple[npt.NDArray[np.float64], list[Hashable], list[str]]:
    """Validate common OPS selector inputs."""
    matrix = np.asarray(coordinates, dtype=np.float64)
    species = list(species_ids)
    accession_list = list(accessions)

    if matrix.ndim != 2:
        raise ValueError("coordinates must be a two-dimensional matrix")

    if matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError("coordinates must not be empty")

    if len(species) != matrix.shape[0]:
        raise ValueError(
            "coordinates and species_ids must contain the same number of rows"
        )

    if len(accession_list) != matrix.shape[0]:
        raise ValueError(
            "coordinates and accessions must contain the same number of rows"
        )

    if not np.all(np.isfinite(matrix)):
        raise ValueError("coordinates must contain only finite numbers")

    if any(item is None or item == "" for item in species):
        raise ValueError("species_ids must not contain missing values")

    if any(not accession for accession in accession_list):
        raise ValueError("accessions must not contain empty values")

    if len(set(accession_list)) != len(accession_list):
        raise ValueError("accessions must be unique")

    return matrix, species, accession_list


def _exact_centroid(
    coordinates: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Return an order-invariant centroid of binary64 coordinates.

    Each binary64 coordinate is converted to its exact rational value.
    Summation and division are exact; only the final centroid coordinate
    is converted back to binary64.
    """
    if coordinates.ndim != 2 or coordinates.shape[0] == 0:
        raise ValueError("centroid input must be a non-empty matrix")

    row_count = coordinates.shape[0]

    centroid = np.empty(
        coordinates.shape[1],
        dtype=np.float64,
    )

    for column in range(coordinates.shape[1]):
        total = sum(
            (
                Fraction.from_float(float(value))
                for value in coordinates[:, column]
            ),
            Fraction(0, 1),
        )

        centroid[column] = float(total / row_count)

    return centroid


def _squared_distances(
    coordinates: npt.NDArray[np.float64],
    point: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Return squared Euclidean distances from rows to one point."""
    differences = coordinates - point

    return np.einsum(
        "ij,ij->i",
        differences,
        differences,
    )


def _tie_resolved_minimum(
    values: npt.NDArray[np.float64],
    candidate_indices: npt.NDArray[np.int64],
    accessions: Sequence[str],
) -> int:
    """Return candidate index with minimum value, then frozen tie key."""
    candidate_values = values[candidate_indices]
    best_value = np.min(candidate_values)

    tied = candidate_indices[candidate_values == best_value]

    return min(
        (int(index) for index in tied),
        key=lambda index: tie_key(accessions[index]),
    )


def _tie_resolved_maximum(
    values: npt.NDArray[np.float64],
    candidate_indices: npt.NDArray[np.int64],
    accessions: Sequence[str],
) -> int:
    """Return candidate index with maximum value, then frozen tie key."""
    candidate_values = values[candidate_indices]
    best_value = np.max(candidate_values)

    tied = candidate_indices[candidate_values == best_value]

    return min(
        (int(index) for index in tied),
        key=lambda index: tie_key(accessions[index]),
    )


def ops_species_representatives(
    coordinates: Sequence[Sequence[float]] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
    accessions: Sequence[str],
) -> npt.NDArray[np.int64]:
    """Choose one genome nearest the centroid of each species.

    Exact distance ties are resolved by the frozen selector-v1 accession
    hash. Returned representatives are placed in deterministic tie-key
    order; that ordering is computational only and is not a scientific
    selection variable.
    """
    matrix, species, accession_list = _validate_inputs(
        coordinates,
        species_ids,
        accessions,
    )

    groups: dict[Hashable, list[int]] = {}

    for index, species_id in enumerate(species):
        groups.setdefault(species_id, []).append(index)

    representatives: list[int] = []

    for member_indices in groups.values():
        members = np.asarray(
            member_indices,
            dtype=np.int64,
        )

        centroid = _exact_centroid(matrix[members])
        distances = _squared_distances(
            matrix[members],
            centroid,
        )

        local_candidates = np.arange(
            members.size,
            dtype=np.int64,
        )

        local_choice = _tie_resolved_minimum(
            distances,
            local_candidates,
            [accession_list[index] for index in members],
        )

        representatives.append(
            int(members[local_choice])
        )

    representatives.sort(
        key=lambda index: tie_key(accession_list[index])
    )

    return np.asarray(
        representatives,
        dtype=np.int64,
    )


def ops_ladder(
    coordinates: Sequence[Sequence[float]] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
    accessions: Sequence[str],
    max_n: int,
) -> npt.NDArray[np.int64]:
    """Return the nested OPS ladder through ``max_n`` genomes.

    The first genome is the species representative nearest the centroid
    of all species representatives. Each subsequent genome maximizes its
    minimum squared Euclidean distance to the selected set.
    """
    matrix, species, accession_list = _validate_inputs(
        coordinates,
        species_ids,
        accessions,
    )

    representatives = ops_species_representatives(
        matrix,
        species,
        accession_list,
    )

    representative_count = representatives.size

    if not isinstance(max_n, int):
        raise TypeError("max_n must be an integer")

    if max_n < 1 or max_n > representative_count:
        raise ValueError(
            "max_n must be between 1 and the number of species representatives"
        )

    representative_coordinates = matrix[representatives]

    global_centroid = _exact_centroid(
        representative_coordinates
    )

    first_distances = _squared_distances(
        representative_coordinates,
        global_centroid,
    )

    local_candidates = np.arange(
        representative_count,
        dtype=np.int64,
    )

    representative_accessions = [
        accession_list[index]
        for index in representatives
    ]

    first_local = _tie_resolved_minimum(
        first_distances,
        local_candidates,
        representative_accessions,
    )

    selected_local = [first_local]

    selected_mask = np.zeros(
        representative_count,
        dtype=bool,
    )
    selected_mask[first_local] = True

    nearest_squared = _squared_distances(
        representative_coordinates,
        representative_coordinates[first_local],
    )
    nearest_squared[first_local] = 0.0

    while len(selected_local) < max_n:
        remaining = np.flatnonzero(~selected_mask)

        next_local = _tie_resolved_maximum(
            nearest_squared,
            remaining,
            representative_accessions,
        )

        selected_local.append(next_local)
        selected_mask[next_local] = True

        distances = _squared_distances(
            representative_coordinates,
            representative_coordinates[next_local],
        )

        nearest_squared = np.minimum(
            nearest_squared,
            distances,
        )

        nearest_squared[selected_mask] = 0.0

    return representatives[
        np.asarray(selected_local, dtype=np.int64)
    ]
