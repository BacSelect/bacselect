from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from bacselect.source_fingerprint import (
    fingerprint_components,
)
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    BIOSAMPLE_NONREPRESENTATIVE,
    BIOSAMPLE_UNRESOLVED,
    CompositionError,
)
from bacselect.source_repeated_biosample_execution import (
    Stage2ExecutionError,
    VerifiedBioSampleFingerprint,
    fingerprint_stage2_candidate,
    reconcile_verified_candidates,
)
from bacselect.source_truth_execution import (
    CandidateAudit,
    ComponentAudit,
    PackageFile,
    source_evidence_sha256,
)


def sha256_text(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("ascii")
    ).hexdigest()


def make_candidate(
    tmp_path: Path,
    *,
    accession: str = "GCA_000000001.1",
    components=(
        (
            "CP000001.1",
            "AACCGGTT",
            "linear",
        ),
    ),
):
    batch = tmp_path / "batch-001"

    package_path = (
        Path("ncbi_dataset")
        / "data"
        / accession
        / f"{accession}_genomic.fna"
    )

    fasta_path = (
        batch
        / package_path
    )

    fasta_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fasta_text = "".join(
        f">{name}\n{sequence}\n"
        for name, sequence, _ in components
    )

    fasta_path.write_text(
        fasta_text,
        encoding="ascii",
    )

    fasta_sha = hashlib.sha256(
        fasta_path.read_bytes()
    ).hexdigest()

    audit_path = (
        batch
        / "candidate-sequence-audit.tsv"
    )

    audit_path.write_text(
        "synthetic fixture\n",
        encoding="utf-8",
    )

    candidate = CandidateAudit(
        accession=accession,
        audit_path=audit_path,
        fasta_file=fasta_path.name,
        fasta_sha256=fasta_sha,
        primary_assembly_records=len(
            components
        ),
    )

    component_rows = tuple(
        ComponentAudit(
            accession=accession,
            component_accession=name,
            length=len(sequence),
            topology=topology,
            sequence_sha256=(
                sha256_text(sequence)
            ),
        )
        for name, sequence, topology
        in components
    )

    package_manifest = {
        str(package_path):
            PackageFile(
                relative_path=str(
                    package_path
                ),
                size_bytes=(
                    fasta_path.stat().st_size
                ),
                sha256=fasta_sha,
            )
    }

    expected_source_sha = (
        source_evidence_sha256(
            candidate,
            component_rows,
            package_manifest,
        )
    )

    return (
        candidate,
        component_rows,
        package_manifest,
        expected_source_sha,
    )


def test_verified_candidate_is_bound_before_fingerprinting(
    tmp_path,
):
    (
        candidate,
        component_rows,
        package_manifest,
        expected_source_sha,
    ) = make_candidate(
        tmp_path
    )

    observed = fingerprint_stage2_candidate(
        candidate=candidate,
        component_rows=component_rows,
        package_manifest=package_manifest,
        expected_source_evidence_sha256=(
            expected_source_sha
        ),
        biosample="SAMN1",
    )

    assert observed.accession == (
        "GCA_000000001.1"
    )

    assert observed.biosample == "SAMN1"

    assert (
        observed.source_evidence_sha256
        == expected_source_sha
    )

    assert observed.assembly_fingerprint == (
        fingerprint_components(
            (
                (
                    "linear",
                    "AACCGGTT",
                ),
            )
        )
    )


