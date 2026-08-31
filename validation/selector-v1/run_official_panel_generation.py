#!/usr/bin/env python3
"""Execute frozen BacSelect selector-v1 reference-panel generation."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import ModuleType

from bacselect.official_panels import (
    ALL_ARTIFACTS,
    CONTENT_MANIFEST_FILENAME,
    PANEL_SIZES,
    SELECTOR,
    WINNING_LADDER_N,
    WINNING_LADDER_SHA256,
    SELECTOR_DECISION_RECORD_SHA256,
    OfficialPanelError,
    audit_reference_panel_artifacts,
    build_reference_panel_artifacts,
    require_artifact_sets_byte_identical,
    resolve_verified_ops_accessions,
    sha256_bytes,
    validate_git_commit,
    validate_sha256,
    verify_selector_decision_bytes,
)


METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-official-selector-v1-panel-generation.md"
)

CORE_RELATIVE = Path(
    "src/bacselect/official_panels.py"
)

CORE_TEST_RELATIVE = Path(
    "tests/test_official_panels.py"
)

WRAPPER_RELATIVE = Path(
    "validation/selector-v1/run_official_panel_generation.py"
)

WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_official_panel_generation.py"
)

DECISION_RELATIVE = Path(
    "validation/selector-v1/stage7-selector-decision-record.json"
)

STAGE7_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/run_selector_resolution_execution.py"
)

STAGE7_WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_selector_resolution_execution.py"
)

STAGE7_ADAPTER_RELATIVE = Path(
    "src/bacselect/selector_resolution_execution.py"
)

EXPECTED_METHOD_SHA256 = (
    "a55daffbaac0ea10f92195f96959fa3ab4da3aef023727ce388e74b2a86dab3c"
)

EXPECTED_CORE_SHA256 = (
    "01859f21d7d8653e8ff671f1c5d74a9469a251470258d742edc9b09c14448356"
)

EXPECTED_CORE_TEST_SHA256 = (
    "491f0f0ee237583c04ef3357ad7b9118ae1cc028fde8f2ce49748224dfcbbecc"
)

EXPECTED_DECISION_SHA256 = (
    "d0cf63ad4d933194e3e782912a2a2a3c617353758d2c87c1b1198681a75869e2"
)

EXPECTED_STAGE7_WRAPPER_SHA256 = (
    "ca1e1a0e58e3d9878bbb48cfbaac40126907d3220c8060624ec991ab7681396c"
)

EXPECTED_STAGE7_WRAPPER_TEST_SHA256 = (
    "fd69bfe12810638a2f433fc456b8e5cdf8b70c43b8ba6580c38c89bff191e0bb"
)

EXPECTED_STAGE7_ADAPTER_SHA256 = (
    "24cb559f906529d5f1599159f560463b5226629000079e9691cd5d430a5a5ddf"
)

EXPECTED_FINAL_LADDER_SHA256 = {
    "OPS":
        "c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13",
    "SR":
        "3c703f5f898e0a13c6eb8568c0b83f5b0d19d4e374155d2d3a8a4e20378bd51f",
}

PRODUCTION_BASE = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/"
    "selector-v1/official-panel-generation"
)

REBUILD_BASE = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/"
    "selector-v1/official-panel-generation-rebuild"
)


class OfficialPanelExecutionError(RuntimeError):
    """Raised when real panel generation fails closed."""


@dataclass(frozen=True)
class ScientificInputs:
    """Verified scientific inputs needed by the deterministic serializer."""

    accessions: tuple[str, ...]
    final_geometry_helper_sha256: str
    baseline_bindings: Mapping[str, str]
    environment_lock_sha256: str


@dataclass(frozen=True)
class GenerationResult:
    """Aggregate result of one production or rebuild execution."""

    output_root: Path
    artifact_sha256: Mapping[str, str]
    content_manifest_sha256: str


def repo_root() -> Path:
    return Path(
        __file__
    ).resolve().parents[2]


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
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


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> None:
    validate_sha256(
        expected,
        label=(
            label
            + " SHA256"
        ),
    )

    if not path.is_file():
        raise OfficialPanelExecutionError(
            f"missing {label}: {path}"
        )

    observed = sha256_file(
        path
    )

    if observed != expected:
        raise OfficialPanelExecutionError(
            f"{label} SHA256 mismatch"
        )


def _git_output(
    repo: Path,
    *arguments: str,
) -> str:
    try:
        completed = subprocess.run(
            (
                "git",
                *arguments,
            ),
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (
        OSError,
        subprocess.CalledProcessError,
    ):
        raise OfficialPanelExecutionError(
            "Git repository preflight failed"
        ) from None

    return completed.stdout.strip()


def repository_preflight(
    *,
    repo: Path,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> None:
    """Require exact pushed implementation and a clean repository."""
    commit = validate_git_commit(
        expected_commit,
        label="execution commit",
    )

    wrapper_sha = validate_sha256(
        expected_wrapper_sha256,
        label="panel execution wrapper SHA256",
    )

    wrapper_test_sha = validate_sha256(
        expected_wrapper_test_sha256,
        label="panel execution wrapper-test SHA256",
    )

    if _git_output(
        repo,
        "rev-parse",
        "HEAD",
    ) != commit:
        raise OfficialPanelExecutionError(
            "HEAD does not equal expected execution commit"
        )

    if _git_output(
        repo,
        "rev-parse",
        "origin/main",
    ) != commit:
        raise OfficialPanelExecutionError(
            "local origin/main does not equal expected execution commit"
        )

    if _git_output(
        repo,
        "status",
        "--porcelain",
    ):
        raise OfficialPanelExecutionError(
            "repository working tree is not clean"
        )

    frozen = (
        (
            METHOD_RELATIVE,
            EXPECTED_METHOD_SHA256,
            "prospective panel-generation method",
        ),
        (
            CORE_RELATIVE,
            EXPECTED_CORE_SHA256,
            "official-panel generator core",
        ),
        (
            CORE_TEST_RELATIVE,
            EXPECTED_CORE_TEST_SHA256,
            "official-panel generator-core test",
        ),
        (
            DECISION_RELATIVE,
            EXPECTED_DECISION_SHA256,
            "selector decision record",
        ),
        (
            STAGE7_WRAPPER_RELATIVE,
            EXPECTED_STAGE7_WRAPPER_SHA256,
            "Stage 7 execution wrapper",
        ),
        (
            STAGE7_WRAPPER_TEST_RELATIVE,
            EXPECTED_STAGE7_WRAPPER_TEST_SHA256,
            "Stage 7 execution wrapper test",
        ),
        (
            STAGE7_ADAPTER_RELATIVE,
            EXPECTED_STAGE7_ADAPTER_SHA256,
            "Stage 7 execution adapter",
        ),
        (
            WRAPPER_RELATIVE,
            wrapper_sha,
            "official-panel execution wrapper",
        ),
        (
            WRAPPER_TEST_RELATIVE,
            wrapper_test_sha,
            "official-panel execution wrapper test",
        ),
    )

    for relative, expected, label in frozen:
        require_sha256(
            repo
            / relative,
            expected,
            label,
        )


def output_root_for_mode(
    mode: str,
    expected_commit: str,
) -> Path:
    """Return the frozen scratch destination for one execution mode."""
    commit = validate_git_commit(
        expected_commit,
        label="execution commit",
    )

    if mode == "production":
        return (
            PRODUCTION_BASE
            / commit
        )

    if mode == "rebuild":
        return (
            REBUILD_BASE
            / commit
        )

    raise OfficialPanelExecutionError(
        "execution mode must be production or rebuild"
    )


def output_preflight(
    output_root: Path,
) -> None:
    """Require a fresh target beneath an already-existing parent."""
    if output_root.exists():
        raise OfficialPanelExecutionError(
            "output root already exists"
        )

    if not output_root.parent.is_dir():
        raise OfficialPanelExecutionError(
            "output root parent does not exist"
        )


def _load_module(
    path: Path,
    module_name: str,
) -> ModuleType:
    """Load one already-hash-verified Python module from an exact path."""
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise OfficialPanelExecutionError(
            f"cannot construct module import: {path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        module_name
    ] = module

    try:
        spec.loader.exec_module(
            module
        )
    except Exception:
        sys.modules.pop(
            module_name,
            None,
        )

        raise OfficialPanelExecutionError(
            f"cannot load frozen module: {path}"
        ) from None

    return module


def load_stage7_wrapper(
    repo: Path,
) -> ModuleType:
    """Load the exact frozen Stage 7 execution wrapper."""
    path = (
        repo
        / STAGE7_WRAPPER_RELATIVE
    )

    require_sha256(
        path,
        EXPECTED_STAGE7_WRAPPER_SHA256,
        "Stage 7 execution wrapper",
    )

    return _load_module(
        path,
        "bacselect_official_panels_stage7_wrapper",
    )


def load_stage7_adapter(
    repo: Path,
) -> ModuleType:
    """Load the exact frozen Stage 7 execution adapter."""
    path = (
        repo
        / STAGE7_ADAPTER_RELATIVE
    )

    require_sha256(
        path,
        EXPECTED_STAGE7_ADAPTER_SHA256,
        "Stage 7 execution adapter",
    )

    return _load_module(
        path,
        "bacselect_official_panels_stage7_adapter",
    )


def reconstruct_verified_accessions(
    repo: Path,
) -> ScientificInputs:
    """Reconstruct and verify the winning OPS ladder before serialization."""
    decision_path = (
        repo
        / DECISION_RELATIVE
    )

    require_sha256(
        decision_path,
        EXPECTED_DECISION_SHA256,
        "selector decision record",
    )

    decision_bytes = decision_path.read_bytes()

    verify_selector_decision_bytes(
        decision_bytes,
        expected_sha256=(
            EXPECTED_DECISION_SHA256
        ),
        expected_final_ladder_sha256=(
            EXPECTED_FINAL_LADDER_SHA256
        ),
    )

    stage7 = load_stage7_wrapper(
        repo
    )

    try:
        frozen_bindings = (
            stage7
            .build_frozen_bindings(
                expected_wrapper_sha256=(
                    EXPECTED_STAGE7_WRAPPER_SHA256
                ),
                expected_wrapper_test_sha256=(
                    EXPECTED_STAGE7_WRAPPER_TEST_SHA256
                ),
            )
        )
    except Exception:
        raise OfficialPanelExecutionError(
            "cannot recover frozen Stage 7 bindings"
        ) from None

    if dict(
        frozen_bindings.final_ladder_sha256
    ) != EXPECTED_FINAL_LADDER_SHA256:
        raise OfficialPanelExecutionError(
            "frozen Stage 7 final-ladder bindings changed"
        )

    try:
        geometry = (
            stage7
            .load_final_geometry_module(
                repo
            )
        )

        foundation = (
            geometry
            .load_final_foundation(
                recompute_coordinates=True,
            )
        )
    except Exception:
        raise OfficialPanelExecutionError(
            "frozen final baseline reconstruction failed"
        ) from None

    row_count = len(
        foundation.accessions
    )

    if not (
        len(
            foundation.raw
        )
        == len(
            foundation.coordinates
        )
        == len(
            foundation.species_ids
        )
        == row_count
    ):
        raise OfficialPanelExecutionError(
            "frozen baseline foundation row alignment changed"
        )

    try:
        candidate_ladders = (
            stage7
            .build_final_ladders(
                foundation
            )
        )
    except Exception:
        raise OfficialPanelExecutionError(
            "frozen final ladder reconstruction failed"
        ) from None

    adapter = load_stage7_adapter(
        repo
    )

    verify_ladders = getattr(
        adapter,
        "_verify_ladders",
        None,
    )

    if not callable(
        verify_ladders
    ):
        raise OfficialPanelExecutionError(
            "frozen Stage 7 ladder verifier unavailable"
        )

    try:
        verified_ladders = verify_ladders(
            foundation=foundation,
            ladders=candidate_ladders,
            expected_hashes=(
                EXPECTED_FINAL_LADDER_SHA256
            ),
            sequence_hasher=(
                stage7.sequence_sha256
            ),
        )
    except Exception:
        raise OfficialPanelExecutionError(
            "frozen Stage 7 ladder verification failed"
        ) from None

    if set(
        verified_ladders
    ) != {
        "OPS",
        "SR",
    }:
        raise OfficialPanelExecutionError(
            "verified Stage 7 selector set changed"
        )

    try:
        accessions = resolve_verified_ops_accessions(
            verified_ladders[
                "OPS"
            ],
            foundation.accessions,
        )
    except (
        TypeError,
        OfficialPanelError,
    ):
        raise OfficialPanelExecutionError(
            "verified OPS accession resolution failed"
        ) from None

    if len(
        accessions
    ) != WINNING_LADDER_N:
        raise OfficialPanelExecutionError(
            "verified OPS accession count changed"
        )

    final_geometry_sha = getattr(
        stage7,
        "EXPECTED_FINAL_GEOMETRY_COMMON_SHA256",
        None,
    )

    if not isinstance(
        final_geometry_sha,
        str,
    ):
        raise OfficialPanelExecutionError(
            "frozen final-geometry identity unavailable"
        )

    validate_sha256(
        final_geometry_sha,
        label="final geometry helper SHA256",
    )

    environment_lock_sha = getattr(
        frozen_bindings,
        "environment_lock_sha256",
        None,
    )

    if not isinstance(
        environment_lock_sha,
        str,
    ):
        raise OfficialPanelExecutionError(
            "frozen environment-lock identity unavailable"
        )

    validate_sha256(
        environment_lock_sha,
        label="environment lock SHA256",
    )

    baseline_bindings = dict(
        frozen_bindings.baseline_bindings
    )

    return ScientificInputs(
        accessions=accessions,
        final_geometry_helper_sha256=(
            final_geometry_sha
        ),
        baseline_bindings=baseline_bindings,
        environment_lock_sha256=(
            environment_lock_sha
        ),
    )


def _safe_artifact_path(
    output_root: Path,
    artifact: str,
) -> Path:
    """Resolve one frozen artifact filename beneath the output root."""
    if (
        not artifact
        or Path(
            artifact
        ).name != artifact
        or "/" in artifact
        or "\\" in artifact
    ):
        raise OfficialPanelExecutionError(
            "invalid official-panel artifact filename"
        )

    return (
        output_root
        / artifact
    )


def write_artifacts_exclusive(
    output_root: Path,
    artifacts: Mapping[str, bytes],
) -> None:
    """Write all eleven files exclusively into one fresh output directory."""
    if set(
        artifacts
    ) != set(
        ALL_ARTIFACTS
    ):
        raise OfficialPanelExecutionError(
            "official-panel artifact set changed before write"
        )

    output_preflight(
        output_root
    )

    try:
        os.mkdir(
            output_root,
            0o755,
        )
        os.chmod(
            output_root,
            0o755,
        )
    except OSError:
        raise OfficialPanelExecutionError(
            "cannot create fresh output root"
        ) from None

    for artifact in sorted(
        ALL_ARTIFACTS
    ):
        payload = artifacts[
            artifact
        ]

        if not isinstance(
            payload,
            bytes,
        ):
            raise OfficialPanelExecutionError(
                "official-panel artifact payload is not bytes"
            )

        path = _safe_artifact_path(
            output_root,
            artifact,
        )

        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
        )

        try:
            descriptor = os.open(
                path,
                flags,
                0o644,
            )
        except OSError:
            raise OfficialPanelExecutionError(
                f"cannot exclusively create artifact: {artifact}"
            ) from None

        try:
            os.fchmod(
                descriptor,
                0o644,
            )

            with os.fdopen(
                descriptor,
                "wb",
                closefd=True,
            ) as handle:
                descriptor = -1

                handle.write(
                    payload
                )

                handle.flush()

                os.fsync(
                    handle.fileno()
                )
        except OSError:
            raise OfficialPanelExecutionError(
                f"cannot write artifact: {artifact}"
            ) from None
        finally:
            if descriptor >= 0:
                os.close(
                    descriptor
                )

    try:
        directory_descriptor = os.open(
            output_root,
            os.O_RDONLY,
        )

        try:
            os.fsync(
                directory_descriptor
            )
        finally:
            os.close(
                directory_descriptor
            )
    except OSError:
        raise OfficialPanelExecutionError(
            "cannot fsync official-panel output directory"
        ) from None


def read_back_and_audit(
    output_root: Path,
    expected_artifacts: Mapping[str, bytes],
) -> Mapping[str, bytes]:
    """Require exact bytes, file modes and scientific artifact audit."""
    if set(
        expected_artifacts
    ) != set(
        ALL_ARTIFACTS
    ):
        raise OfficialPanelExecutionError(
            "expected official-panel artifact set changed"
        )

    observed: dict[str, bytes] = {}

    for artifact in ALL_ARTIFACTS:
        path = _safe_artifact_path(
            output_root,
            artifact,
        )

        if not path.is_file():
            raise OfficialPanelExecutionError(
                f"written artifact missing: {artifact}"
            )

        mode = stat.S_IMODE(
            path.stat().st_mode
        )

        if mode != 0o644:
            raise OfficialPanelExecutionError(
                f"written artifact mode changed: {artifact}"
            )

        payload = path.read_bytes()

        if payload != expected_artifacts[
            artifact
        ]:
            raise OfficialPanelExecutionError(
                f"written artifact bytes changed: {artifact}"
            )

        observed[
            artifact
        ] = payload

    try:
        audit_reference_panel_artifacts(
            observed
        )
    except OfficialPanelError:
        raise OfficialPanelExecutionError(
            "written official-panel artifact audit failed"
        ) from None

    return observed


def execute_panel_generation(
    *,
    repo: Path,
    expected_commit: str,
    mode: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    scientific_builder: Callable[
        [
            Path,
        ],
        ScientificInputs,
    ] = reconstruct_verified_accessions,
    output_root_override: Path | None = None,
) -> GenerationResult:
    """Run one production/rebuild generation after exact preflight."""
    repository_preflight(
        repo=repo,
        expected_commit=expected_commit,
        expected_wrapper_sha256=(
            expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            expected_wrapper_test_sha256
        ),
    )

    if output_root_override is None:
        output_root = output_root_for_mode(
            mode,
            expected_commit,
        )
    else:
        output_root = output_root_override

    output_preflight(
        output_root
    )

    scientific = scientific_builder(
        repo
    )

    if not isinstance(
        scientific,
        ScientificInputs,
    ):
        raise OfficialPanelExecutionError(
            "scientific builder returned unexpected result"
        )

    try:
        artifacts = dict(
            build_reference_panel_artifacts(
                scientific.accessions,
                execution_commit=expected_commit,
                implementation_sha256=(
                    EXPECTED_CORE_SHA256
                ),
                implementation_test_sha256=(
                    EXPECTED_CORE_TEST_SHA256
                ),
                stage7_wrapper_sha256=(
                    EXPECTED_STAGE7_WRAPPER_SHA256
                ),
                stage7_execution_adapter_sha256=(
                    EXPECTED_STAGE7_ADAPTER_SHA256
                ),
                final_geometry_helper_sha256=(
                    scientific
                    .final_geometry_helper_sha256
                ),
                baseline_bindings=(
                    scientific
                    .baseline_bindings
                ),
                environment_lock_sha256=(
                    scientific
                    .environment_lock_sha256
                ),
            )
        )
    except (
        TypeError,
        OfficialPanelError,
    ):
        raise OfficialPanelExecutionError(
            "deterministic official-panel serialization failed"
        ) from None

    write_artifacts_exclusive(
        output_root,
        artifacts,
    )

    observed = read_back_and_audit(
        output_root,
        artifacts,
    )

    artifact_sha = {
        artifact:
            sha256_bytes(
                observed[
                    artifact
                ]
            )
        for artifact in sorted(
            ALL_ARTIFACTS
        )
    }

    return GenerationResult(
        output_root=output_root,
        artifact_sha256=artifact_sha,
        content_manifest_sha256=(
            artifact_sha[
                CONTENT_MANIFEST_FILENAME
            ]
        ),
    )


def compare_execution_roots(
    production_root: Path,
    rebuild_root: Path,
) -> None:
    """Require all eleven production/rebuild files to be byte-identical."""
    production: dict[str, bytes] = {}
    rebuild: dict[str, bytes] = {}

    for artifact in ALL_ARTIFACTS:
        production_path = _safe_artifact_path(
            production_root,
            artifact,
        )

        rebuild_path = _safe_artifact_path(
            rebuild_root,
            artifact,
        )

        if (
            not production_path.is_file()
            or not rebuild_path.is_file()
        ):
            raise OfficialPanelExecutionError(
                "production/rebuild artifact missing"
            )

        production[
            artifact
        ] = production_path.read_bytes()

        rebuild[
            artifact
        ] = rebuild_path.read_bytes()

    try:
        require_artifact_sets_byte_identical(
            production,
            rebuild,
        )

        audit_reference_panel_artifacts(
            production
        )

        audit_reference_panel_artifacts(
            rebuild
        )
    except OfficialPanelError:
        raise OfficialPanelExecutionError(
            "production/rebuild byte-identity audit failed"
        ) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate frozen BacSelect selector-v1 "
            "reference-panel artefacts."
        )
    )

    parser.add_argument(
        "--mode",
        choices=(
            "production",
            "rebuild",
        ),
        required=True,
    )

    parser.add_argument(
        "--expected-commit",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-test-sha256",
        required=True,
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    return parser


def main(
    argv: list[str] | None = None,
) -> int:
    args = build_parser().parse_args(
        argv
    )

    if not args.authorize_real_execution:
        print(
            "ERROR | real official-panel generation requires "
            "--authorize-real-execution",
            file=sys.stderr,
        )

        return 2

    try:
        result = execute_panel_generation(
            repo=repo_root(),
            expected_commit=(
                args.expected_commit
            ),
            mode=args.mode,
            expected_wrapper_sha256=(
                args.expected_wrapper_sha256
            ),
            expected_wrapper_test_sha256=(
                args.expected_wrapper_test_sha256
            ),
        )
    except (
        OfficialPanelExecutionError,
        OfficialPanelError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"ERROR | {exc}",
            file=sys.stderr,
        )

        return 1

    print(
        "PASS | official selector-v1 reference-panel generation"
    )

    print(
        "execution_mode="
        + args.mode
    )

    print(
        "winning_selector="
        + SELECTOR
    )

    print(
        "winning_ladder_n="
        + str(
            WINNING_LADDER_N
        )
    )

    print(
        "winning_ladder_sha256="
        + WINNING_LADDER_SHA256
    )

    print(
        "preset_panel_sizes="
        + ",".join(
            str(
                value
            )
            for value in PANEL_SIZES
        )
    )

    print(
        "output_root="
        + str(
            result.output_root
        )
    )

    for artifact in sorted(
        result.artifact_sha256
    ):
        print(
            "artifact_sha256="
            + artifact
            + ":"
            + result.artifact_sha256[
                artifact
            ]
        )

    print(
        "content_manifest_sha256="
        + result.content_manifest_sha256
    )

    print(
        "monthly_release_assigned=no"
    )

    print(
        "panel_membership_dumped_to_console=no"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
