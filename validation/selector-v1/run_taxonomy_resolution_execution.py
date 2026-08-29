#!/usr/bin/env python3
"""Run frozen BacSelect selector-v1 Stage 4 taxonomy resolution.

Importing this module performs no production evidence access.

Production execution verifies the exact frozen Stage 3 completion checkpoint,
Stage 3 decision artifact, frozen raw NCBI source report and frozen taxonomy
snapshot. It writes Stage 4 input evidence and predecision provenance before
reading candidate organism TaxIDs or constructing the taxonomy resolver.

Identity-bearing Stage 4 taxonomy decisions remain scratch-only. The wrapper
does not construct the complete eligible universe, holdout, structural
features, OPS/SR outcomes, panels, distances or selector coverage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable, Mapping, Sequence

from bacselect import source_chromosome_integrity
from bacselect.source_taxonomy import Taxonomy
from bacselect.source_taxonomy_execution import (
    STAGE4_DECISION_FIELDS,
    Stage4ExecutionError,
    build_decision_rows,
    evaluate_taxonomy_population,
    load_source_taxids,
    load_stage3_population,
)


STAGE3_COMPLETION_RELATIVE = Path(
    "validation/selector-v1/"
    "stage3-chromosome-integrity-completion-evidence.json"
)

STAGE4_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-stage4-taxonomy-resolution-execution.md"
)

STAGE4_EXECUTION_RELATIVE = Path(
    "src/bacselect/source_taxonomy_execution.py"
)

STAGE4_EXECUTION_TEST_RELATIVE = Path(
    "tests/test_source_taxonomy_execution.py"
)

TAXONOMY_PRIMITIVE_RELATIVE = Path(
    "src/bacselect/source_taxonomy.py"
)

POST_SEQUENCE_RELATIVE = Path(
    "src/bacselect/source_post_sequence_eligibility.py"
)

SOURCE_PARSER_RELATIVE = Path(
    "src/bacselect/source_eligibility.py"
)

TAXONOMY_ACQUISITION_FREEZE_RELATIVE = Path(
    "validation/selector-v1/"
    "taxonomy-snapshot-acquisition-freeze.json"
)

STAGE4_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_taxonomy_resolution_execution.py"
)

STAGE4_WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_taxonomy_resolution_execution.py"
)

EXPECTED_STAGE3_COMPLETION_SHA256 = (
    "c5aff0e1e5cca6202688198a49069b1"
    "ae3e7b35d19f4939538d7c3f01ff562d2"
)

EXPECTED_STAGE3_EXECUTION_COMMIT = (
    "dfe72a4c0c6ddef3af999c10b2db66d05b0eca88"
)

EXPECTED_STAGE3_DECISIONS_SHA256 = (
    "13d66c0febb809d30862730eff0b419c"
    "3568fc9cdd113970ac441b0fce748f04"
)

EXPECTED_STAGE4_METHOD_SHA256 = (
    "6e8629f40fdc6752bf210694c64f0fc"
    "246a97acd9e797f59cd95d1c1fee963e1"
)

EXPECTED_STAGE4_EXECUTION_SHA256 = (
    "426e42c87a58f454fbc8107b27562342"
    "681bea06cc38428bd884d8372b1e43a1"
)

EXPECTED_STAGE4_EXECUTION_TEST_SHA256 = (
    "2e9b836e4b775c400b1f9137396d8096"
    "a4cb5c11b7c2fde073ee1f249068071d"
)

EXPECTED_TAXONOMY_PRIMITIVE_SHA256 = (
    "9c8c4149c5db2a757e8c201a6523bdb"
    "113511b5f72a4dd2893572dd8c7928e4d"
)

EXPECTED_POST_SEQUENCE_SHA256 = (
    "62fa1e2f7d806f94b5f5eca73fb7687"
    "45d3913a4b218a4d354562033cd300fe8"
)

EXPECTED_SOURCE_PARSER_SHA256 = (
    "6e57dd950f972a9883e8fcbc78a18c69"
    "4a5fabda58b03835f268eef681a03cc2"
)

EXPECTED_TAXONOMY_ACQUISITION_FREEZE_SHA256 = (
    "ef7c7f73d5ad4dcc20f74f761e43a3e"
    "3c05e77d264b93d0a01d606a8e3866ac4"
)

EXPECTED_RAW_SOURCE_SHA256 = (
    "b1b016891ae4e976d03606dfb2f35f74"
    "b03d21cf3ec82832f77f4d113bd622d5"
)

EXPECTED_NODES_SHA256 = (
    "1d096a81dbd87eccc6d412b28c37ca1e"
    "ee292fa80e22ae4347c91dcbc7f03153"
)

EXPECTED_MERGED_SHA256 = (
    "3dcd79305dbebc33f50292e7877b7094"
    "f99ba920041c7bce199c3b45b4c9e725"
)

EXPECTED_DELNODES_SHA256 = (
    "9dab07574818ae7696d4a18d5512295e"
    "3054fb8260c167a3c894366866f10221"
)

EXPECTED_TAXONOMY_ARCHIVE_SHA256 = (
    "005d1b674bb12719c003652c867486f8"
    "3a5c860b4beb1016adf17f3c56c2d844"
)

EXPECTED_TAXONOMY_SNAPSHOT_RECORD_SHA256 = (
    "4c89bc24bd06925b24f94b0313cf9ec9"
    "87adc97b88dd72be19c037db6232b05b"
)

EXPECTED_SOURCE_SNAPSHOT_ID = (
    "snapshot-20260825T132821Z"
)

EXPECTED_TAXONOMY_SNAPSHOT_ID = (
    "taxonomy-20260826T070308Z"
)

PROJECT_FINCH_TAXONOMY_COMMIT = (
    "44f9e231a754962a6091105c031d330d686103aa"
)

PROJECT_FINCH_TAXONOMY_PATH = (
    "scripts/experiment-0/build_species_resolution.py"
)

PROJECT_FINCH_TAXONOMY_SHA256 = (
    "fcc3321975eef2e250c166215680fdd60"
    "aa90d1eef20bd68543fac759fab8ee8"
)

EXPECTED_STAGE3_TOTAL = 68278
EXPECTED_STAGE4_TOTAL = 68175
EXPECTED_RAW_SOURCE_RECORDS = 70850

EXPECTED_STAGE3_STATUS_COUNTS = {
    source_chromosome_integrity.EXCLUDE: 33,
    source_chromosome_integrity.PASS: 68175,
    source_chromosome_integrity.UNRESOLVED: 70,
}

EXPECTED_STAGE3_REASON_COUNTS = {
    "HISTORICAL_FRAGMENTED_CHROMOSOME_SET": 33,
    "HISTORICAL_RETAIN_CONFIRMED_MULTIPARTITE": 35,
    "HISTORICAL_UNRESOLVED": 12,
    "NOT_HISTORICAL_PROJECT_FINCH_PACKAGE": 58,
    "NO_CHROMOSOME_INTEGRITY_TRIGGER": 68140,
}

EXPECTED_STAGE3_LATER_STAGE = {
    "chromosome_integrity_generated": True,
    "complete_universe_generated": False,
    "holdout_membership_generated": False,
    "selector_outcomes_calculated": False,
    "structural_features_calculated": False,
    "taxonomy_resolution_generated": False,
}

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

LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

LOWER_GIT_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

FROZEN_REPO_FILES = {
    STAGE3_COMPLETION_RELATIVE:
        EXPECTED_STAGE3_COMPLETION_SHA256,
    STAGE4_METHOD_RELATIVE:
        EXPECTED_STAGE4_METHOD_SHA256,
    STAGE4_EXECUTION_RELATIVE:
        EXPECTED_STAGE4_EXECUTION_SHA256,
    STAGE4_EXECUTION_TEST_RELATIVE:
        EXPECTED_STAGE4_EXECUTION_TEST_SHA256,
    TAXONOMY_PRIMITIVE_RELATIVE:
        EXPECTED_TAXONOMY_PRIMITIVE_SHA256,
    POST_SEQUENCE_RELATIVE:
        EXPECTED_POST_SEQUENCE_SHA256,
    SOURCE_PARSER_RELATIVE:
        EXPECTED_SOURCE_PARSER_SHA256,
    TAXONOMY_ACQUISITION_FREEZE_RELATIVE:
        EXPECTED_TAXONOMY_ACQUISITION_FREEZE_SHA256,
}


class Stage4WrapperError(RuntimeError):
    """Raised when Stage 4 orchestration evidence fails closed."""


def sha256_file(
    path: Path,
    block_size: int = 8 * 1024 * 1024,
) -> str:
    """Return SHA256 for one exact regular file."""

    source = Path(
        path
    )

    if (
        not source.is_file()
        or source.is_symlink()
    ):
        raise Stage4WrapperError(
            "required regular file missing"
        )

    digest = hashlib.sha256()

    with source.open(
        "rb"
    ) as handle:
        for block in iter(
            lambda: handle.read(
                block_size
            ),
            b"",
        ):
            digest.update(
                block
            )

    return digest.hexdigest()


def require_lower_sha256(
    value: object,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or LOWER_SHA256_RE.fullmatch(
            value
        ) is None
    ):
        raise Stage4WrapperError(
            f"{label} must be lowercase SHA256"
        )

    return value


def require_sha256(
    path: Path,
    expected: object,
    label: str,
) -> str:
    expected_sha = require_lower_sha256(
        expected,
        f"{label} expected SHA256",
    )

    observed = sha256_file(
        path
    )

    if observed != expected_sha:
        raise Stage4WrapperError(
            f"{label} SHA256 mismatch"
        )

    return observed


def _positive_int(
    value: object,
    *,
    label: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise Stage4WrapperError(
            f"{label} must be a positive integer"
        )

    return value


def _nonnegative_counts(
    value: object,
    *,
    label: str,
) -> dict[str, int]:
    if not isinstance(
        value,
        Mapping,
    ):
        raise Stage4WrapperError(
            f"{label} must be a mapping"
        )

    result: dict[str, int] = {}

    for key, count in value.items():
        if (
            not isinstance(key, str)
            or not key
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            raise Stage4WrapperError(
                f"{label} is malformed"
            )

        result[key] = count

    return dict(
        sorted(
            result.items()
        )
    )


def write_json_atomic(
    path: Path,
    payload: object,
) -> str:
    """Write deterministic JSON through a sibling temporary file."""

    target = Path(
        path
    )

    temporary = target.with_name(
        target.name + ".tmp"
    )

    if temporary.exists():
        raise Stage4WrapperError(
            "JSON temporary output already exists"
        )

    try:
        temporary.write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        os.replace(
            temporary,
            target,
        )

    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise

    return sha256_file(
        target
    )


def write_tsv_atomic(
    path: Path,
    fields: Sequence[str],
    rows: Iterable[Mapping[str, object]],
) -> str:
    """Write deterministic TSV through a sibling temporary file."""

    target = Path(
        path
    )

    temporary = target.with_name(
        target.name + ".tmp"
    )

    if temporary.exists():
        raise Stage4WrapperError(
            "TSV temporary output already exists"
        )

    try:
        with temporary.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fields,
                delimiter="\t",
                lineterminator="\n",
                extrasaction="raise",
            )

            writer.writeheader()

            for row in rows:
                writer.writerow(
                    row
                )

        os.replace(
            temporary,
            target,
        )

    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise

    return sha256_file(
        target
    )


def evidence_row(
    *,
    source_group: str,
    batch: str,
    file_role: str,
    path: Path,
    expected_sha256: str,
) -> dict[str, str]:
    """Bind one exact input file without parsing its scientific contents."""

    observed_sha = require_sha256(
        path,
        expected_sha256,
        file_role,
    )

    return {
        "source_group":
            source_group,
        "batch":
            batch,
        "file_role":
            file_role,
        "file_name":
            Path(
                path
            ).name,
        "size_bytes":
            str(
                Path(
                    path
                ).stat().st_size
            ),
        "sha256":
            observed_sha,
    }


def verify_frozen_repo_files(
    repo: Path,
) -> dict[str, str]:
    """Require all pre-wrapper Stage 4 implementation identities."""

    root = Path(
        repo
    ).resolve()

    observed: dict[str, str] = {}

    for relative, expected in sorted(
        FROZEN_REPO_FILES.items(),
        key=lambda item:
            str(
                item[0]
            ),
    ):
        observed[
            str(
                relative
            )
        ] = require_sha256(
            root / relative,
            expected,
            str(
                relative
            ),
        )

    return observed


def verify_repo_state(
    repo: Path,
    expected_commit: str,
) -> None:
    """Require the exact clean local production execution commit."""

    root = Path(
        repo
    ).resolve()

    if (
        not isinstance(
            expected_commit,
            str,
        )
        or LOWER_GIT_COMMIT_RE.fullmatch(
            expected_commit
        ) is None
    ):
        raise Stage4WrapperError(
            "expected Git commit must be lowercase 40-hex"
        )

    try:
        head = subprocess.run(
            [
                "git",
                "-C",
                str(
                    root
                ),
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        status = subprocess.run(
            [
                "git",
                "-C",
                str(
                    root
                ),
                "status",
                "--porcelain",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    except (
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        raise Stage4WrapperError(
            "cannot verify production Git state"
        ) from exc

    if head != expected_commit:
        raise Stage4WrapperError(
            "production Git commit mismatch"
        )

    if status:
        raise Stage4WrapperError(
            "production worktree must be clean"
        )


def load_stage3_completion(
    path: Path,
    *,
    expected_sha256: str = (
        EXPECTED_STAGE3_COMPLETION_SHA256
    ),
    expected_execution_commit: str = (
        EXPECTED_STAGE3_EXECUTION_COMMIT
    ),
    expected_decisions_sha256: str = (
        EXPECTED_STAGE3_DECISIONS_SHA256
    ),
    expected_total: int = (
        EXPECTED_STAGE3_TOTAL
    ),
    expected_pass: int = (
        EXPECTED_STAGE4_TOTAL
    ),
    expected_status_counts: Mapping[str, int] = (
        EXPECTED_STAGE3_STATUS_COUNTS
    ),
    expected_reason_counts: Mapping[str, int] = (
        EXPECTED_STAGE3_REASON_COUNTS
    ),
) -> Mapping[str, object]:
    """Load the exact blinded Stage 3 completion checkpoint."""

    require_sha256(
        path,
        expected_sha256,
        "Stage 3 completion evidence",
    )

    try:
        payload = json.loads(
            Path(
                path
            ).read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise Stage4WrapperError(
            "cannot parse Stage 3 completion evidence"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise Stage4WrapperError(
            "Stage 3 completion evidence must be a JSON object"
        )

    if payload.get(
        "schema_version"
    ) != 1:
        raise Stage4WrapperError(
            "unexpected Stage 3 completion schema version"
        )

    if payload.get(
        "status"
    ) != "STAGE3_CHROMOSOME_INTEGRITY_COMPLETE":
        raise Stage4WrapperError(
            "Stage 3 completion status mismatch"
        )

    if payload.get(
        "execution_git_commit"
    ) != expected_execution_commit:
        raise Stage4WrapperError(
            "Stage 3 execution commit mismatch"
        )

    if (
        payload.get(
            "decision_row_count"
        ) != expected_total
        or payload.get(
            "stage3_input_candidate_count"
        ) != expected_total
        or payload.get(
            "pass_count"
        ) != expected_pass
    ):
        raise Stage4WrapperError(
            "Stage 3 completion candidate accounting mismatch"
        )

    observed_status = _nonnegative_counts(
        payload.get(
            "status_counts"
        ),
        label="Stage 3 completion status counts",
    )

    if observed_status != _nonnegative_counts(
        expected_status_counts,
        label="expected Stage 3 status counts",
    ):
        raise Stage4WrapperError(
            "Stage 3 completion status counts mismatch"
        )

    observed_reason = _nonnegative_counts(
        payload.get(
            "reason_counts"
        ),
        label="Stage 3 completion reason counts",
    )

    if observed_reason != _nonnegative_counts(
        expected_reason_counts,
        label="expected Stage 3 reason counts",
    ):
        raise Stage4WrapperError(
            "Stage 3 completion reason counts mismatch"
        )

    artifacts = payload.get(
        "artifacts_sha256"
    )

    if not isinstance(
        artifacts,
        Mapping,
    ):
        raise Stage4WrapperError(
            "Stage 3 completion artifacts malformed"
        )

    if artifacts.get(
        "stage3-chromosome-integrity-decisions.tsv"
    ) != expected_decisions_sha256:
        raise Stage4WrapperError(
            "Stage 3 decision artifact identity mismatch"
        )

    if payload.get(
        "later_stage"
    ) != EXPECTED_STAGE3_LATER_STAGE:
        raise Stage4WrapperError(
            "Stage 3 later-stage boundary mismatch"
        )

    return payload


def load_taxonomy_freeze(
    path: Path,
    *,
    expected_sha256: str = (
        EXPECTED_TAXONOMY_ACQUISITION_FREEZE_SHA256
    ),
) -> Mapping[str, object]:
    """Load and verify the frozen taxonomy acquisition checkpoint."""

    require_sha256(
        path,
        expected_sha256,
        "taxonomy acquisition freeze",
    )

    try:
        payload = json.loads(
            Path(
                path
            ).read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise Stage4WrapperError(
            "cannot parse taxonomy acquisition freeze"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise Stage4WrapperError(
            "taxonomy acquisition freeze must be a JSON object"
        )

    required = {
        "schema_version":
            1,
        "record_status":
            "FROZEN_TAXONOMY_ACQUISITION_EVIDENCE",
        "acquisition_exit_status":
            0,
        "bound_source_snapshot_id":
            EXPECTED_SOURCE_SNAPSHOT_ID,
        "bound_source_raw_report_sha256":
            EXPECTED_RAW_SOURCE_SHA256,
        "taxonomy_snapshot_id":
            EXPECTED_TAXONOMY_SNAPSHOT_ID,
        "archive_sha256":
            EXPECTED_TAXONOMY_ARCHIVE_SHA256,
        "nodes_sha256":
            EXPECTED_NODES_SHA256,
        "merged_sha256":
            EXPECTED_MERGED_SHA256,
        "delnodes_sha256":
            EXPECTED_DELNODES_SHA256,
        "taxonomy_snapshot_freeze_record_sha256":
            EXPECTED_TAXONOMY_SNAPSHOT_RECORD_SHA256,
        "source_taxonomy_sha256":
            EXPECTED_TAXONOMY_PRIMITIVE_SHA256,
        "independent_post_acquisition_audit":
            "pass",
        "structural_validation":
            "pass",
        "candidate_taxids_read":
            False,
        "candidate_species_generated":
            False,
        "taxonomy_resolution_performed":
            False,
        "complete_eligible_universe_generated":
            False,
        "holdout_membership_generated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    for key, expected in required.items():
        if payload.get(
            key
        ) != expected:
            raise Stage4WrapperError(
                f"taxonomy acquisition freeze mismatch: {key}"
            )

    return payload


def _ensure_output_root_outside_repo(
    output_root: Path,
    repo: Path,
) -> Path:
    output = Path(
        output_root
    ).resolve()

    root = Path(
        repo
    ).resolve()

    if (
        output == root
        or root in output.parents
    ):
        raise Stage4WrapperError(
            "Stage 4 output root must be outside the repository"
        )

    return output


def _taxonomy_paths(
    taxonomy_root: Path,
) -> dict[str, Path]:
    root = Path(
        taxonomy_root
    ).resolve()

    return {
        "nodes":
            root / "nodes.dmp",
        "merged":
            root / "merged.dmp",
        "delnodes":
            root / "delnodes.dmp",
        "snapshot_record":
            root / "taxonomy-snapshot-freeze.json",
    }


def execute_to_scratch(
    *,
    repo: Path,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    output_root: Path,
    stage3_completion_path: Path,
    stage3_completion: Mapping[str, object],
    stage3_decisions_path: Path,
    raw_source_path: Path,
    taxonomy_acquisition_freeze_path: Path,
    taxonomy_freeze: Mapping[str, object],
    taxonomy_root: Path,
    frozen_repo_sha256: Mapping[str, str],
    expected_stage3_decisions_sha256: str = (
        EXPECTED_STAGE3_DECISIONS_SHA256
    ),
    expected_stage3_total: int = (
        EXPECTED_STAGE3_TOTAL
    ),
    expected_stage4_total: int = (
        EXPECTED_STAGE4_TOTAL
    ),
    expected_raw_source_records: int = (
        EXPECTED_RAW_SOURCE_RECORDS
    ),
) -> Path:
    """Execute Stage 4 only after predecision evidence is finalized."""

    root = Path(
        repo
    ).resolve()

    wrapper_path = (
        root
        / STAGE4_WRAPPER_RELATIVE
    )

    wrapper_test_path = (
        root
        / STAGE4_WRAPPER_TEST_RELATIVE
    )

    wrapper_sha = require_sha256(
        wrapper_path,
        expected_wrapper_sha256,
        "Stage 4 production wrapper",
    )

    wrapper_test_sha = require_sha256(
        wrapper_test_path,
        expected_wrapper_test_sha256,
        "Stage 4 production wrapper tests",
    )

    if stage3_completion.get(
        "pass_count"
    ) != expected_stage4_total:
        raise Stage4WrapperError(
            "Stage 4 expected input differs from Stage 3 completion"
        )

    artifacts = stage3_completion.get(
        "artifacts_sha256"
    )

    if (
        not isinstance(
            artifacts,
            Mapping,
        )
        or artifacts.get(
            "stage3-chromosome-integrity-decisions.tsv"
        )
        != expected_stage3_decisions_sha256
    ):
        raise Stage4WrapperError(
            "Stage 3 completion does not bind Stage 4 input artifact"
        )

    taxonomy_paths = _taxonomy_paths(
        taxonomy_root
    )

    raw_source_sha = require_sha256(
        raw_source_path,
        taxonomy_freeze[
            "bound_source_raw_report_sha256"
        ],
        "frozen raw source JSONL",
    )

    stage3_decisions_sha = require_sha256(
        stage3_decisions_path,
        expected_stage3_decisions_sha256,
        "Stage 3 chromosome-integrity decisions",
    )

    nodes_sha = require_sha256(
        taxonomy_paths[
            "nodes"
        ],
        taxonomy_freeze[
            "nodes_sha256"
        ],
        "nodes.dmp",
    )

    merged_sha = require_sha256(
        taxonomy_paths[
            "merged"
        ],
        taxonomy_freeze[
            "merged_sha256"
        ],
        "merged.dmp",
    )

    delnodes_sha = require_sha256(
        taxonomy_paths[
            "delnodes"
        ],
        taxonomy_freeze[
            "delnodes_sha256"
        ],
        "delnodes.dmp",
    )

    snapshot_record_sha = require_sha256(
        taxonomy_paths[
            "snapshot_record"
        ],
        taxonomy_freeze[
            "taxonomy_snapshot_freeze_record_sha256"
        ],
        "taxonomy snapshot freeze record",
    )

    output = _ensure_output_root_outside_repo(
        output_root,
        root,
    )

    output.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_dir = (
        output
        / expected_commit
    )

    partial_dir = (
        output
        / (
            expected_commit
            + ".partial"
        )
    )

    if final_dir.exists():
        raise Stage4WrapperError(
            "final Stage 4 output directory already exists"
        )

    if partial_dir.exists():
        raise Stage4WrapperError(
            "partial Stage 4 output directory already exists"
        )

    partial_dir.mkdir()

    input_rows = (
        evidence_row(
            source_group="stage4-input",
            batch="",
            file_role="stage3_completion_evidence",
            path=stage3_completion_path,
            expected_sha256=(
                sha256_file(
                    stage3_completion_path
                )
            ),
        ),
        evidence_row(
            source_group="stage4-input",
            batch="",
            file_role="stage3_decisions",
            path=stage3_decisions_path,
            expected_sha256=stage3_decisions_sha,
        ),
        evidence_row(
            source_group="stage4-input",
            batch="",
            file_role="raw_source_jsonl",
            path=raw_source_path,
            expected_sha256=raw_source_sha,
        ),
        evidence_row(
            source_group="stage4-input",
            batch="",
            file_role="taxonomy_acquisition_freeze",
            path=taxonomy_acquisition_freeze_path,
            expected_sha256=(
                sha256_file(
                    taxonomy_acquisition_freeze_path
                )
            ),
        ),
        evidence_row(
            source_group="stage4-input",
            batch="",
            file_role="taxonomy_nodes",
            path=taxonomy_paths[
                "nodes"
            ],
            expected_sha256=nodes_sha,
        ),
        evidence_row(
            source_group="stage4-input",
            batch="",
            file_role="taxonomy_merged",
            path=taxonomy_paths[
                "merged"
            ],
            expected_sha256=merged_sha,
        ),
        evidence_row(
            source_group="stage4-input",
            batch="",
            file_role="taxonomy_delnodes",
            path=taxonomy_paths[
                "delnodes"
            ],
            expected_sha256=delnodes_sha,
        ),
        evidence_row(
            source_group="stage4-input",
            batch="",
            file_role="taxonomy_snapshot_freeze_record",
            path=taxonomy_paths[
                "snapshot_record"
            ],
            expected_sha256=snapshot_record_sha,
        ),
    )

    input_rows = tuple(
        sorted(
            input_rows,
            key=lambda row: (
                row[
                    "source_group"
                ],
                row[
                    "batch"
                ],
                row[
                    "file_role"
                ],
                row[
                    "file_name"
                ],
            ),
        )
    )

    input_manifest_path = (
        partial_dir
        / "stage4-input-evidence-manifest.tsv"
    )

    input_manifest_sha = write_tsv_atomic(
        input_manifest_path,
        INPUT_EVIDENCE_FIELDS,
        input_rows,
    )

    predecision_path = (
        partial_dir
        / "stage4-predecision-provenance.json"
    )

    predecision = {
        "schema_version":
            1,
        "status":
            "STAGE4_PREDECISION_FROZEN",
        "bacselect_git_commit":
            expected_commit,
        "stage4_method_sha256":
            EXPECTED_STAGE4_METHOD_SHA256,
        "stage3_completion_evidence_sha256":
            sha256_file(
                stage3_completion_path
            ),
        "stage3_candidate_decision_sha256":
            stage3_decisions_sha,
        "stage4_expected_input_candidate_count":
            expected_stage4_total,
        "raw_source_snapshot_id":
            taxonomy_freeze[
                "bound_source_snapshot_id"
            ],
        "raw_source_sha256":
            raw_source_sha,
        "raw_source_record_count":
            expected_raw_source_records,
        "source_taxid_field":
            "organism.tax_id",
        "taxonomy_snapshot_id":
            taxonomy_freeze[
                "taxonomy_snapshot_id"
            ],
        "taxonomy_acquisition_freeze_sha256":
            sha256_file(
                taxonomy_acquisition_freeze_path
            ),
        "taxonomy_archive_sha256":
            taxonomy_freeze[
                "archive_sha256"
            ],
        "nodes_sha256":
            nodes_sha,
        "merged_sha256":
            merged_sha,
        "delnodes_sha256":
            delnodes_sha,
        "taxonomy_snapshot_freeze_record_sha256":
            snapshot_record_sha,
        "taxonomy_primitive_sha256":
            EXPECTED_TAXONOMY_PRIMITIVE_SHA256,
        "post_sequence_composition_sha256":
            EXPECTED_POST_SEQUENCE_SHA256,
        "source_parser_sha256":
            EXPECTED_SOURCE_PARSER_SHA256,
        "stage4_execution_helper_sha256":
            EXPECTED_STAGE4_EXECUTION_SHA256,
        "stage4_execution_test_sha256":
            EXPECTED_STAGE4_EXECUTION_TEST_SHA256,
        "stage4_wrapper_sha256":
            wrapper_sha,
        "stage4_wrapper_test_sha256":
            wrapper_test_sha,
        "project_finch_taxonomy_commit":
            PROJECT_FINCH_TAXONOMY_COMMIT,
        "project_finch_taxonomy_path":
            PROJECT_FINCH_TAXONOMY_PATH,
        "project_finch_taxonomy_sha256":
            PROJECT_FINCH_TAXONOMY_SHA256,
        "frozen_repo_sha256":
            dict(
                sorted(
                    frozen_repo_sha256.items()
                )
            ),
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "candidate_taxids_read":
            False,
        "taxonomy_snapshot_parsed":
            False,
        "taxonomy_resolution_generated":
            False,
        "complete_eligible_universe_generated":
            False,
        "holdout_membership_generated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    predecision_sha = write_json_atomic(
        predecision_path,
        predecision,
    )

    try:
        stage3 = load_stage3_population(
            stage3_decisions_path,
            expected_sha256=(
                stage3_decisions_sha
            ),
            expected_total=(
                expected_stage3_total
            ),
            expected_pass=(
                expected_stage4_total
            ),
            expected_status_counts=(
                stage3_completion[
                    "status_counts"
                ]
            ),
            expected_reason_counts=(
                stage3_completion[
                    "reason_counts"
                ]
            ),
        )

        source = load_source_taxids(
            raw_source_path,
            expected_sha256=(
                raw_source_sha
            ),
            expected_record_count=(
                expected_raw_source_records
            ),
            wanted_accessions=(
                stage3.pass_accessions
            ),
        )

        taxonomy = Taxonomy(
            nodes_path=taxonomy_paths[
                "nodes"
            ],
            merged_path=taxonomy_paths[
                "merged"
            ],
            delnodes_path=taxonomy_paths[
                "delnodes"
            ],
        )

        evaluations = (
            evaluate_taxonomy_population(
                stage3=stage3,
                source=source,
                taxonomy=taxonomy,
            )
        )

        decision_build = (
            build_decision_rows(
                evaluations,
                expected_total=(
                    expected_stage4_total
                ),
            )
        )

    except (
        Stage4ExecutionError,
        Stage4WrapperError,
    ):
        raise
    except Exception as exc:
        raise Stage4WrapperError(
            "Stage 4 taxonomy evaluation failed closed"
        ) from exc

    if (
        decision_build.unique_organism_taxid_count
        != source.unique_selected_taxid_count
    ):
        raise Stage4WrapperError(
            "Stage 4 organism-TaxID aggregate disagreement"
        )

    decisions_path = (
        partial_dir
        / "stage4-taxonomy-decisions.tsv"
    )

    decisions_sha = write_tsv_atomic(
        decisions_path,
        STAGE4_DECISION_FIELDS,
        decision_build.rows,
    )

    status_counts = dict(
        sorted(
            decision_build.status_counts.items()
        )
    )

    reason_counts = dict(
        sorted(
            decision_build.reason_counts.items()
        )
    )

    if sum(
        status_counts.values()
    ) != expected_stage4_total:
        raise Stage4WrapperError(
            "Stage 4 status counts do not close"
        )

    if sum(
        reason_counts.values()
    ) != expected_stage4_total:
        raise Stage4WrapperError(
            "Stage 4 reason counts do not close"
        )

    execution_provenance_path = (
        partial_dir
        / "stage4-execution-provenance.json"
    )

    execution_provenance = {
        "schema_version":
            1,
        "status":
            "STAGE4_TAXONOMY_RESOLUTION_COMPLETE",
        "bacselect_git_commit":
            expected_commit,
        "predecision_provenance_sha256":
            predecision_sha,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "stage4_candidate_decision_sha256":
            decisions_sha,
        "stage4_input_candidate_count":
            expected_stage4_total,
        "stage4_input_membership_sha256":
            stage3.pass_membership_sha256,
        "stage4_decision_row_count":
            len(
                decision_build.rows
            ),
        "status_counts":
            status_counts,
        "reason_counts":
            reason_counts,
        "unique_frozen_organism_taxid_count":
            decision_build.unique_organism_taxid_count,
        "resolved_distinct_species_taxid_count":
            (
                decision_build
                .resolved_distinct_species_taxid_count
            ),
        "raw_source_snapshot_id":
            taxonomy_freeze[
                "bound_source_snapshot_id"
            ],
        "raw_source_sha256":
            raw_source_sha,
        "taxonomy_snapshot_id":
            taxonomy_freeze[
                "taxonomy_snapshot_id"
            ],
        "taxonomy_acquisition_freeze_sha256":
            sha256_file(
                taxonomy_acquisition_freeze_path
            ),
        "taxonomy_archive_sha256":
            taxonomy_freeze[
                "archive_sha256"
            ],
        "nodes_sha256":
            nodes_sha,
        "merged_sha256":
            merged_sha,
        "delnodes_sha256":
            delnodes_sha,
        "taxonomy_snapshot_freeze_record_sha256":
            snapshot_record_sha,
        "stage4_method_sha256":
            EXPECTED_STAGE4_METHOD_SHA256,
        "stage4_execution_helper_sha256":
            EXPECTED_STAGE4_EXECUTION_SHA256,
        "stage4_execution_test_sha256":
            EXPECTED_STAGE4_EXECUTION_TEST_SHA256,
        "taxonomy_primitive_sha256":
            EXPECTED_TAXONOMY_PRIMITIVE_SHA256,
        "post_sequence_composition_sha256":
            EXPECTED_POST_SEQUENCE_SHA256,
        "source_parser_sha256":
            EXPECTED_SOURCE_PARSER_SHA256,
        "stage4_wrapper_sha256":
            wrapper_sha,
        "stage4_wrapper_test_sha256":
            wrapper_test_sha,
        "project_finch_taxonomy_commit":
            PROJECT_FINCH_TAXONOMY_COMMIT,
        "project_finch_taxonomy_path":
            PROJECT_FINCH_TAXONOMY_PATH,
        "project_finch_taxonomy_sha256":
            PROJECT_FINCH_TAXONOMY_SHA256,
        "taxonomy_resolution_generated":
            True,
        "complete_eligible_universe_generated":
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
        / "stage4-aggregate-summary.json"
    )

    summary = {
        "schema_version":
            1,
        "status":
            "STAGE4_TAXONOMY_RESOLUTION_COMPLETE",
        "stage4_input_candidate_count":
            expected_stage4_total,
        "stage4_input_membership_sha256":
            stage3.pass_membership_sha256,
        "decision_count":
            len(
                decision_build.rows
            ),
        "status_counts":
            status_counts,
        "reason_counts":
            reason_counts,
        "unique_frozen_organism_taxid_count":
            decision_build.unique_organism_taxid_count,
        "resolved_distinct_species_taxid_count":
            (
                decision_build
                .resolved_distinct_species_taxid_count
            ),
        "candidate_decisions_sha256":
            decisions_sha,
        "predecision_provenance_sha256":
            predecision_sha,
        "execution_provenance_sha256":
            execution_provenance_sha,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "taxonomy_resolution_generated":
            True,
        "complete_eligible_universe_generated":
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

    content_paths = (
        input_manifest_path,
        predecision_path,
        decisions_path,
        execution_provenance_path,
        summary_path,
    )

    content_rows = tuple(
        {
            "path":
                path.name,
            "size_bytes":
                str(
                    path.stat().st_size
                ),
            "sha256":
                sha256_file(
                    path
                ),
        }
        for path in sorted(
            content_paths,
            key=lambda item:
                item.name,
        )
    )

    content_manifest_path = (
        partial_dir
        / "stage4-content-manifest.tsv"
    )

    content_manifest_sha = (
        write_tsv_atomic(
            content_manifest_path,
            CONTENT_MANIFEST_FIELDS,
            content_rows,
        )
    )

    if final_dir.exists():
        raise Stage4WrapperError(
            "final Stage 4 directory appeared before finalization"
        )

    os.replace(
        partial_dir,
        final_dir,
    )

    print(
        "PASS | Stage 4 taxonomy-resolution execution complete"
    )

    print(
        "stage4_input_candidate_count="
        f"{expected_stage4_total}"
    )

    print(
        "stage4_input_membership_sha256="
        f"{stage3.pass_membership_sha256}"
    )

    print(
        "status_counts="
        + json.dumps(
            status_counts,
            sort_keys=True,
        )
    )

    print(
        "reason_counts="
        + json.dumps(
            reason_counts,
            sort_keys=True,
        )
    )

    print(
        "unique_frozen_organism_taxid_count="
        f"{decision_build.unique_organism_taxid_count}"
    )

    print(
        "resolved_distinct_species_taxid_count="
        f"{decision_build.resolved_distinct_species_taxid_count}"
    )

    print(
        "candidate_decisions_sha256="
        f"{decisions_sha}"
    )

    print(
        "predecision_provenance_sha256="
        f"{predecision_sha}"
    )

    print(
        "execution_provenance_sha256="
        f"{execution_provenance_sha}"
    )

    print(
        "aggregate_summary_sha256="
        f"{summary_sha}"
    )

    print(
        "content_manifest_sha256="
        f"{content_manifest_sha}"
    )

    print(
        "execution_dir="
        f"{final_dir}"
    )

    return final_dir


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute frozen BacSelect selector-v1 "
            "Stage 4 taxonomy resolution."
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
        "--expected-wrapper-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-test-sha256",
        required=True,
    )

    parser.add_argument(
        "--stage3-decisions",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--raw-source",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--taxonomy-root",
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

    try:
        repo = args.repo.resolve()

        verify_repo_state(
            repo,
            args.expected_commit,
        )

        frozen_repo_sha256 = (
            verify_frozen_repo_files(
                repo
            )
        )

        require_sha256(
            repo
            / STAGE4_WRAPPER_RELATIVE,
            args.expected_wrapper_sha256,
            "Stage 4 production wrapper",
        )

        require_sha256(
            repo
            / STAGE4_WRAPPER_TEST_RELATIVE,
            args.expected_wrapper_test_sha256,
            "Stage 4 production wrapper tests",
        )

        stage3_completion_path = (
            repo
            / STAGE3_COMPLETION_RELATIVE
        )

        stage3_completion = (
            load_stage3_completion(
                stage3_completion_path
            )
        )

        taxonomy_acquisition_freeze_path = (
            repo
            / TAXONOMY_ACQUISITION_FREEZE_RELATIVE
        )

        taxonomy_freeze = (
            load_taxonomy_freeze(
                taxonomy_acquisition_freeze_path
            )
        )

        print(
            "PASS | frozen Stage 4 production inputs verified"
        )

        print(
            "stage4_expected_input_candidate_count="
            f"{EXPECTED_STAGE4_TOTAL}"
        )

        print(
            "stage3_candidate_decision_sha256="
            f"{EXPECTED_STAGE3_DECISIONS_SHA256}"
        )

        print(
            "raw_source_sha256="
            f"{EXPECTED_RAW_SOURCE_SHA256}"
        )

        print(
            "taxonomy_snapshot_id="
            f"{EXPECTED_TAXONOMY_SNAPSHOT_ID}"
        )

        execute_to_scratch(
            repo=repo,
            expected_commit=(
                args.expected_commit
            ),
            expected_wrapper_sha256=(
                args.expected_wrapper_sha256
            ),
            expected_wrapper_test_sha256=(
                args.expected_wrapper_test_sha256
            ),
            output_root=(
                args.output_root
            ),
            stage3_completion_path=(
                stage3_completion_path
            ),
            stage3_completion=(
                stage3_completion
            ),
            stage3_decisions_path=(
                args.stage3_decisions
            ),
            raw_source_path=(
                args.raw_source
            ),
            taxonomy_acquisition_freeze_path=(
                taxonomy_acquisition_freeze_path
            ),
            taxonomy_freeze=(
                taxonomy_freeze
            ),
            taxonomy_root=(
                args.taxonomy_root
            ),
            frozen_repo_sha256=(
                frozen_repo_sha256
            ),
        )

    except Exception:
        print(
            "ERROR | Stage 4 taxonomy execution failed closed",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
