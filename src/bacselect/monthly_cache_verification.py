"""Pure BacSelect monthly verified-cache evidence contract.

This module defines deterministic per-accession cache verification evidence
for the monthly Stage 2 sequence planner.

It performs no filesystem access, network access, external process execution,
archive retrieval, cache discovery, taxonomy, structural-feature analysis,
or selector analysis.

Filesystem executors are responsible for reconstructing and re-hashing
candidate evidence before constructing the inputs accepted here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Iterable, Mapping, Sequence

from bacselect.monthly_sequence_plan import (
    VerifiedMonthlyCacheEvidence,
)
from bacselect.source_eligibility import (
    BIOSAMPLE_RE,
    CANONICAL_GCA_RE,
)
from bacselect.source_fingerprint import (
    assembly_fingerprint,
    component_sequence_hash,
    normalize_sequence,
)
from bacselect.source_truth_execution import (
    CandidateAudit,
    ComponentAudit,
    PackageFile,
    source_evidence_sha256,
)


MONTHLY_CACHE_RESULT_SCHEMA = (
    "bacselect-monthly-cache-verification-result-v1"
)

MONTHLY_VERIFIED_CACHE_SCHEMA = (
    "bacselect-monthly-verified-cache-evidence-v1"
)

MONTHLY_CACHE_RECORD_SCHEMA = (
    "bacselect-monthly-cache-verification-record-v1"
)

MONTHLY_CACHE_VERIFICATION_RECORD_SCHEMA = (
    "bacselect-monthly-cache-candidate-verification-v1"
)

MONTHLY_CACHE_STATUS = (
    "CACHE_VERIFICATION_COMPLETE"
)

CACHE_VERIFIED = (
    "VERIFIED_CACHE_REUSE"
)

CACHE_FRESH_REQUIRED = (
    "FRESH_ACQUISITION_REQUIRED"
)

REASON_VERIFIED = "verified"

REASON_BATCH_PROVENANCE = (
    "batch_provenance_not_verified"
)

REASON_BIOSAMPLE = (
    "current_biosample_mismatch"
)

REASON_PACKAGE_MISSING = (
    "package_file_missing"
)

REASON_PACKAGE_SIZE = (
    "package_file_size_mismatch"
)

REASON_PACKAGE_SHA256 = (
    "package_file_sha256_mismatch"
)

REASON_COMPONENT_SHA256 = (
    "component_sequence_sha256_mismatch"
)

REASON_COMPONENT_FINGERPRINT = (
    "component_sequence_not_fingerprintable"
)


LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

GIT_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

RELEASE_ID_RE = re.compile(
    r"^[0-9]{4}\.[0-9]{2}$"
)


class MonthlyCacheVerificationError(
    ValueError
):
    """Raised when monthly cache evidence is malformed or inconsistent."""


@dataclass(frozen=True)
class MonthlyCachePackageFileObservation:
    """One persisted package file and its observed read-back identity."""

    path: str
    expected_size_bytes: int
    expected_sha256: str
    observed_size_bytes: int | None
    observed_sha256: str | None


@dataclass(frozen=True)
class MonthlyCacheComponent:
    """One reconstructed Primary Assembly component."""

    component_accession: str
    length: int
    topology: str
    sequence_sha256: str
    sequence: str


@dataclass(frozen=True)
class MonthlyCacheCandidate:
    """One previous sequence-evidence candidate considered for reuse."""

    canonical_genbank_assembly_accession: str
    biosample: str

    cache_origin_release_id: str
    cache_origin_source_snapshot_id: str
    cache_origin_git_commit: str

    origin_batch_summary_sha256: str
    origin_candidate_audit_sha256: str
    origin_component_audit_sha256: str
    origin_package_files_sha256: str

    batch_provenance_verified: bool

    candidate_fasta_file: str
    candidate_fasta_sha256: str
    primary_assembly_records: int

    components: tuple[
        MonthlyCacheComponent,
        ...,
    ]

    package_files: tuple[
        MonthlyCachePackageFileObservation,
        ...,
    ]


@dataclass(frozen=True)
class MonthlyCacheVerificationResult:
    """One candidate-level current-snapshot verification result."""

    canonical_genbank_assembly_accession: str
    biosample: str
    verified_source_snapshot_id: str

    cache_origin_release_id: str
    cache_origin_source_snapshot_id: str
    cache_origin_git_commit: str

    origin_batch_summary_sha256: str
    origin_candidate_audit_sha256: str
    origin_component_audit_sha256: str
    origin_package_files_sha256: str

    status: str
    reason: str

    component_identity_sha256: str | None
    assembly_fingerprint: str | None
    source_evidence_sha256: str | None
    package_manifest_sha256: str | None
    verification_record_sha256: str | None


@dataclass(frozen=True)
class MonthlyCacheVerificationBuild:
    """Deterministic candidate outcomes and Stage 2 verified evidence."""

    results: tuple[
        MonthlyCacheVerificationResult,
        ...,
    ]

    verified_cache: tuple[
        VerifiedMonthlyCacheEvidence,
        ...,
    ]


def _canonical_json_bytes(
    value: object,
) -> bytes:
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlyCacheVerificationError(
            "cache evidence is not JSON serializable"
        ) from exc

    return (
        text
        + "\n"
    ).encode(
        "ascii"
    )


def _normalized_text(
    value: object,
    *,
    label: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise MonthlyCacheVerificationError(
            f"{label} must be text"
        )

    if (
        not value
        or value != value.strip()
        or any(
            character.isspace()
            for character in value
        )
    ):
        raise MonthlyCacheVerificationError(
            f"{label} must be normalized non-empty text"
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
        or LOWER_SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyCacheVerificationError(
            f"{label} must be lowercase SHA256"
        )

    return value


def _git_commit(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or GIT_COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyCacheVerificationError(
            f"{label} must be a lowercase 40-character Git commit"
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
        or RELEASE_ID_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyCacheVerificationError(
            "cache-origin release ID is invalid"
        )

    return value


def _canonical_accession(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or CANONICAL_GCA_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyCacheVerificationError(
            f"{label} is not a canonical GCA accession"
        )

    return value


def _biosample(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or BIOSAMPLE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyCacheVerificationError(
            f"{label} is not a valid BioSample"
        )

    return value


def _positive_int(
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
        or value <= 0
    ):
        raise MonthlyCacheVerificationError(
            f"{label} must be a positive integer"
        )

    return value


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
        raise MonthlyCacheVerificationError(
            f"{label} must be a non-negative integer"
        )

    return value


def _optional_nonnegative_int(
    value: object,
    *,
    label: str,
) -> int | None:
    if value is None:
        return None

    return _nonnegative_int(
        value,
        label=label,
    )


def _optional_sha256(
    value: object,
    *,
    label: str,
) -> str | None:
    if value is None:
        return None

    return _sha256(
        value,
        label=label,
    )


def _safe_package_path(
    value: object,
) -> str:
    text = _normalized_text(
        value,
        label="package path",
    )

    if "\\" in text:
        raise MonthlyCacheVerificationError(
            "package path must use POSIX separators"
        )

    path = PurePosixPath(
        text
    )

    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
    ):
        raise MonthlyCacheVerificationError(
            "package path is unsafe"
        )

    if path.as_posix() != text:
        raise MonthlyCacheVerificationError(
            "package path is not canonical POSIX text"
        )

    return text


def _fasta_filename(
    value: object,
) -> str:
    text = _normalized_text(
        value,
        label="candidate FASTA file",
    )

    if (
        "\\" in text
        or PurePosixPath(
            text
        ).name != text
    ):
        raise MonthlyCacheVerificationError(
            "candidate FASTA file must be a basename"
        )

    return text


def _validate_candidate(
    candidate: MonthlyCacheCandidate,
) -> None:
    if not isinstance(
        candidate,
        MonthlyCacheCandidate,
    ):
        raise MonthlyCacheVerificationError(
            "cache candidate has wrong type"
        )

    accession = _canonical_accession(
        candidate.canonical_genbank_assembly_accession,
        label="cache candidate accession",
    )

    _biosample(
        candidate.biosample,
        label="cache candidate BioSample",
    )

    _release_id(
        candidate.cache_origin_release_id
    )

    _normalized_text(
        candidate.cache_origin_source_snapshot_id,
        label="cache-origin source snapshot ID",
    )

    _git_commit(
        candidate.cache_origin_git_commit,
        label="cache-origin Git commit",
    )

    for label, value in (
        (
            "origin batch-summary SHA256",
            candidate.origin_batch_summary_sha256,
        ),
        (
            "origin candidate-audit SHA256",
            candidate.origin_candidate_audit_sha256,
        ),
        (
            "origin component-audit SHA256",
            candidate.origin_component_audit_sha256,
        ),
        (
            "origin package-files SHA256",
            candidate.origin_package_files_sha256,
        ),
        (
            "candidate FASTA SHA256",
            candidate.candidate_fasta_sha256,
        ),
    ):
        _sha256(
            value,
            label=label,
        )

    if not isinstance(
        candidate.batch_provenance_verified,
        bool,
    ):
        raise MonthlyCacheVerificationError(
            "batch provenance flag must be boolean"
        )

    _fasta_filename(
        candidate.candidate_fasta_file
    )

    primary_count = _positive_int(
        candidate.primary_assembly_records,
        label="Primary Assembly component count",
    )

    if len(
        candidate.components
    ) != primary_count:
        raise MonthlyCacheVerificationError(
            "cache candidate Primary Assembly component count changed"
        )

    if not candidate.components:
        raise MonthlyCacheVerificationError(
            "cache candidate has no Primary Assembly components"
        )

    seen_components: set[str] = set()

    for component in candidate.components:
        if not isinstance(
            component,
            MonthlyCacheComponent,
        ):
            raise MonthlyCacheVerificationError(
                "cache component has wrong type"
            )

        component_accession = _normalized_text(
            component.component_accession,
            label="component accession",
        )

        if component_accession in seen_components:
            raise MonthlyCacheVerificationError(
                "duplicate component accession in cache candidate"
            )

        seen_components.add(
            component_accession
        )

        _positive_int(
            component.length,
            label="component length",
        )

        if component.topology not in {
            "linear",
            "circular",
        }:
            raise MonthlyCacheVerificationError(
                "cache component topology is unsupported"
            )

        _sha256(
            component.sequence_sha256,
            label="component sequence SHA256",
        )

        if not isinstance(
            component.sequence,
            str,
        ):
            raise MonthlyCacheVerificationError(
                "component sequence must be text"
            )

    if not candidate.package_files:
        raise MonthlyCacheVerificationError(
            "cache candidate package evidence is empty"
        )

    seen_paths: set[str] = set()

    for observed in candidate.package_files:
        if not isinstance(
            observed,
            MonthlyCachePackageFileObservation,
        ):
            raise MonthlyCacheVerificationError(
                "package-file observation has wrong type"
            )

        package_path = _safe_package_path(
            observed.path
        )

        if package_path in seen_paths:
            raise MonthlyCacheVerificationError(
                "duplicate package path in cache candidate"
            )

        seen_paths.add(
            package_path
        )

        _nonnegative_int(
            observed.expected_size_bytes,
            label="expected package-file size",
        )

        _sha256(
            observed.expected_sha256,
            label="expected package-file SHA256",
        )

        _optional_nonnegative_int(
            observed.observed_size_bytes,
            label="observed package-file size",
        )

        _optional_sha256(
            observed.observed_sha256,
            label="observed package-file SHA256",
        )

        if (
            observed.observed_size_bytes is None
        ) != (
            observed.observed_sha256 is None
        ):
            raise MonthlyCacheVerificationError(
                "package-file observation is only partially populated"
            )

    prefix = (
        "ncbi_dataset",
        "data",
        accession,
    )

    accession_rows = [
        observed
        for observed in candidate.package_files
        if (
            len(
                PurePosixPath(
                    observed.path
                ).parts
            )
            > 3
            and PurePosixPath(
                observed.path
            ).parts[
                :3
            ]
            == prefix
        )
    ]

    if not accession_rows:
        raise MonthlyCacheVerificationError(
            "cache candidate has no accession-scoped package files"
        )

    fasta_rows = [
        observed
        for observed in accession_rows
        if PurePosixPath(
            observed.path
        ).name
        == candidate.candidate_fasta_file
    ]

    if len(
        fasta_rows
    ) != 1:
        raise MonthlyCacheVerificationError(
            "candidate FASTA must resolve to exactly one "
            "accession-scoped package row"
        )

    if (
        fasta_rows[
            0
        ].expected_sha256
        != candidate.candidate_fasta_sha256
    ):
        raise MonthlyCacheVerificationError(
            "candidate FASTA SHA256 conflicts with package manifest"
        )


def _candidate_scoped_package_rows(
    candidate: MonthlyCacheCandidate,
) -> tuple[
    MonthlyCachePackageFileObservation,
    ...,
]:
    accession = (
        candidate.canonical_genbank_assembly_accession
    )

    prefix = (
        "ncbi_dataset",
        "data",
        accession,
    )

    return tuple(
        sorted(
            (
                observed
                for observed in candidate.package_files
                if (
                    len(
                        PurePosixPath(
                            observed.path
                        ).parts
                    )
                    > 3
                    and PurePosixPath(
                        observed.path
                    ).parts[
                        :3
                    ]
                    == prefix
                )
            ),
            key=lambda item:
                item.path,
        )
    )


def component_identity_payload(
    candidate: MonthlyCacheCandidate,
) -> bytes:
    """Return deterministic per-accession component identity."""

    _validate_candidate(
        candidate
    )

    rows = [
        {
            "component_genbank_accession":
                component.component_accession,
            "length":
                component.length,
            "sequence_sha256":
                component.sequence_sha256,
            "topology":
                component.topology,
        }
        for component in sorted(
            candidate.components,
            key=lambda item:
                item.component_accession,
        )
    ]

    return _canonical_json_bytes(
        {
            "canonical_genbank_assembly_accession":
                candidate.canonical_genbank_assembly_accession,
            "components":
                rows,
            "schema_version":
                "bacselect-monthly-cache-component-identity-v1",
        }
    )


def component_identity_sha256(
    candidate: MonthlyCacheCandidate,
) -> str:
    return hashlib.sha256(
        component_identity_payload(
            candidate
        )
    ).hexdigest()


def package_manifest_payload(
    candidate: MonthlyCacheCandidate,
) -> bytes:
    """Return deterministic accession-scoped package identity."""

    _validate_candidate(
        candidate
    )

    rows = [
        {
            "path":
                observed.path,
            "sha256":
                observed.expected_sha256,
            "size_bytes":
                observed.expected_size_bytes,
        }
        for observed in _candidate_scoped_package_rows(
            candidate
        )
    ]

    return _canonical_json_bytes(
        {
            "canonical_genbank_assembly_accession":
                candidate.canonical_genbank_assembly_accession,
            "files":
                rows,
            "schema_version":
                "bacselect-monthly-cache-package-manifest-v1",
        }
    )


def package_manifest_sha256(
    candidate: MonthlyCacheCandidate,
) -> str:
    return hashlib.sha256(
        package_manifest_payload(
            candidate
        )
    ).hexdigest()


def _package_failure_reason(
    candidate: MonthlyCacheCandidate,
) -> str | None:
    for observed in sorted(
        candidate.package_files,
        key=lambda item:
            item.path,
    ):
        if (
            observed.observed_size_bytes is None
            and observed.observed_sha256 is None
        ):
            return REASON_PACKAGE_MISSING

        if (
            observed.observed_size_bytes
            != observed.expected_size_bytes
        ):
            return REASON_PACKAGE_SIZE

        if (
            observed.observed_sha256
            != observed.expected_sha256
        ):
            return REASON_PACKAGE_SHA256

    return None


def _component_failure_reason(
    candidate: MonthlyCacheCandidate,
) -> str | None:
    for component in candidate.components:
        try:
            normalized = normalize_sequence(
                component.sequence
            )
        except (
            TypeError,
            ValueError,
        ):
            return REASON_COMPONENT_FINGERPRINT

        if len(
            normalized
        ) != component.length:
            return REASON_COMPONENT_SHA256

        raw_sha = hashlib.sha256(
            normalized.encode(
                "utf-8"
            )
        ).hexdigest()

        if raw_sha != component.sequence_sha256:
            return REASON_COMPONENT_SHA256

    return None


def _source_truth_objects(
    candidate: MonthlyCacheCandidate,
) -> tuple[
    CandidateAudit,
    tuple[
        ComponentAudit,
        ...,
    ],
    dict[
        str,
        PackageFile,
    ],
]:
    candidate_audit = CandidateAudit(
        accession=(
            candidate.canonical_genbank_assembly_accession
        ),
        audit_path=Path(
            "candidate-sequence-audit.tsv"
        ),
        fasta_file=(
            candidate.candidate_fasta_file
        ),
        fasta_sha256=(
            candidate.candidate_fasta_sha256
        ),
        primary_assembly_records=(
            candidate.primary_assembly_records
        ),
    )

    components = tuple(
        ComponentAudit(
            accession=(
                candidate.canonical_genbank_assembly_accession
            ),
            component_accession=(
                component.component_accession
            ),
            length=(
                component.length
            ),
            topology=(
                component.topology
            ),
            sequence_sha256=(
                component.sequence_sha256
            ),
        )
        for component in candidate.components
    )

    package = {
        observed.path:
            PackageFile(
                relative_path=(
                    observed.path
                ),
                size_bytes=(
                    observed.expected_size_bytes
                ),
                sha256=(
                    observed.expected_sha256
                ),
            )
        for observed in candidate.package_files
    }

    return (
        candidate_audit,
        components,
        package,
    )


def assembly_fingerprint_for_candidate(
    candidate: MonthlyCacheCandidate,
) -> str:
    """Recompute the frozen topology-aware assembly fingerprint."""

    _validate_candidate(
        candidate
    )

    pairs = [
        (
            component.topology,
            component_sequence_hash(
                component.sequence,
                component.topology,
            ),
        )
        for component in candidate.components
    ]

    return assembly_fingerprint(
        pairs
    )


def source_evidence_sha256_for_candidate(
    candidate: MonthlyCacheCandidate,
) -> str:
    """Recompute the frozen Stage 1 source-evidence identity."""

    _validate_candidate(
        candidate
    )

    (
        candidate_audit,
        components,
        package,
    ) = _source_truth_objects(
        candidate
    )

    return source_evidence_sha256(
        candidate_audit,
        components,
        package,
    )


def candidate_verification_record_bytes(
    *,
    candidate: MonthlyCacheCandidate,
    verified_source_snapshot_id: str,
    component_identity: str,
    assembly_identity: str,
    source_evidence_identity: str,
    package_manifest_identity: str,
) -> bytes:
    """Build the canonical current-snapshot verification record."""

    _validate_candidate(
        candidate
    )

    snapshot = _normalized_text(
        verified_source_snapshot_id,
        label="verified source snapshot ID",
    )

    component_sha = _sha256(
        component_identity,
        label="component identity SHA256",
    )

    assembly_sha = _sha256(
        assembly_identity,
        label="assembly fingerprint",
    )

    source_sha = _sha256(
        source_evidence_identity,
        label="source-evidence SHA256",
    )

    package_sha = _sha256(
        package_manifest_identity,
        label="package-manifest SHA256",
    )

    return _canonical_json_bytes(
        {
            "assembly_fingerprint":
                assembly_sha,
            "biosample":
                candidate.biosample,
            "cache_origin_git_commit":
                candidate.cache_origin_git_commit,
            "cache_origin_release_id":
                candidate.cache_origin_release_id,
            "cache_origin_source_snapshot_id":
                candidate.cache_origin_source_snapshot_id,
            "canonical_genbank_assembly_accession":
                candidate.canonical_genbank_assembly_accession,
            "component_identity_sha256":
                component_sha,
            "origin_batch_summary_sha256":
                candidate.origin_batch_summary_sha256,
            "origin_candidate_audit_sha256":
                candidate.origin_candidate_audit_sha256,
            "origin_component_audit_sha256":
                candidate.origin_component_audit_sha256,
            "origin_package_files_sha256":
                candidate.origin_package_files_sha256,
            "package_manifest_sha256":
                package_sha,
            "schema_version":
                MONTHLY_CACHE_VERIFICATION_RECORD_SCHEMA,
            "source_evidence_sha256":
                source_sha,
            "status":
                CACHE_VERIFIED,
            "verified_source_snapshot_id":
                snapshot,
        }
    )


def _fresh_result(
    candidate: MonthlyCacheCandidate,
    *,
    source_snapshot_id: str,
    reason: str,
) -> MonthlyCacheVerificationResult:
    return MonthlyCacheVerificationResult(
        canonical_genbank_assembly_accession=(
            candidate.canonical_genbank_assembly_accession
        ),
        biosample=(
            candidate.biosample
        ),
        verified_source_snapshot_id=(
            source_snapshot_id
        ),
        cache_origin_release_id=(
            candidate.cache_origin_release_id
        ),
        cache_origin_source_snapshot_id=(
            candidate.cache_origin_source_snapshot_id
        ),
        cache_origin_git_commit=(
            candidate.cache_origin_git_commit
        ),
        origin_batch_summary_sha256=(
            candidate.origin_batch_summary_sha256
        ),
        origin_candidate_audit_sha256=(
            candidate.origin_candidate_audit_sha256
        ),
        origin_component_audit_sha256=(
            candidate.origin_component_audit_sha256
        ),
        origin_package_files_sha256=(
            candidate.origin_package_files_sha256
        ),
        status=(
            CACHE_FRESH_REQUIRED
        ),
        reason=reason,
        component_identity_sha256=None,
        assembly_fingerprint=None,
        source_evidence_sha256=None,
        package_manifest_sha256=None,
        verification_record_sha256=None,
    )


def verify_cache_candidate(
    candidate: MonthlyCacheCandidate,
    *,
    current_source_snapshot_id: str,
    current_biosample: str,
) -> tuple[
    MonthlyCacheVerificationResult,
    VerifiedMonthlyCacheEvidence | None,
]:
    """Verify one previous candidate for current-snapshot Stage 2 reuse."""

    _validate_candidate(
        candidate
    )

    snapshot = _normalized_text(
        current_source_snapshot_id,
        label="current source snapshot ID",
    )

    biosample = _biosample(
        current_biosample,
        label="current BioSample",
    )

    if not candidate.batch_provenance_verified:
        return (
            _fresh_result(
                candidate,
                source_snapshot_id=(
                    snapshot
                ),
                reason=(
                    REASON_BATCH_PROVENANCE
                ),
            ),
            None,
        )

    if candidate.biosample != biosample:
        return (
            _fresh_result(
                candidate,
                source_snapshot_id=(
                    snapshot
                ),
                reason=(
                    REASON_BIOSAMPLE
                ),
            ),
            None,
        )

    package_failure = (
        _package_failure_reason(
            candidate
        )
    )

    if package_failure is not None:
        return (
            _fresh_result(
                candidate,
                source_snapshot_id=(
                    snapshot
                ),
                reason=package_failure,
            ),
            None,
        )

    component_failure = (
        _component_failure_reason(
            candidate
        )
    )

    if component_failure is not None:
        return (
            _fresh_result(
                candidate,
                source_snapshot_id=(
                    snapshot
                ),
                reason=component_failure,
            ),
            None,
        )

    component_identity = (
        component_identity_sha256(
            candidate
        )
    )

    package_identity = (
        package_manifest_sha256(
            candidate
        )
    )

    assembly_identity = (
        assembly_fingerprint_for_candidate(
            candidate
        )
    )

    source_identity = (
        source_evidence_sha256_for_candidate(
            candidate
        )
    )

    verification_record = (
        candidate_verification_record_bytes(
            candidate=candidate,
            verified_source_snapshot_id=(
                snapshot
            ),
            component_identity=(
                component_identity
            ),
            assembly_identity=(
                assembly_identity
            ),
            source_evidence_identity=(
                source_identity
            ),
            package_manifest_identity=(
                package_identity
            ),
        )
    )

    verification_sha = (
        hashlib.sha256(
            verification_record
        ).hexdigest()
    )

    result = MonthlyCacheVerificationResult(
        canonical_genbank_assembly_accession=(
            candidate.canonical_genbank_assembly_accession
        ),
        biosample=(
            candidate.biosample
        ),
        verified_source_snapshot_id=(
            snapshot
        ),
        cache_origin_release_id=(
            candidate.cache_origin_release_id
        ),
        cache_origin_source_snapshot_id=(
            candidate.cache_origin_source_snapshot_id
        ),
        cache_origin_git_commit=(
            candidate.cache_origin_git_commit
        ),
        origin_batch_summary_sha256=(
            candidate.origin_batch_summary_sha256
        ),
        origin_candidate_audit_sha256=(
            candidate.origin_candidate_audit_sha256
        ),
        origin_component_audit_sha256=(
            candidate.origin_component_audit_sha256
        ),
        origin_package_files_sha256=(
            candidate.origin_package_files_sha256
        ),
        status=(
            CACHE_VERIFIED
        ),
        reason=(
            REASON_VERIFIED
        ),
        component_identity_sha256=(
            component_identity
        ),
        assembly_fingerprint=(
            assembly_identity
        ),
        source_evidence_sha256=(
            source_identity
        ),
        package_manifest_sha256=(
            package_identity
        ),
        verification_record_sha256=(
            verification_sha
        ),
    )

    evidence = VerifiedMonthlyCacheEvidence(
        canonical_genbank_assembly_accession=(
            candidate.canonical_genbank_assembly_accession
        ),
        biosample=(
            candidate.biosample
        ),
        verified_source_snapshot_id=(
            snapshot
        ),
        component_identity_sha256=(
            component_identity
        ),
        assembly_fingerprint=(
            assembly_identity
        ),
        source_evidence_sha256=(
            source_identity
        ),
        package_manifest_sha256=(
            package_identity
        ),
        verification_record_sha256=(
            verification_sha
        ),
    )

    return (
        result,
        evidence,
    )


def verify_cache_candidates(
    candidates: Iterable[
        MonthlyCacheCandidate
    ],
    *,
    current_source_snapshot_id: str,
    current_metadata: Mapping[
        str,
        str,
    ],
) -> MonthlyCacheVerificationBuild:
    """Verify a deterministic candidate set against current retained metadata."""

    snapshot = _normalized_text(
        current_source_snapshot_id,
        label="current source snapshot ID",
    )

    retained: dict[
        str,
        str,
    ] = {}

    for accession_value, biosample_value in current_metadata.items():
        accession = _canonical_accession(
            accession_value,
            label="current metadata accession",
        )

        biosample = _biosample(
            biosample_value,
            label="current metadata BioSample",
        )

        if accession in retained:
            raise MonthlyCacheVerificationError(
                "duplicate current metadata accession"
            )

        retained[
            accession
        ] = biosample

    values = tuple(
        candidates
    )

    seen: set[str] = set()

    for candidate in values:
        _validate_candidate(
            candidate
        )

        accession = (
            candidate.canonical_genbank_assembly_accession
        )

        if accession in seen:
            raise MonthlyCacheVerificationError(
                "duplicate monthly cache candidate accession"
            )

        seen.add(
            accession
        )

        if accession not in retained:
            raise MonthlyCacheVerificationError(
                "cache candidate is not in current metadata-retained universe"
            )

    results: list[
        MonthlyCacheVerificationResult
    ] = []

    verified: list[
        VerifiedMonthlyCacheEvidence
    ] = []

    for candidate in sorted(
        values,
        key=lambda item:
            item.canonical_genbank_assembly_accession,
    ):
        result, evidence = (
            verify_cache_candidate(
                candidate,
                current_source_snapshot_id=(
                    snapshot
                ),
                current_biosample=(
                    retained[
                        candidate.canonical_genbank_assembly_accession
                    ]
                ),
            )
        )

        results.append(
            result
        )

        if evidence is not None:
            verified.append(
                evidence
            )

    return MonthlyCacheVerificationBuild(
        results=tuple(
            results
        ),
        verified_cache=tuple(
            verified
        ),
    )


def _result_record(
    result: MonthlyCacheVerificationResult,
) -> dict[str, object]:
    if not isinstance(
        result,
        MonthlyCacheVerificationResult,
    ):
        raise MonthlyCacheVerificationError(
            "cache verification result has wrong type"
        )

    accession = _canonical_accession(
        result.canonical_genbank_assembly_accession,
        label="verification result accession",
    )

    biosample = _biosample(
        result.biosample,
        label="verification result BioSample",
    )

    snapshot = _normalized_text(
        result.verified_source_snapshot_id,
        label="verification result source snapshot ID",
    )

    origin_release = _release_id(
        result.cache_origin_release_id
    )

    origin_snapshot = _normalized_text(
        result.cache_origin_source_snapshot_id,
        label="cache-origin source snapshot ID",
    )

    origin_commit = _git_commit(
        result.cache_origin_git_commit,
        label="cache-origin Git commit",
    )

    batch_sha = _sha256(
        result.origin_batch_summary_sha256,
        label="origin batch-summary SHA256",
    )

    candidate_sha = _sha256(
        result.origin_candidate_audit_sha256,
        label="origin candidate-audit SHA256",
    )

    component_audit_sha = _sha256(
        result.origin_component_audit_sha256,
        label="origin component-audit SHA256",
    )

    package_files_sha = _sha256(
        result.origin_package_files_sha256,
        label="origin package-files SHA256",
    )

    allowed_reasons = {
        REASON_VERIFIED,
        REASON_BATCH_PROVENANCE,
        REASON_BIOSAMPLE,
        REASON_PACKAGE_MISSING,
        REASON_PACKAGE_SIZE,
        REASON_PACKAGE_SHA256,
        REASON_COMPONENT_SHA256,
        REASON_COMPONENT_FINGERPRINT,
    }

    if result.reason not in allowed_reasons:
        raise MonthlyCacheVerificationError(
            "cache verification result has unsupported reason"
        )

    if result.status == CACHE_VERIFIED:
        if result.reason != REASON_VERIFIED:
            raise MonthlyCacheVerificationError(
                "verified cache result has non-verified reason"
            )

        identities = (
            _sha256(
                result.component_identity_sha256,
                label="component identity SHA256",
            ),
            _sha256(
                result.assembly_fingerprint,
                label="assembly fingerprint",
            ),
            _sha256(
                result.source_evidence_sha256,
                label="source-evidence SHA256",
            ),
            _sha256(
                result.package_manifest_sha256,
                label="package-manifest SHA256",
            ),
            _sha256(
                result.verification_record_sha256,
                label="verification-record SHA256",
            ),
        )

        (
            component_identity,
            assembly_identity,
            source_identity,
            package_identity,
            verification_identity,
        ) = identities

        reconstructed = _canonical_json_bytes(
            {
                "assembly_fingerprint":
                    assembly_identity,
                "biosample":
                    biosample,
                "cache_origin_git_commit":
                    origin_commit,
                "cache_origin_release_id":
                    origin_release,
                "cache_origin_source_snapshot_id":
                    origin_snapshot,
                "canonical_genbank_assembly_accession":
                    accession,
                "component_identity_sha256":
                    component_identity,
                "origin_batch_summary_sha256":
                    batch_sha,
                "origin_candidate_audit_sha256":
                    candidate_sha,
                "origin_component_audit_sha256":
                    component_audit_sha,
                "origin_package_files_sha256":
                    package_files_sha,
                "package_manifest_sha256":
                    package_identity,
                "schema_version":
                    MONTHLY_CACHE_VERIFICATION_RECORD_SCHEMA,
                "source_evidence_sha256":
                    source_identity,
                "status":
                    CACHE_VERIFIED,
                "verified_source_snapshot_id":
                    snapshot,
            }
        )

        if (
            hashlib.sha256(
                reconstructed
            ).hexdigest()
            != verification_identity
        ):
            raise MonthlyCacheVerificationError(
                "verification-record SHA256 does not match derived record"
            )

    elif result.status == CACHE_FRESH_REQUIRED:
        if result.reason == REASON_VERIFIED:
            raise MonthlyCacheVerificationError(
                "fresh-required result has verified reason"
            )

        if any(
            value is not None
            for value in (
                result.component_identity_sha256,
                result.assembly_fingerprint,
                result.source_evidence_sha256,
                result.package_manifest_sha256,
                result.verification_record_sha256,
            )
        ):
            raise MonthlyCacheVerificationError(
                "fresh-required result contains verified identities"
            )

        component_identity = None
        assembly_identity = None
        source_identity = None
        package_identity = None
        verification_identity = None

    else:
        raise MonthlyCacheVerificationError(
            "cache verification result has unsupported status"
        )

    return {
        "assembly_fingerprint":
            assembly_identity,
        "biosample":
            biosample,
        "cache_origin_git_commit":
            origin_commit,
        "cache_origin_release_id":
            origin_release,
        "cache_origin_source_snapshot_id":
            origin_snapshot,
        "canonical_genbank_assembly_accession":
            accession,
        "component_identity_sha256":
            component_identity,
        "origin_batch_summary_sha256":
            batch_sha,
        "origin_candidate_audit_sha256":
            candidate_sha,
        "origin_component_audit_sha256":
            component_audit_sha,
        "origin_package_files_sha256":
            package_files_sha,
        "package_manifest_sha256":
            package_identity,
        "reason":
            result.reason,
        "schema_version":
            MONTHLY_CACHE_RESULT_SCHEMA,
        "source_evidence_sha256":
            source_identity,
        "status":
            result.status,
        "verification_record_sha256":
            verification_identity,
        "verified_source_snapshot_id":
            snapshot,
    }


def serialize_cache_verification_results(
    results: Iterable[
        MonthlyCacheVerificationResult
    ],
) -> bytes:
    values = tuple(
        results
    )

    ordered = tuple(
        sorted(
            values,
            key=lambda item:
                item.canonical_genbank_assembly_accession,
        )
    )

    accessions = [
        item.canonical_genbank_assembly_accession
        for item in ordered
    ]

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlyCacheVerificationError(
            "duplicate accession in cache verification results"
        )

    return b"".join(
        _canonical_json_bytes(
            _result_record(
                result
            )
        )
        for result in ordered
    )


def _verified_evidence_record(
    evidence: VerifiedMonthlyCacheEvidence,
) -> dict[str, object]:
    if not isinstance(
        evidence,
        VerifiedMonthlyCacheEvidence,
    ):
        raise MonthlyCacheVerificationError(
            "verified cache evidence has wrong type"
        )

    return {
        "assembly_fingerprint":
            _sha256(
                evidence.assembly_fingerprint,
                label="assembly fingerprint",
            ),
        "biosample":
            _biosample(
                evidence.biosample,
                label="verified cache BioSample",
            ),
        "canonical_genbank_assembly_accession":
            _canonical_accession(
                evidence.canonical_genbank_assembly_accession,
                label="verified cache accession",
            ),
        "component_identity_sha256":
            _sha256(
                evidence.component_identity_sha256,
                label="component identity SHA256",
            ),
        "package_manifest_sha256":
            _sha256(
                evidence.package_manifest_sha256,
                label="package-manifest SHA256",
            ),
        "schema_version":
            MONTHLY_VERIFIED_CACHE_SCHEMA,
        "source_evidence_sha256":
            _sha256(
                evidence.source_evidence_sha256,
                label="source-evidence SHA256",
            ),
        "verification_record_sha256":
            _sha256(
                evidence.verification_record_sha256,
                label="verification-record SHA256",
            ),
        "verified_source_snapshot_id":
            _normalized_text(
                evidence.verified_source_snapshot_id,
                label="verified source snapshot ID",
            ),
    }


def serialize_verified_cache_evidence(
    evidence: Iterable[
        VerifiedMonthlyCacheEvidence
    ],
) -> bytes:
    values = tuple(
        evidence
    )

    ordered = tuple(
        sorted(
            values,
            key=lambda item:
                item.canonical_genbank_assembly_accession,
        )
    )

    accessions = [
        item.canonical_genbank_assembly_accession
        for item in ordered
    ]

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlyCacheVerificationError(
            "duplicate accession in verified cache evidence"
        )

    return b"".join(
        _canonical_json_bytes(
            _verified_evidence_record(
                item
            )
        )
        for item in ordered
    )


def _audit_jsonl(
    payload: bytes,
    *,
    label: str,
) -> tuple[
    Mapping[
        str,
        object,
    ],
    ...,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            f"{label} must be bytes"
        )

    if not payload:
        return ()

    if not payload.endswith(
        b"\n"
    ):
        raise MonthlyCacheVerificationError(
            f"{label} must be newline terminated"
        )

    try:
        text = payload.decode(
            "ascii"
        )
    except UnicodeDecodeError as exc:
        raise MonthlyCacheVerificationError(
            f"{label} must be ASCII"
        ) from exc

    records: list[
        Mapping[
            str,
            object,
        ]
    ] = []

    for line_number, line in enumerate(
        text.splitlines(),
        1,
    ):
        if not line:
            raise MonthlyCacheVerificationError(
                f"{label} contains blank line {line_number}"
            )

        try:
            value = json.loads(
                line
            )
        except json.JSONDecodeError as exc:
            raise MonthlyCacheVerificationError(
                f"{label} contains invalid JSON"
            ) from exc

        if not isinstance(
            value,
            dict,
        ):
            raise MonthlyCacheVerificationError(
                f"{label} row must be a JSON object"
            )

        canonical = (
            _canonical_json_bytes(
                value
            ).decode(
                "ascii"
            ).rstrip(
                "\n"
            )
        )

        if line != canonical:
            raise MonthlyCacheVerificationError(
                f"{label} row is not canonical JSON"
            )

        records.append(
            value
        )

    return tuple(
        records
    )


def audit_verified_cache_evidence(
    payload: bytes,
) -> tuple[
    VerifiedMonthlyCacheEvidence,
    ...,
]:
    records = _audit_jsonl(
        payload,
        label="verified cache evidence",
    )

    values: list[
        VerifiedMonthlyCacheEvidence
    ] = []

    expected_keys = {
        "assembly_fingerprint",
        "biosample",
        "canonical_genbank_assembly_accession",
        "component_identity_sha256",
        "package_manifest_sha256",
        "schema_version",
        "source_evidence_sha256",
        "verification_record_sha256",
        "verified_source_snapshot_id",
    }

    for record in records:
        if set(
            record
        ) != expected_keys:
            raise MonthlyCacheVerificationError(
                "verified cache evidence schema changed"
            )

        if (
            record[
                "schema_version"
            ]
            != MONTHLY_VERIFIED_CACHE_SCHEMA
        ):
            raise MonthlyCacheVerificationError(
                "verified cache evidence schema version changed"
            )

        values.append(
            VerifiedMonthlyCacheEvidence(
                canonical_genbank_assembly_accession=(
                    _canonical_accession(
                        record[
                            "canonical_genbank_assembly_accession"
                        ],
                        label="verified cache accession",
                    )
                ),
                biosample=(
                    _biosample(
                        record[
                            "biosample"
                        ],
                        label="verified cache BioSample",
                    )
                ),
                verified_source_snapshot_id=(
                    _normalized_text(
                        record[
                            "verified_source_snapshot_id"
                        ],
                        label="verified source snapshot ID",
                    )
                ),
                component_identity_sha256=(
                    _sha256(
                        record[
                            "component_identity_sha256"
                        ],
                        label="component identity SHA256",
                    )
                ),
                assembly_fingerprint=(
                    _sha256(
                        record[
                            "assembly_fingerprint"
                        ],
                        label="assembly fingerprint",
                    )
                ),
                source_evidence_sha256=(
                    _sha256(
                        record[
                            "source_evidence_sha256"
                        ],
                        label="source-evidence SHA256",
                    )
                ),
                package_manifest_sha256=(
                    _sha256(
                        record[
                            "package_manifest_sha256"
                        ],
                        label="package-manifest SHA256",
                    )
                ),
                verification_record_sha256=(
                    _sha256(
                        record[
                            "verification_record_sha256"
                        ],
                        label="verification-record SHA256",
                    )
                ),
            )
        )

    accessions = tuple(
        value.canonical_genbank_assembly_accession
        for value in values
    )

    if accessions != tuple(
        sorted(
            accessions
        )
    ):
        raise MonthlyCacheVerificationError(
            "verified cache evidence is not accession sorted"
        )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlyCacheVerificationError(
            "verified cache evidence contains duplicate accession"
        )

    if (
        serialize_verified_cache_evidence(
            values
        )
        != payload
    ):
        raise MonthlyCacheVerificationError(
            "verified cache evidence derived identity changed"
        )

    return tuple(
        values
    )


def audit_cache_verification_results(
    payload: bytes,
) -> tuple[
    Mapping[
        str,
        object,
    ],
    ...,
]:
    records = _audit_jsonl(
        payload,
        label="cache verification results",
    )

    expected_keys = {
        "assembly_fingerprint",
        "biosample",
        "cache_origin_git_commit",
        "cache_origin_release_id",
        "cache_origin_source_snapshot_id",
        "canonical_genbank_assembly_accession",
        "component_identity_sha256",
        "origin_batch_summary_sha256",
        "origin_candidate_audit_sha256",
        "origin_component_audit_sha256",
        "origin_package_files_sha256",
        "package_manifest_sha256",
        "reason",
        "schema_version",
        "source_evidence_sha256",
        "status",
        "verification_record_sha256",
        "verified_source_snapshot_id",
    }

    accessions: list[str] = []

    for record in records:
        if set(
            record
        ) != expected_keys:
            raise MonthlyCacheVerificationError(
                "cache verification result schema changed"
            )

        if (
            record[
                "schema_version"
            ]
            != MONTHLY_CACHE_RESULT_SCHEMA
        ):
            raise MonthlyCacheVerificationError(
                "cache verification result schema version changed"
            )

        accession = _canonical_accession(
            record[
                "canonical_genbank_assembly_accession"
            ],
            label="cache verification accession",
        )

        accessions.append(
            accession
        )

        _biosample(
            record[
                "biosample"
            ],
            label="cache verification BioSample",
        )

        _release_id(
            record[
                "cache_origin_release_id"
            ]
        )

        _normalized_text(
            record[
                "cache_origin_source_snapshot_id"
            ],
            label="cache-origin source snapshot ID",
        )

        _git_commit(
            record[
                "cache_origin_git_commit"
            ],
            label="cache-origin Git commit",
        )

        _normalized_text(
            record[
                "verified_source_snapshot_id"
            ],
            label="verified source snapshot ID",
        )

        for field in (
            "origin_batch_summary_sha256",
            "origin_candidate_audit_sha256",
            "origin_component_audit_sha256",
            "origin_package_files_sha256",
        ):
            _sha256(
                record[
                    field
                ],
                label=field,
            )

        status = record[
            "status"
        ]

        reason = record[
            "reason"
        ]

        if status == CACHE_VERIFIED:
            if reason != REASON_VERIFIED:
                raise MonthlyCacheVerificationError(
                    "verified result has wrong reason"
                )

            for field in (
                "component_identity_sha256",
                "assembly_fingerprint",
                "source_evidence_sha256",
                "package_manifest_sha256",
                "verification_record_sha256",
            ):
                _sha256(
                    record[
                        field
                    ],
                    label=field,
                )

            verification_record = (
                _canonical_json_bytes(
                    {
                        "assembly_fingerprint":
                            record[
                                "assembly_fingerprint"
                            ],
                        "biosample":
                            record[
                                "biosample"
                            ],
                        "cache_origin_git_commit":
                            record[
                                "cache_origin_git_commit"
                            ],
                        "cache_origin_release_id":
                            record[
                                "cache_origin_release_id"
                            ],
                        "cache_origin_source_snapshot_id":
                            record[
                                "cache_origin_source_snapshot_id"
                            ],
                        "canonical_genbank_assembly_accession":
                            accession,
                        "component_identity_sha256":
                            record[
                                "component_identity_sha256"
                            ],
                        "origin_batch_summary_sha256":
                            record[
                                "origin_batch_summary_sha256"
                            ],
                        "origin_candidate_audit_sha256":
                            record[
                                "origin_candidate_audit_sha256"
                            ],
                        "origin_component_audit_sha256":
                            record[
                                "origin_component_audit_sha256"
                            ],
                        "origin_package_files_sha256":
                            record[
                                "origin_package_files_sha256"
                            ],
                        "package_manifest_sha256":
                            record[
                                "package_manifest_sha256"
                            ],
                        "schema_version":
                            MONTHLY_CACHE_VERIFICATION_RECORD_SCHEMA,
                        "source_evidence_sha256":
                            record[
                                "source_evidence_sha256"
                            ],
                        "status":
                            CACHE_VERIFIED,
                        "verified_source_snapshot_id":
                            record[
                                "verified_source_snapshot_id"
                            ],
                    }
                )
            )

            if (
                hashlib.sha256(
                    verification_record
                ).hexdigest()
                != record[
                    "verification_record_sha256"
                ]
            ):
                raise MonthlyCacheVerificationError(
                    "cache result verification-record SHA256 changed"
                )

        elif status == CACHE_FRESH_REQUIRED:
            if reason not in {
                REASON_BATCH_PROVENANCE,
                REASON_BIOSAMPLE,
                REASON_PACKAGE_MISSING,
                REASON_PACKAGE_SIZE,
                REASON_PACKAGE_SHA256,
                REASON_COMPONENT_SHA256,
                REASON_COMPONENT_FINGERPRINT,
            }:
                raise MonthlyCacheVerificationError(
                    "fresh-required result has unsupported reason"
                )

            for field in (
                "component_identity_sha256",
                "assembly_fingerprint",
                "source_evidence_sha256",
                "package_manifest_sha256",
                "verification_record_sha256",
            ):
                if record[
                    field
                ] is not None:
                    raise MonthlyCacheVerificationError(
                        "fresh-required result contains verified identity"
                    )

        else:
            raise MonthlyCacheVerificationError(
                "cache verification result has unsupported status"
            )

    if tuple(
        accessions
    ) != tuple(
        sorted(
            accessions
        )
    ):
        raise MonthlyCacheVerificationError(
            "cache verification results are not accession sorted"
        )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlyCacheVerificationError(
            "cache verification results contain duplicate accession"
        )

    return records


def build_cache_verification_record(
    *,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
    retained_count: int,
    results_payload: bytes,
    verified_cache_payload: bytes,
) -> dict[str, object]:
    """Bind explicit zero or non-zero cache verification to current metadata."""

    snapshot = _normalized_text(
        source_snapshot_id,
        label="source snapshot ID",
    )

    snapshot_record_sha = _sha256(
        source_snapshot_record_sha256,
        label="source-snapshot-record SHA256",
    )

    metadata_record_sha = _sha256(
        metadata_record_sha256,
        label="metadata record SHA256",
    )

    metadata_completion_sha = _sha256(
        metadata_completion_sha256,
        label="metadata completion SHA256",
    )

    retained = _nonnegative_int(
        retained_count,
        label="retained metadata count",
    )

    results = (
        audit_cache_verification_results(
            results_payload
        )
    )

    verified = (
        audit_verified_cache_evidence(
            verified_cache_payload
        )
    )

    if len(
        results
    ) > retained:
        raise MonthlyCacheVerificationError(
            "cache candidate count exceeds metadata-retained count"
        )

    result_verified = {
        str(
            record[
                "canonical_genbank_assembly_accession"
            ]
        ):
            record
        for record in results
        if record[
            "status"
        ]
        == CACHE_VERIFIED
    }

    evidence_by_accession = {
        item.canonical_genbank_assembly_accession:
            item
        for item in verified
    }

    if set(
        result_verified
    ) != set(
        evidence_by_accession
    ):
        raise MonthlyCacheVerificationError(
            "verified result and Stage 2 evidence accession sets differ"
        )

    for accession, evidence in evidence_by_accession.items():
        record = result_verified[
            accession
        ]

        comparisons = (
            (
                evidence.biosample,
                record[
                    "biosample"
                ],
            ),
            (
                evidence.verified_source_snapshot_id,
                record[
                    "verified_source_snapshot_id"
                ],
            ),
            (
                evidence.component_identity_sha256,
                record[
                    "component_identity_sha256"
                ],
            ),
            (
                evidence.assembly_fingerprint,
                record[
                    "assembly_fingerprint"
                ],
            ),
            (
                evidence.source_evidence_sha256,
                record[
                    "source_evidence_sha256"
                ],
            ),
            (
                evidence.package_manifest_sha256,
                record[
                    "package_manifest_sha256"
                ],
            ),
            (
                evidence.verification_record_sha256,
                record[
                    "verification_record_sha256"
                ],
            ),
        )

        if any(
            left != right
            for left, right
            in comparisons
        ):
            raise MonthlyCacheVerificationError(
                "verified cache evidence differs from verification result"
            )

        if (
            evidence.verified_source_snapshot_id
            != snapshot
        ):
            raise MonthlyCacheVerificationError(
                "verified cache evidence belongs to another source snapshot"
            )

    fallback_count = sum(
        record[
            "status"
        ]
        == CACHE_FRESH_REQUIRED
        for record in results
    )

    return {
        "candidate_input_count":
            len(
                results
            ),
        "fallback_to_fresh_count":
            fallback_count,
        "metadata_completion_sha256":
            metadata_completion_sha,
        "metadata_record_sha256":
            metadata_record_sha,
        "results_sha256":
            hashlib.sha256(
                results_payload
            ).hexdigest(),
        "retained_count":
            retained,
        "schema_version":
            MONTHLY_CACHE_RECORD_SCHEMA,
        "source_snapshot_id":
            snapshot,
        "source_snapshot_record_sha256":
            snapshot_record_sha,
        "status":
            MONTHLY_CACHE_STATUS,
        "verified_cache_count":
            len(
                verified
            ),
        "verified_cache_evidence_sha256":
            hashlib.sha256(
                verified_cache_payload
            ).hexdigest(),
    }


def serialize_cache_verification_record(
    **kwargs,
) -> bytes:
    return _canonical_json_bytes(
        build_cache_verification_record(
            **kwargs
        )
    )


def audit_cache_verification_record(
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
            "cache verification record must be bytes"
        )

    expected = (
        serialize_cache_verification_record(
            **kwargs
        )
    )

    if payload != expected:
        raise MonthlyCacheVerificationError(
            "cache verification record derived identity changed"
        )

    try:
        record = json.loads(
            payload.decode(
                "ascii"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlyCacheVerificationError(
            "cache verification record is invalid"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise MonthlyCacheVerificationError(
            "cache verification record must be an object"
        )

    return record
