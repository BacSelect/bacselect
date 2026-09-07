#!/usr/bin/env python3
"""Parallel worker/shard support for BacSelect monthly Stage 6-v2."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Mapping, Sequence

from bacselect.source_truth_execution import accession_membership_sha256


SERIAL_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_chromosome_integrity_v2.py"
)

SERIAL_WRAPPER_SHA256 = (
    "df5ba50c5b7f3df2c5a823ddd35d57273b61c4a1e1bc145bb34fc7e23a9b7ec8"
)

SHARD_SCHEMA = (
    "bacselect-monthly-chromosome-integrity-shard-v2"
)
SHARD_STATUS = (
    "CHROMOSOME_INTEGRITY_SHARD_COMPLETE"
)

SHARD_DECISIONS_NAME = (
    "chromosome-integrity-decisions.tsv"
)
SHARD_RECEIPT_NAME = "shard-receipt.json"

_BATCH_RE = re.compile(
    r"^batch-[0-9]{5}$"
)


class ParallelStage6Error(RuntimeError):
    """Raised when Stage 6-v2 parallel execution fails closed."""


@dataclass(frozen=True)
class WorkerRuntime:
    serial: ModuleType
    stage6_v1: ModuleType
    stage5_v2: ModuleType
    stage5_v1: ModuleType
    stage4_v2: ModuleType
    stage4_v1: ModuleType
    context: object
    population: object


@dataclass(frozen=True)
class BatchSelection:
    batch_id: str
    provenance_sha256: str
    accessions: tuple[str, ...]


@dataclass(frozen=True)
class BatchEvaluation:
    selection: BatchSelection
    decisions_payload: bytes
    candidate_count: int
    triggered_count: int
    pass_count: int
    excluded_count: int
    unresolved_count: int
    provider_class: str


def _fail(message: str) -> None:
    raise ParallelStage6Error(
        message
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def _canonical_json(
    value: Mapping[str, object],
) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def _load_module(
    path: Path,
    *,
    name: str,
    expected_sha256: str,
) -> ModuleType:
    path = Path(path)

    if (
        path.is_symlink()
        or not path.is_file()
    ):
        _fail(
            f"{name} is not a regular file"
        )

    if (
        _sha256_file(path)
        != expected_sha256
    ):
        _fail(
            f"{name} SHA256 mismatch"
        )

    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        _fail(
            f"cannot import {name}"
        )

    module = importlib.util.module_from_spec(
        spec
    )
    sys.modules[
        spec.name
    ] = module
    spec.loader.exec_module(
        module
    )

    return module


def load_serial_v2(
    repo: Path,
) -> ModuleType:
    return _load_module(
        Path(repo)
        / SERIAL_WRAPPER_RELATIVE,
        name="_bacselect_stage6_v2_serial",
        expected_sha256=(
            SERIAL_WRAPPER_SHA256
        ),
    )


def _batch_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _BATCH_RE.fullmatch(
            value
        )
        is None
    ):
        _fail(
            "batch_id must use batch-NNNNN"
        )

    return value


def load_worker_runtime(
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
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
    expected_source_truth_completion_sha256: str,
    expected_biosample_completion_sha256: str,
) -> WorkerRuntime:
    repo = Path(
        repo
    ).resolve()

    serial = load_serial_v2(
        repo
    )

    stage6_v1 = (
        serial.load_stage6_v1(
            repo
        )
    )

    stage5_v2 = (
        serial.load_stage5_v2(
            repo
        )
    )

    stage5_v1 = (
        stage5_v2.load_stage5_v1(
            repo
        )
    )

    stage4_v2 = (
        stage5_v2.load_stage4_v2(
            repo
        )
    )

    stage4_v1 = (
        stage4_v2.load_stage4_v1(
            repo
        )
    )

    chromosome_commit = (
        stage4_v2.validate_commit(
            chromosome_execution_commit,
            label=(
                "chromosome execution commit"
            ),
        )
    )

    if (
        serial._git(
            repo,
            "rev-parse",
            "HEAD",
        )
        != chromosome_commit
    ):
        _fail(
            "repository HEAD differs from "
            "chromosome execution commit"
        )

    if serial._git(
        repo,
        "status",
        "--porcelain",
    ):
        _fail(
            "repository is not clean"
        )

    context = (
        serial.load_stage5_context_v2(
            repo=repo,
            source_repo=(
                Path(source_repo)
            ),
            production_root=(
                Path(production_root)
            ),
            stage1_root=(
                Path(stage1_root)
            ),
            source_production_commit=(
                source_production_commit
            ),
            completion_execution_commit=(
                completion_execution_commit
            ),
            cache_execution_commit=(
                cache_execution_commit
            ),
            source_truth_execution_commit=(
                source_truth_execution_commit
            ),
            biosample_execution_commit=(
                biosample_execution_commit
            ),
            expected_completion_sha256=(
                expected_completion_sha256
            ),
            expected_catalogue_sha256=(
                expected_catalogue_sha256
            ),
            expected_source_truth_completion_sha256=(
                expected_source_truth_completion_sha256
            ),
            expected_biosample_completion_sha256=(
                expected_biosample_completion_sha256
            ),
            stage6_v1=stage6_v1,
            stage5_v2=stage5_v2,
        )
    )

    try:
        population = (
            stage6_v1
            .monthly_chromosome_integrity
            .build_monthly_chromosome_population(
                context.decisions_payload,
                expected_biosample_decisions_sha256=(
                    context
                    .completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                origin_git_commit=(
                    chromosome_commit
                ),
            )
        )
    except Exception as exc:
        raise ParallelStage6Error(
            "Stage 6 population "
            "construction failed"
        ) from exc

    return WorkerRuntime(
        serial=serial,
        stage6_v1=stage6_v1,
        stage5_v2=stage5_v2,
        stage5_v1=stage5_v1,
        stage4_v2=stage4_v2,
        stage4_v1=stage4_v1,
        context=context,
        population=population,
    )


def select_batch(
    runtime: WorkerRuntime,
    batch_id: str,
) -> BatchSelection:
    batch = _batch_id(
        batch_id
    )

    stage4 = (
        runtime
        .context
        .stage4_context
    )

    selected = []
    provenance_values = set()

    for accession in (
        runtime
        .population
        .continue_accessions
    ):
        entry = (
            stage4
            .entries_by_accession
            .get(
                accession
            )
        )

        if entry is None:
            _fail(
                f"{accession}: "
                "catalogue entry missing"
            )

        provenance_sha = (
            runtime
            .stage4_v1
            .validate_sha256(
                entry.get(
                    "origin_batch_provenance_sha256"
                ),
                label=(
                    "origin batch-provenance SHA256"
                ),
            )
        )

        provenance = (
            stage4
            .provenance_by_sha
            .get(
                provenance_sha
            )
        )

        if provenance is None:
            _fail(
                f"{accession}: "
                "provenance missing"
            )

        if (
            provenance.get(
                "cache_origin_release_id"
            )
            != runtime.context.release_id
        ):
            _fail(
                "September Stage 6-v2 "
                "encountered historical origin"
            )

        observed_batch = str(
            provenance.get(
                "batch_id",
                "",
            )
        )

        if observed_batch == batch:
            selected.append(
                accession
            )
            provenance_values.add(
                provenance_sha
            )

    if not selected:
        _fail(
            f"{batch}: no Stage 6 "
            "CONTINUE candidates"
        )

    if len(
        provenance_values
    ) != 1:
        _fail(
            f"{batch}: expected exactly "
            "one provenance identity"
        )

    accessions = tuple(
        selected
    )

    if accessions != tuple(
        sorted(
            accessions
        )
    ):
        _fail(
            f"{batch}: candidate "
            "membership is not sorted"
        )

    return BatchSelection(
        batch_id=batch,
        provenance_sha256=next(
            iter(
                provenance_values
            )
        ),
        accessions=accessions,
    )


def subset_population(
    runtime: WorkerRuntime,
    selection: BatchSelection,
):
    full = runtime.population

    return (
        runtime
        .stage6_v1
        .monthly_chromosome_integrity
        .MonthlyChromosomePopulation(
            release_id=(
                full.release_id
            ),
            source_snapshot_id=(
                full.source_snapshot_id
            ),
            origin_git_commit=(
                full.origin_git_commit
            ),
            biosample_decisions_sha256=(
                full.biosample_decisions_sha256
            ),
            continue_accessions=(
                selection.accessions
            ),
            continue_accessions_sha256=(
                accession_membership_sha256(
                    selection.accessions
                )
            ),
            source_evidence_sha256_by_accession={
                accession:
                    full
                    .source_evidence_sha256_by_accession[
                        accession
                    ]
                for accession
                in selection.accessions
            },
        )
    )


def evaluate_batch(
    *,
    runtime: WorkerRuntime,
    stage1_root: Path,
    selection: BatchSelection,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
) -> BatchEvaluation:
    stage4 = (
        runtime
        .context
        .stage4_context
    )

    provenance = (
        stage4
        .provenance_by_sha[
            selection.provenance_sha256
        ]
    )

    completion_batch = (
        stage4
        .completion_by_batch
        .get(
            selection.batch_id
        )
    )

    if completion_batch is None:
        _fail(
            f"{selection.batch_id}: "
            "missing completion-v2 batch"
        )

    try:
        provider = (
            runtime
            .stage4_v2
            ._provider_batch_context_v2(
                stage1_root=(
                    Path(
                        stage1_root
                    ).resolve()
                ),
                cache_execution=(
                    stage4.cache_execution
                ),
                provenance=(
                    provenance
                ),
                completion_batch=(
                    completion_batch
                ),
                release_id=(
                    runtime
                    .context
                    .release_id
                ),
                source_snapshot_id=(
                    runtime
                    .context
                    .source_snapshot_id
                ),
                source_production_commit=(
                    source_production_commit
                ),
                completion_execution_commit=(
                    completion_execution_commit
                ),
                cache_execution_commit=(
                    cache_execution_commit
                ),
                completion_sha256=(
                    stage4
                    .completion_v2_sha256
                ),
            )
        )
    except Exception as exc:
        raise ParallelStage6Error(
            f"{selection.batch_id}: "
            "provider authentication failed"
        ) from exc

    evaluations = []

    for accession in (
        selection.accessions
    ):
        entry = (
            stage4
            .entries_by_accession[
                accession
            ]
        )

        try:
            bridge = (
                runtime
                .stage4_v1
                .validate_candidate_bridge(
                    stage4.cache_execution,
                    entry=entry,
                    batch=provider.batch,
                )
            )
        except Exception as exc:
            raise ParallelStage6Error(
                f"{accession}: "
                "candidate bridge audit failed"
            ) from exc

        if bridge.accession != accession:
            _fail(
                f"{accession}: "
                "candidate bridge identity changed"
            )

        expected_source_sha = (
            runtime
            .population
            .source_evidence_sha256_by_accession[
                accession
            ]
        )

        source_row = (
            stage4
            .decision_by_accession
            .get(
                accession
            )
        )

        if (
            source_row is None
            or source_row[
                "source_truth_status"
            ]
            != runtime
            .stage5_v1
            .source_truth
            .SUITABLE
            or source_row[
                "source_evidence_sha256"
            ]
            != expected_source_sha
        ):
            _fail(
                f"{accession}: "
                "authenticated Stage 4 "
                "source truth changed"
            )

        try:
            (
                candidate,
                components,
                package_manifest,
            ) = (
                runtime
                .stage4_v1
                ._source_truth_objects(
                    bridge,
                    audit_path=(
                        provider
                        .candidate_audit_path
                    ),
                )
            )

            evaluated = (
                runtime
                .stage6_v1
                .source_chromosome_integrity_execution
                .evaluate_stage3_candidate(
                    candidate=candidate,
                    component_rows=(
                        components
                    ),
                    package_manifest=(
                        package_manifest
                    ),
                    expected_source_evidence_sha256=(
                        expected_source_sha
                    ),
                    historical_provider=(
                        runtime
                        .stage6_v1
                        .monthly_historical_provider
                    ),
                )
            )
        except Exception as exc:
            raise ParallelStage6Error(
                f"{accession}: "
                "frozen chromosome "
                "evaluation failed"
            ) from exc

        if (
            evaluated.accession
            != accession
            or evaluated
            .source_evidence_sha256
            != expected_source_sha
        ):
            _fail(
                f"{accession}: "
                "frozen evaluation "
                "identity changed"
            )

        evaluations.append(
            evaluated
        )

    if tuple(
        value.accession
        for value in evaluations
    ) != selection.accessions:
        _fail(
            f"{selection.batch_id}: "
            "evaluation membership changed"
        )

    # Reauthenticate the small provider evidence after
    # expensive sequence evaluation. This intentionally
    # does NOT perform an additional whole-package pass.
    try:
        runtime.stage4_v1.reverify_observations(
            tuple(
                runtime
                .stage4_v1
                .InputObservation(
                    path=path,
                    sha256=digest,
                    size_bytes=size,
                )
                for path, digest, size
                in provider.observations
            )
        )
    except Exception as exc:
        raise ParallelStage6Error(
            f"{selection.batch_id}: "
            "provider evidence changed "
            "during evaluation"
        ) from exc

    subpopulation = subset_population(
        runtime,
        selection,
    )

    try:
        build = (
            runtime
            .stage6_v1
            .monthly_chromosome_integrity
            .build_monthly_chromosome_integrity(
                subpopulation,
                evaluations,
            )
        )

        decisions = (
            runtime
            .stage6_v1
            .monthly_chromosome_integrity
            .serialize_monthly_chromosome_decisions(
                build
            )
        )

        runtime.stage6_v1.monthly_chromosome_integrity.audit_monthly_chromosome_decisions(
            decisions
        )
    except Exception as exc:
        raise ParallelStage6Error(
            f"{selection.batch_id}: "
            "canonical shard build failed"
        ) from exc

    pass_count = int(
        build.status_counts.get(
            runtime
            .stage6_v1
            .source_chromosome_integrity
            .PASS,
            0,
        )
    )

    excluded_count = int(
        build.status_counts.get(
            runtime
            .stage6_v1
            .source_chromosome_integrity
            .EXCLUDE,
            0,
        )
    )

    unresolved_count = int(
        build.status_counts.get(
            runtime
            .stage6_v1
            .source_chromosome_integrity
            .UNRESOLVED,
            0,
        )
    )

    if (
        pass_count
        + excluded_count
        + unresolved_count
        != len(
            selection.accessions
        )
    ):
        _fail(
            f"{selection.batch_id}: "
            "shard status accounting changed"
        )

    provider_class = (
        "fresh-recovery"
        if (
            "sequence-acquisition-recovery"
            in provider.provider_root.parts
        )
        else "fresh"
    )

    return BatchEvaluation(
        selection=selection,
        decisions_payload=(
            decisions
        ),
        candidate_count=len(
            selection.accessions
        ),
        triggered_count=(
            build
            .triggered_candidate_count
        ),
        pass_count=(
            pass_count
        ),
        excluded_count=(
            excluded_count
        ),
        unresolved_count=(
            unresolved_count
        ),
        provider_class=(
            provider_class
        ),
    )


def build_shard_receipt(
    *,
    runtime: WorkerRuntime,
    evaluation: BatchEvaluation,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    chromosome_execution_commit: str,
    work_manifest_sha256: str,
) -> bytes:
    context = runtime.context
    stage4 = (
        context.stage4_context
    )

    receipt = {
        "schema_version":
            SHARD_SCHEMA,
        "status":
            SHARD_STATUS,
        "release_id":
            context.release_id,
        "source_snapshot_id":
            context.source_snapshot_id,
        "batch_id":
            evaluation
            .selection
            .batch_id,
        "provider_class":
            evaluation
            .provider_class,
        "batch_provenance_sha256":
            evaluation
            .selection
            .provenance_sha256,
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
        "work_manifest_sha256":
            runtime.stage4_v1.validate_sha256(
                work_manifest_sha256,
                label="Stage 6 work-manifest SHA256",
            ),
        "sequence_acquisition_completion_sha256":
            stage4.completion_v2_sha256,
        "sequence_cache_catalogue_sha256":
            stage4.catalogue_sha256,
        "source_truth_completion_sha256":
            stage4.source_truth_completion_sha256,
        "biosample_completion_sha256":
            context.completion_sha256,
        "candidate_count":
            evaluation.candidate_count,
        "candidate_accessions_sha256":
            accession_membership_sha256(
                evaluation
                .selection
                .accessions
            ),
        "triggered_count":
            evaluation.triggered_count,
        "pass_count":
            evaluation.pass_count,
        "excluded_count":
            evaluation.excluded_count,
        "unresolved_count":
            evaluation.unresolved_count,
        "decisions_sha256":
            hashlib.sha256(
                evaluation
                .decisions_payload
            ).hexdigest(),
    }

    return _canonical_json(
        receipt
    )


def publish_shard(
    *,
    shard_root: Path,
    evaluation: BatchEvaluation,
    receipt_payload: bytes,
    stage5_v1,
) -> Path:
    root = Path(
        shard_root
    ).resolve()

    root.mkdir(
        mode=0o755,
        parents=True,
        exist_ok=True,
    )

    final = (
        root
        / evaluation
        .selection
        .batch_id
    )

    partial = (
        root
        / (
            evaluation
            .selection
            .batch_id
            + ".partial"
        )
    )

    for path in (
        final,
        partial,
    ):
        if os.path.lexists(
            path
        ):
            _fail(
                f"shard path already exists: "
                f"{path}"
            )

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    try:
        stage5_v1.write_no_clobber(
            partial
            / SHARD_DECISIONS_NAME,
            evaluation.decisions_payload,
        )

        stage5_v1.write_no_clobber(
            partial
            / SHARD_RECEIPT_NAME,
            receipt_payload,
        )

        stage5_v1.fsync_directory(
            partial
        )

        os.rename(
            partial,
            final,
        )

        stage5_v1.fsync_directory(
            root
        )

    except Exception:
        if (
            partial.exists()
            and not partial.is_symlink()
        ):
            for child in (
                partial.iterdir()
            ):
                child.unlink()
            partial.rmdir()

        raise

    return final


# ---------------------------------------------------------------------------
# Frozen parallel work plan, shard authentication and global aggregation.
# ---------------------------------------------------------------------------

import argparse


WORK_MANIFEST_NAME = "work-manifest.tsv"

WORK_MANIFEST_HEADER = (
    "task_id",
    "batch_id",
    "provenance_sha256",
    "candidate_count",
    "candidate_accessions_sha256",
)

SEPTEMBER_BATCH_COUNT = 142


def build_batch_selections(
    runtime: WorkerRuntime,
) -> tuple[
    BatchSelection,
    ...
]:
    stage4 = (
        runtime.context.stage4_context
    )

    accessions_by_batch: dict[
        str,
        list[str],
    ] = {}

    provenance_by_batch: dict[
        str,
        str,
    ] = {}

    for accession in (
        runtime.population.continue_accessions
    ):
        entry = (
            stage4.entries_by_accession.get(
                accession
            )
        )

        if entry is None:
            _fail(
                f"{accession}: catalogue entry missing"
            )

        provenance_sha = (
            runtime.stage4_v1.validate_sha256(
                entry.get(
                    "origin_batch_provenance_sha256"
                ),
                label=(
                    "origin batch-provenance SHA256"
                ),
            )
        )

        provenance = (
            stage4.provenance_by_sha.get(
                provenance_sha
            )
        )

        if provenance is None:
            _fail(
                f"{accession}: provenance missing"
            )

        if (
            provenance.get(
                "cache_origin_release_id"
            )
            != runtime.context.release_id
        ):
            _fail(
                "September Stage 6-v2 "
                "encountered historical origin"
            )

        batch = _batch_id(
            provenance.get(
                "batch_id"
            )
        )

        previous = (
            provenance_by_batch.get(
                batch
            )
        )

        if (
            previous is not None
            and previous != provenance_sha
        ):
            _fail(
                f"{batch}: multiple provenance "
                "identities observed"
            )

        provenance_by_batch[
            batch
        ] = provenance_sha

        accessions_by_batch.setdefault(
            batch,
            [],
        ).append(
            accession
        )

    batches = tuple(
        sorted(
            accessions_by_batch
        )
    )

    if (
        runtime.context.release_id
        == "2026.09"
    ):
        expected = tuple(
            f"batch-{value:05d}"
            for value in range(
                1,
                SEPTEMBER_BATCH_COUNT + 1,
            )
        )

        if batches != expected:
            _fail(
                "September Stage 6-v2 batch "
                "membership differs from 1..142"
            )

    selections = []

    for batch in batches:
        accessions = tuple(
            sorted(
                accessions_by_batch[
                    batch
                ]
            )
        )

        if not accessions:
            _fail(
                f"{batch}: empty Stage 6 population"
            )

        selections.append(
            BatchSelection(
                batch_id=batch,
                provenance_sha256=(
                    provenance_by_batch[
                        batch
                    ]
                ),
                accessions=accessions,
            )
        )

    if sum(
        len(
            selection.accessions
        )
        for selection in selections
    ) != len(
        runtime.population.continue_accessions
    ):
        _fail(
            "parallel work-plan population "
            "accounting changed"
        )

    return tuple(
        selections
    )


def select_batch(
    runtime: WorkerRuntime,
    batch_id: str,
) -> BatchSelection:
    batch = _batch_id(
        batch_id
    )

    for selection in (
        build_batch_selections(
            runtime
        )
    ):
        if selection.batch_id == batch:
            return selection

    _fail(
        f"{batch}: no Stage 6 CONTINUE candidates"
    )


def build_work_manifest(
    runtime: WorkerRuntime,
) -> bytes:
    lines = [
        "\t".join(
            WORK_MANIFEST_HEADER
        )
    ]

    for task_id, selection in enumerate(
        build_batch_selections(
            runtime
        ),
        start=1,
    ):
        lines.append(
            "\t".join(
                (
                    str(
                        task_id
                    ),
                    selection.batch_id,
                    selection.provenance_sha256,
                    str(
                        len(
                            selection.accessions
                        )
                    ),
                    accession_membership_sha256(
                        selection.accessions
                    ),
                )
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "ascii"
    )


def audit_work_manifest(
    runtime: WorkerRuntime,
    payload: bytes,
) -> tuple[
    BatchSelection,
    ...
]:
    if not isinstance(
        payload,
        bytes,
    ):
        _fail(
            "work manifest must be bytes"
        )

    expected = build_work_manifest(
        runtime
    )

    if payload != expected:
        _fail(
            "Stage 6 work manifest differs "
            "from authenticated population"
        )

    return build_batch_selections(
        runtime
    )


def publish_work_manifest(
    *,
    path: Path,
    runtime: WorkerRuntime,
) -> tuple[
    Path,
    str,
]:
    path = Path(
        path
    )

    path.parent.mkdir(
        mode=0o755,
        parents=True,
        exist_ok=True,
    )

    if os.path.lexists(
        path
    ):
        _fail(
            "Stage 6 work manifest already exists"
        )

    payload = build_work_manifest(
        runtime
    )

    runtime.stage5_v1.write_no_clobber(
        path,
        payload,
    )

    runtime.stage5_v1.fsync_directory(
        path.parent
    )

    observed = (
        runtime.stage5_v1
        ._require_regular_file(
            path,
            label="Stage 6 work manifest",
        )
        .read_bytes()
    )

    audit_work_manifest(
        runtime,
        observed,
    )

    digest = hashlib.sha256(
        observed
    ).hexdigest()

    return (
        path,
        digest,
    )


def load_work_manifest(
    *,
    path: Path,
    runtime: WorkerRuntime,
) -> tuple[
    bytes,
    tuple[
        BatchSelection,
        ...
    ],
]:
    try:
        payload = (
            runtime.stage5_v1
            ._require_regular_file(
                Path(
                    path
                ),
                label="Stage 6 work manifest",
            )
            .read_bytes()
        )
    except Exception as exc:
        raise ParallelStage6Error(
            "Stage 6 work-manifest loading failed"
        ) from exc

    selections = audit_work_manifest(
        runtime,
        payload,
    )

    return (
        payload,
        selections,
    )


def _provider_for_selection(
    *,
    runtime: WorkerRuntime,
    stage1_root: Path,
    selection: BatchSelection,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
):
    stage4 = (
        runtime.context.stage4_context
    )

    provenance = (
        stage4.provenance_by_sha.get(
            selection.provenance_sha256
        )
    )

    if provenance is None:
        _fail(
            f"{selection.batch_id}: "
            "provenance disappeared"
        )

    completion_batch = (
        stage4.completion_by_batch.get(
            selection.batch_id
        )
    )

    if completion_batch is None:
        _fail(
            f"{selection.batch_id}: "
            "completion-v2 batch disappeared"
        )

    try:
        provider = (
            runtime.stage4_v2
            ._provider_batch_context_v2(
                stage1_root=(
                    Path(
                        stage1_root
                    ).resolve()
                ),
                cache_execution=(
                    stage4.cache_execution
                ),
                provenance=provenance,
                completion_batch=(
                    completion_batch
                ),
                release_id=(
                    runtime.context.release_id
                ),
                source_snapshot_id=(
                    runtime.context.source_snapshot_id
                ),
                source_production_commit=(
                    source_production_commit
                ),
                completion_execution_commit=(
                    completion_execution_commit
                ),
                cache_execution_commit=(
                    cache_execution_commit
                ),
                completion_sha256=(
                    stage4.completion_v2_sha256
                ),
            )
        )
    except Exception as exc:
        raise ParallelStage6Error(
            f"{selection.batch_id}: "
            "provider authentication failed"
        ) from exc

    return provider


def audit_shard(
    *,
    runtime: WorkerRuntime,
    stage1_root: Path,
    shard_path: Path,
    selection: BatchSelection,
    work_manifest_sha256: str,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    chromosome_execution_commit: str,
) -> tuple[
    tuple[
        object,
        ...
    ],
    BatchEvaluation,
]:
    try:
        shard = (
            runtime.stage5_v1
            ._require_real_directory(
                Path(
                    shard_path
                ),
                label=(
                    f"{selection.batch_id} shard"
                ),
            )
        )

        runtime.stage5_v1._require_exact_inventory(
            shard,
            expected_files={
                SHARD_DECISIONS_NAME,
                SHARD_RECEIPT_NAME,
            },
            label=(
                f"{selection.batch_id} shard"
            ),
        )

        decisions = (
            runtime.stage5_v1
            ._require_regular_file(
                shard
                / SHARD_DECISIONS_NAME,
                label=(
                    f"{selection.batch_id} "
                    "shard decisions"
                ),
            )
            .read_bytes()
        )

        receipt = (
            runtime.stage5_v1
            ._require_regular_file(
                shard
                / SHARD_RECEIPT_NAME,
                label=(
                    f"{selection.batch_id} "
                    "shard receipt"
                ),
            )
            .read_bytes()
        )

    except Exception as exc:
        raise ParallelStage6Error(
            f"{selection.batch_id}: "
            "shard loading failed"
        ) from exc

    try:
        rows = (
            runtime.stage6_v1
            .monthly_chromosome_integrity
            .audit_monthly_chromosome_decisions(
                decisions
            )
        )

        observed_accessions = tuple(
            row[
                "canonical_genbank_assembly_accession"
            ]
            for row in rows
        )

        if (
            observed_accessions
            != selection.accessions
        ):
            _fail(
                f"{selection.batch_id}: "
                "shard membership changed"
            )

        evaluations = tuple(
            runtime.stage6_v1
            .monthly_chromosome_integrity
            ._evaluation_from_row(
                row
            )
            for row in rows
        )

        subpopulation = subset_population(
            runtime,
            selection,
        )

        build = (
            runtime.stage6_v1
            .monthly_chromosome_integrity
            .build_monthly_chromosome_integrity(
                subpopulation,
                evaluations,
            )
        )

        canonical = (
            runtime.stage6_v1
            .monthly_chromosome_integrity
            .serialize_monthly_chromosome_decisions(
                build
            )
        )

        if canonical != decisions:
            _fail(
                f"{selection.batch_id}: "
                "shard decisions are not canonical"
            )

    except ParallelStage6Error:
        raise
    except Exception as exc:
        raise ParallelStage6Error(
            f"{selection.batch_id}: "
            "shard scientific audit failed"
        ) from exc

    provider = _provider_for_selection(
        runtime=runtime,
        stage1_root=stage1_root,
        selection=selection,
        source_production_commit=(
            source_production_commit
        ),
        completion_execution_commit=(
            completion_execution_commit
        ),
        cache_execution_commit=(
            cache_execution_commit
        ),
    )

    provider_class = (
        "fresh-recovery"
        if (
            "sequence-acquisition-recovery"
            in provider.provider_root.parts
        )
        else "fresh"
    )

    pass_count = int(
        build.status_counts.get(
            runtime.stage6_v1
            .source_chromosome_integrity
            .PASS,
            0,
        )
    )

    excluded_count = int(
        build.status_counts.get(
            runtime.stage6_v1
            .source_chromosome_integrity
            .EXCLUDE,
            0,
        )
    )

    unresolved_count = int(
        build.status_counts.get(
            runtime.stage6_v1
            .source_chromosome_integrity
            .UNRESOLVED,
            0,
        )
    )

    evaluation = BatchEvaluation(
        selection=selection,
        decisions_payload=decisions,
        candidate_count=len(
            selection.accessions
        ),
        triggered_count=(
            build.triggered_candidate_count
        ),
        pass_count=pass_count,
        excluded_count=excluded_count,
        unresolved_count=unresolved_count,
        provider_class=provider_class,
    )

    expected_receipt = build_shard_receipt(
        runtime=runtime,
        evaluation=evaluation,
        source_production_commit=(
            source_production_commit
        ),
        completion_execution_commit=(
            completion_execution_commit
        ),
        cache_execution_commit=(
            cache_execution_commit
        ),
        source_truth_execution_commit=(
            source_truth_execution_commit
        ),
        biosample_execution_commit=(
            biosample_execution_commit
        ),
        chromosome_execution_commit=(
            chromosome_execution_commit
        ),
        work_manifest_sha256=(
            work_manifest_sha256
        ),
    )

    if receipt != expected_receipt:
        _fail(
            f"{selection.batch_id}: "
            "shard receipt differs from "
            "authenticated evidence"
        )

    return (
        evaluations,
        evaluation,
    )


def audit_all_shards(
    *,
    runtime: WorkerRuntime,
    stage1_root: Path,
    shard_root: Path,
    selections: Sequence[
        BatchSelection
    ],
    work_manifest_sha256: str,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    chromosome_execution_commit: str,
) -> tuple[
    tuple[
        object,
        ...
    ],
    tuple[
        BatchEvaluation,
        ...
    ],
]:
    try:
        root = (
            runtime.stage5_v1
            ._require_real_directory(
                Path(
                    shard_root
                ),
                label="Stage 6 shard root",
            )
        )
    except Exception as exc:
        raise ParallelStage6Error(
            "Stage 6 shard root is invalid"
        ) from exc

    expected_names = {
        selection.batch_id
        for selection in selections
    }

    observed_names = {
        path.name
        for path in root.iterdir()
    }

    if observed_names != expected_names:
        missing = sorted(
            expected_names
            - observed_names
        )
        extra = sorted(
            observed_names
            - expected_names
        )

        _fail(
            "Stage 6 shard inventory differs "
            f"missing={missing!r} extra={extra!r}"
        )

    evaluations = []
    batch_results = []

    for selection in selections:
        observed, result = audit_shard(
            runtime=runtime,
            stage1_root=stage1_root,
            shard_path=(
                root
                / selection.batch_id
            ),
            selection=selection,
            work_manifest_sha256=(
                work_manifest_sha256
            ),
            source_production_commit=(
                source_production_commit
            ),
            completion_execution_commit=(
                completion_execution_commit
            ),
            cache_execution_commit=(
                cache_execution_commit
            ),
            source_truth_execution_commit=(
                source_truth_execution_commit
            ),
            biosample_execution_commit=(
                biosample_execution_commit
            ),
            chromosome_execution_commit=(
                chromosome_execution_commit
            ),
        )

        evaluations.extend(
            observed
        )
        batch_results.append(
            result
        )

    evaluations = tuple(
        sorted(
            evaluations,
            key=lambda value:
                value.accession,
        )
    )

    if tuple(
        value.accession
        for value in evaluations
    ) != runtime.population.continue_accessions:
        _fail(
            "merged Stage 6 shard population "
            "differs from authenticated "
            "Stage 5 CONTINUE population"
        )

    return (
        evaluations,
        tuple(
            batch_results
        ),
    )


def shard_tree_identity(
    *,
    shard_root: Path,
    selections: Sequence[
        BatchSelection
    ],
) -> tuple[
    tuple[
        str,
        str,
        str,
    ],
    ...
]:
    root = Path(
        shard_root
    )

    values = []

    for selection in selections:
        shard = (
            root
            / selection.batch_id
        )

        decisions = (
            shard
            / SHARD_DECISIONS_NAME
        )
        receipt = (
            shard
            / SHARD_RECEIPT_NAME
        )

        values.append(
            (
                selection.batch_id,
                _sha256_file(
                    decisions
                ),
                _sha256_file(
                    receipt
                ),
            )
        )

    return tuple(
        values
    )


def aggregate_and_publish(
    *,
    runtime: WorkerRuntime,
    source_repo: Path,
    production_root: Path,
    stage1_root: Path,
    work_manifest_path: Path,
    shard_root: Path,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    chromosome_execution_commit: str,
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
    expected_source_truth_completion_sha256: str,
    expected_biosample_completion_sha256: str,
) -> Mapping[
    str,
    object,
]:
    stage1 = Path(
        stage1_root
    ).resolve()

    work_payload, selections = (
        load_work_manifest(
            path=work_manifest_path,
            runtime=runtime,
        )
    )

    work_sha = hashlib.sha256(
        work_payload
    ).hexdigest()

    (
        evaluations,
        batch_results,
    ) = audit_all_shards(
        runtime=runtime,
        stage1_root=stage1,
        shard_root=shard_root,
        selections=selections,
        work_manifest_sha256=(
            work_sha
        ),
        source_production_commit=(
            source_production_commit
        ),
        completion_execution_commit=(
            completion_execution_commit
        ),
        cache_execution_commit=(
            cache_execution_commit
        ),
        source_truth_execution_commit=(
            source_truth_execution_commit
        ),
        biosample_execution_commit=(
            biosample_execution_commit
        ),
        chromosome_execution_commit=(
            chromosome_execution_commit
        ),
    )

    provider_counts = {
        "fresh":
            sum(
                value.provider_class
                == "fresh"
                for value in batch_results
            ),
        "fresh-recovery":
            sum(
                value.provider_class
                == "fresh-recovery"
                for value in batch_results
            ),
    }

    if (
        runtime.context.release_id
        == "2026.09"
        and provider_counts
        != {
            "fresh": 139,
            "fresh-recovery": 3,
        }
    ):
        _fail(
            "September Stage 6 provider "
            "class accounting changed"
        )

    try:
        build = (
            runtime.stage6_v1
            .monthly_chromosome_integrity
            .build_monthly_chromosome_integrity(
                runtime.population,
                evaluations,
            )
        )

        if (
            build.historical_adjudication_reuse_count
            != 0
        ):
            _fail(
                "monthly production unexpectedly "
                "reused historical adjudication"
            )

        decisions_payload = (
            runtime.stage6_v1
            .monthly_chromosome_integrity
            .serialize_monthly_chromosome_decisions(
                build
            )
        )

        record_payload = (
            runtime.stage6_v1
            .monthly_chromosome_integrity
            .serialize_monthly_chromosome_record(
                build,
                biosample_record_sha256=(
                    hashlib.sha256(
                        runtime
                        .context
                        .record_payload
                    ).hexdigest()
                ),
                biosample_completion_sha256=(
                    runtime
                    .context
                    .completion_sha256
                ),
            )
        )

        runtime.stage6_v1.monthly_chromosome_integrity.audit_monthly_chromosome_decisions(
            decisions_payload
        )

        runtime.stage6_v1.monthly_chromosome_integrity.audit_monthly_chromosome_record(
            record_payload,
            biosample_decisions_payload=(
                runtime
                .context
                .decisions_payload
            ),
            expected_biosample_decisions_sha256=(
                runtime
                .context
                .completion_record[
                    "decisions_sha256"
                ]
            ),
            release_id=(
                runtime.context.release_id
            ),
            source_snapshot_id=(
                runtime.context.source_snapshot_id
            ),
            origin_git_commit=(
                chromosome_execution_commit
            ),
            biosample_record_sha256=(
                hashlib.sha256(
                    runtime
                    .context
                    .record_payload
                ).hexdigest()
            ),
            biosample_completion_sha256=(
                runtime
                .context
                .completion_sha256
            ),
            decisions_payload=(
                decisions_payload
            ),
        )

    except ParallelStage6Error:
        raise
    except Exception as exc:
        raise ParallelStage6Error(
            "global frozen Stage 6 build failed"
        ) from exc

    final = (
        stage1
        / runtime.stage6_v1.STAGE_NAME
    )
    partial = (
        stage1
        / runtime.stage6_v1.PARTIAL_NAME
    )

    forbidden = (
        final,
        partial,
        stage1
        / runtime.stage6_v1.COMPLETION_NAME,
        stage1
        / runtime.stage6_v1.COMPLETION_TEMP_NAME,
        stage1
        / runtime.serial.COMPLETION_NAME,
        stage1
        / runtime.serial.COMPLETION_TEMP_NAME,
    )

    for path in forbidden:
        if os.path.lexists(
            path
        ):
            _fail(
                f"canonical Stage 6 path "
                f"already exists: {path}"
            )

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    runtime.stage5_v1.write_no_clobber(
        partial
        / runtime.stage6_v1.DECISIONS_NAME,
        decisions_payload,
    )

    runtime.stage5_v1.write_no_clobber(
        partial
        / runtime.stage6_v1.RECORD_NAME,
        record_payload,
    )

    runtime.stage5_v1.fsync_directory(
        partial
    )

    initial_stage5_identity = (
        runtime.serial
        .stage5_identity_v2(
            runtime.context
        )
    )

    initial_shards = shard_tree_identity(
        shard_root=shard_root,
        selections=selections,
    )

    def stability_check() -> None:
        observed_runtime = (
            load_worker_runtime(
                repo=(
                    Path(
                        runtime.serial.__file__
                    )
                    .resolve()
                    .parents[2]
                ),
                source_repo=source_repo,
                production_root=(
                    production_root
                ),
                stage1_root=stage1,
                source_production_commit=(
                    source_production_commit
                ),
                completion_execution_commit=(
                    completion_execution_commit
                ),
                cache_execution_commit=(
                    cache_execution_commit
                ),
                source_truth_execution_commit=(
                    source_truth_execution_commit
                ),
                biosample_execution_commit=(
                    biosample_execution_commit
                ),
                chromosome_execution_commit=(
                    chromosome_execution_commit
                ),
                expected_completion_sha256=(
                    expected_completion_sha256
                ),
                expected_catalogue_sha256=(
                    expected_catalogue_sha256
                ),
                expected_source_truth_completion_sha256=(
                    expected_source_truth_completion_sha256
                ),
                expected_biosample_completion_sha256=(
                    expected_biosample_completion_sha256
                ),
            )
        )

        if (
            observed_runtime.serial
            .stage5_identity_v2(
                observed_runtime.context
            )
            != initial_stage5_identity
        ):
            _fail(
                "upstream Stage 5 evidence changed "
                "during Stage 6 publication"
            )

        observed_work = (
            observed_runtime.stage5_v1
            ._require_regular_file(
                Path(
                    work_manifest_path
                ),
                label="Stage 6 work manifest",
            )
            .read_bytes()
        )

        if observed_work != work_payload:
            _fail(
                "Stage 6 work manifest changed "
                "during publication"
            )

        if (
            shard_tree_identity(
                shard_root=shard_root,
                selections=selections,
            )
            != initial_shards
        ):
            _fail(
                "Stage 6 shard evidence changed "
                "during publication"
            )

    def stage_auditor(
        observed_decisions: bytes,
        observed_record: bytes,
    ):
        runtime.stage6_v1.monthly_chromosome_integrity.audit_monthly_chromosome_decisions(
            observed_decisions
        )

        return (
            runtime.stage6_v1
            .monthly_chromosome_integrity
            .audit_monthly_chromosome_record(
                observed_record,
                biosample_decisions_payload=(
                    runtime
                    .context
                    .decisions_payload
                ),
                expected_biosample_decisions_sha256=(
                    runtime
                    .context
                    .completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=(
                    runtime.context.release_id
                ),
                source_snapshot_id=(
                    runtime.context.source_snapshot_id
                ),
                origin_git_commit=(
                    chromosome_execution_commit
                ),
                biosample_record_sha256=(
                    hashlib.sha256(
                        runtime
                        .context
                        .record_payload
                    ).hexdigest()
                ),
                biosample_completion_sha256=(
                    runtime
                    .context
                    .completion_sha256
                ),
                decisions_payload=(
                    observed_decisions
                ),
            )
        )

    runtime.stage6_v1.publish_stage(
        stage1_root=stage1,
        partial=partial,
        final=final,
        expected_decisions=(
            decisions_payload
        ),
        expected_record=(
            record_payload
        ),
        auditor=stage_auditor,
        stability_check=(
            stability_check
        ),
        stage5_execution=(
            runtime.stage5_v1
        ),
    )

    pass_count = int(
        build.status_counts.get(
            runtime.stage6_v1
            .source_chromosome_integrity
            .PASS,
            0,
        )
    )

    excluded_count = int(
        build.status_counts.get(
            runtime.stage6_v1
            .source_chromosome_integrity
            .EXCLUDE,
            0,
        )
    )

    unresolved_count = int(
        build.status_counts.get(
            runtime.stage6_v1
            .source_chromosome_integrity
            .UNRESOLVED,
            0,
        )
    )

    decisions_sha = hashlib.sha256(
        decisions_payload
    ).hexdigest()

    record_sha = hashlib.sha256(
        record_payload
    ).hexdigest()

    completion_kwargs = {
        "release_id":
            runtime.context.release_id,
        "source_snapshot_id":
            runtime.context.source_snapshot_id,
        "biosample_decisions_sha256":
            hashlib.sha256(
                runtime
                .context
                .decisions_payload
            ).hexdigest(),
        "biosample_record_sha256":
            hashlib.sha256(
                runtime
                .context
                .record_payload
            ).hexdigest(),
        "biosample_completion_sha256":
            runtime
            .context
            .completion_sha256,
        "continue_count":
            len(
                runtime
                .population
                .continue_accessions
            ),
        "continue_accessions_sha256":
            runtime
            .population
            .continue_accessions_sha256,
        "decision_count":
            len(
                build.decision_rows
            ),
        "triggered_candidate_count":
            build.triggered_candidate_count,
        "nontriggered_candidate_count":
            build.nontriggered_candidate_count,
        "historical_adjudication_reuse_count":
            build.historical_adjudication_reuse_count,
        "pass_count":
            pass_count,
        "excluded_count":
            excluded_count,
        "unresolved_count":
            unresolved_count,
        "decisions_sha256":
            decisions_sha,
        "record_sha256":
            record_sha,
        "stage5_execution":
            runtime.stage5_v1,
    }

    audit_kwargs = {
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
        "sequence_acquisition_completion_sha256":
            runtime
            .context
            .stage4_context
            .completion_v2_sha256,
        "source_truth_completion_sha256":
            runtime
            .context
            .stage4_context
            .source_truth_completion_sha256,
        **completion_kwargs,
    }

    completion_payload = (
        runtime.serial
        .build_completion_receipt_v2(
            runtime.stage6_v1,
            **audit_kwargs,
        )
    )

    completion_path = (
        runtime.serial
        .publish_completion_v2(
            stage1_root=stage1,
            payload=(
                completion_payload
            ),
            auditor=lambda payload:
                runtime.serial
                .audit_completion_receipt_v2(
                    runtime.stage6_v1,
                    payload,
                    **audit_kwargs,
                ),
            stability_check=(
                stability_check
            ),
            stage5_v1=(
                runtime.stage5_v1
            ),
        )
    )

    return {
        "release_id":
            runtime.context.release_id,
        "decision_count":
            len(
                build.decision_rows
            ),
        "pass_count":
            pass_count,
        "excluded_count":
            excluded_count,
        "unresolved_count":
            unresolved_count,
        "triggered_count":
            build.triggered_candidate_count,
        "provider_fresh_count":
            provider_counts["fresh"],
        "provider_recovery_count":
            provider_counts[
                "fresh-recovery"
            ],
        "decisions_sha256":
            decisions_sha,
        "record_sha256":
            record_sha,
        "completion_path":
            str(
                completion_path
            ),
        "completion_sha256":
            hashlib.sha256(
                completion_payload
            ).hexdigest(),
    }


def _add_common_arguments(
    parser,
) -> None:
    parser.add_argument(
        "--repo",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--source-repo",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--production-root",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--stage1-root",
        required=True,
        type=Path,
    )
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


def _runtime_from_args(
    args,
) -> WorkerRuntime:
    return load_worker_runtime(
        repo=args.repo,
        source_repo=args.source_repo,
        production_root=(
            args.production_root
        ),
        stage1_root=(
            args.stage1_root
        ),
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
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Parallel BacSelect Stage 6-v2 "
            "worker and deterministic aggregator."
        )
    )

    subparsers = (
        parser.add_subparsers(
            dest="command",
            required=True,
        )
    )

    plan = subparsers.add_parser(
        "plan"
    )
    _add_common_arguments(
        plan
    )
    plan.add_argument(
        "--work-manifest",
        required=True,
        type=Path,
    )

    worker = subparsers.add_parser(
        "worker"
    )
    _add_common_arguments(
        worker
    )
    worker.add_argument(
        "--work-manifest",
        required=True,
        type=Path,
    )
    worker.add_argument(
        "--shard-root",
        required=True,
        type=Path,
    )
    worker.add_argument(
        "--task-id",
        required=True,
        type=int,
    )

    aggregate = subparsers.add_parser(
        "aggregate"
    )
    _add_common_arguments(
        aggregate
    )
    aggregate.add_argument(
        "--work-manifest",
        required=True,
        type=Path,
    )
    aggregate.add_argument(
        "--shard-root",
        required=True,
        type=Path,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    runtime = _runtime_from_args(
        args
    )

    if args.command == "plan":
        path, digest = (
            publish_work_manifest(
                path=(
                    args.work_manifest
                ),
                runtime=runtime,
            )
        )

        selections = (
            build_batch_selections(
                runtime
            )
        )

        print(
            "PASS | Stage6-v2 "
            "parallel work manifest"
        )
        print(
            f"batch_count="
            f"{len(selections)}"
        )
        print(
            "candidate_count="
            f"{sum(len(x.accessions) for x in selections)}"
        )
        print(
            f"work_manifest={path}"
        )
        print(
            f"work_manifest_sha256="
            f"{digest}"
        )

        return 0

    work_payload, selections = (
        load_work_manifest(
            path=args.work_manifest,
            runtime=runtime,
        )
    )

    work_sha = hashlib.sha256(
        work_payload
    ).hexdigest()

    if args.command == "worker":
        if (
            args.task_id < 1
            or args.task_id
            > len(
                selections
            )
        ):
            _fail(
                "task_id outside frozen "
                "work-manifest range"
            )

        selection = (
            selections[
                args.task_id - 1
            ]
        )

        evaluation = evaluate_batch(
            runtime=runtime,
            stage1_root=(
                args.stage1_root
            ),
            selection=selection,
            source_production_commit=(
                args.source_production_commit
            ),
            completion_execution_commit=(
                args.completion_execution_commit
            ),
            cache_execution_commit=(
                args.cache_execution_commit
            ),
        )

        receipt = build_shard_receipt(
            runtime=runtime,
            evaluation=evaluation,
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
            work_manifest_sha256=(
                work_sha
            ),
        )

        final = publish_shard(
            shard_root=(
                args.shard_root
            ),
            evaluation=evaluation,
            receipt_payload=receipt,
            stage5_v1=(
                runtime.stage5_v1
            ),
        )

        print(
            "PASS | Stage6-v2 shard complete"
        )
        print(
            f"task_id={args.task_id}"
        )
        print(
            f"batch_id="
            f"{selection.batch_id}"
        )
        print(
            f"candidate_count="
            f"{evaluation.candidate_count}"
        )
        print(
            f"triggered_count="
            f"{evaluation.triggered_count}"
        )
        print(
            f"pass_count="
            f"{evaluation.pass_count}"
        )
        print(
            f"excluded_count="
            f"{evaluation.excluded_count}"
        )
        print(
            f"unresolved_count="
            f"{evaluation.unresolved_count}"
        )
        print(
            f"provider_class="
            f"{evaluation.provider_class}"
        )
        print(
            f"shard_path={final}"
        )

        return 0

    result = aggregate_and_publish(
        runtime=runtime,
        source_repo=(
            args.source_repo
        ),
        production_root=(
            args.production_root
        ),
        stage1_root=(
            args.stage1_root
        ),
        work_manifest_path=(
            args.work_manifest
        ),
        shard_root=(
            args.shard_root
        ),
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
    )

    print(
        "PASS | BacSelect monthly "
        "chromosome integrity v2 complete"
    )

    for key, value in (
        result.items()
    ):
        print(
            f"{key}={value}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
