import json
import os
from pathlib import Path

import pytest

from bacselect import (
    monthly_post_snapshot_supersession_execution
    as execution,
)
from bacselect import (
    monthly_sequence_recovery_authority
    as authority,
)
from bacselect import (
    monthly_sequence_validation
    as monthly,
)


SOURCE_COMMIT = "a" * 40
RECOVERY_COMMIT = "b" * 40
RELEASE = "2026.09"

BATCH = "batch-00118"

ACC1 = "GCA_123456789.1"
ACC1_NEXT = "GCA_123456789.2"
BIO1 = "SAMN12345678"
COMP1 = "CP000001.1"

ACC2 = "GCA_223456789.1"
ACC2_NEXT = "GCA_223456789.2"
BIO2 = "SAMN22345678"
COMP2 = "CP000002.1"


def target(
    accession,
    biosample,
):
    return monthly.MonthlyFreshAcquisitionTarget(
        canonical_genbank_assembly_accession=(
            accession
        ),
        source_biosample=biosample,
        acquisition_reason="no_verified_cache",
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


def metadata_record(
    accession,
    biosample,
    *,
    status="current",
    current_accession=None,
):
    if current_accession is None:
        current_accession = accession

    return {
        "accession":
            accession,
        "currentAccession":
            current_accession,
        "assemblyInfo": {
            "assemblyStatus":
                status,
            "assemblyLevel":
                "Complete Genome",
            "biosample": {
                "accession":
                    biosample,
            },
        },
    }


def write_jsonl(
    path,
    rows,
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
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    sort_keys=True,
                )
            )
            handle.write(
                "\n"
            )


def make_snapshot(
    tmp_path,
):
    path = (
        tmp_path
        / "assembly_data_report.raw.jsonl"
    )

    write_jsonl(
        path,
        (
            metadata_record(
                ACC1,
                BIO1,
            ),
            metadata_record(
                ACC2,
                BIO2,
            ),
        ),
    )

    return path


def make_source_partial(
    tmp_path,
    *,
    both_superseded=False,
):
    sequence_root = (
        tmp_path
        / "sequence-acquisition"
    )

    sequence_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    partial = (
        sequence_root
        / f"{BATCH}.partial"
    )

    data_root = (
        partial
        / "package"
        / "ncbi_dataset"
        / "data"
    )

    data_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    second_status = (
        "previous"
        if both_superseded
        else "current"
    )

    second_current = (
        ACC2_NEXT
        if both_superseded
        else ACC2
    )

    write_jsonl(
        data_root
        / "assembly_data_report.jsonl",
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
                status=(
                    second_status
                ),
                current_accession=(
                    second_current
                ),
            ),
        ),
    )

    fetch = (
        partial
        / "package"
        / "ncbi_dataset"
        / "fetch.txt"
    )

    lines = []

    for accession in (
        ACC1,
        ACC2,
    ):
        lines.extend(
            (
                (
                    f"https://example.invalid/{accession}/gbff"
                    f"\t100\tdata/{accession}/genomic.gbff"
                ),
                (
                    f"https://example.invalid/{accession}/fasta"
                    f"\t100\tdata/{accession}/"
                    f"{accession}_ASMsynthetic_genomic.fna"
                ),
                (
                    f"https://example.invalid/{accession}/report"
                    f"\t100\tdata/{accession}/sequence_report.jsonl"
                ),
            )
        )

    fetch.write_text(
        "\n".join(
            lines
        )
        + "\n",
        encoding="utf-8",
    )

    (
        partial
        / "accessions.txt"
    ).write_text(
        f"{ACC1}\n{ACC2}\n",
        encoding="ascii",
    )

    (
        partial
        / "batch-targets.tsv"
    ).write_text(
        (
            "canonical_genbank_assembly_accession\t"
            "source_biosample\t"
            "acquisition_reason\n"
            f"{ACC1}\t{BIO1}\tno_verified_cache\n"
            f"{ACC2}\t{BIO2}\tno_verified_cache\n"
        ),
        encoding="utf-8",
    )

    (
        partial
        / "attempt-origin.json"
    ).write_text(
        "{}\n",
        encoding="ascii",
    )

    (
        partial
        / "dehydrated.zip"
    ).write_bytes(
        b"synthetic dehydrated zip\n"
    )

    return (
        sequence_root,
        partial,
    )


