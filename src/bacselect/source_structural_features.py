"""Stage 6 authoritative package binding for structural-feature execution.

This module contains no structural-feature mathematics.  It binds a requested
accession membership to the already-reconstructed Stage 1 package population
and resolves the exact files required by the frozen Project Finch loader.

No recursive discovery, newest-file selection, or package-class heuristic is
permitted.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable, Mapping, Protocol, Sequence

from bacselect.source_cache_verify import (
    path_scope,
    resolve_manifest_path,
)
from bacselect.source_truth_execution import (
    CandidateAudit,
    PackageFile,
    load_package_manifest,
)


ALLOWED_SOURCE_GROUPS = frozenset(
    {
        "historical",
        "fresh",
        "fresh-recovery",
    }
)

SEQUENCE_REPORT_NAME = "sequence_report.jsonl"


class StructuralFeatureBindingError(
    RuntimeError
):
    """Raised when Stage 6 package binding cannot be proven exactly."""


class BatchSpecLike(Protocol):
    """Minimum frozen BatchSpec interface consumed by Stage 6."""

    source_group: str
    batch: str
    candidate_audit: Path
    component_audit: Path
    package_manifest: Path
    candidates: Sequence[CandidateAudit]


class PopulationBundleLike(Protocol):
    """Minimum frozen PopulationBundle interface consumed by Stage 6."""

    batches: Sequence[BatchSpecLike]


@dataclass(frozen=True)
class CandidatePackageBinding:
    """Exact authoritative package binding for one Stage 6 accession."""

    accession: str
    source_group: str
    batch: str
    candidate_dir: Path
    candidate_audit: Path
    component_audit: Path
    package_manifest: Path
    fasta_path: Path
    sequence_report_path: Path
    fasta_sha256: str
    sequence_report_sha256: str


def _sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def _nonempty(
    value: object,
    *,
    label: str,
) -> str:
    text = str(
        value
    ).strip()

    if not text:
        raise StructuralFeatureBindingError(
            f"{label} must not be empty"
        )

    return text


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    current = Path(
        path
    )

    if (
        not current.is_file()
        or current.is_symlink()
    ):
        raise StructuralFeatureBindingError(
            f"{label} must be a regular non-symlink file"
        )

    return current


def _accession_rows(
    package_manifest: Mapping[
        str,
        PackageFile,
    ],
    accession: str,
) -> tuple[PackageFile, ...]:
    rows: list[
        PackageFile
    ] = []

    for row in package_manifest.values():
        try:
            scope, scoped_accession = (
                path_scope(
                    row.relative_path
                )
            )
        except ValueError as exc:
            raise StructuralFeatureBindingError(
                "invalid package-manifest path scope"
            ) from exc

        if scope == "batch_common":
            continue

        if scope != "accession":
            raise StructuralFeatureBindingError(
                "unexpected package-manifest path scope"
            )

        if scoped_accession == accession:
            rows.append(
                row
            )

    return tuple(
        sorted(
            rows,
            key=lambda item:
                item.relative_path,
        )
    )


def _resolve_verified_package_file(
    *,
    batch_dir: Path,
    row: PackageFile,
    label: str,
) -> Path:
    try:
        resolved = resolve_manifest_path(
            batch_dir,
            row.relative_path,
        )
    except ValueError as exc:
        raise StructuralFeatureBindingError(
            f"{label} package path could not be resolved exactly"
        ) from exc

    observed_size = (
        resolved.stat().st_size
    )

    if observed_size != row.size_bytes:
        raise StructuralFeatureBindingError(
            f"{label} size differs from package manifest"
        )

    observed_sha = _sha256_file(
        resolved
    )

    if observed_sha != row.sha256:
        raise StructuralFeatureBindingError(
            f"{label} SHA256 differs from package manifest"
        )

    return resolved


def resolve_candidate_package(
    *,
    batch: BatchSpecLike,
    candidate: CandidateAudit,
    package_manifest: Mapping[
        str,
        PackageFile,
    ],
) -> CandidatePackageBinding:
    """Resolve one candidate to the exact directory expected by Finch.

    The candidate FASTA and sequence_report.jsonl are selected only from the
    accession-scoped authoritative package-manifest rows.  The manifest paths
    are then resolved with the already-frozen two-layout resolver.

    Both files must resolve to the same directory, whose basename must be the
    canonical candidate accession.  No directory search or path heuristic is
    used.
    """

    accession = _nonempty(
        candidate.accession,
        label="candidate accession",
    )

    source_group = _nonempty(
        batch.source_group,
        label="source group",
    )

    if source_group not in (
        ALLOWED_SOURCE_GROUPS
    ):
        raise StructuralFeatureBindingError(
            "unexpected package source group"
        )

    batch_name = _nonempty(
        batch.batch,
        label="batch",
    )

    candidate_audit = (
        _require_regular_file(
            Path(
                batch.candidate_audit
            ),
            label="candidate audit",
        )
    )

    component_audit = (
        _require_regular_file(
            Path(
                batch.component_audit
            ),
            label="component audit",
        )
    )

    package_manifest_path = (
        _require_regular_file(
            Path(
                batch.package_manifest
            ),
            label="package manifest",
        )
    )

    try:
        candidate_audit_resolved = (
            candidate_audit.resolve(
                strict=True
            )
        )
        candidate_origin_resolved = (
            Path(
                candidate.audit_path
            ).resolve(
                strict=True
            )
        )
    except OSError as exc:
        raise StructuralFeatureBindingError(
            "candidate audit path could not be resolved"
        ) from exc

    if (
        candidate_origin_resolved
        != candidate_audit_resolved
    ):
        raise StructuralFeatureBindingError(
            "candidate audit does not belong to BatchSpec"
        )

    accession_rows = _accession_rows(
        package_manifest,
        accession,
    )

    if not accession_rows:
        raise StructuralFeatureBindingError(
            "candidate has no accession-scoped package rows"
        )

    fasta_rows = tuple(
        row
        for row in accession_rows
        if (
            Path(
                row.relative_path
            ).name
            == candidate.fasta_file
            and row.sha256
            == candidate.fasta_sha256
        )
    )

    if len(
        fasta_rows
    ) != 1:
        raise StructuralFeatureBindingError(
            "candidate FASTA does not resolve to exactly one "
            "authoritative package row"
        )

    report_rows = tuple(
        row
        for row in accession_rows
        if Path(
            row.relative_path
        ).name
        == SEQUENCE_REPORT_NAME
    )

    if len(
        report_rows
    ) != 1:
        raise StructuralFeatureBindingError(
            "sequence report does not resolve to exactly one "
            "authoritative package row"
        )

    batch_dir = (
        candidate_audit.parent
    )

    fasta_path = (
        _resolve_verified_package_file(
            batch_dir=batch_dir,
            row=fasta_rows[0],
            label="candidate FASTA",
        )
    )

    sequence_report_path = (
        _resolve_verified_package_file(
            batch_dir=batch_dir,
            row=report_rows[0],
            label="sequence report",
        )
    )

    if (
        fasta_path.parent
        != sequence_report_path.parent
    ):
        raise StructuralFeatureBindingError(
            "candidate FASTA and sequence report resolve to "
            "different directories"
        )

    candidate_dir = (
        fasta_path.parent
    )

    if candidate_dir.name != accession:
        raise StructuralFeatureBindingError(
            "resolved candidate directory basename differs "
            "from accession"
        )

    return CandidatePackageBinding(
        accession=accession,
        source_group=source_group,
        batch=batch_name,
        candidate_dir=candidate_dir,
        candidate_audit=candidate_audit,
        component_audit=component_audit,
        package_manifest=(
            package_manifest_path
        ),
        fasta_path=fasta_path,
        sequence_report_path=(
            sequence_report_path
        ),
        fasta_sha256=(
            fasta_rows[0].sha256
        ),
        sequence_report_sha256=(
            report_rows[0].sha256
        ),
    )


def build_package_bindings(
    *,
    bundle: PopulationBundleLike,
    accessions: Iterable[str],
) -> tuple[
    CandidatePackageBinding,
    ...,
]:
    """Bind exactly the requested membership to authoritative packages.

    Non-requested candidates are ignored.  Every requested accession must map
    to exactly one BatchSpec candidate and one authoritative package.
    """

    requested_list = tuple(
        _nonempty(
            value,
            label="requested accession",
        )
        for value in accessions
    )

    requested = set(
        requested_list
    )

    if (
        len(requested)
        != len(requested_list)
    ):
        raise StructuralFeatureBindingError(
            "requested accession membership contains duplicates"
        )

    if not requested:
        raise StructuralFeatureBindingError(
            "requested accession membership is empty"
        )

    observed: dict[
        str,
        CandidatePackageBinding,
    ] = {}

    batch_seen: set[
        str
    ] = set()

    for batch in bundle.batches:
        source_group = _nonempty(
            batch.source_group,
            label="source group",
        )

        if source_group not in (
            ALLOWED_SOURCE_GROUPS
        ):
            raise StructuralFeatureBindingError(
                "unexpected package source group"
            )

        selected = tuple(
            candidate
            for candidate in batch.candidates
            if candidate.accession in requested
        )

        for candidate in batch.candidates:
            accession = _nonempty(
                candidate.accession,
                label="batch candidate accession",
            )

            if accession in batch_seen:
                raise StructuralFeatureBindingError(
                    "duplicate candidate across authoritative "
                    "batch specifications"
                )

            batch_seen.add(
                accession
            )

        if not selected:
            continue

        try:
            package_manifest = (
                load_package_manifest(
                    Path(
                        batch.package_manifest
                    )
                )
            )
        except ValueError as exc:
            raise StructuralFeatureBindingError(
                "authoritative package manifest could not be loaded"
            ) from exc

        for candidate in sorted(
            selected,
            key=lambda item:
                item.accession,
        ):
            accession = candidate.accession

            if accession in observed:
                raise StructuralFeatureBindingError(
                    "requested accession resolved more than once"
                )

            observed[
                accession
            ] = resolve_candidate_package(
                batch=batch,
                candidate=candidate,
                package_manifest=(
                    package_manifest
                ),
            )

    missing = (
        requested
        - set(
            observed
        )
    )

    if missing:
        raise StructuralFeatureBindingError(
            "requested accession package binding incomplete"
        )

    if set(
        observed
    ) != requested:
        raise StructuralFeatureBindingError(
            "package binding contains unexpected accession"
        )

    return tuple(
        observed[
            accession
        ]
        for accession in sorted(
            observed
        )
    )
