"""Recovery primitives for a Datasets package with an omitted requested GBFF."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Mapping, Sequence

from bacselect import monthly_sequence_validation as monthly


EFETCH_ENDPOINT = (
    "https://eutils.ncbi.nlm.nih.gov/"
    "entrez/eutils/efetch.fcgi"
)

EFETCH_SOURCE = "ncbi_efetch_nuccore"

MISSING_DATASETS_GBFF_SUFFIX = (
    "expected exactly one NCBI Datasets GBFF, found 0"
)


class MonthlyMissingDatasetsGbffRecoveryError(
    RuntimeError
):
    """Raised when missing-GBFF recovery evidence fails closed."""


@dataclass(frozen=True)
class MissingDatasetsGbffRecoveryTarget:
    accession: str
    observed_biosample: str
    component_accessions: tuple[str, ...]
    fetch_destinations: tuple[str, ...]


def _fail(
    message: str,
) -> None:
    raise MonthlyMissingDatasetsGbffRecoveryError(
        message
    )


def _sequence_report_components(
    sequence_report: Path,
    accession: str,
) -> tuple[str, ...]:
    if (
        not sequence_report.is_file()
        or sequence_report.stat().st_size <= 0
    ):
        _fail(
            f"{accession}: sequence report "
            "is missing or empty"
        )

    components: list[str] = []

    try:
        rows = monthly.jsonl_records(
            sequence_report
        )
    except Exception as exc:
        raise MonthlyMissingDatasetsGbffRecoveryError(
            f"{accession}: sequence report "
            "could not be parsed"
        ) from exc

    for row in rows:
        returned = monthly.value(
            row,
            "assemblyAccession",
            "assembly_accession",
        )

        if returned != accession:
            _fail(
                f"{accession}: sequence report "
                f"returned accession {returned!r}"
            )

        component = monthly.value(
            row,
            "genbankAccession",
            "genbank_accession",
        )

        if (
            not isinstance(
                component,
                str,
            )
            or not component
        ):
            _fail(
                f"{accession}: sequence report "
                "record lacks GenBank accession"
            )

        components.append(
            component
        )

    if not components:
        _fail(
            f"{accession}: sequence report "
            "contains no GenBank components"
        )

    if len(set(components)) != len(
        components
    ):
        _fail(
            f"{accession}: sequence report "
            "contains duplicate GenBank components"
        )

    return tuple(
        sorted(
            components
        )
    )


def _fetch_destinations_for_accession(
    package: Path,
    accession: str,
) -> tuple[str, ...]:
    fetch = (
        package
        / "ncbi_dataset"
        / "fetch.txt"
    )

    if not fetch.is_file():
        _fail(
            f"{accession}: preserved package "
            "lacks fetch.txt"
        )

    destinations: list[str] = []

    try:
        with fetch.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            reader = csv.reader(
                handle,
                delimiter="\t",
            )

            for row in reader:
                if not row:
                    continue

                destination = (
                    row[-1].strip()
                )

                if not destination:
                    continue

                pure = PurePosixPath(
                    destination
                )

                if (
                    pure.is_absolute()
                    or ".." in pure.parts
                ):
                    _fail(
                        f"{accession}: unsafe "
                        "fetch destination"
                    )

                if accession not in pure.parts:
                    continue

                destinations.append(
                    destination
                )

    except UnicodeError as exc:
        raise MonthlyMissingDatasetsGbffRecoveryError(
            f"{accession}: fetch.txt is not "
            "valid UTF-8"
        ) from exc

    if not destinations:
        _fail(
            f"{accession}: fetch.txt contains "
            "no accession destinations"
        )

    return tuple(
        sorted(
            destinations
        )
    )


def _inspect_manifest_omission(
    package: Path,
    data_root: Path,
    accession: str,
    observed_biosample: str,
) -> MissingDatasetsGbffRecoveryTarget:
    acc_dir = (
        data_root
        / accession
    )

    if not acc_dir.is_dir():
        _fail(
            f"{accession}: accession directory "
            "is missing"
        )

    sequence_report = (
        acc_dir
        / "sequence_report.jsonl"
    )

    all_fasta = sorted(
        acc_dir.glob(
            "*.fna"
        )
    )

    derived_fasta = {
        path
        for path in all_fasta
        if path.name.endswith(
            (
                "_cds_from_genomic.fna",
                "_rna_from_genomic.fna",
            )
        )
    }

    genomic_fasta = [
        path
        for path in all_fasta
        if path not in derived_fasta
    ]

    if len(genomic_fasta) != 1:
        _fail(
            f"{accession}: recovery trigger "
            "requires exactly one genomic FASTA"
        )

    if genomic_fasta[0].stat().st_size <= 0:
        _fail(
            f"{accession}: recovery trigger "
            "genomic FASTA is empty"
        )

    datasets_gbff = sorted(
        path
        for path in acc_dir.glob(
            "*.gbff"
        )
        if path.name
        != f"{accession}_efetch_components.gbff"
    )

    if datasets_gbff:
        _fail(
            f"{accession}: recovery trigger "
            "requires zero Datasets GBFF files"
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
        _fail(
            f"{accession}: preserved source "
            "already contains EFetch evidence"
        )

    components = (
        _sequence_report_components(
            sequence_report,
            accession,
        )
    )

    destinations = (
        _fetch_destinations_for_accession(
            package,
            accession,
        )
    )

    gbff_destinations = [
        destination
        for destination in destinations
        if destination.lower().endswith(
            (
                ".gbff",
                ".gbff.gz",
            )
        )
    ]

    if gbff_destinations:
        _fail(
            f"{accession}: fetch manifest "
            "contains a GBFF destination; "
            "this is hydration failure, not "
            "manifest omission"
        )

    fetch_root = (
        package
        / "ncbi_dataset"
    )

    for destination in destinations:
        pure = PurePosixPath(
            destination
        )

        local = fetch_root.joinpath(
            *pure.parts
        )

        if (
            not local.is_file()
            or local.stat().st_size <= 0
        ):
            _fail(
                f"{accession}: fetch destination "
                "is not completely hydrated: "
                f"{destination}"
            )

    return (
        MissingDatasetsGbffRecoveryTarget(
            accession=accession,
            observed_biosample=(
                observed_biosample
            ),
            component_accessions=(
                components
            ),
            fetch_destinations=(
                destinations
            ),
        )
    )


def detect_missing_datasets_gbff_targets(
    package: Path,
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
) -> tuple[
    MissingDatasetsGbffRecoveryTarget,
    ...,
]:
    """Detect only the prospectively frozen missing-manifest-GBFF class."""

    target_values = tuple(
        targets
    )

    try:
        (
            data_root,
            observed_biosamples,
            _,
        ) = monthly.validate_metadata(
            package,
            target_values,
        )
    except Exception as exc:
        raise MonthlyMissingDatasetsGbffRecoveryError(
            "package metadata validation failed"
        ) from exc

    recovery_targets: list[
        MissingDatasetsGbffRecoveryTarget
    ] = []

    for target in target_values:
        accession = (
            target
            .canonical_genbank_assembly_accession
        )

        observed = (
            observed_biosamples[
                accession
            ]
        )

        try:
            monthly.validate_candidate_payload(
                data_root,
                target,
                observed,
            )

        except monthly.MonthlySequenceValidationError as exc:
            expected_suffix = (
                f"{accession}: "
                + MISSING_DATASETS_GBFF_SUFFIX
            )

            if str(exc) != expected_suffix:
                raise MonthlyMissingDatasetsGbffRecoveryError(
                    f"{accession}: candidate failure "
                    "is outside the frozen recovery class: "
                    f"{exc}"
                ) from exc

            recovery_targets.append(
                _inspect_manifest_omission(
                    package,
                    data_root,
                    accession,
                    observed,
                )
            )

    return tuple(
        recovery_targets
    )


def _load_efetch_provenance(
    provenance: Path,
    gbff: Path,
    accession: str,
    component_accessions: tuple[
        str,
        ...,
    ],
) -> Mapping[str, object]:
    if (
        not provenance.is_file()
        or provenance.stat().st_size <= 0
    ):
        _fail(
            f"{accession}: EFetch provenance "
            "is missing or empty"
        )

    try:
        payload = json.loads(
            provenance.read_text(
                encoding="utf-8"
            )
        )
    except (
        json.JSONDecodeError,
        UnicodeError,
        OSError,
    ) as exc:
        raise MonthlyMissingDatasetsGbffRecoveryError(
            f"{accession}: invalid EFetch "
            "provenance"
        ) from exc

    if not isinstance(
        payload,
        Mapping,
    ):
        _fail(
            f"{accession}: EFetch provenance "
            "is not a JSON object"
        )

    required_exact = {
        "schema_version":
            1,
        "retrieval_method":
            EFETCH_SOURCE,
        "endpoint":
            EFETCH_ENDPOINT,
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
                component_accessions
            ),
        "requested_component_count":
            len(
                component_accessions
            ),
    }

    for key, expected in (
        required_exact.items()
    ):
        if payload.get(key) != expected:
            _fail(
                f"{accession}: EFetch provenance "
                f"{key!r} mismatch"
            )

    observed_sha = (
        monthly.sha256_file(
            gbff
        )
    )

    if (
        payload.get(
            "combined_gbff_sha256"
        )
        != observed_sha
    ):
        _fail(
            f"{accession}: EFetch GBFF SHA256 "
            "does not match provenance"
        )

    if (
        payload.get(
            "combined_gbff_size_bytes"
        )
        != gbff.stat().st_size
    ):
        _fail(
            f"{accession}: EFetch GBFF size "
            "does not match provenance"
        )

    chunk_size = payload.get(
        "chunk_size"
    )

    chunk_count = payload.get(
        "chunk_count"
    )

    chunks = payload.get(
        "chunks"
    )

    if (
        isinstance(
            chunk_size,
            bool,
        )
        or not isinstance(
            chunk_size,
            int,
        )
        or chunk_size <= 0
    ):
        _fail(
            f"{accession}: invalid EFetch "
            "chunk size"
        )

    if (
        isinstance(
            chunk_count,
            bool,
        )
        or not isinstance(
            chunk_count,
            int,
        )
        or chunk_count <= 0
    ):
        _fail(
            f"{accession}: invalid EFetch "
            "chunk count"
        )

    if (
        not isinstance(
            chunks,
            list,
        )
        or len(chunks) != chunk_count
    ):
        _fail(
            f"{accession}: EFetch chunk "
            "provenance mismatch"
        )

    flattened: list[str] = []

    for expected_index, chunk in enumerate(
        chunks,
        1,
    ):
        if not isinstance(
            chunk,
            Mapping,
        ):
            _fail(
                f"{accession}: malformed "
                "EFetch chunk provenance"
            )

        if (
            chunk.get(
                "chunk_index"
            )
            != expected_index
        ):
            _fail(
                f"{accession}: EFetch chunk "
                "index mismatch"
            )

        requested = chunk.get(
            "requested_component_accessions"
        )

        if (
            not isinstance(
                requested,
                list,
            )
            or not requested
            or not all(
                isinstance(
                    value,
                    str,
                )
                and value
                for value in requested
            )
        ):
            _fail(
                f"{accession}: invalid EFetch "
                "chunk component list"
            )

        flattened.extend(
            requested
        )

        response_size = chunk.get(
            "response_size_bytes"
        )

        if (
            isinstance(
                response_size,
                bool,
            )
            or not isinstance(
                response_size,
                int,
            )
            or response_size <= 0
        ):
            _fail(
                f"{accession}: invalid EFetch "
                "chunk response size"
            )

        response_sha = chunk.get(
            "response_sha256"
        )

        if (
            not isinstance(
                response_sha,
                str,
            )
            or len(response_sha) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character
                in response_sha
            )
        ):
            _fail(
                f"{accession}: invalid EFetch "
                "chunk response SHA256"
            )

    if flattened != list(
        component_accessions
    ):
        _fail(
            f"{accession}: EFetch chunk "
            "component population mismatch"
        )

    retrieved_at = payload.get(
        "retrieved_at_utc"
    )

    if (
        not isinstance(
            retrieved_at,
            str,
        )
        or not retrieved_at
    ):
        _fail(
            f"{accession}: EFetch provenance "
            "lacks retrieval timestamp"
        )

    return payload


def validate_recovered_candidate(
    data_root: Path,
    target: monthly.MonthlyFreshAcquisitionTarget,
    observed_biosample: str,
) -> tuple[
    Mapping[str, str],
    tuple[
        Mapping[str, str],
        ...,
    ],
]:
    """Apply the unchanged monthly science to explicit EFetch evidence."""

    accession = (
        target
        .canonical_genbank_assembly_accession
    )

    acc_dir = (
        data_root
        / accession
    )

    if not acc_dir.is_dir():
        _fail(
            f"{accession}: recovery accession "
            "directory is missing"
        )

    efetch_gbff = (
        acc_dir
        / f"{accession}_efetch_components.gbff"
    )

    provenance = (
        acc_dir
        / f"{accession}_efetch_components.json"
    )

    if (
        not efetch_gbff.is_file()
        or efetch_gbff.stat().st_size <= 0
    ):
        _fail(
            f"{accession}: recovered EFetch GBFF "
            "is missing or empty"
        )

    other_gbff = [
        path
        for path in acc_dir.glob(
            "*.gbff"
        )
        if path != efetch_gbff
    ]

    if other_gbff:
        _fail(
            f"{accession}: recovery package "
            "contains both Datasets and EFetch GBFF"
        )

    sequence_report = (
        acc_dir
        / "sequence_report.jsonl"
    )

    components = (
        _sequence_report_components(
            sequence_report,
            accession,
        )
    )

    _load_efetch_provenance(
        provenance,
        efetch_gbff,
        accession,
        components,
    )

    # The production monthly validator deliberately rejects EFetch
    # filenames/provenance before running the scientific checks.  To
    # reuse those checks exactly without altering the recovery package,
    # construct an ephemeral validation-only view.  No alias is written
    # into the recovery package and the view disappears before return.
    with tempfile.TemporaryDirectory(
        prefix=(
            "bacselect-missing-gbff-"
            "validation-"
        )
    ) as temporary:
        shadow_root = Path(
            temporary
        )

        shadow_acc = (
            shadow_root
            / accession
        )

        shadow_acc.mkdir(
            parents=True
        )

        for fasta in sorted(
            acc_dir.glob(
                "*.fna"
            )
        ):
            shutil.copy2(
                fasta,
                shadow_acc
                / fasta.name,
            )

        shutil.copy2(
            sequence_report,
            shadow_acc
            / sequence_report.name,
        )

        shadow_gbff = (
            shadow_acc
            / (
                f"{accession}_"
                "recovery_validation.gbff"
            )
        )

        shutil.copy2(
            efetch_gbff,
            shadow_gbff,
        )

        try:
            (
                candidate,
                component_rows,
            ) = (
                monthly
                .validate_candidate_payload(
                    shadow_root,
                    target,
                    observed_biosample,
                )
            )
        except Exception as exc:
            raise MonthlyMissingDatasetsGbffRecoveryError(
                f"{accession}: recovered candidate "
                "failed monthly scientific validation"
            ) from exc

    recovered_candidate = dict(
        candidate
    )

    recovered_candidate[
        "gbff_file"
    ] = efetch_gbff.name

    recovered_candidate[
        "gbff_sha256"
    ] = monthly.sha256_file(
        efetch_gbff
    )

    recovered_candidate[
        "gbff_source"
    ] = EFETCH_SOURCE

    recovered_candidate[
        "gbff_provenance_file"
    ] = provenance.name

    recovered_candidate[
        "gbff_provenance_sha256"
    ] = monthly.sha256_file(
        provenance
    )

    return (
        recovered_candidate,
        tuple(
            component_rows
        ),
    )


def validate_recovered_package(
    package: Path,
    targets: Sequence[
        monthly.MonthlyFreshAcquisitionTarget
    ],
    recovery_accessions: Sequence[str],
) -> monthly.MonthlyValidatedPackage:
    """Validate a whole batch while preserving target order exactly."""

    target_values = tuple(
        targets
    )

    recovery_set = set(
        recovery_accessions
    )

    target_accessions = {
        target
        .canonical_genbank_assembly_accession
        for target in target_values
    }

    if not recovery_set:
        _fail(
            "recovery package contains no "
            "declared recovery accessions"
        )

    if not recovery_set <= target_accessions:
        _fail(
            "recovery accession set is not "
            "a subset of batch targets"
        )

    try:
        (
            data_root,
            observed_biosamples,
            assembly_report,
        ) = monthly.validate_metadata(
            package,
            target_values,
        )
    except Exception as exc:
        raise MonthlyMissingDatasetsGbffRecoveryError(
            "recovery package metadata validation failed"
        ) from exc

    candidate_rows: list[
        Mapping[str, str]
    ] = []

    component_rows: list[
        Mapping[str, str]
    ] = []

    observed_recovery: set[
        str
    ] = set()

    for target in target_values:
        accession = (
            target
            .canonical_genbank_assembly_accession
        )

        observed = (
            observed_biosamples[
                accession
            ]
        )

        if accession in recovery_set:
            (
                candidate,
                components,
            ) = (
                validate_recovered_candidate(
                    data_root,
                    target,
                    observed,
                )
            )

            observed_recovery.add(
                accession
            )

        else:
            try:
                (
                    candidate,
                    components,
                ) = (
                    monthly
                    .validate_candidate_payload(
                        data_root,
                        target,
                        observed,
                    )
                )
            except Exception as exc:
                raise MonthlyMissingDatasetsGbffRecoveryError(
                    f"{accession}: non-recovery "
                    "candidate failed ordinary "
                    "monthly validation"
                ) from exc

        candidate_rows.append(
            candidate
        )

        component_rows.extend(
            components
        )

    if observed_recovery != recovery_set:
        _fail(
            "declared recovery accession set "
            "was not validated exactly"
        )

    observed_order = tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in candidate_rows
    )

    expected_order = tuple(
        target
        .canonical_genbank_assembly_accession
        for target in target_values
    )

    if observed_order != expected_order:
        _fail(
            "recovery candidate audit does not "
            "preserve Stage 2 target order"
        )

    return monthly.MonthlyValidatedPackage(
        candidate_rows=tuple(
            candidate_rows
        ),
        component_rows=tuple(
            component_rows
        ),
        package_file_rows=(
            monthly.package_file_manifest(
                package
            )
        ),
        assembly_data_report=(
            assembly_report
        ),
    )
