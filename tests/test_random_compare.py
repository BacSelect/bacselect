from decimal import Decimal

import pytest

from bacselect.random_compare import (
    lower_is_better_empirical_rank,
)


def D(value: str) -> Decimal:
    return Decimal(value)


def test_rank_one_when_no_random_value_is_lower() -> None:
    assert lower_is_better_empirical_rank(
        D("1"),
        [D("1"), D("2"), D("3")],
    ) == 1


def test_rank_after_strictly_lower_random_values() -> None:
    assert lower_is_better_empirical_rank(
        D("2.5"),
        [D("1"), D("2"), D("3"), D("4")],
    ) == 3


def test_exact_ties_do_not_count_as_better() -> None:
    assert lower_is_better_empirical_rank(
        D("2"),
        [D("1"), D("2"), D("2"), D("3")],
    ) == 2


def test_rank_can_be_1001() -> None:
    random_values = [
        Decimal(index)
        for index in range(1000)
    ]

    assert lower_is_better_empirical_rank(
        D("1000"),
        random_values,
    ) == 1001


def test_rejects_empty_random_values() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        lower_is_better_empirical_rank(
            D("1"),
            [],
        )


def test_rejects_nonfinite_candidate() -> None:
    with pytest.raises(ValueError, match="finite"):
        lower_is_better_empirical_rank(
            D("NaN"),
            [D("1")],
        )


def test_rejects_nonfinite_random_value() -> None:
    with pytest.raises(ValueError, match="finite"):
        lower_is_better_empirical_rank(
            D("1"),
            [D("Infinity")],
        )


def test_requires_decimal_candidate() -> None:
    with pytest.raises(TypeError, match="candidate"):
        lower_is_better_empirical_rank(
            1.0,  # type: ignore[arg-type]
            [D("1")],
        )


def test_requires_decimal_random_values() -> None:
    with pytest.raises(TypeError, match="random_values"):
        lower_is_better_empirical_rank(
            D("1"),
            [1.0],  # type: ignore[list-item]
        )
