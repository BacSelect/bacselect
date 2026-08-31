from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

import bacselect.monthly_sequence_transport as module
from bacselect.monthly_sequence_plan import (
    MonthlyFreshAcquisitionTarget,
    NO_VERIFIED_CACHE,
)
from bacselect.monthly_sequence_transport import (
    INCLUDE_VALUE,
    REHYDRATE_WORKERS,
    TARGETED_RETRY_ROUNDS,
    FetchEntry,
    MonthlySequenceTransportError,
    MonthlyTransportBatch,
    batch_target_manifest_bytes,
    build_download_command,
    build_pre_network_attempt_record,
    build_rehydrate_command,
    build_targeted_rehydrate_command,
    fetch_entry_problem,
    parse_fetch_txt,
    remove_fetch_destinations,
    safe_extract,
    unresolved_fetches,
    validate_batch_contract,
)


DATASETS = Path(
    "/opt/bacselect/bin/datasets"
)

SNAPSHOT = (
    "source-snapshot-20260901T001700Z"
)

STAGE2_SHA = "1" * 64
ENV_SHA = "2" * 64
IMPLEMENTATION_SHA = "3" * 64
GIT_COMMIT = "4" * 40


def target(
    number: int,
):
    return MonthlyFreshAcquisitionTarget(
        canonical_genbank_assembly_accession=(
            f"GCA_{number:09d}.1"
        ),
        source_biosample=(
            f"SAMN{number:08d}"
        ),
        acquisition_reason=(
            NO_VERIFIED_CACHE
        ),
    )


def batch(
    *,
    targets=None,
    full_target_count=2,
    batch_index=1,
    batch_count=1,
    batch_size=500,
):
    if targets is None:
        targets = (
            target(1),
            target(2),
        )

    return MonthlyTransportBatch(
        source_snapshot_id=SNAPSHOT,
        stage2_fresh_target_manifest_sha256=(
            STAGE2_SHA
        ),
        batch_index=batch_index,
        batch_count=batch_count,
        batch_size=batch_size,
        full_target_count=full_target_count,
        targets=tuple(
            targets
        ),
    )


def test_dynamic_batch_contract_accepts_nonhistorical_population():
    value = batch(
        targets=tuple(
            target(number)
            for number in range(
                1001,
                1202,
            )
        ),
        full_target_count=1201,
        batch_index=3,
        batch_count=3,
        batch_size=500,
    )

    validate_batch_contract(
        value
    )

    assert len(
        value.targets
    ) == 201


def test_wrong_dynamic_batch_count_fails_closed():
    value = batch(
        full_target_count=1201,
        batch_index=1,
        batch_count=31,
        batch_size=500,
    )

    with pytest.raises(
        MonthlySequenceTransportError,
        match="batch count",
    ):
        validate_batch_contract(
            value
        )


def test_batch_target_manifest_preserves_stage2_identity():
    payload = batch_target_manifest_bytes(
        (
            target(1),
            target(2),
        )
    )

    assert payload == (
        b"canonical_genbank_assembly_accession"
        b"\tsource_biosample"
        b"\tacquisition_reason\n"
        b"GCA_000000001.1"
        b"\tSAMN00000001"
        b"\tno_verified_cache\n"
        b"GCA_000000002.1"
        b"\tSAMN00000002"
        b"\tno_verified_cache\n"
    )


def test_download_command_preserves_frozen_datasets_arguments():
    observed = build_download_command(
        datasets_executable=DATASETS,
        accessions_path=Path(
            "/tmp/accessions.txt"
        ),
        partial_zip_path=Path(
            "/tmp/dehydrated.zip.partial"
        ),
    )

    assert observed == (
        "/opt/bacselect/bin/datasets",
        "download",
        "genome",
        "accession",
        "--inputfile",
        "/tmp/accessions.txt",
        "--include",
        "genome,gbff,seq-report",
        "--dehydrated",
        "--filename",
        "/tmp/dehydrated.zip.partial",
        "--no-progressbar",
    )

    assert INCLUDE_VALUE == (
        "genome,gbff,seq-report"
    )


