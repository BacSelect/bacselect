import hashlib

import pytest

from bacselect.source_truth import (
    EXCLUDE,
    SUITABLE,
    UNRESOLVED,
    circular_inner_containment,
    classify,
    containment_relation,
    duplicate_relation,
    reverse_complement,
    sequence_set_sha256,
)


def component(
    sequence,
    topology,
):
    return {
        "sequence": sequence,
        "topology": topology,
    }


def test_reverse_complement():
    assert reverse_complement(
        "AAGTCCGA"
    ) == "TCGGACTT"


def test_exact_forward_duplicate():
    assert duplicate_relation(
        component(
            "AACCGGTT",
            "linear",
        ),
        component(
            "AACCGGTT",
            "linear",
        ),
    ) == "exact_forward"


def test_exact_reverse_complement_duplicate():
    assert duplicate_relation(
        component(
            "AAGTCCGA",
            "linear",
        ),
        component(
            "TCGGACTT",
            "linear",
        ),
    ) == "exact_reverse_complement"


def test_circular_rotation_duplicate():
    assert duplicate_relation(
        component(
            "GGTTAACC",
            "circular",
        ),
        component(
            "AACCGGTT",
            "circular",
        ),
    ) == "circular_rotation_forward"


def test_circular_rotation_not_applied_to_linear_pair():
    assert duplicate_relation(
        component(
            "GGTTAACC",
            "linear",
        ),
        component(
            "AACCGGTT",
            "linear",
        ),
    ) is None


def test_unequal_length_is_not_duplicate():
    assert duplicate_relation(
        component(
            "ACGT",
            "linear",
        ),
        component(
            "ACGTA",
            "linear",
        ),
    ) is None


def test_invalid_topology_fails_closed():
    with pytest.raises(
        ValueError,
        match="unsupported topology",
    ):
        duplicate_relation(
            component(
                "ACGT",
                "unknown",
            ),
            component(
                "ACGT",
                "linear",
            ),
        )


def test_invalid_sequence_fails_closed():
    with pytest.raises(
        ValueError,
        match="unsupported symbols",
    ):
        containment_relation(
            component(
                "ACGN",
                "linear",
            ),
            component(
                "AAAACGNT",
                "linear",
            ),
        )


def test_linear_forward_containment():
    assert containment_relation(
        component(
            "CCCC",
            "linear",
        ),
        component(
            "AAAACCCC",
            "linear",
        ),
    ) == (
        "forward",
        False,
    )


def test_linear_reverse_complement_containment():
    assert containment_relation(
        component(
            "AAGT",
            "linear",
        ),
        component(
            "CCCACTTGG",
            "linear",
        ),
    ) == (
        "reverse_complement",
        False,
    )


def test_linear_containment_across_circular_outer_origin():
    assert containment_relation(
        component(
            "TTAA",
            "linear",
        ),
        component(
            "AACCGGTT",
            "circular",
        ),
    ) == (
        "forward",
        True,
    )


def test_equal_length_is_not_containment():
    assert containment_relation(
        component(
            "AACCGGTT",
            "linear",
        ),
        component(
            "AACCGGTT",
            "linear",
        ),
    ) is None


def test_circular_inner_shifted_origin_containment():
    assert containment_relation(
        component(
            "AACCGGTT",
            "circular",
        ),
        component(
            "TTTGGTTAACCGA",
            "linear",
        ),
    ) == (
        "forward",
        False,
    )


def test_circular_inner_shifted_origin_reverse_containment():
    assert containment_relation(
        component(
            "AAGTCCGA",
            "circular",
        ),
        component(
            "CCCGACTTTCGAAA",
            "linear",
        ),
    ) == (
        "reverse_complement",
        False,
    )


def test_circular_inner_crosses_circular_outer_origin():
    assert containment_relation(
        component(
            "AACCGGTT",
            "circular",
        ),
        component(
            "TAACCGGGGTT",
            "circular",
        ),
    ) == (
        "forward",
        True,
    )