def test_stage1_source_evidence_mismatch_fails_closed(
    tmp_path,
):
    (
        candidate,
        component_rows,
        package_manifest,
        _,
    ) = make_candidate(
        tmp_path
    )

    with pytest.raises(
        Stage2ExecutionError,
        match=(
            "Stage 1 source-evidence "
            "SHA256 mismatch"
        ),
    ):
        fingerprint_stage2_candidate(
            candidate=candidate,
            component_rows=component_rows,
            package_manifest=package_manifest,
            expected_source_evidence_sha256=(
                "0" * 64
            ),
            biosample="SAMN1",
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "SAMN1 ",
        None,
    ],
)
def test_malformed_biosample_fails_closed(
    tmp_path,
    value,
):
    (
        candidate,
        component_rows,
        package_manifest,
        expected_source_sha,
    ) = make_candidate(
        tmp_path
    )

    with pytest.raises(
        Stage2ExecutionError,
        match="BioSample",
    ):
        fingerprint_stage2_candidate(
            candidate=candidate,
            component_rows=component_rows,
            package_manifest=package_manifest,
            expected_source_evidence_sha256=(
                expected_source_sha
            ),
            biosample=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0" * 63,
        "G" * 64,
        None,
    ],
)
def test_malformed_expected_source_sha_fails_closed(
    tmp_path,
    value,
):
    (
        candidate,
        component_rows,
        package_manifest,
        _,
    ) = make_candidate(
        tmp_path
    )

    with pytest.raises(
        Stage2ExecutionError,
        match="lowercase SHA256",
    ):
        fingerprint_stage2_candidate(
            candidate=candidate,
            component_rows=component_rows,
            package_manifest=package_manifest,
            expected_source_evidence_sha256=value,
            biosample="SAMN1",
        )


def verified(
    accession,
    biosample,
    fingerprint,
):
    return VerifiedBioSampleFingerprint(
        accession=accession,
        biosample=biosample,
        source_evidence_sha256="1" * 64,
        assembly_fingerprint=fingerprint,
    )


def test_reconciliation_delegates_identical_group_rule():
    fingerprint = "a" * 64

    decisions = reconcile_verified_candidates(
        (
            verified(
                "GCA_000000003.1",
                "SAMN1",
                fingerprint,
            ),
            verified(
                "GCA_000000001.1",
                "SAMN1",
                fingerprint,
            ),
        )
    )

    assert decisions[
        "GCA_000000001.1"
    ].status == BIOSAMPLE_CONTINUE

    assert decisions[
        "GCA_000000003.1"
    ].status == BIOSAMPLE_NONREPRESENTATIVE


def test_reconciliation_delegates_differing_group_rule():
    decisions = reconcile_verified_candidates(
        (
            verified(
                "GCA_000000001.1",
                "SAMN1",
                "a" * 64,
            ),
            verified(
                "GCA_000000002.1",
                "SAMN1",
                "b" * 64,
            ),
        )
    )

    assert decisions[
        "GCA_000000001.1"
    ].status == BIOSAMPLE_UNRESOLVED

    assert decisions[
        "GCA_000000002.1"
    ].status == BIOSAMPLE_UNRESOLVED


def test_input_order_does_not_change_reconciliation():
    records = (
        verified(
            "GCA_000000003.1",
            "SAMN1",
            "a" * 64,
        ),
        verified(
            "GCA_000000001.1",
            "SAMN1",
            "a" * 64,
        ),
        verified(
            "GCA_000000002.1",
            "SAMN2",
            "b" * 64,
        ),
    )

    assert reconcile_verified_candidates(
        records
    ) == reconcile_verified_candidates(
        tuple(reversed(records))
    )


def test_empty_reconciliation_input_fails_closed():
    with pytest.raises(
        Stage2ExecutionError,
        match="must not be empty",
    ):
        reconcile_verified_candidates(
            ()
        )


def test_unexpected_verified_record_type_fails_deliberately():
    with pytest.raises(
        Stage2ExecutionError,
        match="unexpected type",
    ):
        reconcile_verified_candidates(
            (
                object(),
            )
        )


def test_duplicate_accession_fails_closed():
    record = verified(
        "GCA_000000001.1",
        "SAMN1",
        "a" * 64,
    )

    with pytest.raises(
        CompositionError,
        match="duplicate candidate accession",
    ):
        reconcile_verified_candidates(
            (
                record,
                record,
            )
        )


def test_malformed_verified_fingerprint_fails_closed():
    with pytest.raises(
        CompositionError,
        match="fingerprint",
    ):
        reconcile_verified_candidates(
            (
                verified(
                    "GCA_000000001.1",
                    "SAMN1",
                    "not-a-sha",
                ),
            )
        )
