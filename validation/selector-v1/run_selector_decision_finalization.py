#!/usr/bin/env python3
"""Fail-closed Stage 7 selector-decision finalization wrapper.

This wrapper separates non-interpreting predecision verification from the
single authorized read of the three production decision-input artifacts.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
import csv
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType

from bacselect.selector_decision_finalization import (
    ANALYSIS_SUMMARY_ARTIFACT,
    EXACT_PRODUCT_ARTIFACT,
    FINAL_LADDER_SHA256,
    PRIMARY_METRIC_ARTIFACT,
    FinalizationEvidence,
    SelectorDecisionFinalizationError,
    finalize_selector_decision,
    verify_finalization_evidence,
)
from bacselect.selector_resolution_artifacts import (
    SCIENTIFIC_ARTIFACT_NAMES,
)


LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

LOWER_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

EXPECTED_FINALIZER_METHOD_SHA256 = (
    "25c36098903b5fa5a18da8c012a6e81a"
    "3b4c6836a6d008d042d8b0bf529e5d8e"
)

EXPECTED_FINALIZER_CORE_SHA256 = (
    "d020cb862266e8dd3544c229dff0d77c3"
    "25d8de1c4f61b4360c9db5d97a6eab1"
)

EXPECTED_FINALIZER_CORE_TEST_SHA256 = (
    "980a653f18389f672fdfe287781de5e14"
    "e582df3954cb61d0f79ddc0705b908c"
)

EXPECTED_SELECTOR_RESOLUTION_DESIGN_SHA256 = (
    "2584fddf1f06562d48abd990372ec70e"
    "a1f48da0962b1f710afb1d93e2c3223a"
)

EXPECTED_STAGE7_METHOD_SHA256 = (
    "6f0e540cdc9def82a164554619699481"
    "7d3d75aabf8ed38a40dc062c1366ff45"
)

EXPECTED_STAGE7_COMPLETION_EVIDENCE_SHA256 = (
    "bec926b41538ea231b2d9f3f0825a33a"
    "b358f764b8fdf3cf448ab35faf97b9d8"
)

EXPECTED_BYTE_IDENTITY_RECORD_SHA256 = (
    "e8071eb213a716fd13d0eb747758cda3d"
    "9bc0791d07a909a4f3da0b938bde473"
)

EXPECTED_FINAL_LADDER_MANIFEST_SHA256 = (
    "c0f17aaa2c92c27f0b4f3aebd9ffd1b"
    "e73cc403c80700b93a1b2d5786fb6b0da"
)

EXPECTED_ENVIRONMENT_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207eae"
    "f5c2435e1b6feeddc1e4654686bc2a8c"
)

EXPECTED_STAGE7_PRODUCTION_WRAPPER_SHA256 = (
    "ca1e1a0e58e3d9878bbb48cfbaac4012"
    "6907d3220c8060624ec991ab7681396c"
)

EXPECTED_STAGE7_PRODUCTION_WRAPPER_TEST_SHA256 = (
    "fd69bfe12810638a2f433fc456b8e5cd"
    "f8b70c43b8ba6580c38c89bff191e0bb"
)

EXPECTED_IMPLEMENTATION_BINDINGS: dict[
    str,
    str,
] = {
    "analysis_layer_sha256":
        "b228cc234e871593c1ce33e99d8bf7aa36c98fae8f7429cdf98117ded1cd81e6",
    "analysis_layer_test_sha256":
        "8dc4c32ac3c087096f02a544a5d4921b2151c124709931b0a264251ba9223829",
    "artifact_layer_sha256":
        "6df58f9b4e49efa4b0b7f9139b9402a2af3d2b8b7a5f0095bc9291831bf2e00a",
    "artifact_layer_test_sha256":
        "74303f78169007b91b126a11c051777dd6f049d88c18e145548462849a691835",
    "execution_adapter_sha256":
        "24cb559f906529d5f1599159f560463b5226629000079e9691cd5d430a5a5ddf",
    "execution_adapter_test_sha256":
        "1bbeb9423080f95fe4fe47d2d9239035d6e034a44b1d37243ef6f01e3c5b3ea3",
    "final_geometry_common_sha256":
        "c2534c1a8522e29362109b82416364f40cb9a8a6c4f536758867916cbe81d9f1",
    "final_ladder_manifest_sha256":
        EXPECTED_FINAL_LADDER_MANIFEST_SHA256,
    "geometry_sha256":
        "fbebf436d049be063817b717878330f38e09b3e7cb79f9dbc1b8f704af6a0d69",
    "geometry_test_sha256":
        "8c215ea881985a8d7fd83b59ee3a9ce4e1ebe5a0ffe64352d2077f098ecedec1",
    "metrics_sha256":
        "c83219404c627c71c900aafbb165e0a8dead27f3f04f073dbb7ce86437bb3af2",
    "metrics_test_sha256":
        "80b4a8f111af9c1ebd739fd99adfb9a6b656e014bf5239f767f73ae599b036ad",
    "ops_sha256":
        "eb6c1b8edab3e694b0f3825bb5ab0eaf44fdd95fdbb6a6e3e41439c18c828c0f",
    "production_wrapper_sha256":
        EXPECTED_STAGE7_PRODUCTION_WRAPPER_SHA256,
    "production_wrapper_test_sha256":
        EXPECTED_STAGE7_PRODUCTION_WRAPPER_TEST_SHA256,
    "scientific_core_sha256":
        "a972dd2d9e611a4c121c0cd6a9efebca9509adcf96ced3c0a02c570e4e570979",
    "scientific_core_test_sha256":
        "f2f9d52902a8e7819fe85ba9bbe2087f44e35c2d554727fadd10729635c90b",
    "source_truth_execution_sha256":
        "83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92",
    "sr_sha256":
        "7d3faf8a89605599e2306eea8d2d56ad690c4a588897b7446983a60e0729693b",
}

# Correct an intentionally split literal above by binding the exact frozen value
# here rather than depending on Python string formatting.
EXPECTED_IMPLEMENTATION_BINDINGS[
    "scientific_core_test_sha256"
] = (
    "f2f9d52902c0a8e7819fe85ba9bbe208"
    "7f44e35c2d554727fadd10729635c90b"
)

EXPECTED_SCIENTIFIC_SHA256: dict[
    str,
    str,
] = {
    "blinded-holdout-nearest-panel-distances.tsv":
        "b837d3f79bd8b785eae3f9ed35eab028224400e2779ab8ffe418674bfefe48f0",
    "blinded-holdout-projected-coordinates.tsv":
        "48eaa48d1a8f10a757ee170f51c2b7e2c5f88e8f43585502bd3d432bf21f1438",
    "selector-descriptive-diagnostics.json":
        "723329d5f4abef2e4ab3eb137bcdbfce24b648226d063d7fb23ad6755189409e",
    EXACT_PRODUCT_ARTIFACT:
        "d84eb7eef0053aaea52a77ab81740a9cc708c0d790bf32fe3a6d3aae01ee46c3",
    PRIMARY_METRIC_ARTIFACT:
        "7d734bf39dc9dd974d7e9947ddca2697febd933d51d456959ee3571fa72b6855",
    ANALYSIS_SUMMARY_ARTIFACT:
        "ac1f8551ac75457f7f6d6eab8bed75a0251929ee9ed723026993a13070d39ea1",
}

EXPECTED_PRODUCTION_PROVENANCE_SHA256: dict[
    str,
    str,
] = {
    "content_manifest_sha256":
        "5c7e1bee26ccdc0c433be98cad9a34092e68523ede50df492764a25511f8b69d",
    "execution_provenance_sha256":
        "ee49086fc2b74502ac3682e849746122b00eecc079bcce2376e62779751d79f3",
    "predecision_provenance_sha256":
        "e6586bb08695502d5bed4a5af925b7a54e71aff79a7438e1b417ef72354d3c07",
}

EXPECTED_REBUILD_PROVENANCE_SHA256: dict[
    str,
    str,
] = {
    "content_manifest_sha256":
        "ec8407f34c3988d5f03c32f2da990552908f087bfe38086c8031c4064849f013",
    "execution_provenance_sha256":
        "efd6d9671b2cb4eda1b78e30751c5185a89451fceb932d600cf50a4e6e8a920c",
    "predecision_provenance_sha256":
        "171b8a2827793ac81bf165139ce0b5bb98525e1c066d1506c6bda13f673656c8",
}

WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_selector_decision_finalization.py"
)

FINALIZER_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-stage7-selector-decision-finalization.md"
)

DESIGN_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-selector-resolution-design.md"
)

STAGE7_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-stage7-selector-resolution-execution.md"
)

COMPLETION_RELATIVE = Path(
    "validation/selector-v1/"
    "stage7-selector-resolution-completion-evidence.json"
)

CORE_RELATIVE = Path(
    "src/bacselect/selector_decision_finalization.py"
)

CORE_TEST_RELATIVE = Path(
    "tests/test_selector_decision_finalization.py"
)

STAGE7_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_selector_resolution_execution.py"
)

STAGE7_WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_selector_resolution_execution.py"
)

LADDER_MANIFEST_RELATIVE = Path(
    "validation/selector-v1/results/"
    "final300-2400-determinism-ladders.tsv"
)

ENVIRONMENT_LOCK_RELATIVE = Path(
    "envs/bacselect-dev-linux-64.lock"
)

EXPECTED_REPO_BINDINGS: dict[
    Path,
    str,
] = {
    FINALIZER_METHOD_RELATIVE:
        EXPECTED_FINALIZER_METHOD_SHA256,
    DESIGN_RELATIVE:
        EXPECTED_SELECTOR_RESOLUTION_DESIGN_SHA256,
    STAGE7_METHOD_RELATIVE:
        EXPECTED_STAGE7_METHOD_SHA256,
    COMPLETION_RELATIVE:
        EXPECTED_STAGE7_COMPLETION_EVIDENCE_SHA256,
    CORE_RELATIVE:
        EXPECTED_FINALIZER_CORE_SHA256,
    CORE_TEST_RELATIVE:
        EXPECTED_FINALIZER_CORE_TEST_SHA256,
    STAGE7_WRAPPER_RELATIVE:
        EXPECTED_STAGE7_PRODUCTION_WRAPPER_SHA256,
    STAGE7_WRAPPER_TEST_RELATIVE:
        EXPECTED_STAGE7_PRODUCTION_WRAPPER_TEST_SHA256,
    LADDER_MANIFEST_RELATIVE:
        EXPECTED_FINAL_LADDER_MANIFEST_SHA256,
    ENVIRONMENT_LOCK_RELATIVE:
        EXPECTED_ENVIRONMENT_LOCK_SHA256,
}


class SelectorDecisionWrapperError(
    RuntimeError
):
    """Raised when wrapper execution must fail closed."""


@dataclass(
    frozen=True,
)
class RunEnvelope:
    scientific_sha256: Mapping[
        str,
        str,
    ]
    provenance_sha256: Mapping[
        str,
        str,
    ]


@dataclass(
    frozen=True,
)
class FinalizerExecutionResult:
    output_path: Path
    output_sha256: str


def repo_root() -> Path:
    """Return repository root from this wrapper location."""
    return Path(
        __file__
    ).resolve().parents[
        2
    ]


def validate_sha256(
    value: str,
    *,
    label: str,
) -> str:
    """Validate one lowercase SHA256."""
    if LOWER_SHA256_RE.fullmatch(
        value
    ) is None:
        raise SelectorDecisionWrapperError(
            f"{label} malformed"
        )

    return value


def validate_commit(
    value: str,
    *,
    label: str,
) -> str:
    """Validate one lowercase 40-character Git commit."""
    if LOWER_COMMIT_RE.fullmatch(
        value
    ) is None:
        raise SelectorDecisionWrapperError(
            f"{label} malformed"
        )

    return value


def sha256_file(
    path: Path,
) -> str:
    """Return SHA256 while treating content as uninterpreted bytes."""
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


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    """Require exact file identity."""
    expected = validate_sha256(
        expected,
        label=label + " expected SHA256",
    )

    path = Path(
        path
    )

    if not path.is_file():
        raise SelectorDecisionWrapperError(
            f"{label} missing"
        )

    observed = sha256_file(
        path
    )

    if observed != expected:
        raise SelectorDecisionWrapperError(
            f"{label} SHA256 mismatch"
        )

    return observed


def run_git(
    repo: Path,
    *arguments: str,
) -> str:
    """Run one local-only Git query."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(
                repo
            ),
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    return result.stdout.strip()


