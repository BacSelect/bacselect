"""Synthetic-only tests for Stage 7 selector-decision finalization."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import hashlib
import json

import pytest

import bacselect.selector_decision_finalization as finalization
from bacselect.selector_decision_finalization import (
    FINAL_LADDER_SHA256,
    SelectorDecisionFinalizationError,
    finalize_selector_decision,
    parse_exact_products,
    parse_primary_metrics,
    sha256_bytes,
    verify_analysis_summary,
    verify_finalization_evidence,
)
from bacselect.selector_resolution import (
    PANEL_SIZES,
    exact_six_size_product,
)
from bacselect.selector_resolution_artifacts import (
    SCIENTIFIC_ARTIFACT_NAMES,
    SELECTORS,
    serialize_analysis_summary,
    serialize_exact_products,
    serialize_primary_metrics,
)


def canonical_json_bytes(
    payload,
):
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


def sha(
    token: str,
) -> str:
    return hashlib.sha256(
        token.encode(
            "utf-8"
        )
    ).hexdigest()


def synthetic_metrics(
    *,
    ops_value: float = 0.5,
    sr_value: float = 0.75,
):
    return {
        (
            selector,
            panel_size,
        ):
            (
                ops_value
                if selector == "OPS"
                else sr_value
            )
        for selector in SELECTORS
        for panel_size in PANEL_SIZES
    }


def synthetic_products(
    metrics,
):
    return {
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


def make_bundle(
    *,
    ops_value: float = 0.5,
    sr_value: float = 0.75,
):
    metrics = synthetic_metrics(
        ops_value=ops_value,
        sr_value=sr_value,
    )

    primary = serialize_primary_metrics(
        metrics
    )

    products = synthetic_products(
        metrics
    )

    product_payload = serialize_exact_products(
        products
    )

    summary = serialize_analysis_summary(
        {
            "schema_version":
                1,
            "status":
                "STAGE7_ANALYSIS_COMPLETE",
            "primary_metric_table_sha256":
                sha256_bytes(
                    primary
                ),
            "selector_exact_products_sha256":
                sha256_bytes(
                    product_payload
                ),
        }
    )

    scientific_sha = {
        "blinded-holdout-projected-coordinates.tsv":
            sha(
                "coordinates"
            ),
        "blinded-holdout-nearest-panel-distances.tsv":
            sha(
                "distances"
            ),
        "selector-primary-metrics.tsv":
            sha256_bytes(
                primary
            ),
        "selector-descriptive-diagnostics.json":
            sha(
                "diagnostics"
            ),
        "selector-exact-products.json":
            sha256_bytes(
                product_payload
            ),
        "selector-resolution-analysis-summary.json":
            sha256_bytes(
                summary
            ),
    }

    implementation_bindings = {
        "scientific_core_sha256":
            sha(
                "scientific-core"
            ),
        "artifact_layer_sha256":
            sha(
                "artifact-layer"
            ),
    }

    production_provenance = {
        "predecision_provenance_sha256":
            sha(
                "production-predecision"
            ),
        "execution_provenance_sha256":
            sha(
                "production-execution"
            ),
        "content_manifest_sha256":
            sha(
                "production-manifest"
            ),
    }

    rebuild_provenance = {
        "predecision_provenance_sha256":
            sha(
                "rebuild-predecision"
            ),
        "execution_provenance_sha256":
            sha(
                "rebuild-execution"
            ),
        "content_manifest_sha256":
            sha(
                "rebuild-manifest"
            ),
    }

    analysis_commit = (
        "1"
        * 40
    )

    stage7_method_sha = sha(
        "stage7-method"
    )

    design_sha = sha(
        "selector-design"
    )

    byte_identity_placeholder = sha(
        "byte-identity-placeholder"
    )

    completion = {
        "schema_version":
            1,
        "stage":
            "selector-v1-stage7",
        "status":
            "STAGE7_ANALYSIS_COMPLETE_BYTE_IDENTICAL",
        "execution_commit":
            analysis_commit,
        "stage7_method_sha256":
            stage7_method_sha,
        "selector_resolution_design_sha256":
            design_sha,
        "stage6_completion_evidence_sha256":
            sha(
                "stage6-completion"
            ),
        "implementation_bindings":
            implementation_bindings,
        "production_scientific_artifact_sha256":
            scientific_sha,
        "rebuild_scientific_artifact_sha256":
            scientific_sha,
        "production_provenance_sha256":
            production_provenance,
        "rebuild_provenance_sha256":
            rebuild_provenance,
        "byte_identity_verification_record_sha256":
            byte_identity_placeholder,
        "all_scientific_artifacts_byte_identical":
            True,
        "identity_bearing_outputs_committed_to_git":
            False,
        "selector_outcome_generated":
            False,
        "selector_decision_finalized":
            False,
    }

    comparisons = [
        {
            "artifact":
                name,
            "production_sha256":
                scientific_sha[
                    name
                ],
            "rebuild_sha256":
                scientific_sha[
                    name
                ],
            "byte_identical":
                True,
        }
        for name in SCIENTIFIC_ARTIFACT_NAMES
    ]

    byte_identity = {
        "schema_version":
            1,
        "stage":
            "selector-v1-stage7",
        "status":
            "STAGE7_SCIENTIFIC_ARTIFACTS_BYTE_IDENTICAL",
        "production_run_identity": {
            "execution_commit":
                analysis_commit,
            "execution_mode":
                "production",
            **production_provenance,
        },
        "rebuild_run_identity": {
            "execution_commit":
                analysis_commit,
            "execution_mode":
                "independent_rebuild",
            **rebuild_provenance,
        },
        "scientific_artifact_comparisons":
            comparisons,
        "all_scientific_artifacts_byte_identical":
            True,
    }

    byte_identity_bytes = canonical_json_bytes(
        byte_identity
    )

    byte_identity_sha = sha256_bytes(
        byte_identity_bytes
    )

    completion[
        "byte_identity_verification_record_sha256"
    ] = byte_identity_sha

    completion_bytes = canonical_json_bytes(
        completion
    )

    return {
        "metrics":
            metrics,
        "products":
            products,
        "primary":
            primary,
        "product_payload":
            product_payload,
        "summary":
            summary,
        "scientific_sha":
            scientific_sha,
        "implementation_bindings":
            implementation_bindings,
        "production_provenance":
            production_provenance,
        "rebuild_provenance":
            rebuild_provenance,
        "stage7_method_sha":
            stage7_method_sha,
        "design_sha":
            design_sha,
        "completion":
            completion,
        "completion_bytes":
            completion_bytes,
        "completion_sha":
            sha256_bytes(
                completion_bytes
            ),
        "byte_identity":
            byte_identity,
        "byte_identity_bytes":
            byte_identity_bytes,
        "byte_identity_sha":
            byte_identity_sha,
    }


def rebind_decision_artifacts(
    bundle,
    *,
    product_payload,
    summary,
):
    """Return a synthetic bundle with consistently rebound decision hashes."""
    changed = dict(
        bundle
    )

    scientific = dict(
        bundle[
            "scientific_sha"
        ]
    )

    scientific[
        "selector-exact-products.json"
    ] = sha256_bytes(
        product_payload
    )

    scientific[
        "selector-resolution-analysis-summary.json"
    ] = sha256_bytes(
        summary
    )

    byte_identity = json.loads(
        bundle[
            "byte_identity_bytes"
        ]
    )

    for item in byte_identity[
        "scientific_artifact_comparisons"
    ]:
        name = item[
            "artifact"
        ]

        if name in scientific:
            item[
                "production_sha256"
            ] = scientific[
                name
            ]

            item[
                "rebuild_sha256"
            ] = scientific[
                name
            ]

    byte_identity_bytes = canonical_json_bytes(
        byte_identity
    )

    byte_identity_sha = sha256_bytes(
        byte_identity_bytes
    )

    completion = json.loads(
        bundle[
            "completion_bytes"
        ]
    )

    completion[
        "production_scientific_artifact_sha256"
    ] = scientific

    completion[
        "rebuild_scientific_artifact_sha256"
    ] = scientific

    completion[
        "byte_identity_verification_record_sha256"
    ] = byte_identity_sha

    completion_bytes = canonical_json_bytes(
        completion
    )

    changed.update(
        {
            "product_payload":
                product_payload,
            "summary":
                summary,
            "scientific_sha":
                scientific,
            "byte_identity":
                byte_identity,
            "byte_identity_bytes":
                byte_identity_bytes,
            "byte_identity_sha":
                byte_identity_sha,
            "completion":
                completion,
            "completion_bytes":
                completion_bytes,
            "completion_sha":
                sha256_bytes(
                    completion_bytes
                ),
        }
    )

    return changed


def verified_evidence(
    bundle,
):
    return verify_finalization_evidence(
        completion_bytes=(
            bundle[
                "completion_bytes"
            ]
        ),
        byte_identity_bytes=(
            bundle[
                "byte_identity_bytes"
            ]
        ),
        expected_completion_sha256=(
            bundle[
                "completion_sha"
            ]
        ),
        expected_byte_identity_sha256=(
            bundle[
                "byte_identity_sha"
            ]
        ),
        expected_stage7_method_sha256=(
            bundle[
                "stage7_method_sha"
            ]
        ),
        expected_selector_resolution_design_sha256=(
            bundle[
                "design_sha"
            ]
        ),
        expected_implementation_bindings=(
            bundle[
                "implementation_bindings"
            ]
        ),
        observed_production_scientific_sha256=(
            bundle[
                "scientific_sha"
            ]
        ),
        observed_rebuild_scientific_sha256=(
            bundle[
                "scientific_sha"
            ]
        ),
        observed_production_provenance_sha256=(
            bundle[
                "production_provenance"
            ]
        ),
        observed_rebuild_provenance_sha256=(
            bundle[
                "rebuild_provenance"
            ]
        ),
        observed_final_ladder_sha256=(
            FINAL_LADDER_SHA256
        ),
    )


def finalize_bundle(
    bundle,
):
    evidence = verified_evidence(
        bundle
    )

    return finalize_selector_decision(
        evidence=evidence,
        primary_metric_bytes=(
            bundle[
                "primary"
            ]
        ),
        exact_product_bytes=(
            bundle[
                "product_payload"
            ]
        ),
        analysis_summary_bytes=(
            bundle[
                "summary"
            ]
        ),
        finalizer_execution_commit=(
            "2"
            * 40
        ),
        finalizer_method_sha256=sha(
            "finalizer-method"
        ),
        finalizer_implementation_sha256=sha(
            "finalizer-implementation"
        ),
        finalizer_test_sha256=sha(
            "finalizer-test"
        ),
        environment_bindings={
            "environment_lock_sha256":
                sha(
                    "environment"
                ),
            "python":
                "3.synthetic",
        },
    )


# Prospective requirements 1-6: aggregate completion/byte-identity gates.

def test_completion_identity_is_required() -> None:
    bundle = make_bundle()

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="completion evidence SHA256 mismatch",
    ):
        verify_finalization_evidence(
            completion_bytes=(
                bundle[
                    "completion_bytes"
                ]
            ),
            byte_identity_bytes=(
                bundle[
                    "byte_identity_bytes"
                ]
            ),
            expected_completion_sha256=(
                "0"
                * 64
            ),
            expected_byte_identity_sha256=(
                bundle[
                    "byte_identity_sha"
                ]
            ),
            expected_stage7_method_sha256=(
                bundle[
                    "stage7_method_sha"
                ]
            ),
            expected_selector_resolution_design_sha256=(
                bundle[
                    "design_sha"
                ]
            ),
            expected_implementation_bindings=(
                bundle[
                    "implementation_bindings"
                ]
            ),
            observed_production_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_rebuild_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_production_provenance_sha256=(
                bundle[
                    "production_provenance"
                ]
            ),
            observed_rebuild_provenance_sha256=(
                bundle[
                    "rebuild_provenance"
                ]
            ),
            observed_final_ladder_sha256=(
                FINAL_LADDER_SHA256
            ),
        )


def test_byte_identity_record_identity_is_required() -> None:
    bundle = make_bundle()

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="byte-identity record SHA256 binding mismatch",
    ):
        verify_finalization_evidence(
            completion_bytes=(
                bundle[
                    "completion_bytes"
                ]
            ),
            byte_identity_bytes=(
                bundle[
                    "byte_identity_bytes"
                ]
            ),
            expected_completion_sha256=(
                bundle[
                    "completion_sha"
                ]
            ),
            expected_byte_identity_sha256=(
                "0"
                * 64
            ),
            expected_stage7_method_sha256=(
                bundle[
                    "stage7_method_sha"
                ]
            ),
            expected_selector_resolution_design_sha256=(
                bundle[
                    "design_sha"
                ]
            ),
            expected_implementation_bindings=(
                bundle[
                    "implementation_bindings"
                ]
            ),
            observed_production_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_rebuild_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_production_provenance_sha256=(
                bundle[
                    "production_provenance"
                ]
            ),
            observed_rebuild_provenance_sha256=(
                bundle[
                    "rebuild_provenance"
                ]
            ),
            observed_final_ladder_sha256=(
                FINAL_LADDER_SHA256
            ),
        )


def test_false_per_artifact_byte_identity_blocks() -> None:
    bundle = make_bundle()

    record = json.loads(
        bundle[
            "byte_identity_bytes"
        ]
    )

    record[
        "scientific_artifact_comparisons"
    ][0][
        "byte_identical"
    ] = False

    changed = canonical_json_bytes(
        record
    )

    changed_sha = sha256_bytes(
        changed
    )

    completion = json.loads(
        bundle[
            "completion_bytes"
        ]
    )

    completion[
        "byte_identity_verification_record_sha256"
    ] = changed_sha

    completion_bytes = canonical_json_bytes(
        completion
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="byte-identical flag is false",
    ):
        verify_finalization_evidence(
            completion_bytes=completion_bytes,
            byte_identity_bytes=changed,
            expected_completion_sha256=sha256_bytes(
                completion_bytes
            ),
            expected_byte_identity_sha256=changed_sha,
            expected_stage7_method_sha256=(
                bundle[
                    "stage7_method_sha"
                ]
            ),
            expected_selector_resolution_design_sha256=(
                bundle[
                    "design_sha"
                ]
            ),
            expected_implementation_bindings=(
                bundle[
                    "implementation_bindings"
                ]
            ),
            observed_production_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_rebuild_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_production_provenance_sha256=(
                bundle[
                    "production_provenance"
                ]
            ),
            observed_rebuild_provenance_sha256=(
                bundle[
                    "rebuild_provenance"
                ]
            ),
            observed_final_ladder_sha256=(
                FINAL_LADDER_SHA256
            ),
        )


def test_false_aggregate_byte_identity_blocks() -> None:
    bundle = make_bundle()

    completion = json.loads(
        bundle[
            "completion_bytes"
        ]
    )

    completion[
        "all_scientific_artifacts_byte_identical"
    ] = False

    changed = canonical_json_bytes(
        completion
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="all_scientific_artifacts_byte_identical",
    ):
        verify_finalization_evidence(
            completion_bytes=changed,
            byte_identity_bytes=(
                bundle[
                    "byte_identity_bytes"
                ]
            ),
            expected_completion_sha256=sha256_bytes(
                changed
            ),
            expected_byte_identity_sha256=(
                bundle[
                    "byte_identity_sha"
                ]
            ),
            expected_stage7_method_sha256=(
                bundle[
                    "stage7_method_sha"
                ]
            ),
            expected_selector_resolution_design_sha256=(
                bundle[
                    "design_sha"
                ]
            ),
            expected_implementation_bindings=(
                bundle[
                    "implementation_bindings"
                ]
            ),
            observed_production_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_rebuild_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_production_provenance_sha256=(
                bundle[
                    "production_provenance"
                ]
            ),
            observed_rebuild_provenance_sha256=(
                bundle[
                    "rebuild_provenance"
                ]
            ),
            observed_final_ladder_sha256=(
                FINAL_LADDER_SHA256
            ),
        )


def test_run_identity_mismatch_blocks() -> None:
    bundle = make_bundle()

    record = json.loads(
        bundle[
            "byte_identity_bytes"
        ]
    )

    record[
        "rebuild_run_identity"
    ][
        "execution_commit"
    ] = "3" * 40

    changed = canonical_json_bytes(
        record
    )

    changed_sha = sha256_bytes(
        changed
    )

    completion = json.loads(
        bundle[
            "completion_bytes"
        ]
    )

    completion[
        "byte_identity_verification_record_sha256"
    ] = changed_sha

    completion_bytes = canonical_json_bytes(
        completion
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="execution commit mismatch",
    ):
        verify_finalization_evidence(
            completion_bytes=completion_bytes,
            byte_identity_bytes=changed,
            expected_completion_sha256=sha256_bytes(
                completion_bytes
            ),
            expected_byte_identity_sha256=changed_sha,
            expected_stage7_method_sha256=(
                bundle[
                    "stage7_method_sha"
                ]
            ),
            expected_selector_resolution_design_sha256=(
                bundle[
                    "design_sha"
                ]
            ),
            expected_implementation_bindings=(
                bundle[
                    "implementation_bindings"
                ]
            ),
            observed_production_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_rebuild_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_production_provenance_sha256=(
                bundle[
                    "production_provenance"
                ]
            ),
            observed_rebuild_provenance_sha256=(
                bundle[
                    "rebuild_provenance"
                ]
            ),
            observed_final_ladder_sha256=(
                FINAL_LADDER_SHA256
            ),
        )


def test_any_observed_scientific_hash_mismatch_blocks() -> None:
    bundle = make_bundle()

    observed = dict(
        bundle[
            "scientific_sha"
        ]
    )

    observed[
        "selector-descriptive-diagnostics.json"
    ] = sha(
        "wrong"
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="observed production scientific hashes",
    ):
        verify_finalization_evidence(
            completion_bytes=(
                bundle[
                    "completion_bytes"
                ]
            ),
            byte_identity_bytes=(
                bundle[
                    "byte_identity_bytes"
                ]
            ),
            expected_completion_sha256=(
                bundle[
                    "completion_sha"
                ]
            ),
            expected_byte_identity_sha256=(
                bundle[
                    "byte_identity_sha"
                ]
            ),
            expected_stage7_method_sha256=(
                bundle[
                    "stage7_method_sha"
                ]
            ),
            expected_selector_resolution_design_sha256=(
                bundle[
                    "design_sha"
                ]
            ),
            expected_implementation_bindings=(
                bundle[
                    "implementation_bindings"
                ]
            ),
            observed_production_scientific_sha256=observed,
            observed_rebuild_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_production_provenance_sha256=(
                bundle[
                    "production_provenance"
                ]
            ),
            observed_rebuild_provenance_sha256=(
                bundle[
                    "rebuild_provenance"
                ]
            ),
            observed_final_ladder_sha256=(
                FINAL_LADDER_SHA256
            ),
        )


def test_final_ladder_fingerprints_are_exact() -> None:
    bundle = make_bundle()

    changed = dict(
        FINAL_LADDER_SHA256
    )

    changed[
        "OPS"
    ] = sha(
        "wrong-ops-ladder"
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="final OPS/SR ladder fingerprints",
    ):
        verify_finalization_evidence(
            completion_bytes=(
                bundle[
                    "completion_bytes"
                ]
            ),
            byte_identity_bytes=(
                bundle[
                    "byte_identity_bytes"
                ]
            ),
            expected_completion_sha256=(
                bundle[
                    "completion_sha"
                ]
            ),
            expected_byte_identity_sha256=(
                bundle[
                    "byte_identity_sha"
                ]
            ),
            expected_stage7_method_sha256=(
                bundle[
                    "stage7_method_sha"
                ]
            ),
            expected_selector_resolution_design_sha256=(
                bundle[
                    "design_sha"
                ]
            ),
            expected_implementation_bindings=(
                bundle[
                    "implementation_bindings"
                ]
            ),
            observed_production_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_rebuild_scientific_sha256=(
                bundle[
                    "scientific_sha"
                ]
            ),
            observed_production_provenance_sha256=(
                bundle[
                    "production_provenance"
                ]
            ),
            observed_rebuild_provenance_sha256=(
                bundle[
                    "rebuild_provenance"
                ]
            ),
            observed_final_ladder_sha256=changed,
        )


# Prospective requirements 7-15: primary metric schema.

def test_primary_metric_parser_accepts_canonical_twelve_rows() -> None:
    bundle = make_bundle()

    parsed = parse_primary_metrics(
        bundle[
            "primary"
        ]
    )

    assert parsed == bundle[
        "metrics"
    ]


@pytest.mark.parametrize(
    "payload,match",
    (
        (
            b"selector\tN\twrong\n",
            "exactly 12",
        ),
        (
            (
                b"wrong\tN\tweighted_p95\n"
                + b"OPS\t10\t1\n" * 12
            ),
            "header mismatch",
        ),
    ),
)
def test_primary_metric_basic_schema_rejected(
    payload,
    match,
) -> None:
    with pytest.raises(
        SelectorDecisionFinalizationError,
        match=match,
    ):
        parse_primary_metrics(
            payload
        )


def test_primary_metric_row_order_is_exact() -> None:
    bundle = make_bundle()

    lines = bundle[
        "primary"
    ].decode(
        "utf-8"
    ).splitlines()

    lines[
        1
    ], lines[
        2
    ] = lines[
        2
    ], lines[
        1
    ]

    changed = (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="row order",
    ):
        parse_primary_metrics(
            changed
        )


def test_primary_metric_duplicate_row_is_rejected() -> None:
    bundle = make_bundle()

    lines = bundle[
        "primary"
    ].decode(
        "utf-8"
    ).splitlines()

    lines[
        2
    ] = lines[
        1
    ]

    changed = (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="row order|duplicate",
    ):
        parse_primary_metrics(
            changed
        )


def test_primary_metric_additional_column_is_rejected() -> None:
    bundle = make_bundle()

    lines = bundle[
        "primary"
    ].decode(
        "utf-8"
    ).splitlines()

    lines[
        1
    ] += "\textra"

    changed = (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="three columns",
    ):
        parse_primary_metrics(
            changed
        )


@pytest.mark.parametrize(
    "value",
    (
        "nan",
        "inf",
        "-1",
    ),
)
def test_primary_metric_nonfinite_or_negative_is_rejected(
    value,
) -> None:
    bundle = make_bundle()

    lines = bundle[
        "primary"
    ].decode(
        "utf-8"
    ).splitlines()

    fields = lines[
        1
    ].split(
        "\t"
    )

    fields[
        2
    ] = value

    lines[
        1
    ] = "\t".join(
        fields
    )

    changed = (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="finite and non-negative",
    ):
        parse_primary_metrics(
            changed
        )


def test_primary_metric_noncanonical_serialization_is_rejected() -> None:
    bundle = make_bundle()

    text = bundle[
        "primary"
    ].decode(
        "utf-8"
    )

    changed = text.replace(
        "\t0.5\n",
        "\t0.500\n",
        1,
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="not canonical",
    ):
        parse_primary_metrics(
            changed
        )


# Prospective requirements 16-22: exact-product artifact schema.

def test_exact_product_parser_accepts_canonical_products() -> None:
    bundle = make_bundle()

    assert parse_exact_products(
        bundle[
            "product_payload"
        ]
    ) == bundle[
        "products"
    ]


def mutate_product_payload(
    bundle,
    callback,
):
    parsed = json.loads(
        bundle[
            "product_payload"
        ]
    )

    callback(
        parsed
    )

    return canonical_json_bytes(
        parsed
    )


def test_exact_product_selector_set_is_exact() -> None:
    bundle = make_bundle()

    changed = mutate_product_payload(
        bundle,
        lambda payload:
            payload[
                "selectors"
            ].pop(
                "SR"
            ),
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="selector set",
    ):
        parse_exact_products(
            changed
        )


@pytest.mark.parametrize(
    "field,value,match",
    (
        (
            "numerator",
            1.5,
            "numerator must be an integer",
        ),
        (
            "denominator",
            2.5,
            "denominator must be an integer",
        ),
        (
            "numerator",
            -1,
            "numerator must be non-negative",
        ),
        (
            "denominator",
            0,
            "denominator must be positive",
        ),
        (
            "denominator",
            -2,
            "denominator must be positive",
        ),
    ),
)
def test_invalid_exact_product_numbers_are_rejected(
    field,
    value,
    match,
) -> None:
    bundle = make_bundle()

    changed = mutate_product_payload(
        bundle,
        lambda payload:
            payload[
                "selectors"
            ][
                "OPS"
            ].__setitem__(
                field,
                value,
            ),
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match=match,
    ):
        parse_exact_products(
            changed
        )


def test_nonreduced_exact_product_is_rejected() -> None:
    bundle = make_bundle()

    changed = mutate_product_payload(
        bundle,
        lambda payload:
            payload[
                "selectors"
            ].__setitem__(
                "OPS",
                {
                    "numerator":
                        2,
                    "denominator":
                        4,
                },
            ),
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="already be reduced",
    ):
        parse_exact_products(
            changed
        )


def test_noncanonical_exact_product_serialization_is_rejected() -> None:
    bundle = make_bundle()

    parsed = json.loads(
        bundle[
            "product_payload"
        ]
    )

    changed = json.dumps(
        parsed,
        separators=(
            ",",
            ":",
        ),
        sort_keys=True,
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="not canonical",
    ):
        parse_exact_products(
            changed
        )


def test_outcome_field_in_exact_product_is_rejected() -> None:
    bundle = make_bundle()

    changed = mutate_product_payload(
        bundle,
        lambda payload:
            payload.__setitem__(
                "winner",
                "OPS",
            ),
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="schema mismatch",
    ):
        parse_exact_products(
            changed
        )


# Prospective requirements 23-24: independent exact recomputation.

def test_stored_products_must_recompute_from_primary_metrics() -> None:
    bundle = make_bundle()

    wrong_products = serialize_exact_products(
        {
            "OPS":
                Fraction(
                    1,
                    2,
                ),
            "SR":
                bundle[
                    "products"
                ][
                    "SR"
                ],
        }
    )

    wrong_summary = serialize_analysis_summary(
        {
            "schema_version":
                1,
            "status":
                "STAGE7_ANALYSIS_COMPLETE",
            "primary_metric_table_sha256":
                sha256_bytes(
                    bundle[
                        "primary"
                    ]
                ),
            "selector_exact_products_sha256":
                sha256_bytes(
                    wrong_products
                ),
        }
    )

    changed = rebind_decision_artifacts(
        bundle,
        product_payload=wrong_products,
        summary=wrong_summary,
    )

    evidence = verified_evidence(
        changed
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="independent recomputation",
    ):
        finalize_selector_decision(
            evidence=evidence,
            primary_metric_bytes=(
                changed[
                    "primary"
                ]
            ),
            exact_product_bytes=(
                changed[
                    "product_payload"
                ]
            ),
            analysis_summary_bytes=(
                changed[
                    "summary"
                ]
            ),
            finalizer_execution_commit=(
                "2"
                * 40
            ),
            finalizer_method_sha256=sha(
                "finalizer-method"
            ),
            finalizer_implementation_sha256=sha(
                "implementation"
            ),
            finalizer_test_sha256=sha(
                "test"
            ),
            environment_bindings={
                "python":
                    "synthetic",
            },
        )


def test_unverified_finalization_evidence_is_rejected() -> None:
    bundle = make_bundle()

    evidence = verified_evidence(
        bundle
    )

    forged = replace(
        evidence,
        _verification_token=object(),
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="not produced by verify_finalization_evidence",
    ):
        finalize_selector_decision(
            evidence=forged,
            primary_metric_bytes=(
                bundle[
                    "primary"
                ]
            ),
            exact_product_bytes=(
                bundle[
                    "product_payload"
                ]
            ),
            analysis_summary_bytes=(
                bundle[
                    "summary"
                ]
            ),
            finalizer_execution_commit=(
                "2"
                * 40
            ),
            finalizer_method_sha256=sha(
                "finalizer-method"
            ),
            finalizer_implementation_sha256=sha(
                "implementation"
            ),
            finalizer_test_sha256=sha(
                "test"
            ),
            environment_bindings={
                "python":
                    "synthetic",
            },
        )


def test_verified_evidence_mappings_are_immutable() -> None:
    bundle = make_bundle()

    evidence = verified_evidence(
        bundle
    )

    with pytest.raises(
        TypeError,
    ):
        evidence.scientific_artifact_sha256[
            "selector-exact-products.json"
        ] = sha(
            "mutated"
        )




# Prospective requirements 25-28: summary bindings/blinding.

def test_analysis_summary_requires_primary_hash_binding() -> None:
    bundle = make_bundle()

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="primary-metric SHA256 binding",
    ):
        verify_analysis_summary(
            bundle[
                "summary"
            ],
            expected_primary_metric_sha256=sha(
                "wrong"
            ),
            expected_exact_product_sha256=sha256_bytes(
                bundle[
                    "product_payload"
                ]
            ),
        )


def test_analysis_summary_requires_product_hash_binding() -> None:
    bundle = make_bundle()

    with pytest.raises(
        SelectorDecisionFinalizationError,
        match="exact-product SHA256 binding",
    ):
        verify_analysis_summary(
            bundle[
                "summary"
            ],
            expected_primary_metric_sha256=sha256_bytes(
                bundle[
                    "primary"
                ]
            ),
            expected_exact_product_sha256=sha(
                "wrong"
            ),
        )


@pytest.mark.parametrize(
    "key,value",
    (
        (
            "accession",
            "GCA_000000001.1",
        ),
        (
            "selector_outcome",
            "OPS",
        ),
        (
            "winner",
            "SR",
        ),
        (
            "numerator",
            1,
        ),
    ),
)
def test_analysis_summary_rejects_identity_or_outcome_values(
    key,
    value,
) -> None:
    bundle = make_bundle()

    payload = json.loads(
        bundle[
            "summary"
        ]
    )

    payload[
        key
    ] = value

    changed = canonical_json_bytes(
        payload
    )

    with pytest.raises(
        SelectorDecisionFinalizationError,
    ):
        verify_analysis_summary(
            changed,
            expected_primary_metric_sha256=sha256_bytes(
                bundle[
                    "primary"
                ]
            ),
            expected_exact_product_sha256=sha256_bytes(
                bundle[
                    "product_payload"
                ]
            ),
        )


# Prospective requirements 29-32: one exact resolver, no fallback.

@pytest.mark.parametrize(
    "ops_value,sr_value,expected",
    (
        (
            0.5,
            0.75,
            "OPS",
        ),
        (
            0.75,
            0.5,
            "SR",
        ),
        (
            0.5,
            0.5,
            "UNRESOLVED",
        ),
    ),
)
def test_exact_decision_outcomes(
    ops_value,
    sr_value,
    expected,
) -> None:
    bundle = make_bundle(
        ops_value=ops_value,
        sr_value=sr_value,
    )

    record = json.loads(
        finalize_bundle(
            bundle
        )
    )

    assert record[
        "decision"
    ] == expected


def test_real_decision_path_calls_exact_resolver_once(
    monkeypatch,
) -> None:
    bundle = make_bundle()

    observed = []

    original = (
        finalization
        .resolve_exact_products
    )

    def counted(
        ops_product,
        sr_product,
    ):
        observed.append(
            (
                ops_product,
                sr_product,
            )
        )

        return original(
            ops_product,
            sr_product,
        )

    monkeypatch.setattr(
        finalization,
        "resolve_exact_products",
        counted,
    )

    finalize_bundle(
        bundle
    )

    assert len(
        observed
    ) == 1


def test_exact_tie_has_no_secondary_fallback() -> None:
    bundle = make_bundle(
        ops_value=0.5,
        sr_value=0.5,
    )

    record = json.loads(
        finalize_bundle(
            bundle
        )
    )

    assert record[
        "decision"
    ] == "UNRESOLVED"


# Prospective requirements 33-34: aggregate-only deterministic decision record.

def test_decision_record_contains_no_identity_bearing_values() -> None:
    bundle = make_bundle()

    payload = finalize_bundle(
        bundle
    )

    text = payload.decode(
        "utf-8"
    )

    assert "GCA_" not in text
    assert "GCF_" not in text
    assert "H00000001" not in text

    record = json.loads(
        payload
    )

    assert set(
        record[
            "decision"
        ]
        if False
        else record[
            "exact_products"
        ]
    ) == {
        "OPS",
        "SR",
    }


def test_decision_record_serialization_is_deterministic() -> None:
    bundle = make_bundle()

    first = finalize_bundle(
        bundle
    )

    second = finalize_bundle(
        bundle
    )

    assert first == second


def test_decision_record_contains_required_aggregate_bindings() -> None:
    bundle = make_bundle()

    record = json.loads(
        finalize_bundle(
            bundle
        )
    )

    assert record[
        "status"
    ] == "STAGE7_SELECTOR_DECISION_FINALIZED"

    assert record[
        "artifact_sha256"
    ][
        "selector-primary-metrics.tsv"
    ] == sha256_bytes(
        bundle[
            "primary"
        ]
    )

    assert record[
        "artifact_sha256"
    ][
        "selector-exact-products.json"
    ] == sha256_bytes(
        bundle[
            "product_payload"
        ]
    )

    assert record[
        "artifact_sha256"
    ][
        "selector-resolution-analysis-summary.json"
    ] == sha256_bytes(
        bundle[
            "summary"
        ]
    )

    assert record[
        "final_ladder_sha256"
    ] == FINAL_LADDER_SHA256
