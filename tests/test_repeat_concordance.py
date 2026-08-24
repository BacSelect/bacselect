"""Tests for selector-v1 reference-scale concordance."""

from __future__ import annotations

from bacselect.repeat_concordance import (
    FLOAT_FEATURES,
    INTEGER_FEATURES,
    REFERENCE_FEATURES,
    REFERENCE_K_VALUES,
    binary64_bytes,
    compare_reference_features,
    extract_reference_features,
)


def test_frozen_reference_definition() -> None:
    assert REFERENCE_K_VALUES == (
        150,
        400,
    )

    assert REFERENCE_FEATURES == (
        "06_non_unique_canonical_150mer_fraction",
        "07_non_unique_canonical_400mer_fraction",
        "08_maximum_canonical_150mer_multiplicity",
        "09_maximum_canonical_400mer_multiplicity",
        "11_inter_replicon_shared_canonical_150mer_fraction",
        "12_inter_replicon_shared_canonical_400mer_fraction",
    )

    assert len(FLOAT_FEATURES) == 4
    assert len(INTEGER_FEATURES) == 2


def test_extract_reference_features() -> None:
    rows = {
        150: {
            "non_unique_fraction": "0.125",
            "maximum_multiplicity": "7",
            "inter_replicon_shared_fraction": "0.25",
        },
        400: {
            "non_unique_fraction": "0.0625",
            "maximum_multiplicity": "3",
            "inter_replicon_shared_fraction": "0.125",
        },
    }

    observed = extract_reference_features(
        rows
    )

    assert observed == {
        "06_non_unique_canonical_150mer_fraction": 0.125,
        "07_non_unique_canonical_400mer_fraction": 0.0625,
        "08_maximum_canonical_150mer_multiplicity": 7,
        "09_maximum_canonical_400mer_multiplicity": 3,
        "11_inter_replicon_shared_canonical_150mer_fraction": 0.25,
        "12_inter_replicon_shared_canonical_400mer_fraction": 0.125,
    }


def test_exact_concordance_passes() -> None:
    expected = {
        "06_non_unique_canonical_150mer_fraction": "0.125",
        "07_non_unique_canonical_400mer_fraction": "0.0625",
        "08_maximum_canonical_150mer_multiplicity": "7",
        "09_maximum_canonical_400mer_multiplicity": "3",
        "11_inter_replicon_shared_canonical_150mer_fraction": "0.25",
        "12_inter_replicon_shared_canonical_400mer_fraction": "0.125",
    }

    observed = {
        key: (
            int(value)
            if key in INTEGER_FEATURES
            else float(value)
        )
        for key, value in expected.items()
    }

    result = compare_reference_features(
        observed,
        expected,
    )

    assert result.passed
    assert result.mismatches == ()


def test_binary64_difference_fails() -> None:
    expected = {
        "06_non_unique_canonical_150mer_fraction": "0.5",
        "07_non_unique_canonical_400mer_fraction": "0.25",
        "08_maximum_canonical_150mer_multiplicity": "7",
        "09_maximum_canonical_400mer_multiplicity": "3",
        "11_inter_replicon_shared_canonical_150mer_fraction": "0.125",
        "12_inter_replicon_shared_canonical_400mer_fraction": "0.0625",
    }

    observed = {
        "06_non_unique_canonical_150mer_fraction": float.fromhex(
            "0x1.0000000000001p-1"
        ),
        "07_non_unique_canonical_400mer_fraction": 0.25,
        "08_maximum_canonical_150mer_multiplicity": 7,
        "09_maximum_canonical_400mer_multiplicity": 3,
        "11_inter_replicon_shared_canonical_150mer_fraction": 0.125,
        "12_inter_replicon_shared_canonical_400mer_fraction": 0.0625,
    }

    assert (
        binary64_bytes(
            observed[
                "06_non_unique_canonical_150mer_fraction"
            ]
        )
        != binary64_bytes(0.5)
    )

    result = compare_reference_features(
        observed,
        expected,
    )

    assert not result.passed
    assert result.mismatches == (
        "06_non_unique_canonical_150mer_fraction",
    )


def test_integer_difference_fails() -> None:
    expected = {
        "06_non_unique_canonical_150mer_fraction": "0.5",
        "07_non_unique_canonical_400mer_fraction": "0.25",
        "08_maximum_canonical_150mer_multiplicity": "7",
        "09_maximum_canonical_400mer_multiplicity": "3",
        "11_inter_replicon_shared_canonical_150mer_fraction": "0.125",
        "12_inter_replicon_shared_canonical_400mer_fraction": "0.0625",
    }

    observed = {
        "06_non_unique_canonical_150mer_fraction": 0.5,
        "07_non_unique_canonical_400mer_fraction": 0.25,
        "08_maximum_canonical_150mer_multiplicity": 8,
        "09_maximum_canonical_400mer_multiplicity": 3,
        "11_inter_replicon_shared_canonical_150mer_fraction": 0.125,
        "12_inter_replicon_shared_canonical_400mer_fraction": 0.0625,
    }

    result = compare_reference_features(
        observed,
        expected,
    )

    assert not result.passed
    assert result.mismatches == (
        "08_maximum_canonical_150mer_multiplicity",
    )
