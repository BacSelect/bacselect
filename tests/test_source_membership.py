import csv
import hashlib
from pathlib import Path

import pytest

from bacselect.source_eligibility import (
    EXCLUDE,
    MetadataAssessment,
    RETAIN,
)
from bacselect.source_membership import (
    BASELINE_ACCESSION_COLUMN,
    MembershipSummary,
    blinded_membership_summary,
    compare_membership,
    load_baseline_accessions,
    metadata_retained_accessions,
)


def write_baseline(path: Path, rows):
    fieldnames = [
        "batch",
        "batch_index",
        BASELINE_ACCESSION_COLUMN,
        "01_total_genome_length",
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()

        for index, accession in enumerate(rows, start=1):
            writer.writerow(
                {
                    "batch": "b",
                    "batch_index": index,
                    BASELINE_ACCESSION_COLUMN: accession,
                    "01_total_genome_length": 1000 + index,
                }
            )

    return hashlib.sha256(path.read_bytes()).hexdigest()


def assessment(accession, decision=RETAIN):
    return MetadataAssessment(
        accession=accession,
        biosample="SAMN1",
        decision=decision,
        reasons=(),
        normalized_warnings=(),
    )


def test_frozen_accession_column_name():
    assert (
        BASELINE_ACCESSION_COLUMN
        == "canonical_genbank_assembly_accession"
    )


def test_loader_uses_named_accession_column_not_first_column(tmp_path):
    path = tmp_path / "baseline.tsv"
    sha = write_baseline(
        path,
        [
            "GCA_000000001.1",
            "GCA_000000002.1",
        ],
    )

    observed = load_baseline_accessions(
        path,
        expected_sha256=sha,
        expected_rows=2,
    )

    assert observed == {
        "GCA_000000001.1",
        "GCA_000000002.1",
    }


def test_loader_rejects_wrong_sha(tmp_path):
    path = tmp_path / "baseline.tsv"
    write_baseline(path, ["GCA_000000001.1"])

    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_baseline_accessions(
            path,
            expected_sha256="0" * 64,
            expected_rows=1,
        )


def test_loader_rejects_missing_named_column(tmp_path):
    path = tmp_path / "baseline.tsv"
    path.write_text(
        "batch\taccession\nb\tGCA_000000001.1\n",
        encoding="utf-8",
    )
    sha = hashlib.sha256(path.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="lacks frozen accession column"):
        load_baseline_accessions(
            path,
            expected_sha256=sha,
            expected_rows=1,
        )


def test_loader_rejects_invalid_accession(tmp_path):
    path = tmp_path / "baseline.tsv"
    sha = write_baseline(path, ["not-an-accession"])

    with pytest.raises(ValueError, match="invalid canonical GCA"):
        load_baseline_accessions(
            path,
            expected_sha256=sha,
            expected_rows=1,
        )


def test_loader_rejects_duplicate_accession(tmp_path):
    path = tmp_path / "baseline.tsv"
    sha = write_baseline(
        path,
        [
            "GCA_000000001.1",
            "GCA_000000001.1",
        ],
    )

    with pytest.raises(ValueError, match="duplicate canonical accession"):
        load_baseline_accessions(
            path,
            expected_sha256=sha,
            expected_rows=2,
        )


def test_loader_rejects_wrong_row_count(tmp_path):
    path = tmp_path / "baseline.tsv"
    sha = write_baseline(path, ["GCA_000000001.1"])

    with pytest.raises(ValueError, match="expected 2 baseline rows"):
        load_baseline_accessions(
            path,
            expected_sha256=sha,
            expected_rows=2,
        )


def test_metadata_retained_filters_excluded_records():
    observed = metadata_retained_accessions(
        [
            assessment("GCA_000000001.1", RETAIN),
            assessment("GCA_000000002.1", EXCLUDE),
        ]
    )

    assert observed == {"GCA_000000001.1"}


def test_metadata_retained_rejects_duplicate_accession():
    records = [
        assessment("GCA_000000001.1"),
        assessment("GCA_000000001.1"),
    ]

    with pytest.raises(ValueError, match="duplicate metadata-retained"):
        metadata_retained_accessions(records)


def test_metadata_retained_rejects_invalid_retained_accession():
    with pytest.raises(ValueError, match="invalid canonical GCA"):
        metadata_retained_accessions(
            [assessment("GCF_000000001.1")]
        )


def test_compare_membership_counts_overlap_and_absence():
    baseline = frozenset(
        {
            "GCA_000000001.1",
            "GCA_000000002.1",
            "GCA_000000003.1",
        }
    )
    retained = frozenset(
        {
            "GCA_000000002.1",
            "GCA_000000003.1",
            "GCA_000000004.1",
            "GCA_000000005.1",
        }
    )

    observed = compare_membership(baseline, retained)

    assert observed == MembershipSummary(
        baseline_accessions=3,
        metadata_retained=4,
        retained_present_in_baseline=2,
        retained_absent_from_baseline=2,
        baseline_not_in_metadata_retained=1,
    )


def test_compare_membership_empty_overlap():
    observed = compare_membership(
        frozenset({"GCA_000000001.1"}),
        frozenset({"GCA_000000002.1"}),
    )

    assert observed.retained_present_in_baseline == 0
    assert observed.retained_absent_from_baseline == 1
    assert observed.baseline_not_in_metadata_retained == 1


def test_compare_membership_full_overlap():
    values = frozenset(
        {
            "GCA_000000001.1",
            "GCA_000000002.1",
        }
    )

    observed = compare_membership(values, values)

    assert observed.retained_present_in_baseline == 2
    assert observed.retained_absent_from_baseline == 0
    assert observed.baseline_not_in_metadata_retained == 0


def test_blinded_summary_contains_only_aggregate_keys():
    baseline = frozenset(
        {
            "GCA_000000001.1",
            "GCA_000000002.1",
        }
    )
    assessments = [
        assessment("GCA_000000002.1"),
        assessment("GCA_000000003.1"),
    ]

    summary = blinded_membership_summary(
        baseline,
        assessments,
    )

    assert set(summary) == {
        "baseline_accessions",
        "metadata_retained",
        "retained_present_in_baseline",
        "retained_absent_from_baseline",
        "baseline_not_in_metadata_retained",
    }

    text = repr(summary)

    assert "GCA_" not in text
    assert "SAMN" not in text
    assert "organism" not in text.lower()
    assert "tax" not in text.lower()


def test_membership_summary_as_dict_is_deterministic():
    summary = MembershipSummary(
        baseline_accessions=10,
        metadata_retained=12,
        retained_present_in_baseline=8,
        retained_absent_from_baseline=4,
        baseline_not_in_metadata_retained=2,
    )

    assert summary.as_dict() == {
        "baseline_accessions": 10,
        "metadata_retained": 12,
        "retained_present_in_baseline": 8,
        "retained_absent_from_baseline": 4,
        "baseline_not_in_metadata_retained": 2,
    }
