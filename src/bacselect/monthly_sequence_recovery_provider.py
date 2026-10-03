"""Common audited provider surface for accepted monthly sequence recoveries."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from typing import Sequence

from bacselect import monthly_missing_datasets_gbff_execution as gbff_execution
from bacselect import monthly_post_snapshot_supersession_execution as supersession_execution
from bacselect import monthly_post_snapshot_supersession_recovery as supersession_recovery
from bacselect import monthly_sequence_recovery_authority as authority
from bacselect import monthly_sequence_validation as monthly


RECOVERY_CLASS_MISSING_DATASETS_GBFF = (
    gbff_execution.FAILURE_CLASS
)

RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION = (
    supersession_recovery.FAILURE_CLASS
)


class MonthlySequenceRecoveryProviderError(
    RuntimeError
):
    """Raised when a finalized recovery cannot be consumed unambiguously."""


@dataclass(
    frozen=True,
)
class AuditedRecoveryProvider:
    """One cause-audited provider behind the generic recovery authority."""

    batch_id: str
    source_class: str
    recovery_class: str
    batch_dir: Path
    source_partial_dir: Path
    source_production_commit: str
    recovery_commit: str
    source_batch_sha256: str
    source_package_sha256: str
    recovery_package_sha256: str
    candidate_audit_sha256: str
    component_audit_sha256: str
    recovery_summary_sha256: str
    cause_evidence_sha256: str
    transport_record_sha256: str | None


def _fail(
    message: str,
) -> None:
    raise MonthlySequenceRecoveryProviderError(
        message
    )


def _load_optional_json_object(
    path: Path,
    *,
    label: str,
) -> Mapping[
    str,
    object,
] | None:
    value = Path(
        path
    )

    if not os.path.lexists(
        value
    ):
        return None

    if (
        value.is_symlink()
        or not value.is_file()
    ):
        _fail(
            f"{label} is not a regular file"
        )

    try:
        payload = value.read_bytes()

    except OSError as exc:
        raise MonthlySequenceRecoveryProviderError(
            f"{label} could not be read"
        ) from exc

    if not payload:
        _fail(
            f"{label} is empty"
        )

    try:
        parsed = json.loads(
            payload.decode(
                "utf-8"
            )
        )

    except (
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlySequenceRecoveryProviderError(
            f"{label} is invalid JSON"
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        _fail(
            f"{label} is not a JSON object"
        )

    return parsed


def _recovery_class(
    batch_dir: Path,
) -> str:
    batch = Path(
        batch_dir
    )

    missing_payload = (
        _load_optional_json_object(
            batch
            / gbff_execution.RECOVERY_EVIDENCE_NAME,
            label=(
                "missing-Datasets-GBFF "
                "cause discriminator"
            ),
        )
    )

    supersession_payload = (
        _load_optional_json_object(
            batch
            / supersession_execution.TRANSPORT_RECORD_NAME,
            label=(
                "post-snapshot supersession "
                "cause discriminator"
            ),
        )
    )

    recognized: list[
        str
    ] = []

    if missing_payload is not None:
        observed = missing_payload.get(
            "failure_class"
        )

        if (
            observed
            != RECOVERY_CLASS_MISSING_DATASETS_GBFF
        ):
            _fail(
                "missing-Datasets-GBFF cause "
                f"discriminator is unknown: "
                f"{observed!r}"
            )

        recognized.append(
            RECOVERY_CLASS_MISSING_DATASETS_GBFF
        )

    if supersession_payload is not None:
        observed = supersession_payload.get(
            "classification"
        )

        if (
            observed
            != RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION
        ):
            _fail(
                "post-snapshot supersession cause "
                f"discriminator is unknown: "
                f"{observed!r}"
            )

        recognized.append(
            RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION
        )

    if not recognized:
        _fail(
            "finalized recovery contains no "
            "recognized cause discriminator"
        )

    if len(
        recognized
    ) != 1:
        _fail(
            "finalized recovery contains multiple "
            "recognized cause discriminators"
        )

    return recognized[
        0
    ]


def _audit_generic_authority(
    authoritative_batch: (
        authority.AuthoritativeSequenceBatch
    ),
    *,
    expected_release_id: str,
    expected_source_production_commit: str,
) -> authority.AcceptedRecoveryEvidence:
    if not isinstance(
        authoritative_batch,
        authority.AuthoritativeSequenceBatch,
    ):
        raise TypeError(
            "authoritative_batch has wrong type"
        )

    if (
        authoritative_batch.source_class
        != authority.SOURCE_CLASS_FRESH_RECOVERY
    ):
        _fail(
            "recovery-provider adapter requires "
            "source_class fresh-recovery"
        )

    if (
        authoritative_batch.source_partial_dir
        is None
        or authoritative_batch.recovery_commit
        is None
        or authoritative_batch.recovery_summary_sha256
        is None
    ):
        _fail(
            "fresh-recovery authority is missing "
            "recovery identity"
        )

    try:
        accepted = (
            authority
            .audit_final_recovery(
                batch_dir=(
                    authoritative_batch.batch_dir
                ),
                source_partial_dir=(
                    authoritative_batch
                    .source_partial_dir
                ),
                expected_release_id=(
                    expected_release_id
                ),
                expected_source_production_commit=(
                    expected_source_production_commit
                ),
            )
        )

    except authority.MonthlySequenceRecoveryAuthorityError as exc:
        raise MonthlySequenceRecoveryProviderError(
            "generic recovery authority audit failed"
        ) from exc

    if (
        accepted.batch_id
        != authoritative_batch.batch_id
        or accepted.batch_dir
        != authoritative_batch.batch_dir
        or accepted.source_partial_dir
        != authoritative_batch.source_partial_dir
        or accepted.recovery_commit
        != authoritative_batch.recovery_commit
        or accepted.summary_sha256
        != authoritative_batch.recovery_summary_sha256
    ):
        _fail(
            "resolver authority differs from "
            "independent finalized-recovery audit"
        )

    return accepted


def _require_common_identity(
    cause_result: object,
    accepted: authority.AcceptedRecoveryEvidence,
) -> None:
    checks = (
        (
            "batch_id",
            accepted.batch_id,
        ),
        (
            "batch_dir",
            accepted.batch_dir,
        ),
        (
            "source_partial_dir",
            accepted.source_partial_dir,
        ),
        (
            "recovery_commit",
            accepted.recovery_commit,
        ),
        (
            "recovery_summary_sha256",
            accepted.summary_sha256,
        ),
    )

    for field, expected in checks:
        observed = getattr(
            cause_result,
            field,
            None,
        )

        if observed != expected:
            _fail(
                "cause-specific final audit "
                f"changed common provider field "
                f"{field!r}"
            )


def audit_authoritative_recovery_provider(
    authoritative_batch: (
        authority.AuthoritativeSequenceBatch
    ),
    *,
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
    expected_release_id: str,
    expected_source_production_commit: str,
    source_snapshot_report: Path | None = None,
) -> AuditedRecoveryProvider:
    """
    Independently audit one resolver-approved fresh-recovery provider.

    Cause selection comes only from frozen explicit cause-discriminator
    records. No accession-, batch-, path-order-, or validator-guessing
    dispatch is permitted.
    """

    target_values = tuple(
        targets
    )

    accepted = (
        _audit_generic_authority(
            authoritative_batch,
            expected_release_id=(
                expected_release_id
            ),
            expected_source_production_commit=(
                expected_source_production_commit
            ),
        )
    )

    recovery_class = (
        _recovery_class(
            accepted.batch_dir
        )
    )

    cause_evidence_sha256: str
    transport_record_sha256: str | None

    if (
        recovery_class
        == RECOVERY_CLASS_MISSING_DATASETS_GBFF
    ):
        try:
            result = (
                gbff_execution
                .audit_finalized_missing_datasets_gbff_recovery(
                    batch_dir=(
                        accepted.batch_dir
                    ),
                    source_partial_dir=(
                        accepted.source_partial_dir
                    ),
                    targets=target_values,
                    expected_release_id=(
                        expected_release_id
                    ),
                    expected_source_production_commit=(
                        expected_source_production_commit
                    ),
                )
            )

        except (
            gbff_execution
            .MonthlyMissingDatasetsGbffExecutionError
        ) as exc:
            raise MonthlySequenceRecoveryProviderError(
                "missing-Datasets-GBFF final "
                "provider audit failed"
            ) from exc

        _require_common_identity(
            result,
            accepted,
        )

        cause_evidence_sha256 = (
            result.recovery_evidence_sha256
        )

        transport_record_sha256 = None

    elif (
        recovery_class
        == RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION
    ):
        if source_snapshot_report is None:
            _fail(
                "post-snapshot supersession provider "
                "requires source_snapshot_report"
            )

        try:
            result = (
                supersession_execution
                .audit_finalized_post_snapshot_supersession_recovery(
                    batch_dir=(
                        accepted.batch_dir
                    ),
                    source_partial_dir=(
                        accepted.source_partial_dir
                    ),
                    source_snapshot_report=(
                        Path(
                            source_snapshot_report
                        )
                    ),
                    targets=target_values,
                    expected_release_id=(
                        expected_release_id
                    ),
                    expected_source_production_commit=(
                        expected_source_production_commit
                    ),
                )
            )

        except (
            supersession_execution
            .MonthlyPostSnapshotSupersessionExecutionError
        ) as exc:
            raise MonthlySequenceRecoveryProviderError(
                "post-snapshot supersession final "
                "provider audit failed"
            ) from exc

        _require_common_identity(
            result,
            accepted,
        )

        cause_evidence_sha256 = (
            result.supersession_evidence_sha256
        )

        transport_record_sha256 = (
            result.transport_record_sha256
        )

    else:
        # Defensive only. _recovery_class() is already closed over
        # the exact recognized set.
        _fail(
            f"unsupported recovery class: "
            f"{recovery_class!r}"
        )

    return AuditedRecoveryProvider(
        batch_id=(
            accepted.batch_id
        ),
        source_class=(
            authority.SOURCE_CLASS_FRESH_RECOVERY
        ),
        recovery_class=(
            recovery_class
        ),
        batch_dir=(
            accepted.batch_dir
        ),
        source_partial_dir=(
            accepted.source_partial_dir
        ),
        source_production_commit=(
            accepted.source_production_commit
        ),
        recovery_commit=(
            accepted.recovery_commit
        ),
        source_batch_sha256=(
            accepted.source_batch_sha256
        ),
        source_package_sha256=(
            accepted.source_package_sha256
        ),
        recovery_package_sha256=(
            accepted.recovery_package_sha256
        ),
        candidate_audit_sha256=(
            accepted.candidate_audit_sha256
        ),
        component_audit_sha256=(
            accepted.component_audit_sha256
        ),
        recovery_summary_sha256=(
            accepted.summary_sha256
        ),
        cause_evidence_sha256=(
            cause_evidence_sha256
        ),
        transport_record_sha256=(
            transport_record_sha256
        ),
    )