def make_fake_datasets(
    tmp_path,
):
    path = (
        tmp_path
        / "fake-datasets"
    )

    path.write_text(
        f"""#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

ACC1 = {ACC1!r}
ACC1_NEXT = {ACC1_NEXT!r}
ACC2 = {ACC2!r}

COMPONENTS = {{
    ACC1: {COMP1!r},
    ACC2: {COMP2!r},
}}

SEQUENCES = {{
    ACC1: "ACGTACGT",
    ACC2: "AACCGGTT",
}}

marker = os.environ.get("FAKE_DATASETS_MARKER")

if marker:
    Path(marker).write_text(
        "called\\n",
        encoding="ascii",
    )

mode = os.environ.get(
    "FAKE_DATASETS_MODE",
    "success",
)

if mode == "fail":
    print(
        "synthetic rehydrate failure",
        file=sys.stderr,
    )
    raise SystemExit(7)

if len(sys.argv) < 4 or sys.argv[1] != "rehydrate":
    raise SystemExit(8)

try:
    package = Path(
        sys.argv[
            sys.argv.index("--directory") + 1
        ]
    )
except (ValueError, IndexError):
    raise SystemExit(9)

fetch = (
    package
    / "ncbi_dataset"
    / "fetch.txt"
)

rows = []

for line in fetch.read_text(
    encoding="utf-8"
).splitlines():
    parts = line.split("\\t")
    rows.append(
        parts[2]
    )

if mode == "unresolved":
    rows = rows[:-1]

for relative in rows:
    path = (
        package
        / "ncbi_dataset"
        / relative
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    accession = relative.split("/")[1]
    component = COMPONENTS[
        accession
    ]
    sequence = SEQUENCES[
        accession
    ]

    if relative.endswith(
        "sequence_report.jsonl"
    ):
        path.write_text(
            json.dumps(
                {{
                    "assemblyAccession":
                        accession,
                    "assemblyUnit":
                        "Primary Assembly",
                    "genbankAccession":
                        component,
                    "length":
                        len(sequence),
                }},
                sort_keys=True,
            )
            + "\\n",
            encoding="utf-8",
        )

    elif relative.endswith(
        "_genomic.fna"
    ):
        path.write_text(
            (
                f">{{component}}\\n"
                f"{{sequence}}\\n"
            ),
            encoding="ascii",
        )

    elif relative.endswith(
        "genomic.gbff"
    ):
        path.write_text(
            (
                f"LOCUS       {{component.split('.')[0]}} "
                f"{{len(sequence)}} bp DNA circular BCT 01-JAN-2000\\n"
                f"VERSION     {{component}}\\n"
                "ORIGIN\\n"
                f"        1 {{sequence.lower()}}\\n"
                "//\\n"
            ),
            encoding="ascii",
        )

    else:
        raise SystemExit(10)

if mode == "successor-dir":
    bad = (
        package
        / "ncbi_dataset"
        / "data"
        / ACC1_NEXT
    )

    bad.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        bad
        / "marker.txt"
    ).write_text(
        "successor must never enter payload\\n",
        encoding="ascii",
    )

print("synthetic rehydrate complete")
""",
        encoding="utf-8",
    )

    path.chmod(
        0o700
    )

    return path


