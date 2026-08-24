"""Reference-scale concordance helpers for BacSelect selector v1."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Mapping


REFERENCE_K_VALUES = (
    150,
    400,
)

REFERENCE_FEATURES = (
    "06_non_unique_canonical_150mer_fraction",
    "07_non_unique_canonical_400mer_fraction",
    "08_maximum_canonical_150mer_multiplicity",
    "09_maximum_canonical_400mer_multiplicity",
    "11_inter_replicon_shared_canonical_150mer_fraction",
    "12_inter_replicon_shared_canonical_400mer_fraction",
)

FLOAT_FEATURES = (
    "06_non_unique_canonical_150mer_fraction",
    "07_non_unique_canonical_400mer_fraction",
    "11_inter_replicon_shared_canonical_150mer_fraction",
    "12_inter_replicon_shared_canonical_400mer_fraction",
)

INTEGER_FEATURES = (
    "08_maximum_canonical_150mer_multiplicity",
    "09_maximum_canonical_400mer_multiplicity",
)


@dataclass(frozen=True)
class ConcordanceResult:
    """Comparison of one recalculated genome with its frozen reference."""

    passed: bool
    mismatches: tuple[str, ...]


def binary64_bytes(value: float) -> bytes:
    """Return the exact IEEE-754 binary64 representation of a value."""
    return struct.pack(
        ">d",
        float(value),
    )


def extract_reference_features(
    engine_rows: Mapping[int, Mapping[str, str]],
) -> dict[str, float | int]:
    """Map frozen k=150/400 engine rows to the six reference features."""
    if set(engine_rows) != set(REFERENCE_K_VALUES):
        raise ValueError(
            "engine_rows must contain exactly k=150 and k=400"
        )

    row150 = engine_rows[150]
    row400 = engine_rows[400]

    return {
        "06_non_unique_canonical_150mer_fraction": float(
            row150["non_unique_fraction"]
        ),
        "07_non_unique_canonical_400mer_fraction": float(
            row400["non_unique_fraction"]
        ),
        "08_maximum_canonical_150mer_multiplicity": int(
            row150["maximum_multiplicity"]
        ),
        "09_maximum_canonical_400mer_multiplicity": int(
            row400["maximum_multiplicity"]
        ),
        "11_inter_replicon_shared_canonical_150mer_fraction": float(
            row150["inter_replicon_shared_fraction"]
        ),
        "12_inter_replicon_shared_canonical_400mer_fraction": float(
            row400["inter_replicon_shared_fraction"]
        ),
    }


def compare_reference_features(
    observed: Mapping[str, float | int],
    expected: Mapping[str, str | float | int],
) -> ConcordanceResult:
    """Compare all six frozen reference-scale features exactly."""
    observed_keys = set(observed)
    required_keys = set(REFERENCE_FEATURES)

    if observed_keys != required_keys:
        raise ValueError(
            "observed feature set does not match frozen reference features"
        )

    if not required_keys.issubset(expected):
        missing = sorted(
            required_keys - set(expected)
        )

        raise ValueError(
            f"expected reference is missing features: {missing!r}"
        )

    mismatches: list[str] = []

    for feature in FLOAT_FEATURES:
        observed_value = float(
            observed[feature]
        )
        expected_value = float(
            expected[feature]
        )

        if binary64_bytes(
            observed_value
        ) != binary64_bytes(
            expected_value
        ):
            mismatches.append(
                feature
            )

    for feature in INTEGER_FEATURES:
        observed_value = int(
            observed[feature]
        )
        expected_value = int(
            expected[feature]
        )

        if observed_value != expected_value:
            mismatches.append(
                feature
            )

    return ConcordanceResult(
        passed=not mismatches,
        mismatches=tuple(mismatches),
    )
