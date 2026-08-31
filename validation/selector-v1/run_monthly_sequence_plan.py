#!/usr/bin/env python3
"""Execute BacSelect monthly Stage 2 sequence planning."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import (
    Callable,
    Mapping,
    Sequence,
)

from bacselect import (
    monthly_cache_verification as cache_contract,
)
from bacselect import (
    monthly_metadata_eligibility as metadata_contract,
)
from bacselect import (
    monthly_sequence_plan as plan_contract,
)


SEQUENCE_PLAN_CORE_RELATIVE = Path(
    "src/bacselect/monthly_sequence_plan.py"
)

SEQUENCE_PLAN_CORE_TEST_RELATIVE = Path(
    "tests/test_monthly_sequence_plan.py"
)

CACHE_CORE_RELATIVE = Path(
    "src/bacselect/monthly_cache_verification.py"
)

CACHE_CORE_TEST_RELATIVE = Path(
    "tests/test_monthly_cache_verification.py"
)

CACHE_EXECUTOR_RELATIVE = Path(
    "validation/selector-v1/run_monthly_cache_verification.py"
)

CACHE_EXECUTOR_TEST_RELATIVE = Path(
    "tests/test_run_monthly_cache_verification.py"
)

CACHE_EXECUTION_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-cache-verification-execution.md"
)

METADATA_CORE_RELATIVE = Path(
    "src/bacselect/monthly_metadata_eligibility.py"
)

METADATA_CORE_TEST_RELATIVE = Path(
    "tests/test_monthly_metadata_eligibility.py"
)

EXECUTION_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-sequence-plan-execution.md"
)

WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_monthly_sequence_plan.py"
)


EXPECTED_SEQUENCE_PLAN_CORE_SHA256 = (
    "e2213fee3703580b0e96fd280a050765812d0a369eff34846d8d1b958dae9e18"
)

EXPECTED_SEQUENCE_PLAN_CORE_TEST_SHA256 = (
    "b273ef4d482dccd0cddbe438bd8896da6f01034b86fd0c6c6cc96927df65e25b"
)

EXPECTED_CACHE_CORE_SHA256 = (
    "4a2ba0c142663a933ee0df25d69f82fdeb3b6a694154ceafbd3e2e9103b3ef7c"
)

EXPECTED_CACHE_CORE_TEST_SHA256 = (
    "fca5c5609473da5f4e0e7d5039f4c5ae3586e5820cc53592e67fa3914c3d4c2a"
)

EXPECTED_CACHE_EXECUTOR_SHA256 = (
    "0a45ee60f06e102afba93cdc08f588f9bc547f7103279e59ffd4362cb5526c3e"
)

EXPECTED_CACHE_EXECUTOR_TEST_SHA256 = (
    "5e6341f3371d5c789b23a493ba16d4736965e897f4dddc430d3a98ce02593c25"
)

EXPECTED_CACHE_EXECUTION_METHOD_SHA256 = (
    "36a61a09c3bbdd931023dedbc0578b211d4d6b70dae020eee80a47e726c633bd"
)

EXPECTED_METADATA_CORE_SHA256 = (
    "90c86d304d42c3e7dc4978a28d1d01a92660d9a359e07516f536ff3a0a2df87f"
)

EXPECTED_METADATA_CORE_TEST_SHA256 = (
    "e50bb48c73e98a619a0d2a180a71d74b295acd9d5d5b3f18e6641a47fa8e6c1e"
)

EXPECTED_EXECUTION_METHOD_SHA256 = (
    "052beb4a621e2236e9aaa2558b7c7e2936b481e975ad37865c17e12cb91c7544"
)


SEQUENCE_PLAN_STAGE_NAME = (
    "sequence-plan"
)

SEQUENCE_PLAN_PARTIAL_STAGE_NAME = (
    "sequence-plan.partial"
)

FRESH_TARGETS_NAME = (
    "fresh-targets.tsv"
)

PLAN_RECORD_NAME = (
    "monthly-sequence-plan-record.json"
)

COMPLETION_NAME = (
    "sequence-plan-completion.json"
)

COMPLETION_TEMP_NAME = (
    ".sequence-plan-completion.json.tmp"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-sequence-plan-completion-v1"
)

COMPLETION_STATUS = (
    "SEQUENCE_PLAN_EXECUTION_COMPLETE"
)

METADATA_STAGE_NAME = (
    "metadata-eligibility"
)

METADATA_ASSESSMENTS_NAME = (
    "metadata-eligibility-assessments.jsonl"
)

CACHE_STAGE_NAME = (
    "cache-verification"
)

CACHE_COMPLETION_NAME = (
    "cache-verification-completion.json"
)


SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

RELEASE_RE = re.compile(
    r"^[0-9]{4}\.[0-9]{2}$"
)


class MonthlySequencePlanExecutionError(
    RuntimeError
):
    """Raised when monthly Stage 2 execution fails closed."""


@dataclass(frozen=True)
class SequencePlanInputs:
    metadata_context: object
    metadata_identity: tuple[
        object,
        ...,
    ]
    assessments_payload: bytes
    assessments: tuple[
        object,
        ...,
    ]
    cache_results_payload: bytes
    verified_cache_payload: bytes
    cache_record_payload: bytes
    cache_completion_payload: bytes
    verified_cache: tuple[
        plan_contract.VerifiedMonthlyCacheEvidence,
        ...,
    ]
    cache_record: Mapping[
        str,
        object,
    ]
    cache_completion: Mapping[
        str,
        object,
    ]
    catalogue_history_mode: str
    catalogue_chain_count: int
    catalogue_chain_sha256: str


@dataclass(frozen=True)
class SequencePlanPayloads:
    plan: plan_contract.MonthlySequencePlan
    fresh_target_manifest: bytes
    plan_record_payload: bytes
    plan_record: Mapping[
        str,
        object,
    ]


@dataclass(frozen=True)
class MonthlySequencePlanExecutionResult:
    release_id: str
    source_snapshot_id: str
    stage_root: Path
    completion_path: Path
    retained_count: int
    cache_reuse_count: int
    fresh_acquisition_count: int
    fresh_batch_count: int
    fresh_target_manifest_sha256: str
    sequence_plan_record_sha256: str
    completion_sha256: str


def sha256_bytes(
    payload: bytes,
) -> str:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "SHA256 payload must be bytes"
        )

    return hashlib.sha256(
        payload
    ).hexdigest()


def sha256_file(
    path: Path,
) -> str:
    return sha256_bytes(
        Path(
            path
        ).read_bytes()
    )


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
        raise MonthlySequencePlanExecutionError(
            f"{label} is not a lowercase SHA256"
        )

    return value


def validate_git_commit(
    value: object,
    *,
    label: str,
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
        raise MonthlySequencePlanExecutionError(
            f"{label} is not a 40-character Git commit"
        )

    return value


def validate_release_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or RELEASE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlySequencePlanExecutionError(
            "release ID is invalid"
        )

    return value


def canonical_json_bytes(
    value: object,
) -> bytes:
    try:
        payload = (
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
    except (
        TypeError,
        ValueError,
        UnicodeEncodeError,
    ) as exc:
        raise MonthlySequencePlanExecutionError(
            "execution evidence is not canonical-JSON serializable"
        ) from exc

    return payload


def default_git_reader(
    repo: Path,
    args: Sequence[
        str
    ],
) -> str:
    try:
        result = subprocess.run(
            (
                "git",
                "-C",
                str(
                    repo
                ),
                *args,
            ),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        raise MonthlySequencePlanExecutionError(
            "unable to inspect Git repository"
        ) from exc

    return result.stdout.strip()


def require_sha256(
    path: Path,
    expected: str,
    *,
    label: str,
    reader: Callable[
        [Path],
        str,
    ] = sha256_file,
) -> None:
    observed = reader(
        path
    )

    if observed != validate_sha256(
        expected,
        label=f"expected {label} SHA256",
    ):
        raise MonthlySequencePlanExecutionError(
            f"{label} SHA256 mismatch: {observed}"
        )


def repository_preflight(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    git_reader=None,
    file_sha256_reader: Callable[
        [Path],
        str,
    ] = sha256_file,
) -> None:
    root = Path(
        repo
    ).resolve()

    commit = validate_git_commit(
        expected_commit,
        label="expected execution commit",
    )

    reader = (
        default_git_reader
        if git_reader is None
        else git_reader
    )

    head = reader(
        root,
        (
            "rev-parse",
            "HEAD",
        ),
    )

    if head != commit:
        raise MonthlySequencePlanExecutionError(
            "repository HEAD differs from expected execution commit"
        )

    status = reader(
        root,
        (
            "status",
            "--short",
        ),
    )

    if status:
        raise MonthlySequencePlanExecutionError(
            "repository working tree is not clean"
        )

    fixed = (
        (
            SEQUENCE_PLAN_CORE_RELATIVE,
            EXPECTED_SEQUENCE_PLAN_CORE_SHA256,
            "monthly sequence-plan contract",
        ),
        (
            SEQUENCE_PLAN_CORE_TEST_RELATIVE,
            EXPECTED_SEQUENCE_PLAN_CORE_TEST_SHA256,
            "monthly sequence-plan contract test",
        ),
        (
            CACHE_CORE_RELATIVE,
            EXPECTED_CACHE_CORE_SHA256,
            "monthly cache-verification contract",
        ),
        (
            CACHE_CORE_TEST_RELATIVE,
            EXPECTED_CACHE_CORE_TEST_SHA256,
            "monthly cache-verification contract test",
        ),
        (
            CACHE_EXECUTOR_RELATIVE,
            EXPECTED_CACHE_EXECUTOR_SHA256,
            "monthly cache-verification executor",
        ),
        (
            CACHE_EXECUTOR_TEST_RELATIVE,
            EXPECTED_CACHE_EXECUTOR_TEST_SHA256,
            "monthly cache-verification executor test",
        ),
        (
            CACHE_EXECUTION_METHOD_RELATIVE,
            EXPECTED_CACHE_EXECUTION_METHOD_SHA256,
            "monthly cache-verification execution method",
        ),
        (
            METADATA_CORE_RELATIVE,
            EXPECTED_METADATA_CORE_SHA256,
            "monthly metadata-eligibility contract",
        ),
        (
            METADATA_CORE_TEST_RELATIVE,
            EXPECTED_METADATA_CORE_TEST_SHA256,
            "monthly metadata-eligibility contract test",
        ),
        (
            EXECUTION_METHOD_RELATIVE,
            EXPECTED_EXECUTION_METHOD_SHA256,
            "monthly sequence-plan execution method",
        ),
    )

    for relative, expected, label in fixed:
        require_sha256(
            root
            / relative,
            expected,
            label=label,
            reader=file_sha256_reader,
        )

    require_sha256(
        root
        / Path(
            __file__
        ).resolve().relative_to(
            root
        ),
        expected_wrapper_sha256,
        label="sequence-plan execution wrapper",
        reader=file_sha256_reader,
    )

    require_sha256(
        root
        / WRAPPER_TEST_RELATIVE,
        expected_wrapper_test_sha256,
        label="sequence-plan execution wrapper test",
        reader=file_sha256_reader,
    )


def load_frozen_cache_execution(
    repo: Path,
):
    root = Path(
        repo
    ).resolve()

    path = (
        root
        / CACHE_EXECUTOR_RELATIVE
    )

    require_sha256(
        path,
        EXPECTED_CACHE_EXECUTOR_SHA256,
        label="monthly cache-verification executor",
    )

    name = (
        "_bacselect_frozen_monthly_cache_verification_execution"
    )

    existing = sys.modules.get(
        name
    )

    if existing is not None:
        return existing

    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise MonthlySequencePlanExecutionError(
            "unable to load frozen cache-verification executor"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        name
    ] = module

    try:
        spec.loader.exec_module(
            module
        )
    except Exception as exc:
        sys.modules.pop(
            name,
            None,
        )

        raise MonthlySequencePlanExecutionError(
            "unable to import frozen cache-verification executor"
        ) from exc

    return module


def _require_regular_file(
    path: Path,
    *,
    label: str,
    expected_mode: int | None = None,
) -> Path:
    candidate = Path(
        path
    )

    try:
        observed = os.lstat(
            candidate
        )
    except OSError as exc:
        raise MonthlySequencePlanExecutionError(
            f"missing {label}: {candidate}"
        ) from exc

    if not stat.S_ISREG(
        observed.st_mode
    ):
        raise MonthlySequencePlanExecutionError(
            f"{label} is not a regular file: {candidate}"
        )

    if expected_mode is not None:
        mode = stat.S_IMODE(
            observed.st_mode
        )

        if mode != expected_mode:
            raise MonthlySequencePlanExecutionError(
                f"{label} mode changed: {oct(mode)}"
            )

    return candidate


def _require_exact_inventory(
    directory: Path,
    *,
    expected_files: set[
        str
    ],
    label: str,
) -> None:
    path = Path(
        directory
    )

    try:
        observed_stat = os.lstat(
            path
        )
    except OSError as exc:
        raise MonthlySequencePlanExecutionError(
            f"missing {label}: {path}"
        ) from exc

    if not stat.S_ISDIR(
        observed_stat.st_mode
    ):
        raise MonthlySequencePlanExecutionError(
            f"{label} is not a directory"
        )

    try:
        names = {
            item.name
            for item in path.iterdir()
        }
    except OSError as exc:
        raise MonthlySequencePlanExecutionError(
            f"unable to enumerate {label}"
        ) from exc

    if names != expected_files:
        raise MonthlySequencePlanExecutionError(
            f"{label} inventory changed"
        )


def _metadata_assessment_path(
    stage1_root: Path,
) -> Path:
    return (
        Path(
            stage1_root
        )
        / METADATA_STAGE_NAME
        / METADATA_ASSESSMENTS_NAME
    )


def _parse_json_object(
    payload: bytes,
    *,
    label: str,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            f"{label} must be bytes"
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
        raise MonthlySequencePlanExecutionError(
            f"invalid {label} JSON"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise MonthlySequencePlanExecutionError(
            f"{label} must be a JSON object"
        )

    return value


def derive_source_catalogue_provenance(
    chain: Sequence[
        object
    ],
    *,
    cache_execution,
) -> tuple[
    str,
    str | None,
    str | None,
    str | None,
    int,
]:
    values = tuple(
        chain
    )

    if not values:
        return (
            cache_execution.HISTORY_NONE,
            None,
            None,
            None,
            0,
        )

    source_item = values[
        -1
    ]

    source_record = getattr(
        source_item,
        "catalogue_record",
        None,
    )

    if not isinstance(
        source_record,
        Mapping,
    ):
        raise MonthlySequencePlanExecutionError(
            "latest source catalogue record is unavailable"
        )

    source_release = validate_release_id(
        getattr(
            source_item,
            "release_id",
            None,
        )
    )

    if source_record.get(
        "release_id"
    ) != source_release:
        raise MonthlySequencePlanExecutionError(
            "latest source catalogue release identity changed"
        )

    source_catalogue_sha = validate_sha256(
        getattr(
            source_item,
            "catalogue_sha256",
            None,
        ),
        label="latest source catalogue SHA256",
    )

    source_entries_sha = validate_sha256(
        source_record.get(
            "entries_sha256"
        ),
        label="latest source catalogue entries SHA256",
    )

    source_entry_count = source_record.get(
        "catalogue_entry_count"
    )

    if (
        isinstance(
            source_entry_count,
            bool,
        )
        or not isinstance(
            source_entry_count,
            int,
        )
        or source_entry_count < 0
    ):
        raise MonthlySequencePlanExecutionError(
            "latest source catalogue entry count is invalid"
        )

    return (
        cache_execution.HISTORY_CHAINED,
        source_release,
        source_catalogue_sha,
        source_entries_sha,
        source_entry_count,
    )


def load_sequence_plan_inputs(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    execution_commit: str,
    cache_execution=None,
) -> SequencePlanInputs:
    root = Path(
        repo
    ).resolve()

    production = Path(
        production_root
    )

    stage1 = Path(
        stage1_root
    )

    commit = validate_git_commit(
        execution_commit,
        label="execution commit",
    )

    cache_exec = (
        load_frozen_cache_execution(
            root
        )
        if cache_execution is None
        else cache_execution
    )

    try:
        metadata_context = (
            cache_exec.load_current_metadata_context(
                repo=root,
                production_root=production,
                stage1_root=stage1,
                execution_commit=commit,
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "current metadata context audit failed"
        ) from exc

    try:
        metadata_identity = tuple(
            cache_exec.metadata_context_identity(
                metadata_context
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "unable to derive metadata-context identity"
        ) from exc

    assessments_path = _require_regular_file(
        _metadata_assessment_path(
            metadata_context.stage1_root
        ),
        label="metadata assessments",
        expected_mode=0o644,
    )

    assessments_payload = (
        assessments_path.read_bytes()
    )

    try:
        assessments = tuple(
            metadata_contract.audit_metadata_assessments(
                assessments_payload
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "metadata assessments audit failed"
        ) from exc

    cache_stage = (
        Path(
            metadata_context.stage1_root
        )
        / CACHE_STAGE_NAME
    )

    try:
        (
            results_payload,
            verified_payload,
            record_payload,
        ) = (
            cache_exec._scientific_stage_payloads(
                cache_stage
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "completed cache-verification stage audit failed"
        ) from exc

    try:
        cache_contract.audit_cache_verification_results(
            results_payload
        )

        verified_cache = tuple(
            cache_contract.audit_verified_cache_evidence(
                verified_payload
            )
        )

        cache_record = (
            cache_contract.audit_cache_verification_record(
                record_payload,
                source_snapshot_id=(
                    metadata_context.source_snapshot_id
                ),
                source_snapshot_record_sha256=(
                    metadata_context.source_snapshot_record_sha256
                ),
                metadata_record_sha256=(
                    metadata_context.metadata_record_sha256
                ),
                metadata_completion_sha256=(
                    metadata_context.metadata_completion_sha256
                ),
                retained_count=len(
                    metadata_context.retained_metadata
                ),
                results_payload=(
                    results_payload
                ),
                verified_cache_payload=(
                    verified_payload
                ),
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "cache-verification scientific evidence audit failed"
        ) from exc

    completion_path = _require_regular_file(
        Path(
            metadata_context.stage1_root
        )
        / CACHE_COMPLETION_NAME,
        label="cache-verification completion",
        expected_mode=0o644,
    )

    completion_payload = (
        completion_path.read_bytes()
    )

    try:
        chain = tuple(
            cache_exec.discover_prior_catalogue_chain(
                repo=root,
                production_root=production,
                current_release_id=(
                    metadata_context.release_id
                ),
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "prior sequence-cache catalogue discovery failed"
        ) from exc

    if not chain:
        try:
            cache_exec.prove_no_prior_sequence_evidence(
                production,
                current_release_id=(
                    metadata_context.release_id
                ),
            )
        except Exception as exc:
            raise MonthlySequencePlanExecutionError(
                "first-release sequence-evidence proof failed"
            ) from exc

    try:
        (
            history_mode,
            source_catalogue_release_id,
            source_catalogue_sha256,
            source_catalogue_entries_sha256,
            source_catalogue_entry_count,
        ) = derive_source_catalogue_provenance(
            chain,
            cache_execution=(
                cache_exec
            ),
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "source catalogue provenance derivation failed"
        ) from exc

    try:
        chain_sha = (
            cache_exec.catalogue_chain_sha256(
                chain
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "unable to derive catalogue-chain identity"
        ) from exc

    results_sha = sha256_bytes(
        results_payload
    )

    verified_sha = sha256_bytes(
        verified_payload
    )

    record_sha = sha256_bytes(
        record_payload
    )

    try:
        cache_completion = (
            cache_exec.audit_completion_receipt(
                completion_payload,
                release_id=(
                    metadata_context.release_id
                ),
                source_snapshot_id=(
                    metadata_context.source_snapshot_id
                ),
                source_snapshot_record_sha256=(
                    metadata_context.source_snapshot_record_sha256
                ),
                execution_commit=commit,
                metadata_record_sha256=(
                    metadata_context.metadata_record_sha256
                ),
                metadata_completion_sha256=(
                    metadata_context.metadata_completion_sha256
                ),
                retained_count=len(
                    metadata_context.retained_metadata
                ),
                catalogue_history_mode=(
                    history_mode
                ),
                catalogue_chain_count=len(
                    chain
                ),
                catalogue_chain_sha256_value=(
                    chain_sha
                ),
                source_catalogue_release_id=(
                    source_catalogue_release_id
                ),
                source_catalogue_sha256=(
                    source_catalogue_sha256
                ),
                source_catalogue_entries_sha256=(
                    source_catalogue_entries_sha256
                ),
                source_catalogue_entry_count=(
                    source_catalogue_entry_count
                ),
                candidate_input_count=int(
                    cache_record[
                        "candidate_input_count"
                    ]
                ),
                verified_cache_count=int(
                    cache_record[
                        "verified_cache_count"
                    ]
                ),
                fallback_to_fresh_count=int(
                    cache_record[
                        "fallback_to_fresh_count"
                    ]
                ),
                results_sha256=(
                    results_sha
                ),
                verified_cache_evidence_sha256=(
                    verified_sha
                ),
                record_sha256=(
                    record_sha
                ),
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "cache-verification completion audit failed"
        ) from exc

    if cache_completion.get(
        "catalogue_history_mode"
    ) != history_mode:
        raise MonthlySequencePlanExecutionError(
            "cache completion catalogue-history mode changed"
        )

    if cache_completion.get(
        "catalogue_chain_count"
    ) != len(
        chain
    ):
        raise MonthlySequencePlanExecutionError(
            "cache completion catalogue-chain count changed"
        )

    if cache_completion.get(
        "catalogue_chain_sha256"
    ) != chain_sha:
        raise MonthlySequencePlanExecutionError(
            "cache completion catalogue-chain identity changed"
        )

    if cache_completion.get(
        "verified_cache_evidence_sha256"
    ) != verified_sha:
        raise MonthlySequencePlanExecutionError(
            "cache completion verified-evidence identity changed"
        )

    if assessments_path.read_bytes() != assessments_payload:
        raise MonthlySequencePlanExecutionError(
            "metadata assessments changed during Stage 2 input audit"
        )

    try:
        (
            results_readback,
            verified_readback,
            record_readback,
        ) = (
            cache_exec._scientific_stage_payloads(
                cache_stage
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "cache-verification read-back audit failed"
        ) from exc

    if (
        results_readback
        != results_payload
        or verified_readback
        != verified_payload
        or record_readback
        != record_payload
        or completion_path.read_bytes()
        != completion_payload
    ):
        raise MonthlySequencePlanExecutionError(
            "cache-verification evidence changed during Stage 2 input audit"
        )

    return SequencePlanInputs(
        metadata_context=(
            metadata_context
        ),
        metadata_identity=(
            metadata_identity
        ),
        assessments_payload=(
            assessments_payload
        ),
        assessments=(
            assessments
        ),
        cache_results_payload=(
            results_payload
        ),
        verified_cache_payload=(
            verified_payload
        ),
        cache_record_payload=(
            record_payload
        ),
        cache_completion_payload=(
            completion_payload
        ),
        verified_cache=(
            verified_cache
        ),
        cache_record=(
            cache_record
        ),
        cache_completion=(
            cache_completion
        ),
        catalogue_history_mode=(
            history_mode
        ),
        catalogue_chain_count=len(
            chain
        ),
        catalogue_chain_sha256=(
            chain_sha
        ),
    )


def sequence_plan_inputs_identity(
    value: SequencePlanInputs,
) -> tuple[
    object,
    ...,
]:
    if not isinstance(
        value,
        SequencePlanInputs,
    ):
        raise TypeError(
            "Stage 2 inputs have wrong type"
        )

    return (
        value.metadata_identity,
        sha256_bytes(
            value.assessments_payload
        ),
        sha256_bytes(
            value.cache_results_payload
        ),
        sha256_bytes(
            value.verified_cache_payload
        ),
        sha256_bytes(
            value.cache_record_payload
        ),
        sha256_bytes(
            value.cache_completion_payload
        ),
        value.catalogue_history_mode,
        value.catalogue_chain_count,
        value.catalogue_chain_sha256,
    )


def build_sequence_plan_payloads(
    inputs: SequencePlanInputs,
) -> SequencePlanPayloads:
    if not isinstance(
        inputs,
        SequencePlanInputs,
    ):
        raise TypeError(
            "Stage 2 inputs have wrong type"
        )

    context = (
        inputs.metadata_context
    )

    try:
        plan = (
            plan_contract.build_monthly_sequence_plan(
                inputs.assessments,
                inputs.verified_cache,
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "frozen monthly sequence planning failed"
        ) from exc

    expected_retained = tuple(
        sorted(
            context.retained_metadata
        )
    )

    if tuple(
        plan.retained_accessions
    ) != expected_retained:
        raise MonthlySequencePlanExecutionError(
            "Stage 2 retained population differs from audited metadata"
        )

    expected_cache = tuple(
        evidence.canonical_genbank_assembly_accession
        for evidence in inputs.verified_cache
    )

    if tuple(
        plan.cache_reuse_accessions
    ) != expected_cache:
        raise MonthlySequencePlanExecutionError(
            "Stage 2 cache-reuse population differs from verified-cache evidence"
        )

    try:
        fresh_payload = (
            plan_contract.fresh_target_manifest_bytes(
                plan
            )
        )

        record_payload = (
            plan_contract.serialize_monthly_sequence_plan_record(
                plan,
                source_snapshot_record_sha256=(
                    context.source_snapshot_record_sha256
                ),
            )
        )

        record = (
            plan_contract.audit_monthly_sequence_plan_record(
                record_payload,
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                source_snapshot_record_sha256=(
                    context.source_snapshot_record_sha256
                ),
                fresh_target_manifest=(
                    fresh_payload
                ),
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "Stage 2 scientific serialization audit failed"
        ) from exc

    if record[
        "retained_count"
    ] != len(
        expected_retained
    ):
        raise MonthlySequencePlanExecutionError(
            "Stage 2 retained-count accounting changed"
        )

    if record[
        "cache_reuse_count"
    ] != len(
        expected_cache
    ):
        raise MonthlySequencePlanExecutionError(
            "Stage 2 cache-reuse accounting changed"
        )

    return SequencePlanPayloads(
        plan=plan,
        fresh_target_manifest=(
            fresh_payload
        ),
        plan_record_payload=(
            record_payload
        ),
        plan_record=(
            record
        ),
    )


def fsync_directory(
    path: Path,
) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY,
    )

    try:
        os.fsync(
            descriptor
        )
    finally:
        os.close(
            descriptor
        )


def write_fresh_file(
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
        raise MonthlySequencePlanExecutionError(
            f"artifact already exists: {path.name}"
        )

    try:
        descriptor = os.open(
            path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL,
            0o644,
        )
    except OSError as exc:
        raise MonthlySequencePlanExecutionError(
            f"unable to create artifact: {path.name}"
        ) from exc

    try:
        with os.fdopen(
            descriptor,
            "wb",
            closefd=True,
        ) as handle:
            handle.write(
                payload
            )
            handle.flush()
            os.fsync(
                handle.fileno()
            )
    except Exception:
        try:
            os.unlink(
                path
            )
        except OSError:
            pass

        raise

    os.chmod(
        path,
        0o644,
    )


def _scientific_stage_payloads(
    stage: Path,
) -> tuple[
    bytes,
    bytes,
]:
    _require_exact_inventory(
        stage,
        expected_files={
            FRESH_TARGETS_NAME,
            PLAN_RECORD_NAME,
        },
        label="sequence-plan stage",
    )

    observed = os.lstat(
        stage
    )

    if stat.S_IMODE(
        observed.st_mode
    ) != 0o755:
        raise MonthlySequencePlanExecutionError(
            "sequence-plan stage mode changed"
        )

    fresh = _require_regular_file(
        stage
        / FRESH_TARGETS_NAME,
        label="fresh-target manifest",
        expected_mode=0o644,
    ).read_bytes()

    record = _require_regular_file(
        stage
        / PLAN_RECORD_NAME,
        label="monthly sequence-plan record",
        expected_mode=0o644,
    ).read_bytes()

    return (
        fresh,
        record,
    )


def audit_scientific_stage(
    stage: Path,
    *,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
) -> tuple[
    bytes,
    bytes,
    Mapping[
        str,
        object,
    ],
]:
    fresh, record_payload = (
        _scientific_stage_payloads(
            stage
        )
    )

    try:
        record = (
            plan_contract.audit_monthly_sequence_plan_record(
                record_payload,
                source_snapshot_id=(
                    source_snapshot_id
                ),
                source_snapshot_record_sha256=(
                    source_snapshot_record_sha256
                ),
                fresh_target_manifest=(
                    fresh
                ),
            )
        )
    except Exception as exc:
        raise MonthlySequencePlanExecutionError(
            "completed sequence-plan stage audit failed"
        ) from exc

    return (
        fresh,
        record_payload,
        record,
    )


def promote_scientific_stage_no_clobber(
    *,
    partial: Path,
    final: Path,
    expected_payloads: tuple[
        bytes,
        bytes,
    ],
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
) -> tuple[
    bytes,
    bytes,
    Mapping[
        str,
        object,
    ],
]:
    if len(
        expected_payloads
    ) != 2:
        raise MonthlySequencePlanExecutionError(
            "expected Stage 2 payload count changed"
        )

    if os.path.lexists(
        final
    ):
        raise MonthlySequencePlanExecutionError(
            "sequence-plan stage already exists"
        )

    try:
        os.mkdir(
            final,
            0o755,
        )
    except FileExistsError as exc:
        raise MonthlySequencePlanExecutionError(
            "sequence-plan stage appeared before publication"
        ) from exc

    os.chmod(
        final,
        0o755,
    )

    fsync_directory(
        final.parent
    )

    for name in (
        FRESH_TARGETS_NAME,
        PLAN_RECORD_NAME,
    ):
        source = _require_regular_file(
            partial
            / name,
            label=f"partial {name}",
            expected_mode=0o644,
        )

        target = (
            final
            / name
        )

        try:
            os.link(
                source,
                target,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise MonthlySequencePlanExecutionError(
                "sequence-plan artifact appeared during canonical publication"
            ) from exc

    fsync_directory(
        final
    )

    (
        final_fresh,
        final_record,
        final_audit,
    ) = audit_scientific_stage(
        final,
        source_snapshot_id=(
            source_snapshot_id
        ),
        source_snapshot_record_sha256=(
            source_snapshot_record_sha256
        ),
    )

    if (
        final_fresh
        != expected_payloads[
            0
        ]
        or final_record
        != expected_payloads[
            1
        ]
    ):
        raise MonthlySequencePlanExecutionError(
            "canonical sequence-plan stage changed during publication"
        )

    for name in (
        FRESH_TARGETS_NAME,
        PLAN_RECORD_NAME,
    ):
        os.unlink(
            partial
            / name
        )

    os.rmdir(
        partial
    )

    fsync_directory(
        final.parent
    )

    return (
        final_fresh,
        final_record,
        final_audit,
    )


def build_completion_receipt(
    *,
    release_id: str,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    execution_commit: str,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
    cache_verification_results_sha256: str,
    verified_cache_evidence_sha256: str,
    cache_verification_record_sha256: str,
    cache_verification_completion_sha256: str,
    retained_count: int,
    cache_reuse_count: int,
    fresh_acquisition_count: int,
    fresh_batch_count: int,
    fresh_target_manifest_sha256: str,
    sequence_plan_record_sha256: str,
) -> bytes:
    release = validate_release_id(
        release_id
    )

    commit = validate_git_commit(
        execution_commit,
        label="completion execution commit",
    )

    counts = (
        retained_count,
        cache_reuse_count,
        fresh_acquisition_count,
        fresh_batch_count,
    )

    if any(
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 0
        for value in counts
    ):
        raise MonthlySequencePlanExecutionError(
            "sequence-plan completion count is invalid"
        )

    if (
        cache_reuse_count
        + fresh_acquisition_count
        != retained_count
    ):
        raise MonthlySequencePlanExecutionError(
            "sequence-plan completion partition accounting changed"
        )

    expected_batches = (
        (
            fresh_acquisition_count
            + plan_contract.FRESH_BATCH_SIZE
            - 1
        )
        // plan_contract.FRESH_BATCH_SIZE
        if fresh_acquisition_count
        else 0
    )

    if fresh_batch_count != expected_batches:
        raise MonthlySequencePlanExecutionError(
            "sequence-plan completion batch accounting changed"
        )

    if (
        not isinstance(
            source_snapshot_id,
            str,
        )
        or not source_snapshot_id
        or source_snapshot_id
        != source_snapshot_id.strip()
    ):
        raise MonthlySequencePlanExecutionError(
            "completion source snapshot ID is invalid"
        )

    return canonical_json_bytes(
        {
            "cache_reuse_count":
                cache_reuse_count,
            "cache_verification_completion_sha256":
                validate_sha256(
                    cache_verification_completion_sha256,
                    label="cache-verification completion SHA256",
                ),
            "cache_verification_record_sha256":
                validate_sha256(
                    cache_verification_record_sha256,
                    label="cache-verification record SHA256",
                ),
            "cache_verification_results_sha256":
                validate_sha256(
                    cache_verification_results_sha256,
                    label="cache-verification results SHA256",
                ),
            "execution_commit":
                commit,
            "fresh_acquisition_count":
                fresh_acquisition_count,
            "fresh_batch_count":
                fresh_batch_count,
            "fresh_target_manifest_sha256":
                validate_sha256(
                    fresh_target_manifest_sha256,
                    label="fresh-target manifest SHA256",
                ),
            "metadata_completion_sha256":
                validate_sha256(
                    metadata_completion_sha256,
                    label="metadata completion SHA256",
                ),
            "metadata_record_sha256":
                validate_sha256(
                    metadata_record_sha256,
                    label="metadata record SHA256",
                ),
            "release_id":
                release,
            "retained_count":
                retained_count,
            "schema_version":
                COMPLETION_SCHEMA,
            "sequence_plan_record_sha256":
                validate_sha256(
                    sequence_plan_record_sha256,
                    label="sequence-plan record SHA256",
                ),
            "source_snapshot_id":
                source_snapshot_id,
            "source_snapshot_record_sha256":
                validate_sha256(
                    source_snapshot_record_sha256,
                    label="source-snapshot-record SHA256",
                ),
            "status":
                COMPLETION_STATUS,
            "verified_cache_evidence_sha256":
                validate_sha256(
                    verified_cache_evidence_sha256,
                    label="verified-cache evidence SHA256",
                ),
        }
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
            "sequence-plan completion receipt must be bytes"
        )

    expected = build_completion_receipt(
        **kwargs
    )

    if payload != expected:
        raise MonthlySequencePlanExecutionError(
            "sequence-plan completion receipt changed"
        )

    return _parse_json_object(
        payload,
        label="sequence-plan completion receipt",
    )


def write_completion_no_clobber(
    path: Path,
    payload: bytes,
) -> None:
    final = Path(
        path
    )

    temporary = (
        final.parent
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlySequencePlanExecutionError(
            "sequence-plan completion already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlySequencePlanExecutionError(
            "sequence-plan completion temporary path already exists"
        )

    write_fresh_file(
        temporary,
        payload,
    )

    try:
        os.link(
            temporary,
            final,
            follow_symlinks=False,
        )
    except FileExistsError as exc:
        try:
            os.unlink(
                temporary
            )
        except OSError:
            pass

        raise MonthlySequencePlanExecutionError(
            "sequence-plan completion appeared during publication"
        ) from exc

    os.unlink(
        temporary
    )

    fsync_directory(
        final.parent
    )


def execute_monthly_sequence_plan(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    execution_commit: str,
    input_loader=load_sequence_plan_inputs,
) -> MonthlySequencePlanExecutionResult:
    root = Path(
        repo
    ).resolve()

    stage1 = Path(
        stage1_root
    ).resolve()

    commit = validate_git_commit(
        execution_commit,
        label="execution commit",
    )

    final = (
        stage1
        / SEQUENCE_PLAN_STAGE_NAME
    )

    partial = (
        stage1
        / SEQUENCE_PLAN_PARTIAL_STAGE_NAME
    )

    completion_path = (
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
            "sequence-plan stage",
        ),
        (
            partial,
            "sequence-plan partial stage",
        ),
        (
            completion_path,
            "sequence-plan completion",
        ),
        (
            completion_temp,
            "sequence-plan completion temporary path",
        ),
    ):
        if os.path.lexists(
            path
        ):
            raise MonthlySequencePlanExecutionError(
                f"{label} already exists"
            )

    first = input_loader(
        repo=root,
        production_root=Path(
            production_root
        ),
        stage1_root=stage1,
        execution_commit=commit,
    )

    first_identity = (
        sequence_plan_inputs_identity(
            first
        )
    )

    first_payloads = (
        build_sequence_plan_payloads(
            first
        )
    )

    try:
        os.mkdir(
            partial,
            0o755,
        )
    except FileExistsError as exc:
        raise MonthlySequencePlanExecutionError(
            "sequence-plan partial stage appeared before creation"
        ) from exc

    os.chmod(
        partial,
        0o755,
    )

    fsync_directory(
        stage1
    )

    write_fresh_file(
        partial
        / FRESH_TARGETS_NAME,
        first_payloads.fresh_target_manifest,
    )

    write_fresh_file(
        partial
        / PLAN_RECORD_NAME,
        first_payloads.plan_record_payload,
    )

    fsync_directory(
        partial
    )

    (
        partial_fresh,
        partial_record,
        _,
    ) = audit_scientific_stage(
        partial,
        source_snapshot_id=(
            first.metadata_context.source_snapshot_id
        ),
        source_snapshot_record_sha256=(
            first.metadata_context.source_snapshot_record_sha256
        ),
    )

    if (
        partial_fresh
        != first_payloads.fresh_target_manifest
        or partial_record
        != first_payloads.plan_record_payload
    ):
        raise MonthlySequencePlanExecutionError(
            "partial sequence-plan bytes changed after write"
        )

    second = input_loader(
        repo=root,
        production_root=Path(
            production_root
        ),
        stage1_root=stage1,
        execution_commit=commit,
    )

    second_identity = (
        sequence_plan_inputs_identity(
            second
        )
    )

    if second_identity != first_identity:
        raise MonthlySequencePlanExecutionError(
            "Stage 2 upstream evidence changed before publication"
        )

    second_payloads = (
        build_sequence_plan_payloads(
            second
        )
    )

    if (
        second_payloads.fresh_target_manifest
        != first_payloads.fresh_target_manifest
        or second_payloads.plan_record_payload
        != first_payloads.plan_record_payload
    ):
        raise MonthlySequencePlanExecutionError(
            "Stage 2 scientific derivation changed before publication"
        )

    (
        final_fresh,
        final_record,
        final_audit,
    ) = promote_scientific_stage_no_clobber(
        partial=partial,
        final=final,
        expected_payloads=(
            first_payloads.fresh_target_manifest,
            first_payloads.plan_record_payload,
        ),
        source_snapshot_id=(
            second.metadata_context.source_snapshot_id
        ),
        source_snapshot_record_sha256=(
            second.metadata_context.source_snapshot_record_sha256
        ),
    )

    retained_count = int(
        final_audit[
            "retained_count"
        ]
    )

    cache_reuse_count = int(
        final_audit[
            "cache_reuse_count"
        ]
    )

    fresh_count = int(
        final_audit[
            "fresh_acquisition_count"
        ]
    )

    fresh_batch_count = int(
        final_audit[
            "fresh_batch_count"
        ]
    )

    completion_payload = (
        build_completion_receipt(
            release_id=(
                second.metadata_context.release_id
            ),
            source_snapshot_id=(
                second.metadata_context.source_snapshot_id
            ),
            source_snapshot_record_sha256=(
                second.metadata_context.source_snapshot_record_sha256
            ),
            execution_commit=commit,
            metadata_record_sha256=(
                second.metadata_context.metadata_record_sha256
            ),
            metadata_completion_sha256=(
                second.metadata_context.metadata_completion_sha256
            ),
            cache_verification_results_sha256=(
                sha256_bytes(
                    second.cache_results_payload
                )
            ),
            verified_cache_evidence_sha256=(
                sha256_bytes(
                    second.verified_cache_payload
                )
            ),
            cache_verification_record_sha256=(
                sha256_bytes(
                    second.cache_record_payload
                )
            ),
            cache_verification_completion_sha256=(
                sha256_bytes(
                    second.cache_completion_payload
                )
            ),
            retained_count=(
                retained_count
            ),
            cache_reuse_count=(
                cache_reuse_count
            ),
            fresh_acquisition_count=(
                fresh_count
            ),
            fresh_batch_count=(
                fresh_batch_count
            ),
            fresh_target_manifest_sha256=(
                sha256_bytes(
                    final_fresh
                )
            ),
            sequence_plan_record_sha256=(
                sha256_bytes(
                    final_record
                )
            ),
        )
    )

    write_completion_no_clobber(
        completion_path,
        completion_payload,
    )

    completion_readback = (
        _require_regular_file(
            completion_path,
            label="sequence-plan completion",
            expected_mode=0o644,
        ).read_bytes()
    )

    audit_completion_receipt(
        completion_readback,
        release_id=(
            second.metadata_context.release_id
        ),
        source_snapshot_id=(
            second.metadata_context.source_snapshot_id
        ),
        source_snapshot_record_sha256=(
            second.metadata_context.source_snapshot_record_sha256
        ),
        execution_commit=commit,
        metadata_record_sha256=(
            second.metadata_context.metadata_record_sha256
        ),
        metadata_completion_sha256=(
            second.metadata_context.metadata_completion_sha256
        ),
        cache_verification_results_sha256=(
            sha256_bytes(
                second.cache_results_payload
            )
        ),
        verified_cache_evidence_sha256=(
            sha256_bytes(
                second.verified_cache_payload
            )
        ),
        cache_verification_record_sha256=(
            sha256_bytes(
                second.cache_record_payload
            )
        ),
        cache_verification_completion_sha256=(
            sha256_bytes(
                second.cache_completion_payload
            )
        ),
        retained_count=(
            retained_count
        ),
        cache_reuse_count=(
            cache_reuse_count
        ),
        fresh_acquisition_count=(
            fresh_count
        ),
        fresh_batch_count=(
            fresh_batch_count
        ),
        fresh_target_manifest_sha256=(
            sha256_bytes(
                final_fresh
            )
        ),
        sequence_plan_record_sha256=(
            sha256_bytes(
                final_record
            )
        ),
    )

    return MonthlySequencePlanExecutionResult(
        release_id=(
            second.metadata_context.release_id
        ),
        source_snapshot_id=(
            second.metadata_context.source_snapshot_id
        ),
        stage_root=final,
        completion_path=(
            completion_path
        ),
        retained_count=(
            retained_count
        ),
        cache_reuse_count=(
            cache_reuse_count
        ),
        fresh_acquisition_count=(
            fresh_count
        ),
        fresh_batch_count=(
            fresh_batch_count
        ),
        fresh_target_manifest_sha256=(
            sha256_bytes(
                final_fresh
            )
        ),
        sequence_plan_record_sha256=(
            sha256_bytes(
                final_record
            )
        ),
        completion_sha256=(
            sha256_bytes(
                completion_readback
            )
        ),
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute BacSelect monthly Stage 2 sequence planning."
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
    )

    parser.add_argument(
        "--stage1-root",
        required=True,
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    return parser


def main(
    argv: Sequence[
        str
    ] | None = None,
) -> int:
    parser = build_argument_parser()

    args = parser.parse_args(
        argv
    )

    if not args.authorize_real_execution:
        raise MonthlySequencePlanExecutionError(
            "real monthly sequence planning requires explicit authorization"
        )

    script_path = Path(
        __file__
    ).resolve()

    repo = script_path.parents[
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

    result = execute_monthly_sequence_plan(
        repo=repo,
        production_root=Path(
            args.production_root
        ),
        stage1_root=Path(
            args.stage1_root
        ),
        execution_commit=(
            args.expected_commit
        ),
    )

    print(
        "PASS | monthly sequence plan complete"
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )

    print(
        f"retained_count={result.retained_count}"
    )

    print(
        f"cache_reuse_count={result.cache_reuse_count}"
    )

    print(
        f"fresh_acquisition_count={result.fresh_acquisition_count}"
    )

    print(
        f"fresh_batch_count={result.fresh_batch_count}"
    )

    print(
        f"fresh_target_manifest_sha256="
        f"{result.fresh_target_manifest_sha256}"
    )

    print(
        f"sequence_plan_record_sha256="
        f"{result.sequence_plan_record_sha256}"
    )

    print(
        f"completion_sha256="
        f"{result.completion_sha256}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
