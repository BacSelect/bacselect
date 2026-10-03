"""Fail-closed authority for ordinary and recovered monthly sequence batches."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
from typing import Mapping, Sequence


BATCH_RE = re.compile(
    r"^batch-[0-9]{5}$"
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

RELEASE_RE = re.compile(
    r"^[0-9]{4}\.(0[1-9]|1[0-2])$"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

SOURCE_CLASS_FRESH = "fresh"
SOURCE_CLASS_FRESH_RECOVERY = "fresh-recovery"

RECOVERY_SCHEMA_VERSION = 1
RECOVERY_STATUS = "RECOVERY_ACCEPTED"

SOURCE_BATCH_MANIFEST_NAME = (
    "source-batch-files.tsv"
)

SOURCE_PACKAGE_MANIFEST_NAME = (
    "source-package-files.tsv"
)

RECOVERY_PACKAGE_MANIFEST_NAME = (
    "recovery-package-files.tsv"
)

RECOVERY_ORIGIN_NAME = (
    "recovery-origin.json"
)

RECOVERY_SUMMARY_NAME = (
    "recovery-summary.json"
)

CANDIDATE_AUDIT_NAME = (
    "candidate-sequence-audit.tsv"
)

COMPONENT_AUDIT_NAME = (
    "component-sequence-audit.tsv"
)

PACKAGE_NAME = "package"

MANIFEST_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
)


class MonthlySequenceRecoveryAuthorityError(
    RuntimeError
):
    """Raised when recovery authority cannot be established exactly."""


@dataclass(frozen=True)
class TreeFingerprint:
    rows: tuple[
        Mapping[str, str],
        ...,
    ]
    payload: bytes
    sha256: str
    file_count: int


@dataclass(frozen=True)
class RecoveryWorkspace:
    batch_id: str
    partial_dir: Path
    final_dir: Path
    source_partial_dir: Path
    source_batch_sha256: str
    source_package_sha256: str


@dataclass(frozen=True)
class AcceptedRecoveryEvidence:
    batch_id: str
    batch_dir: Path
    source_partial_dir: Path
    source_production_commit: str
    recovery_commit: str
    source_batch_sha256: str
    source_package_sha256: str
    recovery_package_sha256: str
    candidate_audit_sha256: str
    component_audit_sha256: str
    summary_sha256: str


@dataclass(frozen=True)
class AuthoritativeSequenceBatch:
    batch_id: str
    source_class: str
    batch_dir: Path
    source_partial_dir: Path | None
    recovery_commit: str | None
    recovery_summary_sha256: str | None


def _fail(
    message: str,
) -> None:
    raise MonthlySequenceRecoveryAuthorityError(
        message
    )


def sha256_file(
    path: Path,
    block_size: int = 8 * 1024 * 1024,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                block_size
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def _batch_id(
    value: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or BATCH_RE.fullmatch(
            value
        )
        is None
    ):
        _fail(
            "invalid recovery batch ID"
        )

    return value


def _commit(
    value: str,
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
        _fail(
            f"invalid {label}"
        )

    return value


def _release_id(
    value: str,
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
        _fail(
            "invalid release ID"
        )

    return value


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
        or SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        _fail(
            f"invalid {label} SHA256"
        )

    return value


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    if (
        path.is_symlink()
        or not path.is_dir()
    ):
        _fail(
            f"{label} is not a real directory: "
            f"{path}"
        )

    return path


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    try:
        metadata = os.lstat(
            path
        )
    except FileNotFoundError:
        _fail(
            f"missing {label}: {path}"
        )

    if not stat.S_ISREG(
        metadata.st_mode
    ):
        _fail(
            f"{label} is not a regular file: "
            f"{path}"
        )

    return path


def _canonical_json_bytes(
    payload: Mapping[
        str,
        object,
    ],
) -> bytes:
    return (
        json.dumps(
            payload,
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


def _manifest_payload(
    rows: Sequence[
        Mapping[str, str]
    ],
) -> bytes:
    output = io.StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        output,
        fieldnames=MANIFEST_FIELDS,
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )

    writer.writeheader()

    for row in rows:
        writer.writerow(
            {
                field:
                    row[
                        field
                    ]
                for field
                in MANIFEST_FIELDS
            }
        )

    return output.getvalue().encode(
        "utf-8"
    )


def strict_tree_fingerprint(
    root: Path,
) -> TreeFingerprint:
    tree = _require_real_directory(
        Path(
            root
        ),
        label="fingerprinted tree",
    )

    rows = []

    for path in sorted(
        tree.rglob(
            "*"
        ),
        key=lambda value:
            value.relative_to(
                tree
            ).as_posix(),
    ):
        relative = path.relative_to(
            tree
        ).as_posix()

        metadata = os.lstat(
            path
        )

        if stat.S_ISLNK(
            metadata.st_mode
        ):
            _fail(
                "fingerprinted tree contains "
                f"symlink: {relative}"
            )

        if stat.S_ISDIR(
            metadata.st_mode
        ):
            continue

        if not stat.S_ISREG(
            metadata.st_mode
        ):
            _fail(
                "fingerprinted tree contains "
                f"non-regular file: {relative}"
            )

        rows.append(
            {
                "path":
                    relative,
                "size_bytes":
                    str(
                        metadata.st_size
                    ),
                "sha256":
                    sha256_file(
                        path
                    ),
            }
        )

    payload = _manifest_payload(
        rows
    )

    return TreeFingerprint(
        rows=tuple(
            rows
        ),
        payload=payload,
        sha256=hashlib.sha256(
            payload
        ).hexdigest(),
        file_count=len(
            rows
        ),
    )


def _write_new_file(
    path: Path,
    payload: bytes,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with path.open(
            "xb"
        ) as handle:
            handle.write(
                payload
            )
            handle.flush()
            os.fsync(
                handle.fileno()
            )
    except FileExistsError:
        _fail(
            f"refusing to overwrite existing "
            f"recovery evidence: {path}"
        )


def _load_json_object(
    path: Path,
    *,
    label: str,
) -> dict[
    str,
    object,
]:
    evidence = _require_regular_file(
        path,
        label=label,
    )

    try:
        value = json.loads(
            evidence.read_text(
                encoding="ascii"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise MonthlySequenceRecoveryAuthorityError(
            f"invalid {label}"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        _fail(
            f"{label} must be a JSON object"
        )

    return value


def prepare_recovery_workspace(
    *,
    source_partial_dir: Path,
    recovery_root: Path,
    batch_id: str,
    release_id: str,
    source_production_commit: str,
    recovery_commit: str,
) -> RecoveryWorkspace:
    batch = _batch_id(
        batch_id
    )

    release = _release_id(
        release_id
    )

    source_commit = _commit(
        source_production_commit,
        label="source production commit",
    )

    recover_commit = _commit(
        recovery_commit,
        label="recovery commit",
    )

    source_partial = (
        Path(
            source_partial_dir
        )
    )

    if (
        source_partial.name
        != f"{batch}.partial"
    ):
        _fail(
            "source partial name does not "
            "match recovery batch"
        )

    _require_real_directory(
        source_partial,
        label="source partial",
    )

    source_final = (
        source_partial.parent
        / batch
    )

    if os.path.lexists(
        source_final
    ):
        _fail(
            "ordinary finalized source batch "
            "already exists"
        )

    source_package = (
        source_partial
        / PACKAGE_NAME
    )

    _require_real_directory(
        source_package,
        label="source package",
    )

    source_batch_before = (
        strict_tree_fingerprint(
            source_partial
        )
    )

    source_package_before = (
        strict_tree_fingerprint(
            source_package
        )
    )

    root = Path(
        recovery_root
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    _require_real_directory(
        root,
        label="recovery root",
    )

    partial_dir = (
        root
        / f"{batch}.partial"
    )

    final_dir = (
        root
        / batch
    )

    if (
        os.path.lexists(
            partial_dir
        )
        or os.path.lexists(
            final_dir
        )
    ):
        _fail(
            "recovery output already exists"
        )

    partial_dir.mkdir()

    try:
        _write_new_file(
            partial_dir
            / SOURCE_BATCH_MANIFEST_NAME,
            source_batch_before.payload,
        )

        _write_new_file(
            partial_dir
            / SOURCE_PACKAGE_MANIFEST_NAME,
            source_package_before.payload,
        )

        origin = {
            "batch_id":
                batch,
            "recovery_commit":
                recover_commit,
            "release_id":
                release,
            "schema_version":
                RECOVERY_SCHEMA_VERSION,
            "source_batch_files_sha256":
                source_batch_before.sha256,
            "source_package_files_sha256":
                source_package_before.sha256,
            "source_partial_name":
                source_partial.name,
            "source_production_commit":
                source_commit,
        }

        _write_new_file(
            partial_dir
            / RECOVERY_ORIGIN_NAME,
            _canonical_json_bytes(
                origin
            ),
        )

        recovery_package = (
            partial_dir
            / PACKAGE_NAME
        )

        shutil.copytree(
            source_package,
            recovery_package,
            copy_function=shutil.copy2,
        )

        copied_package = (
            strict_tree_fingerprint(
                recovery_package
            )
        )

        if (
            copied_package.payload
            != source_package_before.payload
        ):
            _fail(
                "recovery package copy differs "
                "from preserved source package"
            )

        source_batch_after = (
            strict_tree_fingerprint(
                source_partial
            )
        )

        if (
            source_batch_after.payload
            != source_batch_before.payload
        ):
            _fail(
                "source partial changed while "
                "creating recovery workspace"
            )

    except Exception:
        # A failed synthetic/workspace preparation is not an accepted
        # recovery. Keep no ambiguous half-created authority directory.
        if partial_dir.exists():
            shutil.rmtree(
                partial_dir
            )
        raise

    return RecoveryWorkspace(
        batch_id=batch,
        partial_dir=partial_dir,
        final_dir=final_dir,
        source_partial_dir=(
            source_partial
        ),
        source_batch_sha256=(
            source_batch_before.sha256
        ),
        source_package_sha256=(
            source_package_before.sha256
        ),
    )


def _audit_recovery_artifacts(
    *,
    batch_dir: Path,
    source_partial_dir: Path,
    expected_release_id: str,
    expected_source_production_commit: str,
    expected_recovery_commit: str | None = None,
) -> AcceptedRecoveryEvidence:
    batch_path = _require_real_directory(
        Path(
            batch_dir
        ),
        label="recovery batch",
    )

    batch = batch_path.name

    if batch.endswith(
        ".partial"
    ):
        batch = batch[
            :-len(
                ".partial"
            )
        ]

    batch = _batch_id(
        batch
    )

    release = _release_id(
        expected_release_id
    )

    source_commit = _commit(
        expected_source_production_commit,
        label="source production commit",
    )

    source_partial = (
        Path(
            source_partial_dir
        )
    )

    if (
        source_partial.name
        != f"{batch}.partial"
    ):
        _fail(
            "recovery source partial does not "
            "match batch"
        )

    _require_real_directory(
        source_partial,
        label="recovery source partial",
    )

    if os.path.lexists(
        source_partial.parent
        / batch
    ):
        _fail(
            "ordinary final exists beside "
            "recovery source partial"
        )

    source_batch_manifest = (
        _require_regular_file(
            batch_path
            / SOURCE_BATCH_MANIFEST_NAME,
            label="source-batch manifest",
        )
    )

    source_package_manifest = (
        _require_regular_file(
            batch_path
            / SOURCE_PACKAGE_MANIFEST_NAME,
            label="source-package manifest",
        )
    )

    recovery_package_manifest = (
        _require_regular_file(
            batch_path
            / RECOVERY_PACKAGE_MANIFEST_NAME,
            label="recovery-package manifest",
        )
    )

    candidate_path = (
        _require_regular_file(
            batch_path
            / CANDIDATE_AUDIT_NAME,
            label="recovery candidate audit",
        )
    )

    component_path = (
        _require_regular_file(
            batch_path
            / COMPONENT_AUDIT_NAME,
            label="recovery component audit",
        )
    )

    recovery_package = (
        _require_real_directory(
            batch_path
            / PACKAGE_NAME,
            label="recovery package",
        )
    )

    origin = _load_json_object(
        batch_path
        / RECOVERY_ORIGIN_NAME,
        label="recovery origin",
    )

    summary = _load_json_object(
        batch_path
        / RECOVERY_SUMMARY_NAME,
        label="recovery summary",
    )

    recovery_commit = _commit(
        str(
            origin.get(
                "recovery_commit"
            )
        ),
        label="recovery commit",
    )

    if (
        expected_recovery_commit
        is not None
        and recovery_commit
        != _commit(
            expected_recovery_commit,
            label="expected recovery commit",
        )
    ):
        _fail(
            "recovery commit changed"
        )

    exact_origin = {
        "batch_id":
            batch,
        "recovery_commit":
            recovery_commit,
        "release_id":
            release,
        "schema_version":
            RECOVERY_SCHEMA_VERSION,
        "source_batch_files_sha256":
            origin.get(
                "source_batch_files_sha256"
            ),
        "source_package_files_sha256":
            origin.get(
                "source_package_files_sha256"
            ),
        "source_partial_name":
            f"{batch}.partial",
        "source_production_commit":
            source_commit,
    }

    if origin != exact_origin:
        _fail(
            "recovery origin binding changed"
        )

    source_batch = (
        strict_tree_fingerprint(
            source_partial
        )
    )

    source_package = (
        strict_tree_fingerprint(
            source_partial
            / PACKAGE_NAME
        )
    )

    if (
        source_batch_manifest.read_bytes()
        != source_batch.payload
    ):
        _fail(
            "preserved source-batch manifest "
            "does not match live source partial"
        )

    if (
        source_package_manifest.read_bytes()
        != source_package.payload
    ):
        _fail(
            "preserved source-package manifest "
            "does not match live source package"
        )

    origin_source_batch_sha = _sha256(
        origin[
            "source_batch_files_sha256"
        ],
        label="origin source-batch-files",
    )

    origin_source_package_sha = _sha256(
        origin[
            "source_package_files_sha256"
        ],
        label="origin source-package-files",
    )

    if (
        origin_source_batch_sha
        != source_batch.sha256
    ):
        _fail(
            "source partial fingerprint changed"
        )

    if (
        origin_source_package_sha
        != source_package.sha256
    ):
        _fail(
            "source package fingerprint changed"
        )

    recovery_package_fingerprint = (
        strict_tree_fingerprint(
            recovery_package
        )
    )

    if (
        recovery_package_manifest.read_bytes()
        != recovery_package_fingerprint.payload
    ):
        _fail(
            "recovery-package manifest does "
            "not match recovery package"
        )

    candidate_sha = sha256_file(
        candidate_path
    )

    component_sha = sha256_file(
        component_path
    )

    recovery_package_manifest_sha = (
        hashlib.sha256(
            recovery_package_manifest.read_bytes()
        ).hexdigest()
    )

    expected_summary = {
        "batch_id":
            batch,
        "candidate_sequence_audit_sha256":
            candidate_sha,
        "component_sequence_audit_sha256":
            component_sha,
        "recovery_commit":
            recovery_commit,
        "recovery_package_file_count":
            recovery_package_fingerprint.file_count,
        "recovery_package_files_sha256":
            recovery_package_manifest_sha,
        "release_id":
            release,
        "schema_version":
            RECOVERY_SCHEMA_VERSION,
        "source_batch_file_count":
            source_batch.file_count,
        "source_batch_files_sha256":
            source_batch.sha256,
        "source_class":
            SOURCE_CLASS_FRESH_RECOVERY,
        "source_package_file_count":
            source_package.file_count,
        "source_package_files_sha256":
            source_package.sha256,
        "source_partial_name":
            f"{batch}.partial",
        "source_production_commit":
            source_commit,
        "status":
            RECOVERY_STATUS,
    }

    if summary != expected_summary:
        _fail(
            "recovery summary derived identity changed"
        )

    return AcceptedRecoveryEvidence(
        batch_id=batch,
        batch_dir=batch_path,
        source_partial_dir=(
            source_partial
        ),
        source_production_commit=(
            source_commit
        ),
        recovery_commit=(
            recovery_commit
        ),
        source_batch_sha256=(
            source_batch.sha256
        ),
        source_package_sha256=(
            source_package.sha256
        ),
        recovery_package_sha256=(
            recovery_package_fingerprint.sha256
        ),
        candidate_audit_sha256=(
            candidate_sha
        ),
        component_audit_sha256=(
            component_sha
        ),
        summary_sha256=sha256_file(
            batch_path
            / RECOVERY_SUMMARY_NAME
        ),
    )


def seal_recovery_workspace(
    workspace: RecoveryWorkspace,
    *,
    release_id: str,
    source_production_commit: str,
    recovery_commit: str,
) -> AcceptedRecoveryEvidence:
    if not isinstance(
        workspace,
        RecoveryWorkspace,
    ):
        raise TypeError(
            "workspace has wrong type"
        )

    partial_dir = (
        workspace.partial_dir
    )

    final_dir = (
        workspace.final_dir
    )

    _require_real_directory(
        partial_dir,
        label="recovery partial",
    )

    if os.path.lexists(
        final_dir
    ):
        _fail(
            "recovery final already exists"
        )

    candidate_path = (
        _require_regular_file(
            partial_dir
            / CANDIDATE_AUDIT_NAME,
            label="candidate audit before seal",
        )
    )

    component_path = (
        _require_regular_file(
            partial_dir
            / COMPONENT_AUDIT_NAME,
            label="component audit before seal",
        )
    )

    source_batch = (
        strict_tree_fingerprint(
            workspace.source_partial_dir
        )
    )

    if (
        source_batch.sha256
        != workspace.source_batch_sha256
    ):
        _fail(
            "source partial changed before "
            "recovery finalization"
        )

    source_package = (
        strict_tree_fingerprint(
            workspace.source_partial_dir
            / PACKAGE_NAME
        )
    )

    if (
        source_package.sha256
        != workspace.source_package_sha256
    ):
        _fail(
            "source package changed before "
            "recovery finalization"
        )

    recovery_package = (
        strict_tree_fingerprint(
            partial_dir
            / PACKAGE_NAME
        )
    )

    _write_new_file(
        partial_dir
        / RECOVERY_PACKAGE_MANIFEST_NAME,
        recovery_package.payload,
    )

    summary = {
        "batch_id":
            workspace.batch_id,
        "candidate_sequence_audit_sha256":
            sha256_file(
                candidate_path
            ),
        "component_sequence_audit_sha256":
            sha256_file(
                component_path
            ),
        "recovery_commit":
            _commit(
                recovery_commit,
                label="recovery commit",
            ),
        "recovery_package_file_count":
            recovery_package.file_count,
        "recovery_package_files_sha256":
            hashlib.sha256(
                recovery_package.payload
            ).hexdigest(),
        "release_id":
            _release_id(
                release_id
            ),
        "schema_version":
            RECOVERY_SCHEMA_VERSION,
        "source_batch_file_count":
            source_batch.file_count,
        "source_batch_files_sha256":
            source_batch.sha256,
        "source_class":
            SOURCE_CLASS_FRESH_RECOVERY,
        "source_package_file_count":
            source_package.file_count,
        "source_package_files_sha256":
            source_package.sha256,
        "source_partial_name":
            workspace.source_partial_dir.name,
        "source_production_commit":
            _commit(
                source_production_commit,
                label="source production commit",
            ),
        "status":
            RECOVERY_STATUS,
    }

    _write_new_file(
        partial_dir
        / RECOVERY_SUMMARY_NAME,
        _canonical_json_bytes(
            summary
        ),
    )

    # Pre-final content audit.
    _audit_recovery_artifacts(
        batch_dir=partial_dir,
        source_partial_dir=(
            workspace.source_partial_dir
        ),
        expected_release_id=(
            release_id
        ),
        expected_source_production_commit=(
            source_production_commit
        ),
        expected_recovery_commit=(
            recovery_commit
        ),
    )

    # Atomic authority transition.
    partial_dir.replace(
        final_dir
    )

    # Post-final audit uses the identical implementation.
    return _audit_recovery_artifacts(
        batch_dir=final_dir,
        source_partial_dir=(
            workspace.source_partial_dir
        ),
        expected_release_id=(
            release_id
        ),
        expected_source_production_commit=(
            source_production_commit
        ),
        expected_recovery_commit=(
            recovery_commit
        ),
    )


def audit_final_recovery(
    *,
    batch_dir: Path,
    source_partial_dir: Path,
    expected_release_id: str,
    expected_source_production_commit: str,
) -> AcceptedRecoveryEvidence:
    batch = _require_real_directory(
        Path(
            batch_dir
        ),
        label="final recovery batch",
    )

    if batch.name.endswith(
        ".partial"
    ):
        _fail(
            "final recovery path is partial"
        )

    if os.path.lexists(
        batch.parent
        / f"{batch.name}.partial"
    ):
        _fail(
            "recovery final and partial both exist"
        )

    return _audit_recovery_artifacts(
        batch_dir=batch,
        source_partial_dir=(
            source_partial_dir
        ),
        expected_release_id=(
            expected_release_id
        ),
        expected_source_production_commit=(
            expected_source_production_commit
        ),
    )


def _discover_batch_like_entries(
    root: Path,
) -> tuple[
    set[str],
    set[str],
]:
    directory = _require_real_directory(
        Path(
            root
        ),
        label="batch authority root",
    )

    finals: set[str] = set()
    partials: set[str] = set()

    for entry in directory.iterdir():
        name = entry.name

        if BATCH_RE.fullmatch(
            name
        ):
            if (
                entry.is_symlink()
                or not entry.is_dir()
            ):
                _fail(
                    "batch-like final is not a "
                    f"real directory: {name}"
                )

            finals.add(
                name
            )
            continue

        if (
            name.endswith(
                ".partial"
            )
            and BATCH_RE.fullmatch(
                name[
                    :-len(
                        ".partial"
                    )
                ]
            )
        ):
            if (
                entry.is_symlink()
                or not entry.is_dir()
            ):
                _fail(
                    "batch-like partial is not a "
                    f"real directory: {name}"
                )

            partials.add(
                name[
                    :-len(
                        ".partial"
                    )
                ]
            )

    return (
        finals,
        partials,
    )


def resolve_authoritative_sequence_batches(
    *,
    sequence_root: Path,
    recovery_roots: Sequence[
        Path
    ],
    expected_batch_ids: Sequence[
        str
    ],
    expected_release_id: str,
    expected_source_production_commit: str,
) -> tuple[
    AuthoritativeSequenceBatch,
    ...,
]:
    expected = tuple(
        _batch_id(
            value
        )
        for value
        in expected_batch_ids
    )

    if len(
        expected
    ) != len(
        set(
            expected
        )
    ):
        _fail(
            "duplicate expected batch ID"
        )

    if tuple(
        sorted(
            expected
        )
    ) != expected:
        _fail(
            "expected batch IDs must be sorted"
        )

    release = _release_id(
        expected_release_id
    )

    source_commit = _commit(
        expected_source_production_commit,
        label="source production commit",
    )

    seq_root = _require_real_directory(
        Path(
            sequence_root
        ),
        label="sequence-acquisition root",
    )

    ordinary_finals, source_partials = (
        _discover_batch_like_entries(
            seq_root
        )
    )

    expected_set = set(
        expected
    )

    extra_finals = (
        ordinary_finals
        - expected_set
    )

    extra_partials = (
        source_partials
        - expected_set
    )

    if (
        extra_finals
        or extra_partials
    ):
        _fail(
            "unexpected source batch-like "
            "entry exists"
        )

    roots = tuple(
        Path(
            value
        )
        for value
        in recovery_roots
    )

    recovery_finals_by_batch: dict[
        str,
        list[
            Path
        ],
    ] = {
        batch:
            []
        for batch
        in expected
    }

    for root in roots:
        finals, partials = (
            _discover_batch_like_entries(
                root
            )
        )

        if partials:
            _fail(
                "unfinished recovery partial exists"
            )

        unexpected = (
            finals
            - expected_set
        )

        if unexpected:
            _fail(
                "unexpected recovered batch exists"
            )

        for batch in finals:
            recovery_finals_by_batch[
                batch
            ].append(
                root
                / batch
            )

    resolved = []

    for batch in expected:
        ordinary_final = (
            batch
            in ordinary_finals
        )

        source_partial = (
            batch
            in source_partials
        )

        recovery_candidates = (
            recovery_finals_by_batch[
                batch
            ]
        )

        if (
            ordinary_final
            and source_partial
        ):
            _fail(
                f"{batch}: ordinary final and "
                "source partial both exist"
            )

        if (
            ordinary_final
            and recovery_candidates
        ):
            _fail(
                f"{batch}: ordinary final and "
                "recovery both claim authority"
            )

        if len(
            recovery_candidates
        ) > 1:
            _fail(
                f"{batch}: multiple recoveries "
                "claim authority"
            )

        if ordinary_final:
            resolved.append(
                AuthoritativeSequenceBatch(
                    batch_id=batch,
                    source_class=(
                        SOURCE_CLASS_FRESH
                    ),
                    batch_dir=(
                        seq_root
                        / batch
                    ),
                    source_partial_dir=None,
                    recovery_commit=None,
                    recovery_summary_sha256=None,
                )
            )
            continue

        if recovery_candidates:
            if not source_partial:
                _fail(
                    f"{batch}: recovery exists "
                    "without preserved source partial"
                )

            recovery = (
                audit_final_recovery(
                    batch_dir=(
                        recovery_candidates[
                            0
                        ]
                    ),
                    source_partial_dir=(
                        seq_root
                        / f"{batch}.partial"
                    ),
                    expected_release_id=(
                        release
                    ),
                    expected_source_production_commit=(
                        source_commit
                    ),
                )
            )

            resolved.append(
                AuthoritativeSequenceBatch(
                    batch_id=batch,
                    source_class=(
                        SOURCE_CLASS_FRESH_RECOVERY
                    ),
                    batch_dir=(
                        recovery.batch_dir
                    ),
                    source_partial_dir=(
                        recovery.source_partial_dir
                    ),
                    recovery_commit=(
                        recovery.recovery_commit
                    ),
                    recovery_summary_sha256=(
                        recovery.summary_sha256
                    ),
                )
            )
            continue

        if source_partial:
            _fail(
                f"{batch}: source partial exists "
                "without accepted recovery"
            )

        _fail(
            f"{batch}: no authoritative batch "
            "provider exists"
        )

    if tuple(
        value.batch_id
        for value
        in resolved
    ) != expected:
        raise RuntimeError(
            "resolved batch order became inconsistent"
        )

    return tuple(
        resolved
    )
