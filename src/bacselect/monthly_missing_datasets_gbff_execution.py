"""Execution layer for prospectively frozen missing-Datasets-GBFF recovery."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Callable
from typing import Mapping
from typing import Sequence
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from bacselect import monthly_missing_datasets_gbff_recovery as recovery
from bacselect import monthly_sequence_recovery_authority as authority
from bacselect import monthly_sequence_validation as monthly


FAILURE_CLASS = "datasets_manifest_omits_requested_gbff"

RECOVERY_EVIDENCE_NAME = (
    "missing-datasets-gbff-recovery-evidence.json"
)

SOURCE_ZIP_FETCH_MEMBER = (
    "ncbi_dataset/fetch.txt"
)

EFETCH_CHUNK_SIZE = 100
EFETCH_RETRY_ROUNDS = 3
EFETCH_RETRY_DELAY_SECONDS = 3.0
EFETCH_REQUEST_INTERVAL_SECONDS = 0.4
EFETCH_TIMEOUT_SECONDS = 120

EFETCH_TOOL = "bacselect"


class MonthlyMissingDatasetsGbffExecutionError(
    RuntimeError
):
    """Raised when missing-GBFF execution evidence fails closed."""


@dataclass(
    frozen=True,
)
class SourceFetchContract:
    dehydrated_zip_sha256: str
    extracted_fetch_sha256: str
    zip_fetch_sha256: str
    zip_fetch_member: str


@dataclass(
    frozen=True,
)
class FinalizedMissingDatasetsGbffRecovery:
    batch_id: str
    batch_dir: Path
    source_partial_dir: Path
    recovery_commit: str
    recovery_summary_sha256: str
    recovery_evidence_sha256: str
    recovery_accessions: tuple[
        str,
        ...,
    ]


def _fail(
    message: str,
) -> None:
    raise MonthlyMissingDatasetsGbffExecutionError(
        message
    )


def _targets(
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
) -> tuple[
    monthly.MonthlyFreshAcquisitionTarget,
    ...,
]:
    values = tuple(
        targets
    )

    if not values:
        _fail(
            "recovery target population is empty"
        )

    accessions: list[
        str
    ] = []

    for target in values:
        if not isinstance(
            target,
            monthly.MonthlyFreshAcquisitionTarget,
        ):
            raise TypeError(
                "recovery target has wrong type"
            )

        accession = (
            target
            .canonical_genbank_assembly_accession
        )

        if (
            not isinstance(
                accession,
                str,
            )
            or monthly.CANONICAL_GCA_RE.fullmatch(
                accession
            )
            is None
        ):
            _fail(
                "recovery target accession is not "
                f"canonical GCA accession.version: "
                f"{accession!r}"
            )

        accessions.append(
            accession
        )

    if len(
        set(
            accessions
        )
    ) != len(
        accessions
    ):
        _fail(
            "recovery target population contains "
            "duplicate accessions"
        )

    return values


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    if (
        value.is_symlink()
        or not value.is_dir()
    ):
        _fail(
            f"{label} is not a real directory: "
            f"{value}"
        )

    return value


def _require_regular_file(
    path: Path,
    *,
    label: str,
    nonempty: bool = True,
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

    if (
        nonempty
        and value.stat().st_size <= 0
    ):
        _fail(
            f"{label} is empty: {value}"
        )

    return value


def _canonical_json_bytes(
    payload: Mapping[
        str,
        object,
    ],
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def _serialize_tsv(
    *,
    fields: Sequence[str],
    rows: Sequence[
        Mapping[
            str,
            str,
        ]
    ],
) -> bytes:
    handle = io.StringIO(
        newline="",
    )

    writer = csv.DictWriter(
        handle,
        fieldnames=list(
            fields
        ),
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )

    writer.writeheader()

    for row in rows:
        writer.writerow(
            row
        )

    return handle.getvalue().encode(
        "utf-8"
    )


def _write_new_file(
    path: Path,
    payload: bytes,
) -> None:
    value = Path(
        path
    )

    if os.path.lexists(
        value
    ):
        _fail(
            "refusing to overwrite recovery "
            f"evidence: {value}"
        )

    with value.open(
        "xb"
    ) as handle:
        handle.write(
            payload
        )
        handle.flush()
        os.fsync(
            handle.fileno()
        )


def _write_partial_file(
    final_path: Path,
    payload: bytes,
) -> Path:
    final = Path(
        final_path
    )

    partial = final.with_name(
        final.name
        + ".partial"
    )

    for path in (
        final,
        partial,
    ):
        if os.path.lexists(
            path
        ):
            _fail(
                "refusing to overwrite EFetch "
                f"evidence: {path}"
            )

    with partial.open(
        "xb"
    ) as handle:
        handle.write(
            payload
        )
        handle.flush()
        os.fsync(
            handle.fileno()
        )

    return partial


def _utc_now() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .replace(
            microsecond=0
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def _batch_id_from_dir(
    batch_dir: Path,
) -> str:
    name = Path(
        batch_dir
    ).name

    if name.endswith(
        ".partial"
    ):
        name = name[
            :-len(
                ".partial"
            )
        ]

    if (
        not name.startswith(
            "batch-"
        )
        or len(
            name
        ) != len(
            "batch-00000"
        )
        or not name[
            len(
                "batch-"
            ):
        ].isdigit()
    ):
        _fail(
            f"invalid recovery batch directory name: "
            f"{Path(batch_dir).name!r}"
        )

    return name


def _validate_source_fetch_contract(
    source_partial_dir: Path,
) -> SourceFetchContract:
    source = _require_real_directory(
        source_partial_dir,
        label="source partial",
    )

    dehydrated = _require_regular_file(
        source
        / "dehydrated.zip",
        label="source dehydrated ZIP",
    )

    extracted_fetch = _require_regular_file(
        source
        / authority.PACKAGE_NAME
        / "ncbi_dataset"
        / "fetch.txt",
        label="extracted source fetch manifest",
    )

    try:
        with zipfile.ZipFile(
            dehydrated,
            "r",
        ) as archive:
            matching = [
                item
                for item
                in archive.infolist()
                if item.filename
                == SOURCE_ZIP_FETCH_MEMBER
            ]

            if len(
                matching
            ) != 1:
                _fail(
                    "source dehydrated ZIP must "
                    "contain exactly one "
                    f"{SOURCE_ZIP_FETCH_MEMBER!r}; "
                    f"observed {len(matching)}"
                )

            zip_fetch = archive.read(
                matching[
                    0
                ]
            )

    except (
        zipfile.BadZipFile,
        KeyError,
        OSError,
    ) as exc:
        raise MonthlyMissingDatasetsGbffExecutionError(
            "source dehydrated ZIP could not "
            "be audited"
        ) from exc

    extracted = extracted_fetch.read_bytes()

    if zip_fetch != extracted:
        _fail(
            "source dehydrated ZIP fetch.txt "
            "differs from extracted package fetch.txt"
        )

    return SourceFetchContract(
        dehydrated_zip_sha256=(
            monthly.sha256_file(
                dehydrated
            )
        ),
        extracted_fetch_sha256=(
            hashlib.sha256(
                extracted
            ).hexdigest()
        ),
        zip_fetch_sha256=(
            hashlib.sha256(
                zip_fetch
            ).hexdigest()
        ),
        zip_fetch_member=(
            SOURCE_ZIP_FETCH_MEMBER
        ),
    )


def _gbff_record_versions(
    path: Path,
) -> tuple[
    str,
    ...,
]:
    gbff = _require_regular_file(
        path,
        label="temporary EFetch GBFF",
    )

    versions: list[
        str
    ] = []

    in_record = False
    version: str | None = None

    try:
        lines = gbff.read_text(
            encoding="utf-8"
        ).splitlines()

    except (
        UnicodeError,
        OSError,
    ) as exc:
        raise MonthlyMissingDatasetsGbffExecutionError(
            "temporary EFetch GBFF could "
            "not be parsed"
        ) from exc

    for line in lines:
        if line.startswith(
            "LOCUS"
        ):
            if in_record:
                _fail(
                    "temporary EFetch GBFF contains "
                    "nested LOCUS records"
                )

            in_record = True
            version = None
            continue

        if line.startswith(
            "VERSION"
        ):
            if not in_record:
                _fail(
                    "temporary EFetch GBFF VERSION "
                    "occurs outside a record"
                )

            parts = line.split()

            if len(
                parts
            ) < 2:
                _fail(
                    "temporary EFetch GBFF VERSION "
                    "record is malformed"
                )

            if version is not None:
                _fail(
                    "temporary EFetch GBFF record "
                    "contains multiple VERSION lines"
                )

            version = parts[
                1
            ]
            continue

        if line.startswith(
            "//"
        ):
            if not in_record:
                _fail(
                    "temporary EFetch GBFF terminator "
                    "occurs outside a record"
                )

            if not version:
                _fail(
                    "temporary EFetch GBFF record "
                    "lacks VERSION"
                )

            versions.append(
                version
            )

            in_record = False
            version = None

    if in_record:
        _fail(
            "temporary EFetch GBFF contains "
            "unterminated record"
        )

    if not versions:
        _fail(
            "temporary EFetch GBFF contains "
            "no records"
        )

    if len(
        set(
            versions
        )
    ) != len(
        versions
    ):
        _fail(
            "temporary EFetch GBFF contains "
            "duplicate VERSION accessions"
        )

    return tuple(
        versions
    )


def _retrieve_exact_component_gbff(
    *,
    acc_dir: Path,
    accession: str,
    component_accessions: Sequence[str],
    urlopen_func: Callable[..., object],
    sleep_func: Callable[[float], None],
    utc_now_func: Callable[[], str],
) -> tuple[
    Path,
    Path,
]:
    directory = _require_real_directory(
        acc_dir,
        label=(
            f"{accession} recovery accession directory"
        ),
    )

    ordered = tuple(
        sorted(
            component_accessions
        )
    )

    if not ordered:
        _fail(
            f"{accession}: cannot use EFetch "
            "without component accessions"
        )

    if len(
        set(
            ordered
        )
    ) != len(
        ordered
    ):
        _fail(
            f"{accession}: duplicate EFetch "
            "component accessions"
        )

    gbff = (
        directory
        / f"{accession}_efetch_components.gbff"
    )

    provenance = (
        directory
        / f"{accession}_efetch_components.json"
    )

    for path in (
        gbff,
        provenance,
        gbff.with_name(
            gbff.name
            + ".partial"
        ),
        provenance.with_name(
            provenance.name
            + ".partial"
        ),
    ):
        if os.path.lexists(
            path
        ):
            _fail(
                f"{accession}: pre-existing EFetch "
                f"evidence is not permitted: {path.name}"
            )

    chunks = [
        ordered[
            start:
            start
            + EFETCH_CHUNK_SIZE
        ]
        for start in range(
            0,
            len(
                ordered
            ),
            EFETCH_CHUNK_SIZE,
        )
    ]

    combined_parts: list[
        bytes
    ] = []

    chunk_events: list[
        dict[
            str,
            object,
        ]
    ] = []

    for chunk_index, chunk in enumerate(
        chunks,
        1,
    ):
        encoded = urllib_parse.urlencode(
            {
                "db":
                    "nuccore",
                "id":
                    ",".join(
                        chunk
                    ),
                "rettype":
                    "gbwithparts",
                "retmode":
                    "text",
                "tool":
                    EFETCH_TOOL,
            }
        ).encode(
            "ascii"
        )

        request = urllib_request.Request(
            recovery.EFETCH_ENDPOINT,
            data=encoded,
            headers={
                "User-Agent":
                    "BacSelect monthly recovery",
            },
            method="POST",
        )

        response_body: bytes | None = None
        last_error: Exception | None = None

        for attempt in range(
            1,
            EFETCH_RETRY_ROUNDS + 1,
        ):
            try:
                with urlopen_func(
                    request,
                    timeout=(
                        EFETCH_TIMEOUT_SECONDS
                    ),
                ) as response:
                    response_body = (
                        response.read()
                    )

                if not response_body:
                    raise OSError(
                        "empty EFetch response"
                    )

                last_error = None
                break

            except (
                urllib_error.URLError,
                TimeoutError,
                OSError,
            ) as exc:
                response_body = None
                last_error = exc

                if (
                    attempt
                    < EFETCH_RETRY_ROUNDS
                ):
                    sleep_func(
                        EFETCH_RETRY_DELAY_SECONDS
                        * attempt
                    )

        if response_body is None:
            _fail(
                f"{accession}: EFetch chunk "
                f"{chunk_index} failed after "
                f"{EFETCH_RETRY_ROUNDS} attempts: "
                f"{last_error}"
            )

        normalized = (
            response_body.rstrip()
            + b"\n"
        )

        combined_parts.append(
            normalized
        )

        chunk_events.append(
            {
                "chunk_index":
                    chunk_index,
                "requested_component_accessions":
                    list(
                        chunk
                    ),
                "response_size_bytes":
                    len(
                        response_body
                    ),
                "response_sha256":
                    hashlib.sha256(
                        response_body
                    ).hexdigest(),
            }
        )

        if chunk_index < len(
            chunks
        ):
            sleep_func(
                EFETCH_REQUEST_INTERVAL_SECONDS
            )

    combined = b"".join(
        combined_parts
    )

    if not combined:
        _fail(
            f"{accession}: EFetch produced "
            "an empty GBFF"
        )

    gbff_partial = _write_partial_file(
        gbff,
        combined,
    )

    try:
        retrieved = (
            _gbff_record_versions(
                gbff_partial
            )
        )

        if (
            len(
                retrieved
            )
            != len(
                ordered
            )
            or set(
                retrieved
            )
            != set(
                ordered
            )
        ):
            missing = sorted(
                set(
                    ordered
                )
                - set(
                    retrieved
                )
            )

            extra = sorted(
                set(
                    retrieved
                )
                - set(
                    ordered
                )
            )

            _fail(
                f"{accession}: EFetch component "
                "set mismatch; "
                f"missing={missing!r}; "
                f"extra={extra!r}"
            )

    except Exception:
        gbff_partial.unlink(
            missing_ok=True
        )
        raise

    gbff_partial.replace(
        gbff
    )

    retrieved_at = utc_now_func()

    if (
        not isinstance(
            retrieved_at,
            str,
        )
        or not retrieved_at
    ):
        _fail(
            f"{accession}: retrieval timestamp "
            "is invalid"
        )

    provenance_payload = {
        "schema_version":
            1,
        "retrieval_method":
            recovery.EFETCH_SOURCE,
        "endpoint":
            recovery.EFETCH_ENDPOINT,
        "db":
            "nuccore",
        "rettype":
            "gbwithparts",
        "retmode":
            "text",
        "assembly_accession":
            accession,
        "requested_component_accessions":
            list(
                ordered
            ),
        "requested_component_count":
            len(
                ordered
            ),
        "chunk_size":
            EFETCH_CHUNK_SIZE,
        "chunk_count":
            len(
                chunks
            ),
        "chunks":
            chunk_events,
        "combined_gbff_size_bytes":
            gbff.stat().st_size,
        "combined_gbff_sha256":
            monthly.sha256_file(
                gbff
            ),
        "retrieved_at_utc":
            retrieved_at,
    }

    provenance_partial = _write_partial_file(
        provenance,
        _canonical_json_bytes(
            provenance_payload
        ),
    )

    provenance_partial.replace(
        provenance
    )

    return (
        gbff,
        provenance,
    )


def _detected_recovery_targets(
    *,
    source_package: Path,
    targets: tuple[
        monthly.MonthlyFreshAcquisitionTarget,
        ...,
    ],
) -> tuple[
    recovery.MissingDatasetsGbffRecoveryTarget,
    ...,
]:
    try:
        detected = (
            recovery
            .detect_missing_datasets_gbff_targets(
                source_package,
                targets,
            )
        )

    except Exception as exc:
        raise MonthlyMissingDatasetsGbffExecutionError(
            "source package is outside the frozen "
            "missing-Datasets-GBFF recovery class"
        ) from exc

    if not detected:
        _fail(
            "source package contains no "
            "missing-Datasets-GBFF recovery target"
        )

    return detected


def _recovery_accessions(
    detected: Sequence[
        recovery.MissingDatasetsGbffRecoveryTarget
    ],
) -> tuple[
    str,
    ...,
]:
    return tuple(
        item.accession
        for item
        in detected
    )


def _recovery_evidence_payload(
    *,
    batch_id: str,
    source_partial_dir: Path,
    source_fetch_contract: SourceFetchContract,
    recovery_batch_dir: Path,
    detected: Sequence[
        recovery.MissingDatasetsGbffRecoveryTarget
    ],
) -> dict[
    str,
    object,
]:
    batch = Path(
        recovery_batch_dir
    )

    package = (
        batch
        / authority.PACKAGE_NAME
    )

    target_rows: list[
        dict[
            str,
            object,
        ]
    ] = []

    for item in detected:
        acc_dir = (
            package
            / "ncbi_dataset"
            / "data"
            / item.accession
        )

        gbff = _require_regular_file(
            acc_dir
            / (
                f"{item.accession}"
                "_efetch_components.gbff"
            ),
            label=(
                f"{item.accession} recovered EFetch GBFF"
            ),
        )

        provenance = _require_regular_file(
            acc_dir
            / (
                f"{item.accession}"
                "_efetch_components.json"
            ),
            label=(
                f"{item.accession} EFetch provenance"
            ),
        )

        target_rows.append(
            {
                "accession":
                    item.accession,
                "observed_biosample":
                    item.observed_biosample,
                "component_accessions":
                    list(
                        item.component_accessions
                    ),
                "fetch_destinations":
                    list(
                        item.fetch_destinations
                    ),
                "efetch_gbff_file":
                    gbff.name,
                "efetch_gbff_sha256":
                    monthly.sha256_file(
                        gbff
                    ),
                "efetch_provenance_file":
                    provenance.name,
                "efetch_provenance_sha256":
                    monthly.sha256_file(
                        provenance
                    ),
            }
        )

    accessions = [
        item.accession
        for item
        in detected
    ]

    return {
        "schema_version":
            1,
        "failure_class":
            FAILURE_CLASS,
        "batch_id":
            batch_id,
        "source_partial_name":
            Path(
                source_partial_dir
            ).name,
        "source_dehydrated_zip_sha256":
            (
                source_fetch_contract
                .dehydrated_zip_sha256
            ),
        "source_fetch_member":
            (
                source_fetch_contract
                .zip_fetch_member
            ),
        "source_extracted_fetch_sha256":
            (
                source_fetch_contract
                .extracted_fetch_sha256
            ),
        "source_zip_fetch_sha256":
            (
                source_fetch_contract
                .zip_fetch_sha256
            ),
        "source_zip_fetch_equals_extracted":
            True,
        "recovery_accession_count":
            len(
                accessions
            ),
        "recovery_accessions":
            accessions,
        "targets":
            target_rows,
    }


def _validate_execution_specific_evidence(
    *,
    batch_dir: Path,
    source_partial_dir: Path,
    targets: tuple[
        monthly.MonthlyFreshAcquisitionTarget,
        ...,
    ],
) -> tuple[
    monthly.MonthlyValidatedPackage,
    tuple[
        recovery.MissingDatasetsGbffRecoveryTarget,
        ...,
    ],
    str,
]:
    batch = _require_real_directory(
        batch_dir,
        label="missing-GBFF recovery batch",
    )

    source = _require_real_directory(
        source_partial_dir,
        label="preserved source partial",
    )

    batch_id = _batch_id_from_dir(
        batch
    )

    source_contract = (
        _validate_source_fetch_contract(
            source
        )
    )

    detected = (
        _detected_recovery_targets(
            source_package=(
                source
                / authority.PACKAGE_NAME
            ),
            targets=targets,
        )
    )

    recovery_accessions = (
        _recovery_accessions(
            detected
        )
    )

    candidate_path = _require_regular_file(
        batch
        / authority.CANDIDATE_AUDIT_NAME,
        label="recovery candidate audit",
    )

    component_path = _require_regular_file(
        batch
        / authority.COMPONENT_AUDIT_NAME,
        label="recovery component audit",
    )

    evidence_path = _require_regular_file(
        batch
        / RECOVERY_EVIDENCE_NAME,
        label="missing-GBFF recovery evidence",
    )

    candidate_before = (
        candidate_path.read_bytes()
    )

    component_before = (
        component_path.read_bytes()
    )

    evidence_before = (
        evidence_path.read_bytes()
    )

    package = _require_real_directory(
        batch
        / authority.PACKAGE_NAME,
        label="recovery package",
    )

    package_before = (
        authority.strict_tree_fingerprint(
            package
        )
    )

    for partial in package.rglob(
        "*.partial"
    ):
        if (
            "_efetch_components"
            in partial.name
        ):
            _fail(
                "recovery package contains "
                "unfinished EFetch evidence: "
                f"{partial}"
            )

    try:
        validated = (
            recovery
            .validate_recovered_package(
                package,
                targets,
                recovery_accessions,
            )
        )

    except Exception as exc:
        raise MonthlyMissingDatasetsGbffExecutionError(
            "recovered package failed frozen "
            "missing-GBFF scientific validation"
        ) from exc

    reconstructed_candidate = (
        _serialize_tsv(
            fields=(
                monthly
                .CANDIDATE_AUDIT_FIELDS
            ),
            rows=(
                validated
                .candidate_rows
            ),
        )
    )

    reconstructed_component = (
        _serialize_tsv(
            fields=(
                monthly
                .COMPONENT_AUDIT_FIELDS
            ),
            rows=(
                validated
                .component_rows
            ),
        )
    )

    if (
        candidate_before
        != reconstructed_candidate
    ):
        _fail(
            "persisted recovery candidate audit "
            "differs from scientific reconstruction"
        )

    if (
        component_before
        != reconstructed_component
    ):
        _fail(
            "persisted recovery component audit "
            "differs from scientific reconstruction"
        )

    try:
        observed_evidence = json.loads(
            evidence_before.decode(
                "utf-8"
            )
        )

    except (
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlyMissingDatasetsGbffExecutionError(
            "missing-GBFF recovery evidence "
            "is invalid JSON"
        ) from exc

    if not isinstance(
        observed_evidence,
        Mapping,
    ):
        _fail(
            "missing-GBFF recovery evidence "
            "is not a JSON object"
        )

    if (
        _canonical_json_bytes(
            observed_evidence
        )
        != evidence_before
    ):
        _fail(
            "missing-GBFF recovery evidence "
            "is not canonical JSON"
        )

    expected_evidence = (
        _recovery_evidence_payload(
            batch_id=batch_id,
            source_partial_dir=source,
            source_fetch_contract=(
                source_contract
            ),
            recovery_batch_dir=batch,
            detected=detected,
        )
    )

    if (
        observed_evidence
        != expected_evidence
    ):
        _fail(
            "missing-GBFF recovery evidence "
            "does not reproduce source and "
            "recovered package state"
        )

    candidate_after = (
        candidate_path.read_bytes()
    )

    component_after = (
        component_path.read_bytes()
    )

    evidence_after = (
        evidence_path.read_bytes()
    )

    package_after = (
        authority.strict_tree_fingerprint(
            package
        )
    )

    if (
        candidate_after
        != candidate_before
        or component_after
        != component_before
        or evidence_after
        != evidence_before
    ):
        _fail(
            "recovery evidence changed during "
            "cause-specific validation"
        )

    if (
        package_after.payload
        != package_before.payload
    ):
        _fail(
            "recovery package changed during "
            "cause-specific validation"
        )

    return (
        validated,
        detected,
        hashlib.sha256(
            evidence_before
        ).hexdigest(),
    )


def execute_missing_datasets_gbff_recovery(
    *,
    source_partial_dir: Path,
    recovery_root: Path,
    batch_id: str,
    release_id: str,
    source_production_commit: str,
    recovery_commit: str,
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
    urlopen_func: Callable[..., object] | None = None,
    sleep_func: Callable[[float], None] | None = None,
    utc_now_func: Callable[[], str] | None = None,
) -> FinalizedMissingDatasetsGbffRecovery:
    target_values = _targets(
        targets
    )

    source = _require_real_directory(
        source_partial_dir,
        label="source partial",
    )

    source_contract = (
        _validate_source_fetch_contract(
            source
        )
    )

    source_detected = (
        _detected_recovery_targets(
            source_package=(
                source
                / authority.PACKAGE_NAME
            ),
            targets=target_values,
        )
    )

    opener = (
        urllib_request.urlopen
        if urlopen_func is None
        else urlopen_func
    )

    sleeper = (
        time.sleep
        if sleep_func is None
        else sleep_func
    )

    now = (
        _utc_now
        if utc_now_func is None
        else utc_now_func
    )

    workspace = (
        authority
        .prepare_recovery_workspace(
            source_partial_dir=(
                source
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=batch_id,
            release_id=release_id,
            source_production_commit=(
                source_production_commit
            ),
            recovery_commit=(
                recovery_commit
            ),
        )
    )

    package = (
        workspace.partial_dir
        / authority.PACKAGE_NAME
    )

    copied_detected = (
        _detected_recovery_targets(
            source_package=package,
            targets=target_values,
        )
    )

    if (
        copied_detected
        != source_detected
    ):
        _fail(
            "missing-GBFF recovery classification "
            "changed after source package copy"
        )

    for item in copied_detected:
        acc_dir = (
            package
            / "ncbi_dataset"
            / "data"
            / item.accession
        )

        _retrieve_exact_component_gbff(
            acc_dir=acc_dir,
            accession=item.accession,
            component_accessions=(
                item.component_accessions
            ),
            urlopen_func=opener,
            sleep_func=sleeper,
            utc_now_func=now,
        )

    recovery_accessions = (
        _recovery_accessions(
            copied_detected
        )
    )

    try:
        validated = (
            recovery
            .validate_recovered_package(
                package,
                target_values,
                recovery_accessions,
            )
        )

    except Exception as exc:
        raise MonthlyMissingDatasetsGbffExecutionError(
            "recovered package failed frozen "
            "missing-GBFF scientific validation"
        ) from exc

    candidate_bytes = (
        _serialize_tsv(
            fields=(
                monthly
                .CANDIDATE_AUDIT_FIELDS
            ),
            rows=(
                validated
                .candidate_rows
            ),
        )
    )

    component_bytes = (
        _serialize_tsv(
            fields=(
                monthly
                .COMPONENT_AUDIT_FIELDS
            ),
            rows=(
                validated
                .component_rows
            ),
        )
    )

    _write_new_file(
        workspace.partial_dir
        / authority.CANDIDATE_AUDIT_NAME,
        candidate_bytes,
    )

    _write_new_file(
        workspace.partial_dir
        / authority.COMPONENT_AUDIT_NAME,
        component_bytes,
    )

    evidence_payload = (
        _recovery_evidence_payload(
            batch_id=batch_id,
            source_partial_dir=source,
            source_fetch_contract=(
                source_contract
            ),
            recovery_batch_dir=(
                workspace.partial_dir
            ),
            detected=(
                copied_detected
            ),
        )
    )

    _write_new_file(
        workspace.partial_dir
        / RECOVERY_EVIDENCE_NAME,
        _canonical_json_bytes(
            evidence_payload
        ),
    )

    # Cause-specific pre-final audit.
    _validate_execution_specific_evidence(
        batch_dir=(
            workspace.partial_dir
        ),
        source_partial_dir=source,
        targets=target_values,
    )

    accepted = (
        authority
        .seal_recovery_workspace(
            workspace,
            release_id=release_id,
            source_production_commit=(
                source_production_commit
            ),
            recovery_commit=(
                recovery_commit
            ),
        )
    )

    # Cause-specific post-final audit.
    (
        _,
        final_detected,
        evidence_sha,
    ) = (
        _validate_execution_specific_evidence(
            batch_dir=(
                accepted.batch_dir
            ),
            source_partial_dir=(
                accepted
                .source_partial_dir
            ),
            targets=target_values,
        )
    )

    return (
        FinalizedMissingDatasetsGbffRecovery(
            batch_id=(
                accepted.batch_id
            ),
            batch_dir=(
                accepted.batch_dir
            ),
            source_partial_dir=(
                accepted
                .source_partial_dir
            ),
            recovery_commit=(
                accepted.recovery_commit
            ),
            recovery_summary_sha256=(
                accepted.summary_sha256
            ),
            recovery_evidence_sha256=(
                evidence_sha
            ),
            recovery_accessions=(
                _recovery_accessions(
                    final_detected
                )
            ),
        )
    )


def audit_finalized_missing_datasets_gbff_recovery(
    *,
    batch_dir: Path,
    source_partial_dir: Path,
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
    expected_release_id: str,
    expected_source_production_commit: str,
) -> FinalizedMissingDatasetsGbffRecovery:
    target_values = _targets(
        targets
    )

    generic = (
        authority
        .audit_final_recovery(
            batch_dir=batch_dir,
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
    )

    (
        _,
        detected,
        evidence_sha,
    ) = (
        _validate_execution_specific_evidence(
            batch_dir=(
                generic.batch_dir
            ),
            source_partial_dir=(
                generic
                .source_partial_dir
            ),
            targets=target_values,
        )
    )

    return (
        FinalizedMissingDatasetsGbffRecovery(
            batch_id=(
                generic.batch_id
            ),
            batch_dir=(
                generic.batch_dir
            ),
            source_partial_dir=(
                generic
                .source_partial_dir
            ),
            recovery_commit=(
                generic.recovery_commit
            ),
            recovery_summary_sha256=(
                generic.summary_sha256
            ),
            recovery_evidence_sha256=(
                evidence_sha
            ),
            recovery_accessions=(
                _recovery_accessions(
                    detected
                )
            ),
        )
    )
