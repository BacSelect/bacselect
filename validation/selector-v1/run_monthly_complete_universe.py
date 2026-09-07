#!/usr/bin/env python3
"""Execute BacSelect monthly Stage 9 complete-universe construction.

Stage 9 adds no eligibility or taxonomy decision rule.

It authenticates the completed monthly Stage 8 result, selects exactly the
Stage 8 PASS rows, constructs CompleteUniverseRecord objects from accession and
species TaxID, validates them with the frozen BacSelect complete-universe
primitive, and publishes the deterministic monthly complete universe.

Historical selector-validation baseline intersection, holdout construction and
terminal-composition reconstruction are not part of monthly Stage 9.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
import csv
from dataclasses import dataclass
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType

from bacselect import source_complete_universe


STAGE_NAME = "complete-universe"
PARTIAL_NAME = "complete-universe.partial"

UNIVERSE_NAME = "complete-universe.tsv"
RECORD_NAME = "monthly-complete-universe-record.json"

COMPLETION_NAME = "complete-universe-completion-v1.json"
COMPLETION_TEMP_NAME = ".complete-universe-completion-v1.json.tmp"

RECORD_SCHEMA = "bacselect-monthly-complete-universe-record-v1"
RECORD_STATUS = "MONTHLY_COMPLETE_UNIVERSE_COMPLETE"

COMPLETION_SCHEMA = (
    "bacselect-monthly-complete-universe-completion-v1"
)
COMPLETION_STATUS = "COMPLETE_UNIVERSE_EXECUTION_COMPLETE"

STAGE8_WRAPPER_SHA256 = (
    "be3bd31dc5480c79c115442e0a10c18b"
    "aadf24752219da8ff6b2ea594b055d70"
)

STAGE8_TEST_SHA256 = (
    "6348a75452546e1029bf2383af9d6a5ad"
    "f1eca3ff473fb87e79b64c3c8773225"
)

COMPLETE_UNIVERSE_PRIMITIVE_SHA256 = (
    "024354a0e909e5a048fa1a408c809a3c"
    "772892c9cf9b517263bdbbe90c476bce"
)

COMPLETE_UNIVERSE_TEST_SHA256 = (
    "5cd589c916e27f57f1ed95f5a1a2af27"
    "5cbe5320af52cf4dc28ec179b8730651"
)

STAGE8_DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "organism_taxid",
    "normalized_organism_taxid",
    "species_taxid",
    "taxonomy_status",
    "taxonomy_reason",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class MonthlyCompleteUniverseError(RuntimeError):
    """Raised when monthly Stage 9 evidence fails closed."""


@dataclass(frozen=True)
class AuthenticatedStage8:
    upstream: object
    decisions_payload: bytes
    record_payload: bytes
    completion_payload: bytes
    record: Mapping[str, object]
    completion: Mapping[str, object]
    decisions_sha256: str
    record_sha256: str
    completion_sha256: str
    identity: tuple[object, ...]


@dataclass(frozen=True)
class MonthlyUniverseBuild:
    universe: tuple[
        source_complete_universe.CompleteUniverseRecord,
        ...
    ]
    universe_rows: tuple[Mapping[str, str], ...]
    universe_count: int
    species_count: int
    membership_sha256: str
    accession_species_mapping_sha256: str
    stage8_status_counts: Mapping[str, int]
    stage8_reason_counts: Mapping[str, int]


@dataclass(frozen=True)
class MonthlyCompleteUniverseResult:
    release_id: str
    source_snapshot_id: str
    taxonomy_snapshot_id: str
    stage_path: Path
    completion_path: Path
    universe_count: int
    species_count: int
    membership_sha256: str
    accession_species_mapping_sha256: str
    universe_sha256: str
    record_sha256: str
    completion_sha256: str


def _fail(message: str) -> None:
    raise MonthlyCompleteUniverseError(message)


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
        _fail(f"{label} must be a lowercase SHA256")

    return value


def _commit(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or _COMMIT_RE.fullmatch(value) is None
    ):
        _fail(f"{label} must be a lowercase Git commit")

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


def load_stage8(repo: Path) -> ModuleType:
    return _load_module(
        Path(repo)
        / "validation/selector-v1/"
          "run_monthly_taxonomy_resolution.py",
        module_name="_bacselect_frozen_stage8_for_stage9",
        expected_sha256=STAGE8_WRAPPER_SHA256,
    )


def repository_preflight(
    repo: Path,
    *,
    complete_universe_execution_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> tuple[Path, ModuleType]:
    root = Path(repo).resolve()

    if root.is_symlink() or not root.is_dir():
        _fail("repository root is not a real directory")

    execution_commit = _commit(
        complete_universe_execution_commit,
        label="complete-universe execution commit",
    )

    if _git(root, "rev-parse", "HEAD") != execution_commit:
        _fail(
            "repository HEAD differs from complete-universe "
            "execution commit"
        )

    if _git(root, "status", "--porcelain"):
        _fail("repository is not clean")

    identities = {
        (
            root
            / "validation/selector-v1/"
              "run_monthly_taxonomy_resolution.py"
        ):
            STAGE8_WRAPPER_SHA256,
        (
            root
            / "tests/"
              "test_run_monthly_taxonomy_resolution.py"
        ):
            STAGE8_TEST_SHA256,
        (
            root
            / "src/bacselect/source_complete_universe.py"
        ):
            COMPLETE_UNIVERSE_PRIMITIVE_SHA256,
        (
            root
            / "tests/test_source_complete_universe.py"
        ):
            COMPLETE_UNIVERSE_TEST_SHA256,
    }

    for path, expected in identities.items():
        if _sha256_file(path) != expected:
            _fail(
                f"frozen Stage 9 dependency SHA256 mismatch: {path}"
            )

    wrapper = (
        root
        / "validation/selector-v1/"
          "run_monthly_complete_universe.py"
    )

    wrapper_test = (
        root
        / "tests/"
          "test_run_monthly_complete_universe.py"
    )

    if (
        _sha256_file(wrapper)
        != _sha256(
            expected_wrapper_sha256,
            label="Stage 9 wrapper expected SHA256",
        )
    ):
        _fail("Stage 9 wrapper SHA256 mismatch")

    if (
        _sha256_file(wrapper_test)
        != _sha256(
            expected_wrapper_test_sha256,
            label="Stage 9 wrapper-test expected SHA256",
        )
    ):
        _fail("Stage 9 wrapper-test SHA256 mismatch")

    return root, load_stage8(root)


def _require_exact_stage(
    path: Path,
    *,
    expected: set[str],
) -> Path:
    stage = Path(path)

    if stage.is_symlink() or not stage.is_dir():
        _fail(f"canonical stage is invalid: {stage}")

    observed = {
        child.name
        for child in stage.iterdir()
    }

    if observed != expected:
        _fail(
            f"canonical stage inventory differs: {stage}"
        )

    for child in stage.iterdir():
        if child.is_symlink() or not child.is_file():
            _fail(
                f"canonical stage contains non-regular file: {child}"
            )

    return stage


def authenticate_stage8(
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
    expected_taxonomy_resolution_completion_sha256: str,
    stage8: ModuleType,
) -> AuthenticatedStage8:
    root = Path(repo).resolve()
    stage1 = Path(stage1_root).resolve()

    stage8_commit = _commit(
        taxonomy_resolution_execution_commit,
        label="taxonomy-resolution execution commit",
    )

    stage7_v3 = stage8.load_stage7_v3(root)

    upstream = stage8.authenticate_stage7_v3(
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
        taxonomy_execution_commit=taxonomy_execution_commit,
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
        expected_taxonomy_completion_sha256=(
            expected_taxonomy_completion_sha256
        ),
        stage7_v3=stage7_v3,
    )

    stage = _require_exact_stage(
        stage1 / stage8.STAGE_NAME,
        expected={
            stage8.DECISIONS_NAME,
            stage8.RECORD_NAME,
        },
    )

    decisions = (
        stage
        / stage8.DECISIONS_NAME
    ).read_bytes()

    record_payload = (
        stage
        / stage8.RECORD_NAME
    ).read_bytes()

    completion_path = (
        stage1
        / stage8.COMPLETION_NAME
    )

    if (
        completion_path.is_symlink()
        or not completion_path.is_file()
    ):
        _fail("Stage 8 completion is absent")

    completion_payload = completion_path.read_bytes()

    decisions_sha = _sha256_bytes(decisions)
    record_sha = _sha256_bytes(record_payload)
    completion_sha = _sha256_bytes(
        completion_payload
    )

    if (
        completion_sha
        != _sha256(
            expected_taxonomy_resolution_completion_sha256,
            label="expected Stage 8 completion SHA256",
        )
    ):
        _fail("Stage 8 completion SHA256 changed")

    try:
        completion = json.loads(
            completion_payload
        )
        record = json.loads(
            record_payload
        )
    except json.JSONDecodeError as exc:
        raise MonthlyCompleteUniverseError(
            "Stage 8 JSON evidence is invalid"
        ) from exc

    if (
        not isinstance(completion, dict)
        or not isinstance(record, dict)
    ):
        _fail("Stage 8 JSON evidence has wrong type")

    stage8.audit_completion_receipt(
        completion_payload,
        record_payload=record_payload,
        decisions_payload=decisions,
    )

    if (
        completion.get("schema_version")
        != stage8.COMPLETION_SCHEMA
        or completion.get("status")
        != stage8.COMPLETION_STATUS
    ):
        _fail("Stage 8 completion schema/status changed")

    if (
        record.get("schema_version")
        != stage8.RECORD_SCHEMA
        or record.get("status")
        != stage8.RECORD_STATUS
    ):
        _fail("Stage 8 record schema/status changed")

    if completion.get(
        "taxonomy_resolution_execution_commit"
    ) != stage8_commit:
        _fail("Stage 8 execution commit changed")

    if record.get(
        "taxonomy_resolution_execution_commit"
    ) != stage8_commit:
        _fail("Stage 8 record execution commit changed")

    if completion.get(
        "taxonomy_snapshot_completion_sha256"
    ) != upstream.completion_sha256:
        _fail(
            "Stage 8 no longer binds authenticated Stage 7"
        )

    if record.get(
        "taxonomy_snapshot_completion_sha256"
    ) != upstream.completion_sha256:
        _fail(
            "Stage 8 record no longer binds authenticated Stage 7"
        )

    if completion.get(
        "decisions_sha256"
    ) != decisions_sha:
        _fail("Stage 8 decision SHA256 changed")

    if completion.get(
        "record_sha256"
    ) != record_sha:
        _fail("Stage 8 record SHA256 changed")

    if record.get(
        "decisions_sha256"
    ) != decisions_sha:
        _fail(
            "Stage 8 record decision SHA256 changed"
        )

    if record.get(
        "source_production_commit"
    ) != source_production_commit:
        _fail(
            "Stage 8 source-production binding changed"
        )

    if record.get(
        "taxonomy_execution_commit"
    ) != taxonomy_execution_commit:
        _fail(
            "Stage 8 taxonomy-execution binding changed"
        )

    if record.get(
        "taxonomy_snapshot_id"
    ) != upstream.completion_record[
        "taxonomy_snapshot_id"
    ]:
        _fail("Stage 8 taxonomy snapshot changed")

    for path in (
        stage1 / stage8.PARTIAL_NAME,
        stage1 / stage8.COMPLETION_TEMP_NAME,
    ):
        if os.path.lexists(path):
            _fail(
                "incomplete Stage 8 authority remains"
            )

    identity = (
        upstream.identity,
        decisions_sha,
        record_sha,
        completion_sha,
    )

    return AuthenticatedStage8(
        upstream=upstream,
        decisions_payload=decisions,
        record_payload=record_payload,
        completion_payload=completion_payload,
        record=record,
        completion=completion,
        decisions_sha256=decisions_sha,
        record_sha256=record_sha,
        completion_sha256=completion_sha,
        identity=identity,
    )


def _positive_decimal(
    value: object,
    *,
    label: str,
) -> int:
    if (
        not isinstance(value, str)
        or not value.isdigit()
    ):
        _fail(
            f"{label} must be canonical positive decimal text"
        )

    parsed = int(value)

    if parsed <= 0 or str(parsed) != value:
        _fail(
            f"{label} must be canonical positive decimal text"
        )

    return parsed


def accession_species_mapping_sha256(
    universe: tuple[
        source_complete_universe.CompleteUniverseRecord,
        ...
    ],
) -> str:
    payload = "".join(
        f"{record.accession}\t{record.species_taxid}\n"
        for record in universe
    ).encode("ascii")

    return hashlib.sha256(payload).hexdigest()


def build_monthly_universe(
    authenticated: AuthenticatedStage8,
    *,
    expected_membership_sha256: str,
    expected_mapping_sha256: str,
) -> MonthlyUniverseBuild:
    if not isinstance(
        authenticated,
        AuthenticatedStage8,
    ):
        _fail(
            "authenticated Stage 8 has wrong type"
        )

    expected_membership = _sha256(
        expected_membership_sha256,
        label="expected Stage 9 membership SHA256",
    )

    expected_mapping = _sha256(
        expected_mapping_sha256,
        label=(
            "expected Stage 9 accession/species mapping SHA256"
        ),
    )

    try:
        text = authenticated.decisions_payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise MonthlyCompleteUniverseError(
            "Stage 8 decisions are not UTF-8"
        ) from exc

    if "\r" in text:
        _fail("Stage 8 decisions contain CR characters")

    reader = csv.DictReader(
        io.StringIO(text),
        delimiter="\t",
    )

    if tuple(
        reader.fieldnames or ()
    ) != STAGE8_DECISION_FIELDS:
        _fail("Stage 8 decision schema changed")

    rows = list(reader)

    expected_decision_count = authenticated.completion[
        "decision_count"
    ]

    if (
        not isinstance(expected_decision_count, int)
        or isinstance(expected_decision_count, bool)
        or len(rows) != expected_decision_count
    ):
        _fail("Stage 8 decision count changed")

    accessions = tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in rows
    )

    if accessions != tuple(sorted(accessions)):
        _fail("Stage 8 decisions are not accession-sorted")

    if len(set(accessions)) != len(accessions):
        _fail("Stage 8 decisions contain duplicate accession")

    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()

    universe_records: list[
        source_complete_universe.CompleteUniverseRecord
    ] = []

    for row in rows:
        status = row["taxonomy_status"]
        reason = row["taxonomy_reason"]

        status_counts[status] += 1
        reason_counts[reason] += 1

        if status == "PASS":
            if reason != "TAXONOMY_SPECIES_RESOLVED":
                _fail(
                    "Stage 8 PASS row has unexpected reason"
                )

            species_taxid = _positive_decimal(
                row["species_taxid"],
                label="species TaxID",
            )

            universe_records.append(
                source_complete_universe
                .CompleteUniverseRecord(
                    accession=row[
                        "canonical_genbank_assembly_accession"
                    ],
                    species_taxid=species_taxid,
                )
            )

        elif status == "REVIEW_UNRESOLVED":
            if row["species_taxid"] != "":
                _fail(
                    "Stage 8 unresolved row contains species TaxID"
                )

        else:
            _fail(
                "Stage 8 taxonomy status is unexpected"
            )

    observed_status = dict(
        sorted(status_counts.items())
    )
    observed_reason = dict(
        sorted(reason_counts.items())
    )

    if observed_status != {
        "PASS":
            authenticated.completion["pass_count"],
        "REVIEW_UNRESOLVED":
            authenticated.completion["unresolved_count"],
    }:
        _fail(
            "Stage 8 status accounting changed"
        )

    if sum(
        observed_status.values()
    ) != expected_decision_count:
        _fail(
            "Stage 8 status accounting does not close"
        )

    try:
        universe = (
            source_complete_universe
            .require_complete_universe(
                universe_records,
                expected_count=(
                    authenticated.completion[
                        "pass_count"
                    ]
                ),
                expected_species_count=(
                    authenticated.completion[
                        "resolved_distinct_species_taxid_count"
                    ]
                ),
            )
        )

        membership_sha = (
            source_complete_universe
            .complete_universe_membership_sha256(
                universe
            )
        )

        universe_rows = (
            source_complete_universe
            .complete_universe_rows(
                universe
            )
        )

    except ValueError as exc:
        raise MonthlyCompleteUniverseError(
            "complete-universe primitive failed closed"
        ) from exc

    if membership_sha != expected_membership:
        _fail(
            "complete-universe membership differs from "
            "frozen Stage 9 expectation"
        )

    mapping_sha = accession_species_mapping_sha256(
        universe
    )

    if mapping_sha != expected_mapping:
        _fail(
            "complete-universe accession/species mapping differs "
            "from frozen Stage 9 expectation"
        )

    return MonthlyUniverseBuild(
        universe=universe,
        universe_rows=universe_rows,
        universe_count=len(universe),
        species_count=len(
            {
                record.species_taxid
                for record in universe
            }
        ),
        membership_sha256=membership_sha,
        accession_species_mapping_sha256=(
            mapping_sha
        ),
        stage8_status_counts=observed_status,
        stage8_reason_counts=observed_reason,
    )


def _serialize_tsv(
    fields: tuple[str, ...],
    rows: tuple[Mapping[str, str], ...],
) -> bytes:
    lines = [
        "\t".join(fields)
    ]

    for row in rows:
        if set(row) != set(fields):
            _fail(
                "complete-universe row has unexpected fields"
            )

        values: list[str] = []

        for field in fields:
            value = row[field]

            if (
                not isinstance(value, str)
                or "\t" in value
                or "\n" in value
                or "\r" in value
            ):
                _fail(
                    "complete-universe row contains invalid TSV text"
                )

            values.append(value)

        lines.append(
            "\t".join(values)
        )

    return (
        "\n".join(lines)
        + "\n"
    ).encode("utf-8")


def serialize_universe(
    build: MonthlyUniverseBuild,
) -> bytes:
    if not isinstance(
        build,
        MonthlyUniverseBuild,
    ):
        _fail(
            "monthly universe build has wrong type"
        )

    return _serialize_tsv(
        source_complete_universe.COMPLETE_UNIVERSE_FIELDS,
        build.universe_rows,
    )


def build_record(
    *,
    authenticated: AuthenticatedStage8,
    build: MonthlyUniverseBuild,
    universe_payload: bytes,
    source_production_commit: str,
    taxonomy_execution_commit: str,
    taxonomy_resolution_execution_commit: str,
    complete_universe_execution_commit: str,
) -> bytes:
    stage8_record = authenticated.record

    record = {
        "schema_version":
            RECORD_SCHEMA,

        "status":
            RECORD_STATUS,

        "release_id":
            stage8_record["release_id"],

        "source_snapshot_id":
            stage8_record["source_snapshot_id"],

        "source_production_commit":
            _commit(
                source_production_commit,
                label="source production commit",
            ),

        "taxonomy_snapshot_id":
            stage8_record["taxonomy_snapshot_id"],

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

        "complete_universe_execution_commit":
            _commit(
                complete_universe_execution_commit,
                label="complete-universe execution commit",
            ),

        "taxonomy_resolution_decisions_sha256":
            authenticated.decisions_sha256,

        "taxonomy_resolution_record_sha256":
            authenticated.record_sha256,

        "taxonomy_resolution_completion_sha256":
            authenticated.completion_sha256,

        "complete_universe_primitive_sha256":
            COMPLETE_UNIVERSE_PRIMITIVE_SHA256,

        "complete_universe_input_count":
            authenticated.completion["pass_count"],

        "complete_universe_count":
            build.universe_count,

        "complete_universe_species_count":
            build.species_count,

        "complete_universe_membership_sha256":
            build.membership_sha256,

        "accession_species_mapping_sha256":
            build.accession_species_mapping_sha256,

        "complete_universe_artifact_sha256":
            _sha256_bytes(
                universe_payload
            ),

        "stage8_status_counts":
            dict(
                sorted(
                    build.stage8_status_counts.items()
                )
            ),

        "stage8_reason_counts":
            dict(
                sorted(
                    build.stage8_reason_counts.items()
                )
            ),

        "complete_eligible_universe_generated":
            True,

        "terminal_composition_reconstructed":
            False,

        "baseline_membership_consulted":
            False,

        "holdout_membership_generated":
            False,

        "structural_features_calculated":
            False,

        "selector_outcomes_calculated":
            False,
    }

    if (
        record["complete_universe_input_count"]
        != record["complete_universe_count"]
    ):
        _fail(
            "Stage 9 universe count differs from Stage 8 PASS count"
        )

    return _canonical_json(record)


def build_completion_receipt(
    *,
    record_payload: bytes,
    universe_payload: bytes,
) -> bytes:
    try:
        record = json.loads(
            record_payload
        )
    except json.JSONDecodeError as exc:
        raise MonthlyCompleteUniverseError(
            "complete-universe record is invalid JSON"
        ) from exc

    if (
        not isinstance(record, dict)
        or record.get("schema_version") != RECORD_SCHEMA
        or record.get("status") != RECORD_STATUS
    ):
        _fail(
            "complete-universe record schema/status changed"
        )

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

        "complete_universe_execution_commit":
            record[
                "complete_universe_execution_commit"
            ],

        "taxonomy_resolution_completion_sha256":
            record[
                "taxonomy_resolution_completion_sha256"
            ],

        "complete_universe_count":
            record["complete_universe_count"],

        "complete_universe_species_count":
            record[
                "complete_universe_species_count"
            ],

        "complete_universe_membership_sha256":
            record[
                "complete_universe_membership_sha256"
            ],

        "accession_species_mapping_sha256":
            record[
                "accession_species_mapping_sha256"
            ],

        "complete_universe_artifact_sha256":
            _sha256_bytes(
                universe_payload
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
    universe_payload: bytes,
) -> Mapping[str, object]:
    expected = build_completion_receipt(
        record_payload=record_payload,
        universe_payload=universe_payload,
    )

    if payload != expected:
        _fail(
            "complete-universe completion changed"
        )

    observed = json.loads(payload)

    if (
        observed.get("schema_version")
        != COMPLETION_SCHEMA
        or observed.get("status")
        != COMPLETION_STATUS
    ):
        _fail(
            "complete-universe completion schema/status changed"
        )

    return observed


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
        with os.fdopen(
            fd,
            "wb",
        ) as handle:
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


def execute_monthly_complete_universe(
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
    complete_universe_execution_commit: str,
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
    expected_source_truth_completion_sha256: str,
    expected_biosample_completion_sha256: str,
    expected_chromosome_completion_sha256: str,
    expected_taxonomy_completion_sha256: str,
    expected_taxonomy_resolution_completion_sha256: str,
    expected_universe_membership_sha256: str,
    expected_accession_species_mapping_sha256: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> MonthlyCompleteUniverseResult:
    root, stage8 = repository_preflight(
        repo,
        complete_universe_execution_commit=(
            complete_universe_execution_commit
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
        "taxonomy_resolution_execution_commit":
            taxonomy_resolution_execution_commit,
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
        "expected_taxonomy_resolution_completion_sha256":
            expected_taxonomy_resolution_completion_sha256,
        "stage8":
            stage8,
    }

    initial = authenticate_stage8(
        **auth_kwargs
    )

    final = stage1 / STAGE_NAME
    partial = stage1 / PARTIAL_NAME
    completion = stage1 / COMPLETION_NAME
    completion_temp = stage1 / COMPLETION_TEMP_NAME

    for path, label in (
        (
            final,
            "canonical complete-universe stage",
        ),
        (
            partial,
            "partial complete-universe stage",
        ),
        (
            completion,
            "complete-universe completion",
        ),
        (
            completion_temp,
            "complete-universe completion temporary artifact",
        ),
    ):
        if os.path.lexists(path):
            _fail(
                f"{label} already exists"
            )

    build = build_monthly_universe(
        initial,
        expected_membership_sha256=(
            expected_universe_membership_sha256
        ),
        expected_mapping_sha256=(
            expected_accession_species_mapping_sha256
        ),
    )

    universe_payload = serialize_universe(
        build
    )

    record_payload = build_record(
        authenticated=initial,
        build=build,
        universe_payload=universe_payload,
        source_production_commit=(
            source_production_commit
        ),
        taxonomy_execution_commit=(
            taxonomy_execution_commit
        ),
        taxonomy_resolution_execution_commit=(
            taxonomy_resolution_execution_commit
        ),
        complete_universe_execution_commit=(
            complete_universe_execution_commit
        ),
    )

    completion_payload = (
        build_completion_receipt(
            record_payload=record_payload,
            universe_payload=universe_payload,
        )
    )

    initial_identity = initial.identity

    def stability_check() -> None:
        observed = authenticate_stage8(
            **auth_kwargs
        )

        if observed.identity != initial_identity:
            _fail(
                "Stage 1-8 evidence changed during Stage 9"
            )

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    universe_path = (
        partial
        / UNIVERSE_NAME
    )

    record_path = (
        partial
        / RECORD_NAME
    )

    _write_no_clobber(
        universe_path,
        universe_payload,
    )

    _write_no_clobber(
        record_path,
        record_payload,
    )

    if universe_path.read_bytes() != universe_payload:
        _fail(
            "complete-universe artifact readback changed"
        )

    if record_path.read_bytes() != record_payload:
        _fail(
            "complete-universe record readback changed"
        )

    _fsync_directory(partial)

    stability_check()

    os.replace(
        partial,
        final,
    )

    _fsync_directory(stage1)

    _write_no_clobber(
        completion_temp,
        completion_payload,
    )

    audit_completion_receipt(
        completion_temp.read_bytes(),
        record_payload=record_payload,
        universe_payload=universe_payload,
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

        audit_completion_receipt(
            observed_completion,
            record_payload=record_payload,
            universe_payload=universe_payload,
        )

        stability_check()

    except Exception:
        if os.path.lexists(completion):
            os.unlink(completion)
            _fsync_directory(stage1)

        raise

    os.unlink(completion_temp)
    _fsync_directory(stage1)

    return MonthlyCompleteUniverseResult(
        release_id=initial.record["release_id"],
        source_snapshot_id=(
            initial.record["source_snapshot_id"]
        ),
        taxonomy_snapshot_id=(
            initial.record["taxonomy_snapshot_id"]
        ),
        stage_path=final,
        completion_path=completion,
        universe_count=build.universe_count,
        species_count=build.species_count,
        membership_sha256=(
            build.membership_sha256
        ),
        accession_species_mapping_sha256=(
            build.accession_species_mapping_sha256
        ),
        universe_sha256=_sha256_bytes(
            universe_payload
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
            "Execute BacSelect monthly Stage 9 complete universe."
        )
    )

    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--source-repo",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--production-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--stage1-root",
        type=Path,
        required=True,
    )

    for name in (
        "source-production-commit",
        "completion-execution-commit",
        "cache-execution-commit",
        "source-truth-execution-commit",
        "biosample-execution-commit",
        "chromosome-execution-commit",
        "taxonomy-execution-commit",
        "taxonomy-resolution-execution-commit",
        "complete-universe-execution-commit",
        "expected-completion-sha256",
        "expected-catalogue-sha256",
        "expected-source-truth-completion-sha256",
        "expected-biosample-completion-sha256",
        "expected-chromosome-completion-sha256",
        "expected-taxonomy-completion-sha256",
        "expected-taxonomy-resolution-completion-sha256",
        "expected-universe-membership-sha256",
        "expected-accession-species-mapping-sha256",
        "expected-wrapper-sha256",
        "expected-wrapper-test-sha256",
    ):
        parser.add_argument(
            "--" + name,
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
            "real Stage 9 execution requires explicit authorization"
        )

    result = execute_monthly_complete_universe(
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
        complete_universe_execution_commit=(
            args.complete_universe_execution_commit
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
        expected_taxonomy_resolution_completion_sha256=(
            args.expected_taxonomy_resolution_completion_sha256
        ),
        expected_universe_membership_sha256=(
            args.expected_universe_membership_sha256
        ),
        expected_accession_species_mapping_sha256=(
            args.expected_accession_species_mapping_sha256
        ),
        expected_wrapper_sha256=(
            args.expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            args.expected_wrapper_test_sha256
        ),
    )

    print(
        "PASS | BacSelect monthly complete universe complete"
    )
    print(f"release_id={result.release_id}")
    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )
    print(
        f"taxonomy_snapshot_id={result.taxonomy_snapshot_id}"
    )
    print(
        f"complete_universe_count={result.universe_count}"
    )
    print(
        f"complete_universe_species_count={result.species_count}"
    )
    print(
        "complete_universe_membership_sha256="
        f"{result.membership_sha256}"
    )
    print(
        "accession_species_mapping_sha256="
        f"{result.accession_species_mapping_sha256}"
    )
    print(
        f"complete_universe_sha256={result.universe_sha256}"
    )
    print(
        f"record_sha256={result.record_sha256}"
    )
    print(
        f"completion_path={result.completion_path}"
    )
    print(
        f"completion_sha256={result.completion_sha256}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
