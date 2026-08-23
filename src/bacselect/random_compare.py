"""Candidate-versus-random comparison helpers for BacSelect selector v1."""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence


def lower_is_better_empirical_rank(
    candidate: Decimal,
    random_values: Sequence[Decimal],
) -> int:
    """Return the frozen lower-is-better empirical competition rank.

    Rank is:

        1 + count(random_value < candidate)

    Exact ties therefore do not count as better random outcomes.
    """
    if not isinstance(candidate, Decimal):
        raise TypeError("candidate must be a decimal.Decimal")

    if not candidate.is_finite():
        raise ValueError("candidate must be finite")

    values = list(random_values)

    if not values:
        raise ValueError("random_values must not be empty")

    for value in values:
        if not isinstance(value, Decimal):
            raise TypeError(
                "random_values must contain only decimal.Decimal values"
            )

        if not value.is_finite():
            raise ValueError(
                "random_values must contain only finite values"
            )

    return 1 + sum(
        value < candidate
        for value in values
    )
