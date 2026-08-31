#!/usr/bin/env python3
"""Portable monthly repeated-BioSample reconciliation executor."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
from types import ModuleType
from typing import (
    Callable,
    Mapping,
    Sequence,
)

from bacselect import monthly_biosample_reconciliation
from bacselect import monthly_source_truth
from bacselect import source_truth
from bacselect.source_cache_verify import (
    resolve_manifest_path,
)
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    BIOSAMPLE_NONREPRESENTATIVE,
    BIOSAMPLE_UNRESOLVED,
)
from bacselect.source_repeated_biosample_execution import (
    VerifiedBioSampleFingerprint,
    fingerprint_stage2_candidate,
)
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


STAGE_NAME = "biosample-reconciliation"
PARTIAL_NAME = "biosample-reconciliation.partial"
MATERIALIZATION_NAME = (
    "biosample-reconciliation-materialization.partial"
)

DECISIONS_NAME = "biosample-reconciliation-decisions.tsv"
RECORD_NAME = "monthly-biosample-reconciliation-record.json"

COMPLETION_NAME = "biosample-reconciliation-completion.json"
COMPLETION_TEMP_NAME = (
    ".biosample-reconciliation-completion.json.tmp"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-biosample-reconciliation-completion-v1"
)
COMPLETION_STATUS = (
    "BIOSAMPLE_RECONCILIATION_EXECUTION_COMPLETE"
)

SEQUENCE_PLAN_STAGE_NAME = "sequence-plan"
SEQUENCE_PLAN_RECORD_NAME = "monthly-sequence-plan-record.json"
FRESH_TARGETS_NAME = "fresh-targets.tsv"

EXPECTED_MONTHLY_BIOSAMPLE_SHA256 = (
    "af9f769ec03e838bc7322dc16a3daf7e"
    "45bab0be5d4db0bb6dfd0ff9c53e5446"
)
EXPECTED_MONTHLY_BIOSAMPLE_TEST_SHA256 = (
    "72691aa31404eb6a2e839f4a2228048d"
    "c9013e66ebd5dad332e7c41c3e3ce531"
)
EXPECTED_MONTHLY_BIOSAMPLE_METHOD_SHA256 = (
    "0f8a0f05856d31a563d8d0c07dcd7ea"
    "fcdb970d4395898b12b6ee6ff8371a30b"
)

EXPECTED_POST_SEQUENCE_SHA256 = (
    "62fa1e2f7d806f94b5f5eca73fb76874"
    "5d3913a4b218a4d354562033cd300fe8"
)
EXPECTED_FINGERPRINT_SHA256 = (
    "6c994d243709abdbe9d7c8949e156009"
    "b9f31f3fcef3247cc3c5679e2fff41c9"
)
EXPECTED_REPEATED_EXECUTION_SHA256 = (
    "ee95fac744d1daf413742b39e9b7d8b5"
    "d4d65c52edce08dc0df2dc1ff776a222"
)
EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256 = (
    "83b8ec7fce774c0b68cb2af982aef139"
    "04c6b64b3ee695512c578f98e5de9b92"
)

EXPECTED_STAGE4_WRAPPER_SHA256 = (
    "f13b6e82e2e750902fe528a5d1fdab2d"
    "c4e829dac5b5aedd717045ab2084d3b5"
)
EXPECTED_STAGE4_TEST_SHA256 = (
    "90a426d6049315ae0e41be0228feba750"
    "035ef77191159d30f0a148f17643117"
)
EXPECTED_STAGE4_METHOD_SHA256 = (
    "3acbc6b651777f1a62eaf8225a4db512"
    "5d9c28cb7016ccc1fc4c35e44b55c454"
)

EXPECTED_CACHE_WRAPPER_SHA256 = (
    "0a45ee60f06e102afba93cdc08f588f9b"
    "c547f7103279e59ffd4362cb5526c3e"
)
EXPECTED_CACHE_TEST_SHA256 = (
    "5e6341f3371d5c789b23a493ba16d473"
    "6965e897f4dddc430d3a98ce02593c25"
)
EXPECTED_CACHE_METHOD_SHA256 = (
    "36a61a09c3bbdd931023dedbc0578b211"
    "d4d6b70dae020eee80a47e726c633bd"
)

EXPECTED_CATALOGUE_WRAPPER_SHA256 = (
    "2cb7e162aa36b141d54b18fc29ffbaa9"
    "be3a5d9ca42a9e6b5bb1ff62e14cb3ea"
)
EXPECTED_CATALOGUE_TEST_SHA256 = (
    "2f6f2e8867e071b93972d3e07f9567f"
    "194991817a8d6dec6cebf266f7ca29f92"
)
EXPECTED_CATALOGUE_METHOD_SHA256 = (
    "128b533c2cfc9f9a0751094a9bb33f5e"
    "f97414ede86f8a3df9d104b9c7d7fdcd"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)
COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)
RELEASE_RE = re.compile(
    r"^([0-9]{4})\.([0-9]{2})$"
)
GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)


class MonthlyBioSampleExecutionError(
    RuntimeError
):
    """Raised when monthly Stage 5 execution fails closed."""


@dataclass(
    frozen=True
)
class Stage4Context:
    release_id: str
    source_snapshot_id: str
    execution_commit: str
    metadata_context: object
    completion_context: object
    catalogue_chain: tuple[object, ...]
    catalogue_chain_signature: tuple[
        tuple[
            str,
            str,
            str,
        ],
        ...
    ]
    catalogue_chain_sha256: str
    catalogue_record: Mapping[
        str,
        object,
    ]
    catalogue_payload: bytes
    catalogue_sha256: str
    entries_by_accession: Mapping[
        str,
        Mapping[
            str,
            object,
        ],
    ]
    provenance_by_sha: Mapping[
        str,
        Mapping[
            str,
            object,
        ],
    ]
    decisions_payload: bytes
    decision_rows: tuple[
        Mapping[
            str,
            str,
        ],
        ...
    ]
    decision_by_accession: Mapping[
        str,
        Mapping[
            str,
            str,
        ],
    ]
    relations_payload: bytes
    record_payload: bytes
    completion_payload: bytes
    completion_record: Mapping[
        str,
        object,
    ]


@dataclass(
    frozen=True
)
class FileObservation:
    path: Path
    sha256: str
    size_bytes: int


@dataclass(
    frozen=True
)
class AuthoritativeObservation:
    sha256: str
    size_bytes: int


@dataclass(
    frozen=True
)
class CurrentBatchObservation:
    """Authenticated current-release batch evidence used by Stage 5."""

    provenance: Mapping[
        str,
        object,
    ]
    batch: object


@dataclass(
    frozen=True
)
class PriorBatchObservation:
    """Authenticated historical batch evidence used by Stage 5."""

    provenance: Mapping[
        str,
        object,
    ]
    batch: object


@dataclass(
    frozen=True
)
class MonthlyBioSampleExecutionResult:
    release_id: str
    source_snapshot_id: str
    stage_path: Path
    decisions_sha256: str
    record_sha256: str
    completion_path: Path
    suitable_count: int
    continue_count: int
    nonrepresentative_count: int
    unresolved_count: int


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def validate_sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyBioSampleExecutionError(
            f"{label} is not a lowercase SHA256"
        )

    return value


def validate_commit(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyBioSampleExecutionError(
            "execution commit is invalid"
        )

    return value


def validate_count(
    value: object,
    *,
    label: str,
) -> int:
    if (
        not isinstance(
            value,
            int,
        )
        or isinstance(
            value,
            bool,
        )
        or value < 0
    ):
        raise MonthlyBioSampleExecutionError(
            f"{label} is invalid"
        )

    return value


def _canonical_json_bytes(
    value: object,
) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )


def _git_output(
    repo: Path,
    *args: str,
) -> str:
    completed = subprocess.run(
        (
            "git",
            *args,
        ),
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return completed.stdout.strip()


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    if (
        value.is_symlink()
        or not value.is_dir()
    ):
        raise MonthlyBioSampleExecutionError(
            f"{label} is not a real directory"
        )

    return value


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    if (
        value.is_symlink()
        or not value.is_file()
    ):
        raise MonthlyBioSampleExecutionError(
            f"{label} is not a regular file"
        )

    return value


def _require_exact_inventory(
    directory: Path,
    *,
    expected_files: set[
        str
    ],
    label: str,
) -> None:
    root = _require_real_directory(
        directory,
        label=label,
    )

    observed = {
        value.name
        for value in root.iterdir()
    }

    if observed != expected_files:
        raise MonthlyBioSampleExecutionError(
            f"{label} inventory changed"
        )

    for name in expected_files:
        _require_regular_file(
            root
            / name,
            label=(
                f"{label} artifact {name}"
            ),
        )


def fsync_directory(
    path: Path,
) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY
        | getattr(
            os,
            "O_DIRECTORY",
            0,
        ),
    )

    try:
        os.fsync(
            descriptor
        )
    finally:
        os.close(
            descriptor
        )


def _write_all(
    descriptor: int,
    payload: bytes,
) -> None:
    view = memoryview(
        payload
    )

    while view:
        written = os.write(
            descriptor,
            view,
        )

        if written <= 0:
            raise MonthlyBioSampleExecutionError(
                "short artifact write"
            )

        view = view[
            written:
        ]


def write_no_clobber(
    path: Path,
    payload: bytes,
) -> None:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "artifact payload must be bytes"
        )

    if os.path.lexists(
        path
    ):
        raise MonthlyBioSampleExecutionError(
            f"artifact already exists: {path.name}"
        )

    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL,
        0o644,
    )

    try:
        os.fchmod(
            descriptor,
            0o644,
        )

        _write_all(
            descriptor,
            payload,
        )

        os.fsync(
            descriptor
        )
    finally:
        os.close(
            descriptor
        )

    observed = _require_regular_file(
        path,
        label=f"written artifact {path.name}",
    ).read_bytes()

    if observed != payload:
        raise MonthlyBioSampleExecutionError(
            f"artifact readback changed: {path.name}"
        )

    if stat.S_IMODE(
        path.stat().st_mode
    ) != 0o644:
        raise MonthlyBioSampleExecutionError(
            f"artifact mode changed: {path.name}"
        )


def _load_module(
    path: Path,
    *,
    module_name: str,
    expected_sha256: str,
) -> ModuleType:
    file_path = _require_regular_file(
        path,
        label=module_name,
    )

    if sha256_file(
        file_path
    ) != expected_sha256:
        raise MonthlyBioSampleExecutionError(
            f"{module_name} SHA256 mismatch"
        )

    spec = importlib.util.spec_from_file_location(
        module_name,
        file_path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise MonthlyBioSampleExecutionError(
            f"cannot import {module_name}"
        )

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


def load_frozen_stage4_execution(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo
        / "validation"
        / "selector-v1"
        / "run_monthly_source_truth.py",
        module_name=(
            "_bacselect_frozen_monthly_source_truth"
        ),
        expected_sha256=(
            EXPECTED_STAGE4_WRAPPER_SHA256
        ),
    )


def load_frozen_cache_execution(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo
        / "validation"
        / "selector-v1"
        / "run_monthly_cache_verification.py",
        module_name=(
            "_bacselect_frozen_monthly_cache_verification"
        ),
        expected_sha256=(
            EXPECTED_CACHE_WRAPPER_SHA256
        ),
    )


def load_frozen_catalogue_execution(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo
        / "validation"
        / "selector-v1"
        / "run_monthly_sequence_cache_catalogue.py",
        module_name=(
            "_bacselect_frozen_monthly_sequence_cache_catalogue"
        ),
        expected_sha256=(
            EXPECTED_CATALOGUE_WRAPPER_SHA256
        ),
    )


def repository_preflight(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> None:
    root = _require_real_directory(
        Path(
            repo
        ).resolve(),
        label="repository root",
    )

    commit = validate_commit(
        expected_commit
    )

    if (
        _git_output(
            root,
            "rev-parse",
            "HEAD",
        )
        != commit
    ):
        raise MonthlyBioSampleExecutionError(
            "repository HEAD differs from expected commit"
        )

    if _git_output(
        root,
        "status",
        "--porcelain",
    ):
        raise MonthlyBioSampleExecutionError(
            "repository is not clean"
        )

    identities = (
        (
            root
            / "src"
            / "bacselect"
            / "monthly_biosample_reconciliation.py",
            EXPECTED_MONTHLY_BIOSAMPLE_SHA256,
            "monthly Stage 5 core",
        ),
        (
            root
            / "tests"
            / "test_monthly_biosample_reconciliation.py",
            EXPECTED_MONTHLY_BIOSAMPLE_TEST_SHA256,
            "monthly Stage 5 core tests",
        ),
        (
            root
            / "validation"
            / "selector-v1"
            / "prospective-monthly-biosample-reconciliation.md",
            EXPECTED_MONTHLY_BIOSAMPLE_METHOD_SHA256,
            "monthly Stage 5 pure method",
        ),
        (
            root
            / "src"
            / "bacselect"
            / "source_post_sequence_eligibility.py",
            EXPECTED_POST_SEQUENCE_SHA256,
            "frozen BioSample reconciler",
        ),
        (
            root
            / "src"
            / "bacselect"
            / "source_fingerprint.py",
            EXPECTED_FINGERPRINT_SHA256,
            "frozen topology fingerprint",
        ),
        (
            root
            / "src"
            / "bacselect"
            / "source_repeated_biosample_execution.py",
            EXPECTED_REPEATED_EXECUTION_SHA256,
            "frozen BioSample evidence bridge",
        ),
        (
            root
            / "src"
            / "bacselect"
            / "source_truth_execution.py",
            EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256,
            "frozen source evidence reconstruction",
        ),
        (
            root
            / "validation"
            / "selector-v1"
            / "run_monthly_source_truth.py",
            EXPECTED_STAGE4_WRAPPER_SHA256,
            "Stage 4 executor",
        ),
        (
            root
            / "tests"
            / "test_run_monthly_source_truth.py",
            EXPECTED_STAGE4_TEST_SHA256,
            "Stage 4 executor tests",
        ),
        (
            root
            / "validation"
            / "selector-v1"
            / "prospective-monthly-source-truth-execution.md",
            EXPECTED_STAGE4_METHOD_SHA256,
            "Stage 4 executor method",
        ),
        (
            root
            / "validation"
            / "selector-v1"
            / "run_monthly_cache_verification.py",
            EXPECTED_CACHE_WRAPPER_SHA256,
            "cache-verification executor",
        ),
        (
            root
            / "tests"
            / "test_run_monthly_cache_verification.py",
            EXPECTED_CACHE_TEST_SHA256,
            "cache-verification executor tests",
        ),
        (
            root
            / "validation"
            / "selector-v1"
            / "prospective-monthly-cache-verification-execution.md",
            EXPECTED_CACHE_METHOD_SHA256,
            "cache-verification execution method",
        ),
        (
            root
            / "validation"
            / "selector-v1"
            / "run_monthly_sequence_cache_catalogue.py",
            EXPECTED_CATALOGUE_WRAPPER_SHA256,
            "sequence-cache catalogue executor",
        ),
        (
            root
            / "tests"
            / "test_run_monthly_sequence_cache_catalogue.py",
            EXPECTED_CATALOGUE_TEST_SHA256,
            "sequence-cache catalogue executor tests",
        ),
        (
            root
            / "validation"
            / "selector-v1"
            / "prospective-monthly-sequence-cache-catalogue-execution.md",
            EXPECTED_CATALOGUE_METHOD_SHA256,
            "sequence-cache catalogue execution method",
        ),
    )

    for path, expected, label in identities:
        file_path = _require_regular_file(
            path,
            label=label,
        )

        observed = sha256_file(
            file_path
        )

        if observed != expected:
            raise MonthlyBioSampleExecutionError(
                f"{label} SHA256 mismatch"
            )

    wrapper = (
        root
        / "validation"
        / "selector-v1"
        / "run_monthly_biosample_reconciliation.py"
    )

    test = (
        root
        / "tests"
        / "test_run_monthly_biosample_reconciliation.py"
    )

    if sha256_file(
        wrapper
    ) != validate_sha256(
        expected_wrapper_sha256,
        label="expected wrapper SHA256",
    ):
        raise MonthlyBioSampleExecutionError(
            "Stage 5 executor SHA256 mismatch"
        )

    if sha256_file(
        test
    ) != validate_sha256(
        expected_wrapper_test_sha256,
        label="expected wrapper-test SHA256",
    ):
        raise MonthlyBioSampleExecutionError(
            "Stage 5 executor-test SHA256 mismatch"
        )

    stage4 = load_frozen_stage4_execution(
        root
    )

    cache = load_frozen_cache_execution(
        root
    )

    catalogue = load_frozen_catalogue_execution(
        root
    )

    stage4.repository_preflight(
        root,
        expected_commit=commit,
        expected_wrapper_sha256=(
            EXPECTED_STAGE4_WRAPPER_SHA256
        ),
        expected_wrapper_test_sha256=(
            EXPECTED_STAGE4_TEST_SHA256
        ),
    )

    cache.repository_preflight(
        root,
        expected_commit=commit,
        expected_wrapper_sha256=(
            EXPECTED_CACHE_WRAPPER_SHA256
        ),
        expected_wrapper_test_sha256=(
            EXPECTED_CACHE_TEST_SHA256
        ),
    )

    catalogue.repository_preflight(
        root,
        expected_commit=commit,
        expected_wrapper_sha256=(
            EXPECTED_CATALOGUE_WRAPPER_SHA256
        ),
        expected_wrapper_test_sha256=(
            EXPECTED_CATALOGUE_TEST_SHA256
        ),
    )


def _release_ordinal(
    value: object,
) -> int:
    if not isinstance(
        value,
        str,
    ):
        raise MonthlyBioSampleExecutionError(
            "origin release ID is invalid"
        )

    match = RELEASE_RE.fullmatch(
        value
    )

    if match is None:
        raise MonthlyBioSampleExecutionError(
            "origin release ID is invalid"
        )

    year = int(
        match.group(
            1
        )
    )

    month = int(
        match.group(
            2
        )
    )

    if not 1 <= month <= 12:
        raise MonthlyBioSampleExecutionError(
            "origin release month is invalid"
        )

    return (
        year
        * 12
        + month
    )


def classify_origin_release(
    origin_release_id: object,
    *,
    current_release_id: str,
) -> str:
    origin = _release_ordinal(
        origin_release_id
    )

    current = _release_ordinal(
        current_release_id
    )

    if origin > current:
        raise MonthlyBioSampleExecutionError(
            "candidate provenance originates from a future release"
        )

    if origin == current:
        return "CURRENT"

    return "PRIOR"


def _stage4_identity(
    context: Stage4Context,
    cache_execution,
) -> tuple[
    object,
    ...,
]:
    return (
        context.release_id,
        context.source_snapshot_id,
        context.execution_commit,
        cache_execution.metadata_context_identity(
            context.metadata_context
        ),
        context.catalogue_chain_signature,
        context.catalogue_chain_sha256,
        context.catalogue_sha256,
        hashlib.sha256(
            context.decisions_payload
        ).hexdigest(),
        hashlib.sha256(
            context.relations_payload
        ).hexdigest(),
        hashlib.sha256(
            context.record_payload
        ).hexdigest(),
        hashlib.sha256(
            context.completion_payload
        ).hexdigest(),
    )


def load_stage4_context(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    authoritative_root: Path,
    execution_commit: str,
    stage4_execution,
    cache_execution,
    catalogue_execution,
) -> Stage4Context:
    root = _require_real_directory(
        Path(
            repo
        ).resolve(),
        label="repository root",
    )

    production = _require_real_directory(
        Path(
            production_root
        ),
        label="production root",
    )

    stage1 = _require_real_directory(
        Path(
            stage1_root
        ),
        label="Stage 1 root",
    ).resolve()

    _require_real_directory(
        Path(
            authoritative_root
        ),
        label="authoritative root",
    )

    commit = validate_commit(
        execution_commit
    )

    try:
        metadata = (
            cache_execution
            .load_current_metadata_context(
                repo=root,
                production_root=production,
                stage1_root=stage1,
                execution_commit=commit,
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleExecutionError(
            "current metadata context audit failed"
        ) from exc

    if (
        Path(
            metadata.stage1_root
        ).resolve()
        != stage1
    ):
        raise MonthlyBioSampleExecutionError(
            "metadata context Stage 1 root changed"
        )

    plan_stage = _require_real_directory(
        stage1
        / SEQUENCE_PLAN_STAGE_NAME,
        label="sequence-plan stage",
    )

    sequence_plan_record = (
        _require_regular_file(
            plan_stage
            / SEQUENCE_PLAN_RECORD_NAME,
            label="monthly sequence-plan record",
        )
    )

    fresh_targets = (
        _require_regular_file(
            plan_stage
            / FRESH_TARGETS_NAME,
            label="monthly fresh targets",
        )
    )

    try:
        acquisition = (
            catalogue_execution
            .audit_existing_completion(
                repo=root,
                production_root=production,
                stage1_root=stage1,
                sequence_plan_record=(
                    sequence_plan_record
                ),
                fresh_target_manifest=(
                    fresh_targets
                ),
                execution_commit=commit,
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleExecutionError(
            "current sequence-acquisition completion audit failed"
        ) from exc

    if (
        acquisition.release_id
        != metadata.release_id
        or acquisition.source_snapshot_id
        != metadata.source_snapshot_id
    ):
        raise MonthlyBioSampleExecutionError(
            "acquisition and metadata identities differ"
        )

    catalogue_path = _require_regular_file(
        stage1
        / stage4_execution.CATALOGUE_NAME,
        label="current sequence-cache catalogue",
    )

    try:
        chain = (
            catalogue_execution
            .discover_catalogue_chain(
                production,
                current_release_id=(
                    metadata.release_id
                ),
                include_current=True,
                current_catalogue_path=(
                    catalogue_path
                ),
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleExecutionError(
            "sequence-cache catalogue-chain audit failed"
        ) from exc

    if not chain:
        raise MonthlyBioSampleExecutionError(
            "current catalogue chain is empty"
        )

    current_catalogue = chain[
        -1
    ]

    if (
        current_catalogue.release_id
        != metadata.release_id
        or current_catalogue.origin_git_commit
        != commit
        or current_catalogue.catalogue_path.resolve()
        != catalogue_path.resolve()
    ):
        raise MonthlyBioSampleExecutionError(
            "current catalogue identity differs from monthly execution"
        )

    try:
        chain_signature = (
            catalogue_execution.chain_signature(
                chain
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleExecutionError(
            "catalogue-chain signature failed"
        ) from exc

    try:
        chain_sha = (
            stage4_execution
            .catalogue_chain_sha256(
                chain
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleExecutionError(
            "catalogue-chain SHA256 failed"
        ) from exc

    catalogue_record = (
        current_catalogue.catalogue_record
    )

    entries = (
        stage4_execution
        ._catalogue_entries_by_accession(
            catalogue_record
        )
    )

    provenance = (
        stage4_execution
        ._catalogue_provenance_by_sha(
            catalogue_record
        )
    )

    stage = _require_real_directory(
        stage1
        / stage4_execution.SOURCE_TRUTH_STAGE_NAME,
        label="monthly source-truth stage",
    )

    _require_exact_inventory(
        stage,
        expected_files={
            stage4_execution.DECISIONS_NAME,
            stage4_execution.RELATIONS_NAME,
            stage4_execution.RECORD_NAME,
        },
        label="monthly source-truth stage",
    )

    decisions = (
        stage
        / stage4_execution.DECISIONS_NAME
    ).read_bytes()

    relations = (
        stage
        / stage4_execution.RELATIONS_NAME
    ).read_bytes()

    record = (
        stage
        / stage4_execution.RECORD_NAME
    ).read_bytes()

    completion = _require_regular_file(
        stage1
        / stage4_execution.COMPLETION_NAME,
        label="source-truth completion receipt",
    ).read_bytes()

    try:
        decision_rows = (
            monthly_source_truth
            .audit_monthly_source_truth_decisions(
                decisions
            )
        )

        relation_rows = (
            monthly_source_truth
            .audit_monthly_source_truth_relations(
                relations
            )
        )

        monthly_source_truth.audit_monthly_source_truth_record(
            record,
            catalogue_payload=(
                current_catalogue.catalogue_payload
            ),
            current_metadata=(
                metadata.retained_metadata
            ),
            release_id=(
                metadata.release_id
            ),
            source_snapshot_id=(
                metadata.source_snapshot_id
            ),
            origin_git_commit=commit,
            metadata_record_sha256=(
                metadata.metadata_record_sha256
            ),
            metadata_completion_sha256=(
                metadata.metadata_completion_sha256
            ),
            decisions_payload=decisions,
            relations_payload=relations,
        )
    except Exception as exc:
        raise MonthlyBioSampleExecutionError(
            "completed monthly source-truth scientific audit failed"
        ) from exc

    decision_accessions = tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in decision_rows
    )

    retained_accessions = tuple(
        sorted(
            metadata.retained_metadata
        )
    )

    decision_set = set(
        decision_accessions
    )

    ineligible_accessions = tuple(
        accession
        for accession in retained_accessions
        if accession not in decision_set
    )

    if not decision_set.issubset(
        metadata.retained_metadata
    ):
        raise MonthlyBioSampleExecutionError(
            "source-truth decisions contain accession outside retained metadata"
        )

    decision_sha = hashlib.sha256(
        decisions
    ).hexdigest()

    relations_sha = hashlib.sha256(
        relations
    ).hexdigest()

    record_sha = hashlib.sha256(
        record
    ).hexdigest()

    try:
        completion_record = (
            stage4_execution
            .audit_completion_receipt(
                completion,
                release_id=(
                    metadata.release_id
                ),
                source_snapshot_id=(
                    metadata.source_snapshot_id
                ),
                source_snapshot_record_sha256=(
                    metadata.source_snapshot_record_sha256
                ),
                execution_commit=commit,
                metadata_record_sha256=(
                    metadata.metadata_record_sha256
                ),
                metadata_completion_sha256=(
                    metadata.metadata_completion_sha256
                ),
                catalogue_chain_count=len(
                    chain
                ),
                catalogue_chain_sha256_value=(
                    chain_sha
                ),
                sequence_cache_catalogue_sha256=(
                    current_catalogue.catalogue_sha256
                ),
                sequence_cache_entries_sha256=(
                    catalogue_record[
                        "entries_sha256"
                    ]
                ),
                retained_count=len(
                    retained_accessions
                ),
                sequence_eligible_count=len(
                    decision_accessions
                ),
                sequence_ineligible_count=len(
                    ineligible_accessions
                ),
                retained_accessions_sha256=(
                    accession_membership_sha256(
                        retained_accessions
                    )
                ),
                sequence_eligible_accessions_sha256=(
                    accession_membership_sha256(
                        decision_accessions
                    )
                ),
                sequence_ineligible_accessions_sha256=(
                    accession_membership_sha256(
                        ineligible_accessions
                    )
                ),
                decision_count=len(
                    decision_rows
                ),
                relation_count=len(
                    relation_rows
                ),
                decisions_sha256=(
                    decision_sha
                ),
                relations_sha256=(
                    relations_sha
                ),
                record_sha256=(
                    record_sha
                ),
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleExecutionError(
            "source-truth completion receipt audit failed"
        ) from exc

    if (
        completion_record.get(
            "decisions_sha256"
        )
        != decision_sha
    ):
        raise MonthlyBioSampleExecutionError(
            "authenticated source-truth decision SHA changed"
        )

    decision_by_accession = {
        row[
            "canonical_genbank_assembly_accession"
        ]:
            row
        for row in decision_rows
    }

    if len(
        decision_by_accession
    ) != len(
        decision_rows
    ):
        raise MonthlyBioSampleExecutionError(
            "duplicate source-truth decision accession"
        )

    return Stage4Context(
        release_id=(
            metadata.release_id
        ),
        source_snapshot_id=(
            metadata.source_snapshot_id
        ),
        execution_commit=commit,
        metadata_context=metadata,
        completion_context=acquisition,
        catalogue_chain=tuple(
            chain
        ),
        catalogue_chain_signature=tuple(
            chain_signature
        ),
        catalogue_chain_sha256=(
            chain_sha
        ),
        catalogue_record=(
            catalogue_record
        ),
        catalogue_payload=(
            current_catalogue.catalogue_payload
        ),
        catalogue_sha256=(
            current_catalogue.catalogue_sha256
        ),
        entries_by_accession=entries,
        provenance_by_sha=provenance,
        decisions_payload=decisions,
        decision_rows=tuple(
            decision_rows
        ),
        decision_by_accession=(
            decision_by_accession
        ),
        relations_payload=relations,
        record_payload=record,
        completion_payload=completion,
        completion_record=(
            completion_record
        ),
    )


def _materialize_prior_fasta(
    *,
    cache_execution,
    authoritative_root: Path,
    materialization_root: Path,
    bridge,
) -> tuple[
    Path,
    AuthoritativeObservation,
]:
    required = (
        cache_execution
        .read_required_object(
            authoritative_root,
            sha256=(
                bridge.fasta_sha256
            ),
            expected_size_bytes=(
                bridge.fasta_size_bytes
            ),
            label=(
                f"{bridge.accession} authoritative FASTA"
            ),
        )
    )

    relative = PurePosixPath(
        bridge.fasta_package_path
    )

    if (
        relative.is_absolute()
        or ".." in relative.parts
    ):
        raise MonthlyBioSampleExecutionError(
            "candidate FASTA package path is unsafe"
        )

    candidate_root = (
        materialization_root
        / bridge.accession
    )

    if os.path.lexists(
        candidate_root
    ):
        raise MonthlyBioSampleExecutionError(
            "candidate materialization path already exists"
        )

    package_root = (
        candidate_root
        / "package"
    )

    destination = (
        package_root
        / Path(
            *relative.parts
        )
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_no_clobber(
        destination,
        required.payload,
    )

    if (
        sha256_file(
            destination
        )
        != bridge.fasta_sha256
        or destination.stat().st_size
        != bridge.fasta_size_bytes
    ):
        raise MonthlyBioSampleExecutionError(
            "materialized FASTA identity changed"
        )

    return (
        candidate_root,
        AuthoritativeObservation(
            sha256=(
                bridge.fasta_sha256
            ),
            size_bytes=(
                bridge.fasta_size_bytes
            ),
        ),
    )


def fingerprint_population(
    *,
    context: Stage4Context,
    stage1_root: Path,
    authoritative_root: Path,
    materialization_root: Path,
    population,
    stage4_execution,
    cache_execution,
    catalogue_execution,
) -> tuple[
    tuple[
        VerifiedBioSampleFingerprint,
        ...
    ],
    tuple[
        FileObservation,
        ...
    ],
    tuple[
        AuthoritativeObservation,
        ...
    ],
    tuple[
        CurrentBatchObservation,
        ...
    ],
    tuple[
        PriorBatchObservation,
        ...
    ],
]:
    fingerprints = []
    local_observations = []
    authoritative_observations = []
    current_batch_observations = []
    prior_batch_observations = []

    current_batches = {}
    prior_batches = {}

    sequence_root_name = getattr(
        catalogue_execution,
        "SEQUENCE_ROOT_NAME",
        "sequence-acquisition",
    )

    for accession in (
        population.suitable_accessions
    ):
        entry = (
            context.entries_by_accession.get(
                accession
            )
        )

        if entry is None:
            raise MonthlyBioSampleExecutionError(
                "Stage 5 candidate lacks current catalogue entry"
            )

        provenance_sha = validate_sha256(
            entry.get(
                "origin_batch_provenance_sha256"
            ),
            label="origin batch-provenance SHA256",
        )

        provenance = (
            context.provenance_by_sha.get(
                provenance_sha
            )
        )

        if provenance is None:
            raise MonthlyBioSampleExecutionError(
                "Stage 5 candidate provenance is missing"
            )

        origin_class = classify_origin_release(
            provenance.get(
                "cache_origin_release_id"
            ),
            current_release_id=(
                context.release_id
            ),
        )

        if origin_class == "CURRENT":
            if provenance_sha not in current_batches:
                try:
                    current_batches[
                        provenance_sha
                    ] = (
                        stage4_execution
                        ._current_batch_evidence(
                            cache_execution=(
                                cache_execution
                            ),
                            completion_context=(
                                context.completion_context
                            ),
                            provenance=provenance,
                            expected_commit=(
                                context.execution_commit
                            ),
                        )
                    )

                    current_batch_observations.append(
                        CurrentBatchObservation(
                            provenance=provenance,
                            batch=(
                                current_batches[
                                    provenance_sha
                                ]
                            ),
                        )
                    )
                except Exception as exc:
                    raise MonthlyBioSampleExecutionError(
                        "current-origin batch evidence audit failed"
                    ) from exc

            batch = current_batches[
                provenance_sha
            ]
        else:
            if provenance_sha not in prior_batches:
                try:
                    prior_batches[
                        provenance_sha
                    ] = (
                        cache_execution
                        .load_batch_evidence(
                            authoritative_root,
                            provenance=provenance,
                        )
                    )

                    prior_batch_observations.append(
                        PriorBatchObservation(
                            provenance=provenance,
                            batch=(
                                prior_batches[
                                    provenance_sha
                                ]
                            ),
                        )
                    )
                except Exception as exc:
                    raise MonthlyBioSampleExecutionError(
                        "prior-origin batch evidence audit failed"
                    ) from exc

            batch = prior_batches[
                provenance_sha
            ]

        try:
            bridge = (
                stage4_execution
                .validate_candidate_bridge(
                    cache_execution,
                    entry=entry,
                    batch=batch,
                )
            )
        except Exception as exc:
            raise MonthlyBioSampleExecutionError(
                f"{accession} candidate bridge audit failed"
            ) from exc

        if (
            bridge.accession
            != accession
            or bridge.biosample
            != population.biosample_by_accession[
                accession
            ]
        ):
            raise MonthlyBioSampleExecutionError(
                "candidate bridge identity differs from Stage 5 population"
            )

        source_row = (
            context.decision_by_accession.get(
                accession
            )
        )

        if (
            source_row is None
            or source_row[
                "source_truth_status"
            ]
            != source_truth.SUITABLE
        ):
            raise MonthlyBioSampleExecutionError(
                "Stage 5 candidate is not Stage 4 SUITABLE"
            )

        candidate_root = None

        try:
            if origin_class == "CURRENT":
                batch_id = str(
                    provenance.get(
                        "batch_id",
                        "",
                    )
                )

                batch_dir = (
                    Path(
                        stage1_root
                    )
                    / sequence_root_name
                    / batch_id
                )

                _require_real_directory(
                    batch_dir,
                    label=(
                        f"current sequence batch {batch_id}"
                    ),
                )

                try:
                    fasta_path = (
                        resolve_manifest_path(
                            batch_dir,
                            bridge.fasta_package_path,
                        )
                    )
                except Exception as exc:
                    raise MonthlyBioSampleExecutionError(
                        f"{accession} current FASTA resolution failed"
                    ) from exc

                fasta_file = _require_regular_file(
                    fasta_path,
                    label=(
                        f"{accession} current FASTA"
                    ),
                )

                if (
                    sha256_file(
                        fasta_file
                    )
                    != bridge.fasta_sha256
                    or fasta_file.stat().st_size
                    != bridge.fasta_size_bytes
                ):
                    raise MonthlyBioSampleExecutionError(
                        "current FASTA identity differs from authenticated audit"
                    )

                audit_root = (
                    batch_dir
                )

                local_observations.append(
                    FileObservation(
                        path=fasta_file,
                        sha256=(
                            bridge.fasta_sha256
                        ),
                        size_bytes=(
                            bridge.fasta_size_bytes
                        ),
                    )
                )
            else:
                (
                    candidate_root,
                    authoritative_observation,
                ) = _materialize_prior_fasta(
                    cache_execution=(
                        cache_execution
                    ),
                    authoritative_root=(
                        authoritative_root
                    ),
                    materialization_root=(
                        materialization_root
                    ),
                    bridge=bridge,
                )

                audit_root = (
                    candidate_root
                )

                authoritative_observations.append(
                    authoritative_observation
                )

            try:
                (
                    candidate,
                    components,
                    package_manifest,
                ) = (
                    stage4_execution
                    ._source_truth_objects(
                        bridge,
                        audit_path=(
                            audit_root
                        ),
                    )
                )
            except Exception as exc:
                raise MonthlyBioSampleExecutionError(
                    f"{accession} source-evidence bridge failed"
                ) from exc

            try:
                verified = (
                    fingerprint_stage2_candidate(
                        candidate=candidate,
                        component_rows=components,
                        package_manifest=(
                            package_manifest
                        ),
                        expected_source_evidence_sha256=(
                            source_row[
                                "source_evidence_sha256"
                            ]
                        ),
                        biosample=(
                            population
                            .biosample_by_accession[
                                accession
                            ]
                        ),
                    )
                )
            except Exception as exc:
                raise MonthlyBioSampleExecutionError(
                    f"{accession} frozen fingerprint execution failed"
                ) from exc

            if verified.accession != accession:
                raise MonthlyBioSampleExecutionError(
                    "verified fingerprint accession changed"
                )

            fingerprints.append(
                verified
            )

        finally:
            if candidate_root is not None:
                if (
                    candidate_root.is_symlink()
                    or not candidate_root.is_dir()
                ):
                    raise MonthlyBioSampleExecutionError(
                        "candidate materialization path became unsafe"
                    )

                shutil.rmtree(
                    candidate_root
                )

    if tuple(
        value.accession
        for value in fingerprints
    ) != population.suitable_accessions:
        raise MonthlyBioSampleExecutionError(
            "verified fingerprint membership differs from Stage 5 population"
        )

    return (
        tuple(
            fingerprints
        ),
        tuple(
            local_observations
        ),
        tuple(
            authoritative_observations
        ),
        tuple(
            current_batch_observations
        ),
        tuple(
            prior_batch_observations
        ),
    )


def verify_observations(
    *,
    stage4_execution,
    cache_execution,
    current_completion_context,
    execution_commit: str,
    authoritative_root: Path,
    local_observations: Sequence[
        FileObservation
    ],
    authoritative_observations: Sequence[
        AuthoritativeObservation
    ],
    current_batch_observations: Sequence[
        CurrentBatchObservation
    ],
    prior_batch_observations: Sequence[
        PriorBatchObservation
    ],
) -> None:
    for observation in local_observations:
        path = _require_regular_file(
            observation.path,
            label="observed current FASTA",
        )

        if (
            path.stat().st_size
            != observation.size_bytes
            or sha256_file(
                path
            )
            != observation.sha256
        ):
            raise MonthlyBioSampleExecutionError(
                "current FASTA changed during Stage 5 execution"
            )

    for observation in authoritative_observations:
        try:
            cache_execution.read_required_object(
                authoritative_root,
                sha256=(
                    observation.sha256
                ),
                expected_size_bytes=(
                    observation.size_bytes
                ),
                label="observed authoritative FASTA",
            )
        except Exception as exc:
            raise MonthlyBioSampleExecutionError(
                "authoritative FASTA changed during Stage 5 execution"
            ) from exc

    for observation in current_batch_observations:
        try:
            observed = (
                stage4_execution
                ._current_batch_evidence(
                    cache_execution=(
                        cache_execution
                    ),
                    completion_context=(
                        current_completion_context
                    ),
                    provenance=(
                        observation.provenance
                    ),
                    expected_commit=(
                        execution_commit
                    ),
                )
            )
        except Exception as exc:
            raise MonthlyBioSampleExecutionError(
                "current batch evidence changed during Stage 5 execution"
            ) from exc

        expected = (
            observation.batch
        )

        if (
            observed.provenance
            != expected.provenance
            or observed.candidate_rows
            != expected.candidate_rows
            or observed.component_rows
            != expected.component_rows
            or observed.package_rows
            != expected.package_rows
        ):
            raise MonthlyBioSampleExecutionError(
                "current batch evidence changed during Stage 5 execution"
            )

    for observation in prior_batch_observations:
        try:
            observed = (
                cache_execution
                .load_batch_evidence(
                    authoritative_root,
                    provenance=(
                        observation.provenance
                    ),
                )
            )
        except Exception as exc:
            raise MonthlyBioSampleExecutionError(
                "historical batch evidence changed during Stage 5 execution"
            ) from exc

        expected = (
            observation.batch
        )

        if (
            observed.provenance
            != expected.provenance
            or observed.candidate_rows
            != expected.candidate_rows
            or observed.component_rows
            != expected.component_rows
            or observed.package_rows
            != expected.package_rows
        ):
            raise MonthlyBioSampleExecutionError(
                "historical batch evidence changed during Stage 5 execution"
            )


def read_exact_scientific_stage(
    stage: Path,
) -> tuple[
    bytes,
    bytes,
]:
    _require_exact_inventory(
        stage,
        expected_files={
            DECISIONS_NAME,
            RECORD_NAME,
        },
        label="monthly BioSample stage",
    )

    return (
        (
            stage
            / DECISIONS_NAME
        ).read_bytes(),
        (
            stage
            / RECORD_NAME
        ).read_bytes(),
    )


def publish_stage(
    *,
    stage1_root: Path,
    partial: Path,
    final: Path,
    expected_decisions: bytes,
    expected_record: bytes,
    auditor: Callable[
        [bytes, bytes],
        object,
    ],
    stability_check: Callable[
        [],
        None,
    ],
) -> None:
    if os.path.lexists(
        final
    ):
        raise MonthlyBioSampleExecutionError(
            "canonical BioSample stage already exists"
        )

    (
        partial_decisions,
        partial_record,
    ) = read_exact_scientific_stage(
        partial
    )

    if (
        partial_decisions
        != expected_decisions
        or partial_record
        != expected_record
    ):
        raise MonthlyBioSampleExecutionError(
            "partial BioSample stage changed"
        )

    auditor(
        partial_decisions,
        partial_record,
    )

    stability_check()

    try:
        final.mkdir(
            mode=0o755,
            exist_ok=False,
        )

        os.link(
            partial
            / DECISIONS_NAME,
            final
            / DECISIONS_NAME,
            follow_symlinks=False,
        )

        os.link(
            partial
            / RECORD_NAME,
            final
            / RECORD_NAME,
            follow_symlinks=False,
        )

        fsync_directory(
            final
        )

        fsync_directory(
            stage1_root
        )

        (
            final_decisions,
            final_record,
        ) = read_exact_scientific_stage(
            final
        )

        if (
            final_decisions
            != expected_decisions
            or final_record
            != expected_record
        ):
            raise MonthlyBioSampleExecutionError(
                "published BioSample stage changed"
            )

        auditor(
            final_decisions,
            final_record,
        )

        stability_check()

    except Exception:
        if (
            final.exists()
            and not final.is_symlink()
            and final.is_dir()
        ):
            shutil.rmtree(
                final
            )

            fsync_directory(
                stage1_root
            )

        raise

    shutil.rmtree(
        partial
    )

    fsync_directory(
        stage1_root
    )


def build_completion_receipt(
    *,
    release_id: str,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    execution_commit: str,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
    catalogue_chain_count: int,
    catalogue_chain_sha256_value: str,
    sequence_cache_catalogue_sha256: str,
    sequence_cache_entries_sha256: str,
    source_truth_completion_sha256: str,
    source_truth_decisions_sha256: str,
    source_truth_record_sha256: str,
    suitable_count: int,
    suitable_accessions_sha256: str,
    decision_count: int,
    continue_count: int,
    nonrepresentative_count: int,
    unresolved_count: int,
    group_count: int,
    singleton_group_count: int,
    repeated_group_count: int,
    identical_repeated_group_count: int,
    differing_repeated_group_count: int,
    decisions_sha256: str,
    record_sha256: str,
) -> bytes:
    counts = {
        "catalogue_chain_count":
            validate_count(
                catalogue_chain_count,
                label="catalogue-chain count",
            ),
        "suitable_count":
            validate_count(
                suitable_count,
                label="suitable count",
            ),
        "decision_count":
            validate_count(
                decision_count,
                label="decision count",
            ),
        "continue_count":
            validate_count(
                continue_count,
                label="continue count",
            ),
        "nonrepresentative_count":
            validate_count(
                nonrepresentative_count,
                label="nonrepresentative count",
            ),
        "unresolved_count":
            validate_count(
                unresolved_count,
                label="unresolved count",
            ),
        "group_count":
            validate_count(
                group_count,
                label="group count",
            ),
        "singleton_group_count":
            validate_count(
                singleton_group_count,
                label="singleton-group count",
            ),
        "repeated_group_count":
            validate_count(
                repeated_group_count,
                label="repeated-group count",
            ),
        "identical_repeated_group_count":
            validate_count(
                identical_repeated_group_count,
                label="identical repeated-group count",
            ),
        "differing_repeated_group_count":
            validate_count(
                differing_repeated_group_count,
                label="differing repeated-group count",
            ),
    }

    if counts[
        "catalogue_chain_count"
    ] == 0:
        raise MonthlyBioSampleExecutionError(
            "catalogue-chain count must be positive"
        )

    if (
        counts[
            "decision_count"
        ]
        != counts[
            "suitable_count"
        ]
    ):
        raise MonthlyBioSampleExecutionError(
            "Stage 5 decision count differs from suitable count"
        )

    if (
        counts[
            "continue_count"
        ]
        + counts[
            "nonrepresentative_count"
        ]
        + counts[
            "unresolved_count"
        ]
        != counts[
            "decision_count"
        ]
    ):
        raise MonthlyBioSampleExecutionError(
            "Stage 5 decision accounting is inconsistent"
        )

    if (
        counts[
            "singleton_group_count"
        ]
        + counts[
            "repeated_group_count"
        ]
        != counts[
            "group_count"
        ]
    ):
        raise MonthlyBioSampleExecutionError(
            "Stage 5 group accounting is inconsistent"
        )

    if (
        counts[
            "identical_repeated_group_count"
        ]
        + counts[
            "differing_repeated_group_count"
        ]
        != counts[
            "repeated_group_count"
        ]
    ):
        raise MonthlyBioSampleExecutionError(
            "Stage 5 repeated-group accounting is inconsistent"
        )

    hashes = {
        "source_snapshot_record_sha256":
            source_snapshot_record_sha256,
        "metadata_record_sha256":
            metadata_record_sha256,
        "metadata_completion_sha256":
            metadata_completion_sha256,
        "catalogue_chain_sha256":
            catalogue_chain_sha256_value,
        "sequence_cache_catalogue_sha256":
            sequence_cache_catalogue_sha256,
        "sequence_cache_entries_sha256":
            sequence_cache_entries_sha256,
        "source_truth_completion_sha256":
            source_truth_completion_sha256,
        "source_truth_decisions_sha256":
            source_truth_decisions_sha256,
        "source_truth_record_sha256":
            source_truth_record_sha256,
        "suitable_accessions_sha256":
            suitable_accessions_sha256,
        "decisions_sha256":
            decisions_sha256,
        "record_sha256":
            record_sha256,
    }

    for label, value in hashes.items():
        validate_sha256(
            value,
            label=label.replace(
                "_",
                " ",
            ),
        )

    record = {
        **counts,
        **hashes,
        "execution_commit":
            validate_commit(
                execution_commit
            ),
        "monthly_biosample_reconciliation_sha256":
            EXPECTED_MONTHLY_BIOSAMPLE_SHA256,
        "source_fingerprint_sha256":
            EXPECTED_FINGERPRINT_SHA256,
        "source_post_sequence_eligibility_sha256":
            EXPECTED_POST_SEQUENCE_SHA256,
        "source_repeated_biosample_execution_sha256":
            EXPECTED_REPEATED_EXECUTION_SHA256,
        "source_snapshot_id":
            source_snapshot_id,
        "release_id":
            release_id,
        "schema_version":
            COMPLETION_SCHEMA,
        "status":
            COMPLETION_STATUS,
    }

    return _canonical_json_bytes(
        record
    )


def audit_completion_receipt(
    payload: bytes,
    **kwargs,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "BioSample completion receipt must be bytes"
        )

    expected = build_completion_receipt(
        **kwargs
    )

    if payload != expected:
        raise MonthlyBioSampleExecutionError(
            "BioSample completion receipt changed"
        )

    try:
        value = json.loads(
            payload.decode(
                "ascii"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlyBioSampleExecutionError(
            "invalid BioSample completion JSON"
        ) from exc

    if (
        value.get(
            "schema_version"
        )
        != COMPLETION_SCHEMA
        or value.get(
            "status"
        )
        != COMPLETION_STATUS
    ):
        raise MonthlyBioSampleExecutionError(
            "BioSample completion schema/status changed"
        )

    return value


def publish_completion(
    *,
    stage1_root: Path,
    payload: bytes,
    auditor: Callable[
        [bytes],
        object,
    ],
    stability_check: Callable[
        [],
        None,
    ],
) -> Path:
    final = (
        stage1_root
        / COMPLETION_NAME
    )

    temporary = (
        stage1_root
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlyBioSampleExecutionError(
            "BioSample completion receipt already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlyBioSampleExecutionError(
            "BioSample completion temporary artifact already exists"
        )

    write_no_clobber(
        temporary,
        payload,
    )

    auditor(
        temporary.read_bytes()
    )

    fsync_directory(
        stage1_root
    )

    stability_check()

    try:
        os.link(
            temporary,
            final,
            follow_symlinks=False,
        )

        fsync_directory(
            stage1_root
        )

        observed = _require_regular_file(
            final,
            label="BioSample completion receipt",
        ).read_bytes()

        if observed != payload:
            raise MonthlyBioSampleExecutionError(
                "BioSample completion readback changed"
            )

        auditor(
            observed
        )

        stability_check()

    except Exception:
        if os.path.lexists(
            final
        ):
            os.unlink(
                final
            )

            fsync_directory(
                stage1_root
            )

        raise

    os.unlink(
        temporary
    )

    fsync_directory(
        stage1_root
    )

    return final


def execute_monthly_biosample_reconciliation(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    authoritative_root: Path,
    execution_commit: str,
) -> MonthlyBioSampleExecutionResult:
    root = _require_real_directory(
        Path(
            repo
        ).resolve(),
        label="repository root",
    )

    production = _require_real_directory(
        Path(
            production_root
        ),
        label="production root",
    )

    stage1 = _require_real_directory(
        Path(
            stage1_root
        ),
        label="Stage 1 root",
    ).resolve()

    authoritative = _require_real_directory(
        Path(
            authoritative_root
        ),
        label="authoritative root",
    ).resolve()

    commit = validate_commit(
        execution_commit
    )

    stage4_execution = (
        load_frozen_stage4_execution(
            root
        )
    )

    cache_execution = (
        load_frozen_cache_execution(
            root
        )
    )

    catalogue_execution = (
        load_frozen_catalogue_execution(
            root
        )
    )

    context = load_stage4_context(
        repo=root,
        production_root=production,
        stage1_root=stage1,
        authoritative_root=authoritative,
        execution_commit=commit,
        stage4_execution=(
            stage4_execution
        ),
        cache_execution=(
            cache_execution
        ),
        catalogue_execution=(
            catalogue_execution
        ),
    )

    final = (
        stage1
        / STAGE_NAME
    )

    partial = (
        stage1
        / PARTIAL_NAME
    )

    materialization = (
        stage1
        / MATERIALIZATION_NAME
    )

    completion = (
        stage1
        / COMPLETION_NAME
    )

    completion_temp = (
        stage1
        / COMPLETION_TEMP_NAME
    )

    for path, label in (
        (
            final,
            "canonical BioSample stage",
        ),
        (
            partial,
            "partial BioSample stage",
        ),
        (
            materialization,
            "BioSample materialization",
        ),
        (
            completion,
            "BioSample completion receipt",
        ),
        (
            completion_temp,
            "BioSample completion temporary artifact",
        ),
    ):
        if os.path.lexists(
            path
        ):
            raise MonthlyBioSampleExecutionError(
                f"{label} already exists"
            )

    try:
        population = (
            monthly_biosample_reconciliation
            .build_monthly_biosample_population(
                context.decisions_payload,
                expected_source_truth_decisions_sha256=(
                    context.completion_record[
                        "decisions_sha256"
                    ]
                ),
                current_metadata=(
                    context
                    .metadata_context
                    .retained_metadata
                ),
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                origin_git_commit=commit,
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleExecutionError(
            "pure Stage 5 population construction failed"
        ) from exc

    materialization.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    try:
        (
            fingerprints,
            local_observations,
            authoritative_observations,
            current_batch_observations,
            prior_batch_observations,
        ) = fingerprint_population(
            context=context,
            stage1_root=stage1,
            authoritative_root=authoritative,
            materialization_root=materialization,
            population=population,
            stage4_execution=(
                stage4_execution
            ),
            cache_execution=(
                cache_execution
            ),
            catalogue_execution=(
                catalogue_execution
            ),
        )

        if any(
            materialization.iterdir()
        ):
            raise MonthlyBioSampleExecutionError(
                "Stage 5 materialization root is not empty"
            )

    finally:
        if (
            materialization.exists()
            and not materialization.is_symlink()
            and materialization.is_dir()
        ):
            shutil.rmtree(
                materialization
            )

    try:
        build = (
            monthly_biosample_reconciliation
            .build_monthly_biosample_reconciliation(
                population,
                fingerprints,
            )
        )

        decisions_payload = (
            monthly_biosample_reconciliation
            .serialize_monthly_biosample_decisions(
                build
            )
        )

        record_payload = (
            monthly_biosample_reconciliation
            .serialize_monthly_biosample_record(
                build,
                source_truth_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                source_truth_completion_sha256=(
                    hashlib.sha256(
                        context.completion_payload
                    ).hexdigest()
                ),
            )
        )

        monthly_biosample_reconciliation.audit_monthly_biosample_decisions(
            decisions_payload
        )

        record = (
            monthly_biosample_reconciliation
            .audit_monthly_biosample_record(
                record_payload,
                source_truth_decisions_payload=(
                    context.decisions_payload
                ),
                expected_source_truth_decisions_sha256=(
                    context.completion_record[
                        "decisions_sha256"
                    ]
                ),
                current_metadata=(
                    context
                    .metadata_context
                    .retained_metadata
                ),
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                origin_git_commit=commit,
                source_truth_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                source_truth_completion_sha256=(
                    hashlib.sha256(
                        context.completion_payload
                    ).hexdigest()
                ),
                decisions_payload=(
                    decisions_payload
                ),
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleExecutionError(
            "pure monthly Stage 5 contract failed"
        ) from exc

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    write_no_clobber(
        partial
        / DECISIONS_NAME,
        decisions_payload,
    )

    write_no_clobber(
        partial
        / RECORD_NAME,
        record_payload,
    )

    fsync_directory(
        partial
    )

    initial_stage4_identity = (
        _stage4_identity(
            context,
            cache_execution,
        )
    )

    def stability_check() -> None:
        observed = load_stage4_context(
            repo=root,
            production_root=production,
            stage1_root=stage1,
            authoritative_root=(
                authoritative
            ),
            execution_commit=commit,
            stage4_execution=(
                stage4_execution
            ),
            cache_execution=(
                cache_execution
            ),
            catalogue_execution=(
                catalogue_execution
            ),
        )

        if (
            _stage4_identity(
                observed,
                cache_execution,
            )
            != initial_stage4_identity
        ):
            raise MonthlyBioSampleExecutionError(
                "Stage 4 evidence changed during Stage 5 publication"
            )

        verify_observations(
            stage4_execution=(
                stage4_execution
            ),
            cache_execution=(
                cache_execution
            ),
            current_completion_context=(
                observed.completion_context
            ),
            execution_commit=commit,
            authoritative_root=(
                authoritative
            ),
            local_observations=(
                local_observations
            ),
            authoritative_observations=(
                authoritative_observations
            ),
            current_batch_observations=(
                current_batch_observations
            ),
            prior_batch_observations=(
                prior_batch_observations
            ),
        )

    def stage_auditor(
        observed_decisions: bytes,
        observed_record: bytes,
    ) -> object:
        monthly_biosample_reconciliation.audit_monthly_biosample_decisions(
            observed_decisions
        )

        return (
            monthly_biosample_reconciliation
            .audit_monthly_biosample_record(
                observed_record,
                source_truth_decisions_payload=(
                    context.decisions_payload
                ),
                expected_source_truth_decisions_sha256=(
                    context.completion_record[
                        "decisions_sha256"
                    ]
                ),
                current_metadata=(
                    context
                    .metadata_context
                    .retained_metadata
                ),
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                origin_git_commit=commit,
                source_truth_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                source_truth_completion_sha256=(
                    hashlib.sha256(
                        context.completion_payload
                    ).hexdigest()
                ),
                decisions_payload=(
                    observed_decisions
                ),
            )
        )

    publish_stage(
        stage1_root=stage1,
        partial=partial,
        final=final,
        expected_decisions=(
            decisions_payload
        ),
        expected_record=(
            record_payload
        ),
        auditor=stage_auditor,
        stability_check=(
            stability_check
        ),
    )

    status_counts = record[
        "decision_status_counts"
    ]

    if not isinstance(
        status_counts,
        dict,
    ):
        raise MonthlyBioSampleExecutionError(
            "Stage 5 status counts changed"
        )

    continue_count = int(
        status_counts.get(
            BIOSAMPLE_CONTINUE,
            0,
        )
    )

    nonrepresentative_count = int(
        status_counts.get(
            BIOSAMPLE_NONREPRESENTATIVE,
            0,
        )
    )

    unresolved_count = int(
        status_counts.get(
            BIOSAMPLE_UNRESOLVED,
            0,
        )
    )

    decisions_sha = hashlib.sha256(
        decisions_payload
    ).hexdigest()

    record_sha = hashlib.sha256(
        record_payload
    ).hexdigest()

    completion_payload = build_completion_receipt(
        release_id=(
            context.release_id
        ),
        source_snapshot_id=(
            context.source_snapshot_id
        ),
        source_snapshot_record_sha256=(
            context
            .metadata_context
            .source_snapshot_record_sha256
        ),
        execution_commit=commit,
        metadata_record_sha256=(
            context
            .metadata_context
            .metadata_record_sha256
        ),
        metadata_completion_sha256=(
            context
            .metadata_context
            .metadata_completion_sha256
        ),
        catalogue_chain_count=len(
            context.catalogue_chain
        ),
        catalogue_chain_sha256_value=(
            context.catalogue_chain_sha256
        ),
        sequence_cache_catalogue_sha256=(
            context.catalogue_sha256
        ),
        sequence_cache_entries_sha256=(
            context.catalogue_record[
                "entries_sha256"
            ]
        ),
        source_truth_completion_sha256=(
            hashlib.sha256(
                context.completion_payload
            ).hexdigest()
        ),
        source_truth_decisions_sha256=(
            hashlib.sha256(
                context.decisions_payload
            ).hexdigest()
        ),
        source_truth_record_sha256=(
            hashlib.sha256(
                context.record_payload
            ).hexdigest()
        ),
        suitable_count=len(
            population.suitable_accessions
        ),
        suitable_accessions_sha256=(
            population.suitable_accessions_sha256
        ),
        decision_count=len(
            build.decision_rows
        ),
        continue_count=(
            continue_count
        ),
        nonrepresentative_count=(
            nonrepresentative_count
        ),
        unresolved_count=(
            unresolved_count
        ),
        group_count=(
            build.group_count
        ),
        singleton_group_count=(
            build.singleton_group_count
        ),
        repeated_group_count=(
            build.repeated_group_count
        ),
        identical_repeated_group_count=(
            build.identical_repeated_group_count
        ),
        differing_repeated_group_count=(
            build.differing_repeated_group_count
        ),
        decisions_sha256=(
            decisions_sha
        ),
        record_sha256=(
            record_sha
        ),
    )

    completion_kwargs = {
        key:
            value
        for key, value in {
            "release_id":
                context.release_id,
            "source_snapshot_id":
                context.source_snapshot_id,
            "source_snapshot_record_sha256":
                context
                .metadata_context
                .source_snapshot_record_sha256,
            "execution_commit":
                commit,
            "metadata_record_sha256":
                context
                .metadata_context
                .metadata_record_sha256,
            "metadata_completion_sha256":
                context
                .metadata_context
                .metadata_completion_sha256,
            "catalogue_chain_count":
                len(
                    context.catalogue_chain
                ),
            "catalogue_chain_sha256_value":
                context.catalogue_chain_sha256,
            "sequence_cache_catalogue_sha256":
                context.catalogue_sha256,
            "sequence_cache_entries_sha256":
                context.catalogue_record[
                    "entries_sha256"
                ],
            "source_truth_completion_sha256":
                hashlib.sha256(
                    context.completion_payload
                ).hexdigest(),
            "source_truth_decisions_sha256":
                hashlib.sha256(
                    context.decisions_payload
                ).hexdigest(),
            "source_truth_record_sha256":
                hashlib.sha256(
                    context.record_payload
                ).hexdigest(),
            "suitable_count":
                len(
                    population.suitable_accessions
                ),
            "suitable_accessions_sha256":
                population.suitable_accessions_sha256,
            "decision_count":
                len(
                    build.decision_rows
                ),
            "continue_count":
                continue_count,
            "nonrepresentative_count":
                nonrepresentative_count,
            "unresolved_count":
                unresolved_count,
            "group_count":
                build.group_count,
            "singleton_group_count":
                build.singleton_group_count,
            "repeated_group_count":
                build.repeated_group_count,
            "identical_repeated_group_count":
                build.identical_repeated_group_count,
            "differing_repeated_group_count":
                build.differing_repeated_group_count,
            "decisions_sha256":
                decisions_sha,
            "record_sha256":
                record_sha,
        }.items()
    }

    completion_path = publish_completion(
        stage1_root=stage1,
        payload=completion_payload,
        auditor=lambda payload:
            audit_completion_receipt(
                payload,
                **completion_kwargs,
            ),
        stability_check=(
            stability_check
        ),
    )

    return MonthlyBioSampleExecutionResult(
        release_id=(
            context.release_id
        ),
        source_snapshot_id=(
            context.source_snapshot_id
        ),
        stage_path=final,
        decisions_sha256=(
            decisions_sha
        ),
        record_sha256=(
            record_sha
        ),
        completion_path=(
            completion_path
        ),
        suitable_count=len(
            population.suitable_accessions
        ),
        continue_count=(
            continue_count
        ),
        nonrepresentative_count=(
            nonrepresentative_count
        ),
        unresolved_count=(
            unresolved_count
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute portable monthly BacSelect "
            "repeated-BioSample reconciliation."
        )
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
        "--production-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--stage1-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--authoritative-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.authorize_real_execution:
        raise SystemExit(
            "real monthly Stage 5 execution requires "
            "--authorize-real-execution"
        )

    repo = Path(
        __file__
    ).resolve().parents[
        2
    ]

    repository_preflight(
        repo,
        expected_commit=(
            args.expected_commit
        ),
        expected_wrapper_sha256=(
            args.expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            args.expected_wrapper_test_sha256
        ),
    )

    result = execute_monthly_biosample_reconciliation(
        repo=repo,
        production_root=(
            args.production_root
        ),
        stage1_root=(
            args.stage1_root
        ),
        authoritative_root=(
            args.authoritative_root
        ),
        execution_commit=(
            args.expected_commit
        ),
    )

    print(
        f"release_id={result.release_id}"
    )
    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )
    print(
        f"stage_path={result.stage_path}"
    )
    print(
        f"suitable_count={result.suitable_count}"
    )
    print(
        f"continue_count={result.continue_count}"
    )
    print(
        "nonrepresentative_count="
        f"{result.nonrepresentative_count}"
    )
    print(
        f"unresolved_count={result.unresolved_count}"
    )
    print(
        f"decisions_sha256={result.decisions_sha256}"
    )
    print(
        f"record_sha256={result.record_sha256}"
    )
    print(
        f"completion_path={result.completion_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
