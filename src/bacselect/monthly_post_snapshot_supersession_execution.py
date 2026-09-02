"""Recovery execution for frozen targets superseded after a monthly snapshot."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Mapping, Sequence

from bacselect import (
    monthly_post_snapshot_supersession_recovery
    as supersession,
)
from bacselect import (
    monthly_sequence_recovery_authority
    as authority,
)
from bacselect import (
    monthly_sequence_validation
    as monthly,
)


TRANSPORT_SCHEMA_VERSION = 1

SUPERSESSION_EVIDENCE_NAME = (
    "post-snapshot-supersession-evidence.tsv"
)

TRANSPORT_RECORD_NAME = (
    "post-snapshot-supersession-transport.json"
)

TRANSPORT_STDOUT_NAME = (
    "post-snapshot-supersession-rehydrate.stdout.txt"
)

TRANSPORT_STDERR_NAME = (
    "post-snapshot-supersession-rehydrate.stderr.txt"
)


class MonthlyPostSnapshotSupersessionExecutionError(
    RuntimeError
):
    """Raised when supersession recovery execution cannot prove its contract."""


@dataclass(frozen=True)
class FrozenFetchContract:
    fetch_path: Path
    fetch_sha256: str
    destinations_by_accession: Mapping[
        str,
        tuple[str, ...],
    ]


@dataclass(frozen=True)
class FinalizedSupersessionRecovery:
    batch_id: str
    batch_dir: Path
    source_partial_dir: Path
    recovery_commit: str
    recovery_summary_sha256: str
    supersession_evidence_sha256: str
    transport_record_sha256: str
    affected_accessions: tuple[str, ...]


def _fail(
    message: str,
) -> None:
    raise MonthlyPostSnapshotSupersessionExecutionError(
        message
    )


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
    except FileExistsError as exc:
        raise MonthlyPostSnapshotSupersessionExecutionError(
            f"refusing to overwrite recovery evidence: {path}"
        ) from exc


def _serialize_tsv(
    *,
    fields: Sequence[str],
    rows: Sequence[
        Mapping[str, str]
    ],
) -> bytes:
    output = io.StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        output,
        fieldnames=tuple(
            fields
        ),
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
                in fields
            }
        )

    return output.getvalue().encode(
        "utf-8"
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
            "supersession execution requires targets"
        )

    accessions = tuple(
        target.canonical_genbank_assembly_accession
        for target
        in values
    )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        _fail(
            "duplicate supersession execution targets"
        )

    if any(
        monthly.CANONICAL_GCA_RE.fullmatch(
            accession
        )
        is None
        for accession
        in accessions
    ):
        _fail(
            "invalid supersession execution target accession"
        )

    return values


def _destination_kind(
    *,
    accession: str,
    destination: str,
) -> str | None:
    prefix = (
        f"data/{accession}/"
    )

    if not destination.startswith(
        prefix
    ):
        return None

    remainder = destination[
        len(
            prefix
        ):
    ]

    if (
        not remainder
        or "/" in remainder
    ):
        return None

    if remainder == "genomic.gbff":
        return "gbff"

    if remainder == "sequence_report.jsonl":
        return "sequence_report"

    if (
        remainder.startswith(
            accession
            + "_"
        )
        and remainder.endswith(
            "_genomic.fna"
        )
    ):
        return "fasta"

    return None


def validate_frozen_fetch_contract(
    *,
    package: Path,
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
    successor_accessions: Sequence[str],
) -> FrozenFetchContract:
    target_values = _targets(
        targets
    )

    expected = tuple(
        target.canonical_genbank_assembly_accession
        for target
        in target_values
    )

    expected_set = set(
        expected
    )

    successors = tuple(
        successor_accessions
    )

    for successor in successors:
        if monthly.CANONICAL_GCA_RE.fullmatch(
            successor
        ) is None:
            _fail(
                "invalid acquisition-time successor accession"
            )

        if successor in expected_set:
            _fail(
                "successor accession is also a frozen "
                "target in the same recovery batch"
            )

    fetch_path = (
        Path(
            package
        )
        / "ncbi_dataset"
        / "fetch.txt"
    )

    if (
        fetch_path.is_symlink()
        or not fetch_path.is_file()
    ):
        _fail(
            "recovery package lacks regular "
            "ncbi_dataset/fetch.txt"
        )

    raw = fetch_path.read_bytes()

    fetch_sha = hashlib.sha256(
        raw
    ).hexdigest()

    try:
        text = raw.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise MonthlyPostSnapshotSupersessionExecutionError(
            "fetch.txt is not UTF-8"
        ) from exc

    for successor in successors:
        if successor in text:
            _fail(
                "successor accession appears in "
                "frozen Datasets fetch manifest"
            )

    seen_destinations: set[str] = set()

    kinds_by_accession = {
        accession: {}
        for accession
        in expected
    }

    destinations_by_accession = {
        accession: []
        for accession
        in expected
    }

    for line_number, line in enumerate(
        text.splitlines(),
        1,
    ):
        if not line:
            _fail(
                f"fetch.txt contains blank line "
                f"{line_number}"
            )

        parts = line.split(
            "\t"
        )

        if len(
            parts
        ) != 3:
            _fail(
                f"fetch.txt line {line_number} "
                "does not contain exactly three fields"
            )

        destination = parts[
            2
        ]

        if (
            destination.startswith(
                "/"
            )
            or ".." in Path(
                destination
            ).parts
        ):
            _fail(
                f"unsafe fetch destination "
                f"{destination!r}"
            )

        if destination in seen_destinations:
            _fail(
                "duplicate fetch destination "
                f"{destination!r}"
            )

        seen_destinations.add(
            destination
        )

        match = re.fullmatch(
            r"data/(GCA_\d+\.\d+)/[^/]+",
            destination,
        )

        if match is None:
            _fail(
                "unexpected Datasets fetch destination "
                f"{destination!r}"
            )

        accession = match.group(
            1
        )

        if accession not in expected_set:
            _fail(
                "fetch manifest contains accession "
                "outside frozen batch: "
                f"{accession}"
            )

        kind = _destination_kind(
            accession=accession,
            destination=destination,
        )

        if kind is None:
            _fail(
                f"{accession}: unexpected fetch "
                f"destination {destination!r}"
            )

        if kind in kinds_by_accession[
            accession
        ]:
            _fail(
                f"{accession}: duplicate {kind} "
                "fetch entry"
            )

        kinds_by_accession[
            accession
        ][
            kind
        ] = destination

        destinations_by_accession[
            accession
        ].append(
            destination
        )

    required = {
        "gbff",
        "fasta",
        "sequence_report",
    }

    for accession in expected:
        observed = set(
            kinds_by_accession[
                accession
            ]
        )

        if observed != required:
            _fail(
                f"{accession}: frozen fetch contract "
                "does not contain exactly GBFF, "
                "genomic FASTA, and sequence report; "
                f"observed={sorted(observed)!r}"
            )

    if len(
        seen_destinations
    ) != 3 * len(
        expected
    ):
        _fail(
            "frozen fetch manifest cardinality "
            "does not equal three entries per target"
        )

    return FrozenFetchContract(
        fetch_path=fetch_path,
        fetch_sha256=fetch_sha,
        destinations_by_accession={
            accession:
                tuple(
                    destinations_by_accession[
                        accession
                    ]
                )
            for accession
            in expected
        },
    )


def _unresolved_fetch_destinations(
    *,
    package: Path,
    contract: FrozenFetchContract,
) -> tuple[str, ...]:
    base = (
        Path(
            package
        )
        / "ncbi_dataset"
    )

    unresolved = []

    for accession in sorted(
        contract.destinations_by_accession
    ):
        for relative in (
            contract
            .destinations_by_accession[
                accession
            ]
        ):
            path = (
                base
                / relative
            )

            if (
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_size <= 0
            ):
                unresolved.append(
                    relative
                )

    return tuple(
        unresolved
    )


def _verify_exact_payload_directories(
    *,
    package: Path,
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
    successor_accessions: Sequence[str],
) -> None:
    expected = {
        target.canonical_genbank_assembly_accession
        for target
        in targets
    }

    data_root = (
        Path(
            package
        )
        / "ncbi_dataset"
        / "data"
    )

    if (
        data_root.is_symlink()
        or not data_root.is_dir()
    ):
        _fail(
            "rehydrated package lacks real "
            "ncbi_dataset/data directory"
        )

    observed = set()

    for entry in data_root.iterdir():
        if (
            entry.is_dir()
            and monthly.CANONICAL_GCA_RE.fullmatch(
                entry.name
            )
            is not None
        ):
            if entry.is_symlink():
                _fail(
                    "accession payload directory is symlink"
                )

            observed.add(
                entry.name
            )

    unexpected = (
        observed
        - expected
    )

    if unexpected:
        _fail(
            "rehydrated package contains accession "
            "payload outside frozen batch: "
            f"{sorted(unexpected)!r}"
        )

    for successor in successor_accessions:
        if successor in observed:
            _fail(
                "successor accession entered "
                "recovered payload"
            )


def _successor_accessions(
    classification: (
        supersession
        .PostSnapshotSupersessionClassification
    ),
) -> tuple[str, ...]:
    return tuple(
        row[
            "acquisition_current_accession"
        ]
        for row
        in classification.evidence_rows
    )


def _transport_payload(
    *,
    batch_id: str,
    datasets_executable: Path,
    command: Sequence[str],
    exit_code: int,
    fetch_sha256_before: str,
    fetch_sha256_after: str,
    stdout_sha256: str,
    stderr_sha256: str,
    target_accessions: Sequence[str],
    affected_accessions: Sequence[str],
    successor_accessions: Sequence[str],
    unresolved_after: Sequence[str],
) -> Mapping[str, object]:
    return {
        "affected_accessions":
            list(
                affected_accessions
            ),
        "batch_id":
            batch_id,
        "classification":
            supersession.FAILURE_CLASS,
        "command":
            list(
                command
            ),
        "datasets_executable":
            str(
                datasets_executable
            ),
        "exit_code":
            exit_code,
        "fetch_sha256_after":
            fetch_sha256_after,
        "fetch_sha256_before":
            fetch_sha256_before,
        "schema_version":
            TRANSPORT_SCHEMA_VERSION,
        "stderr_sha256":
            stderr_sha256,
        "stdout_sha256":
            stdout_sha256,
        "successor_accessions":
            list(
                successor_accessions
            ),
        "target_accessions":
            list(
                target_accessions
            ),
        "unresolved_after":
            list(
                unresolved_after
            ),
    }


def _validate_execution_specific_evidence(
    *,
    batch_dir: Path,
    source_snapshot_report: Path,
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
) -> tuple[
    supersession.MonthlyPostSnapshotSupersessionValidatedPackage,
    Mapping[str, object],
]:
    package = (
        Path(
            batch_dir
        )
        / authority.PACKAGE_NAME
    )

    validated = (
        supersession
        .validate_post_snapshot_supersession_package(
            package=package,
            source_snapshot_report=(
                source_snapshot_report
            ),
            targets=targets,
        )
    )

    supersession_path = (
        Path(
            batch_dir
        )
        / SUPERSESSION_EVIDENCE_NAME
    )

    if (
        supersession_path.is_symlink()
        or not supersession_path.is_file()
    ):
        _fail(
            "missing supersession cause evidence"
        )

    expected_supersession = (
        supersession
        .serialize_supersession_evidence(
            validated.supersession_rows
        )
    )

    if (
        supersession_path.read_bytes()
        != expected_supersession
    ):
        _fail(
            "supersession cause evidence "
            "does not reproduce validation"
        )

    candidate_path = (
        Path(
            batch_dir
        )
        / authority.CANDIDATE_AUDIT_NAME
    )

    component_path = (
        Path(
            batch_dir
        )
        / authority.COMPONENT_AUDIT_NAME
    )

    expected_candidates = (
        _serialize_tsv(
            fields=(
                monthly
                .CANDIDATE_AUDIT_FIELDS
            ),
            rows=(
                validated
                .validated_package
                .candidate_rows
            ),
        )
    )

    expected_components = (
        _serialize_tsv(
            fields=(
                monthly
                .COMPONENT_AUDIT_FIELDS
            ),
            rows=(
                validated
                .validated_package
                .component_rows
            ),
        )
    )

    if (
        not candidate_path.is_file()
        or candidate_path.is_symlink()
        or candidate_path.read_bytes()
        != expected_candidates
    ):
        _fail(
            "candidate audit does not reproduce "
            "supersession scientific validation"
        )

    if (
        not component_path.is_file()
        or component_path.is_symlink()
        or component_path.read_bytes()
        != expected_components
    ):
        _fail(
            "component audit does not reproduce "
            "supersession scientific validation"
        )

    stdout_path = (
        Path(
            batch_dir
        )
        / TRANSPORT_STDOUT_NAME
    )

    stderr_path = (
        Path(
            batch_dir
        )
        / TRANSPORT_STDERR_NAME
    )

    transport_path = (
        Path(
            batch_dir
        )
        / TRANSPORT_RECORD_NAME
    )

    for path, label in (
        (
            stdout_path,
            "transport stdout",
        ),
        (
            stderr_path,
            "transport stderr",
        ),
        (
            transport_path,
            "transport record",
        ),
    ):
        if (
            path.is_symlink()
            or not path.is_file()
        ):
            _fail(
                f"missing regular {label}"
            )

    try:
        transport = json.loads(
            transport_path.read_text(
                encoding="ascii"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlyPostSnapshotSupersessionExecutionError(
            "invalid supersession transport record"
        ) from exc

    if not isinstance(
        transport,
        dict,
    ):
        _fail(
            "supersession transport record "
            "is not a JSON object"
        )

    expected_accessions = [
        target.canonical_genbank_assembly_accession
        for target
        in targets
    ]

    affected = [
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row
        in validated.supersession_rows
    ]

    successors = [
        row[
            "acquisition_current_accession"
        ]
        for row
        in validated.supersession_rows
    ]

    contract = (
        validate_frozen_fetch_contract(
            package=package,
            targets=targets,
            successor_accessions=(
                successors
            ),
        )
    )

    unresolved = (
        _unresolved_fetch_destinations(
            package=package,
            contract=contract,
        )
    )

    _verify_exact_payload_directories(
        package=package,
        targets=targets,
        successor_accessions=(
            successors
        ),
    )

    if transport.get(
        "schema_version"
    ) != TRANSPORT_SCHEMA_VERSION:
        _fail(
            "transport schema version changed"
        )

    if transport.get(
        "classification"
    ) != supersession.FAILURE_CLASS:
        _fail(
            "transport classification changed"
        )

    if transport.get(
        "target_accessions"
    ) != expected_accessions:
        _fail(
            "transport target order changed"
        )

    if transport.get(
        "affected_accessions"
    ) != affected:
        _fail(
            "transport affected-accession order changed"
        )

    if transport.get(
        "successor_accessions"
    ) != successors:
        _fail(
            "transport successor evidence changed"
        )

    if transport.get(
        "exit_code"
    ) != 0:
        _fail(
            "accepted transport record does not "
            "have exit code zero"
        )

    if transport.get(
        "unresolved_after"
    ) != []:
        _fail(
            "accepted transport record contains "
            "unresolved fetch destinations"
        )

    if unresolved:
        _fail(
            "finalized recovered package contains "
            "unresolved fetch destinations"
        )

    if transport.get(
        "fetch_sha256_before"
    ) != contract.fetch_sha256:
        _fail(
            "transport pre-rehydrate fetch hash changed"
        )

    if transport.get(
        "fetch_sha256_after"
    ) != contract.fetch_sha256:
        _fail(
            "transport post-rehydrate fetch hash changed"
        )

    if transport.get(
        "stdout_sha256"
    ) != monthly.sha256_file(
        stdout_path
    ):
        _fail(
            "transport stdout hash mismatch"
        )

    if transport.get(
        "stderr_sha256"
    ) != monthly.sha256_file(
        stderr_path
    ):
        _fail(
            "transport stderr hash mismatch"
        )

    command = transport.get(
        "command"
    )

    if (
        not isinstance(
            command,
            list,
        )
        or len(
            command
        ) < 2
        or command[
            1
        ]
        != "rehydrate"
    ):
        _fail(
            "transport command is not a "
            "Datasets rehydrate command"
        )

    return (
        validated,
        transport,
    )


def execute_post_snapshot_supersession_recovery(
    *,
    source_partial_dir: Path,
    recovery_root: Path,
    batch_id: str,
    release_id: str,
    source_production_commit: str,
    recovery_commit: str,
    source_snapshot_report: Path,
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
    datasets_executable: Path,
    max_workers: int = 8,
) -> FinalizedSupersessionRecovery:
    target_values = _targets(
        targets
    )

    if max_workers < 1:
        _fail(
            "max_workers must be positive"
        )

    executable = Path(
        datasets_executable
    )

    if (
        executable.is_symlink()
        or not executable.is_file()
        or not os.access(
            executable,
            os.X_OK,
        )
    ):
        _fail(
            "datasets executable is not a "
            "regular executable file"
        )

    workspace = (
        authority
        .prepare_recovery_workspace(
            source_partial_dir=(
                source_partial_dir
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

    classification = (
        supersession
        .classify_post_snapshot_supersession(
            package=package,
            source_snapshot_report=(
                source_snapshot_report
            ),
            targets=target_values,
        )
    )

    successors = (
        _successor_accessions(
            classification
        )
    )

    frozen_accessions = tuple(
        target.canonical_genbank_assembly_accession
        for target
        in target_values
    )

    if set(
        successors
    ) & set(
        frozen_accessions
    ):
        _fail(
            "successor accession collides with "
            "frozen batch target"
        )

    contract = (
        validate_frozen_fetch_contract(
            package=package,
            targets=target_values,
            successor_accessions=(
                successors
            ),
        )
    )

    command = [
        str(
            executable
        ),
        "rehydrate",
        "--directory",
        str(
            package
        ),
        "--max-workers",
        str(
            max_workers
        ),
        "--no-progressbar",
    ]

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )

    stdout_bytes = result.stdout.encode(
        "utf-8"
    )

    stderr_bytes = result.stderr.encode(
        "utf-8"
    )

    _write_new_file(
        workspace.partial_dir
        / TRANSPORT_STDOUT_NAME,
        stdout_bytes,
    )

    _write_new_file(
        workspace.partial_dir
        / TRANSPORT_STDERR_NAME,
        stderr_bytes,
    )

    if result.returncode != 0:
        _fail(
            "Datasets rehydrate failed with "
            f"exit code {result.returncode}"
        )

    fetch_after = monthly.sha256_file(
        contract.fetch_path
    )

    if fetch_after != contract.fetch_sha256:
        _fail(
            "Datasets rehydrate changed frozen "
            "fetch.txt"
        )

    unresolved = (
        _unresolved_fetch_destinations(
            package=package,
            contract=contract,
        )
    )

    if unresolved:
        _fail(
            "recovered package remains incomplete "
            "after Datasets rehydrate: "
            f"{unresolved!r}"
        )

    _verify_exact_payload_directories(
        package=package,
        targets=target_values,
        successor_accessions=(
            successors
        ),
    )

    validated = (
        supersession
        .validate_post_snapshot_supersession_package(
            package=package,
            source_snapshot_report=(
                source_snapshot_report
            ),
            targets=target_values,
        )
    )

    if (
        tuple(
            row[
                "canonical_genbank_assembly_accession"
            ]
            for row
            in validated.supersession_rows
        )
        != classification.affected_accessions
    ):
        _fail(
            "supersession classification changed "
            "after rehydration"
        )

    supersession_bytes = (
        supersession
        .serialize_supersession_evidence(
            validated.supersession_rows
        )
    )

    candidate_bytes = (
        _serialize_tsv(
            fields=(
                monthly
                .CANDIDATE_AUDIT_FIELDS
            ),
            rows=(
                validated
                .validated_package
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
                .validated_package
                .component_rows
            ),
        )
    )

    _write_new_file(
        workspace.partial_dir
        / SUPERSESSION_EVIDENCE_NAME,
        supersession_bytes,
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

    transport_payload = (
        _transport_payload(
            batch_id=batch_id,
            datasets_executable=(
                executable
            ),
            command=command,
            exit_code=(
                result.returncode
            ),
            fetch_sha256_before=(
                contract.fetch_sha256
            ),
            fetch_sha256_after=(
                fetch_after
            ),
            stdout_sha256=hashlib.sha256(
                stdout_bytes
            ).hexdigest(),
            stderr_sha256=hashlib.sha256(
                stderr_bytes
            ).hexdigest(),
            target_accessions=(
                frozen_accessions
            ),
            affected_accessions=(
                classification
                .affected_accessions
            ),
            successor_accessions=(
                successors
            ),
            unresolved_after=(),
        )
    )

    _write_new_file(
        workspace.partial_dir
        / TRANSPORT_RECORD_NAME,
        _canonical_json_bytes(
            transport_payload
        ),
    )

    # Cause-specific pre-final audit.
    _validate_execution_specific_evidence(
        batch_dir=(
            workspace.partial_dir
        ),
        source_snapshot_report=(
            source_snapshot_report
        ),
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
        final_validated,
        _,
    ) = _validate_execution_specific_evidence(
        batch_dir=(
            accepted.batch_dir
        ),
        source_snapshot_report=(
            source_snapshot_report
        ),
        targets=target_values,
    )

    return FinalizedSupersessionRecovery(
        batch_id=batch_id,
        batch_dir=(
            accepted.batch_dir
        ),
        source_partial_dir=(
            accepted.source_partial_dir
        ),
        recovery_commit=(
            accepted.recovery_commit
        ),
        recovery_summary_sha256=(
            accepted.summary_sha256
        ),
        supersession_evidence_sha256=(
            monthly.sha256_file(
                accepted.batch_dir
                / SUPERSESSION_EVIDENCE_NAME
            )
        ),
        transport_record_sha256=(
            monthly.sha256_file(
                accepted.batch_dir
                / TRANSPORT_RECORD_NAME
            )
        ),
        affected_accessions=tuple(
            row[
                "canonical_genbank_assembly_accession"
            ]
            for row
            in final_validated
            .supersession_rows
        ),
    )


def audit_finalized_post_snapshot_supersession_recovery(
    *,
    batch_dir: Path,
    source_partial_dir: Path,
    source_snapshot_report: Path,
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
    expected_release_id: str,
    expected_source_production_commit: str,
) -> FinalizedSupersessionRecovery:
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
        validated,
        _,
    ) = _validate_execution_specific_evidence(
        batch_dir=(
            generic.batch_dir
        ),
        source_snapshot_report=(
            source_snapshot_report
        ),
        targets=target_values,
    )

    return FinalizedSupersessionRecovery(
        batch_id=(
            generic.batch_id
        ),
        batch_dir=(
            generic.batch_dir
        ),
        source_partial_dir=(
            generic.source_partial_dir
        ),
        recovery_commit=(
            generic.recovery_commit
        ),
        recovery_summary_sha256=(
            generic.summary_sha256
        ),
        supersession_evidence_sha256=(
            monthly.sha256_file(
                generic.batch_dir
                / SUPERSESSION_EVIDENCE_NAME
            )
        ),
        transport_record_sha256=(
            monthly.sha256_file(
                generic.batch_dir
                / TRANSPORT_RECORD_NAME
            )
        ),
        affected_accessions=tuple(
            row[
                "canonical_genbank_assembly_accession"
            ]
            for row
            in validated.supersession_rows
        ),
    )
