"""Species-balanced random baseline for BacSelect selector v1."""

from __future__ import annotations

from typing import Hashable, Sequence

import numpy as np
import numpy.typing as npt

from bacselect.tie import species_tie_key, tie_key


DEFAULT_SEED = 20260824
DEFAULT_REPLICATES = 1000
DEFAULT_MAX_N = 500


def _validate_inputs(
    species_ids: Sequence[Hashable],
    accessions: Sequence[str],
) -> tuple[list[Hashable], list[str]]:
    """Validate random-baseline membership inputs."""
    species = list(species_ids)
    accession_list = list(accessions)

    if not species:
        raise ValueError("species_ids must not be empty")

    if len(species) != len(accession_list):
        raise ValueError(
            "species_ids and accessions must contain the same number of rows"
        )

    if any(item is None or item == "" for item in species):
        raise ValueError("species_ids must not contain missing values")

    if any(not accession for accession in accession_list):
        raise ValueError("accessions must not contain empty values")

    if len(set(accession_list)) != len(accession_list):
        raise ValueError("accessions must be unique")

    return species, accession_list


def _ordered_species_groups(
    species_ids: Sequence[Hashable],
    accessions: Sequence[str],
) -> list[npt.NDArray[np.int64]]:
    """Return groups in frozen identity-neutral RNG input order."""
    raw_groups: dict[Hashable, list[int]] = {}

    for index, species_id in enumerate(species_ids):
        raw_groups.setdefault(species_id, []).append(index)

    keyed_groups: list[
        tuple[str, npt.NDArray[np.int64]]
    ] = []

    for indices in raw_groups.values():
        ordered_indices = sorted(
            indices,
            key=lambda index: tie_key(accessions[index]),
        )

        member_accessions = [
            accessions[index]
            for index in ordered_indices
        ]

        keyed_groups.append(
            (
                species_tie_key(member_accessions),
                np.asarray(
                    ordered_indices,
                    dtype=np.int64,
                ),
            )
        )

    keyed_groups.sort(key=lambda item: item[0])

    return [
        members
        for _, members in keyed_groups
    ]


def _validate_sampling_parameters(
    species_count: int,
    max_n: int,
    replicates: int,
    seed: int,
) -> None:
    """Validate deterministic random-baseline parameters."""
    for name, value in (
        ("max_n", max_n),
        ("replicates", replicates),
        ("seed", seed),
    ):
        if isinstance(value, (bool, np.bool_)) or not isinstance(
            value,
            (int, np.integer),
        ):
            raise TypeError(f"{name} must be an integer")

    if max_n < 1 or max_n > species_count:
        raise ValueError(
            "max_n must be between 1 and the number of species groups"
        )

    if replicates < 1:
        raise ValueError("replicates must be at least 1")

    if seed < 0:
        raise ValueError("seed must not be negative")


def _draw_ladder(
    groups: Sequence[npt.NDArray[np.int64]],
    rng: np.random.Generator,
    max_n: int,
) -> npt.NDArray[np.int64]:
    """Draw one nested species-balanced random ladder.

    Species are sampled uniformly without replacement using Generator.choice
    with shuffle=True. One Generator.integers call is then made for every
    sampled species, including species containing only one eligible genome.
    """
    chosen_groups = rng.choice(
        len(groups),
        size=max_n,
        replace=False,
        shuffle=True,
    )

    selected = np.empty(
        max_n,
        dtype=np.int64,
    )

    for position, group_index in enumerate(chosen_groups):
        members = groups[int(group_index)]

        member_position = int(
            rng.integers(
                low=0,
                high=members.size,
            )
        )

        selected[position] = members[member_position]

    return selected


def random_ladders(
    species_ids: Sequence[Hashable],
    accessions: Sequence[str],
    *,
    max_n: int = DEFAULT_MAX_N,
    replicates: int = DEFAULT_REPLICATES,
    seed: int = DEFAULT_SEED,
) -> npt.NDArray[np.int64]:
    """Generate deterministic species-balanced random replicate ladders.

    A single Generator(PCG64(seed)) instance is used sequentially for all
    replicate ladders, as frozen for selector-v1 validation.
    """
    species, accession_list = _validate_inputs(
        species_ids,
        accessions,
    )

    groups = _ordered_species_groups(
        species,
        accession_list,
    )

    _validate_sampling_parameters(
        len(groups),
        max_n,
        replicates,
        seed,
    )

    rng = np.random.Generator(
        np.random.PCG64(int(seed))
    )

    ladders = np.empty(
        (replicates, max_n),
        dtype=np.int64,
    )

    for replicate in range(replicates):
        ladders[replicate] = _draw_ladder(
            groups,
            rng,
            max_n,
        )

    return ladders
