"""Evidence-bound Stage 1 source-truth execution helpers for BacSelect.

This module reconstructs and verifies Primary Assembly sequence evidence and
delegates all scientific duplicate/containment semantics to the prospectively
frozen :mod:`bacselect.source_truth` implementation.

It contains no production evidence paths and performs no network access,
BioSample reconciliation, chromosome-integrity adjudication, taxonomy
resolution, baseline comparison, feature calculation, or selector analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
from itertools import combinations
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence

from bacselect.source_cache_verify import (
    resolve_manifest_path,
    sha256_file,
)
from bacselect.source_truth import (
    SUPPORTED_TOPOLOGIES,
    classify,
    containment_relation,
    duplicate_relation,
    sequence_set_sha256,
    sha256_text,
)


CANONICAL_GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)
LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

SEQUENCE_ELIGIBLE = "eligible"
SEQUENCE_INELIGIBLE = "ineligible"

CANDIDATE_REQUIRED_FIELDS = frozenset(
    {
        "canonical_genbank_assembly_accession",
        "sequence_eligibility",
        "fasta_file",
        "fasta_sha256",
        "primary_assembly_records",
    }
)

COMPONENT_FIELDS = (
    "canonical_genbank_assembly_accession",
    "component_genbank_accession",
    "length",
    "topology",
    "ambiguous_base_count",
    "ambiguous_symbols",
    "sequence_sha256",
)

PACKAGE_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
)


@dataclass(frozen=True)
class CandidateAudit:
    """One sequence-eligible candidate and its frozen FASTA evidence."""

    accession: str
    audit_path: Path
    fasta_file: str
    fasta_sha256: str
    primary_assembly_records: int

    @property
    def batch_dir(self) -> Path:
        return self.audit_path.parent


@dataclass(frozen=True)
class CandidatePopulation:
    """Deterministically reconstructed sequence-eligible population."""

    candidates: tuple[CandidateAudit, ...]
    total_records: int
    eligible_records: int
    ineligible_records: int
    membership_sha256: str


@dataclass(frozen=True)
class ComponentAudit:
    """Frozen evidence for one retained Primary Assembly component."""

    accession: str
    component_accession: str
    length: int
    topology: str
    sequence_sha256: str


@dataclass(frozen=True)
class PackageFile:
    """One exact package-manifest file identity."""

    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class DuplicateEvidence:
    """One deterministic complete-molecule duplicate relation."""

    left_component: str
    right_component: str
    relation: str


@dataclass(frozen=True)
class ContainmentEvidence:
    """One deterministic full-component containment relation."""

    inner_component: str
    outer_component: str
    inner_topology: str
    outer_topology: str
    orientation: str
    outer_origin_crossing: bool


@dataclass(frozen=True)
class SourceTruthDecision:
    """Complete deterministic Stage 1 result for one candidate."""

    accession: str
    source_evidence_sha256: str | None
    sequence_set_sha256: str
    duplicate_relations: tuple[DuplicateEvidence, ...]
    containment_relations: tuple[ContainmentEvidence, ...]
    status: str
    reason: str
    explanation: str


def _read_tsv(
    path: Path,
) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    if not path.is_file():
        raise ValueError(
            f"TSV does not exist: {path}"
        )

    with path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        if reader.fieldnames is None:
            raise ValueError(
                f"{path}: missing TSV header"
            )

        fields = tuple(reader.fieldnames)
        rows = [
            dict(row)
            for row in reader
        ]

    return fields, rows


def _canonical_accession(
    value: object,
    *,
    field: str,
) -> str:
    if (
        not isinstance(value, str)
        or not CANONICAL_GCA_RE.fullmatch(value)
    ):
        raise ValueError(
            f"invalid canonical GCA accession in {field}"
        )

    return value


def _sha256(
    value: object,
    *,
    field: str,
) -> str:
    if (
        not isinstance(value, str)
        or not LOWER_SHA256_RE.fullmatch(value)
    ):
        raise ValueError(
            f"invalid SHA256 in {field}"
        )

    return value


def _positive_int(
    value: object,
    *,
    field: str,
) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        raise ValueError(
            f"invalid integer in {field}"
        ) from None

    if parsed <= 0:
        raise ValueError(
            f"{field} must be positive"
        )

    return parsed


def accession_membership_sha256(
    accessions: Iterable[str],
) -> str:
    """Hash exact sorted newline-delimited accession membership."""

    values = tuple(
        sorted(accessions)
    )

    if len(values) != len(set(values)):
        raise ValueError(
            "duplicate accession in membership"
        )

    for accession in values:
        _canonical_accession(
            accession,
            field="membership",
        )

    payload = "".join(
        f"{accession}\n"
        for accession in values
    ).encode("ascii")

    return hashlib.sha256(
        payload
    ).hexdigest()


def load_candidate_population(
    audit_paths: Sequence[Path],
    *,
    expected_total: int | None = None,
    expected_eligible: int | None = None,
    expected_ineligible: int | None = None,
) -> CandidatePopulation:
    """Reconstruct one frozen sequence-eligible population from audits."""

    if not audit_paths:
        raise ValueError(
            "candidate audit path list is empty"
        )

    seen: set[str] = set()
    eligible: list[CandidateAudit] = []

    total = 0
    eligible_count = 0
    ineligible_count = 0

    for audit_path_value in audit_paths:
        audit_path = Path(
            audit_path_value
        )

        fields, rows = _read_tsv(
            audit_path
        )

        missing = (
            CANDIDATE_REQUIRED_FIELDS
            - set(fields)
        )

        if missing:
            raise ValueError(
                f"{audit_path}: candidate audit missing fields: "
                + ",".join(sorted(missing))
            )

        for row in rows:
            total += 1

            accession = _canonical_accession(
                row.get(
                    "canonical_genbank_assembly_accession"
                ),
                field="candidate audit",
            )

            if accession in seen:
                raise ValueError(
                    "duplicate GCA across candidate audits"
                )

            seen.add(
                accession
            )

            state = row.get(
                "sequence_eligibility"
            )

            if state == SEQUENCE_INELIGIBLE:
                ineligible_count += 1
                continue

            if state != SEQUENCE_ELIGIBLE:
                raise ValueError(
                    "unexpected sequence_eligibility state"
                )

            eligible_count += 1

            fasta_file = row.get(
                "fasta_file",
                "",
            )

            if not fasta_file:
                raise ValueError(
                    "sequence-eligible candidate has empty fasta_file"
                )

            fasta_sha = _sha256(
                row.get(
                    "fasta_sha256"
                ),
                field="candidate fasta_sha256",
            )

            primary_records = _positive_int(
                row.get(
                    "primary_assembly_records"
                ),
                field="primary_assembly_records",
            )

            eligible.append(
                CandidateAudit(
                    accession=accession,
                    audit_path=audit_path,
                    fasta_file=fasta_file,
                    fasta_sha256=fasta_sha,
                    primary_assembly_records=primary_records,
                )
            )

    if (
        expected_total is not None
        and total != expected_total
    ):
        raise ValueError(
            f"unexpected candidate record count: "
            f"expected {expected_total}, observed {total}"
        )

    if (
        expected_eligible is not None
        and eligible_count != expected_eligible
    ):
        raise ValueError(
            f"unexpected eligible record count: "
            f"expected {expected_eligible}, observed {eligible_count}"
        )

    if (
        expected_ineligible is not None
        and ineligible_count != expected_ineligible
    ):
        raise ValueError(
            f"unexpected ineligible record count: "
            f"expected {expected_ineligible}, observed {ineligible_count}"
        )

    if (
        eligible_count
        + ineligible_count
        != total
    ):
        raise RuntimeError(
            "candidate population accounting is inconsistent"
        )

    ordered = tuple(
        sorted(
            eligible,
            key=lambda item: item.accession,
        )
    )

    return CandidatePopulation(
        candidates=ordered,
        total_records=total,
        eligible_records=eligible_count,
        ineligible_records=ineligible_count,
        membership_sha256=accession_membership_sha256(
            item.accession
            for item in ordered
        ),
    )


def load_component_index(
    path: Path,
    *,
    accessions: Iterable[str] | None = None,
) -> dict[str, tuple[ComponentAudit, ...]]:
    """Load retained Primary Assembly component evidence."""

    fields, rows = _read_tsv(
        Path(path)
    )

    if fields != COMPONENT_FIELDS:
        raise ValueError(
            "unexpected component-sequence-audit.tsv schema"
        )

    wanted = (
        None
        if accessions is None
        else set(accessions)
    )

    grouped: dict[
        str,
        list[ComponentAudit],
    ] = {}

    seen_components: set[
        tuple[str, str]
    ] = set()

    for row in rows:
        accession = _canonical_accession(
            row.get(
                "canonical_genbank_assembly_accession"
            ),
            field="component audit",
        )

        if (
            wanted is not None
            and accession not in wanted
        ):
            continue

        component_accession = row.get(
            "component_genbank_accession",
            "",
        )

        if not component_accession:
            raise ValueError(
                "component audit has empty component accession"
            )

        key = (
            accession,
            component_accession,
        )

        if key in seen_components:
            raise ValueError(
                "duplicate component in component audit"
            )

        seen_components.add(
            key
        )

        length = _positive_int(
            row.get("length"),
            field="component length",
        )

        topology = row.get(
            "topology",
            "",
        ).strip().lower()

        if topology not in SUPPORTED_TOPOLOGIES:
            raise ValueError(
                "unsupported topology in component audit"
            )

        sequence_sha = _sha256(
            row.get(
                "sequence_sha256"
            ),
            field="component sequence_sha256",
        )

        grouped.setdefault(
            accession,
            [],
        ).append(
            ComponentAudit(
                accession=accession,
                component_accession=component_accession,
                length=length,
                topology=topology,
                sequence_sha256=sequence_sha,
            )
        )

    result: dict[
        str,
        tuple[ComponentAudit, ...],
    ] = {}

    for accession, components in grouped.items():
        result[accession] = tuple(
            sorted(
                components,
                key=lambda item: item.component_accession,
            )
        )

    if wanted is not None:
        missing = (
            wanted
            - set(result)
        )

        if missing:
            raise ValueError(
                "missing component evidence for requested candidate"
            )

    return result


def load_package_manifest(
    path: Path,
) -> dict[str, PackageFile]:
    """Load an exact package-files style manifest."""

    fields, rows = _read_tsv(
        Path(path)
    )

    if fields != PACKAGE_FIELDS:
        raise ValueError(
            "unexpected package manifest schema"
        )

    result: dict[
        str,
        PackageFile,
    ] = {}

    for row in rows:
        relative_path = row.get(
            "path",
            "",
        )

        if not relative_path:
            raise ValueError(
                "package manifest has empty path"
            )

        if relative_path in result:
            raise ValueError(
                "duplicate path in package manifest"
            )

        try:
            size_bytes = int(
                row.get(
                    "size_bytes",
                    "",
                )
            )
        except (TypeError, ValueError):
            raise ValueError(
                "invalid package size_bytes"
            ) from None

        if size_bytes < 0:
            raise ValueError(
                "negative package size_bytes"
            )

        expected_sha = _sha256(
            row.get("sha256"),
            field="package manifest sha256",
        )

        result[relative_path] = PackageFile(
            relative_path=relative_path,
            size_bytes=size_bytes,
            sha256=expected_sha,
        )

    if not result:
        raise ValueError(
            "package manifest is empty"
        )

    return result


def _parse_fasta(
    path: Path,
) -> dict[str, str]:
    records: dict[
        str,
        str,
    ] = {}

    current: str | None = None
    chunks: list[str] = []

    def finish() -> None:
        nonlocal current
        nonlocal chunks

        if current is None:
            return

        sequence = "".join(
            chunks
        ).upper()

        if not sequence:
            raise ValueError(
                "FASTA record has empty sequence"
            )

        invalid = set(sequence) - set(
            "ACGT"
        )

        if invalid:
            raise ValueError(
                "FASTA contains unsupported symbols"
            )

        if current in records:
            raise ValueError(
                "duplicate FASTA record identifier"
            )

        records[current] = sequence

        current = None
        chunks = []

    with path.open(
        "r",
        encoding="ascii",
    ) as handle:
        for line_number, raw_line in enumerate(
            handle,
            start=1,
        ):
            line = raw_line.strip()

            if not line:
                continue

            if line.startswith(">"):
                finish()

                header = line[1:].strip()

                if not header:
                    raise ValueError(
                        f"empty FASTA header at line {line_number}"
                    )

                current = header.split(
                    None,
                    1,
                )[0]

                chunks = []
                continue

            if current is None:
                raise ValueError(
                    "FASTA sequence precedes first header"
                )

            chunks.append(
                line
            )

    finish()

    if not records:
        raise ValueError(
            "FASTA contains no records"
        )

    return records


def source_evidence_sha256(
    candidate: CandidateAudit,
    component_rows: Sequence[ComponentAudit],
    package_manifest: Mapping[str, PackageFile],
) -> str:
    """Fingerprint exactly the frozen evidence used for one Stage 1 candidate.

    The identity binds the candidate FASTA evidence, its package-manifest
    identity, and every sorted Primary Assembly component identity, length,
    topology, and sequence SHA256. Filesystem location is deliberately not
    part of the scientific evidence identity.
    """

    if not component_rows:
        raise ValueError(
            "candidate has no component evidence"
        )

    if any(
        row.accession != candidate.accession
        for row in component_rows
    ):
        raise ValueError(
            "component evidence belongs to another candidate"
        )

    if (
        len(component_rows)
        != candidate.primary_assembly_records
    ):
        raise ValueError(
            "Primary Assembly component count mismatch"
        )

    candidate_sha = _sha256(
        candidate.fasta_sha256,
        field="candidate fasta_sha256",
    )

    package_row = _match_candidate_package_row(
        candidate.fasta_file,
        candidate_sha,
        package_manifest,
    )

    package_sha = _sha256(
        package_row.sha256,
        field="package FASTA sha256",
    )

    if package_sha != candidate_sha:
        raise ValueError(
            "candidate FASTA SHA conflicts with package manifest"
        )

    payload = {
        "candidate": {
            "canonical_genbank_assembly_accession": candidate.accession,
            "fasta_file": candidate.fasta_file,
            "fasta_sha256": candidate_sha,
            "primary_assembly_records": candidate.primary_assembly_records,
        },
        "package": {
            "path": package_row.relative_path,
            "size_bytes": package_row.size_bytes,
            "sha256": package_sha,
        },
        "primary_assembly_components": [
            {
                "component_genbank_accession": row.component_accession,
                "length": row.length,
                "sequence_sha256": _sha256(
                    row.sequence_sha256,
                    field="component sequence_sha256",
                ),
                "topology": row.topology,
            }
            for row in sorted(
                component_rows,
                key=lambda item: item.component_accession,
            )
        ],
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")

    return hashlib.sha256(
        encoded
    ).hexdigest()


def _match_candidate_package_row(
    fasta_file: str,
    fasta_sha256: str,
    package_manifest: Mapping[str, PackageFile],
) -> PackageFile:
    """Bind frozen candidate FASTA evidence to exactly one package row."""

    candidate_sha = _sha256(
        fasta_sha256,
        field="candidate fasta_sha256",
    )

    exact = package_manifest.get(
        fasta_file
    )

    if exact is not None:
        exact_sha = _sha256(
            exact.sha256,
            field="package FASTA sha256",
        )

        if exact_sha != candidate_sha:
            raise ValueError(
                "candidate FASTA SHA conflicts with package manifest"
            )

        return exact

    candidate_basename = Path(
        fasta_file
    ).name

    matches = tuple(
        row
        for row in package_manifest.values()
        if (
            Path(
                row.relative_path
            ).name
            == candidate_basename
            and row.sha256
            == candidate_sha
        )
    )

    if not matches:
        raise ValueError(
            "candidate FASTA absent from package manifest: "
            "no package-manifest FASTA row matches "
            "candidate basename and SHA256"
        )

    if len(matches) != 1:
        raise ValueError(
            "multiple package-manifest FASTA rows match "
            "candidate basename and SHA256"
        )

    return matches[0]


def load_primary_components(
    candidate: CandidateAudit,
    component_rows: Sequence[ComponentAudit],
    package_manifest: Mapping[str, PackageFile],
) -> dict[str, dict[str, str]]:
    """Verify and reconstruct one candidate's Primary Assembly components."""

    if not component_rows:
        raise ValueError(
            "candidate has no component evidence"
        )

    if any(
        row.accession != candidate.accession
        for row in component_rows
    ):
        raise ValueError(
            "component evidence belongs to another candidate"
        )

    if (
        len(component_rows)
        != candidate.primary_assembly_records
    ):
        raise ValueError(
            "Primary Assembly component count mismatch"
        )

    package_row = _match_candidate_package_row(
        candidate.fasta_file,
        candidate.fasta_sha256,
        package_manifest,
    )

    if (
        package_row.sha256
        != candidate.fasta_sha256
    ):
        raise ValueError(
            "candidate FASTA SHA conflicts with package manifest"
        )

    fasta_path = resolve_manifest_path(
        candidate.batch_dir,
        package_row.relative_path,
    )

    observed_size = fasta_path.stat().st_size

    if observed_size != package_row.size_bytes:
        raise ValueError(
            "candidate FASTA size differs from package manifest"
        )

    observed_sha = sha256_file(
        fasta_path
    )

    if observed_sha != package_row.sha256:
        raise ValueError(
            "candidate FASTA SHA differs from package manifest"
        )

    if observed_sha != candidate.fasta_sha256:
        raise ValueError(
            "candidate FASTA SHA differs from candidate audit"
        )

    fasta_records = _parse_fasta(
        fasta_path
    )

    components: dict[
        str,
        dict[str, str],
    ] = {}

    for evidence in sorted(
        component_rows,
        key=lambda item: item.component_accession,
    ):
        sequence = fasta_records.get(
            evidence.component_accession
        )

        if sequence is None:
            raise ValueError(
                "Primary Assembly component missing from FASTA"
            )

        if len(sequence) != evidence.length:
            raise ValueError(
                "Primary Assembly component length mismatch"
            )

        if (
            sha256_text(sequence)
            != evidence.sequence_sha256
        ):
            raise ValueError(
                "Primary Assembly component SHA256 mismatch"
            )

        components[
            evidence.component_accession
        ] = {
            "sequence": sequence,
            "topology": evidence.topology,
        }

    if len(components) != len(component_rows):
        raise RuntimeError(
            "Primary Assembly reconstruction is inconsistent"
        )

    return components


