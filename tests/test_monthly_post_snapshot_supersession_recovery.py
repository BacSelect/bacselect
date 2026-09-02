import json
from pathlib import Path

import pytest

from bacselect import (
    monthly_post_snapshot_supersession_recovery
    as recovery,
)
from bacselect import (
    monthly_sequence_validation
    as monthly,
)


ACC1 = "GCA_123456789.1"
ACC1_NEXT = "GCA_123456789.2"

ACC2 = "GCA_223456789.1"
ACC2_NEXT = "GCA_223456789.2"

BIO1 = "SAMN12345678"
BIO2 = "SAMN22345678"

COMP1 = "CP000001.1"
COMP2 = "CP000002.1"


def target(
    accession,
    biosample,
):
    return monthly.MonthlyFreshAcquisitionTarget(
        canonical_genbank_assembly_accession=(
            accession
        ),
        source_biosample=(
            biosample
        ),
        acquisition_reason=(
            "no_verified_cache"
        ),
    )


def metadata_record(
    accession,
    biosample,
    *,
    status="current",
    current_accession=None,
    level="Complete Genome",
    snake_case=False,
):
    if current_accession is None:
        current_accession = accession

    if snake_case:
        return {
            "accession":
                accession,
            "current_accession":
                current_accession,
            "assembly_info": {
                "assembly_status":
                    status,
                "assembly_level":
                    level,
                "biosample": {
                    "accession":
                        biosample,
                },
            },
        }

    return {
        "accession":
            accession,
        "currentAccession":
            current_accession,
        "assemblyInfo": {
            "assemblyStatus":
                status,
            "assemblyLevel":
                level,
            "biosample": {
                "accession":
                    biosample,
            },
        },
    }


