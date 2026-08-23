import numpy as np
import pytest

from bacselect.random_baseline import random_ladders


def _toy_data() -> tuple[list[str], list[str]]:
    species = [
        "A",
        "A",
        "B",
        "B",
        "C",
        "D",
        "E",
        "E",
    ]

    accessions = [
        "A0",
        "A1",
        "B0",
        "B1",
        "C0",
        "D0",
        "E0",
        "E1",
    ]

    return species, accessions


def test_random_ladders_have_expected_shape() -> None:
    species, accessions = _toy_data()

    observed = random_ladders(
        species,
        accessions,
        max_n=4,
        replicates=7,
        seed=20260824,
    )

    assert observed.shape == (7, 4)
    assert observed.dtype == np.int64


def test_each_ladder_contains_distinct_species() -> None:
    species, accessions = _toy_data()

    ladders = random_ladders(
        species,
        accessions,
        max_n=5,
        replicates=20,
        seed=20260824,
    )

    for ladder in ladders:
        selected_species = [
            species[index]
            for index in ladder
        ]

        assert len(selected_species) == 5
        assert len(set(selected_species)) == 5


def test_random_ladder_genomes_are_unique() -> None:
    species, accessions = _toy_data()

    ladders = random_ladders(
        species,
        accessions,
        max_n=5,
        replicates=20,
        seed=20260824,
    )

    for ladder in ladders:
        assert np.unique(ladder).size == ladder.size


def test_same_seed_is_byte_identical() -> None:
    species, accessions = _toy_data()

    first = random_ladders(
        species,
        accessions,
        max_n=5,
        replicates=25,
        seed=20260824,
    )

    second = random_ladders(
        species,
        accessions,
        max_n=5,
        replicates=25,
        seed=20260824,
    )

    assert first.tobytes() == second.tobytes()


def test_different_seed_changes_ladders() -> None:
    species, accessions = _toy_data()

    first = random_ladders(
        species,
        accessions,
        max_n=5,
        replicates=10,
        seed=20260824,
    )

    second = random_ladders(
        species,
        accessions,
        max_n=5,
        replicates=10,
        seed=20260825,
    )

    assert not np.array_equal(first, second)


def test_replicates_use_one_sequential_generator_state() -> None:
    species, accessions = _toy_data()

    together = random_ladders(
        species,
        accessions,
        max_n=5,
        replicates=2,
        seed=20260824,
    )

    first_only = random_ladders(
        species,
        accessions,
        max_n=5,
        replicates=1,
        seed=20260824,
    )

    np.testing.assert_array_equal(
        together[0],
        first_only[0],
    )

    assert not np.array_equal(
        together[1],
        first_only[0],
    )


def test_prefixes_are_nested_within_each_ladder() -> None:
    species, accessions = _toy_data()

    ladders = random_ladders(
        species,
        accessions,
        max_n=5,
        replicates=10,
        seed=20260824,
    )

    for ladder in ladders:
        prefix_2 = ladder[:2]
        prefix_3 = ladder[:3]
        prefix_5 = ladder[:5]

        np.testing.assert_array_equal(
            prefix_2,
            prefix_3[:2],
        )

        np.testing.assert_array_equal(
            prefix_3,
            prefix_5[:3],
        )


def test_input_order_invariance() -> None:
    species, accessions = _toy_data()

    species_array = np.asarray(
        species,
        dtype=object,
    )
    accession_array = np.asarray(
        accessions,
        dtype=object,
    )

    expected = random_ladders(
        species_array,
        accession_array,
        max_n=5,
        replicates=20,
        seed=20260824,
    )

    expected_accessions = [
        [
            str(accession_array[index])
            for index in ladder
        ]
        for ladder in expected
    ]

    permutation = np.array(
        [7, 2, 0, 5, 3, 1, 6, 4]
    )

    observed = random_ladders(
        species_array[permutation],
        accession_array[permutation],
        max_n=5,
        replicates=20,
        seed=20260824,
    )

    permuted_accessions = accession_array[permutation]

    observed_accessions = [
        [
            str(permuted_accessions[index])
            for index in ladder
        ]
        for ladder in observed
    ]

    assert observed_accessions == expected_accessions


def test_one_genome_is_drawn_from_each_selected_species() -> None:
    species = ["A", "A", "B", "B", "C"]
    accessions = ["A0", "A1", "B0", "B1", "C0"]

    ladders = random_ladders(
        species,
        accessions,
        max_n=3,
        replicates=100,
        seed=20260824,
    )

    for ladder in ladders:
        selected_species = [
            species[index]
            for index in ladder
        ]

        assert set(selected_species) == {"A", "B", "C"}


def test_rejects_duplicate_accessions() -> None:
    with pytest.raises(ValueError, match="unique"):
        random_ladders(
            ["A", "B"],
            ["same", "same"],
            max_n=2,
            replicates=1,
        )


def test_rejects_max_n_larger_than_species_count() -> None:
    with pytest.raises(ValueError, match="number of species groups"):
        random_ladders(
            ["A", "A", "B"],
            ["A0", "A1", "B0"],
            max_n=3,
            replicates=1,
        )


def test_rejects_zero_replicates() -> None:
    species, accessions = _toy_data()

    with pytest.raises(ValueError, match="at least 1"):
        random_ladders(
            species,
            accessions,
            max_n=5,
            replicates=0,
        )


def test_rejects_negative_seed() -> None:
    species, accessions = _toy_data()

    with pytest.raises(ValueError, match="negative"):
        random_ladders(
            species,
            accessions,
            max_n=5,
            replicates=1,
            seed=-1,
        )
