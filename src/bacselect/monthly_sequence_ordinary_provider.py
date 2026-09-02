"""Audited ordinary Stage 3B provider surface for recovery-aware completion."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from bacselect import monthly_sequence_recovery_authority as authority
from bacselect.monthly_sequence_acquisition_completion import (
    CompletedTransportBatchEvidence,
    MonthlySequenceAcquisitionCompletionError,
    _audit_package_files_manifest,
    _audit_package_readback,
    _audit_transport_summary,
    _batch_id,
    _git_commit,
    _nonnegative_int,
    _normalized_text,
    _positive_int,
    _sha256,
    _summary_sha256,
)
from bacselect.monthly_sequence_plan import (
    FRESH_BATCH_SIZE,
)
from bacselect.monthly_sequence_transport import (
    TARGETED_RETRY_ROUNDS,
    MonthlySequenceTransportError,
    batch_accession_bytes,
    batch_target_manifest_sha256,
)
from bacselect.source_eligibility import (
    DATASETS_VERSION,
)


SOURCE_CLASS_FRESH = (
    authority.SOURCE_CLASS_FRESH
)


class MonthlySequenceOrdinaryProviderError(
    RuntimeError
):
    """Raised when an ordinary finalized Stage 3B provider is inconsistent."""


@dataclass(
    frozen=True,
)
class AuditedOrdinaryProvider:
    """One fully audited ordinary Stage 3B provider."""

    batch_id: str
    source_class: str

    requested_accessions: int
    first_accession: str
    last_accession: str

    observed_batch_target_manifest_sha256: str
    observed_accessions_sha256: str
    observed_candidate_audit_sha256: str
    observed_component_audit_sha256: str

    provider_summary_sha256: str
    package_manifest_sha256: str

    package_file_count: int
    package_file_readback_count: int
    package_file_readback_sha256: str


def _fail(
    message: str,
) -> None:
    raise MonthlySequenceOrdinaryProviderError(
        message
    )


def audit_completed_transport_provider(
    evidence: CompletedTransportBatchEvidence,
    *,
    batch_index: int,
    expected_batch_count: int,
    expected_fresh_count: int,
    batch_targets: Sequence[
        object
    ],
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    stage2_sequence_plan_record_sha256: str,
    stage2_fresh_target_manifest_sha256: str,
    source_production_commit: str,
    environment_explicit_sha256: str,
) -> AuditedOrdinaryProvider:
    """
    Reproduce the frozen v1 ordinary per-batch completion audit.

    The live filesystem/scientific package is first revalidated by the frozen
    completion collector. This function then preserves the v1 transport-summary,
    provenance, manifest and independent-readback checks without invoking the
    ordinary-only release discovery gate.
    """

    if not isinstance(
        evidence,
        CompletedTransportBatchEvidence,
    ):
        raise TypeError(
            "ordinary provider evidence has wrong type"
        )

    index = _positive_int(
        batch_index,
        label="batch index",
    )

    batch_count = _nonnegative_int(
        expected_batch_count,
        label="expected batch count",
    )

    fresh_count = _nonnegative_int(
        expected_fresh_count,
        label="expected fresh-acquisition count",
    )

    if (
        index
        > batch_count
    ):
        _fail(
            "batch index exceeds expected batch count"
        )

    expected_id = (
        f"batch-{index:05d}"
    )

    observed_id = _batch_id(
        evidence.batch_id
    )

    if observed_id != expected_id:
        _fail(
            "ordinary provider batch ID changed"
        )

    snapshot = _normalized_text(
        source_snapshot_id,
        label="source snapshot ID",
    )

    snapshot_record_sha = _sha256(
        source_snapshot_record_sha256,
        label="source-snapshot-record SHA256",
    )

    plan_sha = _sha256(
        stage2_sequence_plan_record_sha256,
        label="Stage 2 sequence-plan SHA256",
    )

    manifest_sha = _sha256(
        stage2_fresh_target_manifest_sha256,
        label="Stage 2 fresh-target manifest SHA256",
    )

    source_commit = _git_commit(
        source_production_commit
    )

    environment_sha = _sha256(
        environment_explicit_sha256,
        label="NCBI environment SHA256",
    )

    try:
        summary = _audit_transport_summary(
            evidence.summary_payload
        )

    except (
        TypeError,
        MonthlySequenceAcquisitionCompletionError,
    ) as exc:
        raise MonthlySequenceOrdinaryProviderError(
            "ordinary transport summary audit failed"
        ) from exc

    if (
        summary[
            "source_snapshot_id"
        ]
        != snapshot
    ):
        _fail(
            "batch source snapshot ID changed"
        )

    if (
        summary[
            "source_snapshot_record_sha256"
        ]
        != snapshot_record_sha
    ):
        _fail(
            "batch source-snapshot-record SHA256 changed"
        )

    if (
        summary[
            "stage2_sequence_plan_record_sha256"
        ]
        != plan_sha
    ):
        _fail(
            "batch Stage 2 sequence-plan identity changed"
        )

    if (
        summary[
            "stage2_fresh_target_manifest_sha256"
        ]
        != manifest_sha
    ):
        _fail(
            "batch Stage 2 fresh-target identity changed"
        )

    if (
        summary[
            "origin_git_commit"
        ]
        != source_commit
    ):
        _fail(
            "batch origin Git commit changed"
        )

    if (
        summary[
            "datasets_version"
        ]
        != DATASETS_VERSION
    ):
        _fail(
            "batch NCBI Datasets version changed"
        )

    if (
        summary[
            "environment_explicit_sha256"
        ]
        != environment_sha
    ):
        _fail(
            "batch NCBI environment identity changed"
        )

    if (
        summary[
            "batch_index"
        ]
        != index
    ):
        _fail(
            "batch index changed"
        )

    if (
        summary[
            "batch_count"
        ]
        != batch_count
    ):
        _fail(
            "batch count changed"
        )

    if (
        summary[
            "batch_size"
        ]
        != FRESH_BATCH_SIZE
    ):
        _fail(
            "batch size changed"
        )

    if (
        summary[
            "full_target_count"
        ]
        != fresh_count
    ):
        _fail(
            "batch full-target count changed"
        )

    target_values = tuple(
        batch_targets
    )

    if not target_values:
        _fail(
            "expected Stage 3B batch has no targets"
        )

    expected_requested = len(
        target_values
    )

    if (
        summary[
            "requested_accessions"
        ]
        != expected_requested
    ):
        _fail(
            "batch requested-accession count changed"
        )

    try:
        first_accession = (
            target_values[
                0
            ].canonical_genbank_assembly_accession
        )

        last_accession = (
            target_values[
                -1
            ].canonical_genbank_assembly_accession
        )

    except AttributeError as exc:
        raise MonthlySequenceOrdinaryProviderError(
            "ordinary provider target has wrong type"
        ) from exc

    if (
        summary[
            "first_accession"
        ]
        != first_accession
    ):
        _fail(
            "batch first accession changed"
        )

    if (
        summary[
            "last_accession"
        ]
        != last_accession
    ):
        _fail(
            "batch last accession changed"
        )

    try:
        expected_target_sha = (
            batch_target_manifest_sha256(
                target_values
            )
        )

        expected_accessions_sha = (
            hashlib.sha256(
                batch_accession_bytes(
                    target_values
                )
            ).hexdigest()
        )

    except MonthlySequenceTransportError as exc:
        raise MonthlySequenceOrdinaryProviderError(
            "unable to derive frozen Stage 3B batch identity"
        ) from exc

    observed_target_sha = _sha256(
        evidence.observed_batch_target_manifest_sha256,
        label="observed batch-target manifest SHA256",
    )

    observed_accessions_sha = _sha256(
        evidence.observed_accessions_sha256,
        label="observed batch accession-list SHA256",
    )

    if (
        summary[
            "batch_target_manifest_sha256"
        ]
        != expected_target_sha
        or observed_target_sha
        != expected_target_sha
    ):
        _fail(
            "batch-target manifest identity changed"
        )

    if (
        summary[
            "accessions_sha256"
        ]
        != expected_accessions_sha
        or observed_accessions_sha
        != expected_accessions_sha
    ):
        _fail(
            "batch accession-list identity changed"
        )

    artifact_pairs = (
        (
            "dehydrated_zip_sha256",
            evidence.observed_dehydrated_zip_sha256,
            "dehydrated ZIP",
        ),
        (
            "fetch_txt_sha256",
            evidence.observed_fetch_txt_sha256,
            "fetch.txt",
        ),
        (
            "attempt_origin_sha256",
            evidence.observed_attempt_origin_sha256,
            "attempt-origin",
        ),
        (
            "candidate_sequence_audit_sha256",
            evidence.observed_candidate_audit_sha256,
            "candidate audit",
        ),
        (
            "component_sequence_audit_sha256",
            evidence.observed_component_audit_sha256,
            "component audit",
        ),
    )

    normalized_artifacts = {}

    for (
        field,
        observed_value,
        label,
    ) in artifact_pairs:
        summary_sha = _sha256(
            summary[
                field
            ],
            label=f"summary {label} SHA256",
        )

        observed_sha = _sha256(
            observed_value,
            label=f"observed {label} SHA256",
        )

        if observed_sha != summary_sha:
            _fail(
                f"{label} identity changed after "
                "Stage 3B completion"
            )

        normalized_artifacts[
            field
        ] = observed_sha

    if not isinstance(
        evidence.package_files_payload,
        bytes,
    ):
        raise TypeError(
            "package-files manifest must be bytes"
        )

    observed_package_manifest_sha = (
        hashlib.sha256(
            evidence.package_files_payload
        ).hexdigest()
    )

    summary_package_manifest_sha = (
        _sha256(
            summary[
                "package_files_sha256"
            ],
            label=(
                "summary package-files "
                "manifest SHA256"
            ),
        )
    )

    if (
        observed_package_manifest_sha
        != summary_package_manifest_sha
    ):
        _fail(
            "package-files manifest identity changed "
            "after Stage 3B completion"
        )

    try:
        package_manifest_rows = (
            _audit_package_files_manifest(
                evidence.package_files_payload
            )
        )

    except (
        TypeError,
        MonthlySequenceAcquisitionCompletionError,
    ) as exc:
        raise MonthlySequenceOrdinaryProviderError(
            "package-files manifest audit failed"
        ) from exc

    package_file_count = _positive_int(
        summary[
            "package_files"
        ],
        label="batch package-file count",
    )

    if (
        len(
            package_manifest_rows
        )
        != package_file_count
    ):
        _fail(
            "package-files manifest row count changed"
        )

    try:
        (
            package_readback_count,
            package_readback_sha,
        ) = _audit_package_readback(
            package_manifest_rows,
            evidence.package_file_observations,
        )

    except (
        TypeError,
        MonthlySequenceAcquisitionCompletionError,
    ) as exc:
        raise MonthlySequenceOrdinaryProviderError(
            "package-file independent readback audit failed"
        ) from exc

    if (
        package_readback_count
        != package_file_count
    ):
        raise RuntimeError(
            "verified package-file population became inconsistent"
        )

    candidate_records = _nonnegative_int(
        summary[
            "candidate_records"
        ],
        label="batch candidate-record count",
    )

    if candidate_records != expected_requested:
        _fail(
            "batch candidate-record count changed"
        )

    component_records = _nonnegative_int(
        summary[
            "component_records"
        ],
        label="batch component-record count",
    )

    if component_records < candidate_records:
        _fail(
            "batch component-record count is impossible"
        )

    _nonnegative_int(
        summary[
            "fetch_entries"
        ],
        label="batch fetch-entry count",
    )

    _nonnegative_int(
        summary[
            "initial_unresolved_accessions"
        ],
        label="batch initial unresolved-accession count",
    )

    broad_exit = summary[
        "broad_rehydrate_exit_code"
    ]

    if (
        broad_exit is not None
        and (
            isinstance(
                broad_exit,
                bool,
            )
            or not isinstance(
                broad_exit,
                int,
            )
        )
    ):
        _fail(
            "batch broad-rehydrate exit code is invalid"
        )

    if (
        summary[
            "targeted_retry_rounds"
        ]
        != TARGETED_RETRY_ROUNDS
    ):
        _fail(
            "batch targeted-retry bound changed"
        )

    if not isinstance(
        summary[
            "targeted_retry_events"
        ],
        list,
    ):
        _fail(
            "batch targeted-retry events changed type"
        )

    _normalized_text(
        summary[
            "execution_completed_at_utc"
        ],
        label="batch execution-completed timestamp",
    )

    return AuditedOrdinaryProvider(
        batch_id=expected_id,
        source_class=(
            SOURCE_CLASS_FRESH
        ),
        requested_accessions=(
            expected_requested
        ),
        first_accession=(
            first_accession
        ),
        last_accession=(
            last_accession
        ),
        observed_batch_target_manifest_sha256=(
            expected_target_sha
        ),
        observed_accessions_sha256=(
            expected_accessions_sha
        ),
        observed_candidate_audit_sha256=(
            normalized_artifacts[
                "candidate_sequence_audit_sha256"
            ]
        ),
        observed_component_audit_sha256=(
            normalized_artifacts[
                "component_sequence_audit_sha256"
            ]
        ),
        provider_summary_sha256=(
            _summary_sha256(
                evidence.summary_payload
            )
        ),
        package_manifest_sha256=(
            summary_package_manifest_sha
        ),
        package_file_count=(
            package_file_count
        ),
        package_file_readback_count=(
            package_readback_count
        ),
        package_file_readback_sha256=(
            package_readback_sha
        ),
    )