def write_jsonl(
    path,
    records,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        for record in records:
            handle.write(
                json.dumps(
                    record,
                    sort_keys=True,
                )
            )
            handle.write(
                "\n"
            )


def write_candidate_payload(
    data_root,
    *,
    accession,
    component,
    sequence,
):
    acc_dir = (
        data_root
        / accession
    )

    acc_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        acc_dir
        / "sequence_report.jsonl"
    ).write_text(
        json.dumps(
            {
                "assemblyAccession":
                    accession,
                "assemblyUnit":
                    "Primary Assembly",
                "genbankAccession":
                    component,
                "length":
                    len(
                        sequence
                    ),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (
        acc_dir
        / f"{accession}_genomic.fna"
    ).write_text(
        (
            f">{component}\n"
            f"{sequence}\n"
        ),
        encoding="ascii",
    )

    (
        acc_dir
        / "genomic.gbff"
    ).write_text(
        (
            f"LOCUS       {component.split('.')[0]} "
            f"{len(sequence)} bp DNA circular BCT 01-JAN-2000\n"
            f"VERSION     {component}\n"
            "ORIGIN\n"
            f"        1 {sequence.lower()}\n"
            "//\n"
        ),
        encoding="ascii",
    )


def write_package(
    root,
    *,
    acquisition_records,
):
    package = (
        root
        / "package"
    )

    data_root = (
        package
        / "ncbi_dataset"
        / "data"
    )

    data_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_jsonl(
        data_root
        / "assembly_data_report.jsonl",
        acquisition_records,
    )

    write_candidate_payload(
        data_root,
        accession=ACC1,
        component=COMP1,
        sequence="ACGTACGT",
    )

    write_candidate_payload(
        data_root,
        accession=ACC2,
        component=COMP2,
        sequence="AACCGGTT",
    )

    return package


def write_snapshot(
    root,
    records,
):
    path = (
        root
        / "assembly_data_report.raw.jsonl"
    )

    write_jsonl(
        path,
        records,
    )

    return path


def normal_snapshot_records():
    return (
        metadata_record(
            ACC1,
            BIO1,
            snake_case=True,
        ),
        metadata_record(
            ACC2,
            BIO2,
            snake_case=True,
        ),
    )


def superseded_acquisition_records():
    return (
        metadata_record(
            ACC1,
            BIO1,
            status="previous",
            current_accession=(
                ACC1_NEXT
            ),
        ),
        metadata_record(
            ACC2,
            BIO2,
        ),
    )


def targets():
    return (
        target(
            ACC1,
            BIO1,
        ),
        target(
            ACC2,
            BIO2,
        ),
    )


def test_exact_supersession_detected_and_evidence_bound(
    tmp_path,
):
    snapshot = write_snapshot(
        tmp_path,
        normal_snapshot_records(),
    )

    package = write_package(
        tmp_path,
        acquisition_records=(
            superseded_acquisition_records()
        ),
    )

    result = (
        recovery
        .classify_post_snapshot_supersession(
            package=package,
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
        )
    )

    assert (
        result.affected_accessions
        == (
            ACC1,
        )
    )

    assert len(
        result.evidence_rows
    ) == 1

    row = result.evidence_rows[
        0
    ]

    assert (
        row[
            "canonical_genbank_assembly_accession"
        ]
        == ACC1
    )

    assert (
        row[
            "snapshot_assembly_status"
        ]
        == "current"
    )

    assert (
        row[
            "snapshot_current_accession"
        ]
        == ACC1
    )

    assert (
        row[
            "acquisition_assembly_status"
        ]
        == "previous"
    )

    assert (
        row[
            "acquisition_current_accession"
        ]
        == ACC1_NEXT
    )

    assert (
        row[
            "classification"
        ]
        == recovery.FAILURE_CLASS
    )

    assert (
        row[
            "source_snapshot_report_sha256"
        ]
        == monthly.sha256_file(
            snapshot
        )
    )

    assert (
        row[
            "acquisition_report_sha256"
        ]
        == monthly.sha256_file(
            package
            / "ncbi_dataset"
            / "data"
            / "assembly_data_report.jsonl"
        )
    )


def test_batch_without_supersession_is_not_recovery_eligible(
    tmp_path,
):
    snapshot = write_snapshot(
        tmp_path,
        normal_snapshot_records(),
    )

    package = write_package(
        tmp_path,
        acquisition_records=(
            (
                metadata_record(
                    ACC1,
                    BIO1,
                ),
                metadata_record(
                    ACC2,
                    BIO2,
                ),
            )
        ),
    )

    with pytest.raises(
        recovery.MonthlyPostSnapshotSupersessionRecoveryError,
        match="contains no post-snapshot supersession",
    ):
        recovery.classify_post_snapshot_supersession(
            package=package,
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
        )


def test_snapshot_target_must_have_been_current(
    tmp_path,
):
    snapshot = write_snapshot(
        tmp_path,
        (
            metadata_record(
                ACC1,
                BIO1,
                status="previous",
                current_accession=(
                    ACC1_NEXT
                ),
                snake_case=True,
            ),
            metadata_record(
                ACC2,
                BIO2,
                snake_case=True,
            ),
        ),
    )

    package = write_package(
        tmp_path,
        acquisition_records=(
            superseded_acquisition_records()
        ),
    )

    with pytest.raises(
        recovery.MonthlyPostSnapshotSupersessionRecoveryError,
        match="snapshot is not an exact current",
    ):
        recovery.classify_post_snapshot_supersession(
            package=package,
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
        )


def test_biosample_change_is_outside_supersession_class(
    tmp_path,
):
    snapshot = write_snapshot(
        tmp_path,
        normal_snapshot_records(),
    )

    package = write_package(
        tmp_path,
        acquisition_records=(
            (
                metadata_record(
                    ACC1,
                    "SAMN99999999",
                    status="previous",
                    current_accession=(
                        ACC1_NEXT
                    ),
                ),
                metadata_record(
                    ACC2,
                    BIO2,
                ),
            )
        ),
    )

    with pytest.raises(
        recovery.MonthlyPostSnapshotSupersessionRecoveryError,
        match="changed outside",
    ):
        recovery.classify_post_snapshot_supersession(
            package=package,
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
        )


def test_assembly_level_change_is_outside_supersession_class(
    tmp_path,
):
    snapshot = write_snapshot(
        tmp_path,
        normal_snapshot_records(),
    )

    package = write_package(
        tmp_path,
        acquisition_records=(
            (
                metadata_record(
                    ACC1,
                    BIO1,
                    status="previous",
                    current_accession=(
                        ACC1_NEXT
                    ),
                    level="Chromosome",
                ),
                metadata_record(
                    ACC2,
                    BIO2,
                ),
            )
        ),
    )

    with pytest.raises(
        recovery.MonthlyPostSnapshotSupersessionRecoveryError,
        match="changed outside",
    ):
        recovery.classify_post_snapshot_supersession(
            package=package,
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
        )


def test_current_status_with_changed_accession_is_not_supersession_class(
    tmp_path,
):
    snapshot = write_snapshot(
        tmp_path,
        normal_snapshot_records(),
    )

    package = write_package(
        tmp_path,
        acquisition_records=(
            (
                metadata_record(
                    ACC1,
                    BIO1,
                    status="current",
                    current_accession=(
                        ACC1_NEXT
                    ),
                ),
                metadata_record(
                    ACC2,
                    BIO2,
                ),
            )
        ),
    )

    with pytest.raises(
        recovery.MonthlyPostSnapshotSupersessionRecoveryError,
        match="changed outside",
    ):
        recovery.classify_post_snapshot_supersession(
            package=package,
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
        )


def test_whole_validator_reproduces_ordinary_science_without_successor_substitution(
    tmp_path,
):
    snapshot = write_snapshot(
        tmp_path
        / "superseded",
        normal_snapshot_records(),
    )

    superseded_package = write_package(
        tmp_path
        / "superseded",
        acquisition_records=(
            superseded_acquisition_records()
        ),
    )

    recovered = (
        recovery
        .validate_post_snapshot_supersession_package(
            package=(
                superseded_package
            ),
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
        )
    )

    ordinary_package = write_package(
        tmp_path
        / "ordinary",
        acquisition_records=(
            (
                metadata_record(
                    ACC1,
                    BIO1,
                ),
                metadata_record(
                    ACC2,
                    BIO2,
                ),
            )
        ),
    )

    ordinary = monthly.validate_hydrated_package(
        ordinary_package,
        targets(),
    )

    assert (
        recovered
        .validated_package
        .candidate_rows
        == ordinary.candidate_rows
    )

    assert (
        recovered
        .validated_package
        .component_rows
        == ordinary.component_rows
    )

    assert tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row
        in recovered
        .validated_package
        .candidate_rows
    ) == (
        ACC1,
        ACC2,
    )

    # No successor payload directory exists or is required.
    assert not (
        superseded_package
        / "ncbi_dataset"
        / "data"
        / ACC1_NEXT
    ).exists()

    assert (
        recovered
        .supersession_rows[
            0
        ][
            "acquisition_current_accession"
        ]
        == ACC1_NEXT
    )


def test_ordinary_monthly_validator_still_rejects_previous_status(
    tmp_path,
):
    package = write_package(
        tmp_path,
        acquisition_records=(
            superseded_acquisition_records()
        ),
    )

    with pytest.raises(
        monthly.MonthlySequenceValidationError,
        match="assembly status is not current",
    ):
        monthly.validate_hydrated_package(
            package,
            targets(),
        )


def test_supersession_evidence_preserves_affected_target_order(
    tmp_path,
):
    snapshot = write_snapshot(
        tmp_path,
        normal_snapshot_records(),
    )

    package = write_package(
        tmp_path,
        acquisition_records=(
            (
                metadata_record(
                    ACC1,
                    BIO1,
                    status="previous",
                    current_accession=(
                        ACC1_NEXT
                    ),
                ),
                metadata_record(
                    ACC2,
                    BIO2,
                    status="previous",
                    current_accession=(
                        ACC2_NEXT
                    ),
                ),
            )
        ),
    )

    result = (
        recovery
        .classify_post_snapshot_supersession(
            package=package,
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
        )
    )

    assert (
        result.affected_accessions
        == (
            ACC1,
            ACC2,
        )
    )

    assert tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row
        in result.evidence_rows
    ) == (
        ACC1,
        ACC2,
    )

    payload = (
        recovery
        .serialize_supersession_evidence(
            result.evidence_rows
        )
    )

    text = payload.decode(
        "utf-8"
    )

    assert (
        text.splitlines()[
            0
        ].split(
            "\t"
        )
        == list(
            recovery
            .SUPERSESSION_EVIDENCE_FIELDS
        )
    )

    assert (
        text.find(
            ACC1
        )
        < text.find(
            ACC2
        )
    )


def test_duplicate_acquisition_record_fails_closed(
    tmp_path,
):
    snapshot = write_snapshot(
        tmp_path,
        normal_snapshot_records(),
    )

    package = write_package(
        tmp_path,
        acquisition_records=(
            (
                metadata_record(
                    ACC1,
                    BIO1,
                    status="previous",
                    current_accession=(
                        ACC1_NEXT
                    ),
                ),
                metadata_record(
                    ACC1,
                    BIO1,
                    status="previous",
                    current_accession=(
                        ACC1_NEXT
                    ),
                ),
                metadata_record(
                    ACC2,
                    BIO2,
                ),
            )
        ),
    )

    with pytest.raises(
        recovery.MonthlyPostSnapshotSupersessionRecoveryError,
        match="duplicate accession",
    ):
        recovery.classify_post_snapshot_supersession(
            package=package,
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
        )
