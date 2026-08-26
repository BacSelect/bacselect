#!/usr/bin/env python3
"""Run frozen BacSelect selector-v1 Stage 1 source-truth execution.

Importing this module performs no production evidence access.

The wrapper verifies the prospective method, frozen BacSelect implementation,
historical/fresh membership handoffs, Project Finch algorithmic provenance,
and sequence-evidence structure before source-truth classification.

Identity-bearing outputs are written only beneath a caller-supplied scratch
output root.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable, Mapping, Sequence

from bacselect.source_truth_execution import (
    CandidateAudit,
    accession_membership_sha256,
    decision_rows,
    evaluate_candidate,
    load_candidate_population,
    load_component_index,
    load_package_manifest,
    relation_rows,
)


# ---------------------------------------------------------------------------
# Frozen BacSelect identities
# ---------------------------------------------------------------------------

METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-source-truth-execution.md"
)

SOURCE_TRUTH_RELATIVE = Path(
    "src/bacselect/source_truth.py"
)

EXECUTION_IMPLEMENTATION_RELATIVE = Path(
    "src/bacselect/source_truth_execution.py"
)

EXECUTION_TEST_RELATIVE = Path(
    "tests/test_source_truth_execution.py"
)

INHERITED_REFERENCES_RELATIVE = Path(
    "validation/selector-v1/"
    "post-sequence-inherited-implementation-references.tsv"
)

TRANSITIVE_REFERENCES_RELATIVE = Path(
    "validation/selector-v1/"
    "post-sequence-transitive-implementation-references.tsv"
)

FINAL_ACQUISITION_EVIDENCE_RELATIVE = Path(
    "validation/selector-v1/"
    "final-acquisition-manifest-evidence.json"
)

RECOVERY_001_CLARIFICATION_RELATIVE = Path(
    "validation/selector-v1/"
    "stage1-source-truth-recovery-001.md"
)


EXPECTED_METHOD_SHA256 = (
    "2d4acf6bef5caed189082c1109e841fafd617d8291b0610b9df1ca07ffe8a105"
)

EXPECTED_SOURCE_TRUTH_SHA256 = (
    "6aac349e591daebfc2569c14633cc807b5d7186ed4ed3e79f37f6627f5184486"
)

EXPECTED_EXECUTION_IMPLEMENTATION_SHA256 = (
    "83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92"
)

EXPECTED_EXECUTION_TEST_SHA256 = (
    "314b417ee05e2293ad37268963d9bdddb5bc58c9d6d6bc102a6cebe6ec926864"
)

EXPECTED_INHERITED_REFERENCES_SHA256 = (
    "64ce497a58e344e0c7136db1aa1a48c5cefda3996c759ae10f18f30a12ff8638"
)

EXPECTED_TRANSITIVE_REFERENCES_SHA256 = (
    "3b53fbf0ec945c1d7f5d4504028ba4d7f38a004764d45abd43cd149c12d62229"
)

EXPECTED_FINAL_ACQUISITION_EVIDENCE_SHA256 = (
    "e4f4c354f5a78f4efc123eede2dbee475440785fa72cc59d233b4406e64103bc"
)

EXPECTED_RECOVERY_001_CLARIFICATION_SHA256 = (
    "a5c836a2b1e7d98b54d6264ad51c600acbbdc222706119b228bf6398fb8fecd0"
)

EXPECTED_FRESH_RECOVERY_SUMMARY_SHA256 = (
    "e1a5eac79f62ae95651a4f83bff44636d7d0221c46b63c39490432eec67aa876"
)

EXPECTED_HISTORICAL_CANDIDATE_AUDITS_SHA256 = (
    "e6aad9f3adef78f8ce12228eee7d61d801643dd3cfbf11087f41b76c3bad7d37"
)


FROZEN_REPO_FILES = {
    METHOD_RELATIVE:
        EXPECTED_METHOD_SHA256,
    SOURCE_TRUTH_RELATIVE:
        EXPECTED_SOURCE_TRUTH_SHA256,
    EXECUTION_IMPLEMENTATION_RELATIVE:
        EXPECTED_EXECUTION_IMPLEMENTATION_SHA256,
    EXECUTION_TEST_RELATIVE:
        EXPECTED_EXECUTION_TEST_SHA256,
    INHERITED_REFERENCES_RELATIVE:
        EXPECTED_INHERITED_REFERENCES_SHA256,
    TRANSITIVE_REFERENCES_RELATIVE:
        EXPECTED_TRANSITIVE_REFERENCES_SHA256,
    FINAL_ACQUISITION_EVIDENCE_RELATIVE:
        EXPECTED_FINAL_ACQUISITION_EVIDENCE_SHA256,
    RECOVERY_001_CLARIFICATION_RELATIVE:
        EXPECTED_RECOVERY_001_CLARIFICATION_SHA256,
}


# ---------------------------------------------------------------------------
# Frozen production population
# ---------------------------------------------------------------------------

EXPECTED_HISTORICAL_AUDIT_ROWS = 55_426
EXPECTED_CACHE_REUSE = 55_151
EXPECTED_HISTORICAL_ELIGIBLE = 55_145
EXPECTED_HISTORICAL_INELIGIBLE = 6

EXPECTED_CACHE_VERIFICATION_ROWS = 55_426

EXPECTED_FRESH_AUDIT_ROWS = 15_319
EXPECTED_FRESH_ELIGIBLE = 13_335
EXPECTED_FRESH_INELIGIBLE = 1_984

EXPECTED_STAGE1_TOTAL = 68_480

RECOVERY_001_IDENTIFIER = (
    "stage1-source-truth-recovery-001"
)

RECOVERY_001_FAILED_ATTEMPT_COMMIT = (
    "25e44f29072d951172784364e0b16c291ecb2331"
)

RECOVERY_001_IMPLEMENTATION_COMMIT = (
    "fa26abf4f69d061a1ff1917788e33e8b01168229"
)

EXPECTED_RECOVERY_001_HISTORICAL_MEMBERSHIP_SHA256 = (
    "ed659ac6f9cba972a819ea3fb291d738ddeaf55842feb787a7c8ebbcf467952c"
)

EXPECTED_RECOVERY_001_FRESH_MEMBERSHIP_SHA256 = (
    "75a8312f090ffef9b2b0c0a41311c02c059a4f353491208c08d3cd64c8256e22"
)

EXPECTED_RECOVERY_001_COMBINED_MEMBERSHIP_SHA256 = (
    "810c584d578bad678e3a9ef3131e13777444961b906a57f5b2cbdcafd691e324"
)


ORDINARY_FRESH_BATCHES = (
    tuple(
        f"batch-{index:03d}"
        for index in range(1, 24)
    )
    + tuple(
        f"batch-{index:03d}"
        for index in range(25, 28)
    )
    + tuple(
        f"batch-{index:03d}"
        for index in range(29, 32)
    )
)

RECOVERY_FRESH_BATCHES = (
    "batch-024",
    "batch-028",
)


RECOVERY_EXPECTED_SHA256 = {
    "batch-024": {
        "candidate-sequence-audit.tsv":
            "9c202f0610450df68ffc966274846ba72a55b6f0a4ff8ff54476f8fef0ca344e",
        "component-sequence-audit.tsv":
            "a02c64c5d36e63bd5b1bc361441660c330be55a9a3d18d6fd314fff8274057c5",
        "source-package-files.tsv":
            "b5d7983fe6387d71cb528fed7b1faf0501102a167d2fc52e6750266771f6ae7f",
        "recovery-package-files.tsv":
            "b5d7983fe6387d71cb528fed7b1faf0501102a167d2fc52e6750266771f6ae7f",
        "recovery-summary.json":
            "ffa558518e70f14631696421f01619696aad4dc36cb84ae2e9a00a635cd2995d",
    },
    "batch-028": {
        "candidate-sequence-audit.tsv":
            "11ceb2c7dbe3c10b3a8d20432b3b7b9dc50fb92177e81955339425d70cd1ad1e",
        "component-sequence-audit.tsv":
            "8df7fd0989d8f42f2e8475454ed11101077ffff2dedbcc1035b8f9291fdda38f",
        "source-package-files.tsv":
            "667eb533e8936432fa57d4cebc546eb85fb70c7efcd3a039e517da210cc3ab37",
        "recovery-package-files.tsv":
            "667eb533e8936432fa57d4cebc546eb85fb70c7efcd3a039e517da210cc3ab37",
        "recovery-summary.json":
            "6856e521986693c12faf4e0da0e5063871eaceac817fb46b925b9c4d64eabe36",
    },
}


REQUIRED_PROJECT_FINCH_ROLES = frozenset(
    {
        "source_truth_worker",
        "source_truth_aggregate",
        "source_truth_adjudicator",
        "source_truth_worker_test",
        "source_truth_aggregate_test",
        "source_truth_adjudicator_test",
        "source_truth_containment_driver",
        "source_truth_containment_driver_test",
        "source_truth_production_wrapper",
    }
)


CACHE_MANIFEST_FIELDS = (
    "canonical_genbank_assembly_accession",
    "fresh_biosample",
    "historical_batch",
    "historical_sequence_eligibility",
    "historical_exclusion_reasons",
)

CACHE_VERIFICATION_FIELDS = (
    "batch",
    "canonical_genbank_assembly_accession",
    "package_file_count",
    "accession_package_files_pass",
    "batch_common_provenance_pass",
    "cache_content_verification",
)

HISTORICAL_AUDIT_MANIFEST_FIELDS = (
    "batch",
    "candidate_sequence_audit_sha256",
)

REFERENCE_FIELDS = (
    "role",
    "project_finch_commit",
    "path",
    "sha256",
)

DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "source_evidence_sha256",
    "sequence_set_sha256",
    "duplicate_relation_count",
    "containment_relation_count",
    "source_truth_status",
    "source_truth_reason",
)

RELATION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "relation_type",
    "left_component",
    "right_component",
    "inner_component",
    "outer_component",
    "inner_topology",
    "outer_topology",
    "relation",
    "outer_origin_crossing",
)

INPUT_EVIDENCE_FIELDS = (
    "source_group",
    "batch",
    "file_role",
    "file_name",
    "size_bytes",
    "sha256",
)

CONTENT_MANIFEST_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
)

TERMINAL_STATUSES = frozenset(
    {
        "SUITABLE",
        "EXCLUDE_SOURCE_TRUTH",
        "REVIEW_UNRESOLVED",
    }
)

CANONICAL_GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class ExecutionError(RuntimeError):
    """Raised when Stage 1 production execution fails closed."""


@dataclass(frozen=True)
class BatchSpec:
    source_group: str
    batch: str
    candidate_audit: Path
    component_audit: Path
    package_manifest: Path
    candidates: tuple[CandidateAudit, ...]


@dataclass(frozen=True)
class PopulationBundle:
    historical_candidates: tuple[CandidateAudit, ...]
    fresh_candidates: tuple[CandidateAudit, ...]
    batches: tuple[BatchSpec, ...]
    historical_membership_sha256: str
    fresh_membership_sha256: str
    combined_membership_sha256: str
    input_evidence_rows: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class PopulationContract:
    historical_audit_rows: int
    cache_reuse: int
    historical_eligible: int
    historical_ineligible: int
    cache_verification_rows: int
    fresh_audit_rows: int
    fresh_eligible: int
    fresh_ineligible: int
    total: int
    ordinary_fresh_batches: tuple[str, ...]
    recovery_fresh_batches: tuple[str, ...]


PRODUCTION_CONTRACT = PopulationContract(
    historical_audit_rows=EXPECTED_HISTORICAL_AUDIT_ROWS,
    cache_reuse=EXPECTED_CACHE_REUSE,
    historical_eligible=EXPECTED_HISTORICAL_ELIGIBLE,
    historical_ineligible=EXPECTED_HISTORICAL_INELIGIBLE,
    cache_verification_rows=EXPECTED_CACHE_VERIFICATION_ROWS,
    fresh_audit_rows=EXPECTED_FRESH_AUDIT_ROWS,
    fresh_eligible=EXPECTED_FRESH_ELIGIBLE,
    fresh_ineligible=EXPECTED_FRESH_INELIGIBLE,
    total=EXPECTED_STAGE1_TOTAL,
    ordinary_fresh_batches=ORDINARY_FRESH_BATCHES,
    recovery_fresh_batches=RECOVERY_FRESH_BATCHES,
)


def sha256_file(
    path: Path,
    block_size: int = 8 * 1024 * 1024,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                block_size
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise ExecutionError(
            f"{label} is not a regular file: {path}"
        )

    observed = sha256_file(
        path
    )

    if observed != expected:
        raise ExecutionError(
            f"{label} SHA256 mismatch: "
            f"expected={expected} observed={observed}"
        )

    return observed


def git_bytes(
    repo: Path,
    *args: str,
) -> bytes:
    try:
        completed = subprocess.run(
            (
                "git",
                "-C",
                str(repo),
                *args,
            ),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(
            "utf-8",
            errors="replace",
        ).strip()

        raise ExecutionError(
            "Git command failed: "
            + stderr
        ) from exc

    return completed.stdout


def git_text(
    repo: Path,
    *args: str,
) -> str:
    return git_bytes(
        repo,
        *args,
    ).decode(
        "utf-8"
    ).strip()


def read_tsv(
    path: Path,
) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    if not path.is_file():
        raise ExecutionError(
            f"TSV missing: {path}"
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
            raise ExecutionError(
                f"TSV header missing: {path}"
            )

        fields = tuple(
            reader.fieldnames
        )

        rows = [
            dict(row)
            for row in reader
        ]

    return fields, rows


def require_exact_fields(
    observed: Sequence[str],
    expected: Sequence[str],
    label: str,
) -> None:
    if tuple(observed) != tuple(expected):
        raise ExecutionError(
            f"{label} schema mismatch: "
            f"expected={tuple(expected)!r} "
            f"observed={tuple(observed)!r}"
        )


def require_accession(
    value: str,
    label: str,
) -> str:
    if not CANONICAL_GCA_RE.fullmatch(
        value
    ):
        raise ExecutionError(
            f"invalid canonical GCA in {label}: {value!r}"
        )

    return value


def require_lower_sha256(
    value: str,
    label: str,
) -> str:
    if not LOWER_SHA256_RE.fullmatch(
        value
    ):
        raise ExecutionError(
            f"invalid SHA256 in {label}: {value!r}"
        )

    return value


def load_historical_candidate_audit_manifest(
    path: Path,
    *,
    expected_sha256: str = (
        EXPECTED_HISTORICAL_CANDIDATE_AUDITS_SHA256
    ),
    expected_count: int = 111,
) -> tuple[
    dict[str, str],
    dict[str, str],
]:
    """Load the frozen historical candidate-audit hash handoff."""

    require_sha256(
        path,
        expected_sha256,
        "historical candidate-audit hash manifest",
    )

    fields, rows = read_tsv(
        path
    )

    require_exact_fields(
        fields,
        HISTORICAL_AUDIT_MANIFEST_FIELDS,
        "historical candidate-audit hash manifest",
    )

    if len(rows) != expected_count:
        raise ExecutionError(
            "historical candidate-audit hash manifest row count mismatch: "
            f"expected={expected_count} observed={len(rows)}"
        )

    expected_batches = {
        f"batch-{index:03d}"
        for index in range(
            1,
            expected_count + 1,
        )
    }

    by_batch: dict[
        str,
        str,
    ] = {}

    for row in rows:
        batch = row[
            "batch"
        ]

        if batch in by_batch:
            raise ExecutionError(
                "duplicate batch in historical candidate-audit "
                f"hash manifest: {batch}"
            )

        by_batch[
            batch
        ] = require_lower_sha256(
            row[
                "candidate_sequence_audit_sha256"
            ],
            (
                "historical candidate-audit hash "
                f"for {batch}"
            ),
        )

    if set(by_batch) != expected_batches:
        raise ExecutionError(
            "historical candidate-audit hash manifest batch set mismatch"
        )

    return (
        by_batch,
        evidence_row(
            "handoff",
            "",
            "historical_candidate_audit_hash_manifest",
            path,
        ),
    )


def verify_batch_summary_evidence(
    *,
    source_group: str,
    batch: str,
    batch_dir: Path,
    candidate_path: Path,
    component_path: Path,
    package_path: Path,
) -> tuple[
    dict[str, object],
    dict[str, str],
]:
    """Verify candidate/component/package files against a batch summary."""

    summary_path = (
        batch_dir
        / "batch-summary.json"
    )

    if (
        not summary_path.is_file()
        or summary_path.is_symlink()
    ):
        raise ExecutionError(
            f"{source_group} {batch} batch summary missing: "
            f"{summary_path}"
        )

    try:
        payload = json.loads(
            summary_path.read_text(
                encoding="utf-8",
            )
        )
    except json.JSONDecodeError as exc:
        raise ExecutionError(
            f"{source_group} {batch} batch summary is invalid JSON"
        ) from exc

    bindings = (
        (
            "candidate_sequence_audit_sha256",
            candidate_path,
            "candidate audit",
        ),
        (
            "component_sequence_audit_sha256",
            component_path,
            "component audit",
        ),
        (
            "package_files_sha256",
            package_path,
            "package manifest",
        ),
    )

    for key, evidence_path, label in bindings:
        expected = require_lower_sha256(
            str(
                payload.get(
                    key,
                    "",
                )
            ),
            f"{source_group} {batch} {key}",
        )

        require_sha256(
            evidence_path,
            expected,
            f"{source_group} {batch} {label}",
        )

    return (
        payload,
        evidence_row(
            source_group,
            batch,
            "batch_summary",
            summary_path,
        ),
    )


def write_json_atomic(
    path: Path,
    payload: object,
) -> str:
    text = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    if temporary.exists():
        raise ExecutionError(
            f"temporary output already exists: {temporary}"
        )

    temporary.write_text(
        text,
        encoding="utf-8",
    )

    os.replace(
        temporary,
        path,
    )

    return sha256_file(
        path
    )


def write_tsv_atomic(
    path: Path,
    fields: Sequence[str],
    rows: Iterable[Mapping[str, object]],
) -> str:
    temporary = path.with_name(
        path.name + ".tmp"
    )

    if temporary.exists():
        raise ExecutionError(
            f"temporary output already exists: {temporary}"
        )

    with temporary.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: row.get(
                        field,
                        "",
                    )
                    for field in fields
                }
            )

    os.replace(
        temporary,
        path,
    )

    return sha256_file(
        path
    )


def evidence_row(
    source_group: str,
    batch: str,
    file_role: str,
    path: Path,
) -> dict[str, str]:
    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise ExecutionError(
            f"evidence file missing or non-regular: {path}"
        )

    return {
        "source_group": source_group,
        "batch": batch,
        "file_role": file_role,
        "file_name": path.name,
        "size_bytes": str(
            path.stat().st_size
        ),
        "sha256": sha256_file(
            path
        ),
    }


def preflight_repository(
    repo: Path,
    expected_commit: str,
    frozen_files: Mapping[Path, str] = FROZEN_REPO_FILES,
) -> dict[str, str]:
    repo = repo.resolve()

    if not repo.is_dir():
        raise ExecutionError(
            f"BacSelect repository missing: {repo}"
        )

    head = git_text(
        repo,
        "rev-parse",
        "HEAD",
    )

    if head != expected_commit:
        raise ExecutionError(
            "repository HEAD differs from expected execution commit: "
            f"expected={expected_commit} observed={head}"
        )

    origin_main = git_text(
        repo,
        "rev-parse",
        "origin/main",
    )

    if origin_main != expected_commit:
        raise ExecutionError(
            "origin/main differs from expected execution commit: "
            f"expected={expected_commit} observed={origin_main}"
        )

    status = git_text(
        repo,
        "status",
        "--porcelain",
    )

    if status:
        raise ExecutionError(
            "BacSelect repository working tree is not clean"
        )

    observed: dict[str, str] = {}

    for relative, expected_sha in sorted(
        frozen_files.items(),
        key=lambda item: str(
            item[0]
        ),
    ):
        observed[
            str(relative)
        ] = require_sha256(
            repo / relative,
            expected_sha,
            str(relative),
        )

    return observed


def verify_project_finch_references(
    bacselect_repo: Path,
    project_finch_repo: Path,
    *,
    required_roles: frozenset[str] = REQUIRED_PROJECT_FINCH_ROLES,
) -> tuple[dict[str, str], ...]:
    project_finch_repo = (
        project_finch_repo.resolve()
    )

    if not project_finch_repo.is_dir():
        raise ExecutionError(
            "Project Finch repository missing: "
            f"{project_finch_repo}"
        )

    inherited_path = (
        bacselect_repo
        / INHERITED_REFERENCES_RELATIVE
    )

    transitive_path = (
        bacselect_repo
        / TRANSITIVE_REFERENCES_RELATIVE
    )

    require_sha256(
        inherited_path,
        EXPECTED_INHERITED_REFERENCES_SHA256,
        "inherited implementation-reference table",
    )

    require_sha256(
        transitive_path,
        EXPECTED_TRANSITIVE_REFERENCES_SHA256,
        "transitive implementation-reference table",
    )

    all_rows: list[
        dict[str, str]
    ] = []

    for path in (
        inherited_path,
        transitive_path,
    ):
        fields, rows = read_tsv(
            path
        )

        require_exact_fields(
            fields,
            REFERENCE_FIELDS,
            str(path),
        )

        all_rows.extend(
            rows
        )

    by_role: dict[
        str,
        dict[str, str],
    ] = {}

    for row in all_rows:
        role = row["role"]

        if role in by_role:
            raise ExecutionError(
                f"duplicate implementation-reference role: {role}"
            )

        by_role[role] = row

    missing = (
        required_roles
        - set(by_role)
    )

    if missing:
        raise ExecutionError(
            "missing required Project Finch roles: "
            f"{sorted(missing)!r}"
        )

    verified: list[
        dict[str, str]
    ] = []

    for role in sorted(
        required_roles
    ):
        row = by_role[
            role
        ]

        commit = row[
            "project_finch_commit"
        ]

        path = row[
            "path"
        ]

        expected_sha = require_lower_sha256(
            row["sha256"],
            f"{role} reference",
        )

        if (
            not re.fullmatch(
                r"[0-9a-f]{40}",
                commit,
            )
        ):
            raise ExecutionError(
                f"invalid Project Finch commit for {role}: {commit}"
            )

        path_object = Path(
            path
        )

        if (
            path_object.is_absolute()
            or ".." in path_object.parts
        ):
            raise ExecutionError(
                f"unsafe Project Finch path for {role}: {path}"
            )

        content = git_bytes(
            project_finch_repo,
            "show",
            f"{commit}:{path}",
        )

        observed_sha = hashlib.sha256(
            content
        ).hexdigest()

        if observed_sha != expected_sha:
            raise ExecutionError(
                f"Project Finch reference mismatch for {role}: "
                f"expected={expected_sha} observed={observed_sha}"
            )

        verified.append(
            {
                "role": role,
                "project_finch_commit": commit,
                "path": path,
                "sha256": expected_sha,
            }
        )

    return tuple(
        verified
    )


def load_final_acquisition_evidence(
    repo: Path,
) -> dict[str, object]:
    path = (
        repo
        / FINAL_ACQUISITION_EVIDENCE_RELATIVE
    )

    require_sha256(
        path,
        EXPECTED_FINAL_ACQUISITION_EVIDENCE_SHA256,
        "final acquisition evidence",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    required = {
        "status":
            "FINAL_ACQUISITION_MANIFESTS_COMPLETE",
        "cache_reuse":
            EXPECTED_CACHE_REUSE,
        "fresh_downloads":
            15_326,
        "fresh_batches":
            31,
        "genome_sequence_downloaded":
            False,
        "identity_bearing_manifests_committed":
            False,
        "network_access_during_manifest_build":
            False,
        "selector_identity_or_distance_consumed":
            False,
        "baseline_membership_used_for_acquisition_partition":
            False,
    }

    for key, expected in required.items():
        observed = payload.get(
            key
        )

        if observed != expected:
            raise ExecutionError(
                "final acquisition evidence mismatch for "
                f"{key}: expected={expected!r} observed={observed!r}"
            )

    eligibility = payload.get(
        "cached_historical_sequence_eligibility_counts"
    )

    if eligibility != {
        "eligible": EXPECTED_HISTORICAL_ELIGIBLE,
        "ineligible": EXPECTED_HISTORICAL_INELIGIBLE,
    }:
        raise ExecutionError(
            "historical eligibility counts differ from frozen evidence"
        )

    return payload


def load_cache_handoff(
    *,
    cache_accessions_path: Path,
    cache_manifest_path: Path,
    cache_verification_path: Path,
    acquisition_evidence: Mapping[str, object],
    contract: PopulationContract,
) -> tuple[
    dict[str, str],
    dict[str, str],
    tuple[dict[str, str], ...],
]:
    require_sha256(
        cache_accessions_path,
        str(
            acquisition_evidence[
                "cache_reuse_accessions_sha256"
            ]
        ),
        "cache-reuse accession list",
    )

    require_sha256(
        cache_manifest_path,
        str(
            acquisition_evidence[
                "cache_reuse_manifest_sha256"
            ]
        ),
        "cache-reuse manifest",
    )

    require_sha256(
        cache_verification_path,
        str(
            acquisition_evidence[
                "cache_verification_sha256"
            ]
        ),
        "historical cache verification",
    )

    accessions = tuple(
        line.strip()
        for line in cache_accessions_path.read_text(
            encoding="utf-8",
        ).splitlines()
        if line.strip()
    )

    if len(accessions) != contract.cache_reuse:
        raise ExecutionError(
            "cache-reuse accession count mismatch"
        )

    if len(set(accessions)) != len(
        accessions
    ):
        raise ExecutionError(
            "duplicate accession in cache-reuse accession list"
        )

    for accession in accessions:
        require_accession(
            accession,
            "cache-reuse accession list",
        )

    manifest_fields, manifest_rows = (
        read_tsv(
            cache_manifest_path
        )
    )

    require_exact_fields(
        manifest_fields,
        CACHE_MANIFEST_FIELDS,
        "cache-reuse manifest",
    )

    if (
        len(manifest_rows)
        != contract.cache_reuse
    ):
        raise ExecutionError(
            "cache-reuse manifest row count mismatch"
        )

    manifest_by_accession: dict[
        str,
        dict[str, str],
    ] = {}

    eligibility_counts = Counter()

    for row in manifest_rows:
        accession = require_accession(
            row[
                "canonical_genbank_assembly_accession"
            ],
            "cache-reuse manifest",
        )

        if accession in manifest_by_accession:
            raise ExecutionError(
                "duplicate accession in cache-reuse manifest"
            )

        state = row[
            "historical_sequence_eligibility"
        ]

        if state not in {
            "eligible",
            "ineligible",
        }:
            raise ExecutionError(
                "unexpected historical eligibility state: "
                f"{state!r}"
            )

        eligibility_counts[
            state
        ] += 1

        manifest_by_accession[
            accession
        ] = row

    if set(manifest_by_accession) != set(
        accessions
    ):
        raise ExecutionError(
            "cache-reuse accession list and manifest differ"
        )

    if eligibility_counts != Counter(
        {
            "eligible":
                contract.historical_eligible,
            "ineligible":
                contract.historical_ineligible,
        }
    ):
        raise ExecutionError(
            "cache-reuse eligibility counts differ from contract"
        )

    verification_fields, verification_rows = (
        read_tsv(
            cache_verification_path
        )
    )

    require_exact_fields(
        verification_fields,
        CACHE_VERIFICATION_FIELDS,
        "historical cache verification",
    )

    if (
        len(verification_rows)
        != contract.cache_verification_rows
    ):
        raise ExecutionError(
            "cache verification row count mismatch"
        )

    verification_by_accession: dict[
        str,
        dict[str, str],
    ] = {}

    for row in verification_rows:
        accession = require_accession(
            row[
                "canonical_genbank_assembly_accession"
            ],
            "historical cache verification",
        )

        if accession in verification_by_accession:
            raise ExecutionError(
                "duplicate accession in cache verification"
            )

        if (
            row[
                "accession_package_files_pass"
            ]
            != "1"
            or row[
                "batch_common_provenance_pass"
            ]
            != "1"
            or row[
                "cache_content_verification"
            ]
            != "pass"
        ):
            raise ExecutionError(
                "historical cache verification contains a non-pass row"
            )

        verification_by_accession[
            accession
        ] = row

    eligible_batches: dict[
        str,
        str,
    ] = {}

    ineligible_batches: dict[
        str,
        str,
    ] = {}

    for accession, row in (
        manifest_by_accession.items()
    ):
        verification = (
            verification_by_accession.get(
                accession
            )
        )

        if verification is None:
            raise ExecutionError(
                "cache-reuse accession absent from cache verification: "
                f"{accession}"
            )

        expected_batch = row[
            "historical_batch"
        ]

        if (
            verification[
                "batch"
            ]
            != expected_batch
        ):
            raise ExecutionError(
                "historical batch differs between cache manifest "
                f"and verification for {accession}"
            )

        if (
            row[
                "historical_sequence_eligibility"
            ]
            == "eligible"
        ):
            eligible_batches[
                accession
            ] = expected_batch
        else:
            ineligible_batches[
                accession
            ] = expected_batch

    evidence_rows = (
        evidence_row(
            "handoff",
            "",
            "cache_reuse_accessions",
            cache_accessions_path,
        ),
        evidence_row(
            "handoff",
            "",
            "cache_reuse_manifest",
            cache_manifest_path,
        ),
        evidence_row(
            "handoff",
            "",
            "historical_cache_verification",
            cache_verification_path,
        ),
    )

    return (
        eligible_batches,
        ineligible_batches,
        evidence_rows,
    )


def discover_historical_batches(
    historical_root: Path,
    *,
    expected_count: int,
) -> dict[str, tuple[Path, Path, Path]]:
    historical_root = (
        historical_root.resolve()
    )

    candidate_paths = sorted(
        historical_root.rglob(
            "candidate-sequence-audit.tsv"
        )
    )

    if len(candidate_paths) != expected_count:
        raise ExecutionError(
            "historical candidate-audit file count mismatch: "
            f"expected={expected_count} "
            f"observed={len(candidate_paths)}"
        )

    result: dict[
        str,
        tuple[Path, Path, Path],
    ] = {}

    for candidate_path in candidate_paths:
        batch_dir = (
            candidate_path.parent
        )

        batch = batch_dir.name

        if batch in result:
            raise ExecutionError(
                f"duplicate historical batch name: {batch}"
            )

        component_path = (
            batch_dir
            / "component-sequence-audit.tsv"
        )

        package_path = (
            batch_dir
            / "package-files.tsv"
        )

        for label, path in (
            (
                "historical component audit",
                component_path,
            ),
            (
                "historical package manifest",
                package_path,
            ),
        ):
            if (
                not path.is_file()
                or path.is_symlink()
            ):
                raise ExecutionError(
                    f"{label} missing for {batch}: {path}"
                )

        result[
            batch
        ] = (
            candidate_path,
            component_path,
            package_path,
        )

    if len(result) != expected_count:
        raise ExecutionError(
            "historical batch count mismatch"
        )

    return result


def candidate_audit_membership(
    batch_files: Mapping[
        str,
        tuple[Path, Path, Path],
    ],
) -> dict[str, tuple[str, str]]:
    result: dict[
        str,
        tuple[str, str],
    ] = {}

    for batch in sorted(
        batch_files
    ):
        candidate_path = (
            batch_files[
                batch
            ][0]
        )

        fields, rows = read_tsv(
            candidate_path
        )

        required = {
            "canonical_genbank_assembly_accession",
            "sequence_eligibility",
        }

        missing = (
            required
            - set(fields)
        )

        if missing:
            raise ExecutionError(
                f"{candidate_path}: missing candidate fields "
                f"{sorted(missing)!r}"
            )

        for row in rows:
            accession = require_accession(
                row[
                    "canonical_genbank_assembly_accession"
                ],
                "historical candidate audit",
            )

            if accession in result:
                raise ExecutionError(
                    "duplicate accession across historical audits"
                )

            result[
                accession
            ] = (
                batch,
                row[
                    "sequence_eligibility"
                ],
            )

    return result


def build_historical_population(
    *,
    historical_root: Path,
    eligible_batches: Mapping[str, str],
    ineligible_batches: Mapping[str, str],
    candidate_audit_sha256_by_batch: Mapping[str, str],
    contract: PopulationContract,
    expected_batch_count: int = 111,
) -> tuple[
    tuple[CandidateAudit, ...],
    tuple[BatchSpec, ...],
    tuple[dict[str, str], ...],
]:
    batch_files = discover_historical_batches(
        historical_root,
        expected_count=expected_batch_count,
    )

    if set(batch_files) != set(
        candidate_audit_sha256_by_batch
    ):
        raise ExecutionError(
            "historical candidate-audit frozen batch set mismatch"
        )

    historical_summary_evidence: dict[
        str,
        dict[str, str],
    ] = {}

    for batch in sorted(
        batch_files
    ):
        (
            candidate_path,
            component_path,
            package_path,
        ) = batch_files[
            batch
        ]

        frozen_candidate_sha = (
            candidate_audit_sha256_by_batch[
                batch
            ]
        )

        require_sha256(
            candidate_path,
            frozen_candidate_sha,
            f"historical {batch} candidate audit",
        )

        (
            summary,
            summary_evidence,
        ) = verify_batch_summary_evidence(
            source_group="historical",
            batch=batch,
            batch_dir=candidate_path.parent,
            candidate_path=candidate_path,
            component_path=component_path,
            package_path=package_path,
        )

        if (
            summary[
                "candidate_sequence_audit_sha256"
            ]
            != frozen_candidate_sha
        ):
            raise ExecutionError(
                f"historical {batch} batch-summary candidate hash "
                "differs from frozen aggregate manifest"
            )

        historical_summary_evidence[
            batch
        ] = summary_evidence

    audit_membership = (
        candidate_audit_membership(
            batch_files
        )
    )

    cache_accessions = (
        set(
            eligible_batches
        )
        | set(
            ineligible_batches
        )
    )

    if not cache_accessions <= set(
        audit_membership
    ):
        missing = sorted(
            cache_accessions
            - set(
                audit_membership
            )
        )

        raise ExecutionError(
            "cache-reuse accession absent from historical candidate audits: "
            f"{missing[:5]!r}"
        )

    for accession, expected_batch in (
        eligible_batches.items()
    ):
        observed_batch, state = (
            audit_membership[
                accession
            ]
        )

        if (
            observed_batch != expected_batch
            or state != "eligible"
        ):
            raise ExecutionError(
                "historical eligible handoff disagrees with candidate audit "
                f"for {accession}"
            )

    for accession, expected_batch in (
        ineligible_batches.items()
    ):
        observed_batch, state = (
            audit_membership[
                accession
            ]
        )

        if (
            observed_batch != expected_batch
            or state != "ineligible"
        ):
            raise ExecutionError(
                "historical ineligible handoff disagrees with candidate audit "
                f"for {accession}"
            )

    population = load_candidate_population(
        [
            batch_files[
                batch
            ][0]
            for batch in sorted(
                batch_files
            )
        ],
        expected_total=contract.historical_audit_rows,
    )

    eligible_map = {
        candidate.accession:
            candidate
        for candidate in (
            population.candidates
        )
    }

    selected: list[
        CandidateAudit
    ] = []

    for accession in sorted(
        eligible_batches
    ):
        candidate = eligible_map.get(
            accession
        )

        if candidate is None:
            raise ExecutionError(
                "historical Stage 1 accession is not sequence eligible: "
                f"{accession}"
            )

        selected.append(
            candidate
        )

    if (
        len(selected)
        != contract.historical_eligible
    ):
        raise ExecutionError(
            "historical Stage 1 eligible count mismatch"
        )

    selected_by_batch: dict[
        str,
        list[CandidateAudit],
    ] = defaultdict(list)

    for candidate in selected:
        batch = (
            candidate.audit_path.parent.name
        )

        expected_batch = (
            eligible_batches[
                candidate.accession
            ]
        )

        if batch != expected_batch:
            raise ExecutionError(
                "historical selected candidate batch mismatch"
            )

        selected_by_batch[
            batch
        ].append(
            candidate
        )

    specs: list[
        BatchSpec
    ] = []

    evidence_rows: list[
        dict[str, str]
    ] = []

    for batch in sorted(
        batch_files
    ):
        candidate_path, component_path, package_path = (
            batch_files[
                batch
            ]
        )

        evidence_rows.extend(
            (
                evidence_row(
                    "historical",
                    batch,
                    "candidate_audit",
                    candidate_path,
                ),
                evidence_row(
                    "historical",
                    batch,
                    "component_audit",
                    component_path,
                ),
                evidence_row(
                    "historical",
                    batch,
                    "package_manifest",
                    package_path,
                ),
                historical_summary_evidence[
                    batch
                ],
            )
        )

        candidates = tuple(
            sorted(
                selected_by_batch.get(
                    batch,
                    []
                ),
                key=lambda item:
                    item.accession,
            )
        )

        if candidates:
            specs.append(
                BatchSpec(
                    source_group="historical",
                    batch=batch,
                    candidate_audit=candidate_path,
                    component_audit=component_path,
                    package_manifest=package_path,
                    candidates=candidates,
                )
            )

    return (
        tuple(selected),
        tuple(specs),
        tuple(evidence_rows),
    )


def verify_fresh_recovery_summary(
    recovery_root: Path,
    *,
    expected_sha256: str | None,
    contract: PopulationContract,
) -> tuple[
    dict[str, object] | None,
    dict[str, str] | None,
]:
    if expected_sha256 is None:
        return (
            None,
            None,
        )

    path = (
        recovery_root
        / "fresh-sequence-validation-recovery-summary.json"
    )

    require_sha256(
        path,
        expected_sha256,
        "fresh sequence-validation recovery summary",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    checks = {
        "candidate_records":
            contract.fresh_audit_rows,
        "component_records":
            35_227,
        "package_content_verified":
            True,
        "selector_outcome_generated":
            False,
    }

    for key, expected in checks.items():
        if payload.get(
            key
        ) != expected:
            raise ExecutionError(
                "fresh recovery summary mismatch for "
                f"{key}"
            )

    if payload.get(
        "sequence_eligibility_counts"
    ) != {
        "eligible":
            contract.fresh_eligible,
        "ineligible":
            contract.fresh_ineligible,
    }:
        raise ExecutionError(
            "fresh recovery summary eligibility counts mismatch"
        )

    return (
        payload,
        evidence_row(
            "handoff",
            "",
            "fresh_recovery_summary",
            path,
        ),
    )


def build_fresh_population(
    *,
    fresh_root: Path,
    recovery_root: Path,
    contract: PopulationContract,
    recovery_expected_sha256: Mapping[
        str,
        Mapping[str, str],
    ] | None,
    recovery_summary_sha256: str | None,
) -> tuple[
    tuple[CandidateAudit, ...],
    tuple[BatchSpec, ...],
    tuple[dict[str, str], ...],
]:
    fresh_root = fresh_root.resolve()
    recovery_root = (
        recovery_root.resolve()
    )

    evidence_rows: list[
        dict[str, str]
    ] = []

    _, summary_evidence = (
        verify_fresh_recovery_summary(
            recovery_root,
            expected_sha256=recovery_summary_sha256,
            contract=contract,
        )
    )

    if summary_evidence is not None:
        evidence_rows.append(
            summary_evidence
        )

    specs_by_batch: dict[
        str,
        tuple[
            Path,
            Path,
            Path,
        ],
    ] = {}

    for batch in (
        contract.ordinary_fresh_batches
    ):
        batch_dir = (
            fresh_root
            / batch
        )

        candidate_path = (
            batch_dir
            / "candidate-sequence-audit.tsv"
        )

        component_path = (
            batch_dir
            / "component-sequence-audit.tsv"
        )

        package_path = (
            batch_dir
            / "package-files.tsv"
        )

        for label, path in (
            (
                "fresh candidate audit",
                candidate_path,
            ),
            (
                "fresh component audit",
                component_path,
            ),
            (
                "fresh package manifest",
                package_path,
            ),
        ):
            if (
                not path.is_file()
                or path.is_symlink()
            ):
                raise ExecutionError(
                    f"{label} missing for {batch}: {path}"
                )

        (
            _,
            summary_evidence,
        ) = verify_batch_summary_evidence(
            source_group="fresh",
            batch=batch,
            batch_dir=batch_dir,
            candidate_path=candidate_path,
            component_path=component_path,
            package_path=package_path,
        )

        specs_by_batch[
            batch
        ] = (
            candidate_path,
            component_path,
            package_path,
        )

        evidence_rows.extend(
            (
                evidence_row(
                    "fresh",
                    batch,
                    "candidate_audit",
                    candidate_path,
                ),
                evidence_row(
                    "fresh",
                    batch,
                    "component_audit",
                    component_path,
                ),
                evidence_row(
                    "fresh",
                    batch,
                    "package_manifest",
                    package_path,
                ),
                summary_evidence,
            )
        )

    for batch in (
        contract.recovery_fresh_batches
    ):
        batch_dir = (
            recovery_root
            / batch
        )

        candidate_path = (
            batch_dir
            / "candidate-sequence-audit.tsv"
        )

        component_path = (
            batch_dir
            / "component-sequence-audit.tsv"
        )

        source_package_path = (
            batch_dir
            / "source-package-files.tsv"
        )

        recovery_package_path = (
            batch_dir
            / "recovery-package-files.tsv"
        )

        recovery_summary_path = (
            batch_dir
            / "recovery-summary.json"
        )

        required_paths = {
            "candidate-sequence-audit.tsv":
                candidate_path,
            "component-sequence-audit.tsv":
                component_path,
            "source-package-files.tsv":
                source_package_path,
            "recovery-package-files.tsv":
                recovery_package_path,
            "recovery-summary.json":
                recovery_summary_path,
        }

        for name, path in (
            required_paths.items()
        ):
            if (
                not path.is_file()
                or path.is_symlink()
            ):
                raise ExecutionError(
                    f"recovery evidence missing for {batch}: {name}"
                )

        if recovery_expected_sha256 is not None:
            expected = (
                recovery_expected_sha256.get(
                    batch
                )
            )

            if expected is None:
                raise ExecutionError(
                    f"no frozen recovery hashes for {batch}"
                )

            for name, path in (
                required_paths.items()
            ):
                expected_sha = (
                    expected.get(
                        name
                    )
                )

                if expected_sha is None:
                    raise ExecutionError(
                        f"missing frozen recovery SHA for {batch}/{name}"
                    )

                require_sha256(
                    path,
                    expected_sha,
                    f"{batch}/{name}",
                )

        if (
            source_package_path.read_bytes()
            != recovery_package_path.read_bytes()
        ):
            raise ExecutionError(
                f"{batch}: source/recovery package manifests differ"
            )

        specs_by_batch[
            batch
        ] = (
            candidate_path,
            component_path,
            source_package_path,
        )

        evidence_rows.extend(
            (
                evidence_row(
                    "fresh-recovery",
                    batch,
                    "candidate_audit",
                    candidate_path,
                ),
                evidence_row(
                    "fresh-recovery",
                    batch,
                    "component_audit",
                    component_path,
                ),
                evidence_row(
                    "fresh-recovery",
                    batch,
                    "source_package_manifest",
                    source_package_path,
                ),
                evidence_row(
                    "fresh-recovery",
                    batch,
                    "recovery_package_manifest",
                    recovery_package_path,
                ),
                evidence_row(
                    "fresh-recovery",
                    batch,
                    "recovery_summary",
                    recovery_summary_path,
                ),
            )
        )

    expected_batches = (
        set(
            contract.ordinary_fresh_batches
        )
        | set(
            contract.recovery_fresh_batches
        )
    )

    if set(
        specs_by_batch
    ) != expected_batches:
        raise ExecutionError(
            "fresh accepted batch set mismatch"
        )

    population = load_candidate_population(
        [
            specs_by_batch[
                batch
            ][0]
            for batch in sorted(
                specs_by_batch
            )
        ],
        expected_total=contract.fresh_audit_rows,
        expected_eligible=contract.fresh_eligible,
        expected_ineligible=contract.fresh_ineligible,
    )

    by_batch: dict[
        str,
        list[CandidateAudit],
    ] = defaultdict(list)

    for candidate in (
        population.candidates
    ):
        batch = (
            candidate.audit_path.parent.name
        )

        if batch not in specs_by_batch:
            raise ExecutionError(
                "fresh candidate resolved to unexpected batch"
            )

        by_batch[
            batch
        ].append(
            candidate
        )

    specs: list[
        BatchSpec
    ] = []

    for batch in sorted(
        specs_by_batch
    ):
        candidate_path, component_path, package_path = (
            specs_by_batch[
                batch
            ]
        )

        candidates = tuple(
            sorted(
                by_batch.get(
                    batch,
                    []
                ),
                key=lambda item:
                    item.accession,
            )
        )

        if candidates:
            specs.append(
                BatchSpec(
                    source_group=(
                        "fresh-recovery"
                        if batch in contract.recovery_fresh_batches
                        else "fresh"
                    ),
                    batch=batch,
                    candidate_audit=candidate_path,
                    component_audit=component_path,
                    package_manifest=package_path,
                    candidates=candidates,
                )
            )

    return (
        population.candidates,
        tuple(specs),
        tuple(evidence_rows),
    )


def build_population_bundle(
    *,
    historical_candidates: Sequence[CandidateAudit],
    fresh_candidates: Sequence[CandidateAudit],
    historical_specs: Sequence[BatchSpec],
    fresh_specs: Sequence[BatchSpec],
    input_evidence_rows: Sequence[Mapping[str, str]],
    expected_total: int,
) -> PopulationBundle:
    historical_accessions = tuple(
        candidate.accession
        for candidate in historical_candidates
    )

    fresh_accessions = tuple(
        candidate.accession
        for candidate in fresh_candidates
    )

    historical_set = set(
        historical_accessions
    )

    fresh_set = set(
        fresh_accessions
    )

    overlap = (
        historical_set
        & fresh_set
    )

    if overlap:
        raise ExecutionError(
            "historical/fresh Stage 1 membership overlap: "
            f"{sorted(overlap)[:5]!r}"
        )

    combined = (
        historical_set
        | fresh_set
    )

    if len(combined) != expected_total:
        raise ExecutionError(
            "combined Stage 1 population mismatch: "
            f"expected={expected_total} observed={len(combined)}"
        )

    if (
        len(historical_accessions)
        != len(historical_set)
        or len(fresh_accessions)
        != len(fresh_set)
    ):
        raise ExecutionError(
            "duplicate accession within Stage 1 population"
        )

    ordered_evidence = tuple(
        sorted(
            (
                dict(row)
                for row in input_evidence_rows
            ),
            key=lambda row: (
                row["source_group"],
                row["batch"],
                row["file_role"],
                row["file_name"],
            ),
        )
    )

    return PopulationBundle(
        historical_candidates=tuple(
            sorted(
                historical_candidates,
                key=lambda item:
                    item.accession,
            )
        ),
        fresh_candidates=tuple(
            sorted(
                fresh_candidates,
                key=lambda item:
                    item.accession,
            )
        ),
        batches=tuple(
            sorted(
                (
                    *historical_specs,
                    *fresh_specs,
                ),
                key=lambda item: (
                    item.source_group,
                    item.batch,
                ),
            )
        ),
        historical_membership_sha256=(
            accession_membership_sha256(
                historical_accessions
            )
        ),
        fresh_membership_sha256=(
            accession_membership_sha256(
                fresh_accessions
            )
        ),
        combined_membership_sha256=(
            accession_membership_sha256(
                combined
            )
        ),
        input_evidence_rows=ordered_evidence,
    )


def verify_recovery_001_membership(
    bundle: PopulationBundle,
) -> None:
    """Require exact failed-attempt Stage 1 membership checkpoints."""

    observed = {
        "historical": (
            len(
                bundle.historical_candidates
            ),
            bundle.historical_membership_sha256,
        ),
        "fresh": (
            len(
                bundle.fresh_candidates
            ),
            bundle.fresh_membership_sha256,
        ),
        "combined": (
            (
                len(
                    bundle.historical_candidates
                )
                + len(
                    bundle.fresh_candidates
                )
            ),
            bundle.combined_membership_sha256,
        ),
    }

    expected = {
        "historical": (
            EXPECTED_HISTORICAL_ELIGIBLE,
            EXPECTED_RECOVERY_001_HISTORICAL_MEMBERSHIP_SHA256,
        ),
        "fresh": (
            EXPECTED_FRESH_ELIGIBLE,
            EXPECTED_RECOVERY_001_FRESH_MEMBERSHIP_SHA256,
        ),
        "combined": (
            EXPECTED_STAGE1_TOTAL,
            EXPECTED_RECOVERY_001_COMBINED_MEMBERSHIP_SHA256,
        ),
    }

    for group in (
        "historical",
        "fresh",
        "combined",
    ):
        (
            observed_count,
            observed_sha,
        ) = observed[group]

        (
            expected_count,
            expected_sha,
        ) = expected[group]

        if observed_count != expected_count:
            raise ExecutionError(
                f"{group} Stage 1 recovery membership count mismatch: "
                f"expected={expected_count} observed={observed_count}"
            )

        if observed_sha != expected_sha:
            raise ExecutionError(
                f"{group} Stage 1 recovery membership SHA256 mismatch"
            )


def evaluate_population(
    bundle: PopulationBundle,
) -> tuple:
    decisions = []

    for spec in (
        bundle.batches
    ):
        wanted = {
            candidate.accession
            for candidate in (
                spec.candidates
            )
        }

        component_index = (
            load_component_index(
                spec.component_audit,
                accessions=wanted,
            )
        )

        package_manifest = (
            load_package_manifest(
                spec.package_manifest
            )
        )

        for candidate in (
            spec.candidates
        ):
            components = (
                component_index.get(
                    candidate.accession
                )
            )

            if components is None:
                raise ExecutionError(
                    "candidate missing component evidence: "
                    f"{candidate.accession}"
                )

            decisions.append(
                evaluate_candidate(
                    candidate,
                    components,
                    package_manifest,
                )
            )

    decisions = sorted(
        decisions,
        key=lambda item:
            item.accession,
    )

    expected_accessions = {
        candidate.accession
        for candidate in (
            bundle.historical_candidates
            + bundle.fresh_candidates
        )
    }

    observed_accessions = [
        decision.accession
        for decision in decisions
    ]

    if len(observed_accessions) != len(
        set(observed_accessions)
    ):
        raise ExecutionError(
            "duplicate candidate decision accession"
        )

    if set(
        observed_accessions
    ) != expected_accessions:
        raise ExecutionError(
            "candidate decision membership differs from Stage 1 population"
        )

    for decision in decisions:
        if decision.status not in (
            TERMINAL_STATUSES
        ):
            raise ExecutionError(
                "unexpected source-truth terminal status: "
                f"{decision.status}"
            )

        if (
            decision.source_evidence_sha256
            is None
        ):
            raise ExecutionError(
                "decision lacks source-evidence identity"
            )

    return tuple(
        decisions
    )


def ensure_output_root_outside_repo(
    repo: Path,
    output_root: Path,
) -> Path:
    repo = repo.resolve()
    output_root = (
        output_root.resolve()
    )

    if output_root == repo:
        raise ExecutionError(
            "Stage 1 output root must be outside Git repository"
        )

    if output_root.is_relative_to(
        repo
    ):
        raise ExecutionError(
            "Stage 1 output root must be outside Git repository"
        )

    return output_root


def execute_to_scratch(
    *,
    repo: Path,
    expected_commit: str,
    output_root: Path,
    bundle: PopulationBundle,
    frozen_repo_sha256: Mapping[str, str],
    project_finch_references: Sequence[Mapping[str, str]],
    acquisition_evidence: Mapping[str, object],
) -> Path:
    output_root = (
        ensure_output_root_outside_repo(
            repo,
            output_root,
        )
    )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_dir = (
        output_root
        / expected_commit
    )

    partial_dir = (
        output_root
        / f".{expected_commit}.partial"
    )

    if final_dir.exists():
        raise ExecutionError(
            f"final Stage 1 execution directory already exists: {final_dir}"
        )

    if partial_dir.exists():
        raise ExecutionError(
            f"partial Stage 1 execution directory already exists: {partial_dir}"
        )

    partial_dir.mkdir()

    input_manifest_path = (
        partial_dir
        / "stage1-input-evidence-manifest.tsv"
    )

    input_manifest_sha = (
        write_tsv_atomic(
            input_manifest_path,
            INPUT_EVIDENCE_FIELDS,
            bundle.input_evidence_rows,
        )
    )

    preclassification_path = (
        partial_dir
        / "stage1-preclassification-provenance.json"
    )

    preclassification = {
        "schema_version": 1,
        "status":
            "PRECLASSIFICATION_FROZEN",
        "bacselect_git_commit":
            expected_commit,
        "frozen_repo_sha256":
            dict(
                sorted(
                    frozen_repo_sha256.items()
                )
            ),
        "project_finch_source_truth_references":
            list(
                project_finch_references
            ),
        "final_acquisition_evidence_sha256":
            EXPECTED_FINAL_ACQUISITION_EVIDENCE_SHA256,
        "cache_reuse_accessions_sha256":
            acquisition_evidence[
                "cache_reuse_accessions_sha256"
            ],
        "cache_reuse_manifest_sha256":
            acquisition_evidence[
                "cache_reuse_manifest_sha256"
            ],
        "cache_verification_sha256":
            acquisition_evidence[
                "cache_verification_sha256"
            ],
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "stage1_recovery": {
            "identifier":
                RECOVERY_001_IDENTIFIER,
            "clarification_relative_path":
                str(
                    RECOVERY_001_CLARIFICATION_RELATIVE
                ),
            "clarification_sha256":
                EXPECTED_RECOVERY_001_CLARIFICATION_SHA256,
            "failed_attempt_bacselect_git_commit":
                RECOVERY_001_FAILED_ATTEMPT_COMMIT,
            "recovery_implementation_bacselect_git_commit":
                RECOVERY_001_IMPLEMENTATION_COMMIT,
            "required_membership_checkpoint": {
                "historical": {
                    "count":
                        EXPECTED_HISTORICAL_ELIGIBLE,
                    "sha256":
                        EXPECTED_RECOVERY_001_HISTORICAL_MEMBERSHIP_SHA256,
                },
                "fresh": {
                    "count":
                        EXPECTED_FRESH_ELIGIBLE,
                    "sha256":
                        EXPECTED_RECOVERY_001_FRESH_MEMBERSHIP_SHA256,
                },
                "combined": {
                    "count":
                        EXPECTED_STAGE1_TOTAL,
                    "sha256":
                        EXPECTED_RECOVERY_001_COMBINED_MEMBERSHIP_SHA256,
                },
            },
        },
        "membership": {
            "historical": {
                "count":
                    len(
                        bundle.historical_candidates
                    ),
                "sha256":
                    bundle.historical_membership_sha256,
            },
            "fresh": {
                "count":
                    len(
                        bundle.fresh_candidates
                    ),
                "sha256":
                    bundle.fresh_membership_sha256,
            },
            "combined": {
                "count":
                    (
                        len(
                            bundle.historical_candidates
                        )
                        + len(
                            bundle.fresh_candidates
                        )
                    ),
                "sha256":
                    bundle.combined_membership_sha256,
            },
        },
        "classification_started":
            False,
        "stage2_repeated_biosample_generated":
            False,
        "chromosome_integrity_generated":
            False,
        "taxonomy_resolution_generated":
            False,
        "complete_universe_generated":
            False,
        "holdout_membership_generated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    preclassification_sha = (
        write_json_atomic(
            preclassification_path,
            preclassification,
        )
    )

    decisions = evaluate_population(
        bundle
    )

    candidate_rows = decision_rows(
        decisions
    )

    relation_evidence_rows = (
        relation_rows(
            decisions
        )
    )

    decision_path = (
        partial_dir
        / "stage1-source-truth-decisions.tsv"
    )

    relation_path = (
        partial_dir
        / "stage1-source-truth-relations.tsv"
    )

    decision_sha = write_tsv_atomic(
        decision_path,
        DECISION_FIELDS,
        candidate_rows,
    )

    relation_sha = write_tsv_atomic(
        relation_path,
        RELATION_FIELDS,
        relation_evidence_rows,
    )

    status_counts = Counter(
        decision.status
        for decision in decisions
    )

    if (
        set(status_counts)
        - TERMINAL_STATUSES
    ):
        raise ExecutionError(
            "non-terminal source-truth status present"
        )

    if (
        sum(
            status_counts.values()
        )
        != len(decisions)
    ):
        raise ExecutionError(
            "source-truth status accounting mismatch"
        )

    reason_counts = Counter(
        decision.reason
        for decision in decisions
    )

    execution_provenance_path = (
        partial_dir
        / "stage1-execution-provenance.json"
    )

    execution_provenance = {
        "schema_version": 1,
        "status":
            "STAGE1_SOURCE_TRUTH_COMPLETE",
        "bacselect_git_commit":
            expected_commit,
        "preclassification_provenance_sha256":
            preclassification_sha,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "candidate_decisions_sha256":
            decision_sha,
        "relation_evidence_sha256":
            relation_sha,
        "candidate_count":
            len(decisions),
        "historical_membership_sha256":
            bundle.historical_membership_sha256,
        "fresh_membership_sha256":
            bundle.fresh_membership_sha256,
        "combined_membership_sha256":
            bundle.combined_membership_sha256,
        "stage2_repeated_biosample_generated":
            False,
        "chromosome_integrity_generated":
            False,
        "taxonomy_resolution_generated":
            False,
        "complete_universe_generated":
            False,
        "holdout_membership_generated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    execution_provenance_sha = (
        write_json_atomic(
            execution_provenance_path,
            execution_provenance,
        )
    )

    summary_path = (
        partial_dir
        / "stage1-aggregate-summary.json"
    )

    summary = {
        "schema_version": 1,
        "status":
            "STAGE1_SOURCE_TRUTH_COMPLETE",
        "candidate_count":
            len(decisions),
        "historical_candidate_count":
            len(
                bundle.historical_candidates
            ),
        "fresh_candidate_count":
            len(
                bundle.fresh_candidates
            ),
        "status_counts":
            dict(
                sorted(
                    status_counts.items()
                )
            ),
        "reason_counts":
            dict(
                sorted(
                    reason_counts.items()
                )
            ),
        "candidate_decisions_sha256":
            decision_sha,
        "relation_evidence_sha256":
            relation_sha,
        "preclassification_provenance_sha256":
            preclassification_sha,
        "execution_provenance_sha256":
            execution_provenance_sha,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "stage2_repeated_biosample_generated":
            False,
        "chromosome_integrity_generated":
            False,
        "taxonomy_resolution_generated":
            False,
        "complete_universe_generated":
            False,
        "holdout_membership_generated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    summary_sha = write_json_atomic(
        summary_path,
        summary,
    )

    content_manifest_path = (
        partial_dir
        / "stage1-content-manifest.tsv"
    )

    content_rows = []

    for path in (
        input_manifest_path,
        preclassification_path,
        decision_path,
        relation_path,
        execution_provenance_path,
        summary_path,
    ):
        content_rows.append(
            {
                "path": path.name,
                "size_bytes": str(
                    path.stat().st_size
                ),
                "sha256": sha256_file(
                    path
                ),
            }
        )

    content_manifest_sha = (
        write_tsv_atomic(
            content_manifest_path,
            CONTENT_MANIFEST_FIELDS,
            sorted(
                content_rows,
                key=lambda row:
                    str(
                        row["path"]
                    ),
            ),
        )
    )

    partial_dir.rename(
        final_dir
    )

    print(
        "PASS | Stage 1 source-truth execution complete"
    )
    print(
        f"candidate_count={len(decisions)}"
    )
    print(
        "historical_membership_sha256="
        f"{bundle.historical_membership_sha256}"
    )
    print(
        "fresh_membership_sha256="
        f"{bundle.fresh_membership_sha256}"
    )
    print(
        "combined_membership_sha256="
        f"{bundle.combined_membership_sha256}"
    )
    print(
        f"candidate_decisions_sha256={decision_sha}"
    )
    print(
        f"relation_evidence_sha256={relation_sha}"
    )
    print(
        "preclassification_provenance_sha256="
        f"{preclassification_sha}"
    )
    print(
        "execution_provenance_sha256="
        f"{execution_provenance_sha}"
    )
    print(
        f"aggregate_summary_sha256={summary_sha}"
    )
    print(
        f"content_manifest_sha256={content_manifest_sha}"
    )
    print(
        f"execution_dir={final_dir}"
    )

    return final_dir


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute frozen BacSelect selector-v1 "
            "Stage 1 source-truth classification."
        )
    )

    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--expected-commit",
        required=True,
    )

    parser.add_argument(
        "--project-finch-repo",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--historical-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--cache-reuse-accessions",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--cache-reuse-manifest",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--cache-verification",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--fresh-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--recovery-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )

    return parser.parse_args(
        argv
    )


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(
        argv
    )

    repo = args.repo.resolve()

    frozen_repo_sha256 = (
        preflight_repository(
            repo,
            args.expected_commit,
        )
    )

    project_finch_references = (
        verify_project_finch_references(
            repo,
            args.project_finch_repo,
        )
    )

    acquisition_evidence = (
        load_final_acquisition_evidence(
            repo
        )
    )

    (
        historical_eligible_batches,
        historical_ineligible_batches,
        handoff_evidence_rows,
    ) = load_cache_handoff(
        cache_accessions_path=(
            args.cache_reuse_accessions
        ),
        cache_manifest_path=(
            args.cache_reuse_manifest
        ),
        cache_verification_path=(
            args.cache_verification
        ),
        acquisition_evidence=(
            acquisition_evidence
        ),
        contract=PRODUCTION_CONTRACT,
    )

    historical_candidate_audit_manifest_path = (
        args.cache_reuse_manifest.resolve().parent
        / "historical-candidate-audits-sha256.tsv"
    )

    (
        historical_candidate_audit_sha256_by_batch,
        historical_candidate_audit_manifest_evidence,
    ) = load_historical_candidate_audit_manifest(
        historical_candidate_audit_manifest_path,
        expected_sha256=(
            EXPECTED_HISTORICAL_CANDIDATE_AUDITS_SHA256
        ),
        expected_count=111,
    )

    (
        historical_candidates,
        historical_specs,
        historical_evidence_rows,
    ) = build_historical_population(
        historical_root=(
            args.historical_root
        ),
        eligible_batches=(
            historical_eligible_batches
        ),
        ineligible_batches=(
            historical_ineligible_batches
        ),
        candidate_audit_sha256_by_batch=(
            historical_candidate_audit_sha256_by_batch
        ),
        contract=PRODUCTION_CONTRACT,
    )

    (
        fresh_candidates,
        fresh_specs,
        fresh_evidence_rows,
    ) = build_fresh_population(
        fresh_root=(
            args.fresh_root
        ),
        recovery_root=(
            args.recovery_root
        ),
        contract=PRODUCTION_CONTRACT,
        recovery_expected_sha256=(
            RECOVERY_EXPECTED_SHA256
        ),
        recovery_summary_sha256=(
            EXPECTED_FRESH_RECOVERY_SUMMARY_SHA256
        ),
    )

    if (
        len(historical_candidates)
        != EXPECTED_HISTORICAL_ELIGIBLE
    ):
        raise ExecutionError(
            "historical Stage 1 count differs from frozen contract"
        )

    if (
        len(fresh_candidates)
        != EXPECTED_FRESH_ELIGIBLE
    ):
        raise ExecutionError(
            "fresh Stage 1 count differs from frozen contract"
        )

    bundle = build_population_bundle(
        historical_candidates=(
            historical_candidates
        ),
        fresh_candidates=(
            fresh_candidates
        ),
        historical_specs=(
            historical_specs
        ),
        fresh_specs=(
            fresh_specs
        ),
        input_evidence_rows=(
            *handoff_evidence_rows,
            historical_candidate_audit_manifest_evidence,
            *historical_evidence_rows,
            *fresh_evidence_rows,
        ),
        expected_total=(
            EXPECTED_STAGE1_TOTAL
        ),
    )

    verify_recovery_001_membership(
        bundle
    )

    print(
        "PASS | Stage 1 Recovery 001 membership checkpoint exact"
    )

    print(
        "PASS | Stage 1 preclassification population frozen"
    )
    print(
        "historical_candidate_count="
        f"{len(bundle.historical_candidates)}"
    )
    print(
        "fresh_candidate_count="
        f"{len(bundle.fresh_candidates)}"
    )
    print(
        "combined_candidate_count="
        f"{len(bundle.historical_candidates) + len(bundle.fresh_candidates)}"
    )
    print(
        "historical_membership_sha256="
        f"{bundle.historical_membership_sha256}"
    )
    print(
        "fresh_membership_sha256="
        f"{bundle.fresh_membership_sha256}"
    )
    print(
        "combined_membership_sha256="
        f"{bundle.combined_membership_sha256}"
    )

    execute_to_scratch(
        repo=repo,
        expected_commit=(
            args.expected_commit
        ),
        output_root=(
            args.output_root
        ),
        bundle=bundle,
        frozen_repo_sha256=(
            frozen_repo_sha256
        ),
        project_finch_references=(
            project_finch_references
        ),
        acquisition_evidence=(
            acquisition_evidence
        ),
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except (
        ExecutionError,
        ValueError,
        OSError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"ERROR | {exc}",
            file=sys.stderr,
        )

        raise SystemExit(
            1
        )
