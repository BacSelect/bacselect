#!/usr/bin/env python3
"""Execute BacSelect monthly taxonomy-snapshot Stage 7."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Any
import urllib.request

from bacselect import monthly_release_start
from bacselect import monthly_taxonomy_snapshot_execution
from bacselect import source_taxonomy_acquisition


STAGE_NAME = "taxonomy-snapshot"
PARTIAL_NAME = "taxonomy-snapshot.partial"

COMPLETION_NAME = (
    "taxonomy-snapshot-completion.json"
)

COMPLETION_TEMP_NAME = (
    ".taxonomy-snapshot-completion.json.tmp"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-taxonomy-snapshot-completion-v1"
)

COMPLETION_STATUS = (
    "TAXONOMY_SNAPSHOT_EXECUTION_COMPLETE"
)

CHECKPOINT_NAME = (
    "release-start-checkpoint.json"
)

RAW_RESPONSE_NAME = (
    "assembly_data_report.raw.jsonl"
)

SOURCE_SNAPSHOT_RECORD_NAME = (
    "source-snapshot-record.json"
)

STAGE6_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_chromosome_integrity.py"
)

EXPECTED_STAGE6_WRAPPER_SHA256 = (
    "da43df5aeeb2b0a7cbf3f404f217d45"
    "ba32501634583924ea047e18c6df77538"
)

EXPECTED_EXECUTION_METHOD_SHA256 = (
    "0dd4105b1360117cc79b185a55c69b5d"
    "519f058178b35635cd5e1d3a28aa342c"
)

EXPECTED_EXECUTION_SUPPORT_SHA256 = (
    "4cb58becd9b1dc6428f0614262c0d55c"
    "05673395dc41acdf358ff251d990e263"
)

FROZEN_DEPENDENCIES = {
    Path(
        "validation/selector-v1/"
        "prospective-monthly-taxonomy-snapshot-execution.md"
    ):
        EXPECTED_EXECUTION_METHOD_SHA256,
    Path(
        "src/bacselect/"
        "monthly_taxonomy_snapshot_execution.py"
    ):
        EXPECTED_EXECUTION_SUPPORT_SHA256,
    Path(
        "src/bacselect/"
        "monthly_taxonomy_snapshot.py"
    ):
        (
            "3e82dfeab3778a29bc4be9f04234c612"
            "44b30b284003b67d6114b45051a5816e"
        ),
    Path(
        "src/bacselect/"
        "source_taxonomy.py"
    ):
        (
            "9c8c4149c5db2a757e8c201a6523bdb1"
            "13511b5f72a4dd2893572dd8c7928e4d"
        ),
    Path(
        "src/bacselect/"
        "source_taxonomy_acquisition.py"
    ):
        (
            "c76f04ab3ab0149d5ede2e1069e547e9"
            "9588ebba98f6ac1aac0ee5727015cef9"
        ),
    Path(
        "src/bacselect/"
        "monthly_authoritative_storage.py"
    ):
        "759c2b09df7b68df36d724c54dc992049484cd2aa80b906cca4e1e3318ba4cd0",
    Path(
        "src/bacselect/"
        "monthly_release_start.py"
    ):
        (
            "76cb24d9c70f1418e580408a04321fc7"
            "e5ae1e78709e60cb2f5d15b8a531588c"
        ),
    STAGE6_WRAPPER_RELATIVE:
        EXPECTED_STAGE6_WRAPPER_SHA256,
}

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_RELEASE_RE = re.compile(
    r"^[0-9]{4}\.[0-9]{2}$"
)

COMPLETION_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "release_id",
        "source_snapshot_id",
        "execution_git_commit",
        "execution_support_module_sha256",
        "validation_wrapper_sha256",
        "execution_method_sha256",
        "source_snapshot_record_sha256",
        "source_raw_response_sha256",
        "chromosome_integrity_decisions_sha256",
        "chromosome_integrity_record_sha256",
        "chromosome_integrity_completion_sha256",
        "taxonomy_snapshot_id",
        "monthly_taxonomy_snapshot_record_sha256",
        "taxonomy_archive_sha256",
        "nodes_sha256",
        "merged_sha256",
        "delnodes_sha256",
        "taxonomy_acquisition_provenance_sha256",
        "taxonomy_content_manifest_sha256",
        "authoritative_storage_manifest_sha256",
        "authoritative_storage_manifest_key",
        "authoritative_storage_receipt_sha256",
        "authoritative_storage_receipt_key",
        "authoritative_verified_object_count",
    }
)


class MonthlyTaxonomyWrapperError(
    RuntimeError
):
    """Raised when monthly Stage 7 wrapper execution fails closed."""


@dataclass(
    frozen=True,
)
class AuthenticatedCurrentUpstream:
    """Fully reauthenticated Stage 1 through Stage 6 authority."""

    support_upstream: (
        monthly_taxonomy_snapshot_execution
        .AuthenticatedMonthlyTaxonomyUpstream
    )

    stage6_decisions_payload: bytes
    stage6_record_payload: bytes
    stage6_completion_payload: bytes

    identity: tuple[
        object,
        ...,
    ]


@dataclass(
    frozen=True,
)
class MonthlyTaxonomyExecutionResult:
    """Terminal local identities for one completed Stage 7 execution."""

    release_id: str
    source_snapshot_id: str
    taxonomy_snapshot_id: str

    stage_path: Path
    completion_path: Path

    record_sha256: str
    completion_sha256: str

    authoritative_manifest_sha256: str
    authoritative_receipt_sha256: str


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def sha256_bytes(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def _canonical_json(
    value: Mapping[
        str,
        object,
    ],
) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def _sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyTaxonomyWrapperError(
            f"{label} is not a SHA256"
        )

    return value


def _commit(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyTaxonomyWrapperError(
            "execution Git commit is invalid"
        )

    return value


def _release_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _RELEASE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyTaxonomyWrapperError(
            "release ID is invalid"
        )

    return value


def _nonempty_text(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value.strip() != value
    ):
        raise MonthlyTaxonomyWrapperError(
            f"{label} is invalid"
        )

    return value


def _count(
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
        raise MonthlyTaxonomyWrapperError(
            f"{label} is invalid"
        )

    return value


def git_output(
    repo: Path,
    *arguments: str,
) -> str:
    result = subprocess.run(
        (
            "git",
            "-C",
            str(
                repo
            ),
            *arguments,
        ),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return result.stdout.strip()


def _require_repository(
    repo: Path,
) -> Path:
    root = Path(
        repo
    ).resolve()

    if (
        root.is_symlink()
        or not root.is_dir()
    ):
        raise MonthlyTaxonomyWrapperError(
            "repository root is not a real directory"
        )

    try:
        observed = Path(
            git_output(
                root,
                "rev-parse",
                "--show-toplevel",
            )
        ).resolve()
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
    ) as exc:
        raise MonthlyTaxonomyWrapperError(
            "repository identity check failed"
        ) from exc

    if observed != root:
        raise MonthlyTaxonomyWrapperError(
            "repository path is not the Git top level"
        )

    return root


def _require_absolute_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    if not value.is_absolute():
        raise MonthlyTaxonomyWrapperError(
            f"{label} must be absolute"
        )

    if (
        value.is_symlink()
        or not value.is_dir()
    ):
        raise MonthlyTaxonomyWrapperError(
            f"{label} is not a real directory"
        )

    return value.resolve()


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    if (
        not os.path.lexists(
            path
        )
        or path.is_symlink()
        or not path.is_file()
    ):
        raise MonthlyTaxonomyWrapperError(
            f"{label} is not a regular file"
        )

    return path


def _require_exact_inventory(
    directory: Path,
    *,
    expected_files: set[
        str
    ],
    label: str,
) -> None:
    observed = {
        child.name
        for child in directory.iterdir()
    }

    if observed != expected_files:
        raise MonthlyTaxonomyWrapperError(
            f"{label} inventory changed"
        )

    for name in expected_files:
        _require_regular_file(
            directory
            / name,
            label=(
                f"{label} file {name}"
            ),
        )


def _fsync_directory(
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


def _write_no_clobber(
    path: Path,
    payload: bytes,
) -> None:
    if not isinstance(
        payload,
        bytes,
    ):
        raise MonthlyTaxonomyWrapperError(
            "publication payload must be bytes"
        )

    descriptor = None

    try:
        descriptor = os.open(
            path,
            (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
            ),
            0o644,
        )

        os.fchmod(
            descriptor,
            0o644,
        )

        with os.fdopen(
            descriptor,
            "wb",
            closefd=True,
        ) as handle:
            descriptor = None

            handle.write(
                payload
            )

            handle.flush()

            os.fsync(
                handle.fileno()
            )

    except FileExistsError as exc:
        raise MonthlyTaxonomyWrapperError(
            f"refusing to overwrite file: {path}"
        ) from exc

    finally:
        if descriptor is not None:
            os.close(
                descriptor
            )


def _link_no_clobber(
    source: Path,
    destination: Path,
) -> None:
    try:
        os.link(
            source,
            destination,
        )
    except FileExistsError as exc:
        raise MonthlyTaxonomyWrapperError(
            f"refusing to overwrite path: {destination}"
        ) from exc


def _remove_owned_file(
    *,
    path: Path,
    device: int,
    inode: int,
    label: str,
) -> None:
    if not os.path.lexists(
        path
    ):
        return

    if (
        path.is_symlink()
        or not path.is_file()
    ):
        raise MonthlyTaxonomyWrapperError(
            f"{label} cleanup target is unsafe"
        )

    observed = path.stat()

    if (
        observed.st_dev != device
        or observed.st_ino != inode
    ):
        raise MonthlyTaxonomyWrapperError(
            f"{label} cleanup target identity changed"
        )

    path.unlink()


def _remove_owned_directory(
    *,
    path: Path,
    device: int,
    inode: int,
    label: str,
) -> None:
    if not os.path.lexists(
        path
    ):
        return

    if (
        path.is_symlink()
        or not path.is_dir()
    ):
        raise MonthlyTaxonomyWrapperError(
            f"{label} cleanup target is unsafe"
        )

    observed = path.stat()

    if (
        observed.st_dev != device
        or observed.st_ino != inode
    ):
        raise MonthlyTaxonomyWrapperError(
            f"{label} cleanup target identity changed"
        )

    if any(
        path.iterdir()
    ):
        raise MonthlyTaxonomyWrapperError(
            f"{label} cleanup directory is not empty"
        )

    path.rmdir()


def wrapper_sha256() -> str:
    return sha256_file(
        Path(
            __file__
        ).resolve()
    )


def verify_frozen_dependencies(
    repo: Path,
) -> None:
    for relative, expected in (
        FROZEN_DEPENDENCIES.items()
    ):
        path = (
            repo
            / relative
        )

        if (
            path.is_symlink()
            or not path.is_file()
        ):
            raise MonthlyTaxonomyWrapperError(
                f"frozen dependency missing: {relative}"
            )

        if sha256_file(
            path
        ) != expected:
            raise MonthlyTaxonomyWrapperError(
                "frozen dependency SHA256 mismatch: "
                f"{relative}"
            )


def repository_preflight(
    repo: Path,
    *,
    execution_commit: str,
) -> Path:
    root = _require_repository(
        repo
    )

    commit = _commit(
        execution_commit
    )

    verify_frozen_dependencies(
        root
    )

    try:
        head = git_output(
            root,
            "rev-parse",
            "HEAD",
        )

        origin = git_output(
            root,
            "rev-parse",
            "origin/main",
        )

        status = git_output(
            root,
            "status",
            "--porcelain",
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ) as exc:
        raise MonthlyTaxonomyWrapperError(
            "repository preflight Git check failed"
        ) from exc

    if head != commit:
        raise MonthlyTaxonomyWrapperError(
            "HEAD differs from execution commit"
        )

    if origin != commit:
        raise MonthlyTaxonomyWrapperError(
            "origin/main differs from execution commit"
        )

    if status:
        raise MonthlyTaxonomyWrapperError(
            "repository working tree is not clean"
        )

    return root


def _load_module(
    path: Path,
    *,
    module_name: str,
    expected_sha256: str,
) -> ModuleType:
    if (
        path.is_symlink()
        or not path.is_file()
    ):
        raise MonthlyTaxonomyWrapperError(
            f"frozen validation wrapper missing: {path}"
        )

    if sha256_file(
        path
    ) != expected_sha256:
        raise MonthlyTaxonomyWrapperError(
            f"frozen validation wrapper SHA256 mismatch: {path}"
        )

    spec = (
        importlib.util
        .spec_from_file_location(
            module_name,
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise MonthlyTaxonomyWrapperError(
            f"cannot load frozen validation wrapper: {path}"
        )

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    sys.modules[
        module_name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


def load_frozen_stage6_execution(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo
        / STAGE6_WRAPPER_RELATIVE,
        module_name=(
            "_bacselect_frozen_monthly_"
            "chromosome_integrity_execution"
        ),
        expected_sha256=(
            EXPECTED_STAGE6_WRAPPER_SHA256
        ),
    )


def _stage6_count(
    rows: Sequence[
        Mapping[
            str,
            str,
        ]
    ],
    *,
    field: str,
    value: str,
) -> int:
    return sum(
        row[
            field
        ]
        == value
        for row in rows
    )


def authenticate_current_upstream(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    authoritative_root: Path,
    execution_commit: str,
    stage6_execution: ModuleType | None = None,
) -> AuthenticatedCurrentUpstream:
    """Rebuild Stage 1 through Stage 6 without re-running Stage 6."""

    root = Path(
        repo
    ).resolve()

    production = (
        _require_absolute_real_directory(
            production_root,
            label="production root",
        )
    )

    stage1 = (
        _require_absolute_real_directory(
            stage1_root,
            label="Stage 1 root",
        )
    )

    authoritative = (
        _require_absolute_real_directory(
            authoritative_root,
            label="authoritative root",
        )
    )

    commit = _commit(
        execution_commit
    )

    stage6 = (
        stage6_execution
        if stage6_execution is not None
        else load_frozen_stage6_execution(
            root
        )
    )

    try:
        stage6.verify_frozen_dependencies(
            root
        )

        stage5_execution = (
            stage6
            .load_frozen_stage5_execution(
                root
            )
        )

        stage4_execution = (
            stage5_execution
            .load_frozen_stage4_execution(
                root
            )
        )

        cache_execution = (
            stage5_execution
            .load_frozen_cache_execution(
                root
            )
        )

        catalogue_execution = (
            stage5_execution
            .load_frozen_catalogue_execution(
                root
            )
        )

        stage5_context = (
            stage6
            .load_stage5_context(
                repo=root,
                production_root=(
                    production
                ),
                stage1_root=(
                    stage1
                ),
                authoritative_root=(
                    authoritative
                ),
                execution_commit=(
                    commit
                ),
                stage5_execution=(
                    stage5_execution
                ),
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
        )
    except Exception as exc:
        raise MonthlyTaxonomyWrapperError(
            "Stage 5 upstream reconstruction failed"
        ) from exc

    release = _release_id(
        stage5_context.release_id
    )

    snapshot = _nonempty_text(
        stage5_context.source_snapshot_id,
        label="source snapshot ID",
    )

    if (
        stage5_context.execution_commit
        != commit
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 5 execution commit changed"
        )

    expected_stage1 = (
        production
        / release
        / "production"
        / commit
    )

    if (
        not expected_stage1.exists()
        or expected_stage1.resolve()
        != stage1
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 1 root does not match release/commit path"
        )

    try:
        population = (
            stage6
            .monthly_chromosome_integrity
            .build_monthly_chromosome_population(
                stage5_context
                .decisions_payload,
                expected_biosample_decisions_sha256=(
                    stage5_context
                    .completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=release,
                source_snapshot_id=snapshot,
                origin_git_commit=commit,
            )
        )
    except Exception as exc:
        raise MonthlyTaxonomyWrapperError(
            "Stage 6 population reconstruction failed"
        ) from exc

    stage6_stage = (
        stage1
        / stage6.STAGE_NAME
    )

    try:
        stage5_execution._require_real_directory(
            stage6_stage,
            label="canonical Stage 6 stage",
        )

        stage5_execution._require_exact_inventory(
            stage6_stage,
            expected_files={
                stage6.DECISIONS_NAME,
                stage6.RECORD_NAME,
            },
            label="canonical Stage 6 stage",
        )

        decisions_payload = (
            stage5_execution
            ._require_regular_file(
                stage6_stage
                / stage6.DECISIONS_NAME,
                label="Stage 6 decisions",
            )
            .read_bytes()
        )

        record_payload = (
            stage5_execution
            ._require_regular_file(
                stage6_stage
                / stage6.RECORD_NAME,
                label="Stage 6 record",
            )
            .read_bytes()
        )

        completion_payload = (
            stage5_execution
            ._require_regular_file(
                stage1
                / stage6.COMPLETION_NAME,
                label="Stage 6 completion",
            )
            .read_bytes()
        )
    except Exception as exc:
        raise MonthlyTaxonomyWrapperError(
            "Stage 6 artifact loading failed"
        ) from exc

    try:
        decision_rows = (
            stage6
            .monthly_chromosome_integrity
            .audit_monthly_chromosome_decisions(
                decisions_payload
            )
        )

        stage6_record = (
            stage6
            .monthly_chromosome_integrity
            .audit_monthly_chromosome_record(
                record_payload,
                biosample_decisions_payload=(
                    stage5_context
                    .decisions_payload
                ),
                expected_biosample_decisions_sha256=(
                    stage5_context
                    .completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=release,
                source_snapshot_id=snapshot,
                origin_git_commit=commit,
                biosample_record_sha256=(
                    sha256_bytes(
                        stage5_context
                        .record_payload
                    )
                ),
                biosample_completion_sha256=(
                    sha256_bytes(
                        stage5_context
                        .completion_payload
                    )
                ),
                decisions_payload=(
                    decisions_payload
                ),
            )
        )
    except Exception as exc:
        raise MonthlyTaxonomyWrapperError(
            "Stage 6 pure evidence authentication failed"
        ) from exc

    if stage6_record.get(
        "schema_version"
    ) != (
        stage6
        .monthly_chromosome_integrity
        .MONTHLY_CHROMOSOME_RECORD_SCHEMA
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 6 record schema changed"
        )

    if stage6_record.get(
        "status"
    ) != (
        stage6
        .monthly_chromosome_integrity
        .MONTHLY_CHROMOSOME_STATUS
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 6 record status changed"
        )

    decision_count = len(
        decision_rows
    )

    triggered_count = (
        _stage6_count(
            decision_rows,
            field=(
                "chromosome_integrity_triggered"
            ),
            value="1",
        )
    )

    reused_count = (
        _stage6_count(
            decision_rows,
            field=(
                "historical_adjudication_reused"
            ),
            value="1",
        )
    )

    pass_count = (
        _stage6_count(
            decision_rows,
            field=(
                "chromosome_integrity_status"
            ),
            value=(
                stage6
                .source_chromosome_integrity
                .PASS
            ),
        )
    )

    excluded_count = (
        _stage6_count(
            decision_rows,
            field=(
                "chromosome_integrity_status"
            ),
            value=(
                stage6
                .source_chromosome_integrity
                .EXCLUDE
            ),
        )
    )

    unresolved_count = (
        _stage6_count(
            decision_rows,
            field=(
                "chromosome_integrity_status"
            ),
            value=(
                stage6
                .source_chromosome_integrity
                .UNRESOLVED
            ),
        )
    )

    completion_kwargs = {
        "release_id":
            release,
        "source_snapshot_id":
            snapshot,
        "execution_commit":
            commit,
        "biosample_decisions_sha256":
            sha256_bytes(
                stage5_context
                .decisions_payload
            ),
        "biosample_record_sha256":
            sha256_bytes(
                stage5_context
                .record_payload
            ),
        "biosample_completion_sha256":
            sha256_bytes(
                stage5_context
                .completion_payload
            ),
        "continue_count":
            len(
                population
                .continue_accessions
            ),
        "continue_accessions_sha256":
            population
            .continue_accessions_sha256,
        "decision_count":
            decision_count,
        "triggered_candidate_count":
            triggered_count,
        "nontriggered_candidate_count":
            (
                decision_count
                - triggered_count
            ),
        "historical_adjudication_reuse_count":
            reused_count,
        "pass_count":
            pass_count,
        "excluded_count":
            excluded_count,
        "unresolved_count":
            unresolved_count,
        "decisions_sha256":
            sha256_bytes(
                decisions_payload
            ),
        "record_sha256":
            sha256_bytes(
                record_payload
            ),
        "stage5_execution":
            stage5_execution,
    }

    try:
        expected_completion = (
            stage6
            .build_completion_receipt(
                **completion_kwargs
            )
        )

        if (
            completion_payload
            != expected_completion
        ):
            raise MonthlyTaxonomyWrapperError(
                "Stage 6 completion differs from reconstructed evidence"
            )

        completion_record = (
            stage6
            .audit_completion_receipt(
                completion_payload,
                **completion_kwargs,
            )
        )
    except MonthlyTaxonomyWrapperError:
        raise
    except Exception as exc:
        raise MonthlyTaxonomyWrapperError(
            "Stage 6 completion authentication failed"
        ) from exc

    if completion_record.get(
        "schema_version"
    ) != stage6.COMPLETION_SCHEMA:
        raise MonthlyTaxonomyWrapperError(
            "Stage 6 completion schema changed"
        )

    if completion_record.get(
        "status"
    ) != stage6.COMPLETION_STATUS:
        raise MonthlyTaxonomyWrapperError(
            "Stage 6 completion status changed"
        )

    checkpoint_path = (
        stage1
        / CHECKPOINT_NAME
    )

    raw_path = (
        stage1
        / RAW_RESPONSE_NAME
    )

    snapshot_path = (
        stage1
        / SOURCE_SNAPSHOT_RECORD_NAME
    )

    checkpoint_payload = (
        _require_regular_file(
            checkpoint_path,
            label="Stage 1 release-start checkpoint",
        )
        .read_bytes()
    )

    raw_payload = (
        _require_regular_file(
            raw_path,
            label="Stage 1 raw source response",
        )
        .read_bytes()
    )

    source_snapshot_payload = (
        _require_regular_file(
            snapshot_path,
            label="Stage 1 source-snapshot record",
        )
        .read_bytes()
    )

    try:
        start_record = (
            monthly_release_start
            .audit_release_start_checkpoint(
                checkpoint_payload,
                expected_git_commit=(
                    commit
                ),
            )
        )

        source_record = (
            monthly_release_start
            .audit_source_snapshot_record(
                source_snapshot_payload,
                release_start_checkpoint=(
                    checkpoint_payload
                ),
                raw_response=(
                    raw_payload
                ),
            )
        )
    except Exception as exc:
        raise MonthlyTaxonomyWrapperError(
            "canonical Stage 1 reauthentication failed"
        ) from exc

    if start_record.get(
        "release_id"
    ) != release:
        raise MonthlyTaxonomyWrapperError(
            "Stage 1 release differs from Stage 6"
        )

    if source_record.get(
        "release_id"
    ) != release:
        raise MonthlyTaxonomyWrapperError(
            "Stage 1 source release differs from Stage 6"
        )

    if source_record.get(
        "source_snapshot_id"
    ) != snapshot:
        raise MonthlyTaxonomyWrapperError(
            "Stage 1 source snapshot differs from Stage 6"
        )

    authenticated_snapshot_sha = (
        stage5_context
        .stage4_context
        .metadata_context
        .source_snapshot_record_sha256
    )

    if (
        sha256_bytes(
            source_snapshot_payload
        )
        != authenticated_snapshot_sha
    ):
        raise MonthlyTaxonomyWrapperError(
            "canonical source-snapshot record differs "
            "from authenticated upstream chain"
        )

    if (
        source_record[
            "raw_response_sha256"
        ]
        != sha256_bytes(
            raw_payload
        )
    ):
        raise MonthlyTaxonomyWrapperError(
            "canonical raw source response differs "
            "from authenticated source-snapshot record"
        )

    support_upstream = (
        monthly_taxonomy_snapshot_execution
        .build_authenticated_upstream_context(
            source_snapshot_record_payload=(
                source_snapshot_payload
            ),
            raw_source_response_payload=(
                raw_payload
            ),
            expected_release_id=release,
            expected_source_snapshot_id=(
                snapshot
            ),
            expected_source_snapshot_record_sha256=(
                authenticated_snapshot_sha
            ),
            chromosome_integrity_decisions_sha256=(
                sha256_bytes(
                    decisions_payload
                )
            ),
            chromosome_integrity_record_sha256=(
                sha256_bytes(
                    record_payload
                )
            ),
            chromosome_integrity_completion_sha256=(
                sha256_bytes(
                    completion_payload
                )
            ),
            execution_git_commit=(
                commit
            ),
        )
    )

    support_upstream = (
        monthly_taxonomy_snapshot_execution
        .audit_authenticated_upstream_context(
            support_upstream
        )
    )

    identity = (
        release,
        snapshot,
        commit,
        support_upstream
        .source_snapshot_record_sha256,
        support_upstream
        .source_raw_response_sha256,
        support_upstream
        .chromosome_integrity_decisions_sha256,
        support_upstream
        .chromosome_integrity_record_sha256,
        support_upstream
        .chromosome_integrity_completion_sha256,
        sha256_bytes(
            checkpoint_payload
        ),
        sha256_bytes(
            stage5_context
            .decisions_payload
        ),
        sha256_bytes(
            stage5_context
            .record_payload
        ),
        sha256_bytes(
            stage5_context
            .completion_payload
        ),
    )

    return AuthenticatedCurrentUpstream(
        support_upstream=(
            support_upstream
        ),
        stage6_decisions_payload=(
            decisions_payload
        ),
        stage6_record_payload=(
            record_payload
        ),
        stage6_completion_payload=(
            completion_payload
        ),
        identity=identity,
    )


def build_completion_receipt(
    *,
    upstream: (
        monthly_taxonomy_snapshot_execution
        .AuthenticatedMonthlyTaxonomyUpstream
    ),
    support_result: (
        monthly_taxonomy_snapshot_execution
        .MonthlyTaxonomySupportResult
    ),
    validation_wrapper_sha256: str,
) -> bytes:
    upstream = (
        monthly_taxonomy_snapshot_execution
        .audit_authenticated_upstream_context(
            upstream
        )
    )

    if not isinstance(
        support_result,
        monthly_taxonomy_snapshot_execution
        .MonthlyTaxonomySupportResult,
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 support result has wrong type"
        )

    if (
        support_result.release_id
        != upstream.release_id
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 support release changed"
        )

    if (
        support_result.source_snapshot_id
        != upstream.source_snapshot_id
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 support source snapshot changed"
        )

    verified_count = _count(
        support_result
        .authoritative_verified_object_count,
        label=(
            "authoritative verified-object count"
        ),
    )

    if (
        verified_count
        != monthly_taxonomy_snapshot_execution
        .EXPECTED_AUTHORITATIVE_VERIFIED_OBJECT_COUNT
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 authoritative verified-object count changed"
        )

    support_sha = (
        monthly_taxonomy_snapshot_execution
        .execution_support_module_sha256()
    )

    if support_sha != (
        EXPECTED_EXECUTION_SUPPORT_SHA256
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 support implementation identity changed"
        )

    payload = {
        "schema_version":
            COMPLETION_SCHEMA,
        "status":
            COMPLETION_STATUS,
        "release_id":
            _release_id(
                upstream.release_id
            ),
        "source_snapshot_id":
            _nonempty_text(
                upstream.source_snapshot_id,
                label="source snapshot ID",
            ),
        "execution_git_commit":
            _commit(
                upstream.execution_git_commit
            ),
        "execution_support_module_sha256":
            _sha256(
                support_sha,
                label=(
                    "execution-support module SHA256"
                ),
            ),
        "validation_wrapper_sha256":
            _sha256(
                validation_wrapper_sha256,
                label="validation-wrapper SHA256",
            ),
        "execution_method_sha256":
            EXPECTED_EXECUTION_METHOD_SHA256,
        "source_snapshot_record_sha256":
            _sha256(
                upstream
                .source_snapshot_record_sha256,
                label=(
                    "source-snapshot record SHA256"
                ),
            ),
        "source_raw_response_sha256":
            _sha256(
                upstream
                .source_raw_response_sha256,
                label=(
                    "raw source-response SHA256"
                ),
            ),
        "chromosome_integrity_decisions_sha256":
            _sha256(
                upstream
                .chromosome_integrity_decisions_sha256,
                label=(
                    "chromosome-integrity decisions SHA256"
                ),
            ),
        "chromosome_integrity_record_sha256":
            _sha256(
                upstream
                .chromosome_integrity_record_sha256,
                label=(
                    "chromosome-integrity record SHA256"
                ),
            ),
        "chromosome_integrity_completion_sha256":
            _sha256(
                upstream
                .chromosome_integrity_completion_sha256,
                label=(
                    "chromosome-integrity completion SHA256"
                ),
            ),
        "taxonomy_snapshot_id":
            _nonempty_text(
                support_result
                .taxonomy_snapshot_id,
                label="taxonomy snapshot ID",
            ),
        "monthly_taxonomy_snapshot_record_sha256":
            _sha256(
                support_result
                .record_sha256,
                label=(
                    "monthly taxonomy-snapshot record SHA256"
                ),
            ),
        "taxonomy_archive_sha256":
            _sha256(
                support_result
                .archive_sha256,
                label="taxonomy archive SHA256",
            ),
        "nodes_sha256":
            _sha256(
                support_result
                .nodes_sha256,
                label="nodes.dmp SHA256",
            ),
        "merged_sha256":
            _sha256(
                support_result
                .merged_sha256,
                label="merged.dmp SHA256",
            ),
        "delnodes_sha256":
            _sha256(
                support_result
                .delnodes_sha256,
                label="delnodes.dmp SHA256",
            ),
        "taxonomy_acquisition_provenance_sha256":
            _sha256(
                support_result
                .acquisition_provenance_sha256,
                label=(
                    "taxonomy acquisition-provenance SHA256"
                ),
            ),
        "taxonomy_content_manifest_sha256":
            _sha256(
                support_result
                .content_manifest_sha256,
                label=(
                    "taxonomy content-manifest SHA256"
                ),
            ),
        "authoritative_storage_manifest_sha256":
            _sha256(
                support_result
                .authoritative_manifest_sha256,
                label=(
                    "authoritative-storage manifest SHA256"
                ),
            ),
        "authoritative_storage_manifest_key":
            _nonempty_text(
                support_result
                .authoritative_manifest_key,
                label=(
                    "authoritative-storage manifest key"
                ),
            ),
        "authoritative_storage_receipt_sha256":
            _sha256(
                support_result
                .authoritative_receipt_sha256,
                label=(
                    "authoritative-storage receipt SHA256"
                ),
            ),
        "authoritative_storage_receipt_key":
            _nonempty_text(
                support_result
                .authoritative_receipt_key,
                label=(
                    "authoritative-storage receipt key"
                ),
            ),
        "authoritative_verified_object_count":
            verified_count,
    }

    if set(
        payload
    ) != COMPLETION_FIELDS:
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 completion schema construction changed"
        )

    return _canonical_json(
        payload
    )


def audit_completion_receipt(
    payload: bytes,
    *,
    upstream: (
        monthly_taxonomy_snapshot_execution
        .AuthenticatedMonthlyTaxonomyUpstream
    ),
    support_result: (
        monthly_taxonomy_snapshot_execution
        .MonthlyTaxonomySupportResult
    ),
    validation_wrapper_sha256: str,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 completion receipt must be bytes"
        )

    try:
        record = json.loads(
            payload
        )
    except json.JSONDecodeError as exc:
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 completion receipt is invalid JSON"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 completion receipt must be an object"
        )

    if set(
        record
    ) != COMPLETION_FIELDS:
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 completion receipt schema changed"
        )

    expected = build_completion_receipt(
        upstream=upstream,
        support_result=(
            support_result
        ),
        validation_wrapper_sha256=(
            validation_wrapper_sha256
        ),
    )

    if payload != expected:
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 completion receipt differs "
            "from reconstructed evidence"
        )

    if record.get(
        "schema_version"
    ) != COMPLETION_SCHEMA:
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 completion schema version changed"
        )

    if record.get(
        "status"
    ) != COMPLETION_STATUS:
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 completion status changed"
        )

    if record.get(
        "authoritative_verified_object_count"
    ) != 8:
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 completion authoritative count changed"
        )

    return record


def _expected_stage_hashes(
    support_result: (
        monthly_taxonomy_snapshot_execution
        .MonthlyTaxonomySupportResult
    ),
) -> dict[
    str,
    str,
]:
    return {
        monthly_taxonomy_snapshot_execution.ARCHIVE_NAME:
            support_result.archive_sha256,
        "nodes.dmp":
            support_result.nodes_sha256,
        "merged.dmp":
            support_result.merged_sha256,
        "delnodes.dmp":
            support_result.delnodes_sha256,
        (
            monthly_taxonomy_snapshot_execution
            .ACQUISITION_PROVENANCE_NAME
        ):
            support_result
            .acquisition_provenance_sha256,
        (
            monthly_taxonomy_snapshot_execution
            .CONTENT_MANIFEST_NAME
        ):
            support_result
            .content_manifest_sha256,
        (
            monthly_taxonomy_snapshot_execution
            .RECORD_NAME
        ):
            support_result.record_sha256,
        (
            monthly_taxonomy_snapshot_execution
            .AUTHORITATIVE_MANIFEST_LOCAL_NAME
        ):
            support_result
            .authoritative_manifest_sha256,
        (
            monthly_taxonomy_snapshot_execution
            .AUTHORITATIVE_RECEIPT_LOCAL_NAME
        ):
            support_result
            .authoritative_receipt_sha256,
    }


def audit_stage_directory(
    stage: Path,
    *,
    support_result: (
        monthly_taxonomy_snapshot_execution
        .MonthlyTaxonomySupportResult
    ),
) -> dict[
    str,
    tuple[
        int,
        int,
    ],
]:
    directory = (
        _require_absolute_real_directory(
            stage,
            label="Stage 7 stage directory",
        )
    )

    expected_hashes = (
        _expected_stage_hashes(
            support_result
        )
    )

    if set(
        expected_hashes
    ) != (
        monthly_taxonomy_snapshot_execution
        .LOCAL_STAGE_FILES
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 expected local inventory changed"
        )

    _require_exact_inventory(
        directory,
        expected_files=set(
            expected_hashes
        ),
        label="Stage 7 stage",
    )

    identities = {}

    for name, expected_sha in (
        expected_hashes.items()
    ):
        path = _require_regular_file(
            directory
            / name,
            label=f"Stage 7 artifact {name}",
        )

        observed_sha = sha256_file(
            path
        )

        if observed_sha != _sha256(
            expected_sha,
            label=f"Stage 7 artifact {name} SHA256",
        ):
            raise MonthlyTaxonomyWrapperError(
                f"Stage 7 artifact identity changed: {name}"
            )

        stat = path.stat()

        identities[
            name
        ] = (
            stat.st_dev,
            stat.st_ino,
        )

    return identities


def publish_stage(
    *,
    stage1_root: Path,
    partial: Path,
    final: Path,
    support_result: (
        monthly_taxonomy_snapshot_execution
        .MonthlyTaxonomySupportResult
    ),
    stability_check: Callable[
        [],
        None,
    ],
) -> Path:
    stage1 = (
        _require_absolute_real_directory(
            stage1_root,
            label="Stage 1 root",
        )
    )

    partial_dir = (
        _require_absolute_real_directory(
            partial,
            label="partial taxonomy stage",
        )
    )

    if final != (
        stage1
        / STAGE_NAME
    ):
        raise MonthlyTaxonomyWrapperError(
            "canonical Stage 7 path changed"
        )

    if os.path.lexists(
        final
    ):
        raise MonthlyTaxonomyWrapperError(
            "canonical taxonomy stage already exists"
        )

    partial_identities = (
        audit_stage_directory(
            partial_dir,
            support_result=(
                support_result
            ),
        )
    )

    stability_check()

    final.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    final_stat = final.stat()

    linked = {}

    try:
        for name in sorted(
            monthly_taxonomy_snapshot_execution
            .LOCAL_STAGE_FILES
        ):
            source = (
                partial_dir
                / name
            )

            destination = (
                final
                / name
            )

            _link_no_clobber(
                source,
                destination,
            )

            observed = (
                destination.stat()
            )

            source_device, source_inode = (
                partial_identities[
                    name
                ]
            )

            if (
                observed.st_dev != source_device
                or observed.st_ino != source_inode
            ):
                raise MonthlyTaxonomyWrapperError(
                    f"published Stage 7 artifact "
                    f"is not source hard link: {name}"
                )

            linked[
                name
            ] = (
                observed.st_dev,
                observed.st_ino,
            )

        _fsync_directory(
            final
        )

        audit_stage_directory(
            final,
            support_result=(
                support_result
            ),
        )

        stability_check()

        for name in sorted(
            monthly_taxonomy_snapshot_execution
            .LOCAL_STAGE_FILES
        ):
            device, inode = (
                partial_identities[
                    name
                ]
            )

            _remove_owned_file(
                path=(
                    partial_dir
                    / name
                ),
                device=device,
                inode=inode,
                label=(
                    f"partial Stage 7 artifact {name}"
                ),
            )

        _fsync_directory(
            partial_dir
        )

        partial_stat = (
            partial_dir.stat()
        )

        _remove_owned_directory(
            path=partial_dir,
            device=(
                partial_stat.st_dev
            ),
            inode=(
                partial_stat.st_ino
            ),
            label="partial Stage 7 directory",
        )

        _fsync_directory(
            stage1
        )

        audit_stage_directory(
            final,
            support_result=(
                support_result
            ),
        )

    except Exception as exc:
        cleanup_errors = []

        for name, (
            device,
            inode,
        ) in reversed(
            tuple(
                linked.items()
            )
        ):
            try:
                _remove_owned_file(
                    path=(
                        final
                        / name
                    ),
                    device=device,
                    inode=inode,
                    label=(
                        f"published Stage 7 artifact {name}"
                    ),
                )
            except Exception as cleanup_exc:
                cleanup_errors.append(
                    cleanup_exc
                )

        try:
            _remove_owned_directory(
                path=final,
                device=(
                    final_stat.st_dev
                ),
                inode=(
                    final_stat.st_ino
                ),
                label="canonical Stage 7 directory",
            )
        except Exception as cleanup_exc:
            cleanup_errors.append(
                cleanup_exc
            )

        try:
            _fsync_directory(
                stage1
            )
        except Exception as cleanup_exc:
            cleanup_errors.append(
                cleanup_exc
            )

        if cleanup_errors:
            raise MonthlyTaxonomyWrapperError(
                "Stage 7 canonical publication failed "
                "and cleanup was incomplete"
            ) from exc

        raise

    return final


def publish_completion(
    *,
    stage1_root: Path,
    payload: bytes,
    auditor: Callable[
        [
            bytes,
        ],
        object,
    ],
    stability_check: Callable[
        [],
        None,
    ],
) -> Path:
    stage1 = (
        _require_absolute_real_directory(
            stage1_root,
            label="Stage 1 root",
        )
    )

    final = (
        stage1
        / COMPLETION_NAME
    )

    temporary = (
        stage1
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlyTaxonomyWrapperError(
            "taxonomy completion already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlyTaxonomyWrapperError(
            "taxonomy completion temporary artifact already exists"
        )

    _write_no_clobber(
        temporary,
        payload,
    )

    _fsync_directory(
        stage1
    )

    temporary_file = (
        _require_regular_file(
            temporary,
            label="temporary taxonomy completion",
        )
    )

    temporary_stat = (
        temporary_file.stat()
    )

    final_linked = False
    final_stat = None

    try:
        temporary_payload = (
            temporary_file.read_bytes()
        )

        if temporary_payload != payload:
            raise MonthlyTaxonomyWrapperError(
                "temporary taxonomy completion readback changed"
            )

        auditor(
            temporary_payload
        )

        stability_check()

        _link_no_clobber(
            temporary,
            final,
        )

        final_linked = True
        final_stat = final.stat()

        _fsync_directory(
            stage1
        )

        final_payload = (
            _require_regular_file(
                final,
                label="published taxonomy completion",
            )
            .read_bytes()
        )

        if final_payload != payload:
            raise MonthlyTaxonomyWrapperError(
                "published taxonomy completion readback changed"
            )

        auditor(
            final_payload
        )

        stability_check()

    except Exception as exc:
        cleanup_errors = []

        if (
            final_linked
            and final_stat is not None
        ):
            try:
                _remove_owned_file(
                    path=final,
                    device=(
                        final_stat.st_dev
                    ),
                    inode=(
                        final_stat.st_ino
                    ),
                    label=(
                        "published taxonomy completion"
                    ),
                )
            except Exception as cleanup_exc:
                cleanup_errors.append(
                    cleanup_exc
                )

        if not os.path.lexists(
            final
        ):
            try:
                _remove_owned_file(
                    path=temporary,
                    device=(
                        temporary_stat.st_dev
                    ),
                    inode=(
                        temporary_stat.st_ino
                    ),
                    label=(
                        "temporary taxonomy completion"
                    ),
                )
            except Exception as cleanup_exc:
                cleanup_errors.append(
                    cleanup_exc
                )

        try:
            _fsync_directory(
                stage1
            )
        except Exception as cleanup_exc:
            cleanup_errors.append(
                cleanup_exc
            )

        if cleanup_errors:
            raise MonthlyTaxonomyWrapperError(
                "taxonomy completion publication "
                "failed and cleanup was incomplete"
            ) from exc

        raise

    _remove_owned_file(
        path=temporary,
        device=(
            temporary_stat.st_dev
        ),
        inode=(
            temporary_stat.st_ino
        ),
        label="temporary taxonomy completion",
    )

    _fsync_directory(
        stage1
    )

    return final


def execute_monthly_taxonomy_snapshot(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    authoritative_root: Path,
    execution_commit: str,
    opener: Callable[
        ...,
        object,
    ] = urllib.request.urlopen,
    timestamp_provider: Callable[
        [],
        str,
    ] | None = None,
    timeout: float = (
        monthly_taxonomy_snapshot_execution
        .DEFAULT_TIMEOUT_SECONDS
    ),
) -> MonthlyTaxonomyExecutionResult:
    root = repository_preflight(
        repo,
        execution_commit=(
            execution_commit
        ),
    )

    production = (
        _require_absolute_real_directory(
            production_root,
            label="production root",
        )
    )

    stage1 = (
        _require_absolute_real_directory(
            stage1_root,
            label="Stage 1 root",
        )
    )

    authoritative = (
        _require_absolute_real_directory(
            authoritative_root,
            label="authoritative root",
        )
    )

    commit = _commit(
        execution_commit
    )

    stage6 = (
        load_frozen_stage6_execution(
            root
        )
    )

    initial = (
        authenticate_current_upstream(
            repo=root,
            production_root=(
                production
            ),
            stage1_root=(
                stage1
            ),
            authoritative_root=(
                authoritative
            ),
            execution_commit=(
                commit
            ),
            stage6_execution=(
                stage6
            ),
        )
    )

    partial = (
        stage1
        / PARTIAL_NAME
    )

    final = (
        stage1
        / STAGE_NAME
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
            partial,
            "partial taxonomy stage",
        ),
        (
            final,
            "canonical taxonomy stage",
        ),
        (
            completion,
            "taxonomy completion",
        ),
        (
            completion_temp,
            "taxonomy completion temporary artifact",
        ),
    ):
        if os.path.lexists(
            path
        ):
            raise MonthlyTaxonomyWrapperError(
                f"{label} already exists"
            )

    def stability_check() -> None:
        observed = (
            authenticate_current_upstream(
                repo=root,
                production_root=(
                    production
                ),
                stage1_root=(
                    stage1
                ),
                authoritative_root=(
                    authoritative
                ),
                execution_commit=(
                    commit
                ),
                stage6_execution=(
                    stage6
                ),
            )
        )

        if (
            observed.identity
            != initial.identity
        ):
            raise MonthlyTaxonomyWrapperError(
                "Stage 1 or Stage 6 evidence changed during Stage 7"
            )

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    wrapper_sha = (
        wrapper_sha256()
    )

    support_kwargs: dict[
        str,
        Any,
    ] = {
        "workspace":
            partial,
        "authoritative_root":
            authoritative,
        "upstream":
            initial.support_upstream,
        "validation_wrapper_sha256":
            wrapper_sha,
        "upstream_stability_check":
            stability_check,
        "opener":
            opener,
        "timeout":
            timeout,
    }

    if timestamp_provider is not None:
        support_kwargs[
            "timestamp_provider"
        ] = timestamp_provider

    try:
        support_result = (
            monthly_taxonomy_snapshot_execution
            .execute_monthly_taxonomy_support(
                **support_kwargs
            )
        )
    except Exception as exc:
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 execution-support layer failed"
        ) from exc

    if (
        support_result.workspace.resolve()
        != partial.resolve()
    ):
        raise MonthlyTaxonomyWrapperError(
            "Stage 7 support workspace changed"
        )

    publish_stage(
        stage1_root=stage1,
        partial=partial,
        final=final,
        support_result=(
            support_result
        ),
        stability_check=(
            stability_check
        ),
    )

    completion_payload = (
        build_completion_receipt(
            upstream=(
                initial
                .support_upstream
            ),
            support_result=(
                support_result
            ),
            validation_wrapper_sha256=(
                wrapper_sha
            ),
        )
    )

    completion_path = (
        publish_completion(
            stage1_root=stage1,
            payload=(
                completion_payload
            ),
            auditor=lambda payload:
                audit_completion_receipt(
                    payload,
                    upstream=(
                        initial
                        .support_upstream
                    ),
                    support_result=(
                        support_result
                    ),
                    validation_wrapper_sha256=(
                        wrapper_sha
                    ),
                ),
            stability_check=(
                stability_check
            ),
        )
    )

    return MonthlyTaxonomyExecutionResult(
        release_id=(
            initial
            .support_upstream
            .release_id
        ),
        source_snapshot_id=(
            initial
            .support_upstream
            .source_snapshot_id
        ),
        taxonomy_snapshot_id=(
            support_result
            .taxonomy_snapshot_id
        ),
        stage_path=(
            final
        ),
        completion_path=(
            completion_path
        ),
        record_sha256=(
            support_result
            .record_sha256
        ),
        completion_sha256=(
            sha256_bytes(
                completion_payload
            )
        ),
        authoritative_manifest_sha256=(
            support_result
            .authoritative_manifest_sha256
        ),
        authoritative_receipt_sha256=(
            support_result
            .authoritative_receipt_sha256
        ),
    )


def parse_args(
    argv: Sequence[
        str
    ] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute BacSelect portable monthly "
            "taxonomy-snapshot Stage 7."
        )
    )

    parser.add_argument(
        "--repo",
        required=True,
        type=Path,
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
        "--execution-commit",
        required=True,
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    return parser.parse_args(
        argv
    )


def main(
    argv: Sequence[
        str
    ] | None = None,
) -> int:
    args = parse_args(
        argv
    )

    if not args.authorize_real_execution:
        raise MonthlyTaxonomyWrapperError(
            "production taxonomy-snapshot execution "
            "requires explicit authorization"
        )

    result = (
        execute_monthly_taxonomy_snapshot(
            repo=args.repo,
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
                args.execution_commit
            ),
        )
    )

    print(
        "PASS | BacSelect monthly "
        "taxonomy snapshot complete"
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        f"source_snapshot_id="
        f"{result.source_snapshot_id}"
    )

    print(
        f"taxonomy_snapshot_id="
        f"{result.taxonomy_snapshot_id}"
    )

    print(
        f"record_sha256="
        f"{result.record_sha256}"
    )

    print(
        f"completion_sha256="
        f"{result.completion_sha256}"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except (
        MonthlyTaxonomyWrapperError,
        monthly_taxonomy_snapshot_execution
        .MonthlyTaxonomyExecutionError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"ERROR | {exc}",
            file=sys.stderr,
        )

        raise SystemExit(
            1
        )
