"""Synthetic tests for deterministic selector-v1 official panel generation."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from bacselect.official_panels import (
    ALL_ARTIFACTS,
    ARCHITECTURE_SCHEMA_VERSION,
    BASELINE_BINDING_KEYS,
    CONTENT_MANIFEST_FILENAME,
    CONTENT_SOURCE_ARTIFACTS,
    CUSTOM_N_MAX,
    CUSTOM_N_MIN,
    GENERATION_STATUS,
    MEMBERSHIP_MANIFEST_FILENAME,
    PANEL_ARTIFACT_SCHEMA_VERSION,
    PANEL_FILENAMES,
    PANEL_PROVENANCE_SCHEMA_VERSION,
    PANEL_SIZES,
    PROVENANCE_FILENAME,
    SELECTOR,
    SELECTOR_DECISION_COMMIT,
    SELECTOR_DECISION_RECORD_SHA256,
    SELECTOR_VERSION,
    SUMMARY_FILENAME,
    WINNING_LADDER_FILENAME,
    WINNING_LADDER_N,
    WINNING_LADDER_SHA256,
    OfficialPanelError,
    audit_reference_panel_artifacts,
    build_reference_panel_artifacts,
    canonical_json_bytes,
    first_public_panel_n,
    require_artifact_sets_byte_identical,
    resolve_verified_ops_accessions,
    serialize_custom_accession_list,
    serialize_generation_provenance,
    serialize_generation_summary,
    serialize_winning_ladder,
    sha256_bytes,
    validate_panel_size,
    validate_verified_accessions,
    verify_selector_decision_bytes,
)


def synthetic_accessions() -> tuple[str, ...]:
    return tuple(
        f"GCA_{900000000 + index:09d}.1"
        for index in range(
            1,
            501,
        )
    )


def synthetic_baseline_bindings() -> dict[str, str]:
    return {
        key:
            format(
                index,
                "064x",
            )
        for index, key in enumerate(
            sorted(
                BASELINE_BINDING_KEYS
            ),
            start=1,
        )
    }


def synthetic_provenance_kwargs() -> dict[str, object]:
    return {
        "execution_commit":
            "a" * 40,
        "implementation_sha256":
            "1" * 64,
        "implementation_test_sha256":
            "2" * 64,
        "stage7_wrapper_sha256":
            "3" * 64,
        "stage7_execution_adapter_sha256":
            "4" * 64,
        "final_geometry_helper_sha256":
            "5" * 64,
        "baseline_bindings":
            synthetic_baseline_bindings(),
        "environment_lock_sha256":
            "6" * 64,
    }


def synthetic_artifacts() -> dict[str, bytes]:
    return dict(
        build_reference_panel_artifacts(
            synthetic_accessions(),
            **synthetic_provenance_kwargs(),
        )
    )


def decision_bytes(
    decision: str,
    *,
    ops_sha: str = WINNING_LADDER_SHA256,
    sr_sha: str = "7" * 64,
) -> bytes:
    return canonical_json_bytes(
        {
            "decision":
                decision,
            "final_ladder_sha256":
                {
                    "OPS":
                        ops_sha,
                    "SR":
                        sr_sha,
                },
        }
    )


def test_exact_ops_decision_is_accepted() -> None:
    payload = decision_bytes(
        "OPS"
    )

    record = verify_selector_decision_bytes(
        payload,
        expected_sha256=sha256_bytes(
            payload
        ),
        expected_final_ladder_sha256={
            "OPS":
                WINNING_LADDER_SHA256,
            "SR":
                "7" * 64,
        },
    )

    assert record[
        "decision"
    ] == "OPS"


def test_sr_decision_is_refused() -> None:
    payload = decision_bytes(
        "SR"
    )

    with pytest.raises(
        OfficialPanelError,
        match="exactly OPS",
    ):
        verify_selector_decision_bytes(
            payload,
            expected_sha256=sha256_bytes(
                payload
            ),
            expected_final_ladder_sha256={
                "OPS":
                    WINNING_LADDER_SHA256,
                "SR":
                    "7" * 64,
            },
        )


def test_unresolved_decision_is_refused() -> None:
    payload = decision_bytes(
        "UNRESOLVED"
    )

    with pytest.raises(
        OfficialPanelError,
        match="exactly OPS",
    ):
        verify_selector_decision_bytes(
            payload,
            expected_sha256=sha256_bytes(
                payload
            ),
            expected_final_ladder_sha256={
                "OPS":
                    WINNING_LADDER_SHA256,
                "SR":
                    "7" * 64,
            },
        )


def test_malformed_decision_is_refused() -> None:
    payload = b"{not-json}\n"

    with pytest.raises(
        OfficialPanelError,
        match="valid UTF-8 JSON",
    ):
        verify_selector_decision_bytes(
            payload,
            expected_sha256=sha256_bytes(
                payload
            ),
            expected_final_ladder_sha256={
                "OPS":
                    WINNING_LADDER_SHA256,
                "SR":
                    "7" * 64,
            },
        )


def test_decision_record_sha_mismatch_is_refused() -> None:
    payload = decision_bytes(
        "OPS"
    )

    with pytest.raises(
        OfficialPanelError,
        match="SHA256 mismatch",
    ):
        verify_selector_decision_bytes(
            payload,
            expected_sha256="0" * 64,
            expected_final_ladder_sha256={
                "OPS":
                    WINNING_LADDER_SHA256,
                "SR":
                    "7" * 64,
            },
        )


def test_winning_ladder_fingerprint_mismatch_is_refused() -> None:
    payload = decision_bytes(
        "OPS",
        ops_sha="8" * 64,
    )

    with pytest.raises(
        OfficialPanelError,
        match="frozen winner",
    ):
        verify_selector_decision_bytes(
            payload,
            expected_sha256=sha256_bytes(
                payload
            ),
            expected_final_ladder_sha256={
                "OPS":
                    "8" * 64,
                "SR":
                    "7" * 64,
            },
        )


def test_incorrect_ops_ladder_length_is_refused() -> None:
    baseline = synthetic_accessions()

    with pytest.raises(
        OfficialPanelError,
        match="exactly 500 indices",
    ):
        resolve_verified_ops_accessions(
            tuple(
                range(
                    499
                )
            ),
            baseline,
        )


def test_duplicate_ladder_index_is_refused() -> None:
    baseline = synthetic_accessions()

    indices = list(
        range(
            500
        )
    )

    indices[
        -1
    ] = indices[
        -2
    ]

    with pytest.raises(
        OfficialPanelError,
        match="indices must be unique",
    ):
        resolve_verified_ops_accessions(
            indices,
            baseline,
        )


def test_out_of_range_ladder_index_is_refused() -> None:
    baseline = synthetic_accessions()

    indices = list(
        range(
            500
        )
    )

    indices[
        -1
    ] = 500

    with pytest.raises(
        OfficialPanelError,
        match="outside baseline",
    ):
        resolve_verified_ops_accessions(
            indices,
            baseline,
        )


def test_duplicate_resolved_accession_is_refused() -> None:
    baseline = list(
        synthetic_accessions()
    )

    baseline[
        -1
    ] = baseline[
        -2
    ]

    with pytest.raises(
        OfficialPanelError,
        match="accessions must be unique",
    ):
        resolve_verified_ops_accessions(
            tuple(
                range(
                    500
                )
            ),
            baseline,
        )


def test_malformed_gca_accession_is_refused() -> None:
    accessions = list(
        synthetic_accessions()
    )

    accessions[
        250
    ] = "GCF_999999999.1"

    with pytest.raises(
        OfficialPanelError,
        match="canonical GCA",
    ):
        validate_verified_accessions(
            accessions
        )


def test_panel_size_below_ten_is_refused() -> None:
    with pytest.raises(
        OfficialPanelError,
        match="10 <= N <= 500",
    ):
        validate_panel_size(
            9
        )


def test_panel_size_above_five_hundred_is_refused() -> None:
    with pytest.raises(
        OfficialPanelError,
        match="10 <= N <= 500",
    ):
        validate_panel_size(
            501
        )


def test_noninteger_panel_size_is_refused() -> None:
    with pytest.raises(
        TypeError,
        match="integer",
    ):
        validate_panel_size(
            10.0
        )


def test_boolean_panel_size_is_refused() -> None:
    with pytest.raises(
        TypeError,
        match="integer",
    ):
        validate_panel_size(
            True
        )


@pytest.mark.parametrize(
    "panel_size",
    PANEL_SIZES,
)
def test_exact_preset_panel_prefixes(
    panel_size: int,
) -> None:
    accessions = synthetic_accessions()

    payload = serialize_custom_accession_list(
        accessions,
        panel_size,
    )

    assert payload.decode(
        "utf-8"
    ).splitlines() == list(
        accessions[
            :panel_size
        ]
    )


def test_exact_custom_n_prefix() -> None:
    accessions = synthetic_accessions()

    payload = serialize_custom_accession_list(
        accessions,
        137,
    )

    assert payload.decode(
        "utf-8"
    ).splitlines() == list(
        accessions[
            :137
        ]
    )


def test_accession_list_has_exact_final_newline() -> None:
    payload = serialize_custom_accession_list(
        synthetic_accessions(),
        10,
    )

    assert payload.endswith(
        b"\n"
    )

    assert not payload.endswith(
        b"\n\n"
    )


def test_ladder_tsv_header_is_exact() -> None:
    payload = serialize_winning_ladder(
        synthetic_accessions()
    )

    assert payload.decode(
        "utf-8"
    ).splitlines()[
        0
    ] == (
        "rank\taccession\tfirst_public_panel_n"
    )


def test_membership_manifest_header_is_exact() -> None:
    artifacts = synthetic_artifacts()

    assert artifacts[
        MEMBERSHIP_MANIFEST_FILENAME
    ].decode(
        "utf-8"
    ).splitlines()[
        0
    ] == (
        "panel_size\tmember_count\taccession_list_sha256"
    )


def test_content_manifest_header_is_exact() -> None:
    artifacts = synthetic_artifacts()

    assert artifacts[
        CONTENT_MANIFEST_FILENAME
    ].decode(
        "utf-8"
    ).splitlines()[
        0
    ] == (
        "artifact\tsha256\tbytes\tdata_rows"
    )


def test_generation_summary_is_canonical_and_exact() -> None:
    payload = serialize_generation_summary()

    parsed = json.loads(
        payload.decode(
            "utf-8"
        )
    )

    assert canonical_json_bytes(
        parsed
    ) == payload

    assert parsed == {
        "architecture_schema_version":
            ARCHITECTURE_SCHEMA_VERSION,
        "custom_n_max":
            CUSTOM_N_MAX,
        "custom_n_min":
            CUSTOM_N_MIN,
        "monthly_release_assigned":
            False,
        "nested_prefix_property":
            True,
        "preset_panel_sizes":
            list(
                PANEL_SIZES
            ),
        "schema_version":
            PANEL_ARTIFACT_SCHEMA_VERSION,
        "selector":
            SELECTOR,
        "selector_decision_commit":
            SELECTOR_DECISION_COMMIT,
        "selector_decision_record_sha256":
            SELECTOR_DECISION_RECORD_SHA256,
        "selector_version":
            SELECTOR_VERSION,
        "status":
            GENERATION_STATUS,
        "winning_ladder_accession_count":
            WINNING_LADDER_N,
        "winning_ladder_n":
            WINNING_LADDER_N,
        "winning_ladder_sha256":
            WINNING_LADDER_SHA256,
    }


def test_generation_provenance_is_canonical_and_exact_schema() -> None:
    payload = serialize_generation_provenance(
        **synthetic_provenance_kwargs()
    )

    parsed = json.loads(
        payload.decode(
            "utf-8"
        )
    )

    assert canonical_json_bytes(
        parsed
    ) == payload

    assert parsed[
        "schema_version"
    ] == PANEL_PROVENANCE_SCHEMA_VERSION

    assert parsed[
        "winning_selector"
    ] == "OPS"

    assert set(
        parsed[
            "baseline_bindings"
        ]
    ) == BASELINE_BINDING_KEYS


def test_preset_membership_manifest_row_order_is_exact() -> None:
    artifacts = synthetic_artifacts()

    rows = artifacts[
        MEMBERSHIP_MANIFEST_FILENAME
    ].decode(
        "utf-8"
    ).splitlines()[
        1:
    ]

    assert [
        int(
            row.split(
                "\t"
            )[
                0
            ]
        )
        for row in rows
    ] == list(
        PANEL_SIZES
    )


@pytest.mark.parametrize(
    (
        "rank",
        "expected",
    ),
    (
        (1, 10),
        (10, 10),
        (11, 20),
        (20, 20),
        (21, 50),
        (50, 50),
        (51, 100),
        (100, 100),
        (101, 200),
        (200, 200),
        (201, 500),
        (500, 500),
    ),
)
def test_first_public_panel_boundaries(
    rank: int,
    expected: int,
) -> None:
    assert first_public_panel_n(
        rank
    ) == expected


def test_exact_artifact_file_set() -> None:
    artifacts = synthetic_artifacts()

    assert set(
        artifacts
    ) == set(
        ALL_ARTIFACTS
    )

    assert len(
        artifacts
    ) == 11

    assert set(
        CONTENT_SOURCE_ARTIFACTS
    ) == (
        set(
            ALL_ARTIFACTS
        )
        - {
            CONTENT_MANIFEST_FILENAME
        }
    )


def test_complete_synthetic_artifact_audit_passes() -> None:
    artifacts = synthetic_artifacts()

    accessions = audit_reference_panel_artifacts(
        artifacts
    )

    assert accessions == synthetic_accessions()


def test_content_manifest_hash_mismatch_is_detected() -> None:
    artifacts = synthetic_artifacts()

    lines = artifacts[
        CONTENT_MANIFEST_FILENAME
    ].decode(
        "utf-8"
    ).splitlines()

    target = PANEL_FILENAMES[
        10
    ]

    replaced = []

    for line in lines:
        if line.startswith(
            target
            + "\t"
        ):
            fields = line.split(
                "\t"
            )

            fields[
                1
            ] = "0" * 64

            line = "\t".join(
                fields
            )

        replaced.append(
            line
        )

    artifacts[
        CONTENT_MANIFEST_FILENAME
    ] = (
        "\n".join(
            replaced
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        OfficialPanelError,
        match="content manifest artifact identity mismatch",
    ):
        audit_reference_panel_artifacts(
            artifacts
        )


def test_production_and_rebuild_byte_identity_passes() -> None:
    production = synthetic_artifacts()
    rebuild = synthetic_artifacts()

    require_artifact_sets_byte_identical(
        production,
        rebuild,
    )


def test_production_and_rebuild_byte_mismatch_is_detected() -> None:
    production = synthetic_artifacts()
    rebuild = synthetic_artifacts()

    rebuild[
        PANEL_FILENAMES[
            20
        ]
    ] = rebuild[
        PANEL_FILENAMES[
            20
        ]
    ].replace(
        b".1\n",
        b".2\n",
        1,
    )

    with pytest.raises(
        OfficialPanelError,
        match="production/rebuild byte mismatch",
    ):
        require_artifact_sets_byte_identical(
            production,
            rebuild,
        )


def test_reference_artifacts_do_not_assign_monthly_release() -> None:
    artifacts = synthetic_artifacts()

    month_pattern = re.compile(
        rb"\b20[0-9]{2}\.[0-9]{2}\b"
    )

    for payload in artifacts.values():
        assert month_pattern.search(
            payload
        ) is None

    summary = json.loads(
        artifacts[
            SUMMARY_FILENAME
        ].decode(
            "utf-8"
        )
    )

    assert summary[
        "monthly_release_assigned"
    ] is False


def test_membership_artifacts_exclude_forbidden_scientific_fields() -> None:
    artifacts = synthetic_artifacts()

    membership_artifacts = (
        WINNING_LADDER_FILENAME,
        MEMBERSHIP_MANIFEST_FILENAME,
        *(
            PANEL_FILENAMES[
                panel_size
            ]
            for panel_size in PANEL_SIZES
        ),
    )

    forbidden = (
        "species",
        "holdout",
        "feature",
        "coordinate",
        "distance",
        "product",
    )

    for artifact in membership_artifacts:
        text = artifacts[
            artifact
        ].decode(
            "utf-8"
        ).lower()

        for token in forbidden:
            assert token not in text


def test_content_manifest_rows_have_exact_data_row_counts() -> None:
    artifacts = synthetic_artifacts()

    rows = {
        fields[
            0
        ]:
            int(
                fields[
                    3
                ]
            )
        for fields in (
            line.split(
                "\t"
            )
            for line in artifacts[
                CONTENT_MANIFEST_FILENAME
            ].decode(
                "utf-8"
            ).splitlines()[
                1:
            ]
        )
    }

    assert rows[
        WINNING_LADDER_FILENAME
    ] == 500

    assert rows[
        MEMBERSHIP_MANIFEST_FILENAME
    ] == 6

    assert rows[
        SUMMARY_FILENAME
    ] == 1

    assert rows[
        PROVENANCE_FILENAME
    ] == 1

    for panel_size in PANEL_SIZES:
        assert rows[
            PANEL_FILENAMES[
                panel_size
            ]
        ] == panel_size


def test_membership_manifest_hashes_exact_panel_bytes() -> None:
    artifacts = synthetic_artifacts()

    for line in artifacts[
        MEMBERSHIP_MANIFEST_FILENAME
    ].decode(
        "utf-8"
    ).splitlines()[
        1:
    ]:
        panel_size_text, count_text, observed_sha = line.split(
            "\t"
        )

        panel_size = int(
            panel_size_text
        )

        assert count_text == panel_size_text

        assert observed_sha == sha256_bytes(
            artifacts[
                PANEL_FILENAMES[
                    panel_size
                ]
            ]
        )


def test_tests_are_synthetic_and_do_not_reference_production_inputs() -> None:
    source = Path(
        __file__
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "/"
        + "NGS"
        + "/",
        "stage7-selector-resolution-"
        + "production",
        "stage6-structural-feature-"
        + "execution",
        "GCA_"
        + "000016065"
        + ".1",
    )

    for token in forbidden:
        assert token not in source