def test_circular_inner_containment_requires_shorter_inner():
    assert circular_inner_containment(
        "ACGT",
        "ACGT",
        False,
    ) is None


def test_sequence_set_hash_is_component_order_independent():
    first = {
        "B": component(
            "CCCC",
            "linear",
        ),
        "A": component(
            "AAAA",
            "circular",
        ),
    }

    second = {
        "A": component(
            "AAAA",
            "circular",
        ),
        "B": component(
            "CCCC",
            "linear",
        ),
    }

    assert sequence_set_sha256(
        first
    ) == sequence_set_sha256(
        second
    )


def test_sequence_set_hash_matches_frozen_byte_contract():
    components = {
        "A": component(
            "AAAA",
            "circular",
        ),
        "B": component(
            "CCCC",
            "linear",
        ),
    }

    expected_payload = (
        "A\t4\t"
        + hashlib.sha256(
            b"AAAA"
        ).hexdigest()
        + "\n"
        + "B\t4\t"
        + hashlib.sha256(
            b"CCCC"
        ).hexdigest()
        + "\n"
    ).encode(
        "ascii"
    )

    expected = hashlib.sha256(
        expected_payload
    ).hexdigest()

    assert sequence_set_sha256(
        components
    ) == expected


def test_sequence_set_preserves_component_names():
    left = {
        "A": component(
            "AAAA",
            "linear",
        ),
    }

    right = {
        "B": component(
            "AAAA",
            "linear",
        ),
    }

    assert sequence_set_sha256(
        left
    ) != sequence_set_sha256(
        right
    )


def test_empty_sequence_set_rejected():
    with pytest.raises(
        ValueError,
        match="at least one",
    ):
        sequence_set_sha256({})


def test_duplicate_rule_has_highest_precedence():
    decision = classify(
        1,
        (
            {
                "inner_topology":
                    "linear",
            },
        ),
    )

    assert decision == (
        EXCLUDE,
        "EXACT_DUPLICATE_PRIMARY_COMPONENTS",
        (
            "one or more distinct Primary Assembly components "
            "have sequence-equivalent complete molecules"
        ),
    )


def test_linear_containment_is_excluded():
    decision = classify(
        0,
        (
            {
                "inner_topology":
                    "linear",
            },
        ),
    )

    assert decision[0] == EXCLUDE
    assert decision[1] == (
        "LINEAR_COMPONENT_FULLY_CONTAINED"
    )


def test_linear_containment_wins_over_circular_containment():
    decision = classify(
        0,
        (
            {
                "inner_topology":
                    "circular",
            },
            {
                "inner_topology":
                    "linear",
            },
        ),
    )

    assert decision[0] == EXCLUDE
    assert decision[1] == (
        "LINEAR_COMPONENT_FULLY_CONTAINED"
    )


def test_all_circular_containment_is_retained():
    decision = classify(
        0,
        (
            {
                "inner_topology":
                    "circular",
            },
            {
                "inner_topology":
                    "CIRCULAR",
            },
        ),
    )

    assert decision[0] == SUITABLE
    assert decision[1] == (
        "CIRCULAR_CONTAINMENT_RETAINED"
    )


@pytest.mark.parametrize(
    "topology",
    [
        "",
        "unknown",
        None,
    ],
)
def test_uncovered_containment_topology_is_unresolved(
    topology,
):
    decision = classify(
        0,
        (
            {
                "inner_topology":
                    topology,
            },
        ),
    )

    assert decision[0] == UNRESOLVED
    assert decision[1] == (
        "UNRESOLVED_SOURCE_TRUTH"
    )


def test_no_redundancy_is_suitable():
    assert classify(
        0,
        (),
    ) == (
        SUITABLE,
        "NO_SOURCE_REDUNDANCY",
        (
            "no exact duplication or full component containment "
            "was detected"
        ),
    )


@pytest.mark.parametrize(
    "value",
    [
        -1,
        1.5,
        True,
    ],
)
def test_invalid_duplicate_count_rejected(
    value,
):
    with pytest.raises(
        ValueError,
        match="non-negative integer",
    ):
        classify(
            value,
            (),
        )
