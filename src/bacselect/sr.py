"""Species-residual selector for BacSelect selector v1."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Hashable, Sequence

import numpy as np
import numpy.typing as npt

from bacselect.tie import species_tie_key, tie_key


def _validate_inputs(
    coordinates: Sequence[Sequence[float]] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
    accessions: Sequence[str],
) -> tuple[npt.NDArray[np.float64], list[Hashable], list[str]]:
    """Validate common SR selector inputs."""
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
    """Return an order-invariant centroid of binary64 coordinates."""
    if coordinates.ndim != 2 or coordinates.shape[0] == 0:
        raise ValueError("centroid input must be a non-empty matrix")

    centroid = np.empty(
        coordinates.shape[1],
        dtype=np.float64,
    )

    row_count = coordinates.shape[0]

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


def _species_groups(
    species_ids: Sequence[Hashable],
    accessions: Sequence[str],
) -> list[tuple[Hashable, npt.NDArray[np.int64], str]]:
    """Return species groups in deterministic identity-neutral order."""
    raw_groups: dict[Hashable, list[int]] = {}

    for index, species_id in enumerate(species_ids):
        raw_groups.setdefault(species_id, []).append(index)

    groups: list[
        tuple[Hashable, npt.NDArray[np.int64], str]
    ] = []

    for species_id, indices in raw_groups.items():
        ordered_indices = sorted(
            indices,
            key=lambda index: accessions[index],
        )

        member_accessions = [
            accessions[index]
            for index in ordered_indices
        ]

        groups.append(
            (
                species_id,
                np.asarray(ordered_indices, dtype=np.int64),
                species_tie_key(member_accessions),
            )
        )

    groups.sort(key=lambda item: item[2])

    return groups


def _choose_species_minimum(
    values: npt.NDArray[np.float64],
    candidate_indices: npt.NDArray[np.int64],
    species_keys: Sequence[str],
) -> int:
    """Choose minimum species score, then frozen species tie key."""
    candidate_values = values[candidate_indices]
    best_value = np.min(candidate_values)

    tied = candidate_indices[candidate_values == best_value]

    return min(
        (int(index) for index in tied),
        key=lambda index: species_keys[index],
    )


def _choose_species_maximum(
    values: npt.NDArray[np.float64],
    candidate_indices: npt.NDArray[np.int64],
    species_keys: Sequence[str],
) -> int:
    """Choose maximum species score, then frozen species tie key."""
    candidate_values = values[candidate_indices]
    best_value = np.max(candidate_values)

    tied = candidate_indices[candidate_values == best_value]

    return min(
        (int(index) for index in tied),
        key=lambda index: species_keys[index],
    )


def _choose_genome_minimum(
    values: npt.NDArray[np.float64],
    candidate_indices: npt.NDArray[np.int64],
    accessions: Sequence[str],
) -> int:
    """Choose minimum genome score, then frozen genome tie key."""
    candidate_values = values[candidate_indices]
    best_value = np.min(candidate_values)

    tied = candidate_indices[candidate_values == best_value]

    return min(
        (int(index) for index in tied),
        key=lambda index: tie_key(accessions[index]),
    )


def _choose_genome_maximum(
    values: npt.NDArray[np.float64],
    candidate_indices: npt.NDArray[np.int64],
    accessions: Sequence[str],
) -> int:
    """Choose maximum genome score, then frozen genome tie key."""
    candidate_values = values[candidate_indices]
    best_value = np.max(candidate_values)

    tied = candidate_indices[candidate_values == best_value]

    return min(
        (int(index) for index in tied),
        key=lambda index: tie_key(accessions[index]),
    )


def sr_ladder(
    coordinates: Sequence[Sequence[float]] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
    accessions: Sequence[str],
    max_n: int,
) -> npt.NDArray[np.int64]:
    """Return the deterministic nested species-residual ladder."""
    matrix, species, accession_list = _validate_inputs(
        coordinates,
        species_ids,
        accessions,
    )

    if not isinstance(max_n, int):
        raise TypeError("max_n must be an integer")

    if max_n < 1 or max_n > matrix.shape[0]:
        raise ValueError(
            "max_n must be between 1 and the number of eligible genomes"
        )

    groups = _species_groups(
        species,
        accession_list,
    )

    group_count = len(groups)

    centroids = np.vstack(
        [
            _exact_centroid(matrix[members])
            for _, members, _ in groups
        ]
    )

    global_centroid = _exact_centroid(centroids)

    centroid_distances = _squared_distances(
        centroids,
        global_centroid,
    )

    species_keys = [
        species_key
        for _, _, species_key in groups
    ]

    all_groups = np.arange(
        group_count,
        dtype=np.int64,
    )

    first_group = _choose_species_minimum(
        centroid_distances,
        all_groups,
        species_keys,
    )

    first_members = groups[first_group][1]

    genome_distances = _squared_distances(
        matrix,
        global_centroid,
    )

    first_genome = _choose_genome_minimum(
        genome_distances,
        first_members,
        accession_list,
    )

    selected = [first_genome]

    selected_mask = np.zeros(
        matrix.shape[0],
        dtype=bool,
    )
    selected_mask[first_genome] = True

    nearest_squared = _squared_distances(
        matrix,
        matrix[first_genome],
    )
    nearest_squared[first_genome] = 0.0

    while len(selected) < max_n:
        residual_scores = np.full(
            group_count,
            -np.inf,
            dtype=np.float64,
        )

        eligible_groups: list[int] = []

        for group_index, (_, members, _) in enumerate(groups):
            if np.all(selected_mask[members]):
                continue

            eligible_groups.append(group_index)

            residual_scores[group_index] = (
                math.fsum(
                    float(nearest_squared[index])
                    for index in members
                )
                / members.size
            )

        if not eligible_groups:
            raise RuntimeError(
                "no eligible species remain before requested max_n"
            )

        chosen_group = _choose_species_maximum(
            residual_scores,
            np.asarray(
                eligible_groups,
                dtype=np.int64,
            ),
            species_keys,
        )

        members = groups[chosen_group][1]

        unselected_members = members[
            ~selected_mask[members]
        ]

        next_genome = _choose_genome_maximum(
            nearest_squared,
            unselected_members,
            accession_list,
        )

        selected.append(next_genome)
        selected_mask[next_genome] = True

        distances = _squared_distances(
            matrix,
            matrix[next_genome],
        )

        nearest_squared = np.minimum(
            nearest_squared,
            distances,
        )

        nearest_squared[selected_mask] = 0.0

    return np.asarray(
        selected,
        dtype=np.int64,
    )
