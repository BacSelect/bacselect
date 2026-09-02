"""Prospective recovery validation for post-snapshot assembly supersession."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping, Sequence

from bacselect.monthly_sequence_validation import (
    CANONICAL_GCA_RE,
    MonthlyFreshAcquisitionTarget,
    MonthlySequenceValidationError,
    MonthlyValidatedPackage,
    package_file_manifest,
    sha256_file,
    validate_candidate_payload,
    validate_metadata,
)


FAILURE_CLASS = (
    "post_snapshot_accession_supersession"
)

SUPERSESSION_EVIDENCE_FIELDS = (
    "canonical_genbank_assembly_accession",
    "expected_biosample",
    "snapshot_biosample",
    "snapshot_assembly_status",
    "snapshot_current_accession",
    "snapshot_assembly_level",
    "acquisition_biosample",
    "acquisition_assembly_status",
    "acquisition_current_accession",
    "acquisition_assembly_level",
    "source_snapshot_report_sha256",
    "acquisition_report_sha256",
    "classification",
)


class MonthlyPostSnapshotSupersessionRecoveryError(
    RuntimeError
):
    """Raised when a package is outside the frozen supersession contract."""


@dataclass(frozen=True)
class PostSnapshotSupersessionClassification:
    snapshot_report: Path
    acquisition_report: Path
    snapshot_report_sha256: str
    acquisition_report_sha256: str
    affected_accessions: tuple[str, ...]
    evidence_rows: tuple[
        Mapping[str, str],
        ...,
    ]
    corrected_metadata_records: tuple[
        Mapping[str, object],
        ...,
    ]


@dataclass(frozen=True)
class MonthlyPostSnapshotSupersessionValidatedPackage:
    validated_package: MonthlyValidatedPackage
    supersession_rows: tuple[
        Mapping[str, str],
        ...,
    ]


def _fail(
    message: str,
) -> None:
    raise MonthlyPostSnapshotSupersessionRecoveryError(
        message
    )


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
        _fail(
            f"{label} is not a regular file: "
            f"{value}"
        )

    return value


def _read_jsonl(
    path: Path,
    *,
    label: str,
) -> tuple[
    Mapping[str, object],
    ...,
]:
    source = _require_regular_file(
        path,
        label=label,
    )

    rows = []

    with source.open(
        "r",
        encoding="utf-8",
    ) as handle:
        for line_number, line in enumerate(
            handle,
            1,
        ):
            if not line.strip():
                _fail(
                    f"{label} contains blank JSONL "
                    f"line {line_number}"
                )

            try:
                row = json.loads(
                    line
                )
            except json.JSONDecodeError as exc:
                raise MonthlyPostSnapshotSupersessionRecoveryError(
                    f"{label} contains invalid JSONL "
                    f"line {line_number}"
                ) from exc

            if not isinstance(
                row,
                dict,
            ):
                _fail(
                    f"{label} line {line_number} "
                    "is not a JSON object"
                )

            rows.append(
                row
            )

    if not rows:
        _fail(
            f"{label} contains no records"
        )

    return tuple(
        rows
    )


def _value(
    obj: Mapping[
        str,
        object,
    ],
    *names: str,
) -> object:
    for name in names:
        if name in obj:
            return obj[
                name
            ]

    return None


def _metadata_identity(
    row: Mapping[
        str,
        object,
    ],
    *,
    label: str,
) -> Mapping[str, str]:
    accession_obj = _value(
        row,
        "accession",
    )

    accession = (
        accession_obj
        if isinstance(
            accession_obj,
            str,
        )
        else ""
    )

    if CANONICAL_GCA_RE.fullmatch(
        accession
    ) is None:
        _fail(
            f"{label} has invalid assembly "
            f"accession {accession_obj!r}"
        )

    info_obj = (
        row.get(
            "assemblyInfo"
        )
        or row.get(
            "assembly_info"
        )
        or {}
    )

    if not isinstance(
        info_obj,
        Mapping,
    ):
        _fail(
            f"{label} {accession}: malformed "
            "assemblyInfo"
        )

    biosample_obj = (
        info_obj.get(
            "biosample"
        )
        or {}
    )

    if not isinstance(
        biosample_obj,
        Mapping,
    ):
        _fail(
            f"{label} {accession}: malformed "
            "BioSample metadata"
        )

    status = _value(
        info_obj,
        "assemblyStatus",
        "assembly_status",
    )

    current = _value(
        row,
        "currentAccession",
        "current_accession",
    )

    level = _value(
        info_obj,
        "assemblyLevel",
        "assembly_level",
    )

    biosample = _value(
        biosample_obj,
        "accession",
    )

    return {
        "accession":
            accession,
        "assembly_status":
            str(status)
            if status is not None
            else "",
        "current_accession":
            str(current)
            if current is not None
            else "",
        "assembly_level":
            str(level)
            if level is not None
            else "",
        "biosample":
            str(biosample)
            if biosample is not None
            else "",
    }


def _target_values(
    targets: Sequence[
        MonthlyFreshAcquisitionTarget
    ],
) -> tuple[
    MonthlyFreshAcquisitionTarget,
    ...,
]:
    values = tuple(
        targets
    )

    if not values:
        _fail(
            "supersession recovery requires "
            "at least one target"
        )

    accessions = []

    for target in values:
        if not isinstance(
            target,
            MonthlyFreshAcquisitionTarget,
        ):
            _fail(
                "supersession target has wrong type"
            )

        accession = (
            target
            .canonical_genbank_assembly_accession
        )

        if CANONICAL_GCA_RE.fullmatch(
            accession
        ) is None:
            _fail(
                "supersession target has invalid "
                f"accession {accession!r}"
            )

        accessions.append(
            accession
        )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        _fail(
            "supersession targets contain "
            "duplicate accessions"
        )

    return values


def _index_snapshot_records(
    rows: Sequence[
        Mapping[str, object]
    ],
    *,
    expected_accessions: set[str],
) -> Mapping[
    str,
    Mapping[str, object],
]:
    selected = {}

    for row in rows:
        accession_obj = _value(
            row,
            "accession",
        )

        if not isinstance(
            accession_obj,
            str,
        ):
            continue

        if accession_obj not in expected_accessions:
            continue

        if accession_obj in selected:
            _fail(
                "frozen source snapshot contains "
                "duplicate target accession "
                f"{accession_obj}"
            )

        selected[
            accession_obj
        ] = row

    missing = sorted(
        expected_accessions
        - set(
            selected
        )
    )

    if missing:
        _fail(
            "frozen source snapshot is missing "
            f"target accessions: {missing!r}"
        )

    return selected


def _index_acquisition_records(
    rows: Sequence[
        Mapping[str, object]
    ],
    *,
    expected_accessions: set[str],
) -> Mapping[
    str,
    Mapping[str, object],
]:
    selected = {}

    for row in rows:
        identity = _metadata_identity(
            row,
            label="acquisition metadata",
        )

        accession = identity[
            "accession"
        ]

        if accession in selected:
            _fail(
                "acquisition metadata contains "
                "duplicate accession "
                f"{accession}"
            )

        selected[
            accession
        ] = row

    observed = set(
        selected
    )

    if observed != expected_accessions:
        _fail(
            "acquisition metadata does not "
            "exactly match frozen batch targets; "
            f"missing={sorted(expected_accessions - observed)!r}; "
            f"extra={sorted(observed - expected_accessions)!r}"
        )

    return selected


def classify_post_snapshot_supersession(
    *,
    package: Path,
    source_snapshot_report: Path,
    targets: Sequence[
        MonthlyFreshAcquisitionTarget
    ],
) -> PostSnapshotSupersessionClassification:
    target_values = _target_values(
        targets
    )

    expected_biosamples = {
        target.canonical_genbank_assembly_accession:
            target.source_biosample
        for target in target_values
    }

    expected_accessions = set(
        expected_biosamples
    )

    snapshot_report = _require_regular_file(
        Path(
            source_snapshot_report
        ),
        label="frozen source snapshot report",
    )

    acquisition_report = _require_regular_file(
        Path(
            package
        )
        / "ncbi_dataset"
        / "data"
        / "assembly_data_report.jsonl",
        label="acquisition assembly report",
    )

    snapshot_sha = sha256_file(
        snapshot_report
    )

    acquisition_sha = sha256_file(
        acquisition_report
    )

    snapshot_records = (
        _index_snapshot_records(
            _read_jsonl(
                snapshot_report,
                label="frozen source snapshot report",
            ),
            expected_accessions=(
                expected_accessions
            ),
        )
    )

    acquisition_records = (
        _index_acquisition_records(
            _read_jsonl(
                acquisition_report,
                label="acquisition assembly report",
            ),
            expected_accessions=(
                expected_accessions
            ),
        )
    )

    affected = []
    evidence_rows = []
    corrected_records = []

    for target in target_values:
        accession = (
            target
            .canonical_genbank_assembly_accession
        )

        expected_biosample = (
            target.source_biosample
        )

        snapshot_row = (
            snapshot_records[
                accession
            ]
        )

        acquisition_row = (
            acquisition_records[
                accession
            ]
        )

        snapshot = _metadata_identity(
            snapshot_row,
            label="frozen source snapshot",
        )

        acquisition = _metadata_identity(
            acquisition_row,
            label="acquisition metadata",
        )

        if (
            snapshot[
                "assembly_status"
            ]
            != "current"
            or snapshot[
                "current_accession"
            ]
            != accession
            or snapshot[
                "assembly_level"
            ]
            != "Complete Genome"
            or snapshot[
                "biosample"
            ]
            != expected_biosample
        ):
            _fail(
                f"{accession}: frozen source "
                "snapshot is not an exact "
                "current Complete Genome match "
                "to the frozen target"
            )

        ordinary = (
            acquisition[
                "assembly_status"
            ]
            == "current"
            and acquisition[
                "current_accession"
            ]
            == accession
            and acquisition[
                "assembly_level"
            ]
            == "Complete Genome"
            and acquisition[
                "biosample"
            ]
            == expected_biosample
        )

        superseded = (
            acquisition[
                "assembly_status"
            ]
            == "previous"
            and acquisition[
                "current_accession"
            ]
            != accession
            and CANONICAL_GCA_RE.fullmatch(
                acquisition[
                    "current_accession"
                ]
            )
            is not None
            and acquisition[
                "assembly_level"
            ]
            == "Complete Genome"
            and acquisition[
                "biosample"
            ]
            == expected_biosample
        )

        if ordinary:
            corrected_records.append(
                acquisition_row
            )
            continue

        if not superseded:
            _fail(
                f"{accession}: acquisition "
                "metadata changed outside the "
                "post-snapshot supersession "
                "failure class; "
                f"status={acquisition['assembly_status']!r}; "
                f"current_accession="
                f"{acquisition['current_accession']!r}; "
                f"assembly_level="
                f"{acquisition['assembly_level']!r}; "
                f"biosample="
                f"{acquisition['biosample']!r}"
            )

        affected.append(
            accession
        )

        evidence_rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "expected_biosample":
                    expected_biosample,
                "snapshot_biosample":
                    snapshot[
                        "biosample"
                    ],
                "snapshot_assembly_status":
                    snapshot[
                        "assembly_status"
                    ],
                "snapshot_current_accession":
                    snapshot[
                        "current_accession"
                    ],
                "snapshot_assembly_level":
                    snapshot[
                        "assembly_level"
                    ],
                "acquisition_biosample":
                    acquisition[
                        "biosample"
                    ],
                "acquisition_assembly_status":
                    acquisition[
                        "assembly_status"
                    ],
                "acquisition_current_accession":
                    acquisition[
                        "current_accession"
                    ],
                "acquisition_assembly_level":
                    acquisition[
                        "assembly_level"
                    ],
                "source_snapshot_report_sha256":
                    snapshot_sha,
                "acquisition_report_sha256":
                    acquisition_sha,
                "classification":
                    FAILURE_CLASS,
            }
        )

        # Validation-only correction:
        # use the frozen snapshot metadata record for this exact
        # frozen accession. No successor accession is introduced.
        corrected_records.append(
            snapshot_row
        )

    if not affected:
        _fail(
            "batch contains no post-snapshot "
            "supersession target"
        )

    if sha256_file(
        snapshot_report
    ) != snapshot_sha:
        _fail(
            "frozen source snapshot report "
            "changed during classification"
        )

    if sha256_file(
        acquisition_report
    ) != acquisition_sha:
        _fail(
            "acquisition assembly report "
            "changed during classification"
        )

    return PostSnapshotSupersessionClassification(
        snapshot_report=(
            snapshot_report
        ),
        acquisition_report=(
            acquisition_report
        ),
        snapshot_report_sha256=(
            snapshot_sha
        ),
        acquisition_report_sha256=(
            acquisition_sha
        ),
        affected_accessions=tuple(
            affected
        ),
        evidence_rows=tuple(
            evidence_rows
        ),
        corrected_metadata_records=tuple(
            corrected_records
        ),
    )


def serialize_supersession_evidence(
    rows: Sequence[
        Mapping[str, str]
    ],
) -> bytes:
    values = tuple(
        rows
    )

    if not values:
        _fail(
            "supersession evidence is empty"
        )

    output = io.StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        output,
        fieldnames=(
            SUPERSESSION_EVIDENCE_FIELDS
        ),
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )

    writer.writeheader()

    for row in values:
        writer.writerow(
            {
                field:
                    row[
                        field
                    ]
                for field
                in SUPERSESSION_EVIDENCE_FIELDS
            }
        )

    return output.getvalue().encode(
        "utf-8"
    )


def _write_corrected_metadata_view(
    *,
    root: Path,
    records: Sequence[
        Mapping[str, object]
    ],
) -> Path:
    package = (
        root
        / "validation-package"
    )

    data_root = (
        package
        / "ncbi_dataset"
        / "data"
    )

    data_root.mkdir(
        parents=True
    )

    report = (
        data_root
        / "assembly_data_report.jsonl"
    )

    with report.open(
        "x",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        for record in records:
            handle.write(
                json.dumps(
                    record,
                    sort_keys=True,
                    separators=(
                        ",",
                        ":",
                    ),
                    ensure_ascii=True,
                )
            )
            handle.write(
                "\n"
            )

    return package


def validate_post_snapshot_supersession_package(
    *,
    package: Path,
    source_snapshot_report: Path,
    targets: Sequence[
        MonthlyFreshAcquisitionTarget
    ],
) -> MonthlyPostSnapshotSupersessionValidatedPackage:
    target_values = _target_values(
        targets
    )

    package_path = Path(
        package
    )

    data_root = (
        package_path
        / "ncbi_dataset"
        / "data"
    )

    if (
        data_root.is_symlink()
        or not data_root.is_dir()
    ):
        _fail(
            "recovery package lacks real "
            "ncbi_dataset/data directory"
        )

    classification = (
        classify_post_snapshot_supersession(
            package=package_path,
            source_snapshot_report=(
                source_snapshot_report
            ),
            targets=target_values,
        )
    )

    with tempfile.TemporaryDirectory(
        prefix=(
            "bacselect-supersession-"
            "metadata-validation-"
        )
    ) as temporary:
        temporary_root = Path(
            temporary
        )

        validation_package = (
            _write_corrected_metadata_view(
                root=temporary_root,
                records=(
                    classification
                    .corrected_metadata_records
                ),
            )
        )

        try:
            (
                _,
                observed_biosamples,
                _,
            ) = validate_metadata(
                validation_package,
                target_values,
            )
        except MonthlySequenceValidationError as exc:
            raise MonthlyPostSnapshotSupersessionRecoveryError(
                "validation-only frozen metadata "
                "view failed ordinary monthly "
                "metadata validation"
            ) from exc

    candidate_rows = []
    component_rows = []

    for target in target_values:
        accession = (
            target
            .canonical_genbank_assembly_accession
        )

        try:
            (
                candidate,
                components,
            ) = validate_candidate_payload(
                data_root,
                target,
                observed_biosamples[
                    accession
                ],
            )
        except MonthlySequenceValidationError as exc:
            raise MonthlyPostSnapshotSupersessionRecoveryError(
                f"{accession}: recovered package "
                "failed unchanged monthly "
                "scientific validation"
            ) from exc

        candidate_rows.append(
            candidate
        )

        component_rows.extend(
            components
        )

    expected_order = tuple(
        target
        .canonical_genbank_assembly_accession
        for target
        in target_values
    )

    observed_order = tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row
        in candidate_rows
    )

    if observed_order != expected_order:
        _fail(
            "recovered candidate audit does not "
            "preserve frozen target order"
        )

    if sha256_file(
        classification.snapshot_report
    ) != classification.snapshot_report_sha256:
        _fail(
            "frozen source snapshot report "
            "changed during package validation"
        )

    if sha256_file(
        classification.acquisition_report
    ) != classification.acquisition_report_sha256:
        _fail(
            "acquisition assembly report "
            "changed during package validation"
        )

    validated = MonthlyValidatedPackage(
        candidate_rows=tuple(
            candidate_rows
        ),
        component_rows=tuple(
            component_rows
        ),
        package_file_rows=(
            package_file_manifest(
                package_path
            )
        ),
        assembly_data_report=(
            classification
            .acquisition_report
        ),
    )

    return MonthlyPostSnapshotSupersessionValidatedPackage(
        validated_package=(
            validated
        ),
        supersession_rows=(
            classification
            .evidence_rows
        ),
    )
