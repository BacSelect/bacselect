"""Pure recovery-aware BacSelect monthly sequence-cache catalogue v2."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping
from typing import Sequence

from bacselect import monthly_sequence_cache_catalogue as v1
from bacselect import monthly_sequence_acquisition_completion_v2 as completion_v2


MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA = (
    "bacselect-monthly-sequence-cache-catalogue-v2"
)

MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_STATUS = (
    "SEQUENCE_CACHE_CATALOGUE_COMPLETE"
)

BATCH_PROVENANCE_V2_SCHEMA = (
    "bacselect-monthly-sequence-cache-batch-provenance-v2"
)

BATCH_PROVENANCE_SET_V2_SCHEMA = (
    "bacselect-monthly-sequence-cache-batch-provenance-set-v2"
)

ENTRY_V2_SCHEMA = (
    "bacselect-monthly-sequence-cache-entry-v2"
)

ENTRY_SET_V2_SCHEMA = (
    "bacselect-monthly-sequence-cache-entry-set-v2"
)

GENESIS = v1.GENESIS
CHAINED = v1.CHAINED

SOURCE_CLASS_FRESH = (
    completion_v2.SOURCE_CLASS_FRESH
)

SOURCE_CLASS_FRESH_RECOVERY = (
    completion_v2.SOURCE_CLASS_FRESH_RECOVERY
)

RECOVERY_CLASS_MISSING_DATASETS_GBFF = (
    completion_v2.RECOVERY_CLASS_MISSING_DATASETS_GBFF
)

RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION = (
    completion_v2.RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION
)

FRESH_PROVIDER_SUMMARY_NAME = (
    completion_v2.FRESH_PROVIDER_SUMMARY_NAME
)

RECOVERY_PROVIDER_SUMMARY_NAME = (
    completion_v2.RECOVERY_PROVIDER_SUMMARY_NAME
)

FRESH_PACKAGE_MANIFEST_NAME = (
    completion_v2.FRESH_PACKAGE_MANIFEST_NAME
)

RECOVERY_PACKAGE_MANIFEST_NAME = (
    completion_v2.RECOVERY_PACKAGE_MANIFEST_NAME
)

CANDIDATE_AUDIT_NAME = (
    "candidate-sequence-audit.tsv"
)

COMPONENT_AUDIT_NAME = (
    "component-sequence-audit.tsv"
)

_V2_BATCH_PROVENANCE_KEYS = {
    "accessions_sha256",
    "batch_id",
    "batch_provenance_sha256",
    "cache_origin_completion_execution_commit",
    "cache_origin_execution_commit",
    "cache_origin_release_id",
    "cache_origin_source_production_commit",
    "cache_origin_source_snapshot_id",
    "candidate_audit",
    "cause_evidence_sha256",
    "component_audit",
    "origin_package_file_readback_sha256",
    "origin_sequence_acquisition_completion_sha256",
    "package_manifest",
    "provider_summary",
    "recovery_class",
    "recovery_commit",
    "recovery_package_sha256",
    "recovery_summary_sha256",
    "requested_accessions",
    "source_batch_sha256",
    "source_class",
    "source_package_sha256",
    "source_partial_name",
    "transport_record_sha256",
}

_ENTRY_KEYS = {
    "biosample",
    "canonical_genbank_assembly_accession",
    "entry_sha256",
    "origin_batch_provenance_sha256",
    "origin_sequence_eligibility",
    "origin_sequence_exclusion_reasons",
    "package_artifacts",
}

_V2_CATALOGUE_KEYS = {
    "batch_provenance",
    "batch_provenance_count",
    "batch_provenance_sha256",
    "cache_execution_commit",
    "carried_forward_entry_count",
    "catalogue_entry_count",
    "catalogue_mode",
    "completion_execution_commit",
    "current_acquisition_count",
    "entries",
    "entries_sha256",
    "new_entry_count",
    "previous_catalogue_entry_count",
    "previous_catalogue_release_id",
    "previous_catalogue_sha256",
    "release_id",
    "replaced_entry_count",
    "schema_version",
    "sequence_acquisition_completion_sha256",
    "sequence_acquisition_fresh_count",
    "sequence_acquisition_source_class_counts",
    "source_production_commit",
    "source_snapshot_id",
    "status",
}


class MonthlySequenceCacheCatalogueV2Error(
    RuntimeError
):
    """Raised when the recovery-aware cache-v2 contract is violated."""


@dataclass(
    frozen=True,
)
class AuthoritativeSequenceCacheBatchEvidenceV2:
    """Provider-normalized current-batch evidence for the pure cache-v2 core."""

    batch_id: str
    source_class: str
    recovery_class: str | None

    provider_summary_name: str
    provider_summary_payload: bytes

    candidate_audit_payload: bytes
    component_audit_payload: bytes

    package_manifest_name: str
    package_manifest_payload: bytes

    source_partial_name: str | None
    recovery_commit: str | None

    source_batch_sha256: str | None
    source_package_sha256: str | None
    recovery_package_sha256: str | None
    recovery_summary_sha256: str | None
    cause_evidence_sha256: str | None
    transport_record_sha256: str | None


def _fail(
    message: str,
) -> None:
    raise MonthlySequenceCacheCatalogueV2Error(
        message
    )


def _canonical_json_bytes(
    value: object,
) -> bytes:
    return v1._canonical_json_bytes(
        value
    )


def _provider_prefix(
    *,
    batch_id: str,
    source_class: str,
    source_production_commit: str,
    recovery_commit: str | None,
) -> str:
    batch = v1._batch_id(
        batch_id
    )

    source_commit = v1._git_commit(
        source_production_commit
    )

    if source_class == SOURCE_CLASS_FRESH:
        if recovery_commit is not None:
            _fail(
                "fresh provider unexpectedly contains recovery commit"
            )

        return (
            f"sequence-acquisition/{batch}/"
        )

    if source_class != SOURCE_CLASS_FRESH_RECOVERY:
        _fail(
            "unknown sequence-cache source class"
        )

    recover_commit = v1._git_commit(
        recovery_commit
    )

    return (
        "sequence-acquisition-recovery/"
        f"{recover_commit}/"
        f"source-{source_commit}/"
        f"{batch}/"
    )


def _batch_provenance_v2_payload(
    row: Mapping[
        str,
        object,
    ],
) -> bytes:
    return _canonical_json_bytes(
        {
            "accessions_sha256":
                row[
                    "accessions_sha256"
                ],
            "batch_id":
                row[
                    "batch_id"
                ],
            "cache_origin_completion_execution_commit":
                row[
                    "cache_origin_completion_execution_commit"
                ],
            "cache_origin_execution_commit":
                row[
                    "cache_origin_execution_commit"
                ],
            "cache_origin_release_id":
                row[
                    "cache_origin_release_id"
                ],
            "cache_origin_source_production_commit":
                row[
                    "cache_origin_source_production_commit"
                ],
            "cache_origin_source_snapshot_id":
                row[
                    "cache_origin_source_snapshot_id"
                ],
            "candidate_audit":
                row[
                    "candidate_audit"
                ],
            "cause_evidence_sha256":
                row[
                    "cause_evidence_sha256"
                ],
            "component_audit":
                row[
                    "component_audit"
                ],
            "origin_package_file_readback_sha256":
                row[
                    "origin_package_file_readback_sha256"
                ],
            "origin_sequence_acquisition_completion_sha256":
                row[
                    "origin_sequence_acquisition_completion_sha256"
                ],
            "package_manifest":
                row[
                    "package_manifest"
                ],
            "provider_summary":
                row[
                    "provider_summary"
                ],
            "recovery_class":
                row[
                    "recovery_class"
                ],
            "recovery_commit":
                row[
                    "recovery_commit"
                ],
            "recovery_package_sha256":
                row[
                    "recovery_package_sha256"
                ],
            "recovery_summary_sha256":
                row[
                    "recovery_summary_sha256"
                ],
            "requested_accessions":
                row[
                    "requested_accessions"
                ],
            "schema_version":
                BATCH_PROVENANCE_V2_SCHEMA,
            "source_batch_sha256":
                row[
                    "source_batch_sha256"
                ],
            "source_class":
                row[
                    "source_class"
                ],
            "source_package_sha256":
                row[
                    "source_package_sha256"
                ],
            "source_partial_name":
                row[
                    "source_partial_name"
                ],
            "transport_record_sha256":
                row[
                    "transport_record_sha256"
                ],
        }
    )


def _entry_v2_payload(
    row: Mapping[
        str,
        object,
    ],
) -> bytes:
    return _canonical_json_bytes(
        {
            "biosample":
                row[
                    "biosample"
                ],
            "canonical_genbank_assembly_accession":
                row[
                    "canonical_genbank_assembly_accession"
                ],
            "origin_batch_provenance_sha256":
                row[
                    "origin_batch_provenance_sha256"
                ],
            "origin_sequence_eligibility":
                row[
                    "origin_sequence_eligibility"
                ],
            "origin_sequence_exclusion_reasons":
                row[
                    "origin_sequence_exclusion_reasons"
                ],
            "package_artifacts":
                row[
                    "package_artifacts"
                ],
            "schema_version":
                ENTRY_V2_SCHEMA,
        }
    )


def _normalize_optional_sha256(
    value: object,
    *,
    label: str,
) -> str | None:
    if value is None:
        return None

    return v1._sha256(
        value,
        label=label,
    )


def _normalize_optional_commit(
    value: object,
) -> str | None:
    if value is None:
        return None

    return v1._git_commit(
        value
    )


def _normalize_optional_text(
    value: object,
    *,
    label: str,
) -> str | None:
    if value is None:
        return None

    return v1._nonempty_text(
        value,
        label=label,
    )


def _validate_source_class_contract(
    *,
    batch_id: str,
    source_class: str,
    recovery_class: str | None,
    source_partial_name: str | None,
    recovery_commit: str | None,
    source_batch_sha256: str | None,
    source_package_sha256: str | None,
    recovery_package_sha256: str | None,
    recovery_summary_sha256: str | None,
    cause_evidence_sha256: str | None,
    transport_record_sha256: str | None,
) -> None:
    batch = v1._batch_id(
        batch_id
    )

    recovery_values = (
        source_partial_name,
        recovery_commit,
        source_batch_sha256,
        source_package_sha256,
        recovery_package_sha256,
        recovery_summary_sha256,
        cause_evidence_sha256,
        transport_record_sha256,
    )

    if source_class == SOURCE_CLASS_FRESH:
        if recovery_class is not None:
            _fail(
                "fresh batch contains recovery class"
            )

        if any(
            value is not None
            for value in recovery_values
        ):
            _fail(
                "fresh batch contains recovery-only identity"
            )

        return

    if source_class != SOURCE_CLASS_FRESH_RECOVERY:
        _fail(
            "unknown sequence-cache source class"
        )

    if recovery_class not in {
        RECOVERY_CLASS_MISSING_DATASETS_GBFF,
        RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION,
    }:
        _fail(
            "fresh-recovery batch has invalid recovery class"
        )

    if source_partial_name != (
        f"{batch}.partial"
    ):
        _fail(
            "fresh-recovery source partial name changed"
        )

    v1._git_commit(
        recovery_commit
    )

    for value, label in (
        (
            source_batch_sha256,
            "source batch SHA256",
        ),
        (
            source_package_sha256,
            "source package SHA256",
        ),
        (
            recovery_package_sha256,
            "recovery package SHA256",
        ),
        (
            recovery_summary_sha256,
            "recovery summary SHA256",
        ),
        (
            cause_evidence_sha256,
            "cause evidence SHA256",
        ),
    ):
        v1._sha256(
            value,
            label=label,
        )

    if (
        recovery_class
        == RECOVERY_CLASS_MISSING_DATASETS_GBFF
    ):
        if transport_record_sha256 is not None:
            _fail(
                "missing-Datasets-GBFF recovery "
                "unexpectedly contains transport record"
            )

    else:
        v1._sha256(
            transport_record_sha256,
            label="supersession transport-record SHA256",
        )


def _audit_batch_provenance_v2_row(
    value: object,
) -> dict[
    str,
    object,
]:
    if (
        not isinstance(
            value,
            dict,
        )
        or set(
            value
        )
        != _V2_BATCH_PROVENANCE_KEYS
    ):
        _fail(
            "cache-v2 batch-provenance schema changed"
        )

    release = v1._release_id(
        value[
            "cache_origin_release_id"
        ]
    )

    snapshot = v1._source_snapshot_id(
        value[
            "cache_origin_source_snapshot_id"
        ],
        release_id=release,
    )

    source_commit = v1._git_commit(
        value[
            "cache_origin_source_production_commit"
        ]
    )

    completion_commit = v1._git_commit(
        value[
            "cache_origin_completion_execution_commit"
        ]
    )

    cache_commit = v1._git_commit(
        value[
            "cache_origin_execution_commit"
        ]
    )

    batch = v1._batch_id(
        value[
            "batch_id"
        ]
    )

    source_class = value[
        "source_class"
    ]

    recovery_class = (
        _normalize_optional_text(
            value[
                "recovery_class"
            ],
            label="recovery class",
        )
    )

    source_partial_name = (
        _normalize_optional_text(
            value[
                "source_partial_name"
            ],
            label="source partial name",
        )
    )

    recovery_commit = (
        _normalize_optional_commit(
            value[
                "recovery_commit"
            ]
        )
    )

    source_batch_sha = (
        _normalize_optional_sha256(
            value[
                "source_batch_sha256"
            ],
            label="source batch SHA256",
        )
    )

    source_package_sha = (
        _normalize_optional_sha256(
            value[
                "source_package_sha256"
            ],
            label="source package SHA256",
        )
    )

    recovery_package_sha = (
        _normalize_optional_sha256(
            value[
                "recovery_package_sha256"
            ],
            label="recovery package SHA256",
        )
    )

    recovery_summary_sha = (
        _normalize_optional_sha256(
            value[
                "recovery_summary_sha256"
            ],
            label="recovery summary SHA256",
        )
    )

    cause_evidence_sha = (
        _normalize_optional_sha256(
            value[
                "cause_evidence_sha256"
            ],
            label="cause evidence SHA256",
        )
    )

    transport_record_sha = (
        _normalize_optional_sha256(
            value[
                "transport_record_sha256"
            ],
            label="transport-record SHA256",
        )
    )

    _validate_source_class_contract(
        batch_id=batch,
        source_class=source_class,
        recovery_class=recovery_class,
        source_partial_name=source_partial_name,
        recovery_commit=recovery_commit,
        source_batch_sha256=source_batch_sha,
        source_package_sha256=source_package_sha,
        recovery_package_sha256=recovery_package_sha,
        recovery_summary_sha256=recovery_summary_sha,
        cause_evidence_sha256=cause_evidence_sha,
        transport_record_sha256=transport_record_sha,
    )

    prefix = _provider_prefix(
        batch_id=batch,
        source_class=source_class,
        source_production_commit=source_commit,
        recovery_commit=recovery_commit,
    )

    provider_summary = (
        v1._audit_artifact_reference(
            value[
                "provider_summary"
            ],
            label="provider summary",
        )
    )

    candidate = (
        v1._audit_artifact_reference(
            value[
                "candidate_audit"
            ],
            label="candidate audit",
        )
    )

    component = (
        v1._audit_artifact_reference(
            value[
                "component_audit"
            ],
            label="component audit",
        )
    )

    package_manifest = (
        v1._audit_artifact_reference(
            value[
                "package_manifest"
            ],
            label="package manifest",
        )
    )

    if source_class == SOURCE_CLASS_FRESH:
        provider_name = (
            FRESH_PROVIDER_SUMMARY_NAME
        )

        manifest_name = (
            FRESH_PACKAGE_MANIFEST_NAME
        )

    else:
        provider_name = (
            RECOVERY_PROVIDER_SUMMARY_NAME
        )

        manifest_name = (
            RECOVERY_PACKAGE_MANIFEST_NAME
        )

    expected_paths = {
        prefix
        + provider_name:
            provider_summary[
                "logical_path"
            ],
        prefix
        + CANDIDATE_AUDIT_NAME:
            candidate[
                "logical_path"
            ],
        prefix
        + COMPONENT_AUDIT_NAME:
            component[
                "logical_path"
            ],
        prefix
        + manifest_name:
            package_manifest[
                "logical_path"
            ],
    }

    for expected, observed in (
        expected_paths.items()
    ):
        if observed != expected:
            _fail(
                "cache-v2 provider artifact logical path changed"
            )

    if (
        source_class
        == SOURCE_CLASS_FRESH_RECOVERY
    ):
        if (
            provider_summary[
                "sha256"
            ]
            != recovery_summary_sha
        ):
            _fail(
                "recovery provider-summary identity changed"
            )

        if (
            package_manifest[
                "sha256"
            ]
            != recovery_package_sha
        ):
            _fail(
                "recovery package-manifest identity changed"
            )

    row = {
        "accessions_sha256":
            v1._sha256(
                value[
                    "accessions_sha256"
                ],
                label="batch accessions SHA256",
            ),
        "batch_id":
            batch,
        "cache_origin_completion_execution_commit":
            completion_commit,
        "cache_origin_execution_commit":
            cache_commit,
        "cache_origin_release_id":
            release,
        "cache_origin_source_production_commit":
            source_commit,
        "cache_origin_source_snapshot_id":
            snapshot,
        "candidate_audit":
            candidate,
        "cause_evidence_sha256":
            cause_evidence_sha,
        "component_audit":
            component,
        "origin_package_file_readback_sha256":
            v1._sha256(
                value[
                    "origin_package_file_readback_sha256"
                ],
                label="origin package read-back SHA256",
            ),
        "origin_sequence_acquisition_completion_sha256":
            v1._sha256(
                value[
                    "origin_sequence_acquisition_completion_sha256"
                ],
                label="origin completion SHA256",
            ),
        "package_manifest":
            package_manifest,
        "provider_summary":
            provider_summary,
        "recovery_class":
            recovery_class,
        "recovery_commit":
            recovery_commit,
        "recovery_package_sha256":
            recovery_package_sha,
        "recovery_summary_sha256":
            recovery_summary_sha,
        "requested_accessions":
            v1._positive_int(
                value[
                    "requested_accessions"
                ],
                label="batch requested-accession count",
            ),
        "source_batch_sha256":
            source_batch_sha,
        "source_class":
            source_class,
        "source_package_sha256":
            source_package_sha,
        "source_partial_name":
            source_partial_name,
        "transport_record_sha256":
            transport_record_sha,
    }

    digest = hashlib.sha256(
        _batch_provenance_v2_payload(
            row
        )
    ).hexdigest()

    if (
        value[
            "batch_provenance_sha256"
        ]
        != digest
    ):
        _fail(
            "cache-v2 batch-provenance SHA256 changed"
        )

    return {
        **row,
        "batch_provenance_sha256":
            digest,
    }


def _audit_package_artifact_v2(
    value: object,
    *,
    accession: str,
    provenance: Mapping[
        str,
        object,
    ],
) -> dict[
    str,
    object,
]:
    if (
        not isinstance(
            value,
            dict,
        )
        or set(
            value
        )
        != {
            "logical_path",
            "package_path",
            "sha256",
            "size_bytes",
        }
    ):
        _fail(
            "cache-v2 package-artifact schema changed"
        )

    accession_value = v1._accession(
        accession
    )

    package_path = v1._safe_relative_path(
        value[
            "package_path"
        ],
        label="cache-v2 package path",
    )

    accession_prefix = (
        "ncbi_dataset/data/"
        f"{accession_value}/"
    )

    if (
        not package_path.startswith(
            accession_prefix
        )
        or package_path
        == accession_prefix
    ):
        _fail(
            "cache-v2 package artifact "
            "does not belong to accession"
        )

    provider_prefix = _provider_prefix(
        batch_id=(
            provenance[
                "batch_id"
            ]
        ),
        source_class=(
            provenance[
                "source_class"
            ]
        ),
        source_production_commit=(
            provenance[
                "cache_origin_source_production_commit"
            ]
        ),
        recovery_commit=(
            provenance[
                "recovery_commit"
            ]
        ),
    )

    logical_path = v1._safe_relative_path(
        value[
            "logical_path"
        ],
        label="cache-v2 package logical path",
    )

    expected_logical_path = (
        provider_prefix
        + "package/"
        + package_path
    )

    if logical_path != expected_logical_path:
        _fail(
            "cache-v2 package logical path "
            "does not match provider provenance"
        )

    return {
        "logical_path":
            logical_path,
        "package_path":
            package_path,
        "sha256":
            v1._sha256(
                value[
                    "sha256"
                ],
                label="cache-v2 package SHA256",
            ),
        "size_bytes":
            v1._nonnegative_int(
                value[
                    "size_bytes"
                ],
                label="cache-v2 package size",
            ),
    }


def _audit_entry_v2(
    value: object,
    *,
    provenance_by_sha: Mapping[
        str,
        Mapping[
            str,
            object,
        ],
    ],
) -> dict[
    str,
    object,
]:
    if (
        not isinstance(
            value,
            dict,
        )
        or set(
            value
        )
        != _ENTRY_KEYS
    ):
        _fail(
            "cache-v2 entry schema changed"
        )

    accession = v1._accession(
        value[
            "canonical_genbank_assembly_accession"
        ]
    )

    biosample = v1._biosample(
        value[
            "biosample"
        ]
    )

    origin = v1._sha256(
        value[
            "origin_batch_provenance_sha256"
        ],
        label="origin batch-provenance SHA256",
    )

    provenance = provenance_by_sha.get(
        origin
    )

    if provenance is None:
        _fail(
            "cache-v2 entry references missing batch provenance"
        )

    if "source_class" not in provenance:
        _fail(
            "cache-v2 entry is bound to legacy provenance"
        )

    eligibility = v1._sequence_eligibility(
        value[
            "origin_sequence_eligibility"
        ]
    )

    exclusion_text = v1._nonempty_text(
        value[
            "origin_sequence_exclusion_reasons"
        ],
        label="origin sequence exclusion reasons",
    )

    reasons = v1._sequence_exclusion_reasons(
        exclusion_text
    )

    v1._validate_sequence_eligibility_pair(
        eligibility=eligibility,
        reasons=reasons,
    )

    artifact_values = value[
        "package_artifacts"
    ]

    if (
        not isinstance(
            artifact_values,
            list,
        )
        or not artifact_values
    ):
        _fail(
            "cache-v2 entry has no package artifacts"
        )

    artifacts = tuple(
        _audit_package_artifact_v2(
            item,
            accession=accession,
            provenance=provenance,
        )
        for item in artifact_values
    )

    package_paths = tuple(
        item[
            "package_path"
        ]
        for item in artifacts
    )

    if package_paths != tuple(
        sorted(
            package_paths
        )
    ):
        _fail(
            "cache-v2 package artifacts are not sorted"
        )

    if len(
        package_paths
    ) != len(
        set(
            package_paths
        )
    ):
        _fail(
            "cache-v2 package artifacts contain duplicate paths"
        )

    row = {
        "biosample":
            biosample,
        "canonical_genbank_assembly_accession":
            accession,
        "origin_batch_provenance_sha256":
            origin,
        "origin_sequence_eligibility":
            eligibility,
        "origin_sequence_exclusion_reasons":
            exclusion_text,
        "package_artifacts":
            list(
                artifacts
            ),
    }

    digest = hashlib.sha256(
        _entry_v2_payload(
            row
        )
    ).hexdigest()

    if value[
        "entry_sha256"
    ] != digest:
        _fail(
            "cache-v2 entry SHA256 changed"
        )

    return {
        **row,
        "entry_sha256":
            digest,
    }


def _compatibility_completion_row(
    row: Mapping[
        str,
        object,
    ],
) -> dict[
    str,
    object,
]:
    """
    Present completion-v2 identities to the frozen v1 scientific derivation.

    The returned ordinary-only provenance from that function is discarded.
    Only its candidate/component/package scientific validation is reused.
    """

    return {
        "accessions_sha256":
            row[
                "accessions_sha256"
            ],
        "batch_id":
            row[
                "batch_id"
            ],
        "batch_index":
            row[
                "batch_index"
            ],
        "batch_summary_sha256":
            row[
                "provider_summary_sha256"
            ],
        "batch_target_manifest_sha256":
            row[
                "batch_target_manifest_sha256"
            ],
        "candidate_sequence_audit_sha256":
            row[
                "candidate_sequence_audit_sha256"
            ],
        "component_sequence_audit_sha256":
            row[
                "component_sequence_audit_sha256"
            ],
        "fetch_entries":
            0,
        "first_accession":
            row[
                "first_accession"
            ],
        "last_accession":
            row[
                "last_accession"
            ],
        "package_file_readback_count":
            row[
                "package_file_readback_count"
            ],
        "package_file_readback_sha256":
            row[
                "package_file_readback_sha256"
            ],
        "package_files":
            row[
                "package_files"
            ],
        "package_files_sha256":
            row[
                "package_manifest_sha256"
            ],
        "requested_accessions":
            row[
                "requested_accessions"
            ],
    }


def _validate_current_evidence_binding(
    evidence: AuthoritativeSequenceCacheBatchEvidenceV2,
    completion_row: Mapping[
        str,
        object,
    ],
) -> None:
    if not isinstance(
        evidence,
        AuthoritativeSequenceCacheBatchEvidenceV2,
    ):
        raise TypeError(
            "cache-v2 current batch evidence has wrong type"
        )

    if (
        v1._batch_id(
            evidence.batch_id
        )
        != completion_row[
            "batch_id"
        ]
    ):
        _fail(
            "cache-v2 evidence batch differs from completion"
        )

    if (
        evidence.source_class
        != completion_row[
            "source_class"
        ]
    ):
        _fail(
            "cache-v2 evidence source class differs from completion"
        )

    if (
        evidence.recovery_class
        != completion_row[
            "recovery_class"
        ]
    ):
        _fail(
            "cache-v2 evidence recovery class differs from completion"
        )

    if (
        evidence.provider_summary_name
        != completion_row[
            "provider_summary_name"
        ]
    ):
        _fail(
            "cache-v2 provider-summary name differs from completion"
        )

    if (
        evidence.package_manifest_name
        != completion_row[
            "package_manifest_name"
        ]
    ):
        _fail(
            "cache-v2 package-manifest name differs from completion"
        )

    for payload, expected, label in (
        (
            evidence.provider_summary_payload,
            completion_row[
                "provider_summary_sha256"
            ],
            "provider summary",
        ),
        (
            evidence.candidate_audit_payload,
            completion_row[
                "candidate_sequence_audit_sha256"
            ],
            "candidate audit",
        ),
        (
            evidence.component_audit_payload,
            completion_row[
                "component_sequence_audit_sha256"
            ],
            "component audit",
        ),
        (
            evidence.package_manifest_payload,
            completion_row[
                "package_manifest_sha256"
            ],
            "package manifest",
        ),
    ):
        if not isinstance(
            payload,
            bytes,
        ):
            raise TypeError(
                f"{label} payload must be bytes"
            )

        observed = hashlib.sha256(
            payload
        ).hexdigest()

        if observed != expected:
            _fail(
                f"cache-v2 {label} identity differs from completion"
            )

    for field in (
        "source_partial_name",
        "recovery_commit",
        "source_batch_sha256",
        "source_package_sha256",
        "recovery_package_sha256",
        "recovery_summary_sha256",
        "cause_evidence_sha256",
        "transport_record_sha256",
    ):
        if (
            getattr(
                evidence,
                field,
            )
            != completion_row[
                field
            ]
        ):
            _fail(
                f"cache-v2 {field} differs from completion"
            )

    _validate_source_class_contract(
        batch_id=evidence.batch_id,
        source_class=evidence.source_class,
        recovery_class=evidence.recovery_class,
        source_partial_name=evidence.source_partial_name,
        recovery_commit=evidence.recovery_commit,
        source_batch_sha256=evidence.source_batch_sha256,
        source_package_sha256=evidence.source_package_sha256,
        recovery_package_sha256=evidence.recovery_package_sha256,
        recovery_summary_sha256=evidence.recovery_summary_sha256,
        cause_evidence_sha256=evidence.cause_evidence_sha256,
        transport_record_sha256=evidence.transport_record_sha256,
    )


def _derive_current_batch_v2(
    *,
    release_id: str,
    source_snapshot_id: str,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    completion_sha256: str,
    completion_row: Mapping[
        str,
        object,
    ],
    evidence: AuthoritativeSequenceCacheBatchEvidenceV2,
) -> tuple[
    dict[
        str,
        object,
    ],
    tuple[
        dict[
            str,
            object,
        ],
        ...,
    ],
]:
    _validate_current_evidence_binding(
        evidence,
        completion_row,
    )

    compatibility_evidence = (
        v1.CompletedSequenceCacheBatchEvidence(
            batch_id=(
                evidence.batch_id
            ),
            summary_payload=(
                evidence.provider_summary_payload
            ),
            candidate_audit_payload=(
                evidence.candidate_audit_payload
            ),
            component_audit_payload=(
                evidence.component_audit_payload
            ),
            package_files_payload=(
                evidence.package_manifest_payload
            ),
        )
    )

    (
        ignored_v1_provenance,
        validated_scientific_entries,
    ) = v1._derive_current_batch(
        release_id=release_id,
        source_snapshot_id=source_snapshot_id,
        origin_git_commit=cache_execution_commit,
        completion_sha256=completion_sha256,
        completion_row=(
            _compatibility_completion_row(
                completion_row
            )
        ),
        evidence=(
            compatibility_evidence
        ),
    )

    del ignored_v1_provenance

    batch = v1._batch_id(
        evidence.batch_id
    )

    prefix = _provider_prefix(
        batch_id=batch,
        source_class=evidence.source_class,
        source_production_commit=(
            source_production_commit
        ),
        recovery_commit=(
            evidence.recovery_commit
        ),
    )

    provenance_base = {
        "accessions_sha256":
            completion_row[
                "accessions_sha256"
            ],
        "batch_id":
            batch,
        "cache_origin_completion_execution_commit":
            completion_execution_commit,
        "cache_origin_execution_commit":
            cache_execution_commit,
        "cache_origin_release_id":
            release_id,
        "cache_origin_source_production_commit":
            source_production_commit,
        "cache_origin_source_snapshot_id":
            source_snapshot_id,
        "candidate_audit":
            v1._artifact_reference(
                logical_path=(
                    prefix
                    + CANDIDATE_AUDIT_NAME
                ),
                payload=(
                    evidence.candidate_audit_payload
                ),
            ),
        "cause_evidence_sha256":
            evidence.cause_evidence_sha256,
        "component_audit":
            v1._artifact_reference(
                logical_path=(
                    prefix
                    + COMPONENT_AUDIT_NAME
                ),
                payload=(
                    evidence.component_audit_payload
                ),
            ),
        "origin_package_file_readback_sha256":
            completion_row[
                "package_file_readback_sha256"
            ],
        "origin_sequence_acquisition_completion_sha256":
            completion_sha256,
        "package_manifest":
            v1._artifact_reference(
                logical_path=(
                    prefix
                    + evidence.package_manifest_name
                ),
                payload=(
                    evidence.package_manifest_payload
                ),
            ),
        "provider_summary":
            v1._artifact_reference(
                logical_path=(
                    prefix
                    + evidence.provider_summary_name
                ),
                payload=(
                    evidence.provider_summary_payload
                ),
            ),
        "recovery_class":
            evidence.recovery_class,
        "recovery_commit":
            evidence.recovery_commit,
        "recovery_package_sha256":
            evidence.recovery_package_sha256,
        "recovery_summary_sha256":
            evidence.recovery_summary_sha256,
        "requested_accessions":
            completion_row[
                "requested_accessions"
            ],
        "source_batch_sha256":
            evidence.source_batch_sha256,
        "source_class":
            evidence.source_class,
        "source_package_sha256":
            evidence.source_package_sha256,
        "source_partial_name":
            evidence.source_partial_name,
        "transport_record_sha256":
            evidence.transport_record_sha256,
    }

    provenance_sha = hashlib.sha256(
        _batch_provenance_v2_payload(
            provenance_base
        )
    ).hexdigest()

    provenance = {
        **provenance_base,
        "batch_provenance_sha256":
            provenance_sha,
    }

    entries = []

    for validated in validated_scientific_entries:
        artifacts = []

        for artifact in validated[
            "package_artifacts"
        ]:
            package_path = artifact[
                "package_path"
            ]

            artifacts.append(
                {
                    "logical_path":
                        (
                            prefix
                            + "package/"
                            + package_path
                        ),
                    "package_path":
                        package_path,
                    "sha256":
                        artifact[
                            "sha256"
                        ],
                    "size_bytes":
                        artifact[
                            "size_bytes"
                        ],
                }
            )

        entry_base = {
            "biosample":
                validated[
                    "biosample"
                ],
            "canonical_genbank_assembly_accession":
                validated[
                    "canonical_genbank_assembly_accession"
                ],
            "origin_batch_provenance_sha256":
                provenance_sha,
            "origin_sequence_eligibility":
                validated[
                    "origin_sequence_eligibility"
                ],
            "origin_sequence_exclusion_reasons":
                validated[
                    "origin_sequence_exclusion_reasons"
                ],
            "package_artifacts":
                artifacts,
        }

        entries.append(
            {
                **entry_base,
                "entry_sha256":
                    hashlib.sha256(
                        _entry_v2_payload(
                            entry_base
                        )
                    ).hexdigest(),
            }
        )

    return (
        provenance,
        tuple(
            entries
        ),
    )


def _audit_previous_catalogue(
    payload: bytes,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "previous catalogue must be bytes"
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
        _fail(
            "invalid previous sequence-cache catalogue"
        )

    if not isinstance(
        value,
        dict,
    ):
        _fail(
            "previous sequence-cache catalogue is not an object"
        )

    schema = value.get(
        "schema_version"
    )

    if (
        schema
        == v1.MONTHLY_SEQUENCE_CACHE_CATALOGUE_SCHEMA
    ):
        try:
            return (
                v1.audit_sequence_cache_catalogue(
                    payload
                )
            )

        except Exception as exc:
            raise MonthlySequenceCacheCatalogueV2Error(
                "previous cache-v1 catalogue audit failed"
            ) from exc

    if (
        schema
        == MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA
    ):
        return (
            audit_sequence_cache_catalogue_v2(
                payload
            )
        )

    _fail(
        "previous sequence-cache catalogue schema is unsupported"
    )


def _audit_mixed_batch_provenance(
    value: object,
) -> dict[
    str,
    object,
]:
    if (
        isinstance(
            value,
            dict,
        )
        and "source_class" in value
    ):
        return (
            _audit_batch_provenance_v2_row(
                value
            )
        )

    try:
        return (
            v1._audit_batch_provenance_row(
                value
            )
        )

    except Exception as exc:
        raise MonthlySequenceCacheCatalogueV2Error(
            "legacy cache-v1 batch provenance audit failed"
        ) from exc


def _audit_mixed_entry(
    value: object,
    *,
    provenance_by_sha: Mapping[
        str,
        Mapping[
            str,
            object,
        ],
    ],
) -> dict[
    str,
    object,
]:
    if not isinstance(
        value,
        dict,
    ):
        _fail(
            "cache-v2 entry is not an object"
        )

    origin = value.get(
        "origin_batch_provenance_sha256"
    )

    provenance = provenance_by_sha.get(
        origin
    )

    if provenance is None:
        _fail(
            "cache-v2 entry references missing batch provenance"
        )

    if "source_class" in provenance:
        return (
            _audit_entry_v2(
                value,
                provenance_by_sha=(
                    provenance_by_sha
                ),
            )
        )

    try:
        return (
            v1._audit_entry(
                value,
                batch_id_by_provenance_sha={
                    digest:
                        row[
                            "batch_id"
                        ]
                    for (
                        digest,
                        row,
                    )
                    in provenance_by_sha.items()
                },
            )
        )

    except Exception as exc:
        raise MonthlySequenceCacheCatalogueV2Error(
            "legacy cache-v1 entry audit failed"
        ) from exc


def audit_sequence_cache_catalogue_v2(
    payload: bytes,
) -> dict[
    str,
    object,
]:
    """Audit one cache-v2 catalogue entirely from deterministic bytes."""

    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "sequence-cache catalogue v2 must be bytes"
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
        raise MonthlySequenceCacheCatalogueV2Error(
            "invalid sequence-cache catalogue v2 JSON"
        ) from exc

    if (
        not isinstance(
            value,
            dict,
        )
        or set(
            value
        )
        != _V2_CATALOGUE_KEYS
    ):
        _fail(
            "sequence-cache catalogue v2 schema changed"
        )

    if _canonical_json_bytes(
        value
    ) != payload:
        _fail(
            "sequence-cache catalogue v2 is not canonical JSON"
        )

    if (
        value[
            "schema_version"
        ]
        != MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA
    ):
        _fail(
            "sequence-cache catalogue v2 schema version changed"
        )

    if (
        value[
            "status"
        ]
        != MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_STATUS
    ):
        _fail(
            "sequence-cache catalogue v2 status changed"
        )

    release = v1._release_id(
        value[
            "release_id"
        ]
    )

    snapshot = v1._source_snapshot_id(
        value[
            "source_snapshot_id"
        ],
        release_id=release,
    )

    source_commit = v1._git_commit(
        value[
            "source_production_commit"
        ]
    )

    completion_commit = v1._git_commit(
        value[
            "completion_execution_commit"
        ]
    )

    cache_commit = v1._git_commit(
        value[
            "cache_execution_commit"
        ]
    )

    completion_sha = v1._sha256(
        value[
            "sequence_acquisition_completion_sha256"
        ],
        label="sequence-acquisition completion SHA256",
    )

    fresh_count = v1._nonnegative_int(
        value[
            "sequence_acquisition_fresh_count"
        ],
        label="sequence-acquisition fresh count",
    )

    source_class_counts_value = value[
        "sequence_acquisition_source_class_counts"
    ]

    if (
        not isinstance(
            source_class_counts_value,
            dict,
        )
        or set(
            source_class_counts_value
        )
        != {
            SOURCE_CLASS_FRESH,
            SOURCE_CLASS_FRESH_RECOVERY,
        }
    ):
        _fail(
            "sequence-acquisition source-class counts changed"
        )

    source_class_counts = {
        SOURCE_CLASS_FRESH:
            v1._nonnegative_int(
                source_class_counts_value[
                    SOURCE_CLASS_FRESH
                ],
                label="fresh batch count",
            ),
        SOURCE_CLASS_FRESH_RECOVERY:
            v1._nonnegative_int(
                source_class_counts_value[
                    SOURCE_CLASS_FRESH_RECOVERY
                ],
                label="fresh-recovery batch count",
            ),
    }

    mode = value[
        "catalogue_mode"
    ]

    previous_release = value[
        "previous_catalogue_release_id"
    ]

    previous_sha = value[
        "previous_catalogue_sha256"
    ]

    previous_count = v1._nonnegative_int(
        value[
            "previous_catalogue_entry_count"
        ],
        label="previous catalogue entry count",
    )

    if mode == GENESIS:
        if (
            previous_release is not None
            or previous_sha is not None
            or previous_count != 0
        ):
            _fail(
                "genesis cache-v2 catalogue contains "
                "previous-catalogue provenance"
            )

    elif mode == CHAINED:
        previous_release = v1._release_id(
            previous_release
        )

        previous_sha = v1._sha256(
            previous_sha,
            label="previous catalogue SHA256",
        )

        if (
            v1._release_ordinal(
                previous_release
            )
            >= v1._release_ordinal(
                release
            )
        ):
            _fail(
                "previous cache catalogue release "
                "is not earlier than current release"
            )

    else:
        _fail(
            "cache-v2 catalogue mode is invalid"
        )

    batch_values = value[
        "batch_provenance"
    ]

    if not isinstance(
        batch_values,
        list,
    ):
        _fail(
            "cache-v2 batch provenance must be a list"
        )

    batches = tuple(
        _audit_mixed_batch_provenance(
            item
        )
        for item in batch_values
    )

    batch_hashes = tuple(
        item[
            "batch_provenance_sha256"
        ]
        for item in batches
    )

    if batch_hashes != tuple(
        sorted(
            batch_hashes
        )
    ):
        _fail(
            "cache-v2 batch provenance is not sorted"
        )

    if len(
        batch_hashes
    ) != len(
        set(
            batch_hashes
        )
    ):
        _fail(
            "cache-v2 contains duplicate batch provenance"
        )

    batch_count = v1._nonnegative_int(
        value[
            "batch_provenance_count"
        ],
        label="cache-v2 batch-provenance count",
    )

    if batch_count != len(
        batches
    ):
        _fail(
            "cache-v2 batch-provenance count changed"
        )

    expected_batch_sha = hashlib.sha256(
        v1._canonical_list_payload(
            schema_version=(
                BATCH_PROVENANCE_SET_V2_SCHEMA
            ),
            field="batch_provenance",
            values=batches,
        )
    ).hexdigest()

    if (
        value[
            "batch_provenance_sha256"
        ]
        != expected_batch_sha
    ):
        _fail(
            "cache-v2 batch-provenance set SHA256 changed"
        )

    provenance_by_sha = {
        item[
            "batch_provenance_sha256"
        ]:
            item
        for item in batches
    }

    entry_values = value[
        "entries"
    ]

    if not isinstance(
        entry_values,
        list,
    ):
        _fail(
            "cache-v2 entries must be a list"
        )

    entries = tuple(
        _audit_mixed_entry(
            item,
            provenance_by_sha=(
                provenance_by_sha
            ),
        )
        for item in entry_values
    )

    accessions = tuple(
        item[
            "canonical_genbank_assembly_accession"
        ]
        for item in entries
    )

    if accessions != tuple(
        sorted(
            accessions
        )
    ):
        _fail(
            "cache-v2 entries are not sorted by accession"
        )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        _fail(
            "cache-v2 contains duplicate accessions"
        )

    referenced = {
        item[
            "origin_batch_provenance_sha256"
        ]
        for item in entries
    }

    if referenced != set(
        batch_hashes
    ):
        _fail(
            "cache-v2 batch provenance is missing, "
            "dangling, or unreferenced"
        )

    entry_count = v1._nonnegative_int(
        value[
            "catalogue_entry_count"
        ],
        label="cache-v2 catalogue entry count",
    )

    if entry_count != len(
        entries
    ):
        _fail(
            "cache-v2 catalogue entry count changed"
        )

    expected_entries_sha = hashlib.sha256(
        v1._canonical_list_payload(
            schema_version=(
                ENTRY_SET_V2_SCHEMA
            ),
            field="entries",
            values=entries,
        )
    ).hexdigest()

    if (
        value[
            "entries_sha256"
        ]
        != expected_entries_sha
    ):
        _fail(
            "cache-v2 entry-set SHA256 changed"
        )

    carried = v1._nonnegative_int(
        value[
            "carried_forward_entry_count"
        ],
        label="cache-v2 carried-forward count",
    )

    new = v1._nonnegative_int(
        value[
            "new_entry_count"
        ],
        label="cache-v2 new-entry count",
    )

    replaced = v1._nonnegative_int(
        value[
            "replaced_entry_count"
        ],
        label="cache-v2 replaced-entry count",
    )

    current = v1._nonnegative_int(
        value[
            "current_acquisition_count"
        ],
        label="cache-v2 current acquisition count",
    )

    if current != (
        new
        + replaced
    ):
        _fail(
            "cache-v2 current acquisition accounting changed"
        )

    if current != fresh_count:
        _fail(
            "cache-v2 current acquisition count "
            "differs from completion"
        )

    if previous_count != (
        carried
        + replaced
    ):
        _fail(
            "cache-v2 previous catalogue accounting changed"
        )

    if entry_count != (
        carried
        + new
        + replaced
    ):
        _fail(
            "cache-v2 merge accounting changed"
        )

    if (
        mode == GENESIS
        and (
            carried != 0
            or replaced != 0
        )
    ):
        _fail(
            "genesis cache-v2 catalogue cannot "
            "carry or replace previous entries"
        )

    current_batches = tuple(
        item
        for item in batches
        if (
            "source_class" in item
            and item[
                "origin_sequence_acquisition_completion_sha256"
            ]
            == completion_sha
        )
    )

    derived_source_class_counts = {
        SOURCE_CLASS_FRESH:
            sum(
                1
                for item in current_batches
                if item[
                    "source_class"
                ]
                == SOURCE_CLASS_FRESH
            ),
        SOURCE_CLASS_FRESH_RECOVERY:
            sum(
                1
                for item in current_batches
                if item[
                    "source_class"
                ]
                == SOURCE_CLASS_FRESH_RECOVERY
            ),
    }

    if (
        derived_source_class_counts
        != source_class_counts
    ):
        _fail(
            "cache-v2 current source-class counts changed"
        )

    return {
        "batch_provenance":
            list(
                batches
            ),
        "batch_provenance_count":
            batch_count,
        "batch_provenance_sha256":
            expected_batch_sha,
        "cache_execution_commit":
            cache_commit,
        "carried_forward_entry_count":
            carried,
        "catalogue_entry_count":
            entry_count,
        "catalogue_mode":
            mode,
        "completion_execution_commit":
            completion_commit,
        "current_acquisition_count":
            current,
        "entries":
            list(
                entries
            ),
        "entries_sha256":
            expected_entries_sha,
        "new_entry_count":
            new,
        "previous_catalogue_entry_count":
            previous_count,
        "previous_catalogue_release_id":
            previous_release,
        "previous_catalogue_sha256":
            previous_sha,
        "release_id":
            release,
        "replaced_entry_count":
            replaced,
        "schema_version":
            MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA,
        "sequence_acquisition_completion_sha256":
            completion_sha,
        "sequence_acquisition_fresh_count":
            fresh_count,
        "sequence_acquisition_source_class_counts":
            source_class_counts,
        "source_production_commit":
            source_commit,
        "source_snapshot_id":
            snapshot,
        "status":
            MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_STATUS,
    }


_COMPLETION_V2_TOP_LEVEL_KEYS = {
    "batches",
    "completed_accession_count",
    "completed_batch_count",
    "completion_execution_commit",
    "environment_explicit_sha256",
    "expected_batch_count",
    "fresh_acquisition_count",
    "fresh_batch_size",
    "schema_version",
    "source_class_counts",
    "source_production_commit",
    "source_snapshot_id",
    "source_snapshot_record_sha256",
    "stage2_fresh_target_manifest_sha256",
    "stage2_sequence_plan_record_sha256",
    "status",
}

_COMPLETION_V2_BATCH_KEYS = {
    "accessions_sha256",
    "batch_id",
    "batch_index",
    "batch_target_manifest_sha256",
    "candidate_sequence_audit_sha256",
    "cause_evidence_sha256",
    "component_sequence_audit_sha256",
    "first_accession",
    "last_accession",
    "package_file_readback_count",
    "package_file_readback_sha256",
    "package_files",
    "package_manifest_name",
    "package_manifest_sha256",
    "provider_summary_name",
    "provider_summary_sha256",
    "recovery_class",
    "recovery_commit",
    "recovery_package_sha256",
    "recovery_summary_sha256",
    "requested_accessions",
    "source_batch_sha256",
    "source_class",
    "source_package_sha256",
    "source_partial_name",
    "transport_record_sha256",
}


def _audit_completion_v2_payload_internal(
    payload: bytes,
) -> dict[
    str,
    object,
]:
    """
    Validate completion-v2 bytes without claiming upstream derived identity.

    The execution wrapper remains responsible for invoking the frozen
    completion-v2 derived-identity auditor with the complete Stage 2,
    source-snapshot, environment, and authoritative-provider context.
    """

    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "sequence-acquisition completion v2 must be bytes"
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
        raise MonthlySequenceCacheCatalogueV2Error(
            "sequence-acquisition completion v2 JSON is invalid"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        _fail(
            "sequence-acquisition completion v2 must be an object"
        )

    if (
        completion_v2._canonical_json_bytes(
            value
        )
        != payload
    ):
        _fail(
            "sequence-acquisition completion v2 is not canonical JSON"
        )

    if set(
        value
    ) != _COMPLETION_V2_TOP_LEVEL_KEYS:
        _fail(
            "sequence-acquisition completion v2 top-level schema changed"
        )

    if (
        value[
            "schema_version"
        ]
        != completion_v2
        .MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_V2_SCHEMA
    ):
        _fail(
            "sequence-acquisition completion v2 schema version changed"
        )

    if (
        value[
            "status"
        ]
        != completion_v2
        .MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_STATUS
    ):
        _fail(
            "sequence-acquisition completion v2 status changed"
        )

    snapshot = completion_v2._text(
        value[
            "source_snapshot_id"
        ],
        label="source snapshot ID",
    )

    snapshot_record_sha = completion_v2._sha256(
        value[
            "source_snapshot_record_sha256"
        ],
        label="source-snapshot-record SHA256",
    )

    source_commit = completion_v2._commit(
        value[
            "source_production_commit"
        ],
        label="source production commit",
    )

    completion_commit = completion_v2._commit(
        value[
            "completion_execution_commit"
        ],
        label="completion execution commit",
    )

    environment_sha = completion_v2._sha256(
        value[
            "environment_explicit_sha256"
        ],
        label="NCBI environment SHA256",
    )

    plan_sha = completion_v2._sha256(
        value[
            "stage2_sequence_plan_record_sha256"
        ],
        label="Stage 2 sequence-plan SHA256",
    )

    manifest_sha = completion_v2._sha256(
        value[
            "stage2_fresh_target_manifest_sha256"
        ],
        label="Stage 2 fresh-target manifest SHA256",
    )

    fresh_count = completion_v2._nonnegative_int(
        value[
            "fresh_acquisition_count"
        ],
        label="fresh-acquisition count",
    )

    fresh_batch_size = completion_v2._positive_int(
        value[
            "fresh_batch_size"
        ],
        label="fresh batch size",
    )

    if (
        fresh_batch_size
        != completion_v2.FRESH_BATCH_SIZE
    ):
        _fail(
            "sequence-acquisition completion v2 fresh batch size changed"
        )

    expected_batch_count = completion_v2._nonnegative_int(
        value[
            "expected_batch_count"
        ],
        label="expected batch count",
    )

    completed_batch_count = completion_v2._nonnegative_int(
        value[
            "completed_batch_count"
        ],
        label="completed batch count",
    )

    completed_accession_count = completion_v2._nonnegative_int(
        value[
            "completed_accession_count"
        ],
        label="completed accession count",
    )

    source_class_counts_value = value[
        "source_class_counts"
    ]

    if (
        not isinstance(
            source_class_counts_value,
            dict,
        )
        or set(
            source_class_counts_value
        )
        != {
            SOURCE_CLASS_FRESH,
            SOURCE_CLASS_FRESH_RECOVERY,
        }
    ):
        _fail(
            "sequence-acquisition completion v2 "
            "source-class count schema changed"
        )

    source_class_counts = {
        SOURCE_CLASS_FRESH:
            completion_v2._nonnegative_int(
                source_class_counts_value[
                    SOURCE_CLASS_FRESH
                ],
                label="fresh source-class count",
            ),
        SOURCE_CLASS_FRESH_RECOVERY:
            completion_v2._nonnegative_int(
                source_class_counts_value[
                    SOURCE_CLASS_FRESH_RECOVERY
                ],
                label="fresh-recovery source-class count",
            ),
    }

    batch_values = value[
        "batches"
    ]

    if not isinstance(
        batch_values,
        list,
    ):
        _fail(
            "sequence-acquisition completion v2 batches must be a list"
        )

    normalized_batches = []

    fresh_batches = 0
    recovery_batches = 0
    observed_accessions = 0

    for index, raw in enumerate(
        batch_values,
        1,
    ):
        if (
            not isinstance(
                raw,
                dict,
            )
            or set(
                raw
            )
            != _COMPLETION_V2_BATCH_KEYS
        ):
            _fail(
                "sequence-acquisition completion v2 "
                "batch-row schema changed"
            )

        batch_id = completion_v2._batch_id(
            raw[
                "batch_id"
            ]
        )

        expected_id = (
            completion_v2._expected_batch_id(
                index
            )
        )

        if batch_id != expected_id:
            _fail(
                "sequence-acquisition completion v2 "
                "batch ordering changed"
            )

        batch_index = completion_v2._positive_int(
            raw[
                "batch_index"
            ],
            label="batch index",
        )

        if batch_index != index:
            _fail(
                "sequence-acquisition completion v2 "
                "batch index changed"
            )

        requested = completion_v2._positive_int(
            raw[
                "requested_accessions"
            ],
            label="requested accession count",
        )

        first_accession = v1._accession(
            raw[
                "first_accession"
            ]
        )

        last_accession = v1._accession(
            raw[
                "last_accession"
            ]
        )

        batch_target_sha = completion_v2._sha256(
            raw[
                "batch_target_manifest_sha256"
            ],
            label="batch-target manifest SHA256",
        )

        accessions_sha = completion_v2._sha256(
            raw[
                "accessions_sha256"
            ],
            label="batch accessions SHA256",
        )

        candidate_sha = completion_v2._sha256(
            raw[
                "candidate_sequence_audit_sha256"
            ],
            label="candidate-sequence audit SHA256",
        )

        component_sha = completion_v2._sha256(
            raw[
                "component_sequence_audit_sha256"
            ],
            label="component-sequence audit SHA256",
        )

        package_file_count = completion_v2._positive_int(
            raw[
                "package_files"
            ],
            label="package-file count",
        )

        package_readback_count = completion_v2._positive_int(
            raw[
                "package_file_readback_count"
            ],
            label="package-file read-back count",
        )

        if (
            package_readback_count
            != package_file_count
        ):
            _fail(
                "sequence-acquisition completion v2 "
                "package read-back count changed"
            )

        package_readback_sha = completion_v2._sha256(
            raw[
                "package_file_readback_sha256"
            ],
            label="package-file read-back SHA256",
        )

        evidence = (
            completion_v2
            .AuthoritativeCompletedBatchEvidence(
                batch_id=batch_id,
                source_class=raw[
                    "source_class"
                ],
                recovery_class=raw[
                    "recovery_class"
                ],
                requested_accessions=requested,
                first_accession=first_accession,
                last_accession=last_accession,
                observed_batch_target_manifest_sha256=(
                    batch_target_sha
                ),
                observed_accessions_sha256=(
                    accessions_sha
                ),
                observed_candidate_audit_sha256=(
                    candidate_sha
                ),
                observed_component_audit_sha256=(
                    component_sha
                ),
                provider_summary_name=raw[
                    "provider_summary_name"
                ],
                provider_summary_sha256=raw[
                    "provider_summary_sha256"
                ],
                package_manifest_name=raw[
                    "package_manifest_name"
                ],
                package_manifest_sha256=raw[
                    "package_manifest_sha256"
                ],
                package_file_count=(
                    package_file_count
                ),
                package_file_readback_count=(
                    package_readback_count
                ),
                package_file_readback_sha256=(
                    package_readback_sha
                ),
                source_partial_name=raw[
                    "source_partial_name"
                ],
                recovery_commit=raw[
                    "recovery_commit"
                ],
                source_batch_sha256=raw[
                    "source_batch_sha256"
                ],
                source_package_sha256=raw[
                    "source_package_sha256"
                ],
                recovery_package_sha256=raw[
                    "recovery_package_sha256"
                ],
                recovery_summary_sha256=raw[
                    "recovery_summary_sha256"
                ],
                cause_evidence_sha256=raw[
                    "cause_evidence_sha256"
                ],
                transport_record_sha256=raw[
                    "transport_record_sha256"
                ],
            )
        )

        try:
            source = (
                completion_v2
                ._audit_source_class(
                    evidence
                )
            )

        except Exception as exc:
            raise MonthlySequenceCacheCatalogueV2Error(
                "sequence-acquisition completion v2 "
                "source-class audit failed"
            ) from exc

        if (
            source[
                "source_class"
            ]
            == SOURCE_CLASS_FRESH
        ):
            fresh_batches += 1

        elif (
            source[
                "source_class"
            ]
            == SOURCE_CLASS_FRESH_RECOVERY
        ):
            recovery_batches += 1

        else:
            _fail(
                "sequence-acquisition completion v2 "
                "source class changed"
            )

        observed_accessions += requested

        normalized_batches.append(
            {
                "accessions_sha256":
                    accessions_sha,
                "batch_id":
                    batch_id,
                "batch_index":
                    batch_index,
                "batch_target_manifest_sha256":
                    batch_target_sha,
                "candidate_sequence_audit_sha256":
                    candidate_sha,
                "cause_evidence_sha256":
                    source[
                        "cause_evidence_sha256"
                    ],
                "component_sequence_audit_sha256":
                    component_sha,
                "first_accession":
                    first_accession,
                "last_accession":
                    last_accession,
                "package_file_readback_count":
                    package_readback_count,
                "package_file_readback_sha256":
                    package_readback_sha,
                "package_files":
                    package_file_count,
                "package_manifest_name":
                    source[
                        "package_manifest_name"
                    ],
                "package_manifest_sha256":
                    source[
                        "package_manifest_sha256"
                    ],
                "provider_summary_name":
                    source[
                        "provider_summary_name"
                    ],
                "provider_summary_sha256":
                    source[
                        "provider_summary_sha256"
                    ],
                "recovery_class":
                    source[
                        "recovery_class"
                    ],
                "recovery_commit":
                    source[
                        "recovery_commit"
                    ],
                "recovery_package_sha256":
                    source[
                        "recovery_package_sha256"
                    ],
                "recovery_summary_sha256":
                    source[
                        "recovery_summary_sha256"
                    ],
                "requested_accessions":
                    requested,
                "source_batch_sha256":
                    source[
                        "source_batch_sha256"
                    ],
                "source_class":
                    source[
                        "source_class"
                    ],
                "source_package_sha256":
                    source[
                        "source_package_sha256"
                    ],
                "source_partial_name":
                    source[
                        "source_partial_name"
                    ],
                "transport_record_sha256":
                    source[
                        "transport_record_sha256"
                    ],
            }
        )

    if expected_batch_count != len(
        normalized_batches
    ):
        _fail(
            "sequence-acquisition completion v2 "
            "expected batch count changed"
        )

    if completed_batch_count != len(
        normalized_batches
    ):
        _fail(
            "sequence-acquisition completion v2 "
            "completed batch count changed"
        )

    if completed_accession_count != observed_accessions:
        _fail(
            "sequence-acquisition completion v2 "
            "completed accession count changed"
        )

    if fresh_count != observed_accessions:
        _fail(
            "sequence-acquisition completion v2 "
            "fresh-acquisition count changed"
        )

    derived_source_class_counts = {
        SOURCE_CLASS_FRESH:
            fresh_batches,
        SOURCE_CLASS_FRESH_RECOVERY:
            recovery_batches,
    }

    if (
        source_class_counts
        != derived_source_class_counts
    ):
        _fail(
            "sequence-acquisition completion v2 "
            "source-class counts changed"
        )

    return {
        "batches":
            normalized_batches,
        "completed_accession_count":
            completed_accession_count,
        "completed_batch_count":
            completed_batch_count,
        "completion_execution_commit":
            completion_commit,
        "environment_explicit_sha256":
            environment_sha,
        "expected_batch_count":
            expected_batch_count,
        "fresh_acquisition_count":
            fresh_count,
        "fresh_batch_size":
            fresh_batch_size,
        "schema_version":
            (
                completion_v2
                .MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_V2_SCHEMA
            ),
        "source_class_counts":
            source_class_counts,
        "source_production_commit":
            source_commit,
        "source_snapshot_id":
            snapshot,
        "source_snapshot_record_sha256":
            snapshot_record_sha,
        "stage2_fresh_target_manifest_sha256":
            manifest_sha,
        "stage2_sequence_plan_record_sha256":
            plan_sha,
        "status":
            (
                completion_v2
                .MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_STATUS
            ),
    }


def build_sequence_cache_catalogue_v2(
    *,
    release_id: str,
    source_snapshot_id: str,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    sequence_acquisition_completion_payload: bytes,
    current_batches: Sequence[
        AuthoritativeSequenceCacheBatchEvidenceV2
    ],
    previous_catalogue_payload: bytes | None = None,
) -> dict[
    str,
    object,
]:
    """Build one deterministic recovery-aware cumulative cache catalogue."""

    release = v1._release_id(
        release_id
    )

    snapshot = v1._source_snapshot_id(
        source_snapshot_id,
        release_id=release,
    )

    source_commit = v1._git_commit(
        source_production_commit
    )

    completion_commit = v1._git_commit(
        completion_execution_commit
    )

    cache_commit = v1._git_commit(
        cache_execution_commit
    )

    if not isinstance(
        sequence_acquisition_completion_payload,
        bytes,
    ):
        raise TypeError(
            "sequence-acquisition completion v2 must be bytes"
        )

    completion = (
        _audit_completion_v2_payload_internal(
            sequence_acquisition_completion_payload
        )
    )

    if (
        completion[
            "source_snapshot_id"
        ]
        != snapshot
    ):
        _fail(
            "completion-v2 source snapshot differs from cache"
        )

    if (
        completion[
            "source_production_commit"
        ]
        != source_commit
    ):
        _fail(
            "completion-v2 source production commit differs from cache"
        )

    if (
        completion[
            "completion_execution_commit"
        ]
        != completion_commit
    ):
        _fail(
            "completion-v2 execution commit differs from cache"
        )

    completion_sha = hashlib.sha256(
        sequence_acquisition_completion_payload
    ).hexdigest()

    evidence_values = tuple(
        current_batches
    )

    completion_rows = tuple(
        completion[
            "batches"
        ]
    )

    if len(
        evidence_values
    ) != len(
        completion_rows
    ):
        _fail(
            "cache-v2 current batch population differs from completion"
        )

    current_provenance = []
    current_entries = []

    for (
        evidence,
        completion_row,
    ) in zip(
        evidence_values,
        completion_rows,
        strict=True,
    ):
        provenance, entries = (
            _derive_current_batch_v2(
                release_id=release,
                source_snapshot_id=snapshot,
                source_production_commit=(
                    source_commit
                ),
                completion_execution_commit=(
                    completion_commit
                ),
                cache_execution_commit=(
                    cache_commit
                ),
                completion_sha256=(
                    completion_sha
                ),
                completion_row=(
                    completion_row
                ),
                evidence=(
                    evidence
                ),
            )
        )

        current_provenance.append(
            provenance
        )

        current_entries.extend(
            entries
        )

    if len(
        current_entries
    ) != completion[
        "fresh_acquisition_count"
    ]:
        _fail(
            "cache-v2 derived current population "
            "differs from completion fresh-acquisition count"
        )

    current_accessions = tuple(
        item[
            "canonical_genbank_assembly_accession"
        ]
        for item in current_entries
    )

    if len(
        current_accessions
    ) != len(
        set(
            current_accessions
        )
    ):
        _fail(
            "cache-v2 current population contains duplicate accessions"
        )

    derived_source_class_counts = {
        SOURCE_CLASS_FRESH:
            sum(
                1
                for item in current_provenance
                if item[
                    "source_class"
                ]
                == SOURCE_CLASS_FRESH
            ),
        SOURCE_CLASS_FRESH_RECOVERY:
            sum(
                1
                for item in current_provenance
                if item[
                    "source_class"
                ]
                == SOURCE_CLASS_FRESH_RECOVERY
            ),
    }

    if (
        derived_source_class_counts
        != completion[
            "source_class_counts"
        ]
    ):
        _fail(
            "cache-v2 source-class population differs from completion"
        )

    if previous_catalogue_payload is None:
        mode = GENESIS

        previous_sha = None
        previous_release = None

        previous_entries = ()
        previous_batches = ()

    else:
        previous_record = (
            _audit_previous_catalogue(
                previous_catalogue_payload
            )
        )

        previous_release = (
            previous_record[
                "release_id"
            ]
        )

        if (
            v1._release_ordinal(
                previous_release
            )
            >= v1._release_ordinal(
                release
            )
        ):
            _fail(
                "previous cache catalogue release "
                "is not earlier than current release"
            )

        mode = CHAINED

        previous_sha = hashlib.sha256(
            previous_catalogue_payload
        ).hexdigest()

        previous_entries = tuple(
            previous_record[
                "entries"
            ]
        )

        previous_batches = tuple(
            previous_record[
                "batch_provenance"
            ]
        )

    previous_by_accession = {
        entry[
            "canonical_genbank_assembly_accession"
        ]:
            entry
        for entry in previous_entries
    }

    if len(
        previous_by_accession
    ) != len(
        previous_entries
    ):
        raise RuntimeError(
            "audited previous catalogue contained duplicate accessions"
        )

    current_by_accession = {
        entry[
            "canonical_genbank_assembly_accession"
        ]:
            entry
        for entry in current_entries
    }

    replaced_accessions = (
        set(
            previous_by_accession
        )
        & set(
            current_by_accession
        )
    )

    new_accessions = (
        set(
            current_by_accession
        )
        - set(
            previous_by_accession
        )
    )

    carried_accessions = (
        set(
            previous_by_accession
        )
        - set(
            current_by_accession
        )
    )

    merged_entries = tuple(
        sorted(
            (
                *(
                    previous_by_accession[
                        accession
                    ]
                    for accession
                    in carried_accessions
                ),
                *current_by_accession.values(),
            ),
            key=lambda item:
                item[
                    "canonical_genbank_assembly_accession"
                ],
        )
    )

    provenance_by_sha = {}

    for row in (
        *previous_batches,
        *current_provenance,
    ):
        digest = row[
            "batch_provenance_sha256"
        ]

        existing = provenance_by_sha.get(
            digest
        )

        if (
            existing is not None
            and existing != row
        ):
            _fail(
                "cache-v2 batch-provenance SHA256 collision "
                "has inconsistent content"
            )

        provenance_by_sha[
            digest
        ] = row

    referenced_provenance = {
        entry[
            "origin_batch_provenance_sha256"
        ]
        for entry in merged_entries
    }

    missing_provenance = (
        referenced_provenance
        - set(
            provenance_by_sha
        )
    )

    if missing_provenance:
        _fail(
            "merged cache-v2 entry lacks batch provenance"
        )

    merged_batches = tuple(
        sorted(
            (
                provenance_by_sha[
                    digest
                ]
                for digest
                in referenced_provenance
            ),
            key=lambda item:
                item[
                    "batch_provenance_sha256"
                ],
        )
    )

    batch_set_sha = hashlib.sha256(
        v1._canonical_list_payload(
            schema_version=(
                BATCH_PROVENANCE_SET_V2_SCHEMA
            ),
            field="batch_provenance",
            values=merged_batches,
        )
    ).hexdigest()

    entry_set_sha = hashlib.sha256(
        v1._canonical_list_payload(
            schema_version=(
                ENTRY_SET_V2_SCHEMA
            ),
            field="entries",
            values=merged_entries,
        )
    ).hexdigest()

    record = {
        "batch_provenance":
            list(
                merged_batches
            ),
        "batch_provenance_count":
            len(
                merged_batches
            ),
        "batch_provenance_sha256":
            batch_set_sha,
        "cache_execution_commit":
            cache_commit,
        "carried_forward_entry_count":
            len(
                carried_accessions
            ),
        "catalogue_entry_count":
            len(
                merged_entries
            ),
        "catalogue_mode":
            mode,
        "completion_execution_commit":
            completion_commit,
        "current_acquisition_count":
            len(
                current_entries
            ),
        "entries":
            list(
                merged_entries
            ),
        "entries_sha256":
            entry_set_sha,
        "new_entry_count":
            len(
                new_accessions
            ),
        "previous_catalogue_entry_count":
            len(
                previous_entries
            ),
        "previous_catalogue_release_id":
            previous_release,
        "previous_catalogue_sha256":
            previous_sha,
        "release_id":
            release,
        "replaced_entry_count":
            len(
                replaced_accessions
            ),
        "schema_version":
            MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA,
        "sequence_acquisition_completion_sha256":
            completion_sha,
        "sequence_acquisition_fresh_count":
            completion[
                "fresh_acquisition_count"
            ],
        "sequence_acquisition_source_class_counts":
            dict(
                completion[
                    "source_class_counts"
                ]
            ),
        "source_production_commit":
            source_commit,
        "source_snapshot_id":
            snapshot,
        "status":
            MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_STATUS,
    }

    audit_sequence_cache_catalogue_v2(
        _canonical_json_bytes(
            record
        )
    )

    return record


def serialize_sequence_cache_catalogue_v2(
    **kwargs,
) -> bytes:
    """Build and serialize one deterministic cache-v2 catalogue."""

    return _canonical_json_bytes(
        build_sequence_cache_catalogue_v2(
            **kwargs
        )
    )