def load_stage7_wrapper_module(
    repo: Path,
) -> ModuleType:
    """Load the already-frozen Stage 7 production wrapper."""
    path = (
        Path(
            repo
        )
        / STAGE7_WRAPPER_RELATIVE
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            "_bacselect_frozen_stage7_wrapper",
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise SelectorDecisionWrapperError(
            "could not load frozen Stage 7 wrapper"
        )

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    # Dynamic execution must register the module first.  Dataclasses and
    # annotation-aware machinery resolve the executing module through
    # sys.modules.
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
        raise

    return module


def require_frozen_repo_bindings(
    repo: Path,
) -> None:
    """Require finalizer plus directly bound frozen repository identities."""
    repo = Path(
        repo
    )

    for relative, expected in sorted(
        EXPECTED_REPO_BINDINGS.items(),
        key=lambda item:
            str(
                item[
                    0
                ]
            ),
    ):
        require_sha256(
            repo
            / relative,
            expected,
            str(
                relative
            ),
        )


def repository_preflight(
    *,
    repo: Path,
    expected_execution_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> None:
    """Complete every repository/self identity check before input reads."""

    repo = Path(
        repo
    )

    expected_execution_commit = validate_commit(
        expected_execution_commit,
        label="finalizer execution commit",
    )

    wrapper_sha = validate_sha256(
        expected_wrapper_sha256,
        label="finalizer wrapper SHA256",
    )

    wrapper_test_sha = validate_sha256(
        expected_wrapper_test_sha256,
        label="finalizer wrapper-test SHA256",
    )

    observed_head = run_git(
        repo,
        "rev-parse",
        "HEAD",
    )

    if observed_head != expected_execution_commit:
        raise SelectorDecisionWrapperError(
            "repository HEAD does not match frozen finalizer execution commit"
        )

    observed_origin = run_git(
        repo,
        "rev-parse",
        "origin/main",
    )

    if observed_origin != expected_execution_commit:
        raise SelectorDecisionWrapperError(
            "origin/main does not match frozen finalizer execution commit"
        )

    if run_git(
        repo,
        "status",
        "--porcelain",
    ):
        raise SelectorDecisionWrapperError(
            "repository working tree is not clean"
        )

    require_sha256(
        Path(
            __file__
        ),
        wrapper_sha,
        "selector-decision finalizer wrapper",
    )

    require_sha256(
        repo
        / WRAPPER_TEST_RELATIVE,
        wrapper_test_sha,
        "selector-decision finalizer wrapper test",
    )

    require_frozen_repo_bindings(
        repo
    )

    # Reuse the already-frozen Stage 7 repository preflight so every existing
    # Stage 7 implementation/test binding is independently rechecked.
    stage7_wrapper = load_stage7_wrapper_module(
        repo
    )

    stage7_preflight = getattr(
        stage7_wrapper,
        "repository_preflight",
        None,
    )

    if not callable(
        stage7_preflight
    ):
        raise SelectorDecisionWrapperError(
            "frozen Stage 7 wrapper lacks repository_preflight"
        )

    try:
        stage7_preflight(
            repo=repo,
            expected_commit=expected_execution_commit,
            expected_wrapper_sha256=(
                EXPECTED_STAGE7_PRODUCTION_WRAPPER_SHA256
            ),
            expected_wrapper_test_sha256=(
                EXPECTED_STAGE7_PRODUCTION_WRAPPER_TEST_SHA256
            ),
        )
    except Exception as exc:
        raise SelectorDecisionWrapperError(
            "frozen Stage 7 repository preflight failed"
        ) from exc


def files_byte_identical(
    first: Path,
    second: Path,
) -> bool:
    """Compare two files byte-for-byte without interpreting their content."""
    first = Path(
        first
    )

    second = Path(
        second
    )

    if (
        not first.is_file()
        or not second.is_file()
    ):
        return False

    if first.stat().st_size != second.stat().st_size:
        return False

    with first.open(
        "rb"
    ) as first_handle, second.open(
        "rb"
    ) as second_handle:
        while True:
            first_chunk = first_handle.read(
                1024 * 1024
            )

            second_chunk = second_handle.read(
                1024 * 1024
            )

            if first_chunk != second_chunk:
                return False

            if not first_chunk:
                return True


def collect_run_envelope(
    *,
    run_dir: Path,
    expected_scientific_sha256: Mapping[
        str,
        str,
    ],
    expected_provenance_sha256: Mapping[
        str,
        str,
    ],
    label: str,
) -> RunEnvelope:
    """Verify one exact nine-file finalized Stage 7 envelope."""

    run_dir = Path(
        run_dir
    )

    if not run_dir.is_dir():
        raise SelectorDecisionWrapperError(
            f"{label} finalized run directory missing"
        )

    entries = sorted(
        run_dir.iterdir(),
        key=lambda path:
            path.name,
    )

    if any(
        not entry.is_file()
        for entry in entries
    ):
        raise SelectorDecisionWrapperError(
            f"{label} finalized run envelope contains non-file entries"
        )

    if len(
        entries
    ) != 9:
        raise SelectorDecisionWrapperError(
            f"{label} finalized run envelope must contain exactly nine files"
        )

    expected_scientific = dict(
        expected_scientific_sha256
    )

    if set(
        expected_scientific
    ) != set(
        SCIENTIFIC_ARTIFACT_NAMES
    ):
        raise SelectorDecisionWrapperError(
            "expected scientific artifact set is malformed"
        )

    observed_names = {
        entry.name
        for entry in entries
    }

    if not set(
        SCIENTIFIC_ARTIFACT_NAMES
    ).issubset(
        observed_names
    ):
        raise SelectorDecisionWrapperError(
            f"{label} finalized run envelope is missing scientific artifacts"
        )

    observed_scientific: dict[
        str,
        str,
    ] = {}

    for name in SCIENTIFIC_ARTIFACT_NAMES:
        path = (
            run_dir
            / name
        )

        observed = sha256_file(
            path
        )

        expected = validate_sha256(
            expected_scientific[
                name
            ],
            label=(
                f"{label} expected scientific SHA256 {name}"
            ),
        )

        if observed != expected:
            raise SelectorDecisionWrapperError(
                f"{label} scientific artifact SHA256 mismatch: {name}"
            )

        observed_scientific[
            name
        ] = observed

    provenance_entries = [
        entry
        for entry in entries
        if entry.name
        not in set(
            SCIENTIFIC_ARTIFACT_NAMES
        )
    ]

    if len(
        provenance_entries
    ) != 3:
        raise SelectorDecisionWrapperError(
            f"{label} finalized run envelope must contain exactly three "
            "provenance artifacts"
        )

    expected_provenance = {
        key:
            validate_sha256(
                value,
                label=(
                    f"{label} expected provenance SHA256 {key}"
                ),
            )
        for key, value in expected_provenance_sha256.items()
    }

    if len(
        expected_provenance
    ) != 3:
        raise SelectorDecisionWrapperError(
            f"{label} expected provenance mapping must contain three hashes"
        )

    if len(
        set(
            expected_provenance.values()
        )
    ) != 3:
        raise SelectorDecisionWrapperError(
            f"{label} expected provenance hashes must be unique"
        )

    observed_provenance_values = [
        sha256_file(
            entry
        )
        for entry in provenance_entries
    ]

    if sorted(
        observed_provenance_values
    ) != sorted(
        expected_provenance.values()
    ):
        raise SelectorDecisionWrapperError(
            f"{label} provenance artifact SHA256 set mismatch"
        )

    return RunEnvelope(
        scientific_sha256=dict(
            sorted(
                observed_scientific.items()
            )
        ),
        provenance_sha256=dict(
            sorted(
                expected_provenance.items()
            )
        ),
    )


def require_scientific_pairs_byte_identical(
    *,
    production_dir: Path,
    rebuild_dir: Path,
) -> None:
    """Require all six production/rebuild scientific files to be identical."""

    production_dir = Path(
        production_dir
    )

    rebuild_dir = Path(
        rebuild_dir
    )

    for name in SCIENTIFIC_ARTIFACT_NAMES:
        if not files_byte_identical(
            production_dir
            / name,
            rebuild_dir
            / name,
        ):
            raise SelectorDecisionWrapperError(
                "production/rebuild scientific artifact pair differs: "
                + name
            )


def parse_final_ladder_manifest(
    path: Path,
) -> dict[
    str,
    str,
]:
    """Require exact final deterministic ladder-manifest structure."""

    path = Path(
        path
    )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        if reader.fieldnames != [
            "selector",
            "max_n",
            "ladder_sha256",
        ]:
            raise SelectorDecisionWrapperError(
                "final ladder manifest header mismatch"
            )

        rows = list(
            reader
        )

    if len(
        rows
    ) != 3:
        raise SelectorDecisionWrapperError(
            "final ladder manifest must contain exactly three rows"
        )

    if [
        row[
            "selector"
        ]
        for row in rows
    ] != [
        "OPS",
        "SR",
        "AG",
    ]:
        raise SelectorDecisionWrapperError(
            "final ladder manifest selector ordering mismatch"
        )

    for row in rows:
        if row[
            "max_n"
        ] != "500":
            raise SelectorDecisionWrapperError(
                "final ladder manifest max_n mismatch"
            )

        validate_sha256(
            row[
                "ladder_sha256"
            ],
            label=(
                "final ladder SHA256 "
                + row[
                    "selector"
                ]
            ),
        )

    observed = {
        row[
            "selector"
        ]:
            row[
                "ladder_sha256"
            ]
        for row in rows
        if row[
            "selector"
        ] in {
            "OPS",
            "SR",
        }
    }

    if observed != FINAL_LADDER_SHA256:
        raise SelectorDecisionWrapperError(
            "final OPS/SR ladder fingerprints mismatch"
        )

    return observed


def output_preflight(
    *,
    repo: Path,
    output_path: Path,
) -> None:
    """Require a fresh atomic-output target outside the repository."""

    repo = Path(
        repo
    ).resolve()

    output_path = Path(
        output_path
    ).resolve()

    parent = output_path.parent

    if not parent.is_dir():
        raise SelectorDecisionWrapperError(
            "selector-decision output parent directory missing"
        )

    try:
        output_path.relative_to(
            repo
        )
    except ValueError:
        pass
    else:
        raise SelectorDecisionWrapperError(
            "selector-decision record must first be written outside Git"
        )

    if output_path.exists():
        raise SelectorDecisionWrapperError(
            "selector-decision output path already exists"
        )

    temporary = output_path.with_name(
        "."
        + output_path.name
        + ".tmp"
    )

    if temporary.exists():
        raise SelectorDecisionWrapperError(
            "selector-decision temporary output path already exists"
        )


def write_bytes_atomic(
    path: Path,
    payload: bytes,
) -> str:
    """Write exact bytes atomically without overwriting prior evidence."""

    path = Path(
        path
    )

    temporary = path.with_name(
        "."
        + path.name
        + ".tmp"
    )

    if (
        path.exists()
        or temporary.exists()
    ):
        raise SelectorDecisionWrapperError(
            "selector-decision output or temporary path already exists"
        )

    # Use exclusive creation and preserve the temporary artifact if any later
    # operation fails. Failed evidence is never silently deleted.
    with temporary.open(
        "xb"
    ) as handle:
        handle.write(
            payload
        )
        handle.flush()
        os.fsync(
            handle.fileno()
        )

    os.replace(
        temporary,
        path,
    )

    return sha256_file(
        path
    )


def predecision_verify(
    *,
    repo: Path,
    expected_execution_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    byte_identity_record: Path,
    production_dir: Path,
    rebuild_dir: Path,
) -> FinalizationEvidence:
    """Complete all non-interpreting checks before product interpretation."""

    repo = Path(
        repo
    )

    repository_preflight(
        repo=repo,
        expected_execution_commit=expected_execution_commit,
        expected_wrapper_sha256=expected_wrapper_sha256,
        expected_wrapper_test_sha256=expected_wrapper_test_sha256,
    )

    completion_path = (
        repo
        / COMPLETION_RELATIVE
    )

    ladder_manifest_path = (
        repo
        / LADDER_MANIFEST_RELATIVE
    )

    require_sha256(
        byte_identity_record,
        EXPECTED_BYTE_IDENTITY_RECORD_SHA256,
        "Stage 7 byte-identity verification record",
    )

    production = collect_run_envelope(
        run_dir=production_dir,
        expected_scientific_sha256=(
            EXPECTED_SCIENTIFIC_SHA256
        ),
        expected_provenance_sha256=(
            EXPECTED_PRODUCTION_PROVENANCE_SHA256
        ),
        label="production",
    )

    rebuild = collect_run_envelope(
        run_dir=rebuild_dir,
        expected_scientific_sha256=(
            EXPECTED_SCIENTIFIC_SHA256
        ),
        expected_provenance_sha256=(
            EXPECTED_REBUILD_PROVENANCE_SHA256
        ),
        label="independent rebuild",
    )

    require_scientific_pairs_byte_identical(
        production_dir=production_dir,
        rebuild_dir=rebuild_dir,
    )

    observed_ladders = parse_final_ladder_manifest(
        ladder_manifest_path
    )

    # These two inputs are aggregate-only predecision evidence, not interpreted
    # selector metrics/products.
    completion_bytes = completion_path.read_bytes()

    byte_identity_bytes = Path(
        byte_identity_record
    ).read_bytes()

    try:
        return verify_finalization_evidence(
            completion_bytes=completion_bytes,
            byte_identity_bytes=byte_identity_bytes,
            expected_completion_sha256=(
                EXPECTED_STAGE7_COMPLETION_EVIDENCE_SHA256
            ),
            expected_byte_identity_sha256=(
                EXPECTED_BYTE_IDENTITY_RECORD_SHA256
            ),
            expected_stage7_method_sha256=(
                EXPECTED_STAGE7_METHOD_SHA256
            ),
            expected_selector_resolution_design_sha256=(
                EXPECTED_SELECTOR_RESOLUTION_DESIGN_SHA256
            ),
            expected_implementation_bindings=(
                EXPECTED_IMPLEMENTATION_BINDINGS
            ),
            observed_production_scientific_sha256=(
                production.scientific_sha256
            ),
            observed_rebuild_scientific_sha256=(
                rebuild.scientific_sha256
            ),
            observed_production_provenance_sha256=(
                production.provenance_sha256
            ),
            observed_rebuild_provenance_sha256=(
                rebuild.provenance_sha256
            ),
            observed_final_ladder_sha256=(
                observed_ladders
            ),
        )
    except SelectorDecisionFinalizationError as exc:
        raise SelectorDecisionWrapperError(
            "aggregate Stage 7 finalization evidence failed verification"
        ) from exc


def read_production_decision_inputs(
    production_dir: Path,
) -> tuple[
    bytes,
    bytes,
    bytes,
]:
    """Perform the only three interpreted production artifact reads."""

    production_dir = Path(
        production_dir
    )

    primary = (
        production_dir
        / PRIMARY_METRIC_ARTIFACT
    ).read_bytes()

    products = (
        production_dir
        / EXACT_PRODUCT_ARTIFACT
    ).read_bytes()

    summary = (
        production_dir
        / ANALYSIS_SUMMARY_ARTIFACT
    ).read_bytes()

    return (
        primary,
        products,
        summary,
    )


def execute_finalization(
    *,
    repo: Path,
    expected_execution_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    byte_identity_record: Path,
    production_dir: Path,
    rebuild_dir: Path,
    output_path: Path,
) -> FinalizerExecutionResult:
    """Run one fully gated selector-decision finalization."""

    evidence = predecision_verify(
        repo=repo,
        expected_execution_commit=expected_execution_commit,
        expected_wrapper_sha256=expected_wrapper_sha256,
        expected_wrapper_test_sha256=expected_wrapper_test_sha256,
        byte_identity_record=byte_identity_record,
        production_dir=production_dir,
        rebuild_dir=rebuild_dir,
    )

    # Output validity is also established before interpreting decision inputs.
    output_preflight(
        repo=repo,
        output_path=output_path,
    )

    (
        primary_metric_bytes,
        exact_product_bytes,
        analysis_summary_bytes,
    ) = read_production_decision_inputs(
        production_dir
    )

    try:
        decision_bytes = finalize_selector_decision(
            evidence=evidence,
            primary_metric_bytes=primary_metric_bytes,
            exact_product_bytes=exact_product_bytes,
            analysis_summary_bytes=analysis_summary_bytes,
            finalizer_execution_commit=(
                expected_execution_commit
            ),
            finalizer_method_sha256=(
                EXPECTED_FINALIZER_METHOD_SHA256
            ),
            finalizer_implementation_sha256=(
                expected_wrapper_sha256
            ),
            finalizer_test_sha256=(
                expected_wrapper_test_sha256
            ),
            environment_bindings={
                "environment_lock_sha256":
                    EXPECTED_ENVIRONMENT_LOCK_SHA256,
                "finalizer_core_sha256":
                    EXPECTED_FINALIZER_CORE_SHA256,
                "finalizer_core_test_sha256":
                    EXPECTED_FINALIZER_CORE_TEST_SHA256,
            },
        )
    except SelectorDecisionFinalizationError as exc:
        raise SelectorDecisionWrapperError(
            "selector-decision core finalization failed"
        ) from exc

    output_sha = write_bytes_atomic(
        output_path,
        decision_bytes,
    )

    return FinalizerExecutionResult(
        output_path=Path(
            output_path
        ).resolve(),
        output_sha256=output_sha,
    )


def parse_args(
    argv: list[
        str
    ] | None = None,
) -> argparse.Namespace:
    """Parse explicit production finalization arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Finalize the frozen BacSelect selector-v1 OPS/SR decision."
        )
    )

    parser.add_argument(
        "--repo",
        type=Path,
        default=repo_root(),
    )

    parser.add_argument(
        "--expected-execution-commit",
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
        "--byte-identity-record",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--production-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--rebuild-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-path",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
        help=(
            "Required explicit acknowledgement that the frozen predecision "
            "gate may proceed to the one real selector-decision read."
        ),
    )

    return parser.parse_args(
        argv
    )


def main(
    argv: list[
        str
    ] | None = None,
) -> int:
    """CLI entry point without printing decision or product values."""

    args = parse_args(
        argv
    )

    if not args.authorize_real_execution:
        raise SelectorDecisionWrapperError(
            "real selector-decision execution requires "
            "--authorize-real-execution"
        )

    result = execute_finalization(
        repo=args.repo,
        expected_execution_commit=(
            args.expected_execution_commit
        ),
        expected_wrapper_sha256=(
            args.expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            args.expected_wrapper_test_sha256
        ),
        byte_identity_record=(
            args.byte_identity_record
        ),
        production_dir=(
            args.production_dir
        ),
        rebuild_dir=(
            args.rebuild_dir
        ),
        output_path=(
            args.output_path
        ),
    )

    print(
        "PASS | STAGE7_SELECTOR_DECISION_RECORD_WRITTEN"
    )

    print(
        "selector_decision_record="
        + str(
            result.output_path
        )
    )

    print(
        "selector_decision_record_sha256="
        + result.output_sha256
    )

    print(
        "SELECTOR_DECISION_FINALIZED_IN_SCRATCH=yes"
    )

    print(
        "PANEL_UNBLINDING_AUTHORIZED=no"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except SelectorDecisionWrapperError as exc:
        print(
            "ERROR | "
            + str(
                exc
            ),
            file=sys.stderr,
        )
        raise SystemExit(
            1
        )
