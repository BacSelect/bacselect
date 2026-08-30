#!/usr/bin/env python3
"""Frozen-input wrapper for BacSelect selector-v1 Stage 7 analysis.

This wrapper binds the production and independent-rebuild executions to the
already frozen Stage 6 holdout matrix, baseline foundation, final deterministic
OPS/SR ladder identities, Stage 7 implementations and software environment.

The wrapper itself does not calculate a selector decision.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType

import numpy as np

from bacselect.ops import ops_ladder
from bacselect.selector_resolution_execution import (
    Stage6MatrixExpectations,
    Stage7ExecutionError,
    Stage7FrozenBindings,
    execute_stage7_analysis,
)
from bacselect.sr import sr_ladder


LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

LOWER_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

EXPECTED_STAGE7_METHOD_SHA256 = (
    "6f0e540cdc9def82a164554619699481"
    "7d3d75aabf8ed38a40dc062c1366ff45"
)

EXPECTED_SELECTOR_RESOLUTION_DESIGN_SHA256 = (
    "2584fddf1f06562d48abd990372ec70e"
    "a1f48da0962b1f710afb1d93e2c3223a"
)

EXPECTED_STAGE6_COMPLETION_EVIDENCE_SHA256 = (
    "8c3c166f2861e09d74e1d2656d30f2a"
    "0739bb4d411c785fab9be6daff18cd299"
)

EXPECTED_STAGE6_MATRIX_ARTIFACT_SHA256 = (
    "8bb29e3b8cb98be1f21fe31fb5774b47"
    "a36835ebe75ef05fc59c7fe097b7eaf5"
)

EXPECTED_STAGE6_MATRIX_NUMERIC_ARRAY_SHA256 = (
    "d2a02dcd6b2ff81d99479ed57b35c1a"
    "04d39e4e2eafbf15d7efd798bc242675b"
)

EXPECTED_HOLDOUT_MEMBERSHIP_SHA256 = (
    "0998a65f617e6c1b951b52990c0e2cf8"
    "110b6327992110d862d9338f0fa06bbd"
)

EXPECTED_HOLDOUT_COUNT = 12952
EXPECTED_HOLDOUT_SPECIES_COUNT = 3542

EXPECTED_BASELINE_MANIFEST_SHA256 = (
    "512d466ff6b8af3e51eb91db715d5fc5"
    "c76995892a4c1b18489d922a0414f0f2"
)

EXPECTED_BASELINE_RAW_FILE_SHA256 = (
    "86c0c3d49317dfc3cc452114e3863666"
    "fe2112b6a3ae8dae2090b60a2a598948"
)

EXPECTED_BASELINE_RAW_ARRAY_SHA256 = (
    "2a0dbd5809fa4d5d77ab6e2d5255ddec"
    "9bb933a94be6c270260ec81758d8cbd6"
)

EXPECTED_BASELINE_PERCENTILE_FILE_SHA256 = (
    "f48e20b28ee89988e7abb42488a35c62"
    "fbfa4a538c15c8d2d70b6b5ba7ae83c1"
)

EXPECTED_BASELINE_PERCENTILE_ARRAY_SHA256 = (
    "9a4a120562ff1151fd8c83e831eb81362"
    "b2372844f7dd7407746554af49cda67"
)

EXPECTED_BASELINE_SPECIES_FILE_SHA256 = (
    "f0343238930e957f82bc28997a216ab3"
    "a8967d007b3d3471679e3f054c76af6c"
)

EXPECTED_FINAL_LADDER_MANIFEST_SHA256 = (
    "c0f17aaa2c92c27f0b4f3aebd9ffd1b"
    "e73cc403c80700b93a1b2d5786fb6b0da"
)

EXPECTED_OPS_FINAL_LADDER_SHA256 = (
    "c81d9fd30cda2d49f0f6c81d4bf99dac"
    "e9fff811c7612036d9265ef90707fa13"
)

EXPECTED_SR_FINAL_LADDER_SHA256 = (
    "3c703f5f898e0a13c6eb8568c0b83f5"
    "b0d19d4e374155d2d3a8a4e20378bd51f"
)

EXPECTED_ENVIRONMENT_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207eae"
    "f5c2435e1b6feeddc1e4654686bc2a8c"
)

EXPECTED_SCIENTIFIC_CORE_SHA256 = (
    "a972dd2d9e611a4c121c0cd6a9efebca"
    "9509adcf96ced3c0a02c570e4e570979"
)

EXPECTED_SCIENTIFIC_CORE_TEST_SHA256 = (
    "f2f9d52902c0a8e7819fe85ba9bbe208"
    "7f44e35c2d554727fadd10729635c90b"
)

EXPECTED_ARTIFACT_LAYER_SHA256 = (
    "6df58f9b4e49efa4b0b7f9139b9402a2"
    "af3d2b8b7a5f0095bc9291831bf2e00a"
)

EXPECTED_ARTIFACT_LAYER_TEST_SHA256 = (
    "74303f78169007b91b126a11c051777d"
    "d6f049d88c18e145548462849a691835"
)

EXPECTED_ANALYSIS_LAYER_SHA256 = (
    "b228cc234e871593c1ce33e99d8bf7aa"
    "36c98fae8f7429cdf98117ded1cd81e6"
)

EXPECTED_ANALYSIS_LAYER_TEST_SHA256 = (
    "8dc4c32ac3c087096f02a544a5d4921b"
    "2151c124709931b0a264251ba9223829"
)

EXPECTED_EXECUTION_ADAPTER_SHA256 = (
    "24cb559f906529d5f1599159f560463b"
    "5226629000079e9691cd5d430a5a5ddf"
)

EXPECTED_EXECUTION_ADAPTER_TEST_SHA256 = (
    "1bbeb9423080f95fe4fe47d2d9239035"
    "d6e034a44b1d37243ef6f01e3c5b3ea3"
)

EXPECTED_GEOMETRY_SHA256 = (
    "fbebf436d049be063817b717878330f38"
    "e09b3e7cb79f9dbc1b8f704af6a0d69"
)

EXPECTED_GEOMETRY_TEST_SHA256 = (
    "8c215ea881985a8d7fd83b59ee3a9ce4"
    "e1ebe5a0ffe64352d2077f098ecedec1"
)

EXPECTED_METRICS_SHA256 = (
    "c83219404c627c71c900aafbb165e0a8"
    "dead27f3f04f073dbb7ce86437bb3af2"
)

EXPECTED_METRICS_TEST_SHA256 = (
    "80b4a8f111af9c1ebd739fd99adfb9a6"
    "b656e014bf5239f767f73ae599b036ad"
)

EXPECTED_OPS_SHA256 = (
    "eb6c1b8edab3e694b0f3825bb5ab0eaf"
    "44fdd95fdbb6a6e3e41439c18c828c0f"
)

EXPECTED_SR_SHA256 = (
    "7d3faf8a89605599e2306eea8d2d56ad"
    "690c4a588897b7446983a60e0729693b"
)

EXPECTED_FINAL_GEOMETRY_COMMON_SHA256 = (
    "c2534c1a8522e29362109b82416364f40"
    "cb9a8a6c4f536758867916cbe81d9f1"
)

EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256 = (
    "83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92"
)

FEATURES = (
    "01_total_genome_length",
    "02_whole_genome_gc_fraction",
    "03_replicon_count",
    "04_non_chromosomal_replicon_count",
    "05_non_chromosomal_sequence_fraction",
    "06_non_unique_canonical_300mer_fraction",
    "07_non_unique_canonical_2400mer_fraction",
    "08_maximum_canonical_300mer_multiplicity",
    "09_maximum_canonical_2400mer_multiplicity",
    "10_longest_exact_repeat_length",
    "11_inter_replicon_shared_canonical_300mer_fraction",
    "12_inter_replicon_shared_canonical_2400mer_fraction",
)

STAGE6_EXECUTION_COMMIT = (
    "01c957b73b9802f284f6f61c28e6cd6e85bbf59a"
)

STAGE6_OUTPUT_ROOT = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/"
    "selector-v1/stage6-structural-feature-execution"
)

STAGE6_MATRIX_PATH = (
    STAGE6_OUTPUT_ROOT
    / STAGE6_EXECUTION_COMMIT
    / "structural-feature-matrix-300-2400.tsv"
)

PRODUCTION_OUTPUT_ROOT = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/"
    "selector-v1/stage7-selector-resolution-production"
)

REBUILD_OUTPUT_ROOT = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/"
    "selector-v1/stage7-selector-resolution-rebuild"
)


class Stage7WrapperError(RuntimeError):
    """Raised when frozen Stage 7 wrapper bindings fail."""


def repo_root() -> Path:
    return Path(
        __file__
    ).resolve().parents[2]


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        for chunk in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def validate_sha256(
    value: object,
    *,
    label: str,
) -> str:
    text = str(
        value
    ).strip()

    if LOWER_SHA256_RE.fullmatch(
        text
    ) is None:
        raise Stage7WrapperError(
            f"{label} is not a lowercase SHA256"
        )

    return text


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    expected = validate_sha256(
        expected,
        label=f"{label} expected SHA256",
    )

    current = Path(
        path
    )

    if (
        not current.is_file()
        or current.is_symlink()
    ):
        raise Stage7WrapperError(
            f"{label} is not a regular non-symlink file"
        )

    observed = sha256_file(
        current
    )

    if observed != expected:
        raise Stage7WrapperError(
            f"{label} SHA256 mismatch"
        )

    return observed


def run_git(
    repo: Path,
    *arguments: str,
) -> str:
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(
                    repo
                ),
                *arguments,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError:
        raise Stage7WrapperError(
            "Git repository verification failed"
        ) from None

    return completed.stdout.strip()


def sequence_sha256(
    namespace: str,
    values: list[str],
) -> str:
    """Established selector-v1 ordered-sequence fingerprint."""
    payload = (
        namespace
        + "\n"
        + "\n".join(
            values
        )
        + "\n"
    )

    return hashlib.sha256(
        payload.encode(
            "utf-8"
        )
    ).hexdigest()


def expected_repo_sha256() -> dict[str, str]:
    """Frozen code/test identities required by Stage 7."""
    return {
        "src/bacselect/selector_resolution.py":
            EXPECTED_SCIENTIFIC_CORE_SHA256,
        "tests/test_selector_resolution.py":
            EXPECTED_SCIENTIFIC_CORE_TEST_SHA256,
        "src/bacselect/selector_resolution_artifacts.py":
            EXPECTED_ARTIFACT_LAYER_SHA256,
        "tests/test_selector_resolution_artifacts.py":
            EXPECTED_ARTIFACT_LAYER_TEST_SHA256,
        "src/bacselect/selector_resolution_analysis.py":
            EXPECTED_ANALYSIS_LAYER_SHA256,
        "tests/test_selector_resolution_analysis.py":
            EXPECTED_ANALYSIS_LAYER_TEST_SHA256,
        "src/bacselect/selector_resolution_execution.py":
            EXPECTED_EXECUTION_ADAPTER_SHA256,
        "tests/test_selector_resolution_execution.py":
            EXPECTED_EXECUTION_ADAPTER_TEST_SHA256,
        "src/bacselect/geometry.py":
            EXPECTED_GEOMETRY_SHA256,
        "tests/test_geometry.py":
            EXPECTED_GEOMETRY_TEST_SHA256,
        "src/bacselect/metrics.py":
            EXPECTED_METRICS_SHA256,
        "tests/test_metrics.py":
            EXPECTED_METRICS_TEST_SHA256,
        "src/bacselect/ops.py":
            EXPECTED_OPS_SHA256,
        "src/bacselect/sr.py":
            EXPECTED_SR_SHA256,
        "src/bacselect/source_truth_execution.py":
            EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256,
        "validation/selector-v1/final_geometry_common.py":
            EXPECTED_FINAL_GEOMETRY_COMMON_SHA256,
    }


def repository_preflight(
    *,
    repo: Path,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> None:
    """Verify frozen repository and environment before Stage 7 dispatch."""
    if LOWER_COMMIT_RE.fullmatch(
        expected_commit
    ) is None:
        raise Stage7WrapperError(
            "expected Stage 7 execution commit malformed"
        )

    wrapper_sha = validate_sha256(
        expected_wrapper_sha256,
        label="Stage 7 wrapper SHA256",
    )

    wrapper_test_sha = validate_sha256(
        expected_wrapper_test_sha256,
        label="Stage 7 wrapper-test SHA256",
    )

    observed_head = run_git(
        repo,
        "rev-parse",
        "HEAD",
    )

    if observed_head != expected_commit:
        raise Stage7WrapperError(
            "Stage 7 repository HEAD does not match expected commit"
        )

    observed_origin = run_git(
        repo,
        "rev-parse",
        "origin/main",
    )

    if observed_origin != expected_commit:
        raise Stage7WrapperError(
            "Stage 7 origin/main does not match expected commit"
        )

    if run_git(
        repo,
        "status",
        "--porcelain",
    ):
        raise Stage7WrapperError(
            "Stage 7 repository working tree is not clean"
        )

    require_sha256(
        Path(
            __file__
        ),
        wrapper_sha,
        "Stage 7 production wrapper",
    )

    require_sha256(
        repo
        / "tests/test_run_selector_resolution_execution.py",
        wrapper_test_sha,
        "Stage 7 production wrapper test",
    )

    for relative, expected in sorted(
        expected_repo_sha256().items()
    ):
        require_sha256(
            repo
            / relative,
            expected,
            relative,
        )

    require_sha256(
        repo
        / (
            "validation/selector-v1/"
            "prospective-stage7-selector-resolution-execution.md"
        ),
        EXPECTED_STAGE7_METHOD_SHA256,
        "Stage 7 prospective execution method",
    )

    require_sha256(
        repo
        / (
            "validation/selector-v1/"
            "prospective-selector-resolution-design.md"
        ),
        EXPECTED_SELECTOR_RESOLUTION_DESIGN_SHA256,
        "selector-resolution prospective design",
    )

    require_sha256(
        repo
        / (
            "validation/selector-v1/"
            "stage6-structural-feature-completion-evidence.json"
        ),
        EXPECTED_STAGE6_COMPLETION_EVIDENCE_SHA256,
        "Stage 6 completion evidence",
    )

    require_sha256(
        repo
        / "validation/selector-v1/final-feature-space-inputs.tsv",
        EXPECTED_BASELINE_MANIFEST_SHA256,
        "final feature-space input manifest",
    )

    require_sha256(
        repo
        / (
            "validation/selector-v1/results/"
            "final300-2400-determinism-ladders.tsv"
        ),
        EXPECTED_FINAL_LADDER_MANIFEST_SHA256,
        "final deterministic ladder fingerprint manifest",
    )

    require_sha256(
        repo
        / "envs/bacselect-dev-linux-64.lock",
        EXPECTED_ENVIRONMENT_LOCK_SHA256,
        "bacselect-dev environment lock",
    )


def load_stage6_expectations(
    repo: Path,
) -> Stage6MatrixExpectations:
    """Load aggregate Stage 6 completion evidence without opening its matrix."""
    evidence_path = (
        repo
        / (
            "validation/selector-v1/"
            "stage6-structural-feature-completion-evidence.json"
        )
    )

    require_sha256(
        evidence_path,
        EXPECTED_STAGE6_COMPLETION_EVIDENCE_SHA256,
        "Stage 6 completion evidence",
    )

    try:
        payload = json.loads(
            evidence_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise Stage7WrapperError(
            "Stage 6 completion evidence cannot be parsed"
        ) from None

    required = {
        "status":
            "STAGE6_RAW_STRUCTURAL_FEATURES_COMPLETE",
        "external_holdout_count":
            EXPECTED_HOLDOUT_COUNT,
        "external_holdout_species_count":
            EXPECTED_HOLDOUT_SPECIES_COUNT,
        "external_holdout_membership_sha256":
            EXPECTED_HOLDOUT_MEMBERSHIP_SHA256,
        "raw_feature_matrix_artifact_sha256":
            EXPECTED_STAGE6_MATRIX_ARTIFACT_SHA256,
        "raw_feature_matrix_numeric_array_sha256":
            EXPECTED_STAGE6_MATRIX_NUMERIC_ARRAY_SHA256,
        "successful_feature_row_count":
            EXPECTED_HOLDOUT_COUNT,
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

    for key, expected in required.items():
        if payload.get(
            key
        ) != expected:
            raise Stage7WrapperError(
                "Stage 6 completion evidence field changed: "
                + key
            )

    return Stage6MatrixExpectations(
        artifact_sha256=(
            EXPECTED_STAGE6_MATRIX_ARTIFACT_SHA256
        ),
        numeric_array_sha256=(
            EXPECTED_STAGE6_MATRIX_NUMERIC_ARRAY_SHA256
        ),
        membership_sha256=(
            EXPECTED_HOLDOUT_MEMBERSHIP_SHA256
        ),
        row_count=EXPECTED_HOLDOUT_COUNT,
        species_count=EXPECTED_HOLDOUT_SPECIES_COUNT,
    )


def build_frozen_bindings(
    *,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> Stage7FrozenBindings:
    """Build exact Stage 7 provenance bindings."""
    wrapper_sha = validate_sha256(
        expected_wrapper_sha256,
        label="Stage 7 wrapper SHA256",
    )

    wrapper_test_sha = validate_sha256(
        expected_wrapper_test_sha256,
        label="Stage 7 wrapper-test SHA256",
    )

    baseline_bindings = {
        "manifest_sha256":
            EXPECTED_BASELINE_MANIFEST_SHA256,
        "raw_file_sha256":
            EXPECTED_BASELINE_RAW_FILE_SHA256,
        "raw_array_sha256":
            EXPECTED_BASELINE_RAW_ARRAY_SHA256,
        "percentile_file_sha256":
            EXPECTED_BASELINE_PERCENTILE_FILE_SHA256,
        "percentile_array_sha256":
            EXPECTED_BASELINE_PERCENTILE_ARRAY_SHA256,
        "species_file_sha256":
            EXPECTED_BASELINE_SPECIES_FILE_SHA256,
    }

    implementation_bindings = {
        "scientific_core_sha256":
            EXPECTED_SCIENTIFIC_CORE_SHA256,
        "scientific_core_test_sha256":
            EXPECTED_SCIENTIFIC_CORE_TEST_SHA256,
        "artifact_layer_sha256":
            EXPECTED_ARTIFACT_LAYER_SHA256,
        "artifact_layer_test_sha256":
            EXPECTED_ARTIFACT_LAYER_TEST_SHA256,
        "analysis_layer_sha256":
            EXPECTED_ANALYSIS_LAYER_SHA256,
        "analysis_layer_test_sha256":
            EXPECTED_ANALYSIS_LAYER_TEST_SHA256,
        "execution_adapter_sha256":
            EXPECTED_EXECUTION_ADAPTER_SHA256,
        "execution_adapter_test_sha256":
            EXPECTED_EXECUTION_ADAPTER_TEST_SHA256,
        "production_wrapper_sha256":
            wrapper_sha,
        "production_wrapper_test_sha256":
            wrapper_test_sha,
        "geometry_sha256":
            EXPECTED_GEOMETRY_SHA256,
        "geometry_test_sha256":
            EXPECTED_GEOMETRY_TEST_SHA256,
        "metrics_sha256":
            EXPECTED_METRICS_SHA256,
        "metrics_test_sha256":
            EXPECTED_METRICS_TEST_SHA256,
        "ops_sha256":
            EXPECTED_OPS_SHA256,
        "sr_sha256":
            EXPECTED_SR_SHA256,
        "source_truth_execution_sha256":
            EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256,
        "final_geometry_common_sha256":
            EXPECTED_FINAL_GEOMETRY_COMMON_SHA256,
        "final_ladder_manifest_sha256":
            EXPECTED_FINAL_LADDER_MANIFEST_SHA256,
    }

    return Stage7FrozenBindings(
        stage7_method_sha256=(
            EXPECTED_STAGE7_METHOD_SHA256
        ),
        selector_resolution_design_sha256=(
            EXPECTED_SELECTOR_RESOLUTION_DESIGN_SHA256
        ),
        stage6_completion_evidence_sha256=(
            EXPECTED_STAGE6_COMPLETION_EVIDENCE_SHA256
        ),
        environment_lock_sha256=(
            EXPECTED_ENVIRONMENT_LOCK_SHA256
        ),
        baseline_bindings=baseline_bindings,
        implementation_bindings=implementation_bindings,
        final_ladder_sha256={
            "OPS":
                EXPECTED_OPS_FINAL_LADDER_SHA256,
            "SR":
                EXPECTED_SR_FINAL_LADDER_SHA256,
        },
    )


def load_final_geometry_module(
    repo: Path,
) -> ModuleType:
    """Load only the frozen final geometry helper, never final_coverage_common."""
    path = (
        repo
        / "validation/selector-v1/final_geometry_common.py"
    )

    require_sha256(
        path,
        EXPECTED_FINAL_GEOMETRY_COMMON_SHA256,
        "final geometry helper",
    )

    spec = importlib.util.spec_from_file_location(
        "bacselect_stage7_final_geometry_common",
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise Stage7WrapperError(
            "cannot construct final geometry helper import"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        spec.name
    ] = module

    try:
        spec.loader.exec_module(
            module
        )
    except Exception:
        sys.modules.pop(
            spec.name,
            None,
        )

        raise Stage7WrapperError(
            "cannot load frozen final geometry helper"
        ) from None

    return module


def build_final_ladders(
    foundation,
) -> Mapping[
    str,
    np.ndarray,
]:
    """Reconstruct both candidate ladders from baseline geometry only."""
    ops = ops_ladder(
        foundation.coordinates,
        foundation.species_ids,
        foundation.accessions,
        max_n=500,
    )

    sr = sr_ladder(
        foundation.coordinates,
        foundation.species_ids,
        foundation.accessions,
        max_n=500,
    )

    return {
        "OPS":
            ops,
        "SR":
            sr,
    }


def output_root_for_mode(
    mode: str,
) -> Path:
    if mode == "production":
        return PRODUCTION_OUTPUT_ROOT

    if mode == "independent_rebuild":
        return REBUILD_OUTPUT_ROOT

    raise Stage7WrapperError(
        "invalid Stage 7 execution mode"
    )


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one frozen, identity-blinded "
            "BacSelect selector-v1 Stage 7 analysis."
        )
    )

    parser.add_argument(
        "--expected-commit",
        required=True,
        help=(
            "Exact pushed Git commit containing this "
            "frozen Stage 7 production wrapper."
        ),
    )

    parser.add_argument(
        "--expected-wrapper-sha256",
        required=True,
        help="Exact frozen SHA256 of this wrapper.",
    )

    parser.add_argument(
        "--expected-wrapper-test-sha256",
        required=True,
        help="Exact frozen SHA256 of the wrapper tests.",
    )

    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "production",
            "independent_rebuild",
        ),
    )

    return parser.parse_args(
        argv
    )


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(
        argv
    )

    repo = repo_root()

    repository_preflight(
        repo=repo,
        expected_commit=args.expected_commit,
        expected_wrapper_sha256=(
            args.expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            args.expected_wrapper_test_sha256
        ),
    )

    stage6_expectations = (
        load_stage6_expectations(
            repo
        )
    )

    frozen_bindings = (
        build_frozen_bindings(
            expected_wrapper_sha256=(
                args.expected_wrapper_sha256
            ),
            expected_wrapper_test_sha256=(
                args.expected_wrapper_test_sha256
            ),
        )
    )

    # Loading this Python helper imports code only. Baseline feature files are
    # not opened until the adapter has written its predecision checkpoint and
    # invokes baseline_loader().
    geometry_module = (
        load_final_geometry_module(
            repo
        )
    )

    def baseline_loader():
        return (
            geometry_module
            .load_final_foundation(
                recompute_coordinates=True,
            )
        )

    try:
        execute_stage7_analysis(
            repo=repo,
            expected_commit=args.expected_commit,
            execution_mode=args.mode,
            output_root=(
                output_root_for_mode(
                    args.mode
                )
            ),
            stage6_matrix_path=STAGE6_MATRIX_PATH,
            stage6_expectations=stage6_expectations,
            frozen_bindings=frozen_bindings,
            feature_names=FEATURES,
            baseline_loader=baseline_loader,
            ladder_builder=build_final_ladders,
            sequence_hasher=sequence_sha256,
        )
    except (
        Stage7ExecutionError,
        Stage7WrapperError,
    ) as exc:
        print(
            f"ERROR | {exc}",
            file=sys.stderr,
        )

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