def test_rehydrate_commands_preserve_frozen_arguments():
    broad = build_rehydrate_command(
        datasets_executable=DATASETS,
        package=Path(
            "/tmp/package"
        ),
    )

    targeted = (
        build_targeted_rehydrate_command(
            datasets_executable=DATASETS,
            package=Path(
                "/tmp/package"
            ),
            accession="GCA_000000001.1",
        )
    )

    assert broad == (
        "/opt/bacselect/bin/datasets",
        "rehydrate",
        "--directory",
        "/tmp/package",
        "--max-workers",
        "10",
        "--no-progressbar",
    )

    assert targeted == (
        "/opt/bacselect/bin/datasets",
        "rehydrate",
        "--directory",
        "/tmp/package",
        "--match",
        "GCA_000000001.1",
        "--max-workers",
        "1",
        "--no-progressbar",
    )

    assert REHYDRATE_WORKERS == 10
    assert TARGETED_RETRY_ROUNDS == 2


def test_datasets_executable_must_be_absolute():
    with pytest.raises(
        MonthlySequenceTransportError,
        match="absolute path",
    ):
        build_rehydrate_command(
            datasets_executable=Path(
                "datasets"
            ),
            package=Path(
                "/tmp/package"
            ),
        )


def test_safe_extract_accepts_normal_zip(
    tmp_path,
):
    archive = (
        tmp_path
        / "payload.zip"
    )

    with zipfile.ZipFile(
        archive,
        "w",
    ) as handle:
        handle.writestr(
            "ncbi_dataset/data/test.txt",
            "ok\n",
        )

    destination = (
        tmp_path
        / "package"
    )

    destination.mkdir()

    safe_extract(
        archive,
        destination,
    )

    assert (
        destination
        / "ncbi_dataset"
        / "data"
        / "test.txt"
    ).read_text(
        encoding="utf-8"
    ) == "ok\n"


def test_safe_extract_rejects_parent_traversal(
    tmp_path,
):
    archive = (
        tmp_path
        / "payload.zip"
    )

    with zipfile.ZipFile(
        archive,
        "w",
    ) as handle:
        handle.writestr(
            "../escape.txt",
            "bad\n",
        )

    destination = (
        tmp_path
        / "package"
    )

    destination.mkdir()

    with pytest.raises(
        MonthlySequenceTransportError,
        match="unsafe path",
    ):
        safe_extract(
            archive,
            destination,
        )


def write_fetch(
    package: Path,
    rows,
):
    path = (
        package
        / "ncbi_dataset"
        / "fetch.txt"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        "".join(
            "\t".join(
                (
                    url,
                    str(size),
                    relative,
                )
            )
            + "\n"
            for (
                url,
                size,
                relative,
            ) in rows
        ),
        encoding="utf-8",
    )

    return path


def test_fetch_manifest_partition_is_exact(
    tmp_path,
):
    package = (
        tmp_path
        / "package"
    )

    write_fetch(
        package,
        (
            (
                "https://example.invalid/a",
                4,
                (
                    "data/GCA_000000001.1/"
                    "GCA_000000001.1_genomic.fna"
                ),
            ),
            (
                "https://example.invalid/b",
                5,
                (
                    "data/GCA_000000002.1/"
                    "GCA_000000002.1_genomic.fna"
                ),
            ),
        ),
    )

    (
        path,
        entries,
        by_accession,
    ) = parse_fetch_txt(
        package,
        (
            "GCA_000000001.1",
            "GCA_000000002.1",
        ),
    )

    assert path.name == "fetch.txt"

    assert len(
        entries
    ) == 2

    assert tuple(
        by_accession
    ) == (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )


