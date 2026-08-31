"""Pure, deterministic Stage 7 selector-decision finalization primitives.

This module contains no production/rebuild filesystem paths.  Real execution is
performed only by a separately frozen wrapper after this module and its tests
have been frozen.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any

from bacselect.selector_resolution import (
    PANEL_SIZES,
    exact_six_size_product,
    resolve_exact_products,
)
from bacselect.selector_resolution_artifacts import (
    SCIENTIFIC_ARTIFACT_NAMES,
    SELECTORS,
    serialize_analysis_summary,
    serialize_exact_products,
    serialize_primary_metrics,
)


PRIMARY_METRIC_ARTIFACT = (
    "selector-primary-metrics.tsv"
)

EXACT_PRODUCT_ARTIFACT = (
    "selector-exact-products.json"
)

ANALYSIS_SUMMARY_ARTIFACT = (
    "selector-resolution-analysis-summary.json"
)

FINAL_LADDER_SHA256: dict[str, str] = {
    "OPS":
        "c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13",
    "SR":
        "3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f",
}

_COMPLETION_TOP_LEVEL = {
    "schema_version",
    "stage",
    "status",
    "execution_commit",
    "stage7_method_sha256",
    "selector_resolution_design_sha256",
    "stage6_completion_evidence_sha256",
    "implementation_bindings",
    "production_scientific_artifact_sha256",
    "rebuild_scientific_artifact_sha256",
    "production_provenance_sha256",
    "rebuild_provenance_sha256",
    "byte_identity_verification_record_sha256",
    "all_scientific_artifacts_byte_identical",
    "identity_bearing_outputs_committed_to_git",
    "selector_outcome_generated",
    "selector_decision_finalized",
}

_RUN_IDENTITY_KEYS = {
    "execution_commit",
    "execution_mode",
    "predecision_provenance_sha256",
    "execution_provenance_sha256",
    "content_manifest_sha256",
}

_PROVENANCE_KEYS = {
    "predecision_provenance_sha256",
    "execution_provenance_sha256",
    "content_manifest_sha256",
}

_BYTE_IDENTITY_TOP_LEVEL = {
    "schema_version",
    "stage",
    "status",
    "production_run_identity",
    "rebuild_run_identity",
    "scientific_artifact_comparisons",
    "all_scientific_artifacts_byte_identical",
}

_COMPARISON_KEYS = {
    "artifact",
    "production_sha256",
    "rebuild_sha256",
    "byte_identical",
}

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_ACCESSION_RE = re.compile(
    r"\bGC[AF]_[0-9]+"
)

_HOLDOUT_KEY_RE = re.compile(
    r"\bH[0-9]{8}\b"
)

_VERIFIED_EVIDENCE_TOKEN = object()


class SelectorDecisionFinalizationError(
    RuntimeError
):
    """Raised when finalization must fail closed."""


@dataclass(
    frozen=True,
)
class FinalizationEvidence:
    """Verified aggregate-only predecision evidence."""

    analysis_execution_commit: str
    completion_sha256: str
    byte_identity_sha256: str
    stage7_method_sha256: str
    selector_resolution_design_sha256: str
    implementation_bindings: Mapping[
        str,
        str,
    ]
    scientific_artifact_sha256: Mapping[
        str,
        str,
    ]
    production_provenance_sha256: Mapping[
        str,
        str,
    ]
    rebuild_provenance_sha256: Mapping[
        str,
        str,
    ]
    final_ladder_sha256: Mapping[
        str,
        str,
    ]
    _verification_token: object


def _freeze_mapping(
    value: Mapping[
        str,
        str,
    ],
) -> Mapping[
    str,
    str,
]:
    """Return a detached immutable mapping for verified evidence."""
    return MappingProxyType(
        dict(
            sorted(
                value.items()
            )
        )
    )


def sha256_bytes(
    payload: bytes,
) -> str:
    """Return lowercase SHA256 for exact bytes."""
    return hashlib.sha256(
        payload
    ).hexdigest()


def _canonical_json_bytes(
    payload: object,
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def _require_sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _SHA256_RE.fullmatch(
            value
        ) is None
    ):
        raise SelectorDecisionFinalizationError(
            f"{label} must be one lowercase SHA256"
        )

    return value


def _require_commit(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _COMMIT_RE.fullmatch(
            value
        ) is None
    ):
        raise SelectorDecisionFinalizationError(
            f"{label} must be one lowercase 40-character Git commit"
        )

    return value


def _load_canonical_json(
    payload: bytes,
    *,
    label: str,
) -> dict[str, Any]:
    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise SelectorDecisionFinalizationError(
            f"{label} must be UTF-8"
        ) from exc

    try:
        value = json.loads(
            text
        )
    except json.JSONDecodeError as exc:
        raise SelectorDecisionFinalizationError(
            f"{label} must be valid JSON"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise SelectorDecisionFinalizationError(
            f"{label} must be a JSON object"
        )

    if _canonical_json_bytes(
        value
    ) != payload:
        raise SelectorDecisionFinalizationError(
            f"{label} serialization is not canonical"
        )

    return value


def _assert_no_identity_text(
    payload: bytes,
    *,
    label: str,
) -> None:
    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise SelectorDecisionFinalizationError(
            f"{label} must be UTF-8"
        ) from exc

    if _ACCESSION_RE.search(
        text
    ):
        raise SelectorDecisionFinalizationError(
            f"{label} contains a genome accession identity"
        )

    if _HOLDOUT_KEY_RE.search(
        text
    ):
        raise SelectorDecisionFinalizationError(
            f"{label} contains a holdout row identity"
        )


def _require_sha_mapping(
    value: object,
    *,
    expected_keys: set[str],
    label: str,
) -> dict[str, str]:
    if not isinstance(
        value,
        dict,
    ):
        raise SelectorDecisionFinalizationError(
            f"{label} must be a mapping"
        )

    if set(
        value
    ) != expected_keys:
        raise SelectorDecisionFinalizationError(
            f"{label} has an unexpected key set"
        )

    return {
        key:
            _require_sha256(
                value[
                    key
                ],
                label=(
                    f"{label}.{key}"
                ),
            )
        for key in sorted(
            expected_keys
        )
    }


def _require_implementation_bindings(
    value: object,
    *,
    expected: Mapping[
        str,
        str,
    ],
) -> dict[str, str]:
    if not isinstance(
        value,
        dict,
    ):
        raise SelectorDecisionFinalizationError(
            "implementation_bindings must be a mapping"
        )

    expected_mapping = dict(
        expected
    )

    if value != expected_mapping:
        raise SelectorDecisionFinalizationError(
            "implementation_bindings do not match frozen expected values"
        )

    for key, sha in value.items():
        if not isinstance(
            key,
            str,
        ) or not key:
            raise SelectorDecisionFinalizationError(
                "implementation binding names must be non-empty strings"
            )

        _require_sha256(
            sha,
            label=(
                "implementation_bindings."
                + key
            ),
        )

    return dict(
        sorted(
            value.items()
        )
    )


def _validate_completion_evidence(
    payload: bytes,
    *,
    expected_completion_sha256: str,
    expected_stage7_method_sha256: str,
    expected_selector_resolution_design_sha256: str,
    expected_byte_identity_sha256: str,
    expected_implementation_bindings: Mapping[
        str,
        str,
    ],
) -> dict[str, Any]:
    expected_completion_sha256 = (
        _require_sha256(
            expected_completion_sha256,
            label="expected completion evidence SHA256",
        )
    )

    if sha256_bytes(
        payload
    ) != expected_completion_sha256:
        raise SelectorDecisionFinalizationError(
            "completion evidence SHA256 mismatch"
        )

    completion = _load_canonical_json(
        payload,
        label="completion evidence",
    )

    if set(
        completion
    ) != _COMPLETION_TOP_LEVEL:
        raise SelectorDecisionFinalizationError(
            "completion evidence schema mismatch"
        )

    if completion[
        "schema_version"
    ] != 1:
        raise SelectorDecisionFinalizationError(
            "completion evidence schema_version must equal 1"
        )

    if completion[
        "stage"
    ] != "selector-v1-stage7":
        raise SelectorDecisionFinalizationError(
            "completion evidence stage mismatch"
        )

    if completion[
        "status"
    ] != "STAGE7_ANALYSIS_COMPLETE_BYTE_IDENTICAL":
        raise SelectorDecisionFinalizationError(
            "completion evidence status mismatch"
        )

    _require_commit(
        completion[
            "execution_commit"
        ],
        label="completion execution_commit",
    )

    if completion[
        "stage7_method_sha256"
    ] != _require_sha256(
        expected_stage7_method_sha256,
        label="expected Stage 7 method SHA256",
    ):
        raise SelectorDecisionFinalizationError(
            "Stage 7 method SHA256 mismatch"
        )

    if completion[
        "selector_resolution_design_sha256"
    ] != _require_sha256(
        expected_selector_resolution_design_sha256,
        label="expected selector-resolution design SHA256",
    ):
        raise SelectorDecisionFinalizationError(
            "selector-resolution design SHA256 mismatch"
        )

    if completion[
        "byte_identity_verification_record_sha256"
    ] != _require_sha256(
        expected_byte_identity_sha256,
        label="expected byte-identity record SHA256",
    ):
        raise SelectorDecisionFinalizationError(
            "byte-identity record SHA256 binding mismatch"
        )

    _require_sha256(
        completion[
            "stage6_completion_evidence_sha256"
        ],
        label="Stage 6 completion evidence SHA256",
    )

    _require_implementation_bindings(
        completion[
            "implementation_bindings"
        ],
        expected=expected_implementation_bindings,
    )

    scientific_names = set(
        SCIENTIFIC_ARTIFACT_NAMES
    )

    production = _require_sha_mapping(
        completion[
            "production_scientific_artifact_sha256"
        ],
        expected_keys=scientific_names,
        label="production scientific artifact SHA256",
    )

    rebuild = _require_sha_mapping(
        completion[
            "rebuild_scientific_artifact_sha256"
        ],
        expected_keys=scientific_names,
        label="rebuild scientific artifact SHA256",
    )

    if production != rebuild:
        raise SelectorDecisionFinalizationError(
            "completion production/rebuild scientific hashes differ"
        )

    _require_sha_mapping(
        completion[
            "production_provenance_sha256"
        ],
        expected_keys=_PROVENANCE_KEYS,
        label="production provenance SHA256",
    )

    _require_sha_mapping(
        completion[
            "rebuild_provenance_sha256"
        ],
        expected_keys=_PROVENANCE_KEYS,
        label="rebuild provenance SHA256",
    )

    if completion[
        "all_scientific_artifacts_byte_identical"
    ] is not True:
        raise SelectorDecisionFinalizationError(
            "all_scientific_artifacts_byte_identical must be true"
        )

    if completion[
        "identity_bearing_outputs_committed_to_git"
    ] is not False:
        raise SelectorDecisionFinalizationError(
            "identity_bearing_outputs_committed_to_git must be false"
        )

    if completion[
        "selector_outcome_generated"
    ] is not False:
        raise SelectorDecisionFinalizationError(
            "selector_outcome_generated must be false"
        )

    if completion[
        "selector_decision_finalized"
    ] is not False:
        raise SelectorDecisionFinalizationError(
            "selector_decision_finalized must be false"
        )

    _assert_no_identity_text(
        payload,
        label="completion evidence",
    )

    return completion


def _validate_byte_identity_record(
    payload: bytes,
    *,
    expected_sha256: str,
    completion: Mapping[
        str,
        Any,
    ],
) -> dict[str, Any]:
    expected_sha256 = _require_sha256(
        expected_sha256,
        label="expected byte-identity record SHA256",
    )

    if sha256_bytes(
        payload
    ) != expected_sha256:
        raise SelectorDecisionFinalizationError(
            "byte-identity verification record SHA256 mismatch"
        )

    record = _load_canonical_json(
        payload,
        label="byte-identity verification record",
    )

    if set(
        record
    ) != _BYTE_IDENTITY_TOP_LEVEL:
        raise SelectorDecisionFinalizationError(
            "byte-identity verification record schema mismatch"
        )

    if record[
        "schema_version"
    ] != 1:
        raise SelectorDecisionFinalizationError(
            "byte-identity schema_version must equal 1"
        )

    if record[
        "stage"
    ] != "selector-v1-stage7":
        raise SelectorDecisionFinalizationError(
            "byte-identity stage mismatch"
        )

    if record[
        "status"
    ] != "STAGE7_SCIENTIFIC_ARTIFACTS_BYTE_IDENTICAL":
        raise SelectorDecisionFinalizationError(
            "byte-identity status mismatch"
        )

    if record[
        "all_scientific_artifacts_byte_identical"
    ] is not True:
        raise SelectorDecisionFinalizationError(
            "byte-identity aggregate boolean must be true"
        )

    expected_modes = {
        "production_run_identity":
            "production",
        "rebuild_run_identity":
            "independent_rebuild",
    }

    for key, expected_mode in expected_modes.items():
        run = record[
            key
        ]

        if (
            not isinstance(
                run,
                dict,
            )
            or set(
                run
            ) != _RUN_IDENTITY_KEYS
        ):
            raise SelectorDecisionFinalizationError(
                f"{key} schema mismatch"
            )

        if run[
            "execution_commit"
        ] != completion[
            "execution_commit"
        ]:
            raise SelectorDecisionFinalizationError(
                f"{key} execution commit mismatch"
            )

        if run[
            "execution_mode"
        ] != expected_mode:
            raise SelectorDecisionFinalizationError(
                f"{key} execution mode mismatch"
            )

        expected_provenance = completion[
            (
                "production_provenance_sha256"
                if expected_mode == "production"
                else "rebuild_provenance_sha256"
            )
        ]

        observed_provenance = {
            provenance_key:
                run[
                    provenance_key
                ]
            for provenance_key in _PROVENANCE_KEYS
        }

        if observed_provenance != expected_provenance:
            raise SelectorDecisionFinalizationError(
                f"{key} provenance mismatch"
            )

    comparisons = record[
        "scientific_artifact_comparisons"
    ]

    if not isinstance(
        comparisons,
        list,
    ):
        raise SelectorDecisionFinalizationError(
            "scientific_artifact_comparisons must be a list"
        )

    if len(
        comparisons
    ) != len(
        SCIENTIFIC_ARTIFACT_NAMES
    ):
        raise SelectorDecisionFinalizationError(
            "scientific artifact comparison count mismatch"
        )

    observed_names = []

    for item in comparisons:
        if (
            not isinstance(
                item,
                dict,
            )
            or set(
                item
            ) != _COMPARISON_KEYS
        ):
            raise SelectorDecisionFinalizationError(
                "scientific artifact comparison schema mismatch"
            )

        name = item[
            "artifact"
        ]

        if name not in SCIENTIFIC_ARTIFACT_NAMES:
            raise SelectorDecisionFinalizationError(
                "unexpected scientific artifact comparison"
            )

        observed_names.append(
            name
        )

        production_sha = _require_sha256(
            item[
                "production_sha256"
            ],
            label=(
                "byte-identity production SHA256 "
                + name
            ),
        )

        rebuild_sha = _require_sha256(
            item[
                "rebuild_sha256"
            ],
            label=(
                "byte-identity rebuild SHA256 "
                + name
            ),
        )

        expected_scientific_sha = completion[
            "production_scientific_artifact_sha256"
        ][
            name
        ]

        if (
            production_sha
            != expected_scientific_sha
            or rebuild_sha
            != expected_scientific_sha
        ):
            raise SelectorDecisionFinalizationError(
                "byte-identity scientific artifact SHA mismatch: "
                + name
            )

        if item[
            "byte_identical"
        ] is not True:
            raise SelectorDecisionFinalizationError(
                "scientific artifact byte-identical flag is false: "
                + name
            )

    if tuple(
        observed_names
    ) != tuple(
        SCIENTIFIC_ARTIFACT_NAMES
    ):
        raise SelectorDecisionFinalizationError(
            "scientific artifact comparison order mismatch"
        )

    _assert_no_identity_text(
        payload,
        label="byte-identity verification record",
    )

    return record


def verify_finalization_evidence(
    *,
    completion_bytes: bytes,
    byte_identity_bytes: bytes,
    expected_completion_sha256: str,
    expected_byte_identity_sha256: str,
    expected_stage7_method_sha256: str,
    expected_selector_resolution_design_sha256: str,
    expected_implementation_bindings: Mapping[
        str,
        str,
    ],
    observed_production_scientific_sha256: Mapping[
        str,
        str,
    ],
    observed_rebuild_scientific_sha256: Mapping[
        str,
        str,
    ],
    observed_production_provenance_sha256: Mapping[
        str,
        str,
    ],
    observed_rebuild_provenance_sha256: Mapping[
        str,
        str,
    ],
    observed_final_ladder_sha256: Mapping[
        str,
        str,
    ],
) -> FinalizationEvidence:
    """Verify all aggregate predecision evidence before decision parsing."""

    completion = _validate_completion_evidence(
        completion_bytes,
        expected_completion_sha256=(
            expected_completion_sha256
        ),
        expected_stage7_method_sha256=(
            expected_stage7_method_sha256
        ),
        expected_selector_resolution_design_sha256=(
            expected_selector_resolution_design_sha256
        ),
        expected_byte_identity_sha256=(
            expected_byte_identity_sha256
        ),
        expected_implementation_bindings=(
            expected_implementation_bindings
        ),
    )

    _validate_byte_identity_record(
        byte_identity_bytes,
        expected_sha256=(
            expected_byte_identity_sha256
        ),
        completion=completion,
    )

    scientific_names = set(
        SCIENTIFIC_ARTIFACT_NAMES
    )

    observed_production = _require_sha_mapping(
        dict(
            observed_production_scientific_sha256
        ),
        expected_keys=scientific_names,
        label="observed production scientific SHA256",
    )

    observed_rebuild = _require_sha_mapping(
        dict(
            observed_rebuild_scientific_sha256
        ),
        expected_keys=scientific_names,
        label="observed rebuild scientific SHA256",
    )

    expected_scientific = completion[
        "production_scientific_artifact_sha256"
    ]

    if observed_production != expected_scientific:
        raise SelectorDecisionFinalizationError(
            "observed production scientific hashes do not match completion evidence"
        )

    if observed_rebuild != expected_scientific:
        raise SelectorDecisionFinalizationError(
            "observed rebuild scientific hashes do not match completion evidence"
        )

    production_provenance = _require_sha_mapping(
        dict(
            observed_production_provenance_sha256
        ),
        expected_keys=_PROVENANCE_KEYS,
        label="observed production provenance SHA256",
    )

    rebuild_provenance = _require_sha_mapping(
        dict(
            observed_rebuild_provenance_sha256
        ),
        expected_keys=_PROVENANCE_KEYS,
        label="observed rebuild provenance SHA256",
    )

    if production_provenance != completion[
        "production_provenance_sha256"
    ]:
        raise SelectorDecisionFinalizationError(
            "observed production provenance does not match completion evidence"
        )

    if rebuild_provenance != completion[
        "rebuild_provenance_sha256"
    ]:
        raise SelectorDecisionFinalizationError(
            "observed rebuild provenance does not match completion evidence"
        )

    observed_ladders = _require_sha_mapping(
        dict(
            observed_final_ladder_sha256
        ),
        expected_keys=set(
            SELECTORS
        ),
        label="observed final ladder SHA256",
    )

    if observed_ladders != FINAL_LADDER_SHA256:
        raise SelectorDecisionFinalizationError(
            "final OPS/SR ladder fingerprints do not match frozen final values"
        )

    return FinalizationEvidence(
        analysis_execution_commit=completion[
            "execution_commit"
        ],
        completion_sha256=(
            expected_completion_sha256
        ),
        byte_identity_sha256=(
            expected_byte_identity_sha256
        ),
        stage7_method_sha256=completion[
            "stage7_method_sha256"
        ],
        selector_resolution_design_sha256=completion[
            "selector_resolution_design_sha256"
        ],
        implementation_bindings=_freeze_mapping(
            completion[
                "implementation_bindings"
            ]
        ),
        scientific_artifact_sha256=_freeze_mapping(
            expected_scientific
        ),
        production_provenance_sha256=_freeze_mapping(
            production_provenance
        ),
        rebuild_provenance_sha256=_freeze_mapping(
            rebuild_provenance
        ),
        final_ladder_sha256=_freeze_mapping(
            FINAL_LADDER_SHA256
        ),
        _verification_token=(
            _VERIFIED_EVIDENCE_TOKEN
        ),
    )


def parse_primary_metrics(
    payload: bytes,
) -> dict[
    tuple[str, int],
    float,
]:
    """Parse and require canonical 12-row Stage 7 primary metrics."""

    _assert_no_identity_text(
        payload,
        label="primary metric table",
    )

    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise SelectorDecisionFinalizationError(
            "primary metric table must be UTF-8"
        ) from exc

    lines = text.splitlines()

    if len(
        lines
    ) != 13:
        raise SelectorDecisionFinalizationError(
            "primary metric table must contain exactly 12 data rows"
        )

    if lines[
        0
    ] != "selector\tN\tweighted_p95":
        raise SelectorDecisionFinalizationError(
            "primary metric table header mismatch"
        )

    metrics: dict[
        tuple[str, int],
        float,
    ] = {}

    expected_pairs = [
        (
            selector,
            panel_size,
        )
        for selector in SELECTORS
        for panel_size in PANEL_SIZES
    ]

    for line, expected_pair in zip(
        lines[
            1:
        ],
        expected_pairs,
        strict=True,
    ):
        fields = line.split(
            "\t"
        )

        if len(
            fields
        ) != 3:
            raise SelectorDecisionFinalizationError(
                "primary metric rows must contain exactly three columns"
            )

        selector_text, panel_text, value_text = fields

        try:
            panel_size = int(
                panel_text
            )
        except ValueError as exc:
            raise SelectorDecisionFinalizationError(
                "primary metric panel size must be an integer"
            ) from exc

        pair = (
            selector_text,
            panel_size,
        )

        if pair != expected_pair:
            raise SelectorDecisionFinalizationError(
                "primary metric row order or panel-size contract mismatch"
            )

        if pair in metrics:
            raise SelectorDecisionFinalizationError(
                "duplicate primary metric row"
            )

        try:
            value = float(
                value_text
            )
        except ValueError as exc:
            raise SelectorDecisionFinalizationError(
                "primary metric value must parse as binary64"
            ) from exc

        if (
            not math.isfinite(
                value
            )
            or value < 0.0
        ):
            raise SelectorDecisionFinalizationError(
                "primary metric values must be finite and non-negative"
            )

        metrics[
            pair
        ] = value

    try:
        canonical = serialize_primary_metrics(
            metrics
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise SelectorDecisionFinalizationError(
            "primary metric table violates frozen serializer"
        ) from exc

    if canonical != payload:
        raise SelectorDecisionFinalizationError(
            "primary metric table serialization is not canonical"
        )

    return metrics


def parse_exact_products(
    payload: bytes,
) -> dict[
    str,
    Fraction,
]:
    """Parse and require canonical reduced exact OPS/SR products."""

    _assert_no_identity_text(
        payload,
        label="exact product artifact",
    )

    parsed = _load_canonical_json(
        payload,
        label="exact product artifact",
    )

    if set(
        parsed
    ) != {
        "schema_version",
        "status",
        "selectors",
    }:
        raise SelectorDecisionFinalizationError(
            "exact product artifact schema mismatch"
        )

    if parsed[
        "schema_version"
    ] != 1:
        raise SelectorDecisionFinalizationError(
            "exact product schema_version must equal 1"
        )

    if parsed[
        "status"
    ] != "STAGE7_EXACT_PRODUCTS_COMPLETE":
        raise SelectorDecisionFinalizationError(
            "exact product status mismatch"
        )

    selectors = parsed[
        "selectors"
    ]

    if (
        not isinstance(
            selectors,
            dict,
        )
        or set(
            selectors
        ) != set(
            SELECTORS
        )
    ):
        raise SelectorDecisionFinalizationError(
            "exact product selector set must be exactly OPS and SR"
        )

    products: dict[
        str,
        Fraction,
    ] = {}

    for selector in SELECTORS:
        raw = selectors[
            selector
        ]

        if (
            not isinstance(
                raw,
                dict,
            )
            or set(
                raw
            ) != {
                "numerator",
                "denominator",
            }
        ):
            raise SelectorDecisionFinalizationError(
                f"{selector} exact product schema mismatch"
            )

        numerator = raw[
            "numerator"
        ]
        denominator = raw[
            "denominator"
        ]

        if (
            type(
                numerator
            )
            is not int
        ):
            raise SelectorDecisionFinalizationError(
                f"{selector} numerator must be an integer"
            )

        if (
            type(
                denominator
            )
            is not int
        ):
            raise SelectorDecisionFinalizationError(
                f"{selector} denominator must be an integer"
            )

        if numerator < 0:
            raise SelectorDecisionFinalizationError(
                f"{selector} numerator must be non-negative"
            )

        if denominator <= 0:
            raise SelectorDecisionFinalizationError(
                f"{selector} denominator must be positive"
            )

        product = Fraction(
            numerator,
            denominator,
        )

        if (
            product.numerator
            != numerator
            or product.denominator
            != denominator
        ):
            raise SelectorDecisionFinalizationError(
                f"{selector} stored exact product must already be reduced"
            )

        products[
            selector
        ] = product

    try:
        canonical = serialize_exact_products(
            products
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise SelectorDecisionFinalizationError(
            "exact product artifact violates frozen serializer"
        ) from exc

    if canonical != payload:
        raise SelectorDecisionFinalizationError(
            "exact product artifact serialization is not canonical"
        )

    return products


def verify_analysis_summary(
    payload: bytes,
    *,
    expected_primary_metric_sha256: str,
    expected_exact_product_sha256: str,
) -> dict[str, Any]:
    """Require canonical blinded non-decisional analysis-summary bindings."""

    _assert_no_identity_text(
        payload,
        label="analysis summary",
    )

    parsed = _load_canonical_json(
        payload,
        label="analysis summary",
    )

    try:
        canonical = serialize_analysis_summary(
            parsed
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise SelectorDecisionFinalizationError(
            "analysis summary violates frozen blinded serializer"
        ) from exc

    if canonical != payload:
        raise SelectorDecisionFinalizationError(
            "analysis summary serialization is not canonical"
        )

    expected_primary_metric_sha256 = _require_sha256(
        expected_primary_metric_sha256,
        label="expected primary metric SHA256",
    )

    expected_exact_product_sha256 = _require_sha256(
        expected_exact_product_sha256,
        label="expected exact product SHA256",
    )

    if parsed.get(
        "primary_metric_table_sha256"
    ) != expected_primary_metric_sha256:
        raise SelectorDecisionFinalizationError(
            "analysis summary primary-metric SHA256 binding mismatch"
        )

    if parsed.get(
        "selector_exact_products_sha256"
    ) != expected_exact_product_sha256:
        raise SelectorDecisionFinalizationError(
            "analysis summary exact-product SHA256 binding mismatch"
        )

    return parsed


def _require_environment_bindings(
    value: Mapping[
        str,
        str,
    ],
) -> dict[str, str]:
    observed = dict(
        value
    )

    for key, item in observed.items():
        if (
            not isinstance(
                key,
                str,
            )
            or not key
        ):
            raise SelectorDecisionFinalizationError(
                "environment binding names must be non-empty strings"
            )

        if (
            not isinstance(
                item,
                str,
            )
            or not item
        ):
            raise SelectorDecisionFinalizationError(
                "environment binding values must be non-empty strings"
            )

    return dict(
        sorted(
            observed.items()
        )
    )


def finalize_selector_decision(
    *,
    evidence: FinalizationEvidence,
    primary_metric_bytes: bytes,
    exact_product_bytes: bytes,
    analysis_summary_bytes: bytes,
    finalizer_execution_commit: str,
    finalizer_method_sha256: str,
    finalizer_implementation_sha256: str,
    finalizer_test_sha256: str,
    environment_bindings: Mapping[
        str,
        str,
    ],
) -> bytes:
    """Perform the single authorized exact-product comparison.

    All aggregate predecision evidence must already be represented by a
    ``FinalizationEvidence`` object returned by ``verify_finalization_evidence``.
    """

    if not isinstance(
        evidence,
        FinalizationEvidence,
    ):
        raise SelectorDecisionFinalizationError(
            "evidence must be verified FinalizationEvidence"
        )

    if (
        evidence._verification_token
        is not _VERIFIED_EVIDENCE_TOKEN
    ):
        raise SelectorDecisionFinalizationError(
            "evidence was not produced by verify_finalization_evidence"
        )

    finalizer_execution_commit = _require_commit(
        finalizer_execution_commit,
        label="finalizer execution commit",
    )

    finalizer_method_sha256 = _require_sha256(
        finalizer_method_sha256,
        label="finalizer method SHA256",
    )

    finalizer_implementation_sha256 = _require_sha256(
        finalizer_implementation_sha256,
        label="finalizer implementation SHA256",
    )

    finalizer_test_sha256 = _require_sha256(
        finalizer_test_sha256,
        label="finalizer test SHA256",
    )

    environment = _require_environment_bindings(
        environment_bindings
    )

    primary_sha = sha256_bytes(
        primary_metric_bytes
    )

    product_sha = sha256_bytes(
        exact_product_bytes
    )

    summary_sha = sha256_bytes(
        analysis_summary_bytes
    )

    expected_primary_sha = evidence.scientific_artifact_sha256[
        PRIMARY_METRIC_ARTIFACT
    ]

    expected_product_sha = evidence.scientific_artifact_sha256[
        EXACT_PRODUCT_ARTIFACT
    ]

    expected_summary_sha = evidence.scientific_artifact_sha256[
        ANALYSIS_SUMMARY_ARTIFACT
    ]

    if primary_sha != expected_primary_sha:
        raise SelectorDecisionFinalizationError(
            "primary metric artifact SHA256 mismatch"
        )

    if product_sha != expected_product_sha:
        raise SelectorDecisionFinalizationError(
            "exact product artifact SHA256 mismatch"
        )

    if summary_sha != expected_summary_sha:
        raise SelectorDecisionFinalizationError(
            "analysis summary artifact SHA256 mismatch"
        )

    metrics = parse_primary_metrics(
        primary_metric_bytes
    )

    stored_products = parse_exact_products(
        exact_product_bytes
    )

    verify_analysis_summary(
        analysis_summary_bytes,
        expected_primary_metric_sha256=(
            primary_sha
        ),
        expected_exact_product_sha256=(
            product_sha
        ),
    )

    recomputed_products = {
        selector:
            exact_six_size_product(
                {
                    panel_size:
                        metrics[
                            (
                                selector,
                                panel_size,
                            )
                        ]
                    for panel_size in PANEL_SIZES
                }
            )
        for selector in SELECTORS
    }

    if recomputed_products != stored_products:
        raise SelectorDecisionFinalizationError(
            "stored exact products do not match independent recomputation "
            "from primary metrics"
        )

    # The real execution path reaches exactly one selector comparison here.
    decision = resolve_exact_products(
        stored_products[
            "OPS"
        ],
        stored_products[
            "SR"
        ],
    )

    if decision not in {
        "OPS",
        "SR",
        "UNRESOLVED",
    }:
        raise SelectorDecisionFinalizationError(
            "exact selector resolver returned an invalid decision"
        )

    record = {
        "schema_version":
            1,
        "status":
            "STAGE7_SELECTOR_DECISION_FINALIZED",
        "decision":
            decision,
        "analysis_execution_commit":
            evidence.analysis_execution_commit,
        "finalizer_execution_commit":
            finalizer_execution_commit,
        "exact_products": {
            selector: {
                "numerator":
                    stored_products[
                        selector
                    ].numerator,
                "denominator":
                    stored_products[
                        selector
                    ].denominator,
            }
            for selector in SELECTORS
        },
        "artifact_sha256": {
            PRIMARY_METRIC_ARTIFACT:
                primary_sha,
            EXACT_PRODUCT_ARTIFACT:
                product_sha,
            ANALYSIS_SUMMARY_ARTIFACT:
                summary_sha,
        },
        "byte_identity_verification_record_sha256":
            evidence.byte_identity_sha256,
        "stage7_completion_evidence_sha256":
            evidence.completion_sha256,
        "selector_resolution_design_sha256":
            evidence.selector_resolution_design_sha256,
        "stage7_method_sha256":
            evidence.stage7_method_sha256,
        "finalizer_method_sha256":
            finalizer_method_sha256,
        "final_ladder_sha256":
            dict(
                evidence.final_ladder_sha256
            ),
        "analysis_implementation_bindings":
            dict(
                evidence.implementation_bindings
            ),
        "finalizer_implementation_bindings": {
            "implementation_sha256":
                finalizer_implementation_sha256,
            "test_sha256":
                finalizer_test_sha256,
        },
        "environment_bindings":
            environment,
    }

    encoded = _canonical_json_bytes(
        record
    )

    _assert_no_identity_text(
        encoded,
        label="selector decision record",
    )

    return encoded