def run_success(
    tmp_path,
    *,
    both_superseded=False,
):
    snapshot = make_snapshot(
        tmp_path
    )

    (
        sequence_root,
        source_partial,
    ) = make_source_partial(
        tmp_path,
        both_superseded=(
            both_superseded
        ),
    )

    executable = (
        make_fake_datasets(
            tmp_path
        )
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    before = (
        authority
        .strict_tree_fingerprint(
            source_partial
        )
    )

    result = (
        execution
        .execute_post_snapshot_supersession_recovery(
            source_partial_dir=(
                source_partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
            datasets_executable=(
                executable
            ),
            max_workers=2,
        )
    )

    after = (
        authority
        .strict_tree_fingerprint(
            source_partial
        )
    )

    return (
        snapshot,
        sequence_root,
        source_partial,
        recovery_root,
        result,
        before,
        after,
    )


def test_full_synthetic_lifecycle_finalizes_and_resolves_fresh_recovery(
    tmp_path,
):
    (
        snapshot,
        sequence_root,
        source_partial,
        recovery_root,
        result,
        before,
        after,
    ) = run_success(
        tmp_path
    )

    assert before == after

    assert not (
        recovery_root
        / f"{BATCH}.partial"
    ).exists()

    assert (
        recovery_root
        / BATCH
    ).is_dir()

    assert (
        result.affected_accessions
        == (
            ACC1,
        )
    )

    final = (
        recovery_root
        / BATCH
    )

    assert (
        final
        / execution.SUPERSESSION_EVIDENCE_NAME
    ).is_file()

    assert (
        final
        / authority.CANDIDATE_AUDIT_NAME
    ).is_file()

    assert (
        final
        / authority.COMPONENT_AUDIT_NAME
    ).is_file()

    assert not (
        final
        / "package"
        / "ncbi_dataset"
        / "data"
        / ACC1_NEXT
    ).exists()

    resolved = (
        authority
        .resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                BATCH,
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )
    )

    assert (
        resolved[
            0
        ].source_class
        == authority.SOURCE_CLASS_FRESH_RECOVERY
    )

    audited = (
        execution
        .audit_finalized_post_snapshot_supersession_recovery(
            batch_dir=(
                final
            ),
            source_partial_dir=(
                source_partial
            ),
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )
    )

    assert (
        audited.affected_accessions
        == (
            ACC1,
        )
    )


def test_successor_in_fetch_manifest_is_rejected_before_rehydrate(
    tmp_path,
    monkeypatch,
):
    snapshot = make_snapshot(
        tmp_path
    )

    (
        _,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    fetch = (
        source_partial
        / "package"
        / "ncbi_dataset"
        / "fetch.txt"
    )

    text = fetch.read_text(
        encoding="utf-8"
    )

    text = text.replace(
        f"data/{ACC1}/genomic.gbff",
        f"data/{ACC1_NEXT}/genomic.gbff",
        1,
    )

    fetch.write_text(
        text,
        encoding="utf-8",
    )

    executable = make_fake_datasets(
        tmp_path
    )

    marker = (
        tmp_path
        / "called.txt"
    )

    monkeypatch.setenv(
        "FAKE_DATASETS_MARKER",
        str(
            marker
        ),
    )

    with pytest.raises(
        execution.MonthlyPostSnapshotSupersessionExecutionError,
        match="successor accession appears|outside frozen batch",
    ):
        execution.execute_post_snapshot_supersession_recovery(
            source_partial_dir=(
                source_partial
            ),
            recovery_root=(
                tmp_path
                / "recovery"
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
            datasets_executable=(
                executable
            ),
        )

    assert not marker.exists()


def test_missing_frozen_fetch_entry_is_rejected_before_rehydrate(
    tmp_path,
    monkeypatch,
):
    snapshot = make_snapshot(
        tmp_path
    )

    (
        _,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    fetch = (
        source_partial
        / "package"
        / "ncbi_dataset"
        / "fetch.txt"
    )

    lines = fetch.read_text(
        encoding="utf-8"
    ).splitlines()

    fetch.write_text(
        "\n".join(
            lines[:-1]
        )
        + "\n",
        encoding="utf-8",
    )

    executable = make_fake_datasets(
        tmp_path
    )

    marker = (
        tmp_path
        / "called.txt"
    )

    monkeypatch.setenv(
        "FAKE_DATASETS_MARKER",
        str(
            marker
        ),
    )

    with pytest.raises(
        execution.MonthlyPostSnapshotSupersessionExecutionError,
        match="does not contain exactly",
    ):
        execution.execute_post_snapshot_supersession_recovery(
            source_partial_dir=(
                source_partial
            ),
            recovery_root=(
                tmp_path
                / "recovery"
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
            datasets_executable=(
                executable
            ),
        )

    assert not marker.exists()


def test_nonzero_rehydrate_fails_and_preserves_source_and_recovery_partial(
    tmp_path,
    monkeypatch,
):
    snapshot = make_snapshot(
        tmp_path
    )

    (
        _,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    before = (
        authority
        .strict_tree_fingerprint(
            source_partial
        )
    )

    executable = make_fake_datasets(
        tmp_path
    )

    monkeypatch.setenv(
        "FAKE_DATASETS_MODE",
        "fail",
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    with pytest.raises(
        execution.MonthlyPostSnapshotSupersessionExecutionError,
        match="exit code 7",
    ):
        execution.execute_post_snapshot_supersession_recovery(
            source_partial_dir=(
                source_partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
            datasets_executable=(
                executable
            ),
        )

    after = (
        authority
        .strict_tree_fingerprint(
            source_partial
        )
    )

    assert before == after

    assert (
        recovery_root
        / f"{BATCH}.partial"
    ).is_dir()

    assert not (
        recovery_root
        / BATCH
    ).exists()


def test_successful_process_with_unresolved_destination_fails_closed(
    tmp_path,
    monkeypatch,
):
    snapshot = make_snapshot(
        tmp_path
    )

    (
        _,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    executable = make_fake_datasets(
        tmp_path
    )

    monkeypatch.setenv(
        "FAKE_DATASETS_MODE",
        "unresolved",
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    with pytest.raises(
        execution.MonthlyPostSnapshotSupersessionExecutionError,
        match="remains incomplete",
    ):
        execution.execute_post_snapshot_supersession_recovery(
            source_partial_dir=(
                source_partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
            datasets_executable=(
                executable
            ),
        )

    assert (
        recovery_root
        / f"{BATCH}.partial"
    ).is_dir()

    assert not (
        recovery_root
        / BATCH
    ).exists()


def test_successor_payload_directory_is_rejected(
    tmp_path,
    monkeypatch,
):
    snapshot = make_snapshot(
        tmp_path
    )

    (
        _,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    executable = make_fake_datasets(
        tmp_path
    )

    monkeypatch.setenv(
        "FAKE_DATASETS_MODE",
        "successor-dir",
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    with pytest.raises(
        execution.MonthlyPostSnapshotSupersessionExecutionError,
        match="outside frozen batch|successor accession entered",
    ):
        execution.execute_post_snapshot_supersession_recovery(
            source_partial_dir=(
                source_partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
            datasets_executable=(
                executable
            ),
        )

    assert (
        recovery_root
        / f"{BATCH}.partial"
    ).is_dir()

    assert not (
        recovery_root
        / BATCH
    ).exists()


def test_two_superseded_targets_preserve_frozen_target_order(
    tmp_path,
):
    (
        _,
        _,
        _,
        recovery_root,
        result,
        _,
        _,
    ) = run_success(
        tmp_path,
        both_superseded=True,
    )

    assert (
        result.affected_accessions
        == (
            ACC1,
            ACC2,
        )
    )

    evidence = (
        recovery_root
        / BATCH
        / execution.SUPERSESSION_EVIDENCE_NAME
    ).read_text(
        encoding="utf-8"
    )

    assert (
        evidence.find(
            ACC1
        )
        < evidence.find(
            ACC2
        )
    )

    assert ACC1_NEXT in evidence
    assert ACC2_NEXT in evidence

    candidate = (
        recovery_root
        / BATCH
        / authority.CANDIDATE_AUDIT_NAME
    ).read_text(
        encoding="utf-8"
    )

    # Successors are temporal-drift evidence only,
    # never candidate identities.
    assert ACC1_NEXT not in candidate
    assert ACC2_NEXT not in candidate


def test_tampered_cause_evidence_is_rejected_by_final_reaudit(
    tmp_path,
):
    (
        snapshot,
        _,
        source_partial,
        recovery_root,
        _,
        _,
        _,
    ) = run_success(
        tmp_path
    )

    final = (
        recovery_root
        / BATCH
    )

    evidence = (
        final
        / execution.SUPERSESSION_EVIDENCE_NAME
    )

    evidence.write_text(
        evidence.read_text(
            encoding="utf-8"
        )
        + "tampered\n",
        encoding="utf-8",
    )

    with pytest.raises(
        execution.MonthlyPostSnapshotSupersessionExecutionError,
        match="cause evidence does not reproduce",
    ):
        execution.audit_finalized_post_snapshot_supersession_recovery(
            batch_dir=(
                final
            ),
            source_partial_dir=(
                source_partial
            ),
            source_snapshot_report=(
                snapshot
            ),
            targets=targets(),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )
