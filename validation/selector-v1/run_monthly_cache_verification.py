#!/usr/bin/env python3
"""Execute BacSelect monthly cache verification."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from typing import Callable, Mapping, Sequence

from bacselect import (
    monthly_authoritative_storage as authoritative_storage,
)
from bacselect import (
    monthly_sequence_acquisition_completion as completion_contract,
)
from bacselect import (
    monthly_sequence_cache_catalogue as catalogue_contract,
)
from bacselect import source_truth_execution
from bacselect.monthly_cache_verification import (
    CACHE_FRESH_REQUIRED,
    CACHE_VERIFIED,
    MonthlyCacheCandidate,
    MonthlyCacheComponent,
    MonthlyCachePackageFileObservation,
    MonthlyCacheVerificationError,
    audit_cache_verification_record,
    audit_cache_verification_results,
    audit_verified_cache_evidence,
    serialize_cache_verification_record,
    serialize_cache_verification_results,
    serialize_verified_cache_evidence,
    verify_cache_candidates,
)
from bacselect.monthly_release_start import (
    canonical_json_bytes,
)
from bacselect.monthly_sequence_validation import (
    CANDIDATE_AUDIT_FIELDS,
    COMPONENT_AUDIT_FIELDS,
    PACKAGE_FILE_FIELDS,
)
from bacselect.source_eligibility import (
    CANONICAL_GCA_RE,
    RETAIN,
)


CATALOGUE_EXECUTOR_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_sequence_cache_catalogue.py"
)

CATALOGUE_EXECUTOR_TEST_RELATIVE = Path(
    "tests/test_run_monthly_sequence_cache_catalogue.py"
)

CATALOGUE_EXECUTION_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-sequence-cache-catalogue-execution.md"
)

METADATA_EXECUTOR_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_metadata_eligibility.py"
)

METADATA_EXECUTOR_TEST_RELATIVE = Path(
    "tests/test_run_monthly_metadata_eligibility.py"
)

METADATA_EXECUTION_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-metadata-eligibility-execution.md"
)

COMPLETION_CORE_RELATIVE = Path(
    "src/bacselect/monthly_sequence_acquisition_completion.py"
)

COMPLETION_CORE_TEST_RELATIVE = Path(
    "tests/test_monthly_sequence_acquisition_completion.py"
)

CACHE_CORE_RELATIVE = Path(
    "src/bacselect/monthly_cache_verification.py"
)

CACHE_CORE_TEST_RELATIVE = Path(
    "tests/test_monthly_cache_verification.py"
)

CACHE_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-cache-verification.md"
)

SEQUENCE_PLAN_RELATIVE = Path(
    "src/bacselect/monthly_sequence_plan.py"
)

SOURCE_ELIGIBILITY_RELATIVE = Path(
    "src/bacselect/source_eligibility.py"
)

SOURCE_FINGERPRINT_RELATIVE = Path(
    "src/bacselect/source_fingerprint.py"
)

SOURCE_TRUTH_RELATIVE = Path(
    "src/bacselect/source_truth_execution.py"
)

EXECUTION_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-cache-verification-execution.md"
)

WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_monthly_cache_verification.py"
)


EXPECTED_CATALOGUE_EXECUTOR_SHA256 = (
    "2cb7e162aa36b141d54b18fc29ffbaa9be3a5d9ca42a9e6b5bb1ff62e14cb3ea"
)

EXPECTED_CATALOGUE_EXECUTOR_TEST_SHA256 = (
    "2f6f2e8867e071b93972d3e07f9567f194991817a8d6dec6cebf266f7ca29f92"
)

EXPECTED_CATALOGUE_EXECUTION_METHOD_SHA256 = (
    "128b533c2cfc9f9a0751094a9bb33f5ef97414ede86f8a3df9d104b9c7d7fdcd"
)

EXPECTED_METADATA_EXECUTOR_SHA256 = (
    "81506e338d14d9a454db2a9f7cd5b1ac2d7ebdbafa069c9aed4fee4fd8b29041"
)

EXPECTED_METADATA_EXECUTOR_TEST_SHA256 = (
    "dadfb0b789faeae94cf5fcf5d22da5ce3242cd48e5e177cf761de8d6856ccc5e"
)

EXPECTED_METADATA_EXECUTION_METHOD_SHA256 = (
    "d99db46fc4487a1e880abc9f0e7b67a780557747df7f80638c4374b22d271aaa"
)

EXPECTED_COMPLETION_CORE_SHA256 = (
    "7482f70aa6c12c9dcc0a6c6b84c4058eeea1c0a227125b3ad97947a0eb303d61"
)

EXPECTED_COMPLETION_CORE_TEST_SHA256 = (
    "83c5fd0b285df4b6e593165160646d4c0c08054a5e434736fcb7b58476733965"
)

EXPECTED_CACHE_CORE_SHA256 = (
    "4a2ba0c142663a933ee0df25d69f82fdeb3b6a694154ceafbd3e2e9103b3ef7c"
)

EXPECTED_CACHE_CORE_TEST_SHA256 = (
    "fca5c5609473da5f4e0e7d5039f4c5ae3586e5820cc53592e67fa3914c3d4c2a"
)

EXPECTED_CACHE_METHOD_SHA256 = (
    "15e8d84f185a47e3358601236bc6f1df780111ff44b3c988e59bd780f192e43f"
)

EXPECTED_SEQUENCE_PLAN_SHA256 = (
    "e2213fee3703580b0e96fd280a050765812d0a369eff34846d8d1b958dae9e18"
)

EXPECTED_SOURCE_ELIGIBILITY_SHA256 = (
    "6e57dd950f972a9883e8fcbc78a18c694a5fabda58b03835f268eef681a03cc2"
)

EXPECTED_SOURCE_FINGERPRINT_SHA256 = (
    "6c994d243709abdbe9d7c8949e156009b9f31f3fcef3247cc3c5679e2fff41c9"
)

EXPECTED_SOURCE_TRUTH_SHA256 = (
    "83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92"
)

EXPECTED_EXECUTION_METHOD_SHA256 = (
    "36a61a09c3bbdd931023dedbc0578b211d4d6b70dae020eee80a47e726c633bd"
)


CACHE_STAGE_NAME = (
    "cache-verification"
)

CACHE_PARTIAL_STAGE_NAME = (
    "cache-verification.partial"
)

RESULTS_NAME = (
    "cache-verification-results.jsonl"
)

VERIFIED_CACHE_NAME = (
    "verified-cache-evidence.jsonl"
)

RECORD_NAME = (
    "cache-verification-record.json"
)

COMPLETION_NAME = (
    "cache-verification-completion.json"
)

COMPLETION_TEMP_NAME = (
    ".cache-verification-completion.json.tmp"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-cache-verification-completion-v1"
)

COMPLETION_STATUS = (
    "CACHE_VERIFICATION_EXECUTION_COMPLETE"
)

HISTORY_NONE = (
    "NO_PRIOR_SEQUENCE_EVIDENCE"
)

HISTORY_CHAINED = (
    "CHAINED_CATALOGUE"
)


COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

RELEASE_RE = re.compile(
    r"^[0-9]{4}\.(0[1-9]|1[0-2])$"
)


class MonthlyCacheVerificationExecutionError(
    RuntimeError
):
    """Raised when monthly cache-verification execution fails closed."""


@dataclass(
    frozen=True,
)
class CurrentMetadataContext:
    release_id: str
    source_snapshot_id: str
    stage1_root: Path
    source_snapshot_record_sha256: str
    metadata_record_sha256: str
    metadata_completion_sha256: str
    retained_metadata: Mapping[
        str,
        str,
    ]


@dataclass(
    frozen=True,
)
class RequiredObject:
    path: Path
    payload: bytes
    size_bytes: int
    sha256: str


@dataclass(
    frozen=True,
)
class OptionalObject:
    path: Path
    payload: bytes | None
    observed_size_bytes: int | None
    observed_sha256: str | None


@dataclass(
    frozen=True,
)
class BatchEvidence:
    provenance: Mapping[
        str,
        object,
    ]
    candidate_rows: tuple[
        Mapping[
            str,
            str,
        ],
        ...,
    ]
    component_rows: tuple[
        Mapping[
            str,
            str,
        ],
        ...,
    ]
    package_rows: tuple[
        Mapping[
            str,
            str,
        ],
        ...,
    ]


@dataclass(
    frozen=True,
)
class CandidateMaterialization:
    candidates: tuple[
        MonthlyCacheCandidate,
        ...,
    ]
    retained_origin_eligible_count: int


@dataclass(
    frozen=True,
)
class MonthlyCacheVerificationExecutionResult:
    release_id: str
    source_snapshot_id: str
    stage_root: Path
    completion_path: Path
    candidate_input_count: int
    verified_cache_count: int
    fallback_to_fresh_count: int
    results_sha256: str
    verified_cache_evidence_sha256: str
    record_sha256: str
    completion_sha256: str


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
        raise MonthlyCacheVerificationExecutionError(
            f"{label} must be a lowercase 40-character Git commit"
        )

    return value


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
        raise MonthlyCacheVerificationExecutionError(
            f"{label} must be lowercase SHA256"
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
        raise MonthlyCacheVerificationExecutionError(
            "release ID is invalid"
        )

    return value


def release_ordinal(
    release_id: str,
) -> int:
    release = validate_release_id(
        release_id
    )

    year, month = release.split(
        ".",
        1,
    )

    return (
        int(
            year
        )
        * 12
        + int(
            month
        )
    )


def sha256_file(
    path: Path,
    block_size: int = 1024 * 1024,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        for block in iter(
            lambda:
                handle.read(
                    block_size
                ),
            b"",
        ):
            digest.update(
                block
            )

    return digest.hexdigest()


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
    expected_sha = validate_sha256(
        expected,
        label=f"expected {label} SHA256",
    )

    observed = reader(
        path
    )

    if observed != expected_sha:
        raise MonthlyCacheVerificationExecutionError(
            f"{label} SHA256 mismatch: {observed}"
        )


def _load_module(
    path: Path,
    *,
    module_name: str,
):
    supplied = Path(
        path
    )

    try:
        metadata = os.lstat(
            supplied
        )
    except FileNotFoundError:
        raise MonthlyCacheVerificationExecutionError(
            f"missing frozen executor: {supplied}"
        ) from None

    if (
        stat.S_ISLNK(
            metadata.st_mode
        )
        or not stat.S_ISREG(
            metadata.st_mode
        )
    ):
        raise MonthlyCacheVerificationExecutionError(
            "frozen executor is not a regular non-symlink file"
        )

    existing = sys.modules.get(
        module_name
    )

    if existing is not None:
        existing_file = getattr(
            existing,
            "__file__",
            None,
        )

        if (
            existing_file is not None
            and Path(
                existing_file
            ).resolve()
            == supplied.resolve()
        ):
            return existing

        raise MonthlyCacheVerificationExecutionError(
            "frozen executor module name is already bound "
            "to another path"
        )

    spec = importlib.util.spec_from_file_location(
        module_name,
        supplied,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise MonthlyCacheVerificationExecutionError(
            "unable to construct frozen executor module"
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
        raise

    return module


def load_frozen_catalogue_execution(
    repo: Path,
):
    return _load_module(
        Path(
            repo
        ).resolve()
        / CATALOGUE_EXECUTOR_RELATIVE,
        module_name=(
            "_bacselect_frozen_sequence_cache_catalogue_execution"
        ),
    )


def load_frozen_metadata_execution(
    repo: Path,
):
    return _load_module(
        Path(
            repo
        ).resolve()
        / METADATA_EXECUTOR_RELATIVE,
        module_name=(
            "_bacselect_frozen_metadata_eligibility_execution"
        ),
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

    catalogue_execution = (
        load_frozen_catalogue_execution(
            root
        )
    )

    metadata_execution = (
        load_frozen_metadata_execution(
            root
        )
    )

    catalogue_kwargs = {
        "expected_commit":
            commit,
        "expected_wrapper_sha256":
            EXPECTED_CATALOGUE_EXECUTOR_SHA256,
        "expected_wrapper_test_sha256":
            EXPECTED_CATALOGUE_EXECUTOR_TEST_SHA256,
        "file_sha256_reader":
            file_sha256_reader,
    }

    metadata_kwargs = {
        "expected_commit":
            commit,
        "expected_wrapper_sha256":
            EXPECTED_METADATA_EXECUTOR_SHA256,
        "expected_wrapper_test_sha256":
            EXPECTED_METADATA_EXECUTOR_TEST_SHA256,
        "file_sha256_reader":
            file_sha256_reader,
    }

    if git_reader is not None:
        catalogue_kwargs[
            "git_reader"
        ] = git_reader

        metadata_kwargs[
            "git_reader"
        ] = git_reader

    try:
        catalogue_execution.repository_preflight(
            root,
            **catalogue_kwargs
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "frozen catalogue-executor preflight failed"
        ) from exc

    try:
        metadata_execution.repository_preflight(
            root,
            **metadata_kwargs
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "frozen metadata-executor preflight failed"
        ) from exc

    fixed = (
        (
            CATALOGUE_EXECUTION_METHOD_RELATIVE,
            EXPECTED_CATALOGUE_EXECUTION_METHOD_SHA256,
            "catalogue execution method",
        ),
        (
            METADATA_EXECUTION_METHOD_RELATIVE,
            EXPECTED_METADATA_EXECUTION_METHOD_SHA256,
            "metadata execution method",
        ),
        (
            COMPLETION_CORE_RELATIVE,
            EXPECTED_COMPLETION_CORE_SHA256,
            "sequence-acquisition completion contract",
        ),
        (
            COMPLETION_CORE_TEST_RELATIVE,
            EXPECTED_COMPLETION_CORE_TEST_SHA256,
            "sequence-acquisition completion contract test",
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
            CACHE_METHOD_RELATIVE,
            EXPECTED_CACHE_METHOD_SHA256,
            "monthly cache-verification method",
        ),
        (
            SEQUENCE_PLAN_RELATIVE,
            EXPECTED_SEQUENCE_PLAN_SHA256,
            "monthly sequence-plan contract",
        ),
        (
            SOURCE_ELIGIBILITY_RELATIVE,
            EXPECTED_SOURCE_ELIGIBILITY_SHA256,
            "source-eligibility implementation",
        ),
        (
            SOURCE_FINGERPRINT_RELATIVE,
            EXPECTED_SOURCE_FINGERPRINT_SHA256,
            "source-fingerprint implementation",
        ),
        (
            SOURCE_TRUTH_RELATIVE,
            EXPECTED_SOURCE_TRUTH_SHA256,
            "source-truth implementation",
        ),
        (
            EXECUTION_METHOD_RELATIVE,
            EXPECTED_EXECUTION_METHOD_SHA256,
            "cache-verification execution method",
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
        Path(
            __file__
        ).resolve(),
        expected_wrapper_sha256,
        label="cache-verification executor",
        reader=file_sha256_reader,
    )

    require_sha256(
        root
        / WRAPPER_TEST_RELATIVE,
        expected_wrapper_test_sha256,
        label="cache-verification executor test",
        reader=file_sha256_reader,
    )


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    supplied = Path(
        path
    )

    try:
        metadata = os.lstat(
            supplied
        )
    except FileNotFoundError:
        raise MonthlyCacheVerificationExecutionError(
            f"missing {label}: {supplied}"
        ) from None

    if (
        stat.S_ISLNK(
            metadata.st_mode
        )
        or not stat.S_ISDIR(
            metadata.st_mode
        )
    ):
        raise MonthlyCacheVerificationExecutionError(
            f"{label} is not a real directory: {supplied}"
        )

    return supplied.resolve()


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    supplied = Path(
        path
    )

    try:
        metadata = os.lstat(
            supplied
        )
    except FileNotFoundError:
        raise MonthlyCacheVerificationExecutionError(
            f"missing {label}: {supplied}"
        ) from None

    if (
        stat.S_ISLNK(
            metadata.st_mode
        )
        or not stat.S_ISREG(
            metadata.st_mode
        )
    ):
        raise MonthlyCacheVerificationExecutionError(
            f"{label} is not a regular non-symlink file: {supplied}"
        )

    return supplied.resolve()


def _require_exact_inventory(
    directory: Path,
    *,
    expected_files: set[
        str
    ],
    label: str,
) -> None:
    observed = set()

    for item in directory.iterdir():
        if item.is_symlink():
            raise MonthlyCacheVerificationExecutionError(
                f"{label} contains a symbolic link"
            )

        if item.is_dir():
            raise MonthlyCacheVerificationExecutionError(
                f"{label} contains an unexpected directory"
            )

        if not item.is_file():
            raise MonthlyCacheVerificationExecutionError(
                f"{label} contains a non-regular entry"
            )

        observed.add(
            item.name
        )

    if observed != expected_files:
        raise MonthlyCacheVerificationExecutionError(
            f"{label} artifact inventory changed"
        )


def load_current_metadata_context(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    execution_commit: str,
) -> CurrentMetadataContext:
    root = Path(
        repo
    ).resolve()

    metadata_execution = (
        load_frozen_metadata_execution(
            root
        )
    )

    try:
        upstream = (
            metadata_execution.load_stage1_contract(
                production_root=(
                    production_root
                ),
                stage1_root=(
                    stage1_root
                ),
                expected_commit=(
                    execution_commit
                ),
            )
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "current Stage 1 audit failed"
        ) from exc

    stage = _require_real_directory(
        upstream.stage1_root
        / metadata_execution.METADATA_STAGE_NAME,
        label="metadata-eligibility stage",
    )

    expected_inventory = {
        metadata_execution.ASSESSMENTS_NAME,
        metadata_execution.SUMMARY_NAME,
        metadata_execution.RECORD_NAME,
    }

    _require_exact_inventory(
        stage,
        expected_files=(
            expected_inventory
        ),
        label="metadata-eligibility stage",
    )

    assessments_path = (
        _require_regular_file(
            stage
            / metadata_execution.ASSESSMENTS_NAME,
            label="metadata assessments",
        )
    )

    summary_path = (
        _require_regular_file(
            stage
            / metadata_execution.SUMMARY_NAME,
            label="metadata summary",
        )
    )

    record_path = (
        _require_regular_file(
            stage
            / metadata_execution.RECORD_NAME,
            label="metadata record",
        )
    )

    completion_path = (
        _require_regular_file(
            upstream.stage1_root
            / metadata_execution.COMPLETION_NAME,
            label="metadata completion receipt",
        )
    )

    assessments = (
        assessments_path.read_bytes()
    )

    summary = (
        summary_path.read_bytes()
    )

    record = (
        record_path.read_bytes()
    )

    completion = (
        completion_path.read_bytes()
    )

    try:
        audited_assessments = (
            metadata_execution.audit_metadata_assessments(
                assessments
            )
        )

        metadata_execution.audit_metadata_summary(
            summary,
            assessments_payload=(
                assessments
            ),
        )

        metadata_execution.audit_metadata_eligibility_record(
            record,
            source_snapshot_id=(
                upstream.source_snapshot_id
            ),
            source_snapshot_record_sha256=(
                upstream.snapshot_sha256
            ),
            raw_response=(
                upstream.raw_response
            ),
            assessments_payload=(
                assessments
            ),
            summary_payload=(
                summary
            ),
            source_eligibility_sha256=(
                metadata_execution.EXPECTED_SOURCE_ELIGIBILITY_SHA256
            ),
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "completed metadata stage audit failed"
        ) from exc

    assessments_sha = hashlib.sha256(
        assessments
    ).hexdigest()

    summary_sha = hashlib.sha256(
        summary
    ).hexdigest()

    record_sha = hashlib.sha256(
        record
    ).hexdigest()

    try:
        metadata_execution.audit_completion_receipt(
            completion,
            release_id=(
                upstream.release_id
            ),
            source_snapshot_id=(
                upstream.source_snapshot_id
            ),
            source_snapshot_record_sha256=(
                upstream.snapshot_sha256
            ),
            execution_commit=(
                execution_commit
            ),
            assessments_sha256=(
                assessments_sha
            ),
            summary_sha256=(
                summary_sha
            ),
            record_sha256=(
                record_sha
            ),
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "metadata completion receipt audit failed"
        ) from exc

    if (
        assessments_path.read_bytes()
        != assessments
        or summary_path.read_bytes()
        != summary
        or record_path.read_bytes()
        != record
        or completion_path.read_bytes()
        != completion
    ):
        raise MonthlyCacheVerificationExecutionError(
            "metadata evidence changed during cache preflight"
        )

    retained: dict[
        str,
        str,
    ] = {}

    for assessment in audited_assessments:
        if assessment.decision != RETAIN:
            continue

        accession = assessment.accession
        biosample = assessment.biosample

        if (
            not isinstance(
                accession,
                str,
            )
            or CANONICAL_GCA_RE.fullmatch(
                accession
            )
            is None
        ):
            raise MonthlyCacheVerificationExecutionError(
                "metadata-retained accession is invalid"
            )

        if not isinstance(
            biosample,
            str,
        ):
            raise MonthlyCacheVerificationExecutionError(
                "metadata-retained BioSample is missing"
            )

        if accession in retained:
            raise MonthlyCacheVerificationExecutionError(
                "duplicate metadata-retained accession"
            )

        retained[
            accession
        ] = biosample

    return CurrentMetadataContext(
        release_id=(
            upstream.release_id
        ),
        source_snapshot_id=(
            upstream.source_snapshot_id
        ),
        stage1_root=(
            upstream.stage1_root
        ),
        source_snapshot_record_sha256=(
            upstream.snapshot_sha256
        ),
        metadata_record_sha256=(
            record_sha
        ),
        metadata_completion_sha256=(
            hashlib.sha256(
                completion
            ).hexdigest()
        ),
        retained_metadata=retained,
    )


def metadata_context_identity(
    context: CurrentMetadataContext,
) -> tuple[
    object,
    ...,
]:
    return (
        context.release_id,
        context.source_snapshot_id,
        str(
            context.stage1_root
        ),
        context.source_snapshot_record_sha256,
        context.metadata_record_sha256,
        context.metadata_completion_sha256,
        tuple(
            sorted(
                context.retained_metadata.items()
            )
        ),
    )


def catalogue_chain_payload(
    chain: Sequence[
        object
    ],
) -> bytes:
    values = []

    for item in chain:
        values.append(
            {
                "catalogue_sha256":
                    validate_sha256(
                        getattr(
                            item,
                            "catalogue_sha256",
                            None,
                        ),
                        label="catalogue-chain SHA256",
                    ),
                "origin_git_commit":
                    validate_git_commit(
                        getattr(
                            item,
                            "origin_git_commit",
                            None,
                        ),
                        label="catalogue-chain Git commit",
                    ),
                "release_id":
                    validate_release_id(
                        getattr(
                            item,
                            "release_id",
                            None,
                        )
                    ),
            }
        )

    return canonical_json_bytes(
        {
            "catalogues":
                values,
            "schema_version":
                (
                    "bacselect-monthly-cache-verification-"
                    "catalogue-chain-v1"
                ),
        }
    )


def catalogue_chain_sha256(
    chain: Sequence[
        object
    ],
) -> str:
    return hashlib.sha256(
        catalogue_chain_payload(
            chain
        )
    ).hexdigest()


def discover_prior_catalogue_chain(
    *,
    repo: Path,
    production_root: Path,
    current_release_id: str,
) -> tuple[
    object,
    ...,
]:
    catalogue_execution = (
        load_frozen_catalogue_execution(
            Path(
                repo
            ).resolve()
        )
    )

    try:
        return tuple(
            catalogue_execution.discover_catalogue_chain(
                Path(
                    production_root
                ),
                current_release_id=(
                    current_release_id
                ),
            )
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "prior sequence-cache catalogue discovery failed"
        ) from exc


def prove_no_prior_sequence_evidence(
    production_root: Path,
    *,
    current_release_id: str,
) -> None:
    root = _require_real_directory(
        production_root,
        label="production root",
    )

    current_ordinal = release_ordinal(
        current_release_id
    )

    evidence_names = (
        "sequence-acquisition",
        "sequence-acquisition-completion.json",
        "sequence-cache-catalogue.json",
    )

    for release_entry in sorted(
        root.iterdir(),
        key=lambda item:
            item.name,
    ):
        if RELEASE_RE.fullmatch(
            release_entry.name
        ) is None:
            continue

        if (
            release_ordinal(
                release_entry.name
            )
            >= current_ordinal
        ):
            continue

        if release_entry.is_symlink():
            raise MonthlyCacheVerificationExecutionError(
                "prior release directory is a symbolic link"
            )

        if not release_entry.is_dir():
            raise MonthlyCacheVerificationExecutionError(
                "prior release entry is not a directory"
            )

        production = (
            release_entry
            / "production"
        )

        if not os.path.lexists(
            production
        ):
            continue

        if (
            production.is_symlink()
            or not production.is_dir()
        ):
            raise MonthlyCacheVerificationExecutionError(
                "prior production directory is not a real directory"
            )

        for commit_entry in production.iterdir():
            if COMMIT_RE.fullmatch(
                commit_entry.name
            ) is None:
                continue

            if commit_entry.is_symlink():
                raise MonthlyCacheVerificationExecutionError(
                    "prior production commit directory is a symbolic link"
                )

            if not commit_entry.is_dir():
                raise MonthlyCacheVerificationExecutionError(
                    "prior production commit entry is not a directory"
                )

            for name in evidence_names:
                path = (
                    commit_entry
                    / name
                )

                if os.path.lexists(
                    path
                ):
                    raise MonthlyCacheVerificationExecutionError(
                        "prior monthly sequence evidence exists "
                        "without an authoritative catalogue chain"
                    )


def _object_path(
    authoritative_root: Path,
    sha256: str,
) -> Path:
    digest = validate_sha256(
        sha256,
        label="authoritative object SHA256",
    )

    key = (
        authoritative_storage.object_key_for_sha256(
            digest
        )
    )

    return (
        Path(
            authoritative_root
        )
        / PurePosixPath(
            key
        )
    )


def _check_object_path_chain(
    authoritative_root: Path,
    object_path: Path,
) -> None:
    root = _require_real_directory(
        authoritative_root,
        label="authoritative object root",
    )

    try:
        relative = (
            object_path.relative_to(
                root
            )
        )
    except ValueError as exc:
        raise MonthlyCacheVerificationExecutionError(
            "authoritative object escaped object root"
        ) from exc

    current = root

    for part in relative.parts[
        :-1
    ]:
        current = (
            current
            / part
        )

        if not os.path.lexists(
            current
        ):
            return

        metadata = os.lstat(
            current
        )

        if stat.S_ISLNK(
            metadata.st_mode
        ):
            raise MonthlyCacheVerificationExecutionError(
                "authoritative object namespace contains a symlink"
            )

        if not stat.S_ISDIR(
            metadata.st_mode
        ):
            raise MonthlyCacheVerificationExecutionError(
                "authoritative object namespace contains a non-directory parent"
            )


def read_required_object(
    authoritative_root: Path,
    *,
    sha256: str,
    expected_size_bytes: int | None = None,
    label: str,
) -> RequiredObject:
    root = _require_real_directory(
        authoritative_root,
        label="authoritative object root",
    )

    path = _object_path(
        root,
        sha256,
    )

    _check_object_path_chain(
        root,
        path,
    )

    file_path = _require_regular_file(
        path,
        label=label,
    )

    payload = file_path.read_bytes()

    observed_sha = hashlib.sha256(
        payload
    ).hexdigest()

    if observed_sha != sha256:
        raise MonthlyCacheVerificationExecutionError(
            f"{label} SHA256 mismatch"
        )

    if (
        expected_size_bytes
        is not None
        and len(
            payload
        )
        != expected_size_bytes
    ):
        raise MonthlyCacheVerificationExecutionError(
            f"{label} size mismatch"
        )

    return RequiredObject(
        path=file_path,
        payload=payload,
        size_bytes=len(
            payload
        ),
        sha256=observed_sha,
    )


def observe_optional_object(
    authoritative_root: Path,
    *,
    sha256: str,
) -> OptionalObject:
    root = _require_real_directory(
        authoritative_root,
        label="authoritative object root",
    )

    path = _object_path(
        root,
        sha256,
    )

    _check_object_path_chain(
        root,
        path,
    )

    if not os.path.lexists(
        path
    ):
        return OptionalObject(
            path=path,
            payload=None,
            observed_size_bytes=None,
            observed_sha256=None,
        )

    metadata = os.lstat(
        path
    )

    if (
        stat.S_ISLNK(
            metadata.st_mode
        )
        or not stat.S_ISREG(
            metadata.st_mode
        )
    ):
        raise MonthlyCacheVerificationExecutionError(
            "accession package object is not a regular non-symlink file"
        )

    payload = path.read_bytes()

    return OptionalObject(
        path=path.resolve(),
        payload=payload,
        observed_size_bytes=len(
            payload
        ),
        observed_sha256=(
            hashlib.sha256(
                payload
            ).hexdigest()
        ),
    )


def _artifact_reference_object(
    authoritative_root: Path,
    reference: Mapping[
        str,
        object,
    ],
    *,
    label: str,
) -> RequiredObject:
    if not isinstance(
        reference,
        Mapping,
    ):
        raise MonthlyCacheVerificationExecutionError(
            f"{label} reference is malformed"
        )

    try:
        expected_size = int(
            reference[
                "size_bytes"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlyCacheVerificationExecutionError(
            f"{label} size reference is malformed"
        ) from exc

    if expected_size < 0:
        raise MonthlyCacheVerificationExecutionError(
            f"{label} size reference is negative"
        )

    return read_required_object(
        authoritative_root,
        sha256=validate_sha256(
            reference.get(
                "sha256"
            ),
            label=f"{label} SHA256",
        ),
        expected_size_bytes=(
            expected_size
        ),
        label=label,
    )


def _parse_json_object(
    payload: bytes,
    *,
    label: str,
) -> Mapping[
    str,
    object,
]:
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
        raise MonthlyCacheVerificationExecutionError(
            f"{label} is invalid JSON"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise MonthlyCacheVerificationExecutionError(
            f"{label} must be a JSON object"
        )

    return value


def _is_accession_scoped_package_path(
    value: str,
) -> bool:
    parts = PurePosixPath(
        value
    ).parts

    return (
        len(
            parts
        )
        > 3
        and parts[
            :2
        ]
        == (
            "ncbi_dataset",
            "data",
        )
        and CANONICAL_GCA_RE.fullmatch(
            parts[
                2
            ]
        )
        is not None
    )


def load_batch_evidence(
    authoritative_root: Path,
    *,
    provenance: Mapping[
        str,
        object,
    ],
) -> BatchEvidence:
    if not isinstance(
        provenance,
        Mapping,
    ):
        raise MonthlyCacheVerificationExecutionError(
            "catalogue batch provenance is malformed"
        )

    batch_id = str(
        provenance.get(
            "batch_id",
            "",
        )
    )

    summary = _artifact_reference_object(
        authoritative_root,
        provenance[
            "batch_summary"
        ],
        label=f"{batch_id} batch summary",
    )

    candidate = _artifact_reference_object(
        authoritative_root,
        provenance[
            "candidate_audit"
        ],
        label=f"{batch_id} candidate audit",
    )

    component = _artifact_reference_object(
        authoritative_root,
        provenance[
            "component_audit"
        ],
        label=f"{batch_id} component audit",
    )

    package = _artifact_reference_object(
        authoritative_root,
        provenance[
            "package_files_manifest"
        ],
        label=f"{batch_id} package-files manifest",
    )

    completion_sha = validate_sha256(
        provenance.get(
            "origin_sequence_acquisition_completion_sha256"
        ),
        label="origin sequence-acquisition completion SHA256",
    )

    completion = read_required_object(
        authoritative_root,
        sha256=completion_sha,
        label=f"{batch_id} origin sequence-acquisition completion",
    )

    summary_auditor = getattr(
        completion_contract,
        "_audit_transport_summary",
        None,
    )

    if not callable(
        summary_auditor
    ):
        raise MonthlyCacheVerificationExecutionError(
            "frozen transport-summary auditor disappeared"
        )

    try:
        summary_record = summary_auditor(
            summary.payload
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "origin Stage 3B batch-summary audit failed"
        ) from exc

    comparisons = (
        (
            summary_record.get(
                "source_snapshot_id"
            ),
            provenance.get(
                "cache_origin_source_snapshot_id"
            ),
            "source snapshot",
        ),
        (
            summary_record.get(
                "origin_git_commit"
            ),
            provenance.get(
                "cache_origin_git_commit"
            ),
            "Git commit",
        ),
        (
            summary_record.get(
                "requested_accessions"
            ),
            provenance.get(
                "requested_accessions"
            ),
            "requested accession count",
        ),
        (
            summary_record.get(
                "accessions_sha256"
            ),
            provenance.get(
                "accessions_sha256"
            ),
            "accession-list SHA256",
        ),
        (
            summary_record.get(
                "candidate_sequence_audit_sha256"
            ),
            provenance[
                "candidate_audit"
            ][
                "sha256"
            ],
            "candidate-audit SHA256",
        ),
        (
            summary_record.get(
                "component_sequence_audit_sha256"
            ),
            provenance[
                "component_audit"
            ][
                "sha256"
            ],
            "component-audit SHA256",
        ),
        (
            summary_record.get(
                "package_files_sha256"
            ),
            provenance[
                "package_files_manifest"
            ][
                "sha256"
            ],
            "package-files SHA256",
        ),
    )

    if summary_record.get(
        "result"
    ) != "PASS":
        raise MonthlyCacheVerificationExecutionError(
            "origin batch summary is not PASS"
        )

    for observed, expected, label in comparisons:
        if observed != expected:
            raise MonthlyCacheVerificationExecutionError(
                f"origin batch summary {label} changed"
            )

    completion_auditor = getattr(
        catalogue_contract,
        "_audit_completion_record",
        None,
    )

    if not callable(
        completion_auditor
    ):
        raise MonthlyCacheVerificationExecutionError(
            "frozen catalogue completion auditor disappeared"
        )

    try:
        completion_record = completion_auditor(
            completion.payload,
            release_id=str(
                provenance[
                    "cache_origin_release_id"
                ]
            ),
            source_snapshot_id=str(
                provenance[
                    "cache_origin_source_snapshot_id"
                ]
            ),
            origin_git_commit=str(
                provenance[
                    "cache_origin_git_commit"
                ]
            ),
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "origin sequence-acquisition completion audit failed"
        ) from exc

    completion_batches = completion_record.get(
        "batches"
    )

    if not isinstance(
        completion_batches,
        list,
    ):
        raise MonthlyCacheVerificationExecutionError(
            "origin completion batch list is malformed"
        )

    matching = [
        row
        for row in completion_batches
        if (
            isinstance(
                row,
                dict,
            )
            and row.get(
                "batch_id"
            )
            == batch_id
        )
    ]

    if len(
        matching
    ) != 1:
        raise MonthlyCacheVerificationExecutionError(
            "origin completion does not contain exactly one matching batch"
        )

    completion_batch = matching[
        0
    ]

    completion_comparisons = (
        (
            completion_batch.get(
                "requested_accessions"
            ),
            provenance.get(
                "requested_accessions"
            ),
            "requested accession count",
        ),
        (
            completion_batch.get(
                "accessions_sha256"
            ),
            provenance.get(
                "accessions_sha256"
            ),
            "accession-list SHA256",
        ),
        (
            completion_batch.get(
                "batch_summary_sha256"
            ),
            provenance[
                "batch_summary"
            ][
                "sha256"
            ],
            "batch-summary SHA256",
        ),
        (
            completion_batch.get(
                "candidate_sequence_audit_sha256"
            ),
            provenance[
                "candidate_audit"
            ][
                "sha256"
            ],
            "candidate-audit SHA256",
        ),
        (
            completion_batch.get(
                "component_sequence_audit_sha256"
            ),
            provenance[
                "component_audit"
            ][
                "sha256"
            ],
            "component-audit SHA256",
        ),
        (
            completion_batch.get(
                "package_files_sha256"
            ),
            provenance[
                "package_files_manifest"
            ][
                "sha256"
            ],
            "package-files SHA256",
        ),
        (
            completion_batch.get(
                "package_file_readback_sha256"
            ),
            provenance.get(
                "origin_package_file_readback_sha256"
            ),
            "package read-back SHA256",
        ),
    )

    for observed, expected, label in completion_comparisons:
        if observed != expected:
            raise MonthlyCacheVerificationExecutionError(
                f"origin completion {label} changed"
            )

    parser = getattr(
        catalogue_contract,
        "_parse_tsv",
        None,
    )

    if not callable(
        parser
    ):
        raise MonthlyCacheVerificationExecutionError(
            "frozen catalogue TSV parser disappeared"
        )

    try:
        candidate_rows = tuple(
            parser(
                candidate.payload,
                fields=CANDIDATE_AUDIT_FIELDS,
                label="candidate audit",
            )
        )

        component_rows = tuple(
            parser(
                component.payload,
                fields=COMPONENT_AUDIT_FIELDS,
                label="component audit",
            )
        )

        package_rows = tuple(
            parser(
                package.payload,
                fields=PACKAGE_FILE_FIELDS,
                label="package-files manifest",
            )
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "origin Stage 3 evidence TSV audit failed"
        ) from exc

    seen_paths = set()

    for row in package_rows:
        path = row[
            "path"
        ]

        if path in seen_paths:
            raise MonthlyCacheVerificationExecutionError(
                "origin package manifest contains duplicate paths"
            )

        seen_paths.add(
            path
        )

        if _is_accession_scoped_package_path(
            path
        ):
            continue

        try:
            size = int(
                row[
                    "size_bytes"
                ]
            )
        except ValueError as exc:
            raise MonthlyCacheVerificationExecutionError(
                "batch-common package size is invalid"
            ) from exc

        read_required_object(
            authoritative_root,
            sha256=validate_sha256(
                row[
                    "sha256"
                ],
                label="batch-common package SHA256",
            ),
            expected_size_bytes=size,
            label="batch-common package object",
        )

    return BatchEvidence(
        provenance=provenance,
        candidate_rows=(
            candidate_rows
        ),
        component_rows=(
            component_rows
        ),
        package_rows=(
            package_rows
        ),
    )


def _candidate_row_for_accession(
    batch: BatchEvidence,
    accession: str,
) -> Mapping[
    str,
    str,
]:
    rows = [
        row
        for row in batch.candidate_rows
        if row[
            "canonical_genbank_assembly_accession"
        ]
        == accession
    ]

    if len(
        rows
    ) != 1:
        raise MonthlyCacheVerificationExecutionError(
            "origin candidate audit does not contain exactly one accession row"
        )

    return rows[
        0
    ]


def _component_rows_for_accession(
    batch: BatchEvidence,
    accession: str,
) -> tuple[
    Mapping[
        str,
        str,
    ],
    ...,
]:
    rows = tuple(
        row
        for row in batch.component_rows
        if row[
            "canonical_genbank_assembly_accession"
        ]
        == accession
    )

    if not rows:
        raise MonthlyCacheVerificationExecutionError(
            "origin component audit has no rows for candidate"
        )

    accessions = [
        row[
            "component_genbank_accession"
        ]
        for row in rows
    ]

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlyCacheVerificationExecutionError(
            "origin component audit contains duplicate component accessions"
        )

    return rows


def _package_rows_for_accession(
    batch: BatchEvidence,
    accession: str,
) -> tuple[
    Mapping[
        str,
        str,
    ],
    ...,
]:
    prefix = (
        "ncbi_dataset",
        "data",
        accession,
    )

    return tuple(
        row
        for row in batch.package_rows
        if (
            len(
                PurePosixPath(
                    row[
                        "path"
                    ]
                ).parts
            )
            > 3
            and PurePosixPath(
                row[
                    "path"
                ]
            ).parts[
                :3
            ]
            == prefix
        )
    )


def materialize_candidate(
    authoritative_root: Path,
    *,
    entry: Mapping[
        str,
        object,
    ],
    batch: BatchEvidence,
) -> MonthlyCacheCandidate:
    accession = str(
        entry[
            "canonical_genbank_assembly_accession"
        ]
    )

    biosample = str(
        entry[
            "biosample"
        ]
    )

    candidate_row = (
        _candidate_row_for_accession(
            batch,
            accession,
        )
    )

    if (
        candidate_row[
            "expected_biosample"
        ]
        != biosample
        or candidate_row[
            "observed_biosample"
        ]
        != biosample
    ):
        raise MonthlyCacheVerificationExecutionError(
            "origin candidate BioSample differs from catalogue entry"
        )

    if (
        candidate_row[
            "sequence_eligibility"
        ]
        != "eligible"
        or candidate_row[
            "exclusion_reasons"
        ]
        != "none"
        or candidate_row[
            "result"
        ]
        != "PASS"
    ):
        raise MonthlyCacheVerificationExecutionError(
            "origin eligible catalogue entry disagrees with candidate audit"
        )

    fasta_file = candidate_row[
        "fasta_file"
    ]

    if (
        not fasta_file
        or PurePosixPath(
            fasta_file
        ).name
        != fasta_file
    ):
        raise MonthlyCacheVerificationExecutionError(
            "origin candidate FASTA file is not a basename"
        )

    fasta_sha = validate_sha256(
        candidate_row[
            "fasta_sha256"
        ],
        label="origin candidate FASTA SHA256",
    )

    try:
        primary_count = int(
            candidate_row[
                "primary_assembly_records"
            ]
        )
    except ValueError as exc:
        raise MonthlyCacheVerificationExecutionError(
            "origin Primary Assembly component count is invalid"
        ) from exc

    if primary_count <= 0:
        raise MonthlyCacheVerificationExecutionError(
            "origin Primary Assembly component count is not positive"
        )

    component_rows = (
        _component_rows_for_accession(
            batch,
            accession,
        )
    )

    if len(
        component_rows
    ) != primary_count:
        raise MonthlyCacheVerificationExecutionError(
            "origin Primary Assembly component count changed"
        )

    package_rows = (
        _package_rows_for_accession(
            batch,
            accession,
        )
    )

    manifest_by_path = {
        row[
            "path"
        ]:
            row
        for row in package_rows
    }

    if len(
        manifest_by_path
    ) != len(
        package_rows
    ):
        raise MonthlyCacheVerificationExecutionError(
            "origin accession package manifest contains duplicate paths"
        )

    artifacts_value = entry[
        "package_artifacts"
    ]

    if not isinstance(
        artifacts_value,
        list,
    ):
        raise MonthlyCacheVerificationExecutionError(
            "catalogue entry package artifacts are malformed"
        )

    artifacts = tuple(
        artifacts_value
    )

    artifact_by_path = {
        str(
            artifact[
                "package_path"
            ]
        ):
            artifact
        for artifact in artifacts
    }

    if len(
        artifact_by_path
    ) != len(
        artifacts
    ):
        raise MonthlyCacheVerificationExecutionError(
            "catalogue entry package artifact paths are duplicated"
        )

    if set(
        artifact_by_path
    ) != set(
        manifest_by_path
    ):
        raise MonthlyCacheVerificationExecutionError(
            "catalogue accession package set differs from "
            "authenticated package manifest"
        )

    observations = []

    fasta_observation = None

    for path in sorted(
        artifact_by_path
    ):
        artifact = artifact_by_path[
            path
        ]

        manifest = manifest_by_path[
            path
        ]

        try:
            manifest_size = int(
                manifest[
                    "size_bytes"
                ]
            )
        except ValueError as exc:
            raise MonthlyCacheVerificationExecutionError(
                "origin package manifest size is invalid"
            ) from exc

        artifact_size = artifact[
            "size_bytes"
        ]

        if (
            isinstance(
                artifact_size,
                bool,
            )
            or not isinstance(
                artifact_size,
                int,
            )
        ):
            raise MonthlyCacheVerificationExecutionError(
                "catalogue package artifact size is invalid"
            )

        if (
            artifact_size
            != manifest_size
            or artifact[
                "sha256"
            ]
            != manifest[
                "sha256"
            ]
        ):
            raise MonthlyCacheVerificationExecutionError(
                "catalogue package artifact identity differs "
                "from authenticated package manifest"
            )

        expected_sha = validate_sha256(
            artifact[
                "sha256"
            ],
            label="catalogue package artifact SHA256",
        )

        observed = observe_optional_object(
            authoritative_root,
            sha256=(
                expected_sha
            ),
        )

        observation = (
            MonthlyCachePackageFileObservation(
                path=path,
                expected_size_bytes=(
                    artifact_size
                ),
                expected_sha256=(
                    expected_sha
                ),
                observed_size_bytes=(
                    observed.observed_size_bytes
                ),
                observed_sha256=(
                    observed.observed_sha256
                ),
            )
        )

        observations.append(
            observation
        )

        if (
            PurePosixPath(
                path
            ).name
            == fasta_file
            and expected_sha
            == fasta_sha
        ):
            if fasta_observation is not None:
                raise MonthlyCacheVerificationExecutionError(
                    "candidate FASTA resolves to multiple package artifacts"
                )

            fasta_observation = (
                observed,
                observation,
            )

    if fasta_observation is None:
        raise MonthlyCacheVerificationExecutionError(
            "candidate FASTA is absent from catalogue package artifacts"
        )

    observed_fasta, fasta_package = (
        fasta_observation
    )

    fasta_is_exact = (
        observed_fasta.payload
        is not None
        and fasta_package.observed_size_bytes
        == fasta_package.expected_size_bytes
        and fasta_package.observed_sha256
        == fasta_package.expected_sha256
    )

    sequences: Mapping[
        str,
        str,
    ] = {}

    if fasta_is_exact:
        parser = getattr(
            source_truth_execution,
            "_parse_fasta",
            None,
        )

        if not callable(
            parser
        ):
            raise MonthlyCacheVerificationExecutionError(
                "frozen source-truth FASTA parser disappeared"
            )

        try:
            sequences = parser(
                observed_fasta.path
            )
        except Exception as exc:
            raise MonthlyCacheVerificationExecutionError(
                "exact origin FASTA object is no longer parseable"
            ) from exc

    components = []

    for row in sorted(
        component_rows,
        key=lambda item:
            item[
                "component_genbank_accession"
            ],
    ):
        component_accession = row[
            "component_genbank_accession"
        ]

        try:
            length = int(
                row[
                    "length"
                ]
            )
        except ValueError as exc:
            raise MonthlyCacheVerificationExecutionError(
                "origin component length is invalid"
            ) from exc

        sequence_sha = validate_sha256(
            row[
                "sequence_sha256"
            ],
            label="origin component sequence SHA256",
        )

        sequence = ""

        if fasta_is_exact:
            observed_sequence = sequences.get(
                component_accession
            )

            if observed_sequence is None:
                raise MonthlyCacheVerificationExecutionError(
                    "exact origin FASTA lacks an authenticated component"
                )

            sequence = observed_sequence

        components.append(
            MonthlyCacheComponent(
                component_accession=(
                    component_accession
                ),
                length=length,
                topology=row[
                    "topology"
                ],
                sequence_sha256=(
                    sequence_sha
                ),
                sequence=sequence,
            )
        )

    provenance = batch.provenance

    return MonthlyCacheCandidate(
        canonical_genbank_assembly_accession=(
            accession
        ),
        biosample=(
            biosample
        ),
        cache_origin_release_id=str(
            provenance[
                "cache_origin_release_id"
            ]
        ),
        cache_origin_source_snapshot_id=str(
            provenance[
                "cache_origin_source_snapshot_id"
            ]
        ),
        cache_origin_git_commit=str(
            provenance[
                "cache_origin_git_commit"
            ]
        ),
        origin_batch_summary_sha256=str(
            provenance[
                "batch_summary"
            ][
                "sha256"
            ]
        ),
        origin_candidate_audit_sha256=str(
            provenance[
                "candidate_audit"
            ][
                "sha256"
            ]
        ),
        origin_component_audit_sha256=str(
            provenance[
                "component_audit"
            ][
                "sha256"
            ]
        ),
        origin_package_files_sha256=str(
            provenance[
                "package_files_manifest"
            ][
                "sha256"
            ]
        ),
        batch_provenance_verified=True,
        candidate_fasta_file=(
            fasta_file
        ),
        candidate_fasta_sha256=(
            fasta_sha
        ),
        primary_assembly_records=(
            primary_count
        ),
        components=tuple(
            components
        ),
        package_files=tuple(
            observations
        ),
    )


def materialize_cache_candidates(
    authoritative_root: Path,
    *,
    catalogue_record: Mapping[
        str,
        object,
    ],
    current_metadata: Mapping[
        str,
        str,
    ],
) -> CandidateMaterialization:
    if not isinstance(
        catalogue_record,
        Mapping,
    ):
        raise MonthlyCacheVerificationExecutionError(
            "source catalogue record is malformed"
        )

    batch_values = catalogue_record.get(
        "batch_provenance"
    )

    entry_values = catalogue_record.get(
        "entries"
    )

    if (
        not isinstance(
            batch_values,
            list,
        )
        or not isinstance(
            entry_values,
            list,
        )
    ):
        raise MonthlyCacheVerificationExecutionError(
            "source catalogue batch/entry structures are malformed"
        )

    provenance_by_sha = {}

    for row in batch_values:
        if not isinstance(
            row,
            Mapping,
        ):
            raise MonthlyCacheVerificationExecutionError(
                "source catalogue batch provenance row is malformed"
            )

        digest = validate_sha256(
            row.get(
                "batch_provenance_sha256"
            ),
            label="batch-provenance SHA256",
        )

        if digest in provenance_by_sha:
            raise MonthlyCacheVerificationExecutionError(
                "duplicate source catalogue batch provenance"
            )

        provenance_by_sha[
            digest
        ] = row

    batch_cache: dict[
        str,
        BatchEvidence,
    ] = {}

    candidates = []

    expected_count = 0

    seen = set()

    for entry in entry_values:
        if not isinstance(
            entry,
            Mapping,
        ):
            raise MonthlyCacheVerificationExecutionError(
                "source catalogue entry is malformed"
            )

        accession = str(
            entry.get(
                "canonical_genbank_assembly_accession",
                "",
            )
        )

        if accession in seen:
            raise MonthlyCacheVerificationExecutionError(
                "duplicate accession in source catalogue reconstruction"
            )

        seen.add(
            accession
        )

        if accession not in current_metadata:
            continue

        if (
            entry.get(
                "origin_sequence_eligibility"
            )
            != "eligible"
            or entry.get(
                "origin_sequence_exclusion_reasons"
            )
            != "none"
        ):
            continue

        expected_count += 1

        provenance_sha = validate_sha256(
            entry.get(
                "origin_batch_provenance_sha256"
            ),
            label="entry origin batch-provenance SHA256",
        )

        provenance = provenance_by_sha.get(
            provenance_sha
        )

        if provenance is None:
            raise MonthlyCacheVerificationExecutionError(
                "catalogue entry references missing batch provenance"
            )

        batch = batch_cache.get(
            provenance_sha
        )

        if batch is None:
            batch = load_batch_evidence(
                authoritative_root,
                provenance=(
                    provenance
                ),
            )

            batch_cache[
                provenance_sha
            ] = batch

        candidates.append(
            materialize_candidate(
                authoritative_root,
                entry=entry,
                batch=batch,
            )
        )

    candidates = sorted(
        candidates,
        key=lambda item:
            item.canonical_genbank_assembly_accession,
    )

    if len(
        candidates
    ) != expected_count:
        raise MonthlyCacheVerificationExecutionError(
            "cache-candidate reconstruction is incomplete"
        )

    if len(
        {
            item.canonical_genbank_assembly_accession
            for item in candidates
        }
    ) != len(
        candidates
    ):
        raise MonthlyCacheVerificationExecutionError(
            "cache-candidate reconstruction contains duplicates"
        )

    return CandidateMaterialization(
        candidates=tuple(
            candidates
        ),
        retained_origin_eligible_count=(
            expected_count
        ),
    )


def _verify_and_serialize(
    materialization: CandidateMaterialization,
    *,
    current_source_snapshot_id: str,
    current_metadata: Mapping[
        str,
        str,
    ],
    source_snapshot_record_sha256: str,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
) -> tuple[
    bytes,
    bytes,
    bytes,
    Mapping[
        str,
        object,
    ],
]:
    try:
        build = verify_cache_candidates(
            materialization.candidates,
            current_source_snapshot_id=(
                current_source_snapshot_id
            ),
            current_metadata=(
                current_metadata
            ),
        )

        results_payload = (
            serialize_cache_verification_results(
                build.results
            )
        )

        verified_payload = (
            serialize_verified_cache_evidence(
                build.verified_cache
            )
        )

        record_payload = (
            serialize_cache_verification_record(
                source_snapshot_id=(
                    current_source_snapshot_id
                ),
                source_snapshot_record_sha256=(
                    source_snapshot_record_sha256
                ),
                metadata_record_sha256=(
                    metadata_record_sha256
                ),
                metadata_completion_sha256=(
                    metadata_completion_sha256
                ),
                retained_count=len(
                    current_metadata
                ),
                results_payload=(
                    results_payload
                ),
                verified_cache_payload=(
                    verified_payload
                ),
            )
        )

        audit_cache_verification_results(
            results_payload
        )

        audit_verified_cache_evidence(
            verified_payload
        )

        record = audit_cache_verification_record(
            record_payload,
            source_snapshot_id=(
                current_source_snapshot_id
            ),
            source_snapshot_record_sha256=(
                source_snapshot_record_sha256
            ),
            metadata_record_sha256=(
                metadata_record_sha256
            ),
            metadata_completion_sha256=(
                metadata_completion_sha256
            ),
            retained_count=len(
                current_metadata
            ),
            results_payload=(
                results_payload
            ),
            verified_cache_payload=(
                verified_payload
            ),
        )
    except (
        MonthlyCacheVerificationError,
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlyCacheVerificationExecutionError(
            "frozen cache-verification contract failed"
        ) from exc

    return (
        results_payload,
        verified_payload,
        record_payload,
        record,
    )


def _nonnegative_int(
    value: object,
    *,
    label: str,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 0
    ):
        raise MonthlyCacheVerificationExecutionError(
            f"{label} must be a non-negative integer"
        )

    return value


def build_completion_receipt(
    *,
    release_id: str,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    execution_commit: str,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
    retained_count: int,
    catalogue_history_mode: str,
    catalogue_chain_count: int,
    catalogue_chain_sha256_value: str,
    source_catalogue_release_id: str | None,
    source_catalogue_sha256: str | None,
    source_catalogue_entries_sha256: str | None,
    source_catalogue_entry_count: int,
    candidate_input_count: int,
    verified_cache_count: int,
    fallback_to_fresh_count: int,
    results_sha256: str,
    verified_cache_evidence_sha256: str,
    record_sha256: str,
) -> bytes:
    release = validate_release_id(
        release_id
    )

    if (
        not isinstance(
            source_snapshot_id,
            str,
        )
        or not source_snapshot_id
        or source_snapshot_id
        != source_snapshot_id.strip()
        or any(
            character.isspace()
            for character in source_snapshot_id
        )
    ):
        raise MonthlyCacheVerificationExecutionError(
            "completion source snapshot ID is invalid"
        )

    commit = validate_git_commit(
        execution_commit,
        label="completion execution commit",
    )

    retained = _nonnegative_int(
        retained_count,
        label="completion retained count",
    )

    chain_count = _nonnegative_int(
        catalogue_chain_count,
        label="completion catalogue-chain count",
    )

    source_count = _nonnegative_int(
        source_catalogue_entry_count,
        label="completion source-catalogue entry count",
    )

    candidate_count = _nonnegative_int(
        candidate_input_count,
        label="completion candidate-input count",
    )

    verified_count = _nonnegative_int(
        verified_cache_count,
        label="completion verified-cache count",
    )

    fallback_count = _nonnegative_int(
        fallback_to_fresh_count,
        label="completion fallback count",
    )

    if candidate_count != (
        verified_count
        + fallback_count
    ):
        raise MonthlyCacheVerificationExecutionError(
            "completion cache-result accounting changed"
        )

    if candidate_count > retained:
        raise MonthlyCacheVerificationExecutionError(
            "completion candidate count exceeds retained count"
        )

    if catalogue_history_mode == HISTORY_NONE:
        if (
            chain_count != 0
            or source_catalogue_release_id
            is not None
            or source_catalogue_sha256
            is not None
            or source_catalogue_entries_sha256
            is not None
            or source_count != 0
        ):
            raise MonthlyCacheVerificationExecutionError(
                "first-release completion contains source-catalogue provenance"
            )

        source_release = None
        source_sha = None
        entries_sha = None

    elif catalogue_history_mode == HISTORY_CHAINED:
        if chain_count <= 0:
            raise MonthlyCacheVerificationExecutionError(
                "chained completion has empty catalogue chain"
            )

        source_release = validate_release_id(
            source_catalogue_release_id
        )

        if (
            release_ordinal(
                source_release
            )
            >= release_ordinal(
                release
            )
        ):
            raise MonthlyCacheVerificationExecutionError(
                "source catalogue is not earlier than current release"
            )

        source_sha = validate_sha256(
            source_catalogue_sha256,
            label="source catalogue SHA256",
        )

        entries_sha = validate_sha256(
            source_catalogue_entries_sha256,
            label="source catalogue entry-set SHA256",
        )

    else:
        raise MonthlyCacheVerificationExecutionError(
            "completion catalogue-history mode is invalid"
        )

    return canonical_json_bytes(
        {
            "candidate_input_count":
                candidate_count,
            "catalogue_chain_count":
                chain_count,
            "catalogue_chain_sha256":
                validate_sha256(
                    catalogue_chain_sha256_value,
                    label="catalogue-chain SHA256",
                ),
            "catalogue_history_mode":
                catalogue_history_mode,
            "execution_commit":
                commit,
            "fallback_to_fresh_count":
                fallback_count,
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
            "record_sha256":
                validate_sha256(
                    record_sha256,
                    label="cache-verification record SHA256",
                ),
            "release_id":
                release,
            "results_sha256":
                validate_sha256(
                    results_sha256,
                    label="cache-verification results SHA256",
                ),
            "retained_count":
                retained,
            "schema_version":
                COMPLETION_SCHEMA,
            "source_catalogue_entries_sha256":
                entries_sha,
            "source_catalogue_entry_count":
                source_count,
            "source_catalogue_release_id":
                source_release,
            "source_catalogue_sha256":
                source_sha,
            "source_snapshot_id":
                source_snapshot_id,
            "source_snapshot_record_sha256":
                validate_sha256(
                    source_snapshot_record_sha256,
                    label="source-snapshot-record SHA256",
                ),
            "status":
                COMPLETION_STATUS,
            "verified_cache_count":
                verified_count,
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
            "cache-verification completion receipt must be bytes"
        )

    expected = build_completion_receipt(
        **kwargs
    )

    if payload != expected:
        raise MonthlyCacheVerificationExecutionError(
            "cache-verification completion receipt changed"
        )

    return _parse_json_object(
        payload,
        label="cache-verification completion receipt",
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
        raise MonthlyCacheVerificationExecutionError(
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

        offset = 0

        while offset < len(
            payload
        ):
            written = os.write(
                descriptor,
                payload[
                    offset:
                ],
            )

            if written <= 0:
                raise MonthlyCacheVerificationExecutionError(
                    f"short write for artifact: {path.name}"
                )

            offset += written

        os.fsync(
            descriptor
        )
    finally:
        os.close(
            descriptor
        )

    if path.read_bytes() != payload:
        raise MonthlyCacheVerificationExecutionError(
            f"artifact readback mismatch: {path.name}"
        )

    if stat.S_IMODE(
        path.stat().st_mode
    ) != 0o644:
        raise MonthlyCacheVerificationExecutionError(
            f"artifact mode mismatch: {path.name}"
        )


def create_partial_stage(
    stage1_root: Path,
) -> tuple[
    Path,
    Path,
    Path,
]:
    final = (
        stage1_root
        / CACHE_STAGE_NAME
    )

    partial = (
        stage1_root
        / CACHE_PARTIAL_STAGE_NAME
    )

    completion = (
        stage1_root
        / COMPLETION_NAME
    )

    for path, label in (
        (
            final,
            "cache-verification stage",
        ),
        (
            partial,
            "cache-verification partial stage",
        ),
        (
            completion,
            "cache-verification completion receipt",
        ),
    ):
        if os.path.lexists(
            path
        ):
            raise MonthlyCacheVerificationExecutionError(
                f"{label} already exists"
            )

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    os.chmod(
        partial,
        0o755,
    )

    fsync_directory(
        stage1_root
    )

    return (
        partial,
        final,
        completion,
    )


def write_completion_no_clobber(
    path: Path,
    payload: bytes,
) -> None:
    temporary = (
        path.parent
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        path
    ):
        raise MonthlyCacheVerificationExecutionError(
            "cache-verification completion receipt already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlyCacheVerificationExecutionError(
            "cache-verification completion temporary artifact already exists"
        )

    write_fresh_file(
        temporary,
        payload,
    )

    fsync_directory(
        path.parent
    )

    try:
        os.link(
            temporary,
            path,
            follow_symlinks=False,
        )
    except FileExistsError as exc:
        raise MonthlyCacheVerificationExecutionError(
            "cache-verification completion receipt appeared "
            "before publication"
        ) from exc

    fsync_directory(
        path.parent
    )

    if path.read_bytes() != payload:
        try:
            os.unlink(
                path
            )
        finally:
            fsync_directory(
                path.parent
            )

        raise MonthlyCacheVerificationExecutionError(
            "cache-verification completion readback changed"
        )

    os.unlink(
        temporary
    )

    fsync_directory(
        path.parent
    )


def _scientific_stage_payloads(
    stage: Path,
) -> tuple[
    bytes,
    bytes,
    bytes,
]:
    _require_exact_inventory(
        stage,
        expected_files={
            RESULTS_NAME,
            VERIFIED_CACHE_NAME,
            RECORD_NAME,
        },
        label="cache-verification stage",
    )

    if stat.S_IMODE(
        stage.stat().st_mode
    ) != 0o755:
        raise MonthlyCacheVerificationExecutionError(
            "cache-verification stage mode changed"
        )

    payloads = []

    for name in (
        RESULTS_NAME,
        VERIFIED_CACHE_NAME,
        RECORD_NAME,
    ):
        path = _require_regular_file(
            stage
            / name,
            label=name,
        )

        if stat.S_IMODE(
            path.stat().st_mode
        ) != 0o644:
            raise MonthlyCacheVerificationExecutionError(
                f"cache-verification artifact mode changed: {name}"
            )

        payloads.append(
            path.read_bytes()
        )

    return tuple(
        payloads
    )


def promote_scientific_stage_no_clobber(
    *,
    partial: Path,
    final: Path,
    expected_payloads: tuple[
        bytes,
        bytes,
        bytes,
    ],
) -> tuple[
    bytes,
    bytes,
    bytes,
]:
    if len(
        expected_payloads
    ) != 3:
        raise MonthlyCacheVerificationExecutionError(
            "expected scientific-stage payload count changed"
        )

    if os.path.lexists(
        final
    ):
        raise MonthlyCacheVerificationExecutionError(
            "cache-verification stage already exists"
        )

    try:
        os.mkdir(
            final,
            0o755,
        )
    except FileExistsError as exc:
        raise MonthlyCacheVerificationExecutionError(
            "cache-verification stage appeared before publication"
        ) from exc

    os.chmod(
        final,
        0o755,
    )

    fsync_directory(
        final.parent
    )

    for name in (
        RESULTS_NAME,
        VERIFIED_CACHE_NAME,
        RECORD_NAME,
    ):
        source = _require_regular_file(
            partial
            / name,
            label=f"partial {name}",
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
            raise MonthlyCacheVerificationExecutionError(
                "cache-verification artifact appeared "
                "during canonical publication"
            ) from exc

    fsync_directory(
        final
    )

    observed = (
        _scientific_stage_payloads(
            final
        )
    )

    if observed != expected_payloads:
        raise MonthlyCacheVerificationExecutionError(
            "canonical cache-verification stage changed "
            "during publication"
        )

    for name in (
        RESULTS_NAME,
        VERIFIED_CACHE_NAME,
        RECORD_NAME,
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

    return observed


def execute_monthly_cache_verification(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    authoritative_root: Path,
    execution_commit: str,
    current_context_loader: Callable[
        ...,
        CurrentMetadataContext,
    ] = load_current_metadata_context,
    chain_loader: Callable[
        ...,
        tuple[
            object,
            ...,
        ],
    ] = discover_prior_catalogue_chain,
    no_prior_evidence_prover: Callable[
        ...,
        None,
    ] = prove_no_prior_sequence_evidence,
) -> MonthlyCacheVerificationExecutionResult:
    commit = validate_git_commit(
        execution_commit,
        label="execution commit",
    )

    production = Path(
        production_root
    )

    if not production.is_absolute():
        raise MonthlyCacheVerificationExecutionError(
            "production root must be absolute"
        )

    _require_real_directory(
        production,
        label="production root",
    )

    authoritative = Path(
        authoritative_root
    )

    if not authoritative.is_absolute():
        raise MonthlyCacheVerificationExecutionError(
            "authoritative object root must be absolute"
        )

    _require_real_directory(
        authoritative,
        label="authoritative object root",
    )

    context = current_context_loader(
        repo=Path(
            repo
        ).resolve(),
        production_root=(
            production
        ),
        stage1_root=Path(
            stage1_root
        ),
        execution_commit=(
            commit
        ),
    )

    if not isinstance(
        context,
        CurrentMetadataContext,
    ):
        raise MonthlyCacheVerificationExecutionError(
            "current metadata loader returned wrong type"
        )

    chain = tuple(
        chain_loader(
            repo=Path(
                repo
            ).resolve(),
            production_root=(
                production
            ),
            current_release_id=(
                context.release_id
            ),
        )
    )

    chain_sha = catalogue_chain_sha256(
        chain
    )

    if chain:
        source_item = chain[
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
            raise MonthlyCacheVerificationExecutionError(
                "source catalogue record is unavailable"
            )

        history_mode = (
            HISTORY_CHAINED
        )

        source_release_id = getattr(
            source_item,
            "release_id",
            None,
        )

        source_catalogue_sha = validate_sha256(
            getattr(
                source_item,
                "catalogue_sha256",
                None,
            ),
            label="source catalogue SHA256",
        )

        source_entries_sha = validate_sha256(
            source_record.get(
                "entries_sha256"
            ),
            label="source catalogue entries SHA256",
        )

        source_entry_count = _nonnegative_int(
            source_record.get(
                "catalogue_entry_count"
            ),
            label="source catalogue entry count",
        )

        materialization = (
            materialize_cache_candidates(
                authoritative,
                catalogue_record=(
                    source_record
                ),
                current_metadata=(
                    context.retained_metadata
                ),
            )
        )

    else:
        no_prior_evidence_prover(
            production,
            current_release_id=(
                context.release_id
            ),
        )

        source_item = None
        source_record = None
        history_mode = (
            HISTORY_NONE
        )
        source_release_id = None
        source_catalogue_sha = None
        source_entries_sha = None
        source_entry_count = 0

        materialization = (
            CandidateMaterialization(
                candidates=(),
                retained_origin_eligible_count=0,
            )
        )

    (
        results_payload,
        verified_payload,
        record_payload,
        cache_record,
    ) = _verify_and_serialize(
        materialization,
        current_source_snapshot_id=(
            context.source_snapshot_id
        ),
        current_metadata=(
            context.retained_metadata
        ),
        source_snapshot_record_sha256=(
            context.source_snapshot_record_sha256
        ),
        metadata_record_sha256=(
            context.metadata_record_sha256
        ),
        metadata_completion_sha256=(
            context.metadata_completion_sha256
        ),
    )

    partial, final, completion_path = (
        create_partial_stage(
            context.stage1_root
        )
    )

    write_fresh_file(
        partial
        / RESULTS_NAME,
        results_payload,
    )

    write_fresh_file(
        partial
        / VERIFIED_CACHE_NAME,
        verified_payload,
    )

    write_fresh_file(
        partial
        / RECORD_NAME,
        record_payload,
    )

    partial_results, partial_verified, partial_record = (
        _scientific_stage_payloads(
            partial
        )
    )

    if (
        partial_results
        != results_payload
        or partial_verified
        != verified_payload
        or partial_record
        != record_payload
    ):
        raise MonthlyCacheVerificationExecutionError(
            "cache-verification partial stage readback changed"
        )

    try:
        audit_cache_verification_results(
            partial_results
        )

        audit_verified_cache_evidence(
            partial_verified
        )

        audit_cache_verification_record(
            partial_record,
            source_snapshot_id=(
                context.source_snapshot_id
            ),
            source_snapshot_record_sha256=(
                context.source_snapshot_record_sha256
            ),
            metadata_record_sha256=(
                context.metadata_record_sha256
            ),
            metadata_completion_sha256=(
                context.metadata_completion_sha256
            ),
            retained_count=len(
                context.retained_metadata
            ),
            results_payload=(
                partial_results
            ),
            verified_cache_payload=(
                partial_verified
            ),
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "cache-verification partial stage audit failed"
        ) from exc

    fsync_directory(
        partial
    )

    context_again = current_context_loader(
        repo=Path(
            repo
        ).resolve(),
        production_root=(
            production
        ),
        stage1_root=Path(
            stage1_root
        ),
        execution_commit=(
            commit
        ),
    )

    if (
        not isinstance(
            context_again,
            CurrentMetadataContext,
        )
        or metadata_context_identity(
            context_again
        )
        != metadata_context_identity(
            context
        )
    ):
        raise MonthlyCacheVerificationExecutionError(
            "current metadata authority changed before publication"
        )

    chain_again = tuple(
        chain_loader(
            repo=Path(
                repo
            ).resolve(),
            production_root=(
                production
            ),
            current_release_id=(
                context.release_id
            ),
        )
    )

    if (
        catalogue_chain_sha256(
            chain_again
        )
        != chain_sha
    ):
        raise MonthlyCacheVerificationExecutionError(
            "prior catalogue chain changed before publication"
        )

    if chain_again:
        repeated_record = getattr(
            chain_again[
                -1
            ],
            "catalogue_record",
            None,
        )

        if not isinstance(
            repeated_record,
            Mapping,
        ):
            raise MonthlyCacheVerificationExecutionError(
                "repeated source catalogue record is unavailable"
            )

        repeated_materialization = (
            materialize_cache_candidates(
                authoritative,
                catalogue_record=(
                    repeated_record
                ),
                current_metadata=(
                    context_again.retained_metadata
                ),
            )
        )

    else:
        no_prior_evidence_prover(
            production,
            current_release_id=(
                context.release_id
            ),
        )

        repeated_materialization = (
            CandidateMaterialization(
                candidates=(),
                retained_origin_eligible_count=0,
            )
        )

    repeated = _verify_and_serialize(
        repeated_materialization,
        current_source_snapshot_id=(
            context_again.source_snapshot_id
        ),
        current_metadata=(
            context_again.retained_metadata
        ),
        source_snapshot_record_sha256=(
            context_again.source_snapshot_record_sha256
        ),
        metadata_record_sha256=(
            context_again.metadata_record_sha256
        ),
        metadata_completion_sha256=(
            context_again.metadata_completion_sha256
        ),
    )

    if (
        repeated[
            0
        ]
        != results_payload
        or repeated[
            1
        ]
        != verified_payload
        or repeated[
            2
        ]
        != record_payload
        or repeated_materialization.retained_origin_eligible_count
        != materialization.retained_origin_eligible_count
    ):
        raise MonthlyCacheVerificationExecutionError(
            "cache-verification reconstruction changed before publication"
        )

    (
        final_results,
        final_verified,
        final_record,
    ) = promote_scientific_stage_no_clobber(
        partial=partial,
        final=final,
        expected_payloads=(
            results_payload,
            verified_payload,
            record_payload,
        ),
    )

    if (
        final_results
        != results_payload
        or final_verified
        != verified_payload
        or final_record
        != record_payload
    ):
        raise MonthlyCacheVerificationExecutionError(
            "completed cache-verification stage readback changed"
        )

    try:
        audit_cache_verification_results(
            final_results
        )

        audit_verified_cache_evidence(
            final_verified
        )

        final_cache_record = (
            audit_cache_verification_record(
                final_record,
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                source_snapshot_record_sha256=(
                    context.source_snapshot_record_sha256
                ),
                metadata_record_sha256=(
                    context.metadata_record_sha256
                ),
                metadata_completion_sha256=(
                    context.metadata_completion_sha256
                ),
                retained_count=len(
                    context.retained_metadata
                ),
                results_payload=(
                    final_results
                ),
                verified_cache_payload=(
                    final_verified
                ),
            )
        )
    except Exception as exc:
        raise MonthlyCacheVerificationExecutionError(
            "completed cache-verification stage audit failed"
        ) from exc

    results_sha = hashlib.sha256(
        final_results
    ).hexdigest()

    verified_sha = hashlib.sha256(
        final_verified
    ).hexdigest()

    record_sha = hashlib.sha256(
        final_record
    ).hexdigest()

    completion_payload = (
        build_completion_receipt(
            release_id=(
                context.release_id
            ),
            source_snapshot_id=(
                context.source_snapshot_id
            ),
            source_snapshot_record_sha256=(
                context.source_snapshot_record_sha256
            ),
            execution_commit=(
                commit
            ),
            metadata_record_sha256=(
                context.metadata_record_sha256
            ),
            metadata_completion_sha256=(
                context.metadata_completion_sha256
            ),
            retained_count=len(
                context.retained_metadata
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
                source_release_id
            ),
            source_catalogue_sha256=(
                source_catalogue_sha
            ),
            source_catalogue_entries_sha256=(
                source_entries_sha
            ),
            source_catalogue_entry_count=(
                source_entry_count
            ),
            candidate_input_count=int(
                final_cache_record[
                    "candidate_input_count"
                ]
            ),
            verified_cache_count=int(
                final_cache_record[
                    "verified_cache_count"
                ]
            ),
            fallback_to_fresh_count=int(
                final_cache_record[
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

    write_completion_no_clobber(
        completion_path,
        completion_payload,
    )

    completion_readback = (
        completion_path.read_bytes()
    )

    audit_completion_receipt(
        completion_readback,
        release_id=(
            context.release_id
        ),
        source_snapshot_id=(
            context.source_snapshot_id
        ),
        source_snapshot_record_sha256=(
            context.source_snapshot_record_sha256
        ),
        execution_commit=(
            commit
        ),
        metadata_record_sha256=(
            context.metadata_record_sha256
        ),
        metadata_completion_sha256=(
            context.metadata_completion_sha256
        ),
        retained_count=len(
            context.retained_metadata
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
            source_release_id
        ),
        source_catalogue_sha256=(
            source_catalogue_sha
        ),
        source_catalogue_entries_sha256=(
            source_entries_sha
        ),
        source_catalogue_entry_count=(
            source_entry_count
        ),
        candidate_input_count=int(
            final_cache_record[
                "candidate_input_count"
            ]
        ),
        verified_cache_count=int(
            final_cache_record[
                "verified_cache_count"
            ]
        ),
        fallback_to_fresh_count=int(
            final_cache_record[
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

    return MonthlyCacheVerificationExecutionResult(
        release_id=(
            context.release_id
        ),
        source_snapshot_id=(
            context.source_snapshot_id
        ),
        stage_root=(
            final
        ),
        completion_path=(
            completion_path
        ),
        candidate_input_count=int(
            final_cache_record[
                "candidate_input_count"
            ]
        ),
        verified_cache_count=int(
            final_cache_record[
                "verified_cache_count"
            ]
        ),
        fallback_to_fresh_count=int(
            final_cache_record[
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
        completion_sha256=(
            hashlib.sha256(
                completion_readback
            ).hexdigest()
        ),
    )


def main(
    argv: Sequence[
        str
    ] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute BacSelect monthly cache verification."
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
        "--authoritative-root",
        required=True,
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    args = parser.parse_args(
        argv
    )

    if not args.authorize_real_execution:
        raise MonthlyCacheVerificationExecutionError(
            "production cache verification requires explicit authorization"
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

    result = (
        execute_monthly_cache_verification(
            repo=repo,
            production_root=Path(
                args.production_root
            ),
            stage1_root=Path(
                args.stage1_root
            ),
            authoritative_root=Path(
                args.authoritative_root
            ),
            execution_commit=(
                args.expected_commit
            ),
        )
    )

    print(
        "PASS | BacSelect monthly cache verification complete"
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )

    print(
        f"stage_root={result.stage_root}"
    )

    print(
        f"completion_path={result.completion_path}"
    )

    print(
        f"candidate_input_count={result.candidate_input_count}"
    )

    print(
        f"verified_cache_count={result.verified_cache_count}"
    )

    print(
        f"fallback_to_fresh_count={result.fallback_to_fresh_count}"
    )

    print(
        f"results_sha256={result.results_sha256}"
    )

    print(
        "verified_cache_evidence_sha256="
        f"{result.verified_cache_evidence_sha256}"
    )

    print(
        f"record_sha256={result.record_sha256}"
    )

    print(
        f"completion_sha256={result.completion_sha256}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
