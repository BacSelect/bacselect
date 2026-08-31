#!/usr/bin/env python3
"""Execute the BacSelect cumulative monthly sequence-cache catalogue."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Callable, Sequence

from bacselect.monthly_sequence_acquisition_completion import (
    MonthlySequenceAcquisitionCompletionError,
    audit_sequence_acquisition_completion_record,
)
from bacselect.monthly_sequence_cache_catalogue import (
    CHAINED,
    GENESIS,
    CompletedSequenceCacheBatchEvidence,
    MonthlySequenceCacheCatalogueError,
    audit_sequence_cache_catalogue,
    serialize_sequence_cache_catalogue,
)


COMPLETION_EXECUTOR_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_sequence_acquisition_completion.py"
)

COMPLETION_EXECUTOR_TEST_RELATIVE = Path(
    "tests/test_run_monthly_sequence_acquisition_completion.py"
)

COMPLETION_EXECUTION_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-sequence-acquisition-completion-execution.md"
)

CATALOGUE_CORE_RELATIVE = Path(
    "src/bacselect/monthly_sequence_cache_catalogue.py"
)

CATALOGUE_CORE_TEST_RELATIVE = Path(
    "tests/test_monthly_sequence_cache_catalogue.py"
)

CATALOGUE_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-sequence-cache-catalogue.md"
)

AUTHORITATIVE_STORAGE_RELATIVE = Path(
    "src/bacselect/monthly_authoritative_storage.py"
)

AUTHORITATIVE_STORAGE_TEST_RELATIVE = Path(
    "tests/test_monthly_authoritative_storage.py"
)

WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_monthly_sequence_cache_catalogue.py"
)

EXECUTION_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-sequence-cache-catalogue-execution.md"
)


EXPECTED_COMPLETION_EXECUTOR_SHA256 = (
    "21c582b4e41dd8013f4716afe10c21f8c664133d423dd1daf9c7d1f7d0048c41"
)

EXPECTED_COMPLETION_EXECUTOR_TEST_SHA256 = (
    "cef4b962a416b7ac276ef5086b24e78b9e0ca20aaead4c86acd8473a33de04b2"
)

EXPECTED_COMPLETION_EXECUTION_METHOD_SHA256 = (
    "faabdfb9270cff66d5d87c908bb6538e25c00a12b40554dddcb14b5750958aed"
)

EXPECTED_CATALOGUE_CORE_SHA256 = (
    "9555a2a72fa4b0f5d731adabead147f8564660fe87a18696b1a2b5312bc05d55"
)

EXPECTED_CATALOGUE_CORE_TEST_SHA256 = (
    "c811f87155766dabc0683be38fc5a1066d93c087052b6b0f826f5f90b5a54ed2"
)

EXPECTED_CATALOGUE_METHOD_SHA256 = (
    "9167c8dec02c33aba5b76513ed77c961fd2833488f5504b9d53be33f861b69eb"
)

EXPECTED_AUTHORITATIVE_STORAGE_SHA256 = (
    "759c2b09df7b68df36d724c54dc992049484cd2aa80b906cca4e1e3318ba4cd0"
)

EXPECTED_AUTHORITATIVE_STORAGE_TEST_SHA256 = (
    "4843b75e9e88f6d3af7a5395ce1d0fff6405a42458f094f165cf1493608e86ed"
)

EXPECTED_EXECUTION_METHOD_SHA256 = (
    "128b533c2cfc9f9a0751094a9bb33f5ef97414ede86f8a3df9d104b9c7d7fdcd"
)


COMPLETION_NAME = (
    "sequence-acquisition-completion.json"
)

SEQUENCE_ROOT_NAME = (
    "sequence-acquisition"
)

CATALOGUE_NAME = (
    "sequence-cache-catalogue.json"
)

CATALOGUE_TEMP_NAME = (
    ".sequence-cache-catalogue.json.tmp"
)

SUMMARY_NAME = (
    "batch-summary.json"
)

CANDIDATE_AUDIT_NAME = (
    "candidate-sequence-audit.tsv"
)

COMPONENT_AUDIT_NAME = (
    "component-sequence-audit.tsv"
)

PACKAGE_FILES_NAME = (
    "package-files.tsv"
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


class MonthlySequenceCacheCatalogueExecutionError(
    RuntimeError
):
    """Raised when catalogue execution fails closed."""


@dataclass(
    frozen=True,
)
class CatalogueChainItem:
    release_id: str
    origin_git_commit: str
    catalogue_path: Path
    catalogue_payload: bytes
    catalogue_sha256: str
    catalogue_record: dict[
        str,
        object,
    ]


@dataclass(
    frozen=True,
)
class AuditedCompletionContext:
    release_id: str
    source_snapshot_id: str
    stage1_root: Path
    completion_payload: bytes
    completion_record: dict[
        str,
        object,
    ]
    batch_evidence: tuple[
        CompletedSequenceCacheBatchEvidence,
        ...,
    ]
    fresh_acquisition_count: int


@dataclass(
    frozen=True,
)
class SequenceCacheCatalogueExecutionResult:
    release_id: str
    source_snapshot_id: str
    catalogue_path: Path
    catalogue_sha256: str
    catalogue_mode: str
    previous_catalogue_release_id: str | None
    previous_catalogue_sha256: str | None
    catalogue_entry_count: int
    current_acquisition_count: int


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
        raise MonthlySequenceCacheCatalogueExecutionError(
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
        raise MonthlySequenceCacheCatalogueExecutionError(
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
        raise MonthlySequenceCacheCatalogueExecutionError(
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
        raise MonthlySequenceCacheCatalogueExecutionError(
            f"{label} SHA256 mismatch: {observed}"
        )


def git_output(
    repo: Path,
    *args: str,
) -> str:
    result = subprocess.run(
        (
            "git",
            *args,
        ),
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "Git command failed: "
            + " ".join(
                args
            )
        )

    return result.stdout.strip()


def load_frozen_completion_execution(
    repo: Path,
):
    root = Path(
        repo
    ).resolve()

    path = (
        root
        / COMPLETION_EXECUTOR_RELATIVE
    )

    try:
        metadata = os.lstat(
            path
        )
    except FileNotFoundError:
        raise MonthlySequenceCacheCatalogueExecutionError(
            f"missing frozen completion executor: {path}"
        ) from None

    if (
        stat.S_ISLNK(
            metadata.st_mode
        )
        or not stat.S_ISREG(
            metadata.st_mode
        )
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "frozen completion executor is not a regular non-symlink file"
        )

    module_name = (
        "_bacselect_frozen_sequence_acquisition_completion_execution"
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
            == path.resolve()
        ):
            return existing

        raise MonthlySequenceCacheCatalogueExecutionError(
            "frozen completion executor module name "
            "is already bound to another path"
        )

    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "unable to construct frozen completion executor module"
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

    required = (
        "repository_preflight",
        "load_upstream_contract",
        "load_frozen_stage3b_execution",
        "expected_batch_ids",
        "discover_sequence_entries",
        "collect_completed_batch_evidence",
        "EXPECTED_DATASETS_ENVIRONMENT_SHA256",
    )

    for name in required:
        if not hasattr(
            module,
            name,
        ):
            raise MonthlySequenceCacheCatalogueExecutionError(
                f"frozen completion helper disappeared: {name}"
            )

    return module


def repository_preflight(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    git_reader: Callable[
        ...,
        str,
    ] = git_output,
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

    completion = load_frozen_completion_execution(
        root
    )

    try:
        completion.repository_preflight(
            root,
            expected_commit=commit,
            expected_wrapper_sha256=(
                EXPECTED_COMPLETION_EXECUTOR_SHA256
            ),
            expected_wrapper_test_sha256=(
                EXPECTED_COMPLETION_EXECUTOR_TEST_SHA256
            ),
            git_reader=git_reader,
            file_sha256_reader=(
                file_sha256_reader
            ),
        )
    except Exception as exc:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "frozen completion-executor preflight failed"
        ) from exc

    fixed = (
        (
            COMPLETION_EXECUTION_METHOD_RELATIVE,
            EXPECTED_COMPLETION_EXECUTION_METHOD_SHA256,
            "completion execution method",
        ),
        (
            CATALOGUE_CORE_RELATIVE,
            EXPECTED_CATALOGUE_CORE_SHA256,
            "sequence-cache catalogue contract",
        ),
        (
            CATALOGUE_CORE_TEST_RELATIVE,
            EXPECTED_CATALOGUE_CORE_TEST_SHA256,
            "sequence-cache catalogue contract test",
        ),
        (
            CATALOGUE_METHOD_RELATIVE,
            EXPECTED_CATALOGUE_METHOD_SHA256,
            "sequence-cache catalogue method",
        ),
        (
            AUTHORITATIVE_STORAGE_RELATIVE,
            EXPECTED_AUTHORITATIVE_STORAGE_SHA256,
            "authoritative-storage contract",
        ),
        (
            AUTHORITATIVE_STORAGE_TEST_RELATIVE,
            EXPECTED_AUTHORITATIVE_STORAGE_TEST_SHA256,
            "authoritative-storage contract test",
        ),
        (
            EXECUTION_METHOD_RELATIVE,
            EXPECTED_EXECUTION_METHOD_SHA256,
            "sequence-cache catalogue execution method",
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
        label="sequence-cache catalogue executor",
        reader=file_sha256_reader,
    )

    require_sha256(
        root
        / WRAPPER_TEST_RELATIVE,
        expected_wrapper_test_sha256,
        label="sequence-cache catalogue executor test",
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
        raise MonthlySequenceCacheCatalogueExecutionError(
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
        raise MonthlySequenceCacheCatalogueExecutionError(
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
        raise MonthlySequenceCacheCatalogueExecutionError(
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
        raise MonthlySequenceCacheCatalogueExecutionError(
            f"{label} is not a regular non-symlink file: {supplied}"
        )

    return supplied.resolve()


def discover_catalogue_chain(
    production_root: Path,
    *,
    current_release_id: str,
    include_current: bool = False,
    current_catalogue_path: Path | None = None,
) -> tuple[
    CatalogueChainItem,
    ...,
]:
    root = Path(
        production_root
    )

    if not root.is_absolute():
        raise MonthlySequenceCacheCatalogueExecutionError(
            "production root must be absolute"
        )

    root = _require_real_directory(
        root,
        label="production root",
    )

    current_release = validate_release_id(
        current_release_id
    )

    current_ordinal = release_ordinal(
        current_release
    )

    current_path_resolved = (
        Path(
            current_catalogue_path
        ).resolve()
        if current_catalogue_path
        is not None
        else None
    )

    candidates_by_release: dict[
        str,
        list[
            CatalogueChainItem
        ],
    ] = {}

    for release_entry in sorted(
        root.iterdir(),
        key=lambda value:
            value.name,
    ):
        release_name = (
            release_entry.name
        )

        if RELEASE_RE.fullmatch(
            release_name
        ) is None:
            continue

        if release_entry.is_symlink():
            raise MonthlySequenceCacheCatalogueExecutionError(
                "catalogue history release directory "
                "must not be a symbolic link"
            )

        if not release_entry.is_dir():
            raise MonthlySequenceCacheCatalogueExecutionError(
                "catalogue history release entry "
                "is not a directory"
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
            raise MonthlySequenceCacheCatalogueExecutionError(
                "catalogue history production directory "
                "is not a real directory"
            )

        release_candidates: list[
            CatalogueChainItem
        ] = []

        for commit_entry in sorted(
            production.iterdir(),
            key=lambda value:
                value.name,
        ):
            commit_name = (
                commit_entry.name
            )

            if COMMIT_RE.fullmatch(
                commit_name
            ) is None:
                continue

            if commit_entry.is_symlink():
                raise MonthlySequenceCacheCatalogueExecutionError(
                    "catalogue history commit directory "
                    "must not be a symbolic link"
                )

            if not commit_entry.is_dir():
                raise MonthlySequenceCacheCatalogueExecutionError(
                    "catalogue history commit entry "
                    "is not a directory"
                )

            catalogue_path = (
                commit_entry
                / CATALOGUE_NAME
            )

            if not os.path.lexists(
                catalogue_path
            ):
                continue

            catalogue_file = (
                _require_regular_file(
                    catalogue_path,
                    label="historical sequence-cache catalogue",
                )
            )

            payload = (
                catalogue_file.read_bytes()
            )

            try:
                record = (
                    audit_sequence_cache_catalogue(
                        payload
                    )
                )
            except (
                MonthlySequenceCacheCatalogueError,
                TypeError,
                ValueError,
            ) as exc:
                raise MonthlySequenceCacheCatalogueExecutionError(
                    "historical sequence-cache catalogue audit failed"
                ) from exc

            if record[
                "release_id"
            ] != release_name:
                raise MonthlySequenceCacheCatalogueExecutionError(
                    "historical catalogue release identity "
                    "differs from directory identity"
                )

            if record[
                "origin_git_commit"
            ] != commit_name:
                raise MonthlySequenceCacheCatalogueExecutionError(
                    "historical catalogue Git identity "
                    "differs from directory identity"
                )

            release_candidates.append(
                CatalogueChainItem(
                    release_id=(
                        release_name
                    ),
                    origin_git_commit=(
                        commit_name
                    ),
                    catalogue_path=(
                        catalogue_file
                    ),
                    catalogue_payload=(
                        payload
                    ),
                    catalogue_sha256=(
                        hashlib.sha256(
                            payload
                        ).hexdigest()
                    ),
                    catalogue_record=(
                        record
                    ),
                )
            )

        if len(
            release_candidates
        ) > 1:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "multiple canonical catalogues exist "
                f"for release {release_name}"
            )

        if release_candidates:
            candidates_by_release[
                release_name
            ] = (
                release_candidates
            )

    candidates = [
        values[
            0
        ]
        for _, values
        in sorted(
            candidates_by_release.items(),
            key=lambda item:
                release_ordinal(
                    item[
                        0
                    ]
                ),
        )
    ]

    accepted: list[
        CatalogueChainItem
    ] = []

    for item in candidates:
        ordinal = release_ordinal(
            item.release_id
        )

        if ordinal > current_ordinal:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "a later canonical catalogue already exists"
            )

        if ordinal == current_ordinal:
            if not include_current:
                raise MonthlySequenceCacheCatalogueExecutionError(
                    "a canonical catalogue already exists "
                    "for the current release"
                )

            if current_path_resolved is None:
                raise MonthlySequenceCacheCatalogueExecutionError(
                    "current catalogue path is required "
                    "when including current release"
                )

            if (
                item.catalogue_path.resolve()
                != current_path_resolved
            ):
                raise MonthlySequenceCacheCatalogueExecutionError(
                    "a competing canonical catalogue exists "
                    "for the current release"
                )

        accepted.append(
            item
        )

    chain = tuple(
        accepted
    )

    if not chain:
        return ()

    first = chain[
        0
    ]

    if first.catalogue_record[
        "catalogue_mode"
    ] != GENESIS:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "catalogue history does not begin with GENESIS"
        )

    for previous, current in zip(
        chain,
        chain[
            1:
        ],
    ):
        if current.catalogue_record[
            "catalogue_mode"
        ] != CHAINED:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "non-genesis catalogue history member "
                "is not CHAINED"
            )

        if current.catalogue_record[
            "previous_catalogue_release_id"
        ] != previous.release_id:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "catalogue history predecessor release link is broken"
            )

        if current.catalogue_record[
            "previous_catalogue_sha256"
        ] != previous.catalogue_sha256:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "catalogue history predecessor SHA256 link is broken"
            )

    return chain


def chain_signature(
    chain: Sequence[
        CatalogueChainItem
    ],
) -> tuple[
    tuple[
        str,
        str,
        str,
    ],
    ...,
]:
    return tuple(
        (
            item.release_id,
            item.origin_git_commit,
            item.catalogue_sha256,
        )
        for item in chain
    )


def _read_catalogue_batch_evidence(
    stage1_root: Path,
    *,
    completion_record: dict[
        str,
        object,
    ],
) -> tuple[
    CompletedSequenceCacheBatchEvidence,
    ...,
]:
    sequence_root = (
        Path(
            stage1_root
        )
        / SEQUENCE_ROOT_NAME
    )

    rows = completion_record[
        "batches"
    ]

    if not isinstance(
        rows,
        list,
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "audited completion batch rows changed"
        )

    if not rows:
        return ()

    _require_real_directory(
        sequence_root,
        label="sequence-acquisition root",
    )

    evidence = []

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            raise MonthlySequenceCacheCatalogueExecutionError(
                "audited completion batch row changed"
            )

        batch_id = str(
            row[
                "batch_id"
            ]
        )

        batch = _require_real_directory(
            sequence_root
            / batch_id,
            label=f"completed Stage 3B batch {batch_id}",
        )

        paths = {
            "summary":
                _require_regular_file(
                    batch
                    / SUMMARY_NAME,
                    label=f"{batch_id} batch summary",
                ),
            "candidate":
                _require_regular_file(
                    batch
                    / CANDIDATE_AUDIT_NAME,
                    label=f"{batch_id} candidate audit",
                ),
            "component":
                _require_regular_file(
                    batch
                    / COMPONENT_AUDIT_NAME,
                    label=f"{batch_id} component audit",
                ),
            "package":
                _require_regular_file(
                    batch
                    / PACKAGE_FILES_NAME,
                    label=f"{batch_id} package-files manifest",
                ),
        }

        payloads = {
            name:
                path.read_bytes()
            for name, path
            in paths.items()
        }

        expected = {
            "summary":
                row[
                    "batch_summary_sha256"
                ],
            "candidate":
                row[
                    "candidate_sequence_audit_sha256"
                ],
            "component":
                row[
                    "component_sequence_audit_sha256"
                ],
            "package":
                row[
                    "package_files_sha256"
                ],
        }

        for name, payload in payloads.items():
            observed = hashlib.sha256(
                payload
            ).hexdigest()

            if observed != expected[
                name
            ]:
                raise MonthlySequenceCacheCatalogueExecutionError(
                    f"{batch_id} {name} evidence "
                    "differs from audited completion"
                )

        evidence.append(
            CompletedSequenceCacheBatchEvidence(
                batch_id=batch_id,
                summary_payload=(
                    payloads[
                        "summary"
                    ]
                ),
                candidate_audit_payload=(
                    payloads[
                        "candidate"
                    ]
                ),
                component_audit_payload=(
                    payloads[
                        "component"
                    ]
                ),
                package_files_payload=(
                    payloads[
                        "package"
                    ]
                ),
            )
        )

    return tuple(
        evidence
    )


def audit_existing_completion(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    sequence_plan_record: Path,
    fresh_target_manifest: Path,
    execution_commit: str,
    package_validator=None,
) -> AuditedCompletionContext:
    root = Path(
        repo
    ).resolve()

    completion_execution = (
        load_frozen_completion_execution(
            root
        )
    )

    try:
        upstream = (
            completion_execution.load_upstream_contract(
                production_root=(
                    production_root
                ),
                stage1_root=(
                    stage1_root
                ),
                sequence_plan_record=(
                    sequence_plan_record
                ),
                fresh_target_manifest=(
                    fresh_target_manifest
                ),
                expected_commit=(
                    execution_commit
                ),
            )
        )
    except Exception as exc:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "frozen upstream production audit failed"
        ) from exc

    completion_path = (
        upstream.stage1_root
        / COMPLETION_NAME
    )

    completion_file = _require_regular_file(
        completion_path,
        label="sequence-acquisition completion",
    )

    completion_payload_before = (
        completion_file.read_bytes()
    )

    stage3b = (
        completion_execution.load_frozen_stage3b_execution(
            root
        )
    )

    try:
        targets = tuple(
            stage3b.parse_fresh_targets(
                upstream.fresh_target_manifest_payload
            )
        )
    except Exception as exc:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "frozen Stage 3B target reconstruction failed"
        ) from exc

    if len(
        targets
    ) != upstream.fresh_acquisition_count:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "Stage 3B target reconstruction changed "
            "the Stage 2 population"
        )

    batch_size = getattr(
        stage3b,
        "FRESH_BATCH_SIZE",
        None,
    )

    if (
        isinstance(
            batch_size,
            bool,
        )
        or not isinstance(
            batch_size,
            int,
        )
        or batch_size <= 0
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "frozen Stage 3B batch size is invalid"
        )

    tsv_serializer = getattr(
        stage3b,
        "_serialize_tsv",
        None,
    )

    if not callable(
        tsv_serializer
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "frozen Stage 3B TSV serializer is unavailable"
        )

    (
        discovered_final_ids,
        discovered_partial_ids,
        unexpected_entries,
    ) = (
        completion_execution.discover_sequence_entries(
            upstream.stage1_root
        )
    )

    expected_ids = (
        completion_execution.expected_batch_ids(
            upstream.expected_batch_count
        )
    )

    if (
        discovered_final_ids
        != expected_ids
        or discovered_partial_ids
        or unexpected_entries
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "Stage 3B discovery is incomplete or "
            "contains partial/unexpected entries"
        )

    if package_validator is None:
        package_validator = getattr(
            completion_execution,
            "validate_hydrated_package",
            None,
        )

    if not callable(
        package_validator
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "frozen Stage 3A package validator is unavailable"
        )

    sequence_root = (
        upstream.stage1_root
        / SEQUENCE_ROOT_NAME
    )

    completion_evidence = []

    for batch_index, batch_id in enumerate(
        expected_ids,
        1,
    ):
        start = (
            batch_index
            - 1
        ) * batch_size

        stop = min(
            start
            + batch_size,
            len(
                targets
            ),
        )

        batch_targets = targets[
            start:
            stop
        ]

        if not batch_targets:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "derived completion batch target set is empty"
            )

        completion_evidence.append(
            completion_execution.collect_completed_batch_evidence(
                sequence_root
                / batch_id,
                batch_targets=(
                    batch_targets
                ),
                package_validator=(
                    package_validator
                ),
                tsv_serializer=(
                    tsv_serializer
                ),
            )
        )

    contract_kwargs = {
        "source_snapshot_id":
            upstream.source_snapshot_id,
        "source_snapshot_record_sha256":
            upstream.source_snapshot_record_sha256,
        "stage2_sequence_plan_record":
            upstream.sequence_plan_payload,
        "stage2_fresh_target_manifest":
            upstream.fresh_target_manifest_payload,
        "origin_git_commit":
            execution_commit,
        "environment_explicit_sha256":
            getattr(
                completion_execution,
                "EXPECTED_DATASETS_ENVIRONMENT_SHA256",
            ),
        "batches":
            tuple(
                completion_evidence
            ),
        "discovered_final_batch_ids":
            discovered_final_ids,
        "discovered_partial_batch_ids":
            discovered_partial_ids,
        "unexpected_batch_entries":
            unexpected_entries,
    }

    try:
        completion_record = (
            audit_sequence_acquisition_completion_record(
                completion_payload_before,
                **contract_kwargs
            )
        )
    except (
        MonthlySequenceAcquisitionCompletionError,
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "sequence-acquisition completion re-audit failed"
        ) from exc

    completion_payload_after = (
        completion_file.read_bytes()
    )

    if (
        completion_payload_after
        != completion_payload_before
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "sequence-acquisition completion changed "
            "during re-audit"
        )

    batch_evidence = (
        _read_catalogue_batch_evidence(
            upstream.stage1_root,
            completion_record=(
                completion_record
            ),
        )
    )

    if (
        completion_file.read_bytes()
        != completion_payload_before
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "sequence-acquisition completion changed "
            "during catalogue evidence loading"
        )

    return AuditedCompletionContext(
        release_id=(
            upstream.release_id
        ),
        source_snapshot_id=(
            upstream.source_snapshot_id
        ),
        stage1_root=(
            upstream.stage1_root
        ),
        completion_payload=(
            completion_payload_before
        ),
        completion_record=(
            completion_record
        ),
        batch_evidence=(
            batch_evidence
        ),
        fresh_acquisition_count=(
            upstream.fresh_acquisition_count
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


def _write_all(
    descriptor: int,
    payload: bytes,
) -> None:
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
            raise MonthlySequenceCacheCatalogueExecutionError(
                "short write while creating catalogue artifact"
            )

        offset += written


def write_audited_catalogue(
    *,
    stage1_root: Path,
    payload: bytes,
    auditor: Callable[
        [bytes],
        object,
    ],
    prepublication_check: Callable[
        [],
        None,
    ],
    postpublication_check: Callable[
        [],
        None,
    ],
) -> tuple[
    Path,
    bytes,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "catalogue payload must be bytes"
        )

    final = (
        stage1_root
        / CATALOGUE_NAME
    )

    temporary = (
        stage1_root
        / CATALOGUE_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "sequence-cache catalogue already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "sequence-cache catalogue temporary artifact already exists"
        )

    descriptor = os.open(
        temporary,
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

    temporary_readback = (
        temporary.read_bytes()
    )

    if temporary_readback != payload:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "temporary catalogue readback changed"
        )

    if stat.S_IMODE(
        temporary.stat().st_mode
    ) != 0o644:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "temporary catalogue mode changed"
        )

    auditor(
        temporary_readback
    )

    fsync_directory(
        stage1_root
    )

    prepublication_check()

    try:
        os.link(
            temporary,
            final,
            follow_symlinks=False,
        )
    except FileExistsError as exc:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "sequence-cache catalogue appeared "
            "before canonical publication"
        ) from exc

    fsync_directory(
        stage1_root
    )

    try:
        final_readback = (
            final.read_bytes()
        )

        if final_readback != payload:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "final catalogue readback changed"
            )

        if stat.S_IMODE(
            final.stat().st_mode
        ) != 0o644:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "final catalogue mode changed"
            )

        auditor(
            final_readback
        )

        postpublication_check()

    except Exception:
        try:
            os.unlink(
                final
            )
        finally:
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

    return (
        final,
        final_readback,
    )


def execute_monthly_sequence_cache_catalogue(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    sequence_plan_record: Path,
    fresh_target_manifest: Path,
    execution_commit: str,
    completion_context_loader: Callable[
        ...,
        AuditedCompletionContext,
    ] = audit_existing_completion,
) -> SequenceCacheCatalogueExecutionResult:
    commit = validate_git_commit(
        execution_commit,
        label="execution commit",
    )

    root = Path(
        production_root
    )

    if not root.is_absolute():
        raise MonthlySequenceCacheCatalogueExecutionError(
            "production root must be absolute"
        )

    _require_real_directory(
        root,
        label="production root",
    )

    context = completion_context_loader(
        repo=Path(
            repo
        ).resolve(),
        production_root=root,
        stage1_root=Path(
            stage1_root
        ),
        sequence_plan_record=Path(
            sequence_plan_record
        ),
        fresh_target_manifest=Path(
            fresh_target_manifest
        ),
        execution_commit=commit,
    )

    if not isinstance(
        context,
        AuditedCompletionContext,
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "completion context loader returned wrong type"
        )

    stage1 = context.stage1_root.resolve()

    final = (
        stage1
        / CATALOGUE_NAME
    )

    temporary = (
        stage1
        / CATALOGUE_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "sequence-cache catalogue already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlySequenceCacheCatalogueExecutionError(
            "sequence-cache catalogue temporary artifact already exists"
        )

    prior_chain = discover_catalogue_chain(
        root,
        current_release_id=(
            context.release_id
        ),
    )

    prior_signature = chain_signature(
        prior_chain
    )

    previous_payload = (
        prior_chain[
            -1
        ].catalogue_payload
        if prior_chain
        else None
    )

    try:
        catalogue_payload = (
            serialize_sequence_cache_catalogue(
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                origin_git_commit=(
                    commit
                ),
                sequence_acquisition_completion_payload=(
                    context.completion_payload
                ),
                current_batches=(
                    context.batch_evidence
                ),
                previous_catalogue_payload=(
                    previous_payload
                ),
            )
        )

        catalogue_record = (
            audit_sequence_cache_catalogue(
                catalogue_payload
            )
        )
    except (
        MonthlySequenceCacheCatalogueError,
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlySequenceCacheCatalogueExecutionError(
            "frozen sequence-cache catalogue contract failed"
        ) from exc

    catalogue_sha = hashlib.sha256(
        catalogue_payload
    ).hexdigest()

    def auditor(
        payload: bytes,
    ) -> object:
        try:
            return (
                audit_sequence_cache_catalogue(
                    payload
                )
            )
        except (
            MonthlySequenceCacheCatalogueError,
            TypeError,
            ValueError,
        ) as exc:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "catalogue artifact read-back audit failed"
            ) from exc

    def prepublication_check() -> None:
        observed = discover_catalogue_chain(
            root,
            current_release_id=(
                context.release_id
            ),
        )

        if chain_signature(
            observed
        ) != prior_signature:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "catalogue history changed before publication"
            )

    expected_post_signature = (
        prior_signature
        + (
            (
                context.release_id,
                commit,
                catalogue_sha,
            ),
        )
    )

    def postpublication_check() -> None:
        observed = discover_catalogue_chain(
            root,
            current_release_id=(
                context.release_id
            ),
            include_current=True,
            current_catalogue_path=(
                final
            ),
        )

        if chain_signature(
            observed
        ) != expected_post_signature:
            raise MonthlySequenceCacheCatalogueExecutionError(
                "catalogue history changed during publication"
            )

    (
        final_path,
        final_payload,
    ) = write_audited_catalogue(
        stage1_root=stage1,
        payload=catalogue_payload,
        auditor=auditor,
        prepublication_check=(
            prepublication_check
        ),
        postpublication_check=(
            postpublication_check
        ),
    )

    return SequenceCacheCatalogueExecutionResult(
        release_id=(
            context.release_id
        ),
        source_snapshot_id=(
            context.source_snapshot_id
        ),
        catalogue_path=(
            final_path
        ),
        catalogue_sha256=(
            hashlib.sha256(
                final_payload
            ).hexdigest()
        ),
        catalogue_mode=str(
            catalogue_record[
                "catalogue_mode"
            ]
        ),
        previous_catalogue_release_id=(
            catalogue_record[
                "previous_catalogue_release_id"
            ]
        ),
        previous_catalogue_sha256=(
            catalogue_record[
                "previous_catalogue_sha256"
            ]
        ),
        catalogue_entry_count=int(
            catalogue_record[
                "catalogue_entry_count"
            ]
        ),
        current_acquisition_count=int(
            catalogue_record[
                "current_acquisition_count"
            ]
        ),
    )


def main(
    argv: Sequence[
        str
    ] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build and publish the BacSelect cumulative "
            "monthly sequence-cache catalogue."
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
        "--sequence-plan-record",
        required=True,
    )

    parser.add_argument(
        "--fresh-target-manifest",
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
        raise MonthlySequenceCacheCatalogueExecutionError(
            "production sequence-cache catalogue execution "
            "requires explicit authorization"
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
        execute_monthly_sequence_cache_catalogue(
            repo=repo,
            production_root=Path(
                args.production_root
            ),
            stage1_root=Path(
                args.stage1_root
            ),
            sequence_plan_record=Path(
                args.sequence_plan_record
            ),
            fresh_target_manifest=Path(
                args.fresh_target_manifest
            ),
            execution_commit=(
                args.expected_commit
            ),
        )
    )

    print(
        "PASS | BacSelect monthly sequence-cache catalogue complete"
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )

    print(
        f"catalogue_path={result.catalogue_path}"
    )

    print(
        f"catalogue_sha256={result.catalogue_sha256}"
    )

    print(
        f"catalogue_mode={result.catalogue_mode}"
    )

    print(
        "previous_catalogue_release_id="
        f"{result.previous_catalogue_release_id}"
    )

    print(
        "previous_catalogue_sha256="
        f"{result.previous_catalogue_sha256}"
    )

    print(
        f"catalogue_entry_count={result.catalogue_entry_count}"
    )

    print(
        f"current_acquisition_count={result.current_acquisition_count}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
