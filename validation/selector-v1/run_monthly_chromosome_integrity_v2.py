#!/usr/bin/env python3
"""Execute recovery-aware BacSelect monthly Stage 6 chromosome integrity."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Mapping


STAGE6_V1_WRAPPER_SHA256 = (
    "da43df5aeeb2b0a7cbf3f404f217d45ba32501634583924ea047e18c6df77538"
)
STAGE6_V1_TEST_SHA256 = (
    "44e0f45acbbf4444e98ccae4a4d4c536ca6f8bc3864dab63af9e52628ed8f295"
)
STAGE5_V2_WRAPPER_SHA256 = (
    "40d0ec3710e55ae7c1141ad857210c5382148f36fa236418aca306be8e3e6d43"
)
STAGE5_V2_TEST_SHA256 = (
    "eeda5e177ad046fe63b1877cb2ad3d3e2aa452c6271a734427ca1b86c73407d1"
)

COMPLETION_NAME = "chromosome-integrity-completion-v2.json"
COMPLETION_TEMP_NAME = ".chromosome-integrity-completion-v2.json.tmp"
COMPLETION_SCHEMA = (
    "bacselect-monthly-chromosome-integrity-completion-v2"
)
COMPLETION_STATUS = "CHROMOSOME_INTEGRITY_EXECUTION_COMPLETE"


class MonthlyChromosomeV2ExecutionError(RuntimeError):
    """Raised when recovery-aware Stage 6 execution fails closed."""


@dataclass(frozen=True)
class Stage5ContextV2:
    release_id: str
    source_snapshot_id: str
    stage4_context: object
    population: object
    build: object
    decisions_payload: bytes
    decision_rows: tuple[Mapping[str, str], ...]
    record_payload: bytes
    completion_payload: bytes
    completion_record: Mapping[str, object]
    completion_sha256: str


@dataclass(frozen=True)
class MonthlyChromosomeV2ExecutionResult:
    release_id: str
    source_snapshot_id: str
    stage_path: Path
    completion_path: Path
    decision_count: int
    pass_count: int
    excluded_count: int
    unresolved_count: int
    triggered_count: int
    decisions_sha256: str
    record_sha256: str
    completion_sha256: str


def _fail(message: str) -> None:
    raise MonthlyChromosomeV2ExecutionError(message)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return result.stdout.strip()


def _load_module(
    path: Path,
    *,
    module_name: str,
    expected_sha256: str,
) -> ModuleType:
    path = Path(path)

    if path.is_symlink() or not path.is_file():
        _fail(f"{module_name} is not a regular file")

    if _sha256_file(path) != expected_sha256:
        _fail(f"{module_name} SHA256 mismatch")

    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None or spec.loader is None:
        _fail(f"cannot import {module_name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def load_stage6_v1(repo: Path) -> ModuleType:
    return _load_module(
        Path(repo)
        / "validation"
        / "selector-v1"
        / "run_monthly_chromosome_integrity.py",
        module_name="_bacselect_frozen_stage6_v1",
        expected_sha256=STAGE6_V1_WRAPPER_SHA256,
    )


def load_stage5_v2(repo: Path) -> ModuleType:
    return _load_module(
        Path(repo)
        / "validation"
        / "selector-v1"
        / "run_monthly_biosample_reconciliation_v2.py",
        module_name="_bacselect_frozen_stage5_v2",
        expected_sha256=STAGE5_V2_WRAPPER_SHA256,
    )


def repository_preflight(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> None:
    root = Path(repo).resolve()

    if root.is_symlink() or not root.is_dir():
        _fail("repository root is not a real directory")

    if _git(root, "rev-parse", "HEAD") != expected_commit:
        _fail("repository HEAD differs from expected commit")

    if _git(root, "status", "--porcelain"):
        _fail("repository is not clean")

    identities = (
        (
            root
            / "validation/selector-v1/run_monthly_chromosome_integrity.py",
            STAGE6_V1_WRAPPER_SHA256,
            "Stage 6-v1 executor",
        ),
        (
            root / "tests/test_run_monthly_chromosome_integrity.py",
            STAGE6_V1_TEST_SHA256,
            "Stage 6-v1 tests",
        ),
        (
            root
            / "validation/selector-v1/run_monthly_biosample_reconciliation_v2.py",
            STAGE5_V2_WRAPPER_SHA256,
            "Stage 5-v2 executor",
        ),
        (
            root / "tests/test_run_monthly_biosample_reconciliation_v2.py",
            STAGE5_V2_TEST_SHA256,
            "Stage 5-v2 tests",
        ),
    )

    for path, expected, label in identities:
        if path.is_symlink() or not path.is_file():
            _fail(f"{label} is not a regular file")

        if _sha256_file(path) != expected:
            _fail(f"{label} SHA256 mismatch")

    stage6_v1 = load_stage6_v1(root)
    stage6_v1.verify_frozen_dependencies(root)

    wrapper = (
        root
        / "validation/selector-v1/run_monthly_chromosome_integrity_v2.py"
    )
    test = (
        root / "tests/test_run_monthly_chromosome_integrity_v2.py"
    )

    if _sha256_file(wrapper) != expected_wrapper_sha256:
        _fail("Stage 6-v2 executor SHA256 mismatch")

    if _sha256_file(test) != expected_wrapper_test_sha256:
        _fail("Stage 6-v2 executor-test SHA256 mismatch")


def load_stage5_context_v2(
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
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
    expected_source_truth_completion_sha256: str,
    expected_biosample_completion_sha256: str,
    stage6_v1,
    stage5_v2,
) -> Stage5ContextV2:
    root = Path(repo).resolve()
    stage1 = Path(stage1_root).resolve()

    stage5_v1 = stage5_v2.load_stage5_v1(root)
    stage4_v2 = stage5_v2.load_stage4_v2(root)

    biosample_commit = stage4_v2.validate_commit(
        biosample_execution_commit,
        label="BioSample execution commit",
    )

    stage4 = stage5_v2.load_stage4_context_v2(
        repo=root,
        source_repo=Path(source_repo),
        production_root=Path(production_root),
        stage1_root=stage1,
        source_production_commit=source_production_commit,
        completion_execution_commit=completion_execution_commit,
        cache_execution_commit=cache_execution_commit,
        source_truth_execution_commit=source_truth_execution_commit,
        expected_completion_sha256=expected_completion_sha256,
        expected_catalogue_sha256=expected_catalogue_sha256,
        expected_source_truth_completion_sha256=(
            expected_source_truth_completion_sha256
        ),
        stage5_v1=stage5_v1,
        stage4_v2=stage4_v2,
    )

    stage = stage1 / stage5_v1.STAGE_NAME

    try:
        stage5_v1._require_real_directory(
            stage,
            label="canonical Stage 5 stage",
        )

        stage5_v1._require_exact_inventory(
            stage,
            expected_files={
                stage5_v1.DECISIONS_NAME,
                stage5_v1.RECORD_NAME,
            },
            label="canonical Stage 5 stage",
        )

        decisions = stage5_v1._require_regular_file(
            stage / stage5_v1.DECISIONS_NAME,
            label="Stage 5 decisions",
        ).read_bytes()

        record = stage5_v1._require_regular_file(
            stage / stage5_v1.RECORD_NAME,
            label="Stage 5 record",
        ).read_bytes()

        completion = stage5_v1._require_regular_file(
            stage1 / stage5_v2.COMPLETION_NAME,
            label="Stage 5 completion-v2",
        ).read_bytes()

    except Exception as exc:
        raise MonthlyChromosomeV2ExecutionError(
            "Stage 5 artifact loading failed"
        ) from exc

    completion_sha = hashlib.sha256(
        completion
    ).hexdigest()

    expected_stage5_sha = stage4_v2.validate_sha256(
        expected_biosample_completion_sha256,
        label="expected BioSample completion-v2 SHA256",
    )

    if completion_sha != expected_stage5_sha:
        _fail(
            "BioSample completion-v2 SHA256 differs from authorized identity"
        )

    try:
        population = (
            stage5_v1.monthly_biosample_reconciliation
            .build_monthly_biosample_population(
                stage4.decisions_payload,
                expected_source_truth_decisions_sha256=(
                    stage4.source_truth_completion_record[
                        "decisions_sha256"
                    ]
                ),
                current_metadata=(
                    stage4.metadata_context.retained_metadata
                ),
                release_id=stage4.release_id,
                source_snapshot_id=stage4.source_snapshot_id,
                origin_git_commit=biosample_commit,
            )
        )

        decision_rows = tuple(
            stage5_v1.monthly_biosample_reconciliation
            .audit_monthly_biosample_decisions(
                decisions
            )
        )

        fingerprints = tuple(
            stage5_v1.VerifiedBioSampleFingerprint(
                accession=(
                    row["canonical_genbank_assembly_accession"]
                ),
                biosample=row["biosample"],
                source_evidence_sha256=(
                    row["source_evidence_sha256"]
                ),
                assembly_fingerprint=(
                    row["assembly_fingerprint"]
                ),
            )
            for row in decision_rows
        )

        if tuple(
            value.accession
            for value in fingerprints
        ) != population.suitable_accessions:
            _fail(
                "Stage 5 decision membership differs from "
                "reconstructed Stage 4 SUITABLE population"
            )

        build = (
            stage5_v1.monthly_biosample_reconciliation
            .build_monthly_biosample_reconciliation(
                population,
                fingerprints,
            )
        )

        expected_decisions = (
            stage5_v1.monthly_biosample_reconciliation
            .serialize_monthly_biosample_decisions(
                build
            )
        )

        if decisions != expected_decisions:
            _fail(
                "Stage 5 decisions differ from frozen Stage 5 contract"
            )

        expected_record = (
            stage5_v1.monthly_biosample_reconciliation
            .serialize_monthly_biosample_record(
                build,
                source_truth_record_sha256=(
                    hashlib.sha256(
                        stage4.record_payload
                    ).hexdigest()
                ),
                source_truth_completion_sha256=(
                    stage4.source_truth_completion_sha256
                ),
            )
        )

        if record != expected_record:
            _fail(
                "Stage 5 record differs from frozen Stage 5 contract"
            )

        stage5_v1.monthly_biosample_reconciliation.audit_monthly_biosample_record(
            record,
            source_truth_decisions_payload=(
                stage4.decisions_payload
            ),
            expected_source_truth_decisions_sha256=(
                stage4.source_truth_completion_record[
                    "decisions_sha256"
                ]
            ),
            current_metadata=(
                stage4.metadata_context.retained_metadata
            ),
            release_id=stage4.release_id,
            source_snapshot_id=stage4.source_snapshot_id,
            origin_git_commit=biosample_commit,
            source_truth_record_sha256=(
                hashlib.sha256(
                    stage4.record_payload
                ).hexdigest()
            ),
            source_truth_completion_sha256=(
                stage4.source_truth_completion_sha256
            ),
            decisions_payload=decisions,
        )

    except MonthlyChromosomeV2ExecutionError:
        raise
    except Exception as exc:
        raise MonthlyChromosomeV2ExecutionError(
            "Stage 5 frozen contract reconstruction failed"
        ) from exc

    continue_count = stage6_v1._count_status(
        decision_rows,
        stage5_v1.BIOSAMPLE_CONTINUE,
    )
    nonrepresentative_count = stage6_v1._count_status(
        decision_rows,
        stage5_v1.BIOSAMPLE_NONREPRESENTATIVE,
    )
    unresolved_count = stage6_v1._count_status(
        decision_rows,
        stage5_v1.BIOSAMPLE_UNRESOLVED,
    )

    decisions_sha = hashlib.sha256(
        decisions
    ).hexdigest()
    record_sha = hashlib.sha256(
        record
    ).hexdigest()

    completion_kwargs = {
        "release_id":
            stage4.release_id,
        "source_snapshot_id":
            stage4.source_snapshot_id,
        "source_snapshot_record_sha256":
            stage4.metadata_context.source_snapshot_record_sha256,
        "metadata_record_sha256":
            stage4.metadata_context.metadata_record_sha256,
        "metadata_completion_sha256":
            stage4.metadata_context.metadata_completion_sha256,
        "catalogue_chain_count":
            len(stage4.catalogue_chain),
        "catalogue_chain_sha256_value":
            stage4.catalogue_chain_sha256,
        "sequence_cache_catalogue_sha256":
            stage4.catalogue_sha256,
        "sequence_cache_entries_sha256":
            stage4.catalogue_record["entries_sha256"],
        "source_truth_completion_sha256":
            stage4.source_truth_completion_sha256,
        "source_truth_decisions_sha256":
            hashlib.sha256(
                stage4.decisions_payload
            ).hexdigest(),
        "source_truth_record_sha256":
            hashlib.sha256(
                stage4.record_payload
            ).hexdigest(),
        "suitable_count":
            len(population.suitable_accessions),
        "suitable_accessions_sha256":
            population.suitable_accessions_sha256,
        "decision_count":
            len(build.decision_rows),
        "continue_count":
            continue_count,
        "nonrepresentative_count":
            nonrepresentative_count,
        "unresolved_count":
            unresolved_count,
        "group_count":
            build.group_count,
        "singleton_group_count":
            build.singleton_group_count,
        "repeated_group_count":
            build.repeated_group_count,
        "identical_repeated_group_count":
            build.identical_repeated_group_count,
        "differing_repeated_group_count":
            build.differing_repeated_group_count,
        "decisions_sha256":
            decisions_sha,
        "record_sha256":
            record_sha,
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
            biosample_commit,
        "sequence_acquisition_completion_sha256":
            stage4.completion_v2_sha256,
        **completion_kwargs,
    }

    try:
        completion_record = (
            stage5_v2.audit_completion_receipt_v2(
                stage5_v1,
                completion,
                **audit_kwargs,
            )
        )
    except Exception as exc:
        raise MonthlyChromosomeV2ExecutionError(
            "Stage 5 completion-v2 authentication failed"
        ) from exc

    if completion_record["decisions_sha256"] != decisions_sha:
        _fail("authenticated Stage 5 decision SHA changed")

    return Stage5ContextV2(
        release_id=stage4.release_id,
        source_snapshot_id=stage4.source_snapshot_id,
        stage4_context=stage4,
        population=population,
        build=build,
        decisions_payload=decisions,
        decision_rows=decision_rows,
        record_payload=record,
        completion_payload=completion,
        completion_record=completion_record,
        completion_sha256=completion_sha,
    )


def stage5_identity_v2(
    context: Stage5ContextV2,
) -> tuple[object, ...]:
    stage4 = context.stage4_context

    return (
        stage4.release_id,
        stage4.source_snapshot_id,
        stage4.completion_v2_sha256,
        stage4.catalogue_sha256,
        stage4.catalogue_chain_signature,
        stage4.source_truth_completion_sha256,
        hashlib.sha256(
            stage4.decisions_payload
        ).hexdigest(),
        hashlib.sha256(
            stage4.record_payload
        ).hexdigest(),
        hashlib.sha256(
            context.decisions_payload
        ).hexdigest(),
        hashlib.sha256(
            context.record_payload
        ).hexdigest(),
        context.completion_sha256,
    )


def evaluate_population_v2(
    *,
    repo: Path,
    context: Stage5ContextV2,
    stage1_root: Path,
    population,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    stage6_v1,
    stage5_v2,
):
    root = Path(repo).resolve()
    stage1 = Path(stage1_root).resolve()

    stage5_v1 = stage5_v2.load_stage5_v1(root)
    stage4_v2 = stage5_v2.load_stage4_v2(root)
    stage4_v1 = stage4_v2.load_stage4_v1(root)

    stage4 = context.stage4_context

    evaluations = []
    package_observations = []
    provider_observations = []

    provider_cache = {}

    for accession in population.continue_accessions:
        entry = stage4.entries_by_accession.get(
            accession
        )

        if entry is None:
            _fail(
                "Stage 6 candidate lacks current catalogue entry"
            )

        provenance_sha = stage4_v1.validate_sha256(
            entry.get(
                "origin_batch_provenance_sha256"
            ),
            label="origin batch-provenance SHA256",
        )

        provenance = stage4.provenance_by_sha.get(
            provenance_sha
        )

        if provenance is None:
            _fail("Stage 6 candidate provenance is missing")

        if (
            provenance.get("cache_origin_release_id")
            != context.release_id
        ):
            _fail(
                "September Stage 6-v2 encountered historical-origin entry"
            )

        provider = provider_cache.get(
            provenance_sha
        )

        if provider is None:
            batch_id = str(
                provenance.get("batch_id", "")
            )

            completion_batch = (
                stage4.completion_by_batch.get(
                    batch_id
                )
            )

            if completion_batch is None:
                _fail(
                    "catalogue provenance batch is missing from completion-v2"
                )

            provider = (
                stage4_v2._provider_batch_context_v2(
                    stage1_root=stage1,
                    cache_execution=stage4.cache_execution,
                    provenance=provenance,
                    completion_batch=completion_batch,
                    release_id=context.release_id,
                    source_snapshot_id=context.source_snapshot_id,
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

            provider_cache[
                provenance_sha
            ] = provider

            for path, digest, size in provider.observations:
                provider_observations.append(
                    stage4_v1.InputObservation(
                        path=path,
                        sha256=digest,
                        size_bytes=size,
                    )
                )

        try:
            bridge = stage4_v1.validate_candidate_bridge(
                stage4.cache_execution,
                entry=entry,
                batch=provider.batch,
            )
        except Exception as exc:
            raise MonthlyChromosomeV2ExecutionError(
                f"{accession} candidate bridge audit failed"
            ) from exc

        if bridge.accession != accession:
            _fail("candidate bridge accession changed")

        expected_source_sha = (
            population
            .source_evidence_sha256_by_accession[
                accession
            ]
        )

        source_row = (
            stage4.decision_by_accession.get(
                accession
            )
        )

        if (
            source_row is None
            or source_row["source_truth_status"]
            != stage5_v1.source_truth.SUITABLE
            or source_row["source_evidence_sha256"]
            != expected_source_sha
        ):
            _fail(
                "Stage 6 candidate differs from "
                "authenticated Stage 4 source truth"
            )

        try:
            current_files = (
                stage6_v1.observe_current_package(
                    batch_dir=(
                        provider.provider_root
                    ),
                    bridge=bridge,
                    stage5_execution=stage5_v1,
                )
            )

            package_observations.extend(
                current_files
            )

            (
                candidate,
                components,
                package_manifest,
            ) = stage4_v1._source_truth_objects(
                bridge,
                audit_path=(
                    provider.candidate_audit_path
                ),
            )

            evaluated = (
                stage6_v1
                .source_chromosome_integrity_execution
                .evaluate_stage3_candidate(
                    candidate=candidate,
                    component_rows=components,
                    package_manifest=package_manifest,
                    expected_source_evidence_sha256=(
                        expected_source_sha
                    ),
                    historical_provider=(
                        stage6_v1.monthly_historical_provider
                    ),
                )
            )

        except MonthlyChromosomeV2ExecutionError:
            raise
        except Exception as exc:
            raise MonthlyChromosomeV2ExecutionError(
                f"{accession} frozen chromosome evaluation failed"
            ) from exc

        if (
            evaluated.accession != accession
            or evaluated.source_evidence_sha256
            != expected_source_sha
        ):
            _fail(
                "frozen chromosome evaluation identity changed"
            )

        evaluations.append(
            evaluated
        )

    if tuple(
        value.accession
        for value in evaluations
    ) != population.continue_accessions:
        _fail(
            "chromosome evaluation population differs "
            "from Stage 5 CONTINUE population"
        )

    return (
        tuple(evaluations),
        tuple(package_observations),
        tuple(provider_observations),
        len(provider_cache),
    )


def build_completion_receipt_v2(
    stage6_v1,
    *,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    chromosome_execution_commit: str,
    sequence_acquisition_completion_sha256: str,
    source_truth_completion_sha256: str,
    **kwargs,
) -> bytes:
    base = stage6_v1.build_completion_receipt(
        execution_commit=chromosome_execution_commit,
        **kwargs,
    )

    record = json.loads(
        base.decode("ascii")
    )

    record.pop(
        "execution_commit",
        None,
    )

    record.update(
        {
            "schema_version":
                COMPLETION_SCHEMA,
            "status":
                COMPLETION_STATUS,
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
                sequence_acquisition_completion_sha256,
            "source_truth_completion_sha256":
                source_truth_completion_sha256,
        }
    )

    return stage6_v1._canonical_json(
        record
    )


def audit_completion_receipt_v2(
    stage6_v1,
    payload: bytes,
    **kwargs,
) -> Mapping[str, object]:
    if not isinstance(payload, bytes):
        raise TypeError(
            "chromosome completion-v2 receipt must be bytes"
        )

    expected = build_completion_receipt_v2(
        stage6_v1,
        **kwargs,
    )

    if payload != expected:
        _fail("chromosome completion-v2 receipt changed")

    value = json.loads(
        payload.decode("ascii")
    )

    if (
        value.get("schema_version")
        != COMPLETION_SCHEMA
        or value.get("status")
        != COMPLETION_STATUS
    ):
        _fail(
            "chromosome completion-v2 schema/status changed"
        )

    if "execution_commit" in value:
        _fail(
            "chromosome completion-v2 reintroduced "
            "ambiguous execution_commit"
        )

    return value


def publish_completion_v2(
    *,
    stage1_root: Path,
    payload: bytes,
    auditor,
    stability_check,
    stage5_v1,
) -> Path:
    root = Path(stage1_root)

    final = root / COMPLETION_NAME
    temporary = root / COMPLETION_TEMP_NAME

    if os.path.lexists(final):
        _fail(
            "chromosome completion-v2 receipt already exists"
        )

    if os.path.lexists(temporary):
        _fail(
            "chromosome completion-v2 temporary artifact already exists"
        )

    stage5_v1.write_no_clobber(
        temporary,
        payload,
    )

    auditor(
        temporary.read_bytes()
    )

    stage5_v1.fsync_directory(
        root
    )

    stability_check()

    try:
        os.link(
            temporary,
            final,
            follow_symlinks=False,
        )

        stage5_v1.fsync_directory(
            root
        )

        observed = stage5_v1._require_regular_file(
            final,
            label="chromosome completion-v2 receipt",
        ).read_bytes()

        if observed != payload:
            _fail(
                "chromosome completion-v2 readback changed"
            )

        auditor(
            observed
        )

        stability_check()

    except Exception:
        if os.path.lexists(final):
            os.unlink(final)
            stage5_v1.fsync_directory(
                root
            )

        raise

    os.unlink(
        temporary
    )

    stage5_v1.fsync_directory(
        root
    )

    return final


def execute_monthly_chromosome_integrity_v2(
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
) -> MonthlyChromosomeV2ExecutionResult:
    root = Path(repo).resolve()
    stage1 = Path(stage1_root).resolve()

    stage6_v1 = load_stage6_v1(
        root
    )
    stage5_v2 = load_stage5_v2(
        root
    )
    stage5_v1 = stage5_v2.load_stage5_v1(
        root
    )
    stage4_v2 = stage5_v2.load_stage4_v2(
        root
    )
    stage4_v1 = stage4_v2.load_stage4_v1(
        root
    )

    chromosome_commit = stage4_v2.validate_commit(
        chromosome_execution_commit,
        label="chromosome execution commit",
    )

    context = load_stage5_context_v2(
        repo=root,
        source_repo=Path(source_repo),
        production_root=Path(production_root),
        stage1_root=stage1,
        source_production_commit=source_production_commit,
        completion_execution_commit=completion_execution_commit,
        cache_execution_commit=cache_execution_commit,
        source_truth_execution_commit=source_truth_execution_commit,
        biosample_execution_commit=biosample_execution_commit,
        expected_completion_sha256=expected_completion_sha256,
        expected_catalogue_sha256=expected_catalogue_sha256,
        expected_source_truth_completion_sha256=(
            expected_source_truth_completion_sha256
        ),
        expected_biosample_completion_sha256=(
            expected_biosample_completion_sha256
        ),
        stage6_v1=stage6_v1,
        stage5_v2=stage5_v2,
    )

    final = stage1 / stage6_v1.STAGE_NAME
    partial = stage1 / stage6_v1.PARTIAL_NAME
    materialization = (
        stage1 / stage6_v1.MATERIALIZATION_NAME
    )

    for path, label in (
        (
            final,
            "canonical chromosome stage",
        ),
        (
            partial,
            "partial chromosome stage",
        ),
        (
            materialization,
            "chromosome materialization",
        ),
        (
            stage1 / stage6_v1.COMPLETION_NAME,
            "legacy chromosome completion",
        ),
        (
            stage1 / stage6_v1.COMPLETION_TEMP_NAME,
            "legacy chromosome completion temporary artifact",
        ),
        (
            stage1 / COMPLETION_NAME,
            "chromosome completion-v2",
        ),
        (
            stage1 / COMPLETION_TEMP_NAME,
            "chromosome completion-v2 temporary artifact",
        ),
    ):
        if os.path.lexists(path):
            _fail(f"{label} already exists")

    try:
        population = (
            stage6_v1.monthly_chromosome_integrity
            .build_monthly_chromosome_population(
                context.decisions_payload,
                expected_biosample_decisions_sha256=(
                    context.completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=context.release_id,
                source_snapshot_id=context.source_snapshot_id,
                origin_git_commit=chromosome_commit,
            )
        )
    except Exception as exc:
        raise MonthlyChromosomeV2ExecutionError(
            "pure Stage 6 population construction failed"
        ) from exc

    (
        evaluations,
        package_observations,
        provider_observations,
        provider_count,
    ) = evaluate_population_v2(
        repo=root,
        context=context,
        stage1_root=stage1,
        population=population,
        source_production_commit=source_production_commit,
        completion_execution_commit=completion_execution_commit,
        cache_execution_commit=cache_execution_commit,
        stage6_v1=stage6_v1,
        stage5_v2=stage5_v2,
    )

    if provider_count != 142:
        _fail(
            "September Stage 6-v2 provider count changed"
        )

    try:
        build = (
            stage6_v1.monthly_chromosome_integrity
            .build_monthly_chromosome_integrity(
                population,
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
            stage6_v1.monthly_chromosome_integrity
            .serialize_monthly_chromosome_decisions(
                build
            )
        )

        record_payload = (
            stage6_v1.monthly_chromosome_integrity
            .serialize_monthly_chromosome_record(
                build,
                biosample_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                biosample_completion_sha256=(
                    context.completion_sha256
                ),
            )
        )

        stage6_v1.monthly_chromosome_integrity.audit_monthly_chromosome_decisions(
            decisions_payload
        )

        record = (
            stage6_v1.monthly_chromosome_integrity
            .audit_monthly_chromosome_record(
                record_payload,
                biosample_decisions_payload=(
                    context.decisions_payload
                ),
                expected_biosample_decisions_sha256=(
                    context.completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=context.release_id,
                source_snapshot_id=context.source_snapshot_id,
                origin_git_commit=chromosome_commit,
                biosample_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                biosample_completion_sha256=(
                    context.completion_sha256
                ),
                decisions_payload=decisions_payload,
            )
        )

    except MonthlyChromosomeV2ExecutionError:
        raise
    except Exception as exc:
        raise MonthlyChromosomeV2ExecutionError(
            "pure monthly Stage 6 contract failed"
        ) from exc

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    stage5_v1.write_no_clobber(
        partial / stage6_v1.DECISIONS_NAME,
        decisions_payload,
    )
    stage5_v1.write_no_clobber(
        partial / stage6_v1.RECORD_NAME,
        record_payload,
    )
    stage5_v1.fsync_directory(
        partial
    )

    initial_identity = stage5_identity_v2(
        context
    )

    def stability_check() -> None:
        observed = load_stage5_context_v2(
            repo=root,
            source_repo=Path(source_repo),
            production_root=Path(production_root),
            stage1_root=stage1,
            source_production_commit=source_production_commit,
            completion_execution_commit=completion_execution_commit,
            cache_execution_commit=cache_execution_commit,
            source_truth_execution_commit=source_truth_execution_commit,
            biosample_execution_commit=biosample_execution_commit,
            expected_completion_sha256=expected_completion_sha256,
            expected_catalogue_sha256=expected_catalogue_sha256,
            expected_source_truth_completion_sha256=(
                expected_source_truth_completion_sha256
            ),
            expected_biosample_completion_sha256=(
                expected_biosample_completion_sha256
            ),
            stage6_v1=stage6_v1,
            stage5_v2=stage5_v2,
        )

        if (
            stage5_identity_v2(observed)
            != initial_identity
        ):
            _fail(
                "Stage 5 evidence changed during "
                "Stage 6-v2 publication"
            )

        stage4_v1.reverify_observations(
            provider_observations
        )

        stage6_v1.verify_package_observations(
            stage5_execution=stage5_v1,
            stage4_execution=stage4_v1,
            cache_execution=(
                context.stage4_context.cache_execution
            ),
            current_completion_context=None,
            execution_commit=source_production_commit,
            authoritative_root=stage1,
            local_observations=package_observations,
            authoritative_observations=(),
            current_batch_observations=(),
            prior_batch_observations=(),
        )

    def stage_auditor(
        observed_decisions: bytes,
        observed_record: bytes,
    ):
        stage6_v1.monthly_chromosome_integrity.audit_monthly_chromosome_decisions(
            observed_decisions
        )

        return (
            stage6_v1.monthly_chromosome_integrity
            .audit_monthly_chromosome_record(
                observed_record,
                biosample_decisions_payload=(
                    context.decisions_payload
                ),
                expected_biosample_decisions_sha256=(
                    context.completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=context.release_id,
                source_snapshot_id=context.source_snapshot_id,
                origin_git_commit=chromosome_commit,
                biosample_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                biosample_completion_sha256=(
                    context.completion_sha256
                ),
                decisions_payload=observed_decisions,
            )
        )

    stage6_v1.publish_stage(
        stage1_root=stage1,
        partial=partial,
        final=final,
        expected_decisions=decisions_payload,
        expected_record=record_payload,
        auditor=stage_auditor,
        stability_check=stability_check,
        stage5_execution=stage5_v1,
    )

    pass_count = int(
        build.status_counts.get(
            stage6_v1.source_chromosome_integrity.PASS,
            0,
        )
    )
    excluded_count = int(
        build.status_counts.get(
            stage6_v1.source_chromosome_integrity.EXCLUDE,
            0,
        )
    )
    unresolved_count = int(
        build.status_counts.get(
            stage6_v1.source_chromosome_integrity.UNRESOLVED,
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
            context.release_id,
        "source_snapshot_id":
            context.source_snapshot_id,
        "biosample_decisions_sha256":
            hashlib.sha256(
                context.decisions_payload
            ).hexdigest(),
        "biosample_record_sha256":
            hashlib.sha256(
                context.record_payload
            ).hexdigest(),
        "biosample_completion_sha256":
            context.completion_sha256,
        "continue_count":
            len(population.continue_accessions),
        "continue_accessions_sha256":
            population.continue_accessions_sha256,
        "decision_count":
            len(build.decision_rows),
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
            stage5_v1,
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
            chromosome_commit,
        "sequence_acquisition_completion_sha256":
            context.stage4_context.completion_v2_sha256,
        "source_truth_completion_sha256":
            context.stage4_context.source_truth_completion_sha256,
        **completion_kwargs,
    }

    completion_payload = build_completion_receipt_v2(
        stage6_v1,
        **audit_kwargs,
    )

    completion_path = publish_completion_v2(
        stage1_root=stage1,
        payload=completion_payload,
        auditor=lambda payload:
            audit_completion_receipt_v2(
                stage6_v1,
                payload,
                **audit_kwargs,
            ),
        stability_check=stability_check,
        stage5_v1=stage5_v1,
    )

    return MonthlyChromosomeV2ExecutionResult(
        release_id=context.release_id,
        source_snapshot_id=context.source_snapshot_id,
        stage_path=final,
        completion_path=completion_path,
        decision_count=len(
            build.decision_rows
        ),
        pass_count=pass_count,
        excluded_count=excluded_count,
        unresolved_count=unresolved_count,
        triggered_count=(
            build.triggered_candidate_count
        ),
        decisions_sha256=decisions_sha,
        record_sha256=record_sha,
        completion_sha256=hashlib.sha256(
            completion_payload
        ).hexdigest(),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute recovery-aware BacSelect monthly "
            "Stage 6 chromosome-component integrity."
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
        "--authorize-real-execution",
        action="store_true",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.authorize_real_execution:
        raise SystemExit(
            "real monthly Stage 6-v2 execution requires "
            "--authorize-real-execution"
        )

    repo = Path(__file__).resolve().parents[2]

    repository_preflight(
        repo,
        expected_commit=args.expected_commit,
        expected_wrapper_sha256=(
            args.expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            args.expected_wrapper_test_sha256
        ),
    )

    result = execute_monthly_chromosome_integrity_v2(
        repo=repo,
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
            args.expected_commit
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
    print(f"release_id={result.release_id}")
    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )
    print(
        f"decision_count={result.decision_count}"
    )
    print(f"pass_count={result.pass_count}")
    print(
        f"excluded_count={result.excluded_count}"
    )
    print(
        f"unresolved_count={result.unresolved_count}"
    )
    print(
        f"triggered_count={result.triggered_count}"
    )
    print(
        f"decisions_sha256={result.decisions_sha256}"
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
