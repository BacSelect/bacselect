#!/usr/bin/env python3
"""Execute recovery-aware BacSelect monthly Stage 5 BioSample reconciliation."""

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
from typing import Mapping, Sequence


STAGE5_V1_WRAPPER_SHA256 = (
    "0787b77f2e0e734a0ec164fd9c020fd51fd8237355ae48c45e5c225666b9ee95"
)
STAGE5_V1_TEST_SHA256 = (
    "61739b08ca0477e027ed243db23c02329165269a8ea0e82ff9dcaed121d9205f"
)
STAGE4_V2_WRAPPER_SHA256 = (
    "3cb27073570ba351089a7e1b0eb0620d2c1c1e8127f52bca3fa8e197e3d8ca91"
)
STAGE4_V2_TEST_SHA256 = (
    "98fb7d0e9a5f4d11cd847777435b194faac1dc72f81af8b5f4bd4200442adc1d"
)

EXPECTED_MONTHLY_BIOSAMPLE_SHA256 = (
    "af9f769ec03e838bc7322dc16a3daf7e45bab0be5d4db0bb6dfd0ff9c53e5446"
)
EXPECTED_MONTHLY_BIOSAMPLE_TEST_SHA256 = (
    "72691aa31404eb6a2e839f4a2228048dc9013e66ebd5dad332e7c41c3e3ce531"
)
EXPECTED_MONTHLY_SOURCE_TRUTH_SHA256 = (
    "0876620b8516c0d8aa7aa26f5b4567de17170aa5456caf57cee7b6718a4158a7"
)
EXPECTED_CACHE_V2_CORE_SHA256 = (
    "1a7f9c2015c73e0cbada26064ad137fd6468ce5592dd5c518095d8f20d2937ca"
)
EXPECTED_CACHE_V2_EXECUTOR_SHA256 = (
    "87b3b32f260abf26acd49deaa2665991bd77e409d6fac7ded7bdf87b2c15a15c"
)

COMPLETION_NAME = "biosample-reconciliation-completion-v2.json"
COMPLETION_TEMP_NAME = ".biosample-reconciliation-completion-v2.json.tmp"
COMPLETION_SCHEMA = (
    "bacselect-monthly-biosample-reconciliation-completion-v2"
)
COMPLETION_STATUS = "BIOSAMPLE_RECONCILIATION_EXECUTION_COMPLETE"


class MonthlyBioSampleV2ExecutionError(RuntimeError):
    """Raised when recovery-aware Stage 5 execution fails closed."""


@dataclass(frozen=True)
class Stage4ContextV2:
    release_id: str
    source_snapshot_id: str
    metadata_context: object
    cache_execution: object
    completion_v2_payload: bytes
    completion_v2_record: Mapping[str, object]
    completion_v2_sha256: str
    catalogue_payload: bytes
    catalogue_record: Mapping[str, object]
    catalogue_sha256: str
    catalogue_chain: tuple[object, ...]
    catalogue_chain_signature: tuple[tuple[str, str, str], ...]
    catalogue_chain_sha256: str
    entries_by_accession: Mapping[str, Mapping[str, object]]
    provenance_by_sha: Mapping[str, Mapping[str, object]]
    completion_by_batch: Mapping[str, Mapping[str, object]]
    decisions_payload: bytes
    decision_rows: tuple[Mapping[str, str], ...]
    decision_by_accession: Mapping[str, Mapping[str, str]]
    relations_payload: bytes
    record_payload: bytes
    source_truth_completion_payload: bytes
    source_truth_completion_record: Mapping[str, object]
    source_truth_completion_sha256: str


@dataclass(frozen=True)
class MonthlyBioSampleV2ExecutionResult:
    release_id: str
    source_snapshot_id: str
    stage_path: Path
    completion_path: Path
    suitable_count: int
    continue_count: int
    nonrepresentative_count: int
    unresolved_count: int
    decisions_sha256: str
    record_sha256: str
    completion_sha256: str


def _fail(message: str) -> None:
    raise MonthlyBioSampleV2ExecutionError(message)


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

    if (
        not path.is_file()
        or path.is_symlink()
    ):
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


def load_stage5_v1(repo: Path) -> ModuleType:
    return _load_module(
        Path(repo)
        / "validation"
        / "selector-v1"
        / "run_monthly_biosample_reconciliation.py",
        module_name="_bacselect_frozen_stage5_v1",
        expected_sha256=STAGE5_V1_WRAPPER_SHA256,
    )


def load_stage4_v2(repo: Path) -> ModuleType:
    return _load_module(
        Path(repo)
        / "validation"
        / "selector-v1"
        / "run_monthly_source_truth_v2.py",
        module_name="_bacselect_frozen_stage4_v2",
        expected_sha256=STAGE4_V2_WRAPPER_SHA256,
    )


