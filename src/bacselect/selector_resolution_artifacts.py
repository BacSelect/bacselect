"""Deterministic blinded scientific-artifact serialization for Stage 7."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
import hashlib
import json
import math
import re
from typing import Any

import numpy as np
import numpy.typing as npt

from bacselect.selector_resolution import (
    PANEL_SIZES,
    format_binary64,
)


SELECTORS: tuple[str, ...] = (
    "OPS",
    "SR",
)

SCIENTIFIC_ARTIFACT_NAMES: tuple[str, ...] = (
    "blinded-holdout-projected-coordinates.tsv",
    "blinded-holdout-nearest-panel-distances.tsv",
    "selector-primary-metrics.tsv",
    "selector-descriptive-diagnostics.json",
    "selector-exact-products.json",
    "selector-resolution-analysis-summary.json",
)

_ANONYMOUS_ROW_KEY = re.compile(
    r"^H[0-9]{8}$"
)

_ACCESSION_PATTERN = re.compile(
    r"\bGC[AF]_[0-9]+"
)

_IDENTITY_KEY_FRAGMENTS: tuple[str, ...] = (
    "accession",
    "species_id",
    "species_taxid",
    "species_name",
    "organism",
    "panel_identity",
    "nearest_panel_identity",
)

_OUTCOME_KEYS: frozenset[str] = frozenset(
    {
        "winner",
        "decision",
        "selector_outcome",
        "resolved_selector",
    }
)

_ANALYSIS_SUMMARY_VALUE_KEYS: frozenset[str] = frozenset(
    {
        "weighted_p95",
        "ops_weighted_p95",
        "sr_weighted_p95",
        "ops_product",
        "sr_product",
        "product_numerator",
        "product_denominator",
        "numerator",
        "denominator",
        "primary_values",
        "primary_metrics",
    }
)


def _validate_safe_field_name(
    value: str,
    *,
    name: str,
) -> str:
    """Require one non-empty TSV-safe, identity-blinded field name."""
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string"
        )

    if not value:
        raise ValueError(
            f"{name} must not be empty"
        )

    if any(
        token in value
        for token in (
            "\t",
            "\n",
            "\r",
        )
    ):
        raise ValueError(
            f"{name} must not contain TSV control characters"
        )

    lower = value.lower()

    if any(
        fragment in lower
        for fragment in _IDENTITY_KEY_FRAGMENTS
    ):
        raise ValueError(
            f"{name} is identity-bearing"
        )

    return value


def _validate_numeric_vector(
    values: Sequence[float]
    | npt.NDArray[np.floating],
    *,
    name: str,
    non_negative: bool,
) -> npt.NDArray[np.float64]:
    """Return one finite binary64 vector."""
    array = np.asarray(
        values,
        dtype=np.float64,
    )

    if array.ndim != 1:
        raise ValueError(
            f"{name} must be one-dimensional"
        )

    if array.size == 0:
        raise ValueError(
            f"{name} must not be empty"
        )

    if not np.all(
        np.isfinite(array)
    ):
        raise ValueError(
            f"{name} must contain only finite values"
        )

    if (
        non_negative
        and np.any(
            array < 0.0
        )
    ):
        raise ValueError(
            f"{name} must contain only non-negative values"
        )

    return array


def _validate_numeric_matrix(
    values: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    *,
    name: str,
) -> npt.NDArray[np.float64]:
    """Return one finite non-empty binary64 matrix."""
    matrix = np.asarray(
        values,
        dtype=np.float64,
    )

    if matrix.ndim != 2:
        raise ValueError(
            f"{name} must be two-dimensional"
        )

    if (
        matrix.shape[0] == 0
        or matrix.shape[1] == 0
    ):
        raise ValueError(
            f"{name} must not be empty"
        )

    if not np.all(
        np.isfinite(matrix)
    ):
        raise ValueError(
            f"{name} must contain only finite values"
        )

    return matrix


def anonymous_holdout_row_keys(
    row_count: int,
) -> tuple[str, ...]:
    """Return deterministic anonymous keys for canonical holdout row order."""
    if (
        not isinstance(
            row_count,
            int,
        )
        or isinstance(
            row_count,
            bool,
        )
        or row_count <= 0
    ):
        raise ValueError(
            "row_count must be a positive integer"
        )

    if row_count > 99_999_999:
        raise ValueError(
            "row_count exceeds anonymous-key capacity"
        )

    return tuple(
        f"H{index:08d}"
        for index in range(
            1,
            row_count + 1,
        )
    )


def _assert_blinded_object(
    value: Any,
    *,
    path: str = "payload",
) -> None:
    """Reject identity-bearing keys or accession-like string values."""
    if isinstance(
        value,
        Mapping,
    ):
        for key, child in value.items():
            if not isinstance(
                key,
                str,
            ):
                raise TypeError(
                    f"{path} mapping keys must be strings"
                )

            _validate_safe_field_name(
                key,
                name=f"{path} key",
            )

            _assert_blinded_object(
                child,
                path=f"{path}.{key}",
            )

        return

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        for index, child in enumerate(
            value
        ):
            _assert_blinded_object(
                child,
                path=f"{path}[{index}]",
            )

        return

    if isinstance(
        value,
        str,
    ):
        if _ACCESSION_PATTERN.search(
            value
        ):
            raise ValueError(
                f"{path} contains accession identity"
            )

        return

    if value is None or isinstance(
        value,
        (
            bool,
            int,
        ),
    ):
        return

    if isinstance(
        value,
        float,
    ):
        if not math.isfinite(
            value
        ):
            raise ValueError(
                f"{path} contains non-finite float"
            )

        return

    raise TypeError(
        f"{path} contains unsupported JSON value type"
    )


def _assert_forbidden_keys_absent(
    value: Any,
    forbidden: frozenset[str],
    *,
    path: str = "payload",
) -> None:
    """Reject exact forbidden semantic keys recursively."""
    if isinstance(
        value,
        Mapping,
    ):
        for key, child in value.items():
            if (
                isinstance(
                    key,
                    str,
                )
                and key.lower()
                in forbidden
            ):
                raise ValueError(
                    f"{path}.{key} is forbidden"
                )

            _assert_forbidden_keys_absent(
                child,
                forbidden,
                path=f"{path}.{key}",
            )

    elif isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        for index, child in enumerate(
            value
        ):
            _assert_forbidden_keys_absent(
                child,
                forbidden,
                path=f"{path}[{index}]",
            )


def canonical_blinded_json_bytes(
    payload: Mapping[str, Any],
    *,
    forbidden_keys: frozenset[str] = frozenset(),
) -> bytes:
    """Return canonical indented UTF-8 JSON after blinding checks."""
    if not isinstance(
        payload,
        Mapping,
    ):
        raise TypeError(
            "payload must be a mapping"
        )

    _assert_blinded_object(
        payload
    )

    _assert_forbidden_keys_absent(
        payload,
        forbidden_keys,
    )

    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def sha256_bytes(
    payload: bytes,
) -> str:
    """Return SHA256 for exact serialized bytes."""
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "payload must be bytes"
        )

    return hashlib.sha256(
        payload
    ).hexdigest()


def serialize_projected_coordinates(
    coordinates: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    feature_names: Sequence[str],
) -> bytes:
    """Serialize the blinded projected-coordinate scientific artifact."""
    matrix = _validate_numeric_matrix(
        coordinates,
        name="coordinates",
    )

    features = [
        _validate_safe_field_name(
            feature,
            name="feature name",
        )
        for feature in feature_names
    ]

    if len(
        features
    ) != matrix.shape[1]:
        raise ValueError(
            "feature_names must match coordinate columns"
        )

    if len(
        set(
            features
        )
    ) != len(
        features
    ):
        raise ValueError(
            "feature_names must be unique"
        )

    row_keys = anonymous_holdout_row_keys(
        matrix.shape[0]
    )

    lines = [
        "\t".join(
            (
                "holdout_row_key",
                *features,
            )
        )
    ]

    for row_key, row in zip(
        row_keys,
        matrix,
        strict=True,
    ):
        lines.append(
            "\t".join(
                (
                    row_key,
                    *(
                        format_binary64(
                            float(
                                value
                            )
                        )
                        for value in row
                    ),
                )
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def serialize_nearest_panel_distances(
    distances: Mapping[
        tuple[str, int],
        Sequence[float]
        | npt.NDArray[np.floating],
    ],
) -> bytes:
    """Serialize all blinded OPS/SR × N nearest-panel distances."""
    required_keys = {
        (
            selector,
            panel_size,
        )
        for selector in SELECTORS
        for panel_size in PANEL_SIZES
    }

    if set(
        distances
    ) != required_keys:
        raise ValueError(
            "distances must contain exactly "
            "OPS/SR × N=10,20,50,100,200,500"
        )

    arrays = {
        key:
            _validate_numeric_vector(
                values,
                name=(
                    f"distances[{key!r}]"
                ),
                non_negative=True,
            )
        for key, values
        in distances.items()
    }

    row_counts = {
        array.size
        for array in arrays.values()
    }

    if len(
        row_counts
    ) != 1:
        raise ValueError(
            "all distance vectors must have the same row count"
        )

    row_count = next(
        iter(
            row_counts
        )
    )

    row_keys = anonymous_holdout_row_keys(
        row_count
    )

    lines = [
        (
            "holdout_row_key\t"
            "selector\t"
            "N\t"
            "nearest_panel_distance"
        )
    ]

    for selector in SELECTORS:
        for panel_size in PANEL_SIZES:
            array = arrays[
                (
                    selector,
                    panel_size,
                )
            ]

            for row_key, value in zip(
                row_keys,
                array,
                strict=True,
            ):
                lines.append(
                    "\t".join(
                        (
                            row_key,
                            selector,
                            str(
                                panel_size
                            ),
                            format_binary64(
                                float(
                                    value
                                )
                            ),
                        )
                    )
                )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def serialize_primary_metrics(
    metrics: Mapping[
        tuple[str, int],
        float,
    ],
) -> bytes:
    """Serialize the canonical 12-row weighted-p95 table."""
    required_keys = {
        (
            selector,
            panel_size,
        )
        for selector in SELECTORS
        for panel_size in PANEL_SIZES
    }

    if set(
        metrics
    ) != required_keys:
        raise ValueError(
            "metrics must contain exactly "
            "OPS/SR × N=10,20,50,100,200,500"
        )

    lines = [
        "selector\tN\tweighted_p95"
    ]

    for selector in SELECTORS:
        for panel_size in PANEL_SIZES:
            value = float(
                metrics[
                    (
                        selector,
                        panel_size,
                    )
                ]
            )

            if (
                not math.isfinite(
                    value
                )
                or value < 0.0
            ):
                raise ValueError(
                    "weighted_p95 values must be "
                    "finite and non-negative"
                )

            lines.append(
                "\t".join(
                    (
                        selector,
                        str(
                            panel_size
                        ),
                        format_binary64(
                            value
                        ),
                    )
                )
            )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def serialize_exact_products(
    products: Mapping[str, Fraction],
) -> bytes:
    """Serialize exact OPS/SR products without resolving a winner."""
    if set(
        products
    ) != set(
        SELECTORS
    ):
        raise ValueError(
            "products must contain exactly OPS and SR"
        )

    selectors: dict[
        str,
        dict[str, int],
    ] = {}

    for selector in SELECTORS:
        product = products[
            selector
        ]

        if not isinstance(
            product,
            Fraction,
        ):
            raise TypeError(
                "selector products must be Fraction values"
            )

        if product < 0:
            raise ValueError(
                "selector products must be non-negative"
            )

        selectors[
            selector
        ] = {
            "denominator":
                product.denominator,
            "numerator":
                product.numerator,
        }

    return canonical_blinded_json_bytes(
        {
            "schema_version":
                1,
            "status":
                "STAGE7_EXACT_PRODUCTS_COMPLETE",
            "selectors":
                selectors,
        },
        forbidden_keys=_OUTCOME_KEYS,
    )


def serialize_descriptive_diagnostics(
    payload: Mapping[str, Any],
) -> bytes:
    """Serialize blinded diagnostics without selector resolution."""
    return canonical_blinded_json_bytes(
        payload,
        forbidden_keys=_OUTCOME_KEYS,
    )


def serialize_analysis_summary(
    payload: Mapping[str, Any],
) -> bytes:
    """Serialize a blinded summary without primary/product values or outcome."""
    return canonical_blinded_json_bytes(
        payload,
        forbidden_keys=(
            _OUTCOME_KEYS
            | _ANALYSIS_SUMMARY_VALUE_KEYS
        ),
    )