def test_fetch_manifest_requires_entries_for_every_target(
    tmp_path,
):
    package = (
        tmp_path
        / "package"
    )

    write_fetch(
        package,
        (
            (
                "https://example.invalid/a",
                4,
                (
                    "data/GCA_000000001.1/"
                    "GCA_000000001.1_genomic.fna"
                ),
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceTransportError,
        match="no hydrated payload entries",
    ):
        parse_fetch_txt(
            package,
            (
                "GCA_000000001.1",
                "GCA_000000002.1",
            ),
        )


def test_fetch_manifest_rejects_unsafe_destination(
    tmp_path,
):
    package = (
        tmp_path
        / "package"
    )

    write_fetch(
        package,
        (
            (
                "https://example.invalid/a",
                4,
                "../escape",
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceTransportError,
        match="unsafe destination",
    ):
        parse_fetch_txt(
            package,
            (
                "GCA_000000001.1",
            ),
        )


def test_unresolved_fetches_detects_missing_empty_and_size_mismatch(
    tmp_path,
):
    package = (
        tmp_path
        / "package"
    )

    base = (
        package
        / "ncbi_dataset"
        / "data"
        / "GCA_000000001.1"
    )

    base.mkdir(
        parents=True
    )

    empty = (
        base
        / "empty.fna"
    )

    empty.write_bytes(
        b""
    )

    short = (
        base
        / "short.gbff"
    )

    short.write_bytes(
        b"abc"
    )

    entries = (
        FetchEntry(
            url="https://example.invalid/missing",
            expected_size=4,
            relative_path=(
                "data/GCA_000000001.1/"
                "missing.fna"
            ),
            accession="GCA_000000001.1",
        ),
        FetchEntry(
            url="https://example.invalid/empty",
            expected_size=4,
            relative_path=(
                "data/GCA_000000001.1/"
                "empty.fna"
            ),
            accession="GCA_000000001.1",
        ),
        FetchEntry(
            url="https://example.invalid/short",
            expected_size=4,
            relative_path=(
                "data/GCA_000000001.1/"
                "short.gbff"
            ),
            accession="GCA_000000001.1",
        ),
    )

    unresolved = unresolved_fetches(
        package,
        {
            "GCA_000000001.1":
                entries,
        },
    )

    assert unresolved == {
        "GCA_000000001.1": (
            (
                (
                    "data/GCA_000000001.1/"
                    "missing.fna"
                ),
                "missing",
            ),
            (
                (
                    "data/GCA_000000001.1/"
                    "empty.fna"
                ),
                "empty",
            ),
            (
                (
                    "data/GCA_000000001.1/"
                    "short.gbff"
                ),
                "size_mismatch:3!=4",
            ),
        )
    }

    assert (
        fetch_entry_problem(
            package,
            entries[2],
        )
        == "size_mismatch:3!=4"
    )


def test_targeted_cleanup_removes_only_manifest_destinations(
    tmp_path,
):
    package = (
        tmp_path
        / "package"
    )

    base = (
        package
        / "ncbi_dataset"
        / "data"
        / "GCA_000000001.1"
    )

    base.mkdir(
        parents=True
    )

    target_path = (
        base
        / "target.fna"
    )

    retained_path = (
        base
        / "retained.txt"
    )

    target_path.write_text(
        "ACGT\n",
        encoding="utf-8",
    )

    retained_path.write_text(
        "keep\n",
        encoding="utf-8",
    )

    remove_fetch_destinations(
        package,
        (
            FetchEntry(
                url="https://example.invalid/a",
                expected_size=5,
                relative_path=(
                    "data/GCA_000000001.1/"
                    "target.fna"
                ),
                accession="GCA_000000001.1",
            ),
        ),
    )

    assert not target_path.exists()
    assert retained_path.is_file()


def test_pre_network_attempt_binds_monthly_identity():
    value = batch()

    observed = (
        build_pre_network_attempt_record(
            value,
            recorded_at_utc=(
                "2026-09-01T00:17:00Z"
            ),
            origin_git_commit=(
                GIT_COMMIT
            ),
            environment_explicit_sha256=(
                ENV_SHA
            ),
            datasets_executable=(
                DATASETS
            ),
            transport_implementation_sha256=(
                IMPLEMENTATION_SHA
            ),
        )
    )

    assert observed[
        "created_before_network_retrieval"
    ] is True

    assert observed[
        "source_snapshot_id"
    ] == SNAPSHOT

    assert observed[
        "stage2_fresh_target_manifest_sha256"
    ] == STAGE2_SHA

    assert observed[
        "full_target_count"
    ] == 2

    assert observed[
        "batch_count"
    ] == 1

    assert observed[
        "requested_accessions"
    ] == 2

    assert observed[
        "datasets_version"
    ] == "18.35.0"

    assert observed[
        "dehydrated_zip_sha256"
    ] is None

    assert len(
        observed[
            "batch_target_manifest_sha256"
        ]
    ) == 64

    assert len(
        observed[
            "accessions_sha256"
        ]
    ) == 64

    json.dumps(
        observed,
        sort_keys=True,
    )


def test_stage3b_primitives_have_no_execution_or_historical_bindings():
    text = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "subprocess",
        "urllib",
        "requests",
        "http.client",
        "urlopen",
        "retrieve_efetch_gbff",
        "EFETCH_ENDPOINT",
        "/NGS/",
        "Rhys_wkdir",
        "finch-ncbi-datasets",
        "Project Finch",
        "SLURM_",
        "sbatch",
        "srun",
        "EXPECTED_TARGETS",
        "EXPECTED_BATCHES",
        "15_326",
        "70_477",
        "55_151",
    )

    for token in forbidden:
        assert token not in text
