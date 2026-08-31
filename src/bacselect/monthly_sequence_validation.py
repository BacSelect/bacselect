"""Pure BacSelect monthly Stage 3 sequence-evidence validation.

This module validates an already hydrated NCBI Datasets package against the
identity-bearing monthly Stage 2 targets.

It performs no network retrieval, external process execution, environment lookup,
cache lookup, taxonomy, structural-feature calculation, or selector analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from bacselect.monthly_sequence_plan import (
    MonthlyFreshAcquisitionTarget,
)
from bacselect.source_eligibility import (
    BIOSAMPLE_RE,
    CANONICAL_GCA_RE,
)


IUPAC_DNA = frozenset(
    "ACGTRYSWKMBDHVN"
)

PRIMARY_DNA = frozenset(
    "ACGT"
)


CANDIDATE_AUDIT_FIELDS = (
    "canonical_genbank_assembly_accession",
    "expected_biosample",
    "observed_biosample",
    "assembly_status",
    "current_accession",
    "assembly_level",
    "sequence_report_records",
    "sequence_report_length_present_records",
    "sequence_report_length_missing_records",
    "sequence_report_length_missing_components",
    "primary_assembly_records",
    "auxiliary_assembly_records",
    "auxiliary_assembly_units",
    "auxiliary_component_accessions",
    "fasta_records",
    "gbff_records",
    "total_sequence_length",
    "package_total_sequence_length",
    "auxiliary_total_sequence_length",
    "topology_circular_records",
    "topology_linear_records",
    "topology_unspecified_records",
    "ambiguous_base_count",
    "ambiguous_symbols",
    "sequence_eligibility",
    "exclusion_reasons",
    "fasta_file",
    "fasta_sha256",
    "gbff_file",
    "gbff_sha256",
    "gbff_source",
    "gbff_provenance_file",
    "gbff_provenance_sha256",
    "sequence_report_sha256",
    "result",
)


COMPONENT_AUDIT_FIELDS = (
    "canonical_genbank_assembly_accession",
    "component_genbank_accession",
    "length",
    "topology",
    "ambiguous_base_count",
    "ambiguous_symbols",
    "sequence_sha256",
)


PACKAGE_FILE_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
)


class MonthlySequenceValidationError(
    ValueError
):
    """Raised when monthly sequence evidence fails closed."""


@dataclass(frozen=True)
class MonthlyValidatedPackage:
    """Validated Stage 3 package evidence."""

    candidate_rows: tuple[
        Mapping[str, str],
        ...,
    ]
    component_rows: tuple[
        Mapping[str, str],
        ...,
    ]
    package_file_rows: tuple[
        Mapping[str, str],
        ...,
    ]
    assembly_data_report: Path


def sha256_file(
    path: Path,
    block_size: int = 1024 * 1024,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(block_size),
            b"",
        ):
            digest.update(
                block
            )

    return digest.hexdigest()


def sha256_text(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def jsonl_records(
    path: Path,
) -> tuple[Mapping[str, object], ...]:
    records: list[
        Mapping[str, object]
    ] = []

    with path.open(
        encoding="utf-8",
    ) as handle:
        for line_number, line in enumerate(
            handle,
            1,
        ):
            if not line.strip():
                raise MonthlySequenceValidationError(
                    f"{path}: blank JSONL line "
                    f"{line_number}"
                )

            try:
                obj = json.loads(
                    line
                )
            except json.JSONDecodeError as exc:
                raise MonthlySequenceValidationError(
                    f"{path}: invalid JSONL line "
                    f"{line_number}: {exc}"
                ) from exc

            if not isinstance(
                obj,
                dict,
            ):
                raise MonthlySequenceValidationError(
                    f"{path}: JSONL line "
                    f"{line_number} is not an object"
                )

            records.append(
                obj
            )

    if not records:
        raise MonthlySequenceValidationError(
            f"{path}: no JSON records"
        )

    return tuple(
        records
    )


def value(
    obj: Mapping[str, object],
    *names: str,
) -> object | None:
    for name in names:
        if name in obj:
            return obj[
                name
            ]

    return None


def _validate_targets(
    targets: Iterable[
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
        raise MonthlySequenceValidationError(
            "monthly Stage 3 target set is empty"
        )

    accessions: list[str] = []
    seen: set[str] = set()

    for target in values:
        accession = (
            target.canonical_genbank_assembly_accession
        )

        if CANONICAL_GCA_RE.fullmatch(
            accession
        ) is None:
            raise MonthlySequenceValidationError(
                "monthly Stage 3 target has invalid "
                "canonical GCA accession"
            )

        if BIOSAMPLE_RE.fullmatch(
            target.source_biosample
        ) is None:
            raise MonthlySequenceValidationError(
                f"{accession}: invalid source BioSample"
            )

        if accession in seen:
            raise MonthlySequenceValidationError(
                "duplicate accession in monthly Stage 3 targets"
            )

        seen.add(
            accession
        )
        accessions.append(
            accession
        )

    if accessions != sorted(
        accessions
    ):
        raise MonthlySequenceValidationError(
            "monthly Stage 3 targets must be "
            "lexicographically sorted"
        )

    return values


def validate_metadata(
    package: Path,
    targets: Sequence[
        MonthlyFreshAcquisitionTarget
    ],
) -> tuple[
    Path,
    Mapping[str, str],
    Path,
]:
    """Validate Datasets assembly metadata against Stage 2 identity."""

    target_values = _validate_targets(
        targets
    )

    data_root = (
        package
        / "ncbi_dataset"
        / "data"
    )

    if not data_root.is_dir():
        raise MonthlySequenceValidationError(
            "hydrated package lacks ncbi_dataset/data"
        )

    report = (
        data_root
        / "assembly_data_report.jsonl"
    )

    if not report.is_file():
        raise MonthlySequenceValidationError(
            "hydrated package lacks "
            "assembly_data_report.jsonl"
        )

    expected = {
        target.canonical_genbank_assembly_accession:
            target.source_biosample
        for target in target_values
    }

    observed: dict[
        str,
        str,
    ] = {}

    for obj in jsonl_records(
        report
    ):
        accession_obj = value(
            obj,
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
            raise MonthlySequenceValidationError(
                "invalid accession in assembly report: "
                f"{accession_obj!r}"
            )

        if accession in observed:
            raise MonthlySequenceValidationError(
                "duplicate assembly-report accession: "
                f"{accession}"
            )

        info_obj = (
            obj.get(
                "assemblyInfo"
            )
            or obj.get(
                "assembly_info"
            )
            or {}
        )

        if not isinstance(
            info_obj,
            Mapping,
        ):
            raise MonthlySequenceValidationError(
                f"{accession}: malformed assemblyInfo"
            )

        status = value(
            info_obj,
            "assemblyStatus",
            "assembly_status",
        )

        current = value(
            obj,
            "currentAccession",
            "current_accession",
        )

        level = value(
            info_obj,
            "assemblyLevel",
            "assembly_level",
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
            raise MonthlySequenceValidationError(
                f"{accession}: malformed BioSample metadata"
            )

        biosample = value(
            biosample_obj,
            "accession",
        )

        if accession not in expected:
            raise MonthlySequenceValidationError(
                "assembly report contains unexpected "
                f"accession {accession}"
            )

        if biosample != expected[
            accession
        ]:
            raise MonthlySequenceValidationError(
                f"{accession}: BioSample mismatch; "
                f"expected {expected[accession]!r}, "
                f"got {biosample!r}"
            )

        if status != "current":
            raise MonthlySequenceValidationError(
                f"{accession}: assembly status "
                f"is not current: {status!r}"
            )

        if current != accession:
            raise MonthlySequenceValidationError(
                f"{accession}: currentAccession "
                f"mismatch: {current!r}"
            )

        if level != "Complete Genome":
            raise MonthlySequenceValidationError(
                f"{accession}: assembly level "
                "is not Complete Genome: "
                f"{level!r}"
            )

        observed[
            accession
        ] = str(
            biosample
        )

    if set(observed) != set(
        expected
    ):
        missing = sorted(
            set(expected)
            - set(observed)
        )

        extra = sorted(
            set(observed)
            - set(expected)
        )

        raise MonthlySequenceValidationError(
            "assembly data report does not "
            "exactly match target set; "
            f"missing={missing!r}; extra={extra!r}"
        )

    return (
        data_root,
        observed,
        report,
    )


def read_fasta(
    path: Path,
) -> Mapping[str, str]:
    sequences: dict[
        str,
        str,
    ] = {}

    identifier: str | None = None
    chunks: list[str] = []

    def store() -> None:
        nonlocal identifier
        nonlocal chunks

        if identifier is None:
            return

        if identifier in sequences:
            raise MonthlySequenceValidationError(
                f"{path}: duplicate FASTA identifier "
                f"{identifier!r}"
            )

        sequence = "".join(
            chunks
        ).upper()

        if not sequence:
            raise MonthlySequenceValidationError(
                f"{path}: empty FASTA sequence "
                f"{identifier!r}"
            )

        invalid = (
            set(sequence)
            - IUPAC_DNA
        )

        if invalid:
            raise MonthlySequenceValidationError(
                f"{path}: unsupported nucleotide symbols "
                f"in {identifier}: {sorted(invalid)!r}"
            )

        sequences[
            identifier
        ] = sequence

    with path.open(
        encoding="utf-8",
    ) as handle:
        for line_number, line in enumerate(
            handle,
            1,
        ):
            if line.startswith(
                ">"
            ):
                store()

                header = (
                    line[1:]
                    .strip()
                )

                if not header:
                    raise MonthlySequenceValidationError(
                        f"{path}: empty FASTA header "
                        f"at line {line_number}"
                    )

                identifier = (
                    header.split()[0]
                )

                chunks = []

            else:
                sequence = "".join(
                    line.split()
                )

                if not sequence:
                    continue

                if identifier is None:
                    raise MonthlySequenceValidationError(
                        f"{path}: sequence before "
                        "first FASTA header"
                    )

                chunks.append(
                    sequence
                )

    store()

    if not sequences:
        raise MonthlySequenceValidationError(
            f"{path}: no FASTA records"
        )

    return sequences


def read_gbff_records(
    path: Path,
) -> Mapping[
    str,
    Mapping[str, object],
]:
    records: dict[
        str,
        Mapping[str, object],
    ] = {}

    length: int | None = None
    topology: str | None = None
    version: str | None = None

    in_record = False
    in_origin = False
    saw_origin = False

    origin_parts: list[str] = []

    with path.open(
        encoding="utf-8",
        errors="strict",
    ) as handle:
        for line_number, line in enumerate(
            handle,
            1,
        ):
            if line.startswith(
                "LOCUS"
            ):
                if in_record:
                    raise MonthlySequenceValidationError(
                        f"{path}: LOCUS before "
                        "previous record ended"
                    )

                tokens = line.split()

                if len(tokens) < 3:
                    raise MonthlySequenceValidationError(
                        f"{path}: malformed LOCUS "
                        f"line {line_number}"
                    )

                try:
                    length = int(
                        tokens[2]
                    )
                except ValueError as exc:
                    raise MonthlySequenceValidationError(
                        f"{path}: invalid LOCUS length "
                        f"at line {line_number}"
                    ) from exc

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
                    raise MonthlySequenceValidationError(
                        f"{path}: multiple topology tokens "
                        f"on LOCUS line {line_number}"
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

            elif line.startswith(
                "VERSION"
            ):
                if not in_record:
                    raise MonthlySequenceValidationError(
                        f"{path}: VERSION outside "
                        "a LOCUS record"
                    )

                tokens = line.split()

                if len(tokens) < 2:
                    raise MonthlySequenceValidationError(
                        f"{path}: malformed VERSION "
                        f"line {line_number}"
                    )

                version = (
                    tokens[1]
                )

            elif line.startswith(
                "ORIGIN"
            ):
                if not in_record:
                    raise MonthlySequenceValidationError(
                        f"{path}: ORIGIN outside "
                        "a LOCUS record"
                    )

                if in_origin:
                    raise MonthlySequenceValidationError(
                        f"{path}: duplicate ORIGIN "
                        f"at line {line_number}"
                    )

                in_origin = True
                saw_origin = True
                origin_parts = []

            elif line.startswith(
                "//"
            ):
                if not in_record:
                    raise MonthlySequenceValidationError(
                        f"{path}: record terminator "
                        "without LOCUS"
                    )

                if not version:
                    raise MonthlySequenceValidationError(
                        f"{path}: GBFF record lacks VERSION"
                    )

                if not saw_origin:
                    raise MonthlySequenceValidationError(
                        f"{path}: GBFF record "
                        f"{version!r} lacks ORIGIN"
                    )

                if version in records:
                    raise MonthlySequenceValidationError(
                        f"{path}: duplicate GBFF VERSION "
                        f"{version}"
                    )

                sequence = (
                    "".join(
                        origin_parts
                    )
                    .upper()
                )

                if length is None:
                    raise MonthlySequenceValidationError(
                        f"{path}: missing LOCUS length"
                    )

                if len(
                    sequence
                ) != length:
                    raise MonthlySequenceValidationError(
                        f"{path}: GBFF ORIGIN length "
                        f"for {version!r} is "
                        f"{len(sequence)}, but LOCUS "
                        f"reports {length}"
                    )

                records[
                    version
                ] = {
                    "length":
                        length,
                    "topology":
                        topology,
                    "sequence":
                        sequence,
                }

                length = None
                topology = None
                version = None
                in_record = False
                in_origin = False
                saw_origin = False
                origin_parts = []

            elif in_origin:
                origin_parts.append(
                    "".join(
                        character
                        for character in line
                        if character.isalpha()
                    )
                )

    if in_record:
        raise MonthlySequenceValidationError(
            f"{path}: unterminated GBFF record"
        )

    if not records:
        raise MonthlySequenceValidationError(
            f"{path}: no GBFF records"
        )

    return records


def validate_candidate_payload(
    data_root: Path,
    target: MonthlyFreshAcquisitionTarget,
    observed_biosample: str,
) -> tuple[
    Mapping[str, str],
    tuple[Mapping[str, str], ...],
]:
    """Validate one complete local Datasets payload.

    Unlike the historical validation executor, this function performs no EFetch
    fallback. Missing GBFF evidence fails closed.
    """

    accession = (
        target.canonical_genbank_assembly_accession
    )

    if observed_biosample != target.source_biosample:
        raise MonthlySequenceValidationError(
            f"{accession}: observed BioSample "
            "does not match Stage 2 expectation"
        )

    acc_dir = (
        data_root
        / accession
    )

    if not acc_dir.is_dir():
        raise MonthlySequenceValidationError(
            f"{accession}: missing hydrated "
            "accession directory"
        )

    sequence_report = (
        acc_dir
        / "sequence_report.jsonl"
    )

    if not sequence_report.is_file():
        raise MonthlySequenceValidationError(
            f"{accession}: missing "
            "sequence_report.jsonl"
        )

    seq_rows = jsonl_records(
        sequence_report
    )

    sequence_report_lengths: dict[
        str,
        int | None,
    ] = {}

    primary_components: set[str] = set()

    auxiliary_components: dict[
        str,
        str,
    ] = {}

    for row in seq_rows:
        returned = value(
            row,
            "assemblyAccession",
            "assembly_accession",
        )

        if returned != accession:
            raise MonthlySequenceValidationError(
                f"{accession}: sequence report "
                f"returned accession {returned!r}"
            )

        unit = value(
            row,
            "assemblyUnit",
            "assembly_unit",
        )

        if not unit:
            raise MonthlySequenceValidationError(
                f"{accession}: sequence report "
                "record lacks assembly unit"
            )

        component_obj = value(
            row,
            "genbankAccession",
            "genbank_accession",
        )

        if not isinstance(
            component_obj,
            str,
        ) or not component_obj:
            raise MonthlySequenceValidationError(
                f"{accession}: sequence report "
                "record lacks GenBank accession"
            )

        component = (
            component_obj
        )

        if component in sequence_report_lengths:
            raise MonthlySequenceValidationError(
                f"{accession}: duplicate component "
                f"accession {component!r}"
            )

        raw_length = value(
            row,
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
            ) as exc:
                raise MonthlySequenceValidationError(
                    f"{accession}: invalid component "
                    f"length {raw_length!r}"
                ) from exc

        sequence_report_lengths[
            component
        ] = component_length

        if unit == "Primary Assembly":
            primary_components.add(
                component
            )
        else:
            auxiliary_components[
                component
            ] = str(
                unit
            )

    if not primary_components:
        raise MonthlySequenceValidationError(
            f"{accession}: sequence report contains "
            "no Primary Assembly records"
        )

    missing_length_components = sorted(
        component
        for component, component_length
        in sequence_report_lengths.items()
        if component_length is None
    )

    present_length_records = (
        len(
            sequence_report_lengths
        )
        - len(
            missing_length_components
        )
    )

    all_fasta_files = sorted(
        acc_dir.glob(
            "*.fna"
        )
    )

    derived_fasta_files = {
        path
        for path in all_fasta_files
        if path.name.endswith(
            (
                "_cds_from_genomic.fna",
                "_rna_from_genomic.fna",
            )
        )
    }

    fasta_files = [
        path
        for path in all_fasta_files
        if path not in derived_fasta_files
    ]

    if len(
        fasta_files
    ) != 1:
        raise MonthlySequenceValidationError(
            f"{accession}: expected exactly one "
            "genomic FASTA after excluding NCBI "
            "CDS/RNA derived FASTAs, found "
            f"{len(fasta_files)}"
        )

    efetch_gbff = (
        acc_dir
        / f"{accession}_efetch_components.gbff"
    )

    efetch_provenance = (
        acc_dir
        / f"{accession}_efetch_components.json"
    )

    if (
        efetch_gbff.exists()
        or efetch_provenance.exists()
    ):
        raise MonthlySequenceValidationError(
            f"{accession}: EFetch fallback evidence "
            "is not permitted in monthly Stage 3 "
            "pure validation"
        )

    gbff_files = sorted(
        acc_dir.glob(
            "*.gbff"
        )
    )

    if len(
        gbff_files
    ) != 1:
        raise MonthlySequenceValidationError(
            f"{accession}: expected exactly one "
            "NCBI Datasets GBFF, found "
            f"{len(gbff_files)}"
        )

    fasta = (
        fasta_files[0]
    )

    gbff = (
        gbff_files[0]
    )

    if fasta.stat().st_size <= 0:
        raise MonthlySequenceValidationError(
            f"{accession}: genomic FASTA is empty"
        )

    if gbff.stat().st_size <= 0:
        raise MonthlySequenceValidationError(
            f"{accession}: GBFF is empty"
        )

    sequences = read_fasta(
        fasta
    )

    fasta_lengths = {
        component:
            len(sequence)
        for component, sequence
        in sequences.items()
    }

    if set(
        fasta_lengths
    ) != set(
        sequence_report_lengths
    ):
        raise MonthlySequenceValidationError(
            f"{accession}: FASTA components do not "
            "match sequence report"
        )

    gbff_records = read_gbff_records(
        gbff
    )

    gbff_lengths = {
        component:
            int(
                row["length"]
            )
        for component, row
        in gbff_records.items()
    }

    if set(
        gbff_lengths
    ) != set(
        sequence_report_lengths
    ):
        raise MonthlySequenceValidationError(
            f"{accession}: GBFF components do not "
            "match sequence report"
        )

    if fasta_lengths != gbff_lengths:
        raise MonthlySequenceValidationError(
            f"{accession}: FASTA and GBFF component "
            "lengths do not agree"
        )

    for component in sorted(
        fasta_lengths
    ):
        if (
            sequences[
                component
            ]
            != gbff_records[
                component
            ][
                "sequence"
            ]
        ):
            raise MonthlySequenceValidationError(
                f"{accession}: FASTA and GBFF ORIGIN "
                "sequences differ for "
                f"{component!r}"
            )

    for component, reported_length in (
        sequence_report_lengths.items()
    ):
        if reported_length is None:
            continue

        observed_length = (
            fasta_lengths[
                component
            ]
        )

        if observed_length != reported_length:
            raise MonthlySequenceValidationError(
                f"{accession}: sequence report length "
                f"for {component!r} is "
                f"{reported_length}, but FASTA and "
                f"GBFF agree on {observed_length}"
            )

    package_total_length = sum(
        len(
            sequence
        )
        for sequence in sequences.values()
    )

    auxiliary_total_length = sum(
        fasta_lengths[
            component
        ]
        for component
        in auxiliary_components
    )

    component_rows: list[
        Mapping[str, str]
    ] = []

    ambiguous_total = 0
    ambiguous_symbols_all: set[str] = set()

    circular = 0
    linear = 0
    unspecified = 0

    total_length = 0

    for component in sorted(
        primary_components
    ):
        sequence = (
            sequences[
                component
            ]
        )

        topology = str(
            gbff_records[
                component
            ][
                "topology"
            ]
        )

        if topology == "circular":
            circular += 1
        elif topology == "linear":
            linear += 1
        elif topology == "unspecified":
            unspecified += 1
        else:
            raise MonthlySequenceValidationError(
                f"{accession}: impossible topology "
                f"{topology!r}"
            )

        ambiguous_symbols = (
            set(sequence)
            - PRIMARY_DNA
        )

        ambiguous_count = sum(
            1
            for base in sequence
            if base not in PRIMARY_DNA
        )

        ambiguous_total += (
            ambiguous_count
        )

        ambiguous_symbols_all.update(
            ambiguous_symbols
        )

        total_length += len(
            sequence
        )

        component_rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "component_genbank_accession":
                    component,
                "length":
                    str(
                        len(
                            sequence
                        )
                    ),
                "topology":
                    topology,
                "ambiguous_base_count":
                    str(
                        ambiguous_count
                    ),
                "ambiguous_symbols":
                    (
                        ",".join(
                            sorted(
                                ambiguous_symbols
                            )
                        )
                        if ambiguous_symbols
                        else "none"
                    ),
                "sequence_sha256":
                    sha256_text(
                        sequence
                    ),
            }
        )

    exclusion_reasons: list[str] = []

    if ambiguous_total:
        exclusion_reasons.append(
            "ambiguous_nucleotide"
        )

    if unspecified:
        exclusion_reasons.append(
            "unresolved_topology"
        )

    eligible = not (
        exclusion_reasons
    )

    candidate_row = {
        "canonical_genbank_assembly_accession":
            accession,
        "expected_biosample":
            target.source_biosample,
        "observed_biosample":
            observed_biosample,
        "assembly_status":
            "current",
        "current_accession":
            accession,
        "assembly_level":
            "Complete Genome",
        "sequence_report_records":
            str(
                len(
                    seq_rows
                )
            ),
        "sequence_report_length_present_records":
            str(
                present_length_records
            ),
        "sequence_report_length_missing_records":
            str(
                len(
                    missing_length_components
                )
            ),
        "sequence_report_length_missing_components":
            (
                "|".join(
                    missing_length_components
                )
                if missing_length_components
                else "none"
            ),
        "primary_assembly_records":
            str(
                len(
                    primary_components
                )
            ),
        "auxiliary_assembly_records":
            str(
                len(
                    auxiliary_components
                )
            ),
        "auxiliary_assembly_units":
            (
                "|".join(
                    sorted(
                        set(
                            auxiliary_components.values()
                        )
                    )
                )
                if auxiliary_components
                else "none"
            ),
        "auxiliary_component_accessions":
            (
                "|".join(
                    sorted(
                        auxiliary_components
                    )
                )
                if auxiliary_components
                else "none"
            ),
        "fasta_records":
            str(
                len(
                    sequences
                )
            ),
        "gbff_records":
            str(
                len(
                    gbff_records
                )
            ),
        "total_sequence_length":
            str(
                total_length
            ),
        "package_total_sequence_length":
            str(
                package_total_length
            ),
        "auxiliary_total_sequence_length":
            str(
                auxiliary_total_length
            ),
        "topology_circular_records":
            str(
                circular
            ),
        "topology_linear_records":
            str(
                linear
            ),
        "topology_unspecified_records":
            str(
                unspecified
            ),
        "ambiguous_base_count":
            str(
                ambiguous_total
            ),
        "ambiguous_symbols":
            (
                ",".join(
                    sorted(
                        ambiguous_symbols_all
                    )
                )
                if ambiguous_symbols_all
                else "none"
            ),
        "sequence_eligibility":
            (
                "eligible"
                if eligible
                else "ineligible"
            ),
        "exclusion_reasons":
            (
                "|".join(
                    exclusion_reasons
                )
                if exclusion_reasons
                else "none"
            ),
        "fasta_file":
            fasta.name,
        "fasta_sha256":
            sha256_file(
                fasta
            ),
        "gbff_file":
            gbff.name,
        "gbff_sha256":
            sha256_file(
                gbff
            ),
        "gbff_source":
            "ncbi_datasets",
        "gbff_provenance_file":
            "none",
        "gbff_provenance_sha256":
            "none",
        "sequence_report_sha256":
            sha256_file(
                sequence_report
            ),
        "result":
            "PASS",
    }

    return (
        candidate_row,
        tuple(
            component_rows
        ),
    )


def package_file_manifest(
    package: Path,
) -> tuple[
    Mapping[str, str],
    ...,
]:
    rows: list[
        Mapping[str, str]
    ] = []

    for path in sorted(
        item
        for item in package.rglob(
            "*"
        )
        if item.is_file()
    ):
        relative = (
            path.relative_to(
                package
            )
            .as_posix()
        )

        rows.append(
            {
                "path":
                    relative,
                "size_bytes":
                    str(
                        path.stat().st_size
                    ),
                "sha256":
                    sha256_file(
                        path
                    ),
            }
        )

    return tuple(
        rows
    )


def validate_hydrated_package(
    package: Path,
    targets: Iterable[
        MonthlyFreshAcquisitionTarget
    ],
) -> MonthlyValidatedPackage:
    """Validate a complete already hydrated monthly Stage 3 package."""

    target_values = _validate_targets(
        targets
    )

    (
        data_root,
        observed_biosamples,
        assembly_report,
    ) = validate_metadata(
        package,
        target_values,
    )

    candidate_rows: list[
        Mapping[str, str]
    ] = []

    component_rows: list[
        Mapping[str, str]
    ] = []

    for target in target_values:
        accession = (
            target.canonical_genbank_assembly_accession
        )

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

        candidate_rows.append(
            candidate
        )

        component_rows.extend(
            components
        )

    observed_accessions = tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in candidate_rows
    )

    expected_accessions = tuple(
        target.canonical_genbank_assembly_accession
        for target in target_values
    )

    if observed_accessions != expected_accessions:
        raise MonthlySequenceValidationError(
            "candidate audit does not preserve "
            "Stage 2 target accession order"
        )

    return MonthlyValidatedPackage(
        candidate_rows=tuple(
            candidate_rows
        ),
        component_rows=tuple(
            component_rows
        ),
        package_file_rows=(
            package_file_manifest(
                package
            )
        ),
        assembly_data_report=(
            assembly_report
        ),
    )
