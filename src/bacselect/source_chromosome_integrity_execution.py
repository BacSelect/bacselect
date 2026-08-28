"""Evidence-bound chromosome-integrity execution helpers for BacSelect Stage 3.

This module adds no chromosome-integrity scientific decision rule.

It verifies one already-resolved Stage 3 candidate against the frozen Stage 1
source evidence, reconstructs the exact Primary Assembly molecule-class,
topology and GenBank DEFINITION evidence from the verified package, and
delegates trigger assessment and classification to the prospectively frozen
``source_chromosome_integrity`` primitive.

It performs no production population discovery, Stage 2 filtering, historical
artifact lookup, taxonomy resolution, baseline comparison, structural-feature
calculation, holdout construction, or selector analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Callable, Mapping, Sequence

from bacselect import source_chromosome_integrity
from bacselect.source_cache_verify import (
    path_scope,
    resolve_manifest_path,
    sha256_file,
)
from bacselect.source_truth_execution import (
    CandidateAudit,
    ComponentAudit,
    PackageFile,
    load_primary_components,
    source_evidence_sha256,
)


LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class Stage3ExecutionError(RuntimeError):
    """Raised when frozen Stage 3 execution evidence is inconsistent."""


@dataclass(frozen=True)
class SequenceReportComponent:
    """One exact NCBI sequence-report component record."""

    assembly_unit: str
    molecule_class: str | None
    length: int | None


@dataclass(frozen=True)
class GbffComponent:
    """Stage 3 evidence reconstructed from one exact GBFF record."""

    length: int
    topology: str
    definition: str


@dataclass(frozen=True)
class Stage3CandidateEvaluation:
    """Verified Stage 3 result for one Stage 2-continuing candidate."""

    accession: str
    source_evidence_sha256: str
    primary_component_count: int
    trigger: source_chromosome_integrity.TriggerAssessment
    decision: source_chromosome_integrity.ChromosomeIntegrityDecision


def _lower_sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or LOWER_SHA256_RE.fullmatch(value) is None
    ):
        raise Stage3ExecutionError(
            f"{label} must be lowercase SHA256"
        )

    return value


def _nonempty_text(
    value: object,
    *,
    label: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise Stage3ExecutionError(
            f"{label} must be a string"
        )

    cleaned = value.strip()

    if not cleaned:
        raise Stage3ExecutionError(
            f"{label} must not be empty"
        )

    return cleaned


def _value(
    record: Mapping[str, object],
    *names: str,
) -> object:
    """Preserve the frozen sequence-validator alias lookup semantics."""

    for name in names:
        if name in record:
            return record[name]

    return None


def _verify_manifest_file(
    *,
    candidate: CandidateAudit,
    package_file: PackageFile,
    label: str,
) -> Path:
    expected_sha = _lower_sha256(
        package_file.sha256,
        label=f"{label} package SHA256",
    )

    if package_file.size_bytes < 0:
        raise Stage3ExecutionError(
            f"{label} package size must be nonnegative"
        )

    try:
        path = resolve_manifest_path(
            candidate.batch_dir,
            package_file.relative_path,
        )
    except ValueError as exc:
        raise Stage3ExecutionError(
            f"{label} package path resolution failed: {exc}"
        ) from exc

    observed_size = path.stat().st_size

    if observed_size != package_file.size_bytes:
        raise Stage3ExecutionError(
            f"{label} size differs from package manifest"
        )

    observed_sha = sha256_file(
        path
    )

    if observed_sha != expected_sha:
        raise Stage3ExecutionError(
            f"{label} SHA256 differs from package manifest"
        )

    return path


def _accession_package_files(
    *,
    accession: str,
    package_manifest: Mapping[str, PackageFile],
) -> tuple[PackageFile, ...]:
    rows = []

    for package_file in package_manifest.values():
        try:
            scope, scoped_accession = path_scope(
                package_file.relative_path
            )
        except ValueError as exc:
            raise Stage3ExecutionError(
                "invalid package-manifest accession scope"
            ) from exc

        if (
            scope == "accession"
            and scoped_accession == accession
        ):
            rows.append(
                package_file
            )

    if not rows:
        raise Stage3ExecutionError(
            "candidate has no accession-scoped package files"
        )

    return tuple(
        sorted(
            rows,
            key=lambda item:
                item.relative_path,
        )
    )


def _select_sequence_report(
    *,
    candidate: CandidateAudit,
    package_manifest: Mapping[str, PackageFile],
) -> Path:
    rows = tuple(
        row
        for row in _accession_package_files(
            accession=candidate.accession,
            package_manifest=package_manifest,
        )
        if Path(
            row.relative_path
        ).name == "sequence_report.jsonl"
    )

    if len(rows) != 1:
        raise Stage3ExecutionError(
            "candidate must have exactly one sequence_report.jsonl"
        )

    return _verify_manifest_file(
        candidate=candidate,
        package_file=rows[0],
        label="sequence report",
    )


def _select_gbff(
    *,
    candidate: CandidateAudit,
    package_manifest: Mapping[str, PackageFile],
) -> Path:
    accepted_names = {
        "genomic.gbff",
        (
            f"{candidate.accession}"
            "_efetch_components.gbff"
        ),
    }

    rows = tuple(
        row
        for row in _accession_package_files(
            accession=candidate.accession,
            package_manifest=package_manifest,
        )
        if Path(
            row.relative_path
        ).name in accepted_names
    )

    if len(rows) != 1:
        raise Stage3ExecutionError(
            "candidate must have exactly one accepted GBFF"
        )

    return _verify_manifest_file(
        candidate=candidate,
        package_file=rows[0],
        label="GBFF",
    )


def read_sequence_report(
    path: Path,
    *,
    accession: str,
) -> dict[str, SequenceReportComponent]:
    """Read the exact component universe from one sequence_report.jsonl."""

    records: dict[
        str,
        SequenceReportComponent,
    ] = {}

    try:
        handle = Path(path).open(
            encoding="utf-8",
            errors="strict",
        )
    except OSError as exc:
        raise Stage3ExecutionError(
            "cannot open sequence report"
        ) from exc

    with handle:
        for line_number, line in enumerate(
            handle,
            start=1,
        ):
            if not line.strip():
                continue

            try:
                record = json.loads(
                    line
                )
            except json.JSONDecodeError as exc:
                raise Stage3ExecutionError(
                    "invalid sequence-report JSON "
                    f"at line {line_number}"
                ) from exc

            if not isinstance(
                record,
                dict,
            ):
                raise Stage3ExecutionError(
                    "sequence-report record must be an object"
                )

            returned = _value(
                record,
                "assemblyAccession",
                "assembly_accession",
            )

            if returned != accession:
                raise Stage3ExecutionError(
                    "sequence-report assembly accession mismatch"
                )

            unit = _nonempty_text(
                _value(
                    record,
                    "assemblyUnit",
                    "assembly_unit",
                ),
                label="sequence-report assembly unit",
            )

            component = _nonempty_text(
                _value(
                    record,
                    "genbankAccession",
                    "genbank_accession",
                ),
                label="sequence-report GenBank accession",
            )

            if component in records:
                raise Stage3ExecutionError(
                    "duplicate sequence-report component accession"
                )

            raw_length = _value(
                record,
                "length",
            )

            if raw_length is None:
                component_length = None
            else:
                try:
                    component_length = int(
                        raw_length
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    raise Stage3ExecutionError(
                        "invalid sequence-report component length"
                    ) from None

                if component_length <= 0:
                    raise Stage3ExecutionError(
                        "sequence-report component length "
                        "must be positive"
                    )

            molecule_class = _value(
                record,
                "assignedMoleculeLocationType",
            )

            if molecule_class is not None and not isinstance(
                molecule_class,
                str,
            ):
                raise Stage3ExecutionError(
                    "sequence-report molecule class must be a string"
                )

            records[
                component
            ] = SequenceReportComponent(
                assembly_unit=unit,
                molecule_class=molecule_class,
                length=component_length,
            )

    if not records:
        raise Stage3ExecutionError(
            "sequence report contains no records"
        )

    return records


def _definition_from_record(
    lines: Sequence[str],
) -> str:
    prefix = "DEFINITION".ljust(
        12
    )

    starts = [
        index
        for index, line in enumerate(
            lines
        )
        if line.startswith(
            prefix
        )
    ]

    if len(starts) != 1:
        raise Stage3ExecutionError(
            "GBFF record must contain exactly one DEFINITION"
        )

    start = starts[0]

    parts = [
        lines[
            start
        ][12:].strip()
    ]

    for line in lines[
        start + 1:
    ]:
        if not line.startswith(
            " " * 12
        ):
            break

        value = line[
            12:
        ].strip()

        if value:
            parts.append(
                value
            )

    definition = " ".join(
        value
        for value in parts
        if value
    )

    if not definition:
        raise Stage3ExecutionError(
            "GBFF DEFINITION must not be empty"
        )

    return definition


def read_gbff_records(
    path: Path,
) -> dict[str, GbffComponent]:
    """Read GBFF using the frozen BacSelect topology/VERSION semantics.

    This extends the already-frozen sequence-validation parser only by
    reconstructing the prospectively specified multiline DEFINITION field.
    """

    records: dict[
        str,
        GbffComponent,
    ] = {}

    length = None
    topology = None
    version = None

    in_record = False
    in_origin = False
    saw_origin = False

    origin_parts: list[str] = []
    record_lines: list[str] = []

    try:
        handle = Path(path).open(
            encoding="utf-8",
            errors="strict",
        )
    except OSError as exc:
        raise Stage3ExecutionError(
            "cannot open GBFF"
        ) from exc

    with handle:
        for line_number, line in enumerate(
            handle,
            start=1,
        ):
            clean_line = line.rstrip(
                "\n"
            )

            if line.startswith(
                "LOCUS"
            ):
                if in_record:
                    raise Stage3ExecutionError(
                        "GBFF LOCUS before previous record ended"
                    )

                tokens = line.split()

                if len(tokens) < 3:
                    raise Stage3ExecutionError(
                        "malformed GBFF LOCUS line"
                    )

                try:
                    length = int(
                        tokens[2]
                    )
                except ValueError:
                    raise Stage3ExecutionError(
                        "invalid GBFF LOCUS length"
                    ) from None

                if length <= 0:
                    raise Stage3ExecutionError(
                        "GBFF LOCUS length must be positive"
                    )

                topologies = [
                    token.lower()
                    for token in tokens
                    if token.lower()
                    in {
                        "linear",
                        "circular",
                    }
                ]

                if len(
                    topologies
                ) > 1:
                    raise Stage3ExecutionError(
                        "multiple topology tokens on GBFF LOCUS"
                    )

                topology = (
                    topologies[0]
                    if topologies
                    else "unspecified"
                )

                version = None
                in_record = True
                in_origin = False
                saw_origin = False
                origin_parts = []
                record_lines = [
                    clean_line
                ]

                continue

            if in_record:
                record_lines.append(
                    clean_line
                )

            if line.startswith(
                "VERSION"
            ):
                if not in_record:
                    raise Stage3ExecutionError(
                        "GBFF VERSION outside a LOCUS record"
                    )

                tokens = line.split()

                if len(tokens) < 2:
                    raise Stage3ExecutionError(
                        "malformed GBFF VERSION line"
                    )

                version = tokens[1]

            elif line.startswith(
                "ORIGIN"
            ):
                if not in_record:
                    raise Stage3ExecutionError(
                        "GBFF ORIGIN outside a LOCUS record"
                    )

                if in_origin:
                    raise Stage3ExecutionError(
                        "duplicate GBFF ORIGIN"
                    )

                in_origin = True
                saw_origin = True
                origin_parts = []

            elif line.startswith(
                "//"
            ):
                if not in_record:
                    raise Stage3ExecutionError(
                        "GBFF record terminator without LOCUS"
                    )

                if not version:
                    raise Stage3ExecutionError(
                        "GBFF record lacks VERSION"
                    )

                if not saw_origin:
                    raise Stage3ExecutionError(
                        "GBFF record lacks ORIGIN"
                    )

                if version in records:
                    raise Stage3ExecutionError(
                        "duplicate GBFF VERSION accession"
                    )

                sequence = (
                    "".join(
                        origin_parts
                    )
                    .upper()
                )

                if len(
                    sequence
                ) != length:
                    raise Stage3ExecutionError(
                        "GBFF ORIGIN length differs from LOCUS"
                    )

                definition = (
                    _definition_from_record(
                        record_lines
                    )
                )

                records[
                    version
                ] = GbffComponent(
                    length=length,
                    topology=topology,
                    definition=definition,
                )

                length = None
                topology = None
                version = None

                in_record = False
                in_origin = False
                saw_origin = False

                origin_parts = []
                record_lines = []

            elif in_origin:
                origin_parts.append(
                    "".join(
                        character
                        for character in line
                        if character.isalpha()
                    )
                )

    if in_record:
        raise Stage3ExecutionError(
            "unterminated GBFF record"
        )

    if not records:
        raise Stage3ExecutionError(
            "GBFF contains no records"
        )

    return records


def evaluate_stage3_candidate(
    *,
    candidate: CandidateAudit,
    component_rows: Sequence[ComponentAudit],
    package_manifest: Mapping[str, PackageFile],
    expected_source_evidence_sha256: str,
    historical_provider: (
        Callable[
            [str],
            source_chromosome_integrity.HistoricalReuseEvidence
            | None,
        ]
        | None
    ) = None,
) -> Stage3CandidateEvaluation:
    """Verify and evaluate one already-resolved Stage 3 candidate."""

    if not isinstance(
        candidate,
        CandidateAudit,
    ):
        raise Stage3ExecutionError(
            "candidate has unexpected type"
        )

    if (
        historical_provider is not None
        and not callable(
            historical_provider
        )
    ):
        raise Stage3ExecutionError(
            "historical evidence provider must be callable"
        )

    expected_source_sha = _lower_sha256(
        expected_source_evidence_sha256,
        label="expected Stage 1 source-evidence SHA256",
    )

    try:
        reconstructed = load_primary_components(
            candidate,
            component_rows,
            package_manifest,
        )

        observed_source_sha = source_evidence_sha256(
            candidate,
            component_rows,
            package_manifest,
        )
    except (
        ValueError,
        RuntimeError,
    ) as exc:
        raise Stage3ExecutionError(
            f"Stage 1 source-evidence verification failed: {exc}"
        ) from exc

    if observed_source_sha != expected_source_sha:
        raise Stage3ExecutionError(
            "Stage 1 source-evidence SHA256 mismatch"
        )

    component_by_accession: dict[
        str,
        ComponentAudit,
    ] = {}

    for component in component_rows:
        if not isinstance(
            component,
            ComponentAudit,
        ):
            raise Stage3ExecutionError(
                "component audit has unexpected type"
            )

        if component.accession != candidate.accession:
            raise Stage3ExecutionError(
                "component audit belongs to another candidate"
            )

        if component.component_accession in (
            component_by_accession
        ):
            raise Stage3ExecutionError(
                "duplicate component-audit accession"
            )

        component_by_accession[
            component.component_accession
        ] = component

    if set(
        component_by_accession
    ) != set(
        reconstructed
    ):
        raise Stage3ExecutionError(
            "Stage 1 reconstructed component set mismatch"
        )

    sequence_report_path = (
        _select_sequence_report(
            candidate=candidate,
            package_manifest=package_manifest,
        )
    )

    gbff_path = _select_gbff(
        candidate=candidate,
        package_manifest=package_manifest,
    )

    sequence_report = read_sequence_report(
        sequence_report_path,
        accession=candidate.accession,
    )

    gbff = read_gbff_records(
        gbff_path
    )

    if set(
        gbff
    ) != set(
        sequence_report
    ):
        raise Stage3ExecutionError(
            "GBFF components do not match sequence report"
        )

    primary = {
        component:
            record
        for component, record
        in sequence_report.items()
        if record.assembly_unit
        == "Primary Assembly"
    }

    if not primary:
        raise Stage3ExecutionError(
            "sequence report contains no Primary Assembly records"
        )

    if len(
        primary
    ) != candidate.primary_assembly_records:
        raise Stage3ExecutionError(
            "Primary Assembly component count mismatch"
        )

    if set(
        primary
    ) != set(
        component_by_accession
    ):
        raise Stage3ExecutionError(
            "Primary Assembly component set mismatch"
        )

    evidence = []

    for component in sorted(
        primary
    ):
        sequence_record = (
            primary[
                component
            ]
        )

        audit_record = (
            component_by_accession[
                component
            ]
        )

        gbff_record = (
            gbff[
                component
            ]
        )

        molecule_class = _nonempty_text(
            sequence_record.molecule_class,
            label=(
                "Primary Assembly molecule class"
            ),
        )

        if (
            sequence_record.length
            is not None
            and sequence_record.length
            != audit_record.length
        ):
            raise Stage3ExecutionError(
                "sequence-report component length "
                "differs from component audit"
            )

        if gbff_record.length != (
            audit_record.length
        ):
            raise Stage3ExecutionError(
                "GBFF component length differs "
                "from component audit"
            )

        if gbff_record.topology != (
            audit_record.topology
        ):
            raise Stage3ExecutionError(
                "GBFF topology differs from component audit"
            )

        evidence.append(
            source_chromosome_integrity.PrimaryComponentEvidence(
                molecule_class=molecule_class,
                topology=gbff_record.topology,
                definition=gbff_record.definition,
            )
        )

    frozen_components = tuple(
        evidence
    )

    try:
        trigger = (
            source_chromosome_integrity.assess_trigger(
                frozen_components
            )
        )
    except source_chromosome_integrity.ChromosomeIntegrityError as exc:
        raise Stage3ExecutionError(
            f"chromosome trigger assessment failed: {exc}"
        ) from exc

    if (
        trigger.closure_supported_chromosome_count
        + trigger.closure_unsupported_chromosome_count
        != trigger.chromosome_component_count
    ):
        raise Stage3ExecutionError(
            "chromosome trigger accounting mismatch"
        )

    historical = None

    if (
        trigger.triggered
        and historical_provider is not None
    ):
        try:
            historical = historical_provider(
                candidate.accession
            )
        except Stage3ExecutionError:
            raise
        except Exception as exc:
            raise Stage3ExecutionError(
                "historical evidence provider failed"
            ) from exc

        if (
            historical is not None
            and not isinstance(
                historical,
                source_chromosome_integrity.HistoricalReuseEvidence,
            )
        ):
            raise Stage3ExecutionError(
                "historical evidence provider returned "
                "unexpected type"
            )

    try:
        decision = (
            source_chromosome_integrity.evaluate(
                accession=candidate.accession,
                components=frozen_components,
                historical=historical,
            )
        )
    except source_chromosome_integrity.ChromosomeIntegrityError as exc:
        raise Stage3ExecutionError(
            f"chromosome-integrity evaluation failed: {exc}"
        ) from exc

    if decision.triggered != (
        trigger.triggered
    ):
        raise Stage3ExecutionError(
            "chromosome decision trigger disagrees "
            "with TriggerAssessment"
        )

    return Stage3CandidateEvaluation(
        accession=candidate.accession,
        source_evidence_sha256=observed_source_sha,
        primary_component_count=len(
            frozen_components
        ),
        trigger=trigger,
        decision=decision,
    )
