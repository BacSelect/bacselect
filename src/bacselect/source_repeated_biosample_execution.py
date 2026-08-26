"""Verified repeated-BioSample execution primitives for BacSelect Stage 2.

This module adds no repeated-BioSample scientific decision rule.

It binds a Stage 2 candidate to the exact frozen source evidence classified
in Stage 1, calculates the already-frozen topology-aware assembly fingerprint,
and delegates reconciliation to the already-frozen post-sequence composition
primitive.

It performs no production population discovery, taxonomy resolution,
chromosome-integrity assessment, baseline comparison, structural-feature
calculation, or selector analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Sequence

from bacselect import source_truth
from bacselect.source_fingerprint import (
    fingerprint_components,
)
from bacselect.source_post_sequence_eligibility import (
    BioSampleDecision,
    BioSampleMember,
    reconcile_repeated_biosamples,
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


class Stage2ExecutionError(RuntimeError):
    """Raised when frozen Stage 2 execution evidence is inconsistent."""


@dataclass(frozen=True)
class VerifiedBioSampleFingerprint:
    """One Stage 1-bound candidate ready for BioSample reconciliation."""

    accession: str
    biosample: str
    source_evidence_sha256: str
    assembly_fingerprint: str


def _lower_sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or LOWER_SHA256_RE.fullmatch(value) is None
    ):
        raise Stage2ExecutionError(
            f"{label} must be lowercase SHA256"
        )

    return value


def _biosample(
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise Stage2ExecutionError(
            "BioSample must be nonempty canonical text"
        )

    return value


def fingerprint_stage2_candidate(
    *,
    candidate: CandidateAudit,
    component_rows: Sequence[ComponentAudit],
    package_manifest: Mapping[str, PackageFile],
    expected_source_evidence_sha256: str,
    biosample: str,
) -> VerifiedBioSampleFingerprint:
    """Verify one Stage 1 candidate and calculate its frozen fingerprint.

    The topology-aware fingerprint is calculated only after the candidate's
    reconstructed source evidence has been rebound to the exact
    ``source_evidence_sha256`` recorded by Stage 1.
    """

    expected_sha = _lower_sha256(
        expected_source_evidence_sha256,
        label="expected Stage 1 source-evidence SHA256",
    )

    biosample = _biosample(
        biosample
    )

    components = load_primary_components(
        candidate,
        component_rows,
        package_manifest,
    )

    observed_sha = source_evidence_sha256(
        candidate,
        component_rows,
        package_manifest,
    )

    if observed_sha != expected_sha:
        raise Stage2ExecutionError(
            "Stage 1 source-evidence SHA256 mismatch"
        )

    topology_sequence_pairs = tuple(
        (
            components[name]["topology"],
            components[name]["sequence"],
        )
        for name in sorted(components)
    )

    fingerprint = fingerprint_components(
        topology_sequence_pairs
    )

    _lower_sha256(
        fingerprint,
        label="assembly fingerprint",
    )

    return VerifiedBioSampleFingerprint(
        accession=candidate.accession,
        biosample=biosample,
        source_evidence_sha256=observed_sha,
        assembly_fingerprint=fingerprint,
    )


def reconcile_verified_candidates(
    candidates: Sequence[
        VerifiedBioSampleFingerprint
    ],
) -> dict[str, BioSampleDecision]:
    """Delegate verified Stage 2 candidates to the frozen reconciler."""

    if isinstance(
        candidates,
        (
            str,
            bytes,
        ),
    ):
        raise Stage2ExecutionError(
            "candidates must be a sequence of verified records"
        )

    if not candidates:
        raise Stage2ExecutionError(
            "candidates must not be empty"
        )

    if any(
        not isinstance(
            candidate,
            VerifiedBioSampleFingerprint,
        )
        for candidate in candidates
    ):
        raise Stage2ExecutionError(
            "candidate has unexpected type"
        )

    ordered = tuple(
        sorted(
            candidates,
            key=lambda item:
                item.accession,
        )
    )

    members = tuple(
        BioSampleMember(
            accession=candidate.accession,
            biosample=candidate.biosample,
            source_truth_status=source_truth.SUITABLE,
            assembly_fingerprint=(
                candidate.assembly_fingerprint
            ),
        )
        for candidate in ordered
    )

    return reconcile_repeated_biosamples(
        members
    )
