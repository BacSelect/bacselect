import itertools

import pytest

from bacselect.source_fingerprint import (
    FINGERPRINT_SCHEMA,
    assembly_fingerprint,
    canonical_circular,
    canonical_linear,
    component_sequence_hash,
    fingerprint_components,
    minimal_rotation,
    normalize_sequence,
    reverse_complement,
)


def brute_minimal_rotation(sequence):
    return min(
        sequence[index:] + sequence[:index]
        for index in range(len(sequence))
    )


def rotations(sequence):
    return tuple(
        sequence[index:] + sequence[:index]
        for index in range(len(sequence))
    )


def test_schema_is_exactly_frozen():
    assert FINGERPRINT_SCHEMA == (
        "project-finch-topology-aware-sequence-v1"
    )


def test_normalization_uppercases_sequence():
    assert normalize_sequence("acgt") == "ACGT"


@pytest.mark.parametrize(
    "sequence",
    [
        "",
        "ACGN",
        "ACG-",
        "ACGT ",
    ],
)
def test_sequence_validation_fails_closed(sequence):
    with pytest.raises(ValueError):
        normalize_sequence(sequence)


def test_non_string_sequence_rejected():
    with pytest.raises(TypeError):
        normalize_sequence(b"ACGT")


def test_reverse_complement():
    assert reverse_complement("AAGTC") == "GACTT"


def test_minimal_rotation_matches_brute_force_exhaustively():
    for length in range(1, 7):
        for symbols in itertools.product(
            "ACGT",
            repeat=length,
        ):
            sequence = "".join(symbols)

            assert minimal_rotation(sequence) == (
                brute_minimal_rotation(sequence)
            )


def test_linear_canonicalization_is_strand_invariant():
    sequence = "AAACCGT"

    assert canonical_linear(sequence) == canonical_linear(
        reverse_complement(sequence)
    )


def test_linear_canonicalization_is_not_origin_invariant():
    sequence = "AAACCGT"

    values = {
        canonical_linear(rotation)
        for rotation in rotations(sequence)
    }

    assert len(values) > 1


def test_circular_canonicalization_is_origin_invariant():
    sequence = "AAACCGT"

    expected = canonical_circular(sequence)

    assert {
        canonical_circular(rotation)
        for rotation in rotations(sequence)
    } == {expected}


def test_circular_canonicalization_is_strand_invariant():
    sequence = "AAACCGT"

    assert canonical_circular(sequence) == canonical_circular(
        reverse_complement(sequence)
    )


def test_component_hash_is_linear_strand_invariant():
    sequence = "AACCGGTA"

    assert component_sequence_hash(
        sequence,
        "linear",
    ) == component_sequence_hash(
        reverse_complement(sequence),
        "linear",
    )


def test_component_hash_is_circular_origin_invariant():
    sequence = "AACCGGTA"

    expected = component_sequence_hash(
        sequence,
        "circular",
    )

    for rotation in rotations(sequence):
        assert component_sequence_hash(
            rotation,
            "circular",
        ) == expected


def test_component_hash_rejects_unknown_topology():
    with pytest.raises(ValueError, match="unsupported topology"):
        component_sequence_hash(
            "ACGT",
            "unknown",
        )


def test_assembly_fingerprint_is_component_order_independent():
    first = component_sequence_hash(
        "AAAACCCC",
        "linear",
    )
    second = component_sequence_hash(
        "ACGTACGT",
        "circular",
    )

    assert assembly_fingerprint(
        (
            ("linear", first),
            ("circular", second),
        )
    ) == assembly_fingerprint(
        (
            ("circular", second),
            ("linear", first),
        )
    )


def test_assembly_fingerprint_preserves_component_multiplicity():
    value = component_sequence_hash(
        "AAAACCCC",
        "linear",
    )

    assert assembly_fingerprint(
        (("linear", value),)
    ) != assembly_fingerprint(
        (
            ("linear", value),
            ("linear", value),
        )
    )


def test_topology_is_part_of_assembly_identity():
    value = component_sequence_hash(
        "ACGTACGT",
        "linear",
    )

    assert assembly_fingerprint(
        (("linear", value),)
    ) != assembly_fingerprint(
        (("circular", value),)
    )


def test_fingerprint_components_is_order_independent():
    left = (
        ("linear", "AAAACCCC"),
        ("circular", "AACCGGTT"),
    )
    right = tuple(reversed(left))

    assert fingerprint_components(left) == fingerprint_components(right)


def test_empty_assembly_rejected():
    with pytest.raises(ValueError, match="at least one"):
        assembly_fingerprint(())


def test_invalid_component_hash_rejected():
    with pytest.raises(ValueError, match="lowercase SHA256"):
        assembly_fingerprint(
            (("linear", "not-a-sha"),)
        )