def evaluate_candidate(
    candidate: CandidateAudit,
    component_rows: Sequence[ComponentAudit],
    package_manifest: Mapping[str, PackageFile],
) -> SourceTruthDecision:
    """Verify source evidence and evaluate one Stage 1 candidate."""

    components = load_primary_components(
        candidate,
        component_rows,
        package_manifest,
    )

    evidence_sha = source_evidence_sha256(
        candidate,
        component_rows,
        package_manifest,
    )

    return evaluate_components(
        candidate.accession,
        components,
        source_evidence_sha256=evidence_sha,
    )



def adjudicate_relations(
    duplicate_relations: Sequence[DuplicateEvidence],
    containment_relations: Sequence[ContainmentEvidence],
) -> tuple[str, str, str]:
    """Delegate frozen relation adjudication to source_truth.classify."""

    rows = [
        {
            "inner_topology": relation.inner_topology,
        }
        for relation in containment_relations
    ]

    return classify(
        len(duplicate_relations),
        rows,
    )


def evaluate_components(
    accession: str,
    components: Mapping[
        str,
        Mapping[str, object],
    ],
    *,
    source_evidence_sha256: str | None = None,
) -> SourceTruthDecision:
    """Evaluate one verified Primary Assembly sequence set."""

    accession = _canonical_accession(
        accession,
        field="source-truth candidate",
    )

    if source_evidence_sha256 is not None:
        source_evidence_sha256 = _sha256(
            source_evidence_sha256,
            field="source evidence",
        )

    if not components:
        raise ValueError(
            "candidate has no Primary Assembly components"
        )

    names = tuple(
        sorted(components)
    )

    duplicates: list[
        DuplicateEvidence
    ] = []

    containments: list[
        ContainmentEvidence
    ] = []

    for left_name, right_name in combinations(
        names,
        2,
    ):
        left = components[
            left_name
        ]
        right = components[
            right_name
        ]

        relation = duplicate_relation(
            left,
            right,
        )

        if relation is not None:
            duplicates.append(
                DuplicateEvidence(
                    left_component=left_name,
                    right_component=right_name,
                    relation=relation,
                )
            )

        left_sequence = left.get(
            "sequence"
        )
        right_sequence = right.get(
            "sequence"
        )

        if not isinstance(
            left_sequence,
            str,
        ) or not isinstance(
            right_sequence,
            str,
        ):
            raise ValueError(
                "component sequence must be a string"
            )

        if len(left_sequence) == len(
            right_sequence
        ):
            continue

        if len(left_sequence) < len(
            right_sequence
        ):
            inner_name = left_name
            outer_name = right_name
        else:
            inner_name = right_name
            outer_name = left_name

        inner = components[
            inner_name
        ]
        outer = components[
            outer_name
        ]

        containment = containment_relation(
            inner,
            outer,
        )

        if containment is None:
            continue

        orientation, crossing = containment

        inner_topology = inner.get(
            "topology"
        )
        outer_topology = outer.get(
            "topology"
        )

        if not isinstance(
            inner_topology,
            str,
        ) or not isinstance(
            outer_topology,
            str,
        ):
            raise ValueError(
                "component topology must be a string"
            )

        containments.append(
            ContainmentEvidence(
                inner_component=inner_name,
                outer_component=outer_name,
                inner_topology=inner_topology,
                outer_topology=outer_topology,
                orientation=orientation,
                outer_origin_crossing=crossing,
            )
        )

    duplicates = sorted(
        duplicates,
        key=lambda item: (
            item.left_component,
            item.right_component,
            item.relation,
        ),
    )

    containments = sorted(
        containments,
        key=lambda item: (
            item.inner_component,
            item.outer_component,
            item.orientation,
            item.outer_origin_crossing,
        ),
    )

    status, reason, explanation = (
        adjudicate_relations(
            duplicates,
            containments,
        )
    )

    return SourceTruthDecision(
        accession=accession,
        source_evidence_sha256=source_evidence_sha256,
        sequence_set_sha256=sequence_set_sha256(
            components
        ),
        duplicate_relations=tuple(
            duplicates
        ),
        containment_relations=tuple(
            containments
        ),
        status=status,
        reason=reason,
        explanation=explanation,
    )