def repository_preflight(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> None:
    root = Path(repo).resolve()

    if (
        not root.is_dir()
        or root.is_symlink()
    ):
        _fail("repository root is not a real directory")

    if _git(root, "rev-parse", "HEAD") != expected_commit:
        _fail("repository HEAD differs from expected commit")

    if _git(root, "status", "--porcelain"):
        _fail("repository is not clean")

    identities = (
        (
            root / "src/bacselect/monthly_biosample_reconciliation.py",
            EXPECTED_MONTHLY_BIOSAMPLE_SHA256,
            "monthly Stage 5 core",
        ),
        (
            root / "tests/test_monthly_biosample_reconciliation.py",
            EXPECTED_MONTHLY_BIOSAMPLE_TEST_SHA256,
            "monthly Stage 5 core tests",
        ),
        (
            root / "src/bacselect/monthly_source_truth.py",
            EXPECTED_MONTHLY_SOURCE_TRUTH_SHA256,
            "audited-catalogue Stage 4 core",
        ),
        (
            root / "src/bacselect/monthly_sequence_cache_catalogue_v2.py",
            EXPECTED_CACHE_V2_CORE_SHA256,
            "cache-v2 core",
        ),
        (
            root
            / "validation/selector-v1/run_monthly_sequence_cache_catalogue_v2.py",
            EXPECTED_CACHE_V2_EXECUTOR_SHA256,
            "cache-v2 executor",
        ),
        (
            root / "validation/selector-v1/run_monthly_source_truth_v2.py",
            STAGE4_V2_WRAPPER_SHA256,
            "Stage 4-v2 executor",
        ),
        (
            root / "tests/test_run_monthly_source_truth_v2.py",
            STAGE4_V2_TEST_SHA256,
            "Stage 4-v2 executor tests",
        ),
        (
            root
            / "validation/selector-v1/run_monthly_biosample_reconciliation.py",
            STAGE5_V1_WRAPPER_SHA256,
            "Stage 5-v1 executor",
        ),
        (
            root / "tests/test_run_monthly_biosample_reconciliation.py",
            STAGE5_V1_TEST_SHA256,
            "Stage 5-v1 executor tests",
        ),
    )

    for path, expected, label in identities:
        if (
            not path.is_file()
            or path.is_symlink()
        ):
            _fail(f"{label} is not a regular file")

        if _sha256_file(path) != expected:
            _fail(f"{label} SHA256 mismatch")

    wrapper = (
        root
        / "validation"
        / "selector-v1"
        / "run_monthly_biosample_reconciliation_v2.py"
    )
    test = (
        root
        / "tests"
        / "test_run_monthly_biosample_reconciliation_v2.py"
    )

    if _sha256_file(wrapper) != expected_wrapper_sha256:
        _fail("Stage 5-v2 executor SHA256 mismatch")

    if _sha256_file(test) != expected_wrapper_test_sha256:
        _fail("Stage 5-v2 executor-test SHA256 mismatch")


def load_stage4_context_v2(
    *,
    repo: Path,
    source_repo: Path,
    production_root: Path,
    stage1_root: Path,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
    expected_source_truth_completion_sha256: str,
    stage5_v1,
    stage4_v2,
) -> Stage4ContextV2:
    root = Path(repo).resolve()
    source_root = Path(source_repo).resolve()
    production = Path(production_root)
    stage1_input = Path(stage1_root)

    if (
        not source_root.is_dir()
        or source_root.is_symlink()
    ):
        _fail("source repository is not a real directory")

    if (
        not stage1_input.is_absolute()
        or not stage1_input.is_dir()
        or stage1_input.is_symlink()
    ):
        _fail("Stage 1 root is not a real absolute directory")

    source_commit = stage4_v2.validate_commit(
        source_production_commit,
        label="source production commit",
    )
    completion_commit = stage4_v2.validate_commit(
        completion_execution_commit,
        label="completion execution commit",
    )
    cache_commit = stage4_v2.validate_commit(
        cache_execution_commit,
        label="cache execution commit",
    )
    stage4_commit = stage4_v2.validate_commit(
        source_truth_execution_commit,
        label="source-truth execution commit",
    )

    expected_completion_sha = stage4_v2.validate_sha256(
        expected_completion_sha256,
        label="expected completion-v2 SHA256",
    )
    expected_catalogue_sha = stage4_v2.validate_sha256(
        expected_catalogue_sha256,
        label="expected cache-v2 SHA256",
    )
    expected_stage4_sha = stage4_v2.validate_sha256(
        expected_source_truth_completion_sha256,
        label="expected source-truth completion-v2 SHA256",
    )

    stage4_v1 = stage4_v2.load_stage4_v1(root)
    cache_v2_execution = stage4_v2.load_cache_v2_execution(root)
    cache_execution = stage4_v1.load_frozen_cache_execution(
        source_root
    )

    if stage4_v2._git(
        source_root,
        "rev-parse",
        "HEAD",
    ) != source_commit:
        _fail("source repository HEAD differs from source production commit")

    if stage4_v2._git(
        source_root,
        "status",
        "--porcelain",
    ):
        _fail("source production repository is not clean")

    try:
        metadata = cache_execution.load_current_metadata_context(
            repo=source_root,
            production_root=production,
            stage1_root=stage1_input,
            execution_commit=source_commit,
        )
    except Exception as exc:
        raise MonthlyBioSampleV2ExecutionError(
            "current metadata re-audit failed"
        ) from exc

    stage1 = metadata.stage1_root.resolve()

    if stage1 != stage1_input.resolve():
        _fail("metadata audit changed Stage 1 root")

    completion_path = stage1 / stage4_v2.COMPLETION_V2_NAME

    completion_payload = completion_path.read_bytes()
    completion_sha = hashlib.sha256(
        completion_payload
    ).hexdigest()

    if completion_sha != expected_completion_sha:
        _fail("completion-v2 SHA256 differs from authorized identity")

    completion_record = (
        stage4_v2.cache_v2
        ._audit_completion_v2_payload_internal(
            completion_payload
        )
    )

    completion_checks = (
        (
            completion_record.get("source_snapshot_id"),
            metadata.source_snapshot_id,
            "source snapshot",
        ),
        (
            completion_record.get("source_snapshot_record_sha256"),
            metadata.source_snapshot_record_sha256,
            "source-snapshot record",
        ),
        (
            completion_record.get("source_production_commit"),
            source_commit,
            "source production commit",
        ),
        (
            completion_record.get("completion_execution_commit"),
            completion_commit,
            "completion execution commit",
        ),
    )

    for observed, expected, label in completion_checks:
        if observed != expected:
            _fail(f"completion-v2 {label} binding changed")

    plan_path = (
        stage1
        / stage4_v1.SEQUENCE_PLAN_DIR
        / stage4_v1.SEQUENCE_PLAN_RECORD_NAME
    )
    targets_path = (
        stage1
        / stage4_v1.SEQUENCE_PLAN_DIR
        / stage4_v1.FRESH_TARGET_NAME
    )

    if stage4_v2.sha256_file(
        plan_path
    ) != completion_record.get(
        "stage2_sequence_plan_record_sha256"
    ):
        _fail("completion-v2 sequence-plan binding changed")

    if stage4_v2.sha256_file(
        targets_path
    ) != completion_record.get(
        "stage2_fresh_target_manifest_sha256"
    ):
        _fail("completion-v2 fresh-target binding changed")

    catalogue_path = stage1 / stage4_v2.CATALOGUE_NAME
    catalogue_payload = catalogue_path.read_bytes()
    catalogue_sha = hashlib.sha256(
        catalogue_payload
    ).hexdigest()

    if catalogue_sha != expected_catalogue_sha:
        _fail("cache-v2 SHA256 differs from authorized identity")

    catalogue_record = (
        stage4_v2.cache_v2
        .audit_sequence_cache_catalogue_v2(
            catalogue_payload
        )
    )

    catalogue_checks = (
        (
            catalogue_record.get("release_id"),
            metadata.release_id,
            "release",
        ),
        (
            catalogue_record.get("source_snapshot_id"),
            metadata.source_snapshot_id,
            "source snapshot",
        ),
        (
            catalogue_record.get("source_production_commit"),
            source_commit,
            "source production commit",
        ),
        (
            catalogue_record.get("completion_execution_commit"),
            completion_commit,
            "completion execution commit",
        ),
        (
            catalogue_record.get("cache_execution_commit"),
            cache_commit,
            "cache execution commit",
        ),
        (
            catalogue_record.get(
                "sequence_acquisition_completion_sha256"
            ),
            completion_sha,
            "completion SHA256",
        ),
    )

    for observed, expected, label in catalogue_checks:
        if observed != expected:
            _fail(f"cache-v2 {label} binding changed")

    chain = cache_v2_execution.discover_catalogue_chain_v2(
        production,
        current_release_id=metadata.release_id,
        include_current=True,
        current_catalogue_path=catalogue_path,
    )
    signature = cache_v2_execution.chain_signature(chain)

    if (
        len(chain) != 1
        or signature
        != (
            (
                metadata.release_id,
                cache_commit,
                catalogue_sha,
            ),
        )
    ):
        _fail(
            "September Stage 5-v2 requires one current GENESIS catalogue"
        )

    if (
        catalogue_record.get("catalogue_mode")
        != stage4_v2.cache_v2.GENESIS
        or catalogue_record.get("carried_forward_entry_count") != 0
        or catalogue_record.get("previous_catalogue_release_id")
        is not None
        or catalogue_record.get("previous_catalogue_sha256")
        is not None
    ):
        _fail("September Stage 5-v2 catalogue history is not GENESIS-only")

    compatibility_catalogue = dict(catalogue_record)
    compatibility_catalogue["origin_git_commit"] = stage4_commit

    stage = (
        stage1
        / stage4_v2.SOURCE_TRUTH_STAGE_NAME
    )

    stage5_v1._require_exact_inventory(
        stage,
        expected_files={
            stage4_v2.DECISIONS_NAME,
            stage4_v2.RELATIONS_NAME,
            stage4_v2.RECORD_NAME,
        },
        label="monthly source-truth stage",
    )

    decisions = (
        stage / stage4_v2.DECISIONS_NAME
    ).read_bytes()
    relations = (
        stage / stage4_v2.RELATIONS_NAME
    ).read_bytes()
    record = (
        stage / stage4_v2.RECORD_NAME
    ).read_bytes()

    try:
        audited_record = (
            stage4_v2._audit_scientific_payloads_v2(
                decisions_payload=decisions,
                relations_payload=relations,
                record_payload=record,
                catalogue_record=compatibility_catalogue,
                catalogue_sha256=catalogue_sha,
                current_metadata=metadata.retained_metadata,
                release_id=metadata.release_id,
                source_snapshot_id=metadata.source_snapshot_id,
                execution_commit=stage4_commit,
                metadata_record_sha256=metadata.metadata_record_sha256,
                metadata_completion_sha256=metadata.metadata_completion_sha256,
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleV2ExecutionError(
            "completed Stage 4-v2 scientific audit failed"
        ) from exc

    decision_rows = tuple(
        stage4_v2.monthly_source_truth
        .audit_monthly_source_truth_decisions(
            decisions
        )
    )
    relation_rows = tuple(
        stage4_v2.monthly_source_truth
        .audit_monthly_source_truth_relations(
            relations
        )
    )

    decisions_sha = hashlib.sha256(
        decisions
    ).hexdigest()
    relations_sha = hashlib.sha256(
        relations
    ).hexdigest()
    record_sha = hashlib.sha256(
        record
    ).hexdigest()

    source_truth_completion_path = (
        stage1 / stage4_v2.COMPLETION_NAME
    )
    source_truth_completion_payload = (
        source_truth_completion_path.read_bytes()
    )
    source_truth_completion_sha = hashlib.sha256(
        source_truth_completion_payload
    ).hexdigest()

    if source_truth_completion_sha != expected_stage4_sha:
        _fail(
            "source-truth completion-v2 SHA256 differs from authorized identity"
        )

    chain_sha = stage4_v2.catalogue_chain_sha256_v2(
        signature
    )

    stage4_completion_kwargs = {
        "release_id":
            metadata.release_id,
        "source_snapshot_id":
            metadata.source_snapshot_id,
        "source_snapshot_record_sha256":
            metadata.source_snapshot_record_sha256,
        "source_production_commit":
            source_commit,
        "completion_execution_commit":
            completion_commit,
        "cache_execution_commit":
            cache_commit,
        "source_truth_execution_commit":
            stage4_commit,
        "metadata_record_sha256":
            metadata.metadata_record_sha256,
        "metadata_completion_sha256":
            metadata.metadata_completion_sha256,
        "sequence_acquisition_completion_sha256":
            completion_sha,
        "catalogue_chain_count":
            len(chain),
        "catalogue_chain_sha256":
            chain_sha,
        "sequence_cache_catalogue_sha256":
            catalogue_sha,
        "sequence_cache_entries_sha256":
            str(catalogue_record["entries_sha256"]),
        "retained_count":
            int(audited_record["retained_count"]),
        "sequence_eligible_count":
            int(audited_record["sequence_eligible_count"]),
        "sequence_ineligible_count":
            int(audited_record["sequence_ineligible_count"]),
        "retained_accessions_sha256":
            str(audited_record["retained_accessions_sha256"]),
        "sequence_eligible_accessions_sha256":
            str(audited_record["sequence_eligible_accessions_sha256"]),
        "sequence_ineligible_accessions_sha256":
            str(audited_record["sequence_ineligible_accessions_sha256"]),
        "decision_count":
            int(audited_record["decision_count"]),
        "relation_count":
            int(audited_record["relation_count"]),
        "decisions_sha256":
            decisions_sha,
        "relations_sha256":
            relations_sha,
        "record_sha256":
            record_sha,
    }

    try:
        source_truth_completion_record = (
            stage4_v2.audit_completion_receipt_v2(
                source_truth_completion_payload,
                **stage4_completion_kwargs,
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleV2ExecutionError(
            "source-truth completion-v2 audit failed"
        ) from exc

    if (
        source_truth_completion_record.get("decisions_sha256")
        != decisions_sha
    ):
        _fail("authenticated Stage 4 decision SHA changed")

    decision_by_accession = {
        row["canonical_genbank_assembly_accession"]:
            row
        for row in decision_rows
    }

    if len(decision_by_accession) != len(decision_rows):
        _fail("duplicate source-truth decision accession")

    return Stage4ContextV2(
        release_id=metadata.release_id,
        source_snapshot_id=metadata.source_snapshot_id,
        metadata_context=metadata,
        cache_execution=cache_execution,
        completion_v2_payload=completion_payload,
        completion_v2_record=completion_record,
        completion_v2_sha256=completion_sha,
        catalogue_payload=catalogue_payload,
        catalogue_record=catalogue_record,
        catalogue_sha256=catalogue_sha,
        catalogue_chain=tuple(chain),
        catalogue_chain_signature=tuple(signature),
        catalogue_chain_sha256=chain_sha,
        entries_by_accession=(
            stage4_v1._catalogue_entries_by_accession(
                catalogue_record
            )
        ),
        provenance_by_sha=(
            stage4_v1._catalogue_provenance_by_sha(
                catalogue_record
            )
        ),
        completion_by_batch=(
            stage4_v2._completion_rows_by_batch(
                completion_record
            )
        ),
        decisions_payload=decisions,
        decision_rows=decision_rows,
        decision_by_accession=decision_by_accession,
        relations_payload=relations,
        record_payload=record,
        source_truth_completion_payload=source_truth_completion_payload,
        source_truth_completion_record=source_truth_completion_record,
        source_truth_completion_sha256=source_truth_completion_sha,
    )


def fingerprint_population_v2(
    *,
    context: Stage4ContextV2,
    stage1_root: Path,
    population,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    stage5_v1,
    stage4_v2,
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    stage4_v1 = stage4_v2.load_stage4_v1(
        Path(__file__).resolve().parents[2]
    )

    provider_cache = {}
    fingerprints = []
    observations = []

    for accession in population.suitable_accessions:
        entry = context.entries_by_accession.get(
            accession
        )

        if entry is None:
            _fail("Stage 5 candidate lacks current catalogue entry")

        provenance_sha = stage4_v1.validate_sha256(
            entry.get("origin_batch_provenance_sha256"),
            label="origin batch-provenance SHA256",
        )
        provenance = context.provenance_by_sha.get(
            provenance_sha
        )

        if provenance is None:
            _fail("Stage 5 candidate provenance is missing")

        if (
            provenance.get("cache_origin_release_id")
            != context.release_id
        ):
            _fail(
                "September Stage 5-v2 encountered historical-origin entry"
            )

        provider = provider_cache.get(
            provenance_sha
        )

        if provider is None:
            batch_id = str(
                provenance.get("batch_id", "")
            )
            completion_batch = (
                context.completion_by_batch.get(
                    batch_id
                )
            )

            if completion_batch is None:
                _fail(
                    "catalogue provenance batch is missing from completion-v2"
                )

            provider = stage4_v2._provider_batch_context_v2(
                stage1_root=Path(stage1_root),
                cache_execution=context.cache_execution,
                provenance=provenance,
                completion_batch=completion_batch,
                release_id=context.release_id,
                source_snapshot_id=context.source_snapshot_id,
                source_production_commit=source_production_commit,
                completion_execution_commit=completion_execution_commit,
                cache_execution_commit=cache_execution_commit,
                completion_sha256=context.completion_v2_sha256,
            )

            provider_cache[
                provenance_sha
            ] = provider

            for path, digest, size in provider.observations:
                observations.append(
                    stage4_v1.InputObservation(
                        path=path,
                        sha256=digest,
                        size_bytes=size,
                    )
                )

        bridge = stage4_v1.validate_candidate_bridge(
            context.cache_execution,
            entry=entry,
            batch=provider.batch,
        )

        if (
            bridge.accession != accession
            or bridge.biosample
            != population.biosample_by_accession[
                accession
            ]
        ):
            _fail(
                "candidate bridge identity differs from Stage 5 population"
            )

        source_row = context.decision_by_accession.get(
            accession
        )

        if (
            source_row is None
            or source_row["source_truth_status"]
            != stage5_v1.source_truth.SUITABLE
        ):
            _fail("Stage 5 candidate is not Stage 4 SUITABLE")

        try:
            (
                candidate,
                components,
                package_manifest,
            ) = stage4_v1._source_truth_objects(
                bridge,
                audit_path=provider.candidate_audit_path,
            )

            verified = stage5_v1.fingerprint_stage2_candidate(
                candidate=candidate,
                component_rows=components,
                package_manifest=package_manifest,
                expected_source_evidence_sha256=(
                    source_row["source_evidence_sha256"]
                ),
                biosample=(
                    population.biosample_by_accession[
                        accession
                    ]
                ),
            )

            resolver = getattr(
                stage4_v1.source_truth_execution,
                "resolve_manifest_path",
                None,
            )

            if not callable(resolver):
                _fail(
                    "frozen source-truth manifest resolver disappeared"
                )

            fasta_path = resolver(
                candidate.batch_dir,
                bridge.fasta_package_path,
            )

            observation = stage4_v1._observe_exact_file(
                fasta_path,
                expected_sha256=bridge.fasta_sha256,
                expected_size_bytes=bridge.fasta_size_bytes,
            )

        except MonthlyBioSampleV2ExecutionError:
            raise
        except Exception as exc:
            raise MonthlyBioSampleV2ExecutionError(
                f"{accession} Stage 5 fingerprint execution failed"
            ) from exc

        if verified.accession != accession:
            _fail("verified fingerprint accession changed")

        fingerprints.append(
            verified
        )
        observations.append(
            observation
        )

    if tuple(
        value.accession
        for value in fingerprints
    ) != population.suitable_accessions:
        _fail(
            "verified fingerprint membership differs from Stage 5 population"
        )

    return (
        tuple(fingerprints),
        tuple(observations),
    )


def build_completion_receipt_v2(
    stage5_v1,
    *,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    sequence_acquisition_completion_sha256: str,
    **kwargs,
) -> bytes:
    base = stage5_v1.build_completion_receipt(
        execution_commit=biosample_execution_commit,
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
            "sequence_acquisition_completion_sha256":
                sequence_acquisition_completion_sha256,
        }
    )

    return stage5_v1._canonical_json_bytes(
        record
    )


def audit_completion_receipt_v2(
    stage5_v1,
    payload: bytes,
    **kwargs,
) -> Mapping[str, object]:
    if not isinstance(payload, bytes):
        raise TypeError(
            "BioSample completion-v2 receipt must be bytes"
        )

    expected = build_completion_receipt_v2(
        stage5_v1,
        **kwargs,
    )

    if payload != expected:
        _fail("BioSample completion-v2 receipt changed")

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
            "BioSample completion-v2 schema/status changed"
        )

    if "execution_commit" in value:
        _fail(
            "BioSample completion-v2 reintroduced ambiguous execution_commit"
        )

    return value


def publish_completion_v2(
    stage5_v1,
    *,
    stage1_root: Path,
    payload: bytes,
    auditor,
    stability_check,
) -> Path:
    final = Path(stage1_root) / COMPLETION_NAME
    temporary = (
        Path(stage1_root)
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(final):
        _fail("BioSample completion-v2 receipt already exists")

    if os.path.lexists(temporary):
        _fail(
            "BioSample completion-v2 temporary artifact already exists"
        )

    stage5_v1.write_no_clobber(
        temporary,
        payload,
    )

    auditor(
        temporary.read_bytes()
    )

    stage5_v1.fsync_directory(
        Path(stage1_root)
    )

    stability_check()

    try:
        os.link(
            temporary,
            final,
            follow_symlinks=False,
        )

        stage5_v1.fsync_directory(
            Path(stage1_root)
        )

        observed = stage5_v1._require_regular_file(
            final,
            label="BioSample completion-v2 receipt",
        ).read_bytes()

        if observed != payload:
            _fail(
                "BioSample completion-v2 readback changed"
            )

        auditor(
            observed
        )
        stability_check()

    except Exception:
        if os.path.lexists(final):
            os.unlink(final)
            stage5_v1.fsync_directory(
                Path(stage1_root)
            )
        raise

    os.unlink(
        temporary
    )
    stage5_v1.fsync_directory(
        Path(stage1_root)
    )

    return final


def execute_monthly_biosample_reconciliation_v2(
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
) -> MonthlyBioSampleV2ExecutionResult:
    root = Path(repo).resolve()
    source_root = Path(source_repo).resolve()
    production = Path(production_root)
    stage1 = Path(stage1_root).resolve()

    stage5_v1 = load_stage5_v1(root)
    stage4_v2 = load_stage4_v2(root)
    stage4_v1 = stage4_v2.load_stage4_v1(
        root
    )
    cache_v2_execution = (
        stage4_v2.load_cache_v2_execution(
            root
        )
    )

    biosample_commit = stage4_v2.validate_commit(
        biosample_execution_commit,
        label="BioSample execution commit",
    )

    context = load_stage4_context_v2(
        repo=root,
        source_repo=source_root,
        production_root=production,
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

    final = stage1 / stage5_v1.STAGE_NAME
    partial = stage1 / stage5_v1.PARTIAL_NAME
    materialization = stage1 / stage5_v1.MATERIALIZATION_NAME

    for path, label in (
        (final, "canonical BioSample stage"),
        (partial, "partial BioSample stage"),
        (materialization, "BioSample materialization"),
        (
            stage1 / stage5_v1.COMPLETION_NAME,
            "legacy BioSample completion receipt",
        ),
        (
            stage1 / stage5_v1.COMPLETION_TEMP_NAME,
            "legacy BioSample completion temporary artifact",
        ),
        (
            stage1 / COMPLETION_NAME,
            "BioSample completion-v2 receipt",
        ),
        (
            stage1 / COMPLETION_TEMP_NAME,
            "BioSample completion-v2 temporary artifact",
        ),
    ):
        if os.path.lexists(path):
            _fail(f"{label} already exists")

    try:
        population = (
            stage5_v1.monthly_biosample_reconciliation
            .build_monthly_biosample_population(
                context.decisions_payload,
                expected_source_truth_decisions_sha256=(
                    context
                    .source_truth_completion_record[
                        "decisions_sha256"
                    ]
                ),
                current_metadata=(
                    context
                    .metadata_context
                    .retained_metadata
                ),
                release_id=context.release_id,
                source_snapshot_id=context.source_snapshot_id,
                origin_git_commit=biosample_commit,
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleV2ExecutionError(
            "pure Stage 5 population construction failed"
        ) from exc

    (
        fingerprints,
        observations,
    ) = fingerprint_population_v2(
        context=context,
        stage1_root=stage1,
        population=population,
        source_production_commit=source_production_commit,
        completion_execution_commit=completion_execution_commit,
        cache_execution_commit=cache_execution_commit,
        stage5_v1=stage5_v1,
        stage4_v2=stage4_v2,
    )

    try:
        build = (
            stage5_v1.monthly_biosample_reconciliation
            .build_monthly_biosample_reconciliation(
                population,
                fingerprints,
            )
        )

        decisions_payload = (
            stage5_v1.monthly_biosample_reconciliation
            .serialize_monthly_biosample_decisions(
                build
            )
        )

        record_payload = (
            stage5_v1.monthly_biosample_reconciliation
            .serialize_monthly_biosample_record(
                build,
                source_truth_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                source_truth_completion_sha256=(
                    context.source_truth_completion_sha256
                ),
            )
        )

        stage5_v1.monthly_biosample_reconciliation.audit_monthly_biosample_decisions(
            decisions_payload
        )

        record = (
            stage5_v1.monthly_biosample_reconciliation
            .audit_monthly_biosample_record(
                record_payload,
                source_truth_decisions_payload=(
                    context.decisions_payload
                ),
                expected_source_truth_decisions_sha256=(
                    context
                    .source_truth_completion_record[
                        "decisions_sha256"
                    ]
                ),
                current_metadata=(
                    context
                    .metadata_context
                    .retained_metadata
                ),
                release_id=context.release_id,
                source_snapshot_id=context.source_snapshot_id,
                origin_git_commit=biosample_commit,
                source_truth_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                source_truth_completion_sha256=(
                    context.source_truth_completion_sha256
                ),
                decisions_payload=decisions_payload,
            )
        )

    except Exception as exc:
        raise MonthlyBioSampleV2ExecutionError(
            "pure monthly Stage 5 contract failed"
        ) from exc

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    stage5_v1.write_no_clobber(
        partial / stage5_v1.DECISIONS_NAME,
        decisions_payload,
    )
    stage5_v1.write_no_clobber(
        partial / stage5_v1.RECORD_NAME,
        record_payload,
    )
    stage5_v1.fsync_directory(
        partial
    )

    metadata_identity = (
        context.cache_execution
        .metadata_context_identity(
            context.metadata_context
        )
    )

    source_truth_stage = (
        stage1
        / stage4_v2.SOURCE_TRUTH_STAGE_NAME
    )

    upstream_payloads = {
        "completion_v2":
            context.completion_v2_payload,
        "catalogue":
            context.catalogue_payload,
        "source_truth_decisions":
            context.decisions_payload,
        "source_truth_relations":
            context.relations_payload,
        "source_truth_record":
            context.record_payload,
        "source_truth_completion":
            context.source_truth_completion_payload,
    }

    def stability_check() -> None:
        observed_metadata = (
            context.cache_execution
            .load_current_metadata_context(
                repo=source_root,
                production_root=production,
                stage1_root=stage1,
                execution_commit=source_production_commit,
            )
        )

        if (
            context.cache_execution
            .metadata_context_identity(
                observed_metadata
            )
            != metadata_identity
        ):
            _fail(
                "metadata identity changed during Stage 5-v2 execution"
            )

        checks = (
            (
                stage1 / stage4_v2.COMPLETION_V2_NAME,
                upstream_payloads["completion_v2"],
                "completion-v2",
            ),
            (
                stage1 / stage4_v2.CATALOGUE_NAME,
                upstream_payloads["catalogue"],
                "cache-v2",
            ),
            (
                source_truth_stage / stage4_v2.DECISIONS_NAME,
                upstream_payloads["source_truth_decisions"],
                "source-truth decisions",
            ),
            (
                source_truth_stage / stage4_v2.RELATIONS_NAME,
                upstream_payloads["source_truth_relations"],
                "source-truth relations",
            ),
            (
                source_truth_stage / stage4_v2.RECORD_NAME,
                upstream_payloads["source_truth_record"],
                "source-truth record",
            ),
            (
                stage1 / stage4_v2.COMPLETION_NAME,
                upstream_payloads["source_truth_completion"],
                "source-truth completion-v2",
            ),
        )

        for path, expected, label in checks:
            if path.read_bytes() != expected:
                _fail(
                    f"{label} changed during Stage 5-v2 execution"
                )

        observed_chain = (
            cache_v2_execution
            .discover_catalogue_chain_v2(
                production,
                current_release_id=context.release_id,
                include_current=True,
                current_catalogue_path=(
                    stage1 / stage4_v2.CATALOGUE_NAME
                ),
            )
        )

        if (
            cache_v2_execution
            .chain_signature(
                observed_chain
            )
            != context.catalogue_chain_signature
        ):
            _fail(
                "cache-v2 chain changed during Stage 5-v2 execution"
            )

        stage4_v1.reverify_observations(
            observations
        )

    def stage_auditor(
        observed_decisions: bytes,
        observed_record: bytes,
    ):
        stage5_v1.monthly_biosample_reconciliation.audit_monthly_biosample_decisions(
            observed_decisions
        )

        return (
            stage5_v1.monthly_biosample_reconciliation
            .audit_monthly_biosample_record(
                observed_record,
                source_truth_decisions_payload=(
                    context.decisions_payload
                ),
                expected_source_truth_decisions_sha256=(
                    context
                    .source_truth_completion_record[
                        "decisions_sha256"
                    ]
                ),
                current_metadata=(
                    context
                    .metadata_context
                    .retained_metadata
                ),
                release_id=context.release_id,
                source_snapshot_id=context.source_snapshot_id,
                origin_git_commit=biosample_commit,
                source_truth_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                source_truth_completion_sha256=(
                    context.source_truth_completion_sha256
                ),
                decisions_payload=observed_decisions,
            )
        )

    stage5_v1.publish_stage(
        stage1_root=stage1,
        partial=partial,
        final=final,
        expected_decisions=decisions_payload,
        expected_record=record_payload,
        auditor=stage_auditor,
        stability_check=stability_check,
    )

    status_counts = record[
        "decision_status_counts"
    ]

    if not isinstance(
        status_counts,
        dict,
    ):
        _fail("Stage 5 status counts changed")

    continue_count = int(
        status_counts.get(
            stage5_v1.BIOSAMPLE_CONTINUE,
            0,
        )
    )
    nonrepresentative_count = int(
        status_counts.get(
            stage5_v1.BIOSAMPLE_NONREPRESENTATIVE,
            0,
        )
    )
    unresolved_count = int(
        status_counts.get(
            stage5_v1.BIOSAMPLE_UNRESOLVED,
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
        "source_snapshot_record_sha256":
            context
            .metadata_context
            .source_snapshot_record_sha256,
        "metadata_record_sha256":
            context
            .metadata_context
            .metadata_record_sha256,
        "metadata_completion_sha256":
            context
            .metadata_context
            .metadata_completion_sha256,
        "catalogue_chain_count":
            len(context.catalogue_chain),
        "catalogue_chain_sha256_value":
            context.catalogue_chain_sha256,
        "sequence_cache_catalogue_sha256":
            context.catalogue_sha256,
        "sequence_cache_entries_sha256":
            context.catalogue_record[
                "entries_sha256"
            ],
        "source_truth_completion_sha256":
            context.source_truth_completion_sha256,
        "source_truth_decisions_sha256":
            hashlib.sha256(
                context.decisions_payload
            ).hexdigest(),
        "source_truth_record_sha256":
            hashlib.sha256(
                context.record_payload
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

    completion_payload = build_completion_receipt_v2(
        stage5_v1,
        source_production_commit=source_production_commit,
        completion_execution_commit=completion_execution_commit,
        cache_execution_commit=cache_execution_commit,
        source_truth_execution_commit=source_truth_execution_commit,
        biosample_execution_commit=biosample_commit,
        sequence_acquisition_completion_sha256=(
            context.completion_v2_sha256
        ),
        **completion_kwargs,
    )

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
            context.completion_v2_sha256,
        **completion_kwargs,
    }

    completion_path = publish_completion_v2(
        stage5_v1,
        stage1_root=stage1,
        payload=completion_payload,
        auditor=lambda payload:
            audit_completion_receipt_v2(
                stage5_v1,
                payload,
                **audit_kwargs,
            ),
        stability_check=stability_check,
    )

    return MonthlyBioSampleV2ExecutionResult(
        release_id=context.release_id,
        source_snapshot_id=context.source_snapshot_id,
        stage_path=final,
        completion_path=completion_path,
        suitable_count=len(
            population.suitable_accessions
        ),
        continue_count=continue_count,
        nonrepresentative_count=nonrepresentative_count,
        unresolved_count=unresolved_count,
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
            "Stage 5 repeated-BioSample reconciliation."
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
        "--authorize-real-execution",
        action="store_true",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.authorize_real_execution:
        raise SystemExit(
            "real monthly Stage 5-v2 execution requires "
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

    result = execute_monthly_biosample_reconciliation_v2(
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
    )

    print(f"release_id={result.release_id}")
    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )
    print(f"stage_path={result.stage_path}")
    print(
        f"suitable_count={result.suitable_count}"
    )
    print(
        f"continue_count={result.continue_count}"
    )
    print(
        "nonrepresentative_count="
        f"{result.nonrepresentative_count}"
    )
    print(
        f"unresolved_count={result.unresolved_count}"
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
