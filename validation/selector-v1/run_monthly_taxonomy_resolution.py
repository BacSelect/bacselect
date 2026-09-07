#!/usr/bin/env python3
"""Execute BacSelect monthly Stage 8 taxonomy resolution.

This wrapper adds no taxonomy scientific rule. It authenticates the completed
monthly Stage 6 and Stage 7-v3 chain, derives exactly the Stage 6 PASS
membership, binds organism.tax_id from the frozen monthly Stage 1 raw source
JSONL, and delegates species resolution to the frozen BacSelect taxonomy
primitives.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Mapping

from bacselect import monthly_chromosome_integrity
from bacselect import source_taxonomy
from bacselect import source_taxonomy_execution


STAGE_NAME = "taxonomy-resolution"
PARTIAL_NAME = "taxonomy-resolution.partial"

DECISIONS_NAME = "taxonomy-resolution-decisions.tsv"
RECORD_NAME = "monthly-taxonomy-resolution-record.json"

COMPLETION_NAME = "taxonomy-resolution-completion-v1.json"
COMPLETION_TEMP_NAME = ".taxonomy-resolution-completion-v1.json.tmp"

RECORD_SCHEMA = "bacselect-monthly-taxonomy-resolution-record-v1"
RECORD_STATUS = "MONTHLY_TAXONOMY_RESOLUTION_COMPLETE"

COMPLETION_SCHEMA = (
    "bacselect-monthly-taxonomy-resolution-completion-v1"
)
COMPLETION_STATUS = "TAXONOMY_RESOLUTION_EXECUTION_COMPLETE"

DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "organism_taxid",
    "normalized_organism_taxid",
    "species_taxid",
    "taxonomy_status",
    "taxonomy_reason",
)

STAGE7_V3_WRAPPER_SHA256 = (
    "77fa87a126e9b7b3ed3234b056b6680d"
    "1501477399da6880663415b36dfbaa4c"
)

STAGE7_V3_TEST_SHA256 = (
    "9371dc4901acbad31199b4655d1b31c11"
    "e96db5a917433375a4f4cf01475ca11"
)

SOURCE_TAXONOMY_EXECUTION_SHA256 = (
    "426e42c87a58f454fbc8107b275623426"
    "81bea06cc38428bd884d8372b1e43a1"
)

SOURCE_POST_SEQUENCE_SHA256 = (
    "62fa1e2f7d806f94b5f5eca73fb768745"
    "d3913a4b218a4d354562033cd300fe8"
)

SOURCE_TAXONOMY_SHA256 = (
    "9c8c4149c5db2a757e8c201a6523bdb1"
    "13511b5f72a4dd2893572dd8c7928e4d"
)

SOURCE_ELIGIBILITY_SHA256 = (
    "6e57dd950f972a9883e8fcbc78a18c694"
    "a5fabda58b03835f268eef681a03cc2"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class MonthlyTaxonomyResolutionError(RuntimeError):
    """Raised when monthly Stage 8 fails closed."""


@dataclass(frozen=True)
class AuthenticatedStage7V3:
    stage6: object
    support_result: object
    completion_payload: bytes
    completion_record: Mapping[str, object]
    completion_sha256: str
    stage_path: Path
    identity: tuple[object, ...]


@dataclass(frozen=True)
class Stage8Population:
    compatibility_population: object
    status_counts: Mapping[str, int]
    reason_counts: Mapping[str, int]


@dataclass(frozen=True)
class MonthlyTaxonomyResolutionResult:
    release_id: str
    source_snapshot_id: str
    taxonomy_snapshot_id: str
    stage_path: Path
    completion_path: Path
    input_candidate_count: int
    pass_count: int
    unresolved_count: int
    resolved_distinct_species_taxid_count: int
    decisions_sha256: str
    record_sha256: str
    completion_sha256: str


def _fail(message: str) -> None:
    raise MonthlyTaxonomyResolutionError(message)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    source = Path(path)

    if source.is_symlink() or not source.is_file():
        _fail(f"required regular file missing: {source}")

    digest = hashlib.sha256()

    with source.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def _sha256(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or _SHA256_RE.fullmatch(value) is None
    ):
        _fail(f"{label} is not a lowercase SHA256")

    return value


def _commit(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or _COMMIT_RE.fullmatch(value) is None
    ):
        _fail(f"{label} is not a lowercase Git commit")

    return value


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return result.stdout.strip()


def _canonical_json(
    payload: Mapping[str, object],
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _load_module(
    path: Path,
    *,
    module_name: str,
    expected_sha256: str,
) -> ModuleType:
    candidate = Path(path)

    if candidate.is_symlink() or not candidate.is_file():
        _fail(f"{module_name} is not a regular file")

    if _sha256_file(candidate) != expected_sha256:
        _fail(f"{module_name} SHA256 mismatch")

    spec = importlib.util.spec_from_file_location(
        module_name,
        candidate,
    )

    if spec is None or spec.loader is None:
        _fail(f"cannot import {module_name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def load_stage7_v3(repo: Path) -> ModuleType:
    return _load_module(
        Path(repo)
        / "validation/selector-v1/"
          "run_monthly_taxonomy_snapshot_v3.py",
        module_name="_bacselect_frozen_stage7_v3_for_stage8",
        expected_sha256=STAGE7_V3_WRAPPER_SHA256,
    )


def repository_preflight(
    repo: Path,
    *,
    taxonomy_resolution_execution_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> tuple[Path, ModuleType]:
    root = Path(repo).resolve()

    if root.is_symlink() or not root.is_dir():
        _fail("repository root is not a real directory")

    execution_commit = _commit(
        taxonomy_resolution_execution_commit,
        label="taxonomy-resolution execution commit",
    )

    if _git(root, "rev-parse", "HEAD") != execution_commit:
        _fail(
            "repository HEAD differs from taxonomy-resolution "
            "execution commit"
        )

    if _git(root, "status", "--porcelain"):
        _fail("repository is not clean")

    frozen_files = {
        (
            root
            / "validation/selector-v1/"
              "run_monthly_taxonomy_snapshot_v3.py"
        ):
            STAGE7_V3_WRAPPER_SHA256,
        (
            root
            / "tests/"
              "test_run_monthly_taxonomy_snapshot_v3.py"
        ):
            STAGE7_V3_TEST_SHA256,
        (
            root
            / "src/bacselect/source_taxonomy_execution.py"
        ):
            SOURCE_TAXONOMY_EXECUTION_SHA256,
        (
            root
            / "src/bacselect/"
              "source_post_sequence_eligibility.py"
        ):
            SOURCE_POST_SEQUENCE_SHA256,
        (
            root
            / "src/bacselect/source_taxonomy.py"
        ):
            SOURCE_TAXONOMY_SHA256,
        (
            root
            / "src/bacselect/source_eligibility.py"
        ):
            SOURCE_ELIGIBILITY_SHA256,
    }

    for path, expected in frozen_files.items():
        if _sha256_file(path) != expected:
            _fail(
                f"frozen Stage 8 dependency SHA256 mismatch: {path}"
            )

    wrapper = (
        root
        / "validation/selector-v1/"
          "run_monthly_taxonomy_resolution.py"
    )

    wrapper_test = (
        root
        / "tests/"
          "test_run_monthly_taxonomy_resolution.py"
    )

    if (
        _sha256_file(wrapper)
        != _sha256(
            expected_wrapper_sha256,
            label="Stage 8 wrapper expected SHA256",
        )
    ):
        _fail("Stage 8 wrapper SHA256 mismatch")

    if (
        _sha256_file(wrapper_test)
        != _sha256(
            expected_wrapper_test_sha256,
            label="Stage 8 wrapper-test expected SHA256",
        )
    ):
        _fail("Stage 8 wrapper-test SHA256 mismatch")

    return root, load_stage7_v3(root)


def authenticate_stage7_v3(
    *,
    repo: Path,
    source_repo: Path,
    production_root: Path,
    stage1_root: Path,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    chromosome_execution_commit: str,
    taxonomy_execution_commit: str,
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
    expected_source_truth_completion_sha256: str,
    expected_biosample_completion_sha256: str,
    expected_chromosome_completion_sha256: str,
    expected_taxonomy_completion_sha256: str,
    stage7_v3: ModuleType,
) -> AuthenticatedStage7V3:
    root = Path(repo).resolve()
    stage1 = Path(stage1_root).resolve()

    taxonomy_commit = _commit(
        taxonomy_execution_commit,
        label="taxonomy execution commit",
    )

    v2 = stage7_v3.load_stage7_v2(root)
    v1 = v2.load_stage7_v1(root)
    stage6_v2 = v2.load_stage6_v2(root)

    stage6 = v2.authenticate_stage6_v2(
        repo=root,
        source_repo=Path(source_repo),
        production_root=Path(production_root),
        stage1_root=stage1,
        source_production_commit=source_production_commit,
        completion_execution_commit=completion_execution_commit,
        cache_execution_commit=cache_execution_commit,
        source_truth_execution_commit=(
            source_truth_execution_commit
        ),
        biosample_execution_commit=biosample_execution_commit,
        chromosome_execution_commit=chromosome_execution_commit,
        expected_completion_sha256=expected_completion_sha256,
        expected_catalogue_sha256=expected_catalogue_sha256,
        expected_source_truth_completion_sha256=(
            expected_source_truth_completion_sha256
        ),
        expected_biosample_completion_sha256=(
            expected_biosample_completion_sha256
        ),
        expected_chromosome_completion_sha256=(
            expected_chromosome_completion_sha256
        ),
        stage7_v1=v1,
        stage6_v2=stage6_v2,
    )

    stage = stage1 / v1.STAGE_NAME
    completion_path = stage1 / stage7_v3.COMPLETION_NAME

    if stage.is_symlink() or not stage.is_dir():
        _fail("canonical Stage 7 directory is invalid")

    if (
        completion_path.is_symlink()
        or not completion_path.is_file()
    ):
        _fail("Stage 7-v3 completion is absent")

    completion_payload = completion_path.read_bytes()
    completion_sha = _sha256_bytes(completion_payload)

    if (
        completion_sha
        != _sha256(
            expected_taxonomy_completion_sha256,
            label="expected Stage 7-v3 completion SHA256",
        )
    ):
        _fail("Stage 7-v3 completion SHA256 changed")

    try:
        completion = json.loads(completion_payload)
    except json.JSONDecodeError as exc:
        raise MonthlyTaxonomyResolutionError(
            "Stage 7-v3 completion is invalid JSON"
        ) from exc

    if not isinstance(completion, dict):
        _fail("Stage 7-v3 completion must be an object")

    if (
        completion.get("schema_version")
        != stage7_v3.COMPLETION_SCHEMA
        or completion.get("status")
        != stage7_v3.COMPLETION_STATUS
    ):
        _fail("Stage 7-v3 completion schema/status changed")

    if (
        completion.get("taxonomy_execution_commit")
        != taxonomy_commit
    ):
        _fail("Stage 7 taxonomy execution commit changed")

    if (
        completion.get("local_cas_status")
        != stage7_v3.LOCAL_CAS_STATUS
    ):
        _fail("Stage 7 local-CAS status changed")

    if (
        completion.get("durable_archive_boundary")
        != stage7_v3.DURABLE_ARCHIVE_BOUNDARY
    ):
        _fail("Stage 7 durable archive boundary changed")

    support = (
        v1.monthly_taxonomy_snapshot_execution
        .MonthlyTaxonomySupportResult(
            workspace=stage,
            release_id=completion["release_id"],
            source_snapshot_id=completion["source_snapshot_id"],
            taxonomy_snapshot_id=completion["taxonomy_snapshot_id"],
            acquisition_provenance_sha256=(
                completion[
                    "taxonomy_acquisition_provenance_sha256"
                ]
            ),
            content_manifest_sha256=(
                completion[
                    "taxonomy_content_manifest_sha256"
                ]
            ),
            record_sha256=(
                completion[
                    "monthly_taxonomy_snapshot_record_sha256"
                ]
            ),
            archive_sha256=(
                completion["taxonomy_archive_sha256"]
            ),
            nodes_sha256=completion["nodes_sha256"],
            merged_sha256=completion["merged_sha256"],
            delnodes_sha256=completion["delnodes_sha256"],
            authoritative_manifest_sha256=(
                completion["local_cas_manifest_sha256"]
            ),
            authoritative_manifest_key=(
                completion["local_cas_manifest_key"]
            ),
            authoritative_receipt_sha256=(
                completion["local_cas_receipt_sha256"]
            ),
            authoritative_receipt_key=(
                completion["local_cas_receipt_key"]
            ),
            authoritative_verified_object_count=(
                completion[
                    "local_cas_verified_object_count"
                ]
            ),
        )
    )

    v1.audit_stage_directory(
        stage,
        support_result=support,
    )

    completion_kwargs = {
        "upstream":
            stage6,

        "support_result":
            support,

        "validation_wrapper_sha256":
            STAGE7_V3_WRAPPER_SHA256,

        "source_production_commit":
            source_production_commit,

        "completion_execution_commit":
            completion_execution_commit,

        "cache_execution_commit":
            cache_execution_commit,

        "source_truth_execution_commit":
            source_truth_execution_commit,

        "biosample_execution_commit":
            biosample_execution_commit,

        "chromosome_execution_commit":
            chromosome_execution_commit,

        "taxonomy_execution_commit":
            taxonomy_commit,
    }

    stage7_v3.audit_completion_receipt_v3(
        v2,
        v1,
        completion_payload,
        **completion_kwargs,
    )

    identity = (
        stage6.identity,
        completion_sha,
        support.record_sha256,
        support.archive_sha256,
        support.nodes_sha256,
        support.merged_sha256,
        support.delnodes_sha256,
    )

    return AuthenticatedStage7V3(
        stage6=stage6,
        support_result=support,
        completion_payload=completion_payload,
        completion_record=completion,
        completion_sha256=completion_sha,
        stage_path=stage,
        identity=identity,
    )


def build_stage8_population(
    stage6_decisions_payload: bytes,
    *,
    stage6_completion_record: Mapping[str, object],
) -> Stage8Population:
    if not isinstance(stage6_completion_record, Mapping):
        _fail("Stage 6 completion record has wrong type")

    decisions_sha = _sha256_bytes(
        stage6_decisions_payload
    )

    if (
        decisions_sha
        != stage6_completion_record.get("decisions_sha256")
    ):
        _fail("Stage 6 decisions SHA256 differs from completion")

    rows = (
        monthly_chromosome_integrity
        .audit_monthly_chromosome_decisions(
            stage6_decisions_payload
        )
    )

    if (
        len(rows)
        != stage6_completion_record.get("decision_count")
    ):
        _fail("Stage 6 decision count changed")

    all_accessions = tuple(
        row["canonical_genbank_assembly_accession"]
        for row in rows
    )

    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    passed: list[str] = []

    for row in rows:
        status = row["chromosome_integrity_status"]
        reason = row["chromosome_integrity_reason"]

        status_counts[status] += 1
        reason_counts[reason] += 1

        if status == "PASS":
            passed.append(
                row[
                    "canonical_genbank_assembly_accession"
                ]
            )

    observed_status = dict(
        sorted(status_counts.items())
    )

    expected_status = {
        "PASS":
            stage6_completion_record.get("pass_count", 0),
        "EXCLUDE_SOURCE_REPLICON_INTEGRITY":
            stage6_completion_record.get("excluded_count", 0),
        "REVIEW_UNRESOLVED":
            stage6_completion_record.get("unresolved_count", 0),
    }

    expected_status = {
        key: value
        for key, value in expected_status.items()
        if value
    }

    if observed_status != expected_status:
        _fail("Stage 6 status accounting changed")

    pass_accessions = tuple(sorted(passed))

    if not pass_accessions:
        _fail("Stage 8 taxonomy input population is empty")

    all_membership_sha = (
        source_taxonomy_execution
        .accession_membership_sha256(
            all_accessions
        )
    )

    if (
        all_membership_sha
        != stage6_completion_record.get(
            "continue_accessions_sha256"
        )
    ):
        _fail("Stage 6 complete membership SHA256 changed")

    compatibility = (
        source_taxonomy_execution.Stage3Population(
            all_accessions=all_accessions,
            pass_accessions=pass_accessions,
            all_membership_sha256=all_membership_sha,
            pass_membership_sha256=(
                source_taxonomy_execution
                .accession_membership_sha256(
                    pass_accessions
                )
            ),
            status_counts=observed_status,
            reason_counts=dict(
                sorted(reason_counts.items())
            ),
            decision_artifact_sha256=decisions_sha,
        )
    )

    return Stage8Population(
        compatibility_population=compatibility,
        status_counts=observed_status,
        reason_counts=dict(
            sorted(reason_counts.items())
        ),
    )


def serialize_decisions(
    build: source_taxonomy_execution.Stage4DecisionBuild,
) -> bytes:
    if not isinstance(
        build,
        source_taxonomy_execution.Stage4DecisionBuild,
    ):
        _fail("taxonomy decision build has wrong type")

    lines = [
        "\t".join(DECISION_FIELDS)
    ]

    for row in build.rows:
        if set(row) != set(
            source_taxonomy_execution.STAGE4_DECISION_FIELDS
        ):
            _fail("taxonomy core decision schema changed")

        values = (
            row["canonical_genbank_assembly_accession"],
            row["organism_taxid"],
            row["normalized_organism_taxid"],
            row["species_taxid"],
            row["stage4_status"],
            row["stage4_reason"],
        )

        if any(
            not isinstance(value, str)
            or "\t" in value
            or "\n" in value
            or "\r" in value
            for value in values
        ):
            _fail("taxonomy decision contains invalid TSV text")

        lines.append(
            "\t".join(values)
        )

    return (
        "\n".join(lines)
        + "\n"
    ).encode("utf-8")


def audit_decisions(
    payload: bytes,
    *,
    expected_build: (
        source_taxonomy_execution.Stage4DecisionBuild
    ),
) -> None:
    expected = serialize_decisions(
        expected_build
    )

    if payload != expected:
        _fail("taxonomy-resolution decisions changed")


def build_record(
    *,
    authenticated: AuthenticatedStage7V3,
    population: Stage8Population,
    source: source_taxonomy_execution.SourceTaxidBundle,
    build: source_taxonomy_execution.Stage4DecisionBuild,
    decisions_payload: bytes,
    source_production_commit: str,
    taxonomy_execution_commit: str,
    taxonomy_resolution_execution_commit: str,
) -> bytes:
    stage7 = authenticated.completion_record
    stage6_completion = (
        authenticated
        .stage6
        .stage6_completion_record
    )

    input_population = (
        population.compatibility_population
    )

    status_counts = dict(
        sorted(build.status_counts.items())
    )

    pass_count = status_counts.get("PASS", 0)
    unresolved_count = status_counts.get(
        "REVIEW_UNRESOLVED",
        0,
    )

    if (
        pass_count
        + unresolved_count
        != len(input_population.pass_accessions)
    ):
        _fail("taxonomy resolution status counts do not close")

    record = {
        "schema_version":
            RECORD_SCHEMA,

        "status":
            RECORD_STATUS,

        "release_id":
            stage7["release_id"],

        "source_snapshot_id":
            stage7["source_snapshot_id"],

        "source_production_commit":
            _commit(
                source_production_commit,
                label="source production commit",
            ),

        "taxonomy_snapshot_id":
            stage7["taxonomy_snapshot_id"],

        "taxonomy_execution_commit":
            _commit(
                taxonomy_execution_commit,
                label="taxonomy execution commit",
            ),

        "taxonomy_resolution_execution_commit":
            _commit(
                taxonomy_resolution_execution_commit,
                label="taxonomy-resolution execution commit",
            ),

        "source_raw_response_sha256":
            stage7["source_raw_response_sha256"],

        "stage6_decisions_sha256":
            stage6_completion["decisions_sha256"],

        "stage6_record_sha256":
            stage6_completion["record_sha256"],

        "stage6_completion_sha256":
            authenticated.stage6.stage6_completion_sha256,

        "taxonomy_snapshot_record_sha256":
            stage7[
                "monthly_taxonomy_snapshot_record_sha256"
            ],

        "taxonomy_snapshot_completion_sha256":
            authenticated.completion_sha256,

        "taxonomy_archive_sha256":
            stage7["taxonomy_archive_sha256"],

        "nodes_sha256":
            stage7["nodes_sha256"],

        "merged_sha256":
            stage7["merged_sha256"],

        "delnodes_sha256":
            stage7["delnodes_sha256"],

        "source_taxonomy_execution_sha256":
            SOURCE_TAXONOMY_EXECUTION_SHA256,

        "source_post_sequence_eligibility_sha256":
            SOURCE_POST_SEQUENCE_SHA256,

        "source_taxonomy_sha256":
            SOURCE_TAXONOMY_SHA256,

        "source_eligibility_sha256":
            SOURCE_ELIGIBILITY_SHA256,

        "input_candidate_count":
            len(
                input_population.pass_accessions
            ),

        "input_membership_sha256":
            input_population.pass_membership_sha256,

        "source_record_count":
            source.source_record_count,

        "unique_organism_taxid_count":
            build.unique_organism_taxid_count,

        "decision_count":
            len(build.rows),

        "pass_count":
            pass_count,

        "unresolved_count":
            unresolved_count,

        "resolved_distinct_species_taxid_count":
            build.resolved_distinct_species_taxid_count,

        "status_counts":
            status_counts,

        "reason_counts":
            dict(
                sorted(
                    build.reason_counts.items()
                )
            ),

        "decisions_sha256":
            _sha256_bytes(
                decisions_payload
            ),

        "taxonomy_resolution_performed":
            True,

        "complete_eligible_universe_generated":
            False,

        "structural_features_calculated":
            False,

        "selector_outcomes_calculated":
            False,
    }

    return _canonical_json(record)


def build_completion_receipt(
    *,
    record_payload: bytes,
    decisions_payload: bytes,
) -> bytes:
    try:
        record = json.loads(record_payload)
    except json.JSONDecodeError as exc:
        raise MonthlyTaxonomyResolutionError(
            "taxonomy-resolution record is invalid JSON"
        ) from exc

    if (
        not isinstance(record, dict)
        or record.get("schema_version") != RECORD_SCHEMA
        or record.get("status") != RECORD_STATUS
    ):
        _fail("taxonomy-resolution record schema/status changed")

    completion = {
        "schema_version":
            COMPLETION_SCHEMA,

        "status":
            COMPLETION_STATUS,

        "release_id":
            record["release_id"],

        "source_snapshot_id":
            record["source_snapshot_id"],

        "source_production_commit":
            record["source_production_commit"],

        "taxonomy_snapshot_id":
            record["taxonomy_snapshot_id"],

        "taxonomy_execution_commit":
            record["taxonomy_execution_commit"],

        "taxonomy_resolution_execution_commit":
            record[
                "taxonomy_resolution_execution_commit"
            ],

        "stage6_completion_sha256":
            record["stage6_completion_sha256"],

        "taxonomy_snapshot_completion_sha256":
            record[
                "taxonomy_snapshot_completion_sha256"
            ],

        "input_candidate_count":
            record["input_candidate_count"],

        "input_membership_sha256":
            record["input_membership_sha256"],

        "decision_count":
            record["decision_count"],

        "pass_count":
            record["pass_count"],

        "unresolved_count":
            record["unresolved_count"],

        "resolved_distinct_species_taxid_count":
            record[
                "resolved_distinct_species_taxid_count"
            ],

        "decisions_sha256":
            _sha256_bytes(
                decisions_payload
            ),

        "record_sha256":
            _sha256_bytes(
                record_payload
            ),
    }

    return _canonical_json(completion)


def audit_completion_receipt(
    payload: bytes,
    *,
    record_payload: bytes,
    decisions_payload: bytes,
) -> Mapping[str, object]:
    expected = build_completion_receipt(
        record_payload=record_payload,
        decisions_payload=decisions_payload,
    )

    if payload != expected:
        _fail("taxonomy-resolution completion changed")

    value = json.loads(payload)

    if (
        value.get("schema_version") != COMPLETION_SCHEMA
        or value.get("status") != COMPLETION_STATUS
    ):
        _fail(
            "taxonomy-resolution completion schema/status changed"
        )

    return value


def _write_no_clobber(
    path: Path,
    payload: bytes,
) -> None:
    target = Path(path)

    fd = os.open(
        target,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o644,
    )

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.unlink(target)
        except FileNotFoundError:
            pass
        raise


def _fsync_directory(path: Path) -> None:
    fd = os.open(
        Path(path),
        os.O_RDONLY | os.O_DIRECTORY,
    )

    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _count_lines(path: Path) -> int:
    count = 0

    with Path(path).open("rb") as handle:
        for _ in handle:
            count += 1

    if count <= 0:
        _fail("frozen raw source JSONL is empty")

    return count


def execute_monthly_taxonomy_resolution(
    *,
    repo: Path,
    source_repo: Path,
    production_root: Path,
    stage1_root: Path,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    chromosome_execution_commit: str,
    taxonomy_execution_commit: str,
    taxonomy_resolution_execution_commit: str,
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
    expected_source_truth_completion_sha256: str,
    expected_biosample_completion_sha256: str,
    expected_chromosome_completion_sha256: str,
    expected_taxonomy_completion_sha256: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> MonthlyTaxonomyResolutionResult:
    root, stage7_v3 = repository_preflight(
        repo,
        taxonomy_resolution_execution_commit=(
            taxonomy_resolution_execution_commit
        ),
        expected_wrapper_sha256=expected_wrapper_sha256,
        expected_wrapper_test_sha256=(
            expected_wrapper_test_sha256
        ),
    )

    stage1 = Path(stage1_root).resolve()

    auth_kwargs = {
        "repo":
            root,
        "source_repo":
            Path(source_repo),
        "production_root":
            Path(production_root),
        "stage1_root":
            stage1,
        "source_production_commit":
            source_production_commit,
        "completion_execution_commit":
            completion_execution_commit,
        "cache_execution_commit":
            cache_execution_commit,
        "source_truth_execution_commit":
            source_truth_execution_commit,
        "biosample_execution_commit":
            biosample_execution_commit,
        "chromosome_execution_commit":
            chromosome_execution_commit,
        "taxonomy_execution_commit":
            taxonomy_execution_commit,
        "expected_completion_sha256":
            expected_completion_sha256,
        "expected_catalogue_sha256":
            expected_catalogue_sha256,
        "expected_source_truth_completion_sha256":
            expected_source_truth_completion_sha256,
        "expected_biosample_completion_sha256":
            expected_biosample_completion_sha256,
        "expected_chromosome_completion_sha256":
            expected_chromosome_completion_sha256,
        "expected_taxonomy_completion_sha256":
            expected_taxonomy_completion_sha256,
        "stage7_v3":
            stage7_v3,
    }

    initial = authenticate_stage7_v3(
        **auth_kwargs
    )

    final = stage1 / STAGE_NAME
    partial = stage1 / PARTIAL_NAME
    completion = stage1 / COMPLETION_NAME
    completion_temp = stage1 / COMPLETION_TEMP_NAME

    for path, label in (
        (final, "canonical taxonomy-resolution stage"),
        (partial, "partial taxonomy-resolution stage"),
        (completion, "taxonomy-resolution completion"),
        (
            completion_temp,
            "taxonomy-resolution completion temporary artifact",
        ),
    ):
        if os.path.lexists(path):
            _fail(f"{label} already exists")

    population = build_stage8_population(
        initial.stage6.stage6_decisions_payload,
        stage6_completion_record=(
            initial.stage6.stage6_completion_record
        ),
    )

    raw_source = (
        stage1
        / "assembly_data_report.raw.jsonl"
    )

    expected_raw_sha = _sha256(
        initial.completion_record[
            "source_raw_response_sha256"
        ],
        label="Stage 7 frozen raw-source SHA256",
    )

    if _sha256_file(raw_source) != expected_raw_sha:
        _fail("frozen raw source JSONL SHA256 changed")

    source_record_count = _count_lines(
        raw_source
    )

    source = (
        source_taxonomy_execution.load_source_taxids(
            raw_source,
            expected_sha256=expected_raw_sha,
            expected_record_count=source_record_count,
            wanted_accessions=(
                population
                .compatibility_population
                .pass_accessions
            ),
        )
    )

    taxonomy = source_taxonomy.Taxonomy(
        nodes_path=(
            initial.stage_path
            / "nodes.dmp"
        ),
        merged_path=(
            initial.stage_path
            / "merged.dmp"
        ),
        delnodes_path=(
            initial.stage_path
            / "delnodes.dmp"
        ),
    )

    evaluations = (
        source_taxonomy_execution
        .evaluate_taxonomy_population(
            stage3=(
                population.compatibility_population
            ),
            source=source,
            taxonomy=taxonomy,
        )
    )

    build = (
        source_taxonomy_execution
        .build_decision_rows(
            evaluations,
            expected_total=len(
                population
                .compatibility_population
                .pass_accessions
            ),
        )
    )

    decisions_payload = serialize_decisions(
        build
    )

    record_payload = build_record(
        authenticated=initial,
        population=population,
        source=source,
        build=build,
        decisions_payload=decisions_payload,
        source_production_commit=source_production_commit,
        taxonomy_execution_commit=taxonomy_execution_commit,
        taxonomy_resolution_execution_commit=(
            taxonomy_resolution_execution_commit
        ),
    )

    completion_payload = build_completion_receipt(
        record_payload=record_payload,
        decisions_payload=decisions_payload,
    )

    initial_identity = initial.identity

    def stability_check() -> None:
        observed = authenticate_stage7_v3(
            **auth_kwargs
        )

        if observed.identity != initial_identity:
            _fail(
                "Stage 1-7 evidence changed during Stage 8"
            )

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    try:
        decisions_path = partial / DECISIONS_NAME
        record_path = partial / RECORD_NAME

        _write_no_clobber(
            decisions_path,
            decisions_payload,
        )

        _write_no_clobber(
            record_path,
            record_payload,
        )

        audit_decisions(
            decisions_path.read_bytes(),
            expected_build=build,
        )

        if record_path.read_bytes() != record_payload:
            _fail("taxonomy-resolution record readback changed")

        _fsync_directory(partial)

        stability_check()

        os.replace(
            partial,
            final,
        )

        _fsync_directory(stage1)

    except Exception:
        raise

    _write_no_clobber(
        completion_temp,
        completion_payload,
    )

    audit_completion_receipt(
        completion_temp.read_bytes(),
        record_payload=record_payload,
        decisions_payload=decisions_payload,
    )

    _fsync_directory(stage1)

    stability_check()

    try:
        os.link(
            completion_temp,
            completion,
            follow_symlinks=False,
        )

        _fsync_directory(stage1)

        observed_completion = (
            completion.read_bytes()
        )

        if observed_completion != completion_payload:
            _fail(
                "taxonomy-resolution completion readback changed"
            )

        audit_completion_receipt(
            observed_completion,
            record_payload=record_payload,
            decisions_payload=decisions_payload,
        )

        stability_check()

    except Exception:
        if os.path.lexists(completion):
            os.unlink(completion)
            _fsync_directory(stage1)

        raise

    os.unlink(completion_temp)
    _fsync_directory(stage1)

    status_counts = build.status_counts

    return MonthlyTaxonomyResolutionResult(
        release_id=initial.completion_record["release_id"],
        source_snapshot_id=(
            initial.completion_record[
                "source_snapshot_id"
            ]
        ),
        taxonomy_snapshot_id=(
            initial.completion_record[
                "taxonomy_snapshot_id"
            ]
        ),
        stage_path=final,
        completion_path=completion,
        input_candidate_count=len(
            population
            .compatibility_population
            .pass_accessions
        ),
        pass_count=status_counts.get("PASS", 0),
        unresolved_count=status_counts.get(
            "REVIEW_UNRESOLVED",
            0,
        ),
        resolved_distinct_species_taxid_count=(
            build.resolved_distinct_species_taxid_count
        ),
        decisions_sha256=_sha256_bytes(
            decisions_payload
        ),
        record_sha256=_sha256_bytes(
            record_payload
        ),
        completion_sha256=_sha256_bytes(
            completion_payload
        ),
    )


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute BacSelect monthly Stage 8 taxonomy resolution."
        )
    )

    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--production-root", type=Path, required=True)
    parser.add_argument("--stage1-root", type=Path, required=True)

    parser.add_argument(
        "--source-production-commit",
        required=True,
    )
    parser.add_argument(
        "--completion-execution-commit",
        required=True,
    )
    parser.add_argument(
        "--cache-execution-commit",
        required=True,
    )
    parser.add_argument(
        "--source-truth-execution-commit",
        required=True,
    )
    parser.add_argument(
        "--biosample-execution-commit",
        required=True,
    )
    parser.add_argument(
        "--chromosome-execution-commit",
        required=True,
    )
    parser.add_argument(
        "--taxonomy-execution-commit",
        required=True,
    )
    parser.add_argument(
        "--taxonomy-resolution-execution-commit",
        required=True,
    )

    parser.add_argument(
        "--expected-completion-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-catalogue-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-source-truth-completion-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-biosample-completion-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-chromosome-completion-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-taxonomy-completion-sha256",
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
        "--authorize-real-execution",
        action="store_true",
    )

    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(argv)

    if not args.authorize_real_execution:
        _fail(
            "real Stage 8 execution requires explicit authorization"
        )

    result = execute_monthly_taxonomy_resolution(
        repo=args.repo,
        source_repo=args.source_repo,
        production_root=args.production_root,
        stage1_root=args.stage1_root,
        source_production_commit=(
            args.source_production_commit
        ),
        completion_execution_commit=(
            args.completion_execution_commit
        ),
        cache_execution_commit=(
            args.cache_execution_commit
        ),
        source_truth_execution_commit=(
            args.source_truth_execution_commit
        ),
        biosample_execution_commit=(
            args.biosample_execution_commit
        ),
        chromosome_execution_commit=(
            args.chromosome_execution_commit
        ),
        taxonomy_execution_commit=(
            args.taxonomy_execution_commit
        ),
        taxonomy_resolution_execution_commit=(
            args.taxonomy_resolution_execution_commit
        ),
        expected_completion_sha256=(
            args.expected_completion_sha256
        ),
        expected_catalogue_sha256=(
            args.expected_catalogue_sha256
        ),
        expected_source_truth_completion_sha256=(
            args.expected_source_truth_completion_sha256
        ),
        expected_biosample_completion_sha256=(
            args.expected_biosample_completion_sha256
        ),
        expected_chromosome_completion_sha256=(
            args.expected_chromosome_completion_sha256
        ),
        expected_taxonomy_completion_sha256=(
            args.expected_taxonomy_completion_sha256
        ),
        expected_wrapper_sha256=(
            args.expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            args.expected_wrapper_test_sha256
        ),
    )

    print(
        "PASS | BacSelect monthly taxonomy resolution complete"
    )
    print(f"release_id={result.release_id}")
    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )
    print(
        f"taxonomy_snapshot_id={result.taxonomy_snapshot_id}"
    )
    print(
        f"input_candidate_count={result.input_candidate_count}"
    )
    print(f"pass_count={result.pass_count}")
    print(f"unresolved_count={result.unresolved_count}")
    print(
        "resolved_distinct_species_taxid_count="
        f"{result.resolved_distinct_species_taxid_count}"
    )
    print(
        f"decisions_sha256={result.decisions_sha256}"
    )
    print(f"record_sha256={result.record_sha256}")
    print(
        f"completion_path={result.completion_path}"
    )
    print(
        f"completion_sha256={result.completion_sha256}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