def decision_rows(
    decisions: Iterable[SourceTruthDecision],
) -> tuple[dict[str, str], ...]:
    """Return deterministic evidence-bound candidate-level output rows."""

    values = tuple(
        sorted(
            decisions,
            key=lambda item: item.accession,
        )
    )

    accessions = tuple(
        item.accession
        for item in values
    )

    if len(accessions) != len(
        set(accessions)
    ):
        raise ValueError(
            "duplicate source-truth decision accession"
        )

    rows: list[dict[str, str]] = []

    for item in values:
        if item.source_evidence_sha256 is None:
            raise ValueError(
                "candidate decision lacks frozen source-evidence identity"
            )

        source_sha = _sha256(
            item.source_evidence_sha256,
            field="decision source evidence",
        )

        rows.append(
            {
                "canonical_genbank_assembly_accession": item.accession,
                "source_evidence_sha256": source_sha,
                "sequence_set_sha256": item.sequence_set_sha256,
                "duplicate_relation_count": str(
                    len(
                        item.duplicate_relations
                    )
                ),
                "containment_relation_count": str(
                    len(
                        item.containment_relations
                    )
                ),
                "source_truth_status": item.status,
                "source_truth_reason": item.reason,
            }
        )

    return tuple(
        rows
    )

def relation_rows(
    decisions: Iterable[SourceTruthDecision],
) -> tuple[dict[str, str], ...]:
    """Return deterministic relation-evidence rows."""

    rows: list[
        dict[str, str]
    ] = []

    for decision in sorted(
        decisions,
        key=lambda item: item.accession,
    ):
        for relation in decision.duplicate_relations:
            rows.append(
                {
                    "canonical_genbank_assembly_accession": decision.accession,
                    "relation_type": "duplicate",
                    "left_component": relation.left_component,
                    "right_component": relation.right_component,
                    "inner_component": "",
                    "outer_component": "",
                    "inner_topology": "",
                    "outer_topology": "",
                    "relation": relation.relation,
                    "outer_origin_crossing": "",
                }
            )

        for relation in decision.containment_relations:
            rows.append(
                {
                    "canonical_genbank_assembly_accession": decision.accession,
                    "relation_type": "containment",
                    "left_component": "",
                    "right_component": "",
                    "inner_component": relation.inner_component,
                    "outer_component": relation.outer_component,
                    "inner_topology": relation.inner_topology,
                    "outer_topology": relation.outer_topology,
                    "relation": relation.orientation,
                    "outer_origin_crossing": (
                        "1"
                        if relation.outer_origin_crossing
                        else "0"
                    ),
                }
            )

    return tuple(
        rows
    )
