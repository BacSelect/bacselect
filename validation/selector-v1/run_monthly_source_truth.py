#!/usr/bin/env python3
"""Execute BacSelect monthly Stage 4 source truth fail-closed."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
from typing import (
    Callable,
    Mapping,
    Sequence,
)

from bacselect import monthly_sequence_cache_catalogue
from bacselect import monthly_source_truth
from bacselect import source_truth_execution


SOURCE_TRUTH_STAGE_NAME = "source-truth"
SOURCE_TRUTH_PARTIAL_NAME = "source-truth.partial"
MATERIALIZATION_NAME = "source-truth-materialization.partial"

DECISIONS_NAME = "source-truth-decisions.tsv"
RELATIONS_NAME = "source-truth-relations.tsv"
RECORD_NAME = "monthly-source-truth-record.json"

COMPLETION_NAME = "source-truth-completion.json"
COMPLETION_TEMP_NAME = ".source-truth-completion.json.tmp"

COMPLETION_SCHEMA = "bacselect-monthly-source-truth-completion-v1"
COMPLETION_STATUS = "SOURCE_TRUTH_EXECUTION_COMPLETE"

CATALOGUE_NAME = "sequence-cache-catalogue.json"

SEQUENCE_PLAN_DIR = "sequence-plan"
SEQUENCE_PLAN_RECORD_NAME = "monthly-sequence-plan-record.json"
FRESH_TARGET_NAME = "fresh-targets.tsv"

SEQUENCE_ACQUISITION_DIR = "sequence-acquisition"

EXPECTED_METHOD_SHA256 = (
    "3acbc6b651777f1a62eaf8225a4db512"
    "5d9c28cb7016ccc1fc4c35e44b55c454"
)

EXPECTED_MONTHLY_SOURCE_TRUTH_SHA256 = (
    "f30c5d67c6042d86f9eafa3b25d0c93b"
    "0bf9aefe1bb6208584256ab6275e89e1"
)

EXPECTED_MONTHLY_SOURCE_TRUTH_TEST_SHA256 = (
    "3cfcc6d2ad5d429f0d116b27dfc9366b"
    "95078a2ae8617fe411ec8e60b2b5af2b"
)

EXPECTED_MONTHLY_SOURCE_TRUTH_METHOD_SHA256 = (
    "614bcb967f2bd764b7c1f4e83af3206e"
    "18896e1f91405f443034d29a11367c16"
)

EXPECTED_SOURCE_TRUTH_SHA256 = (
    "6aac349e591daebfc2569c14633cc807"
    "b5d7186ed4ed3e79f37f6627f5184486"
)

EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256 = (
    "83b8ec7fce774c0b68cb2af982aef139"
    "04c6b64b3ee695512c578f98e5de9b92"
)

EXPECTED_SOURCE_POST_SEQUENCE_SHA256 = (
    "62fa1e2f7d806f94b5f5eca73fb768745"
    "d3913a4b218a4d354562033cd300fe8"
)

EXPECTED_CATALOGUE_SHA256 = (
    "9555a2a72fa4b0f5d731adabead147f8"
    "56460fe87a18696b1a2b5312bc05d55"
)

EXPECTED_CATALOGUE_EXECUTOR_SHA256 = (
    "2cb7e162aa36b141d54b18fc29ffbaa9"
    "be3a5d9ca42a9e6b5bb1ff62e14cb3ea"
)

EXPECTED_CATALOGUE_EXECUTOR_TEST_SHA256 = (
    "2f6f2e8867e071b93972d3e07f9567f"
    "194991817a8d6dec6cebf266f7ca29f92"
)

EXPECTED_CATALOGUE_EXECUTOR_METHOD_SHA256 = (
    "128b533c2cfc9f9a0751094a9bb33f5e"
    "f97414ede86f8a3df9d104b9c7d7fdcd"
)

EXPECTED_CACHE_EXECUTOR_SHA256 = (
    "0a45ee60f06e102afba93cdc08f588f9b"
    "c547f7103279e59ffd4362cb5526c3e"
)

EXPECTED_CACHE_EXECUTOR_TEST_SHA256 = (
    "5e6341f3371d5c789b23a493ba16d473"
    "6965e897f4dddc430d3a98ce02593c25"
)

EXPECTED_CACHE_EXECUTOR_METHOD_SHA256 = (
    "36a61a09c3bbdd931023dedbc0578b211"
    "d4d6b70dae020eee80a47e726c633bd"
)

EXPECTED_METADATA_CORE_SHA256 = (
    "90c86d304d42c3e7dc4978a28d1d01a"
    "92660d9a359e07516f536ff3a0a2df87f"
)

EXPECTED_METADATA_EXECUTOR_SHA256 = (
    "81506e338d14d9a454db2a9f7cd5b1a"
    "c2d7ebdbafa069c9aed4fee4fd8b29041"
)

EXPECTED_METADATA_EXECUTOR_TEST_SHA256 = (
    "dadfb0b789faeae94cf5fcf5d22da5c"
    "e3242cd48e5e177cf761de8d6856ccc5e"
)

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GCA_RE = re.compile(r"^GCA_[0-9]+\.[0-9]+$")
RELEASE_RE = re.compile(
    r"^[0-9]{4}\.(0[1-9]|1[0-2])$"
)


SCIENTIFIC_NAMES = (
    DECISIONS_NAME,
    RELATIONS_NAME,
    RECORD_NAME,
)


FROZEN_FILES = {
    "src/bacselect/monthly_source_truth.py":
        EXPECTED_MONTHLY_SOURCE_TRUTH_SHA256,
    "tests/test_monthly_source_truth.py":
        EXPECTED_MONTHLY_SOURCE_TRUTH_TEST_SHA256,
    "validation/selector-v1/prospective-monthly-source-truth.md":
        EXPECTED_MONTHLY_SOURCE_TRUTH_METHOD_SHA256,
    "src/bacselect/source_truth.py":
        EXPECTED_SOURCE_TRUTH_SHA256,
    "src/bacselect/source_truth_execution.py":
        EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256,
    "src/bacselect/source_post_sequence_eligibility.py":
        EXPECTED_SOURCE_POST_SEQUENCE_SHA256,
    "src/bacselect/monthly_sequence_cache_catalogue.py":
        EXPECTED_CATALOGUE_SHA256,
    "validation/selector-v1/run_monthly_sequence_cache_catalogue.py":
        EXPECTED_CATALOGUE_EXECUTOR_SHA256,
    "tests/test_run_monthly_sequence_cache_catalogue.py":
        EXPECTED_CATALOGUE_EXECUTOR_TEST_SHA256,
    "validation/selector-v1/prospective-monthly-sequence-cache-catalogue-execution.md":
        EXPECTED_CATALOGUE_EXECUTOR_METHOD_SHA256,
    "validation/selector-v1/run_monthly_cache_verification.py":
        EXPECTED_CACHE_EXECUTOR_SHA256,
    "tests/test_run_monthly_cache_verification.py":
        EXPECTED_CACHE_EXECUTOR_TEST_SHA256,
    "validation/selector-v1/prospective-monthly-cache-verification-execution.md":
        EXPECTED_CACHE_EXECUTOR_METHOD_SHA256,
    "src/bacselect/monthly_metadata_eligibility.py":
        EXPECTED_METADATA_CORE_SHA256,
    "validation/selector-v1/run_monthly_metadata_eligibility.py":
        EXPECTED_METADATA_EXECUTOR_SHA256,
    "tests/test_run_monthly_metadata_eligibility.py":
        EXPECTED_METADATA_EXECUTOR_TEST_SHA256,
}


class MonthlySourceTruthExecutionError(RuntimeError):
    """Raised when monthly Stage 4 execution fails closed."""


@dataclass(frozen=True)
class CandidateBridge:
    accession: str
    biosample: str
    candidate_row: Mapping[str, str]
    component_rows: tuple[Mapping[str, str], ...]
    package_rows: tuple[Mapping[str, str], ...]
    fasta_package_path: str
    fasta_sha256: str
    fasta_size_bytes: int
    primary_assembly_records: int


@dataclass(frozen=True)
class InputObservation:
    path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class MonthlySourceTruthExecutionResult:
    release_id: str
    source_snapshot_id: str
    stage_root: Path
    completion_path: Path
    retained_count: int
    sequence_eligible_count: int
    sequence_ineligible_count: int
    decision_count: int
    relation_count: int
    decisions_sha256: str
    relations_sha256: str
    record_sha256: str
    completion_sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def validate_sha256(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or SHA256_RE.fullmatch(value) is None
    ):
        raise MonthlySourceTruthExecutionError(
            f"{label} is not a lowercase SHA256"
        )

    return value


def validate_commit(value: object) -> str:
    if (
        not isinstance(value, str)
        or COMMIT_RE.fullmatch(value) is None
    ):
        raise MonthlySourceTruthExecutionError(
            "execution commit is invalid"
        )

    return value


def release_ordinal(
    value: object,
) -> int:
    if (
        not isinstance(
            value,
            str,
        )
        or RELEASE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlySourceTruthExecutionError(
            "release ID is invalid"
        )

    year_text, month_text = (
        value.split(
            ".",
            1,
        )
    )

    return (
        int(
            year_text
        )
        * 12
        + int(
            month_text
        )
    )


def classify_origin_release(
    origin_release: object,
    current_release: object,
) -> str:
    origin = release_ordinal(
        origin_release
    )

    current = release_ordinal(
        current_release
    )

    if origin > current:
        raise MonthlySourceTruthExecutionError(
            "catalogue entry has a future origin release"
        )

    if origin == current:
        if origin_release != current_release:
            raise MonthlySourceTruthExecutionError(
                "origin/current release identity is inconsistent"
            )

        return "current"

    return "prior"


def validate_count(
    value: object,
    *,
    label: str,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 0
    ):
        raise MonthlySourceTruthExecutionError(
            f"{label} must be a non-negative integer"
        )

    return value


def git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(
        (
            "git",
            "-C",
            str(repo),
            *args,
        ),
        check=True,
        capture_output=True,
        text=True,
    )

    return result.stdout.strip()


def _load_module(
    repo: Path,
    relative: str,
    name: str,
):
    path = (
        repo
        / relative
    ).resolve()

    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    if spec is None or spec.loader is None:
        raise MonthlySourceTruthExecutionError(
            f"unable to load frozen module: {relative}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

    return module


def load_frozen_cache_execution(repo: Path):
    return _load_module(
        repo,
        "validation/selector-v1/run_monthly_cache_verification.py",
        "_bacselect_frozen_monthly_cache_execution_for_source_truth",
    )


def load_frozen_catalogue_execution(repo: Path):
    return _load_module(
        repo,
        "validation/selector-v1/run_monthly_sequence_cache_catalogue.py",
        "_bacselect_frozen_monthly_catalogue_execution_for_source_truth",
    )


def repository_preflight(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> None:
    root = Path(repo).resolve()
    commit = validate_commit(expected_commit)

    wrapper_sha = validate_sha256(
        expected_wrapper_sha256,
        label="expected wrapper SHA256",
    )

    test_sha = validate_sha256(
        expected_wrapper_test_sha256,
        label="expected wrapper-test SHA256",
    )

    if git_output(root, "rev-parse", "HEAD") != commit:
        raise MonthlySourceTruthExecutionError(
            "repository HEAD differs from expected execution commit"
        )

    if git_output(root, "status", "--porcelain"):
        raise MonthlySourceTruthExecutionError(
            "repository working tree is not clean"
        )

    for relative, expected in FROZEN_FILES.items():
        path = root / relative

        if not path.is_file() or path.is_symlink():
            raise MonthlySourceTruthExecutionError(
                f"frozen dependency missing or symlinked: {relative}"
            )

        observed = sha256_file(path)

        if observed != expected:
            raise MonthlySourceTruthExecutionError(
                f"frozen dependency SHA256 changed: {relative}"
            )

    method = (
        root
        / "validation/selector-v1/"
        "prospective-monthly-source-truth-execution.md"
    )

    if sha256_file(method) != EXPECTED_METHOD_SHA256:
        raise MonthlySourceTruthExecutionError(
            "monthly source-truth execution method SHA256 changed"
        )

    wrapper = Path(__file__).resolve()

    if sha256_file(wrapper) != wrapper_sha:
        raise MonthlySourceTruthExecutionError(
            "monthly source-truth wrapper SHA256 changed"
        )

    wrapper_test = (
        root
        / "tests/test_run_monthly_source_truth.py"
    )

    if sha256_file(wrapper_test) != test_sha:
        raise MonthlySourceTruthExecutionError(
            "monthly source-truth wrapper test SHA256 changed"
        )

    cache_execution = (
        load_frozen_cache_execution(
            root
        )
    )

    catalogue_execution = (
        load_frozen_catalogue_execution(
            root
        )
    )

    try:
        cache_execution.repository_preflight(
            root,
            expected_commit=commit,
            expected_wrapper_sha256=(
                EXPECTED_CACHE_EXECUTOR_SHA256
            ),
            expected_wrapper_test_sha256=(
                EXPECTED_CACHE_EXECUTOR_TEST_SHA256
            ),
        )
    except Exception as exc:
        raise MonthlySourceTruthExecutionError(
            "frozen cache-execution preflight failed"
        ) from exc

    try:
        catalogue_execution.repository_preflight(
            root,
            expected_commit=commit,
            expected_wrapper_sha256=(
                EXPECTED_CATALOGUE_EXECUTOR_SHA256
            ),
            expected_wrapper_test_sha256=(
                EXPECTED_CATALOGUE_EXECUTOR_TEST_SHA256
            ),
        )
    except Exception as exc:
        raise MonthlySourceTruthExecutionError(
            "frozen catalogue-execution preflight failed"
        ) from exc


def _require_real_directory(path: Path, *, label: str) -> Path:
    value = Path(path)

    if (
        not os.path.lexists(value)
        or value.is_symlink()
        or not value.is_dir()
    ):
        raise MonthlySourceTruthExecutionError(
            f"{label} is not a real directory"
        )

    return value.resolve()


def _require_regular_file(path: Path, *, label: str) -> Path:
    value = Path(path)

    if not os.path.lexists(value):
        raise MonthlySourceTruthExecutionError(
            f"{label} does not exist"
        )

    metadata = os.lstat(value)

    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
    ):
        raise MonthlySourceTruthExecutionError(
            f"{label} is not a regular non-symlink file"
        )

    return value.resolve()


def require_output_paths_clear(
    stage1_root: Path,
) -> None:
    stage1 = Path(
        stage1_root
    )

    paths = (
        (
            "canonical source-truth stage",
            stage1
            / SOURCE_TRUTH_STAGE_NAME,
        ),
        (
            "source-truth partial stage",
            stage1
            / SOURCE_TRUTH_PARTIAL_NAME,
        ),
        (
            "source-truth materialization",
            stage1
            / MATERIALIZATION_NAME,
        ),
        (
            "source-truth completion",
            stage1
            / COMPLETION_NAME,
        ),
        (
            "source-truth completion temporary artifact",
            stage1
            / COMPLETION_TEMP_NAME,
        ),
    )

    for label, candidate in paths:
        if os.path.lexists(
            candidate
        ):
            raise MonthlySourceTruthExecutionError(
                f"{label} already exists"
            )


def _serialize_tsv(
    rows: Sequence[Mapping[str, str]],
    fields: Sequence[str],
) -> bytes:
    handle = io.StringIO(newline="")

    writer = csv.DictWriter(
        handle,
        fieldnames=list(fields),
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )

    writer.writeheader()

    for row in rows:
        if set(row) != set(fields):
            raise MonthlySourceTruthExecutionError(
                "temporary TSV row schema changed"
            )

        writer.writerow(row)

    return handle.getvalue().encode("ascii")


def _write_bytes_exclusive(
    path: Path,
    payload: bytes,
    *,
    mode: int = 0o644,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL,
        mode,
    )

    try:
        os.fchmod(descriptor, mode)

        offset = 0

        while offset < len(payload):
            written = os.write(
                descriptor,
                payload[offset:],
            )

            if written <= 0:
                raise MonthlySourceTruthExecutionError(
                    "short write while creating Stage 4 evidence"
                )

            offset += written

        os.fsync(descriptor)

    finally:
        os.close(descriptor)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)

    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_exact_scientific_stage(
    path: Path,
) -> dict[
    str,
    bytes,
]:
    root = _require_real_directory(
        path,
        label="source-truth scientific stage",
    )

    entries = tuple(
        sorted(
            root.iterdir(),
            key=lambda value:
                value.name,
        )
    )

    observed_names = tuple(
        item.name
        for item in entries
    )

    expected_names = tuple(
        sorted(
            SCIENTIFIC_NAMES
        )
    )

    if observed_names != expected_names:
        raise MonthlySourceTruthExecutionError(
            "source-truth scientific stage inventory changed"
        )

    result = {}

    for item in entries:
        file_path = _require_regular_file(
            item,
            label=(
                f"source-truth scientific artifact {item.name}"
            ),
        )

        result[
            item.name
        ] = file_path.read_bytes()

    return result


def catalogue_chain_sha256(chain: Sequence[object]) -> str:
    rows = []

    for item in chain:
        rows.append(
            (
                str(item.release_id),
                str(item.origin_git_commit),
                validate_sha256(
                    item.catalogue_sha256,
                    label="catalogue-chain SHA256",
                ),
            )
        )

    payload = "".join(
        f"{release}\t{commit}\t{sha}\n"
        for release, commit, sha in rows
    ).encode("ascii")

    return hashlib.sha256(payload).hexdigest()


def _catalogue_provenance_by_sha(
    catalogue_record: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    values = catalogue_record.get("batch_provenance")

    if not isinstance(values, list):
        raise MonthlySourceTruthExecutionError(
            "current catalogue batch provenance is malformed"
        )

    result: dict[str, Mapping[str, object]] = {}

    for value in values:
        if not isinstance(value, Mapping):
            raise MonthlySourceTruthExecutionError(
                "current catalogue batch-provenance row is malformed"
            )

        digest = validate_sha256(
            value.get("batch_provenance_sha256"),
            label="batch provenance SHA256",
        )

        if digest in result:
            raise MonthlySourceTruthExecutionError(
                "duplicate catalogue batch-provenance SHA256"
            )

        result[digest] = value

    return result


def _catalogue_entries_by_accession(
    catalogue_record: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    values = catalogue_record.get("entries")

    if not isinstance(values, list):
        raise MonthlySourceTruthExecutionError(
            "current catalogue entries are malformed"
        )

    result: dict[str, Mapping[str, object]] = {}

    for value in values:
        if not isinstance(value, Mapping):
            raise MonthlySourceTruthExecutionError(
                "current catalogue entry is malformed"
            )

        accession = str(
            value.get(
                "canonical_genbank_assembly_accession",
                "",
            )
        )

        if GCA_RE.fullmatch(accession) is None:
            raise MonthlySourceTruthExecutionError(
                "current catalogue contains invalid accession"
            )

        if accession in result:
            raise MonthlySourceTruthExecutionError(
                "current catalogue contains duplicate accession"
            )

        result[accession] = value

    return result


def _current_batch_evidence(
    *,
    cache_execution,
    completion_context,
    provenance: Mapping[str, object],
    expected_commit: str,
):
    release_id = str(
        provenance.get("cache_origin_release_id")
    )

    if release_id != completion_context.release_id:
        raise MonthlySourceTruthExecutionError(
            "current-origin provenance release differs from current completion"
        )

    if (
        provenance.get(
            "cache_origin_source_snapshot_id"
        )
        != completion_context.source_snapshot_id
    ):
        raise MonthlySourceTruthExecutionError(
            "current-origin source snapshot differs from current completion"
        )

    if (
        provenance.get(
            "cache_origin_git_commit"
        )
        != expected_commit
    ):
        raise MonthlySourceTruthExecutionError(
            "current-origin Git commit differs from current execution"
        )

    expected_completion_sha = hashlib.sha256(
        completion_context.completion_payload
    ).hexdigest()

    if (
        provenance.get(
            "origin_sequence_acquisition_completion_sha256"
        )
        != expected_completion_sha
    ):
        raise MonthlySourceTruthExecutionError(
            "current-origin completion SHA256 differs from catalogue provenance"
        )

    batch_id = str(
        provenance.get(
            "batch_id",
            "",
        )
    )

    completion_rows = (
        completion_context
        .completion_record
        .get(
            "batches"
        )
    )

    if not isinstance(
        completion_rows,
        list,
    ):
        raise MonthlySourceTruthExecutionError(
            "current completion batch list is malformed"
        )

    completion_matches = [
        row
        for row in completion_rows
        if (
            isinstance(
                row,
                Mapping,
            )
            and row.get(
                "batch_id"
            )
            == batch_id
        )
    ]

    if len(
        completion_matches
    ) != 1:
        raise MonthlySourceTruthExecutionError(
            "current completion does not contain exactly one provenance batch"
        )

    completion_batch = (
        completion_matches[
            0
        ]
    )

    provenance_comparisons = (
        (
            provenance.get(
                "requested_accessions"
            ),
            completion_batch.get(
                "requested_accessions"
            ),
            "requested accession count",
        ),
        (
            provenance.get(
                "accessions_sha256"
            ),
            completion_batch.get(
                "accessions_sha256"
            ),
            "accession-list SHA256",
        ),
        (
            provenance[
                "batch_summary"
            ][
                "sha256"
            ],
            completion_batch.get(
                "batch_summary_sha256"
            ),
            "batch-summary SHA256",
        ),
        (
            provenance[
                "candidate_audit"
            ][
                "sha256"
            ],
            completion_batch.get(
                "candidate_sequence_audit_sha256"
            ),
            "candidate-audit SHA256",
        ),
        (
            provenance[
                "component_audit"
            ][
                "sha256"
            ],
            completion_batch.get(
                "component_sequence_audit_sha256"
            ),
            "component-audit SHA256",
        ),
        (
            provenance[
                "package_files_manifest"
            ][
                "sha256"
            ],
            completion_batch.get(
                "package_files_sha256"
            ),
            "package-files SHA256",
        ),
        (
            provenance.get(
                "origin_package_file_readback_sha256"
            ),
            completion_batch.get(
                "package_file_readback_sha256"
            ),
            "package read-back SHA256",
        ),
    )

    for observed, expected, label in (
        provenance_comparisons
    ):
        if observed != expected:
            raise MonthlySourceTruthExecutionError(
                f"current-origin {label} differs from current completion"
            )

    matching = [
        value
        for value in completion_context.batch_evidence
        if value.batch_id == batch_id
    ]

    if len(matching) != 1:
        raise MonthlySourceTruthExecutionError(
            "current completion does not provide exactly one origin batch"
        )

    evidence = matching[0]

    comparisons = (
        (
            evidence.summary_payload,
            provenance["batch_summary"]["sha256"],
            "batch summary",
        ),
        (
            evidence.candidate_audit_payload,
            provenance["candidate_audit"]["sha256"],
            "candidate audit",
        ),
        (
            evidence.component_audit_payload,
            provenance["component_audit"]["sha256"],
            "component audit",
        ),
        (
            evidence.package_files_payload,
            provenance["package_files_manifest"]["sha256"],
            "package-files manifest",
        ),
    )

    for payload, expected, label in comparisons:
        if hashlib.sha256(payload).hexdigest() != expected:
            raise MonthlySourceTruthExecutionError(
                f"current-origin {label} differs from catalogue provenance"
            )

    parser = getattr(
        monthly_sequence_cache_catalogue,
        "_parse_tsv",
        None,
    )

    if not callable(parser):
        raise MonthlySourceTruthExecutionError(
            "frozen catalogue TSV parser disappeared"
        )

    return cache_execution.BatchEvidence(
        provenance=provenance,
        candidate_rows=tuple(
            parser(
                evidence.candidate_audit_payload,
                fields=cache_execution.CANDIDATE_AUDIT_FIELDS,
                label="current candidate audit",
            )
        ),
        component_rows=tuple(
            parser(
                evidence.component_audit_payload,
                fields=cache_execution.COMPONENT_AUDIT_FIELDS,
                label="current component audit",
            )
        ),
        package_rows=tuple(
            parser(
                evidence.package_files_payload,
                fields=cache_execution.PACKAGE_FILE_FIELDS,
                label="current package-files manifest",
            )
        ),
    )


def validate_candidate_bridge(
    cache_execution,
    *,
    entry: Mapping[str, object],
    batch,
) -> CandidateBridge:
    accession = str(
        entry[
            "canonical_genbank_assembly_accession"
        ]
    )

    biosample = str(
        entry[
            "biosample"
        ]
    )

    candidate_row = cache_execution._candidate_row_for_accession(
        batch,
        accession,
    )

    if (
        candidate_row["expected_biosample"] != biosample
        or candidate_row["observed_biosample"] != biosample
    ):
        raise MonthlySourceTruthExecutionError(
            "candidate BioSample differs from catalogue/current metadata"
        )

    if (
        candidate_row["sequence_eligibility"] != "eligible"
        or candidate_row["exclusion_reasons"] != "none"
        or candidate_row["result"] != "PASS"
    ):
        raise MonthlySourceTruthExecutionError(
            "sequence-eligible catalogue entry disagrees with origin audit"
        )

    fasta_file = candidate_row["fasta_file"]

    if (
        not fasta_file
        or PurePosixPath(fasta_file).name != fasta_file
    ):
        raise MonthlySourceTruthExecutionError(
            "candidate FASTA file is not a basename"
        )

    fasta_sha = validate_sha256(
        candidate_row["fasta_sha256"],
        label="candidate FASTA SHA256",
    )

    try:
        primary_count = int(
            candidate_row["primary_assembly_records"]
        )
    except ValueError as exc:
        raise MonthlySourceTruthExecutionError(
            "candidate Primary Assembly count is invalid"
        ) from exc

    if primary_count <= 0:
        raise MonthlySourceTruthExecutionError(
            "candidate Primary Assembly count is not positive"
        )

    component_rows = tuple(
        cache_execution._component_rows_for_accession(
            batch,
            accession,
        )
    )

    if len(component_rows) != primary_count:
        raise MonthlySourceTruthExecutionError(
            "candidate component count differs from candidate audit"
        )

    package_rows = tuple(
        cache_execution._package_rows_for_accession(
            batch,
            accession,
        )
    )

    if not package_rows:
        raise MonthlySourceTruthExecutionError(
            "candidate has no accession-scoped package rows"
        )

    manifest_by_path: dict[str, Mapping[str, str]] = {}

    for row in package_rows:
        path = row["path"]

        if path in manifest_by_path:
            raise MonthlySourceTruthExecutionError(
                "candidate package manifest contains duplicate path"
            )

        manifest_by_path[path] = row

    artifacts_value = entry.get("package_artifacts")

    if (
        not isinstance(artifacts_value, list)
        or not artifacts_value
    ):
        raise MonthlySourceTruthExecutionError(
            "catalogue entry package artifacts are malformed"
        )

    artifact_by_path: dict[str, Mapping[str, object]] = {}

    for value in artifacts_value:
        if not isinstance(value, Mapping):
            raise MonthlySourceTruthExecutionError(
                "catalogue package artifact is malformed"
            )

        path = str(
            value.get(
                "package_path",
                "",
            )
        )

        if path in artifact_by_path:
            raise MonthlySourceTruthExecutionError(
                "catalogue entry contains duplicate package path"
            )

        artifact_by_path[path] = value

    if set(artifact_by_path) != set(manifest_by_path):
        raise MonthlySourceTruthExecutionError(
            "catalogue package artifacts differ from authenticated manifest"
        )

    for path, manifest in manifest_by_path.items():
        artifact = artifact_by_path[path]

        try:
            manifest_size = int(manifest["size_bytes"])
        except ValueError as exc:
            raise MonthlySourceTruthExecutionError(
                "package manifest size is invalid"
            ) from exc

        if (
            artifact.get("size_bytes") != manifest_size
            or artifact.get("sha256") != manifest["sha256"]
        ):
            raise MonthlySourceTruthExecutionError(
                "catalogue package artifact identity differs from manifest"
            )

        validate_sha256(
            manifest["sha256"],
            label="package manifest SHA256",
        )

    fasta_matches = [
        row
        for row in package_rows
        if (
            PurePosixPath(row["path"]).name == fasta_file
            and row["sha256"] == fasta_sha
        )
    ]

    if len(fasta_matches) != 1:
        raise MonthlySourceTruthExecutionError(
            "candidate FASTA does not resolve to exactly one package row"
        )

    fasta_row = fasta_matches[0]
    fasta_path = fasta_row["path"]

    parts = PurePosixPath(fasta_path).parts

    if (
        len(parts) <= 3
        or parts[:3]
        != (
            "ncbi_dataset",
            "data",
            accession,
        )
        or ".." in parts
    ):
        raise MonthlySourceTruthExecutionError(
            "candidate FASTA package path is not accession scoped"
        )

    try:
        fasta_size = int(
            fasta_row["size_bytes"]
        )
    except ValueError as exc:
        raise MonthlySourceTruthExecutionError(
            "candidate FASTA package size is invalid"
        ) from exc

    if fasta_size <= 0:
        raise MonthlySourceTruthExecutionError(
            "candidate FASTA package size is not positive"
        )

    return CandidateBridge(
        accession=accession,
        biosample=biosample,
        candidate_row=candidate_row,
        component_rows=component_rows,
        package_rows=package_rows,
        fasta_package_path=fasta_path,
        fasta_sha256=fasta_sha,
        fasta_size_bytes=fasta_size,
        primary_assembly_records=primary_count,
    )


def _source_truth_objects(
    bridge: CandidateBridge,
    *,
    audit_path: Path,
):
    candidate = source_truth_execution.CandidateAudit(
        accession=bridge.accession,
        audit_path=audit_path,
        fasta_file=str(
            bridge.candidate_row["fasta_file"]
        ),
        fasta_sha256=bridge.fasta_sha256,
        primary_assembly_records=(
            bridge.primary_assembly_records
        ),
    )

    components = []

    for row in bridge.component_rows:
        try:
            length = int(row["length"])
        except ValueError as exc:
            raise MonthlySourceTruthExecutionError(
                "component length is invalid"
            ) from exc

        components.append(
            source_truth_execution.ComponentAudit(
                accession=bridge.accession,
                component_accession=(
                    row[
                        "component_genbank_accession"
                    ]
                ),
                length=length,
                topology=row["topology"],
                sequence_sha256=validate_sha256(
                    row["sequence_sha256"],
                    label="component sequence SHA256",
                ),
            )
        )

    package_manifest = {}

    for row in bridge.package_rows:
        path = row["path"]

        if path in package_manifest:
            raise MonthlySourceTruthExecutionError(
                "duplicate package path while building source-truth evidence"
            )

        try:
            size = int(row["size_bytes"])
        except ValueError as exc:
            raise MonthlySourceTruthExecutionError(
                "package size is invalid"
            ) from exc

        if size < 0:
            raise MonthlySourceTruthExecutionError(
                "package size is negative"
            )

        package_manifest[path] = (
            source_truth_execution.PackageFile(
                relative_path=path,
                size_bytes=size,
                sha256=validate_sha256(
                    row["sha256"],
                    label="package SHA256",
                ),
            )
        )

    return (
        candidate,
        tuple(components),
        package_manifest,
    )


def _observe_exact_file(
    path: Path,
    *,
    expected_sha256: str,
    expected_size_bytes: int,
) -> InputObservation:
    file_path = _require_regular_file(
        path,
        label="source-truth FASTA",
    )

    observed_size = file_path.stat().st_size

    if observed_size != expected_size_bytes:
        raise MonthlySourceTruthExecutionError(
            "source-truth FASTA size changed"
        )

    observed_sha = sha256_file(file_path)

    if observed_sha != expected_sha256:
        raise MonthlySourceTruthExecutionError(
            "source-truth FASTA SHA256 changed"
        )

    return InputObservation(
        path=file_path,
        sha256=observed_sha,
        size_bytes=observed_size,
    )


def _evaluate_current_candidate(
    *,
    bridge: CandidateBridge,
    stage1_root: Path,
    batch_id: str,
):
    batch_dir = (
        stage1_root
        / SEQUENCE_ACQUISITION_DIR
        / batch_id
    )

    candidate_audit = _require_regular_file(
        batch_dir
        / "candidate-sequence-audit.tsv",
        label="current candidate audit",
    )

    candidate, components, package_manifest = (
        _source_truth_objects(
            bridge,
            audit_path=candidate_audit,
        )
    )

    try:
        decision = source_truth_execution.evaluate_candidate(
            candidate,
            components,
            package_manifest,
        )

        resolver = getattr(
            source_truth_execution,
            "resolve_manifest_path",
            None,
        )

        if not callable(resolver):
            raise MonthlySourceTruthExecutionError(
                "frozen source-truth manifest resolver disappeared"
            )

        fasta_path = resolver(
            candidate.batch_dir,
            bridge.fasta_package_path,
        )

    except MonthlySourceTruthExecutionError:
        raise
    except Exception as exc:
        raise MonthlySourceTruthExecutionError(
            f"source-truth evaluation failed for {bridge.accession}"
        ) from exc

    observation = _observe_exact_file(
        fasta_path,
        expected_sha256=bridge.fasta_sha256,
        expected_size_bytes=bridge.fasta_size_bytes,
    )

    return decision, observation


def _evaluate_prior_candidate(
    *,
    cache_execution,
    authoritative_root: Path,
    materialization_root: Path,
    bridge: CandidateBridge,
):
    try:
        required = cache_execution.read_required_object(
            authoritative_root,
            sha256=bridge.fasta_sha256,
            expected_size_bytes=(
                bridge.fasta_size_bytes
            ),
            label=(
                f"{bridge.accession} source-truth FASTA"
            ),
        )
    except Exception as exc:
        raise MonthlySourceTruthExecutionError(
            f"required authoritative FASTA failed for {bridge.accession}"
        ) from exc

    candidate_root = (
        materialization_root
        / bridge.accession
    )

    if os.path.lexists(candidate_root):
        raise MonthlySourceTruthExecutionError(
            "candidate materialization path already exists"
        )

    candidate_root.mkdir(
        mode=0o700,
    )

    try:
        audit_path = (
            candidate_root
            / "candidate-sequence-audit.tsv"
        )

        _write_bytes_exclusive(
            audit_path,
            _serialize_tsv(
                [bridge.candidate_row],
                cache_execution.CANDIDATE_AUDIT_FIELDS,
            ),
            mode=0o600,
        )

        parts = PurePosixPath(
            bridge.fasta_package_path
        ).parts

        destination = (
            candidate_root
            / "package"
            / Path(*parts)
        )

        _write_bytes_exclusive(
            destination,
            required.payload,
            mode=0o400,
        )

        candidate, components, package_manifest = (
            _source_truth_objects(
                bridge,
                audit_path=audit_path,
            )
        )

        try:
            decision = (
                source_truth_execution.evaluate_candidate(
                    candidate,
                    components,
                    package_manifest,
                )
            )
        except Exception as exc:
            raise MonthlySourceTruthExecutionError(
                f"source-truth evaluation failed for {bridge.accession}"
            ) from exc

    finally:
        shutil.rmtree(
            candidate_root,
            ignore_errors=True,
        )

    observation = InputObservation(
        path=required.path,
        sha256=required.sha256,
        size_bytes=required.size_bytes,
    )

    return decision, observation


def reverify_observations(
    observations: Sequence[InputObservation],
) -> None:
    for observation in observations:
        _observe_exact_file(
            observation.path,
            expected_sha256=observation.sha256,
            expected_size_bytes=(
                observation.size_bytes
            ),
        )


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def build_completion_receipt(
    *,
    release_id: str,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    execution_commit: str,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
    catalogue_chain_count: int,
    catalogue_chain_sha256_value: str,
    sequence_cache_catalogue_sha256: str,
    sequence_cache_entries_sha256: str,
    retained_count: int,
    sequence_eligible_count: int,
    sequence_ineligible_count: int,
    retained_accessions_sha256: str,
    sequence_eligible_accessions_sha256: str,
    sequence_ineligible_accessions_sha256: str,
    decision_count: int,
    relation_count: int,
    decisions_sha256: str,
    relations_sha256: str,
    record_sha256: str,
) -> bytes:
    catalogue_chain_count = validate_count(
        catalogue_chain_count,
        label="catalogue-chain count",
    )

    retained_count = validate_count(
        retained_count,
        label="retained count",
    )

    sequence_eligible_count = validate_count(
        sequence_eligible_count,
        label="sequence-eligible count",
    )

    sequence_ineligible_count = validate_count(
        sequence_ineligible_count,
        label="sequence-ineligible count",
    )

    decision_count = validate_count(
        decision_count,
        label="decision count",
    )

    relation_count = validate_count(
        relation_count,
        label="relation count",
    )

    if catalogue_chain_count == 0:
        raise MonthlySourceTruthExecutionError(
            "catalogue-chain count must be positive"
        )

    if retained_count != (
        sequence_eligible_count
        + sequence_ineligible_count
    ):
        raise MonthlySourceTruthExecutionError(
            "completion population accounting is inconsistent"
        )

    if decision_count != sequence_eligible_count:
        raise MonthlySourceTruthExecutionError(
            "completion decision count differs from eligible count"
        )

    for value, label in (
        (
            source_snapshot_record_sha256,
            "source snapshot record SHA256",
        ),
        (
            metadata_record_sha256,
            "metadata record SHA256",
        ),
        (
            metadata_completion_sha256,
            "metadata completion SHA256",
        ),
        (
            catalogue_chain_sha256_value,
            "catalogue chain SHA256",
        ),
        (
            sequence_cache_catalogue_sha256,
            "sequence-cache catalogue SHA256",
        ),
        (
            sequence_cache_entries_sha256,
            "sequence-cache entries SHA256",
        ),
        (
            retained_accessions_sha256,
            "retained membership SHA256",
        ),
        (
            sequence_eligible_accessions_sha256,
            "eligible membership SHA256",
        ),
        (
            sequence_ineligible_accessions_sha256,
            "ineligible membership SHA256",
        ),
        (
            decisions_sha256,
            "decision artifact SHA256",
        ),
        (
            relations_sha256,
            "relation artifact SHA256",
        ),
        (
            record_sha256,
            "source-truth record SHA256",
        ),
    ):
        validate_sha256(value, label=label)

    record = {
        "catalogue_chain_count":
            catalogue_chain_count,
        "catalogue_chain_sha256":
            catalogue_chain_sha256_value,
        "decision_count":
            decision_count,
        "decisions_sha256":
            decisions_sha256,
        "execution_commit":
            validate_commit(
                execution_commit
            ),
        "metadata_completion_sha256":
            metadata_completion_sha256,
        "metadata_record_sha256":
            metadata_record_sha256,
        "monthly_source_truth_sha256":
            EXPECTED_MONTHLY_SOURCE_TRUTH_SHA256,
        "record_sha256":
            record_sha256,
        "relation_count":
            relation_count,
        "relations_sha256":
            relations_sha256,
        "release_id":
            release_id,
        "retained_accessions_sha256":
            retained_accessions_sha256,
        "retained_count":
            retained_count,
        "schema_version":
            COMPLETION_SCHEMA,
        "sequence_cache_catalogue_sha256":
            sequence_cache_catalogue_sha256,
        "sequence_cache_entries_sha256":
            sequence_cache_entries_sha256,
        "sequence_eligible_accessions_sha256":
            sequence_eligible_accessions_sha256,
        "sequence_eligible_count":
            sequence_eligible_count,
        "sequence_ineligible_accessions_sha256":
            sequence_ineligible_accessions_sha256,
        "sequence_ineligible_count":
            sequence_ineligible_count,
        "source_snapshot_id":
            source_snapshot_id,
        "source_snapshot_record_sha256":
            source_snapshot_record_sha256,
        "source_truth_execution_sha256":
            EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256,
        "status":
            COMPLETION_STATUS,
    }

    return _canonical_json_bytes(record)


def audit_completion_receipt(
    payload: bytes,
    **kwargs,
) -> Mapping[str, object]:
    if not isinstance(payload, bytes):
        raise TypeError(
            "source-truth completion receipt must be bytes"
        )

    expected = build_completion_receipt(
        **kwargs
    )

    if payload != expected:
        raise MonthlySourceTruthExecutionError(
            "source-truth completion receipt changed"
        )

    try:
        value = json.loads(
            payload.decode("ascii")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlySourceTruthExecutionError(
            "invalid source-truth completion JSON"
        ) from exc

    if (
        value.get("schema_version")
        != COMPLETION_SCHEMA
        or value.get("status")
        != COMPLETION_STATUS
    ):
        raise MonthlySourceTruthExecutionError(
            "source-truth completion schema/status changed"
        )

    return value


def _audit_scientific_payloads(
    *,
    decisions_payload: bytes,
    relations_payload: bytes,
    record_payload: bytes,
    catalogue_payload: bytes,
    current_metadata: Mapping[str, str],
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
) -> Mapping[str, object]:
    monthly_source_truth.audit_monthly_source_truth_decisions(
        decisions_payload
    )

    monthly_source_truth.audit_monthly_source_truth_relations(
        relations_payload
    )

    return monthly_source_truth.audit_monthly_source_truth_record(
        record_payload,
        catalogue_payload=catalogue_payload,
        current_metadata=current_metadata,
        release_id=release_id,
        source_snapshot_id=source_snapshot_id,
        origin_git_commit=execution_commit,
        metadata_record_sha256=metadata_record_sha256,
        metadata_completion_sha256=metadata_completion_sha256,
        decisions_payload=decisions_payload,
        relations_payload=relations_payload,
    )


def _remove_stage_directory(path: Path) -> None:
    if not os.path.lexists(path):
        return

    if path.is_symlink() or not path.is_dir():
        raise MonthlySourceTruthExecutionError(
            "cannot safely remove malformed Stage 4 directory"
        )

    for child in path.iterdir():
        if child.is_symlink() or not child.is_file():
            raise MonthlySourceTruthExecutionError(
                "unexpected Stage 4 publication entry"
            )

        child.unlink()

    path.rmdir()


def publish_scientific_stage(
    *,
    stage1_root: Path,
    payloads: Mapping[str, bytes],
    auditor: Callable[[Mapping[str, bytes]], object],
    stability_check: Callable[[], None],
) -> Path:
    final = (
        stage1_root
        / SOURCE_TRUTH_STAGE_NAME
    )

    partial = (
        stage1_root
        / SOURCE_TRUTH_PARTIAL_NAME
    )

    if os.path.lexists(final):
        raise MonthlySourceTruthExecutionError(
            "canonical source-truth stage already exists"
        )

    if os.path.lexists(partial):
        raise MonthlySourceTruthExecutionError(
            "source-truth partial stage already exists"
        )

    partial.mkdir(
        mode=0o755,
    )

    try:
        for name in (
            DECISIONS_NAME,
            RELATIONS_NAME,
            RECORD_NAME,
        ):
            _write_bytes_exclusive(
                partial
                / name,
                payloads[
                    name
                ],
            )

        observed_partial = (
            read_exact_scientific_stage(
                partial
            )
        )

        if observed_partial != dict(payloads):
            raise MonthlySourceTruthExecutionError(
                "partial scientific readback changed"
            )

        auditor(
            observed_partial
        )

        fsync_directory(
            partial
        )

        stability_check()

        try:
            final.mkdir(
                mode=0o755,
            )
        except FileExistsError as exc:
            raise MonthlySourceTruthExecutionError(
                "canonical source-truth directory appeared before publication"
            ) from exc

        try:
            for name in (
                DECISIONS_NAME,
                RELATIONS_NAME,
                RECORD_NAME,
            ):
                os.link(
                    partial
                    / name,
                    final
                    / name,
                    follow_symlinks=False,
                )

            fsync_directory(
                final
            )

            fsync_directory(
                stage1_root
            )

            observed_final = (
                read_exact_scientific_stage(
                    final
                )
            )

            if observed_final != dict(payloads):
                raise MonthlySourceTruthExecutionError(
                    "final scientific readback changed"
                )

            auditor(
                observed_final
            )

            stability_check()

        except Exception:
            _remove_stage_directory(
                final
            )

            fsync_directory(
                stage1_root
            )

            raise

    finally:
        if os.path.lexists(partial):
            _remove_stage_directory(
                partial
            )

            fsync_directory(
                stage1_root
            )

    return final


def publish_completion(
    *,
    stage1_root: Path,
    payload: bytes,
    auditor: Callable[[bytes], object],
    stability_check: Callable[[], None],
) -> Path:
    final = (
        stage1_root
        / COMPLETION_NAME
    )

    temporary = (
        stage1_root
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(final):
        raise MonthlySourceTruthExecutionError(
            "source-truth completion already exists"
        )

    if os.path.lexists(temporary):
        raise MonthlySourceTruthExecutionError(
            "source-truth completion temporary artifact already exists"
        )

    _write_bytes_exclusive(
        temporary,
        payload,
    )

    try:
        if temporary.read_bytes() != payload:
            raise MonthlySourceTruthExecutionError(
                "temporary completion readback changed"
            )

        auditor(
            payload
        )

        stability_check()

        try:
            os.link(
                temporary,
                final,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise MonthlySourceTruthExecutionError(
                "source-truth completion appeared before publication"
            ) from exc

        fsync_directory(
            stage1_root
        )

        try:
            final_payload = (
                _require_regular_file(
                    final,
                    label="source-truth completion",
                ).read_bytes()
            )

            if final_payload != payload:
                raise MonthlySourceTruthExecutionError(
                    "final completion readback changed"
                )

            auditor(
                final_payload
            )

            stability_check()

        except Exception:
            if os.path.lexists(final):
                os.unlink(final)

            fsync_directory(
                stage1_root
            )

            raise

    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)

            fsync_directory(
                stage1_root
            )

    return final


def execute_monthly_source_truth(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    authoritative_root: Path,
    execution_commit: str,
) -> MonthlySourceTruthExecutionResult:
    root = Path(repo).resolve()
    production = Path(production_root)
    stage1_input = Path(stage1_root)
    authoritative = Path(authoritative_root)

    commit = validate_commit(
        execution_commit
    )

    if not production.is_absolute():
        raise MonthlySourceTruthExecutionError(
            "production root must be absolute"
        )

    if not stage1_input.is_absolute():
        raise MonthlySourceTruthExecutionError(
            "stage1 root must be absolute"
        )

    if not authoritative.is_absolute():
        raise MonthlySourceTruthExecutionError(
            "authoritative root must be absolute"
        )

    production = _require_real_directory(
        production,
        label="production root",
    )

    authoritative = _require_real_directory(
        authoritative,
        label="authoritative root",
    )

    cache_execution = load_frozen_cache_execution(
        root
    )

    catalogue_execution = (
        load_frozen_catalogue_execution(
            root
        )
    )

    try:
        metadata_context = (
            cache_execution.load_current_metadata_context(
                repo=root,
                production_root=production,
                stage1_root=stage1_input,
                execution_commit=commit,
            )
        )
    except Exception as exc:
        raise MonthlySourceTruthExecutionError(
            "current metadata re-audit failed"
        ) from exc

    stage1 = metadata_context.stage1_root.resolve()

    if stage1 != stage1_input.resolve():
        raise MonthlySourceTruthExecutionError(
            "metadata audit changed Stage 1 root"
        )

    require_output_paths_clear(
        stage1
    )

    sequence_plan_record = (
        stage1
        / SEQUENCE_PLAN_DIR
        / SEQUENCE_PLAN_RECORD_NAME
    )

    fresh_target_manifest = (
        stage1
        / SEQUENCE_PLAN_DIR
        / FRESH_TARGET_NAME
    )

    try:
        completion_context = (
            catalogue_execution.audit_existing_completion(
                repo=root,
                production_root=production,
                stage1_root=stage1,
                sequence_plan_record=(
                    sequence_plan_record
                ),
                fresh_target_manifest=(
                    fresh_target_manifest
                ),
                execution_commit=commit,
            )
        )
    except Exception as exc:
        raise MonthlySourceTruthExecutionError(
            "current sequence-acquisition completion re-audit failed"
        ) from exc

    catalogue_path = (
        stage1
        / CATALOGUE_NAME
    )

    try:
        chain = tuple(
            catalogue_execution.discover_catalogue_chain(
                production,
                current_release_id=(
                    metadata_context.release_id
                ),
                include_current=True,
                current_catalogue_path=(
                    catalogue_path
                ),
            )
        )
    except Exception as exc:
        raise MonthlySourceTruthExecutionError(
            "complete current catalogue chain audit failed"
        ) from exc

    if not chain:
        raise MonthlySourceTruthExecutionError(
            "current catalogue chain is empty"
        )

    current_catalogue = chain[-1]

    if (
        current_catalogue.release_id
        != metadata_context.release_id
        or current_catalogue.origin_git_commit
        != commit
    ):
        raise MonthlySourceTruthExecutionError(
            "current catalogue identity differs from current release"
        )

    catalogue_record = (
        current_catalogue.catalogue_record
    )

    if (
        catalogue_record.get(
            "source_snapshot_id"
        )
        != metadata_context.source_snapshot_id
    ):
        raise MonthlySourceTruthExecutionError(
            "current catalogue source snapshot differs from metadata"
        )

    completion_sha = hashlib.sha256(
        completion_context.completion_payload
    ).hexdigest()

    if (
        catalogue_record.get(
            "sequence_acquisition_completion_sha256"
        )
        != completion_sha
    ):
        raise MonthlySourceTruthExecutionError(
            "current catalogue is not bound to re-audited acquisition completion"
        )

    catalogue_payload = (
        current_catalogue.catalogue_payload
    )

    catalogue_sha = (
        current_catalogue.catalogue_sha256
    )

    chain_count = len(chain)
    chain_sha = catalogue_chain_sha256(
        chain
    )

    try:
        population = (
            monthly_source_truth.build_monthly_source_truth_population(
                catalogue_payload,
                current_metadata=(
                    metadata_context.retained_metadata
                ),
                release_id=(
                    metadata_context.release_id
                ),
                source_snapshot_id=(
                    metadata_context.source_snapshot_id
                ),
                origin_git_commit=commit,
            )
        )
    except Exception as exc:
        raise MonthlySourceTruthExecutionError(
            "pure monthly source-truth population audit failed"
        ) from exc

    entries_by_accession = (
        _catalogue_entries_by_accession(
            catalogue_record
        )
    )

    provenance_by_sha = (
        _catalogue_provenance_by_sha(
            catalogue_record
        )
    )

    materialization_root = (
        stage1
        / MATERIALIZATION_NAME
    )

    if os.path.lexists(materialization_root):
        raise MonthlySourceTruthExecutionError(
            "source-truth materialization path already exists"
        )

    materialization_root.mkdir(
        mode=0o700,
    )

    decisions = []
    observations = []

    prior_batch_cache = {}
    current_batch_cache = {}

    try:
        for accession in (
            population.sequence_eligible_accessions
        ):
            entry = entries_by_accession.get(
                accession
            )

            if entry is None:
                raise MonthlySourceTruthExecutionError(
                    "eligible accession disappeared from current catalogue"
                )

            provenance_sha = validate_sha256(
                entry.get(
                    "origin_batch_provenance_sha256"
                ),
                label="entry batch-provenance SHA256",
            )

            provenance = provenance_by_sha.get(
                provenance_sha
            )

            if provenance is None:
                raise MonthlySourceTruthExecutionError(
                    "eligible catalogue entry references missing provenance"
                )

            origin_release = str(
                provenance.get(
                    "cache_origin_release_id"
                )
            )

            origin_class = (
                classify_origin_release(
                    origin_release,
                    metadata_context.release_id,
                )
            )

            if origin_class == "current":
                batch = current_batch_cache.get(
                    provenance_sha
                )

                if batch is None:
                    batch = _current_batch_evidence(
                        cache_execution=(
                            cache_execution
                        ),
                        completion_context=(
                            completion_context
                        ),
                        provenance=provenance,
                        expected_commit=commit,
                    )

                    current_batch_cache[
                        provenance_sha
                    ] = batch

                bridge = validate_candidate_bridge(
                    cache_execution,
                    entry=entry,
                    batch=batch,
                )

                decision, observation = (
                    _evaluate_current_candidate(
                        bridge=bridge,
                        stage1_root=stage1,
                        batch_id=str(
                            provenance[
                                "batch_id"
                            ]
                        ),
                    )
                )

            else:
                batch = prior_batch_cache.get(
                    provenance_sha
                )

                if batch is None:
                    try:
                        batch = (
                            cache_execution.load_batch_evidence(
                                authoritative,
                                provenance=provenance,
                            )
                        )
                    except Exception as exc:
                        raise MonthlySourceTruthExecutionError(
                            "earlier origin batch evidence could not be "
                            "restored from authoritative storage"
                        ) from exc

                    prior_batch_cache[
                        provenance_sha
                    ] = batch

                bridge = validate_candidate_bridge(
                    cache_execution,
                    entry=entry,
                    batch=batch,
                )

                decision, observation = (
                    _evaluate_prior_candidate(
                        cache_execution=(
                            cache_execution
                        ),
                        authoritative_root=(
                            authoritative
                        ),
                        materialization_root=(
                            materialization_root
                        ),
                        bridge=bridge,
                    )
                )

            decisions.append(
                decision
            )

            observations.append(
                observation
            )

    finally:
        if os.path.lexists(
            materialization_root
        ):
            if (
                materialization_root.is_symlink()
                or not materialization_root.is_dir()
            ):
                raise MonthlySourceTruthExecutionError(
                    "source-truth materialization path became unsafe"
                )

            shutil.rmtree(
                materialization_root
            )

    try:
        build = (
            monthly_source_truth.build_monthly_source_truth(
                population,
                decisions,
            )
        )

        decisions_payload = (
            monthly_source_truth
            .serialize_monthly_source_truth_decisions(
                build
            )
        )

        relations_payload = (
            monthly_source_truth
            .serialize_monthly_source_truth_relations(
                build
            )
        )

        record_payload = (
            monthly_source_truth
            .serialize_monthly_source_truth_record(
                build,
                metadata_record_sha256=(
                    metadata_context.metadata_record_sha256
                ),
                metadata_completion_sha256=(
                    metadata_context.metadata_completion_sha256
                ),
            )
        )

        audited_record = (
            _audit_scientific_payloads(
                decisions_payload=(
                    decisions_payload
                ),
                relations_payload=(
                    relations_payload
                ),
                record_payload=(
                    record_payload
                ),
                catalogue_payload=(
                    catalogue_payload
                ),
                current_metadata=(
                    metadata_context.retained_metadata
                ),
                release_id=(
                    metadata_context.release_id
                ),
                source_snapshot_id=(
                    metadata_context.source_snapshot_id
                ),
                execution_commit=commit,
                metadata_record_sha256=(
                    metadata_context.metadata_record_sha256
                ),
                metadata_completion_sha256=(
                    metadata_context.metadata_completion_sha256
                ),
            )
        )

    except Exception as exc:
        raise MonthlySourceTruthExecutionError(
            "monthly source-truth output contract failed"
        ) from exc

    decisions_sha = hashlib.sha256(
        decisions_payload
    ).hexdigest()

    relations_sha = hashlib.sha256(
        relations_payload
    ).hexdigest()

    record_sha = hashlib.sha256(
        record_payload
    ).hexdigest()

    original_metadata_identity = (
        cache_execution.metadata_context_identity(
            metadata_context
        )
    )

    def stability_check() -> None:
        try:
            observed_metadata = (
                cache_execution.load_current_metadata_context(
                    repo=root,
                    production_root=production,
                    stage1_root=stage1,
                    execution_commit=commit,
                )
            )
        except Exception as exc:
            raise MonthlySourceTruthExecutionError(
                "metadata changed during Stage 4 execution"
            ) from exc

        if (
            cache_execution.metadata_context_identity(
                observed_metadata
            )
            != original_metadata_identity
        ):
            raise MonthlySourceTruthExecutionError(
                "metadata identity changed during Stage 4 execution"
            )

        try:
            observed_completion = (
                catalogue_execution.audit_existing_completion(
                    repo=root,
                    production_root=production,
                    stage1_root=stage1,
                    sequence_plan_record=(
                        sequence_plan_record
                    ),
                    fresh_target_manifest=(
                        fresh_target_manifest
                    ),
                    execution_commit=commit,
                )
            )
        except Exception as exc:
            raise MonthlySourceTruthExecutionError(
                "acquisition completion changed during Stage 4 execution"
            ) from exc

        if (
            observed_completion.completion_payload
            != completion_context.completion_payload
        ):
            raise MonthlySourceTruthExecutionError(
                "acquisition completion identity changed during Stage 4 execution"
            )

        try:
            observed_chain = tuple(
                catalogue_execution.discover_catalogue_chain(
                    production,
                    current_release_id=(
                        metadata_context.release_id
                    ),
                    include_current=True,
                    current_catalogue_path=(
                        catalogue_path
                    ),
                )
            )
        except Exception as exc:
            raise MonthlySourceTruthExecutionError(
                "catalogue history changed during Stage 4 execution"
            ) from exc

        if (
            len(observed_chain) != chain_count
            or catalogue_chain_sha256(
                observed_chain
            )
            != chain_sha
        ):
            raise MonthlySourceTruthExecutionError(
                "catalogue chain identity changed during Stage 4 execution"
            )

        reverify_observations(
            observations
        )

    payloads = {
        DECISIONS_NAME:
            decisions_payload,
        RELATIONS_NAME:
            relations_payload,
        RECORD_NAME:
            record_payload,
    }

    def scientific_auditor(
        values: Mapping[str, bytes],
    ) -> object:
        return _audit_scientific_payloads(
            decisions_payload=(
                values[
                    DECISIONS_NAME
                ]
            ),
            relations_payload=(
                values[
                    RELATIONS_NAME
                ]
            ),
            record_payload=(
                values[
                    RECORD_NAME
                ]
            ),
            catalogue_payload=(
                catalogue_payload
            ),
            current_metadata=(
                metadata_context.retained_metadata
            ),
            release_id=(
                metadata_context.release_id
            ),
            source_snapshot_id=(
                metadata_context.source_snapshot_id
            ),
            execution_commit=commit,
            metadata_record_sha256=(
                metadata_context.metadata_record_sha256
            ),
            metadata_completion_sha256=(
                metadata_context.metadata_completion_sha256
            ),
        )

    stage_root = publish_scientific_stage(
        stage1_root=stage1,
        payloads=payloads,
        auditor=scientific_auditor,
        stability_check=stability_check,
    )

    completion_kwargs = {
        "release_id":
            metadata_context.release_id,
        "source_snapshot_id":
            metadata_context.source_snapshot_id,
        "source_snapshot_record_sha256":
            metadata_context.source_snapshot_record_sha256,
        "execution_commit":
            commit,
        "metadata_record_sha256":
            metadata_context.metadata_record_sha256,
        "metadata_completion_sha256":
            metadata_context.metadata_completion_sha256,
        "catalogue_chain_count":
            chain_count,
        "catalogue_chain_sha256_value":
            chain_sha,
        "sequence_cache_catalogue_sha256":
            catalogue_sha,
        "sequence_cache_entries_sha256":
            str(
                catalogue_record[
                    "entries_sha256"
                ]
            ),
        "retained_count":
            int(
                audited_record[
                    "retained_count"
                ]
            ),
        "sequence_eligible_count":
            int(
                audited_record[
                    "sequence_eligible_count"
                ]
            ),
        "sequence_ineligible_count":
            int(
                audited_record[
                    "sequence_ineligible_count"
                ]
            ),
        "retained_accessions_sha256":
            str(
                audited_record[
                    "retained_accessions_sha256"
                ]
            ),
        "sequence_eligible_accessions_sha256":
            str(
                audited_record[
                    "sequence_eligible_accessions_sha256"
                ]
            ),
        "sequence_ineligible_accessions_sha256":
            str(
                audited_record[
                    "sequence_ineligible_accessions_sha256"
                ]
            ),
        "decision_count":
            int(
                audited_record[
                    "decision_count"
                ]
            ),
        "relation_count":
            int(
                audited_record[
                    "relation_count"
                ]
            ),
        "decisions_sha256":
            decisions_sha,
        "relations_sha256":
            relations_sha,
        "record_sha256":
            record_sha,
    }

    completion_payload = (
        build_completion_receipt(
            **completion_kwargs
        )
    )

    def completion_auditor(
        payload: bytes,
    ) -> object:
        return audit_completion_receipt(
            payload,
            **completion_kwargs,
        )

    try:
        completion_path = publish_completion(
            stage1_root=stage1,
            payload=completion_payload,
            auditor=completion_auditor,
            stability_check=stability_check,
        )
    except Exception:
        _remove_stage_directory(
            stage_root
        )

        fsync_directory(
            stage1
        )

        raise

    return MonthlySourceTruthExecutionResult(
        release_id=(
            metadata_context.release_id
        ),
        source_snapshot_id=(
            metadata_context.source_snapshot_id
        ),
        stage_root=stage_root,
        completion_path=completion_path,
        retained_count=int(
            audited_record[
                "retained_count"
            ]
        ),
        sequence_eligible_count=int(
            audited_record[
                "sequence_eligible_count"
            ]
        ),
        sequence_ineligible_count=int(
            audited_record[
                "sequence_ineligible_count"
            ]
        ),
        decision_count=int(
            audited_record[
                "decision_count"
            ]
        ),
        relation_count=int(
            audited_record[
                "relation_count"
            ]
        ),
        decisions_sha256=decisions_sha,
        relations_sha256=relations_sha,
        record_sha256=record_sha,
        completion_sha256=hashlib.sha256(
            completion_payload
        ).hexdigest(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute BacSelect monthly Stage 4 source truth."
        )
    )

    parser.add_argument(
        "--expected-commit",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-test-sha256",
        required=True,
    )

    parser.add_argument(
        "--production-root",
        required=True,
    )

    parser.add_argument(
        "--stage1-root",
        required=True,
    )

    parser.add_argument(
        "--authoritative-root",
        required=True,
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    args = parser.parse_args(argv)

    if not args.authorize_real_execution:
        raise MonthlySourceTruthExecutionError(
            "production source-truth execution requires explicit authorization"
        )

    repo = Path(__file__).resolve().parents[2]

    repository_preflight(
        repo,
        expected_commit=(
            args.expected_commit
        ),
        expected_wrapper_sha256=(
            args.expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            args.expected_wrapper_test_sha256
        ),
    )

    result = execute_monthly_source_truth(
        repo=repo,
        production_root=Path(
            args.production_root
        ),
        stage1_root=Path(
            args.stage1_root
        ),
        authoritative_root=Path(
            args.authoritative_root
        ),
        execution_commit=(
            args.expected_commit
        ),
    )

    print(
        "PASS | BacSelect monthly source-truth execution complete"
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )

    print(
        f"stage_root={result.stage_root}"
    )

    print(
        f"completion_path={result.completion_path}"
    )

    print(
        f"retained_count={result.retained_count}"
    )

    print(
        "sequence_eligible_count="
        f"{result.sequence_eligible_count}"
    )

    print(
        "sequence_ineligible_count="
        f"{result.sequence_ineligible_count}"
    )

    print(
        f"decision_count={result.decision_count}"
    )

    print(
        f"relation_count={result.relation_count}"
    )

    print(
        f"decisions_sha256={result.decisions_sha256}"
    )

    print(
        f"relations_sha256={result.relations_sha256}"
    )

    print(
        f"record_sha256={result.record_sha256}"
    )

    print(
        f"completion_sha256={result.completion_sha256}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
