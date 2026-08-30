"""Synthetic/code-only tests for the Stage 7 production wrapper."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest


REPO = Path(
    __file__
).resolve().parents[1]

WRAPPER_PATH = (
    REPO
    / "validation/selector-v1/run_selector_resolution_execution.py"
)


def load_wrapper():
    spec = importlib.util.spec_from_file_location(
        "test_stage7_production_wrapper",
        WRAPPER_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        spec.name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


wrapper = load_wrapper()


def sha(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def test_real_stage7_frozen_constants_are_exact() -> None:
    assert wrapper.EXPECTED_STAGE7_METHOD_SHA256 == (
        "6f0e540cdc9def82a1645546196994817"
        "d3d75aabf8ed38a40dc062c1366ff45"
    )

    assert (
        wrapper.EXPECTED_SELECTOR_RESOLUTION_DESIGN_SHA256
        == (
            "2584fddf1f06562d48abd990372ec70e"
            "a1f48da0962b1f710afb1d93e2c3223a"
        )
    )

    assert (
        wrapper.EXPECTED_STAGE6_COMPLETION_EVIDENCE_SHA256
        == (
            "8c3c166f2861e09d74e1d2656d30f2a"
            "0739bb4d411c785fab9be6daff18cd299"
        )
    )

    assert wrapper.EXPECTED_HOLDOUT_COUNT == 12952
    assert wrapper.EXPECTED_HOLDOUT_SPECIES_COUNT == 3542

    assert wrapper.EXPECTED_OPS_FINAL_LADDER_SHA256 == (
        "c81d9fd30cda2d49f0f6c81d4bf99dac"
        "e9fff811c7612036d9265ef90707fa13"
    )

    assert wrapper.EXPECTED_SR_FINAL_LADDER_SHA256 == (
        "3c703f5f898e0a13c6eb8568c0b83f5b"
        "0d19d4e374155d2d3a8a4e20378bd51f"
    )


def test_obsolete_ladder_hashes_are_absent() -> None:
    text = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        "ab5d75b2d35b9577bcf84acceb8e10d8"
        not in text
    )

    assert (
        "080cbaf23d9259610d59fc1ef5a316432"
        not in text
    )

    assert "final_coverage_common" in text
    assert (
        "from final_coverage_common"
        not in text
    )
    assert (
        "import final_coverage_common"
        not in text
    )


def test_stage6_matrix_identity_is_bound_exactly() -> None:
    assert (
        wrapper.EXPECTED_STAGE6_MATRIX_ARTIFACT_SHA256
        == (
            "8bb29e3b8cb98be1f21fe31fb5774b47"
            "a36835ebe75ef05fc59c7fe097b7eaf5"
        )
    )

    assert (
        wrapper.EXPECTED_STAGE6_MATRIX_NUMERIC_ARRAY_SHA256
        == (
            "d2a02dcd6b2ff81d99479ed57b35c1a"
            "04d39e4e2eafbf15d7efd798bc242675b"
        )
    )

    assert (
        wrapper.EXPECTED_HOLDOUT_MEMBERSHIP_SHA256
        == (
            "0998a65f617e6c1b951b52990c0e2cf8"
            "110b6327992110d862d9338f0fa06bbd"
        )
    )


def test_stage6_matrix_path_is_frozen_but_not_opened_on_import() -> None:
    expected = Path(
        "/NGS/scratch/EXT/Rhys_wkdir/bacselect/"
        "selector-v1/stage6-structural-feature-execution/"
        "01c957b73b9802f284f6f61c28e6cd6e85bbf59a/"
        "structural-feature-matrix-300-2400.tsv"
    )

    assert wrapper.STAGE6_MATRIX_PATH == expected


def test_output_roots_are_separate() -> None:
    assert (
        wrapper.output_root_for_mode(
            "production"
        )
        != wrapper.output_root_for_mode(
            "independent_rebuild"
        )
    )


def test_invalid_output_mode_fails() -> None:
    with pytest.raises(
        wrapper.Stage7WrapperError,
        match="invalid Stage 7 execution mode",
    ):
        wrapper.output_root_for_mode(
            "other"
        )


def test_ordered_sequence_hash_matches_frozen_semantics() -> None:
    namespace = (
        "BacSelect-selector-v1|OPS|ladder|N=500"
    )

    values = [
        "A",
        "B",
        "C",
    ]

    expected_payload = (
        namespace
        + "\n"
        + "A\nB\nC\n"
    )

    assert wrapper.sequence_sha256(
        namespace,
        values,
    ) == hashlib.sha256(
        expected_payload.encode(
            "utf-8"
        )
    ).hexdigest()


def test_frozen_binding_builder_has_only_final_ladder_hashes() -> None:
    bindings = wrapper.build_frozen_bindings(
        expected_wrapper_sha256="1" * 64,
        expected_wrapper_test_sha256="2" * 64,
    )

    assert bindings.final_ladder_sha256 == {
        "OPS":
            wrapper.EXPECTED_OPS_FINAL_LADDER_SHA256,
        "SR":
            wrapper.EXPECTED_SR_FINAL_LADDER_SHA256,
    }

    assert bindings.implementation_bindings[
        "production_wrapper_sha256"
    ] == "1" * 64

    assert bindings.implementation_bindings[
        "production_wrapper_test_sha256"
    ] == "2" * 64


def test_baseline_bindings_are_exact() -> None:
    bindings = wrapper.build_frozen_bindings(
        expected_wrapper_sha256="1" * 64,
        expected_wrapper_test_sha256="2" * 64,
    )

    assert bindings.baseline_bindings == {
        "manifest_sha256":
            wrapper.EXPECTED_BASELINE_MANIFEST_SHA256,
        "raw_file_sha256":
            wrapper.EXPECTED_BASELINE_RAW_FILE_SHA256,
        "raw_array_sha256":
            wrapper.EXPECTED_BASELINE_RAW_ARRAY_SHA256,
        "percentile_file_sha256":
            wrapper.EXPECTED_BASELINE_PERCENTILE_FILE_SHA256,
        "percentile_array_sha256":
            wrapper.EXPECTED_BASELINE_PERCENTILE_ARRAY_SHA256,
        "species_file_sha256":
            wrapper.EXPECTED_BASELINE_SPECIES_FILE_SHA256,
    }


def test_stage6_completion_schema_parser_with_synthetic_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    evidence = {
        "status":
            "STAGE6_RAW_STRUCTURAL_FEATURES_COMPLETE",
        "external_holdout_count":
            wrapper.EXPECTED_HOLDOUT_COUNT,
        "external_holdout_species_count":
            wrapper.EXPECTED_HOLDOUT_SPECIES_COUNT,
        "external_holdout_membership_sha256":
            wrapper.EXPECTED_HOLDOUT_MEMBERSHIP_SHA256,
        "raw_feature_matrix_artifact_sha256":
            wrapper.EXPECTED_STAGE6_MATRIX_ARTIFACT_SHA256,
        "raw_feature_matrix_numeric_array_sha256":
            wrapper.EXPECTED_STAGE6_MATRIX_NUMERIC_ARRAY_SHA256,
        "successful_feature_row_count":
            wrapper.EXPECTED_HOLDOUT_COUNT,
        "structural_features_calculated":
            True,
        "percentile_coordinates_calculated":
            False,
        "ops_sr_distances_calculated":
            False,
        "panel_identities_generated":
            False,
        "selector_outcomes_calculated":
            False,
        "identity_bearing_outputs_committed_to_git":
            False,
    }

    path = (
        tmp_path
        / "validation/selector-v1/"
        "stage6-structural-feature-completion-evidence.json"
    )

    path.parent.mkdir(
        parents=True
    )

    path.write_text(
        json.dumps(
            evidence,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        wrapper,
        "require_sha256",
        lambda *args, **kwargs:
            "synthetic",
    )

    observed = (
        wrapper.load_stage6_expectations(
            tmp_path
        )
    )

    assert observed.row_count == (
        wrapper.EXPECTED_HOLDOUT_COUNT
    )

    assert observed.species_count == (
        wrapper.EXPECTED_HOLDOUT_SPECIES_COUNT
    )


@pytest.mark.parametrize(
    "field,bad_value",
    (
        (
            "percentile_coordinates_calculated",
            True,
        ),
        (
            "ops_sr_distances_calculated",
            True,
        ),
        (
            "panel_identities_generated",
            True,
        ),
        (
            "selector_outcomes_calculated",
            True,
        ),
        (
            "identity_bearing_outputs_committed_to_git",
            True,
        ),
    ),
)
def test_stage6_completion_invalid_scientific_state_rejected(
    tmp_path: Path,
    monkeypatch,
    field: str,
    bad_value,
) -> None:
    evidence = {
        "status":
            "STAGE6_RAW_STRUCTURAL_FEATURES_COMPLETE",
        "external_holdout_count":
            wrapper.EXPECTED_HOLDOUT_COUNT,
        "external_holdout_species_count":
            wrapper.EXPECTED_HOLDOUT_SPECIES_COUNT,
        "external_holdout_membership_sha256":
            wrapper.EXPECTED_HOLDOUT_MEMBERSHIP_SHA256,
        "raw_feature_matrix_artifact_sha256":
            wrapper.EXPECTED_STAGE6_MATRIX_ARTIFACT_SHA256,
        "raw_feature_matrix_numeric_array_sha256":
            wrapper.EXPECTED_STAGE6_MATRIX_NUMERIC_ARRAY_SHA256,
        "successful_feature_row_count":
            wrapper.EXPECTED_HOLDOUT_COUNT,
        "structural_features_calculated":
            True,
        "percentile_coordinates_calculated":
            False,
        "ops_sr_distances_calculated":
            False,
        "panel_identities_generated":
            False,
        "selector_outcomes_calculated":
            False,
        "identity_bearing_outputs_committed_to_git":
            False,
    }

    evidence[
        field
    ] = bad_value

    path = (
        tmp_path
        / "validation/selector-v1/"
        "stage6-structural-feature-completion-evidence.json"
    )

    path.parent.mkdir(
        parents=True
    )

    path.write_text(
        json.dumps(
            evidence
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        wrapper,
        "require_sha256",
        lambda *args, **kwargs:
            "synthetic",
    )

    with pytest.raises(
        wrapper.Stage7WrapperError,
        match="Stage 6 completion evidence field changed",
    ):
        wrapper.load_stage6_expectations(
            tmp_path
        )


def test_final_ladder_builder_uses_exactly_500_baseline_rows(
    monkeypatch,
) -> None:
    observed = []

    def fake_ops(
        coordinates,
        species_ids,
        accessions,
        max_n,
    ):
        observed.append(
            (
                "OPS",
                max_n,
            )
        )

        return np.arange(
            500,
            dtype=np.int64,
        )

    def fake_sr(
        coordinates,
        species_ids,
        accessions,
        max_n,
    ):
        observed.append(
            (
                "SR",
                max_n,
            )
        )

        return np.arange(
            500,
            dtype=np.int64,
        )

    monkeypatch.setattr(
        wrapper,
        "ops_ladder",
        fake_ops,
    )

    monkeypatch.setattr(
        wrapper,
        "sr_ladder",
        fake_sr,
    )

    foundation = SimpleNamespace(
        coordinates=np.zeros(
            (
                520,
                12,
            ),
            dtype=np.float64,
        ),
        species_ids=[
            str(
                index
            )
            for index in range(
                520
            )
        ],
        accessions=[
            f"A{index}"
            for index in range(
                520
            )
        ],
    )

    result = wrapper.build_final_ladders(
        foundation
    )

    assert set(
        result
    ) == {
        "OPS",
        "SR",
    }

    assert observed == [
        (
            "OPS",
            500,
        ),
        (
            "SR",
            500,
        ),
    ]


def test_main_dispatches_without_opening_real_scientific_inputs(
    monkeypatch,
) -> None:
    expected_commit = "a" * 40
    wrapper_sha = "1" * 64
    wrapper_test_sha = "2" * 64

    observed = {}

    monkeypatch.setattr(
        wrapper,
        "repository_preflight",
        lambda **kwargs:
            observed.setdefault(
                "preflight",
                kwargs,
            ),
    )

    synthetic_expectations = (
        wrapper.Stage6MatrixExpectations(
            artifact_sha256="3" * 64,
            numeric_array_sha256="4" * 64,
            membership_sha256="5" * 64,
            row_count=6,
            species_count=4,
        )
    )

    monkeypatch.setattr(
        wrapper,
        "load_stage6_expectations",
        lambda repo:
            synthetic_expectations,
    )

    synthetic_geometry = SimpleNamespace(
        load_final_foundation=lambda **kwargs:
            (_ for _ in ()).throw(
                AssertionError(
                    "baseline must not be opened by mocked dispatch"
                )
            )
    )

    monkeypatch.setattr(
        wrapper,
        "load_final_geometry_module",
        lambda repo:
            synthetic_geometry,
    )

    def fake_execute(**kwargs):
        observed[
            "execute"
        ] = kwargs

        # Deliberately do not invoke baseline_loader,
        # ladder_builder or matrix access.
        return Path(
            "/synthetic/final"
        )

    monkeypatch.setattr(
        wrapper,
        "execute_stage7_analysis",
        fake_execute,
    )

    result = wrapper.main(
        [
            "--expected-commit",
            expected_commit,
            "--expected-wrapper-sha256",
            wrapper_sha,
            "--expected-wrapper-test-sha256",
            wrapper_test_sha,
            "--mode",
            "production",
        ]
    )

    assert result == 0

    assert observed[
        "execute"
    ][
        "stage6_matrix_path"
    ] == wrapper.STAGE6_MATRIX_PATH

    assert observed[
        "execute"
    ][
        "stage6_expectations"
    ] is synthetic_expectations

    assert observed[
        "execute"
    ][
        "execution_mode"
    ] == "production"

    assert observed[
        "execute"
    ][
        "output_root"
    ] == wrapper.PRODUCTION_OUTPUT_ROOT

    assert callable(
        observed[
            "execute"
        ][
            "baseline_loader"
        ]
    )

    assert observed[
        "execute"
    ][
        "ladder_builder"
    ] is wrapper.build_final_ladders

    assert observed[
        "execute"
    ][
        "sequence_hasher"
    ] is wrapper.sequence_sha256


def test_main_rebuild_dispatch_uses_distinct_root(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        wrapper,
        "repository_preflight",
        lambda **kwargs:
            None,
    )

    monkeypatch.setattr(
        wrapper,
        "load_stage6_expectations",
        lambda repo:
            wrapper.Stage6MatrixExpectations(
                artifact_sha256="3" * 64,
                numeric_array_sha256="4" * 64,
                membership_sha256="5" * 64,
                row_count=6,
                species_count=4,
            ),
    )

    monkeypatch.setattr(
        wrapper,
        "load_final_geometry_module",
        lambda repo:
            SimpleNamespace(
                load_final_foundation=lambda **kwargs:
                    None
            ),
    )

    observed = {}

    monkeypatch.setattr(
        wrapper,
        "execute_stage7_analysis",
        lambda **kwargs:
            observed.update(
                kwargs
            ),
    )

    result = wrapper.main(
        [
            "--expected-commit",
            "a" * 40,
            "--expected-wrapper-sha256",
            "1" * 64,
            "--expected-wrapper-test-sha256",
            "2" * 64,
            "--mode",
            "independent_rebuild",
        ]
    )

    assert result == 0
    assert observed[
        "execution_mode"
    ] == "independent_rebuild"
    assert observed[
        "output_root"
    ] == wrapper.REBUILD_OUTPUT_ROOT


def test_repository_preflight_verifies_no_remote_network(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = []

    monkeypatch.setattr(
        wrapper,
        "run_git",
        lambda repo, *arguments:
            calls.append(
                arguments
            )
            or (
                "a" * 40
                if arguments != (
                    "status",
                    "--porcelain",
                )
                else ""
            ),
    )

    monkeypatch.setattr(
        wrapper,
        "require_sha256",
        lambda *args, **kwargs:
            "synthetic",
    )

    monkeypatch.setattr(
        wrapper,
        "__file__",
        str(
            tmp_path
            / "validation/selector-v1/"
            "run_selector_resolution_execution.py"
        ),
    )

    wrapper.repository_preflight(
        repo=tmp_path,
        expected_commit="a" * 40,
        expected_wrapper_sha256="1" * 64,
        expected_wrapper_test_sha256="2" * 64,
    )

    assert (
        "ls-remote",
    ) not in calls

    assert calls == [
        (
            "rev-parse",
            "HEAD",
        ),
        (
            "rev-parse",
            "origin/main",
        ),
        (
            "status",
            "--porcelain",
        ),
    ]


def test_feature_contract_is_exact_12() -> None:
    assert len(
        wrapper.FEATURES
    ) == 12

    assert wrapper.FEATURES[
        0
    ] == "01_total_genome_length"

    assert wrapper.FEATURES[
        -1
    ] == (
        "12_inter_replicon_shared_canonical_2400mer_fraction"
    )


def test_no_decision_finalizer_imported() -> None:
    text = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "resolve_exact_products(",
        "selector_decision",
        "decision_finalizer",
    )

    for value in forbidden:
        assert value not in text
