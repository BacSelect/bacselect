#!/usr/bin/env python3
"""Run frozen BacSelect selector-v1 Stage 3 chromosome-integrity execution.

Importing this module performs no production evidence access.

The wrapper loads the exact frozen Stage 2 orchestration layer, derives the
Stage 3 input only from Stage 2 CONTINUE decisions, reconstructs the exact
Stage 1 package population, writes predecision provenance, and only then calls
the frozen Stage 3 execution helper.

Historical Project Finch adjudication rows are loaded lazily and only when a
currently evaluated historical-package candidate triggers chromosome-integrity
review. Identity-bearing Stage 3 decisions remain scratch-only.
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
import sys
from types import ModuleType
from typing import Mapping, Sequence
from bacselect import source_chromosome_integrity
from bacselect.source_chromosome_integrity_execution import Stage3CandidateEvaluation, Stage3ExecutionError, evaluate_stage3_candidate
from bacselect.source_post_sequence_eligibility import BIOSAMPLE_CONTINUE, BIOSAMPLE_NONREPRESENTATIVE, BIOSAMPLE_UNRESOLVED
from bacselect.source_truth_execution import accession_membership_sha256, load_component_index, load_package_manifest
STAGE2_WRAPPER_RELATIVE = Path('validation/selector-v1/run_repeated_biosample_execution.py')
STAGE2_WRAPPER_TEST_RELATIVE = Path('tests/test_run_repeated_biosample_execution.py')
STAGE2_COMPLETION_RELATIVE = Path('validation/selector-v1/stage2-repeated-biosample-completion-evidence.json')
STAGE3_METHOD_RELATIVE = Path('validation/selector-v1/prospective-stage3-chromosome-integrity-execution.md')
STAGE3_EXECUTION_RELATIVE = Path('src/bacselect/source_chromosome_integrity_execution.py')
STAGE3_EXECUTION_TEST_RELATIVE = Path('tests/test_source_chromosome_integrity_execution.py')
CHROMOSOME_PRIMITIVE_RELATIVE = Path('src/bacselect/source_chromosome_integrity.py')
CHROMOSOME_PRIMITIVE_TEST_RELATIVE = Path('tests/test_source_chromosome_integrity.py')
CHROMOSOME_CLARIFICATION_RELATIVE = Path('validation/selector-v1/prospective-chromosome-integrity-implementation-clarification.md')
SOURCE_TRUTH_EXECUTION_RELATIVE = Path('src/bacselect/source_truth_execution.py')
STAGE3_WRAPPER_RELATIVE = Path('validation/selector-v1/run_chromosome_integrity_execution.py')
EXPECTED_STAGE2_WRAPPER_SHA256 = '5e5f51891e5348e62bc53dfacc28f57216f2e0f38ef69d3ce686121ed6aff355'
EXPECTED_STAGE2_WRAPPER_TEST_SHA256 = '36f406c766ade6485a4bd3ae73da0f717996e000e2a53a0b5bb794570a89bf60'
EXPECTED_STAGE2_COMPLETION_SHA256 = 'd00801b1833c6c3cdee44a8c981d9eb1fc900f6becabc6d59e996877462d76a6'
EXPECTED_STAGE3_METHOD_SHA256 = '74b702ea899d47534d9de7ff4e968ad08f2564873f1e1ced77e869f2d366765c'
EXPECTED_STAGE3_EXECUTION_SHA256 = '187816b76ae804ad2e682e036a5fb76528ac1762d6535062a566edd2fe6e4b9c'
EXPECTED_STAGE3_EXECUTION_TEST_SHA256 = '2bc2b83a768597c47da8a35cf1f38f5edcf7df118886d0de2c70c5861f305a1d'
EXPECTED_CHROMOSOME_PRIMITIVE_SHA256 = '04f1b580ec9480a20f3679b7eb996da08a074c48ff246549df2e0ed20b97b9c0'
EXPECTED_CHROMOSOME_PRIMITIVE_TEST_SHA256 = '94d4eb099ec3812a40fdd11780f82fb65042203bae425ab14e4ec5b184971697'
EXPECTED_CHROMOSOME_CLARIFICATION_SHA256 = 'c13114780c6788f4b9541d6428edf1d2e0827ff3797541b848ec1570a57ac30b'
EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256 = '83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92'
EXPECTED_STAGE2_EXECUTION_COMMIT = '38b49a677fa9e6e6832816392a788ea16905c6b0'
EXPECTED_STAGE2_DECISIONS_SHA256 = '3613195996b8d8d1a5d6cbb23976a5418d97666054aa8ef33601b5ac31a7979a'
PROJECT_FINCH_ADJUDICATION_COMMIT = '24c75483c8fa6d1bcbaa9e32fe6c4c85efae0d97'
EXPECTED_HISTORICAL_ADJUDICATION_SHA256 = 'def13131598e351d06c943f8a8e614e49b2c0b4bc55210ac7c9efd20f1f58828'
EXPECTED_STAGE1_TOTAL = 68480
EXPECTED_STAGE2_TOTAL = 68359
EXPECTED_STAGE3_TOTAL = 68278
EXPECTED_STAGE2_STATUS_COUNTS = {BIOSAMPLE_CONTINUE: 68278, BIOSAMPLE_NONREPRESENTATIVE: 6, BIOSAMPLE_UNRESOLVED: 75}
FROZEN_REPO_FILES = {STAGE2_WRAPPER_RELATIVE: EXPECTED_STAGE2_WRAPPER_SHA256, STAGE2_WRAPPER_TEST_RELATIVE: EXPECTED_STAGE2_WRAPPER_TEST_SHA256, STAGE2_COMPLETION_RELATIVE: EXPECTED_STAGE2_COMPLETION_SHA256, STAGE3_METHOD_RELATIVE: EXPECTED_STAGE3_METHOD_SHA256, STAGE3_EXECUTION_RELATIVE: EXPECTED_STAGE3_EXECUTION_SHA256, STAGE3_EXECUTION_TEST_RELATIVE: EXPECTED_STAGE3_EXECUTION_TEST_SHA256, CHROMOSOME_PRIMITIVE_RELATIVE: EXPECTED_CHROMOSOME_PRIMITIVE_SHA256, CHROMOSOME_PRIMITIVE_TEST_RELATIVE: EXPECTED_CHROMOSOME_PRIMITIVE_TEST_SHA256, CHROMOSOME_CLARIFICATION_RELATIVE: EXPECTED_CHROMOSOME_CLARIFICATION_SHA256, SOURCE_TRUTH_EXECUTION_RELATIVE: EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256}
HISTORICAL_ADJUDICATION_FIELDS = ('review_order', 'canonical_genbank_assembly_accession', 'outcome', 'adjudication_reason')
STAGE3_DECISION_FIELDS = ('canonical_genbank_assembly_accession', 'source_evidence_sha256', 'stage2_status', 'chromosome_component_count', 'closure_supported_chromosome_count', 'closure_unsupported_chromosome_count', 'chromosome_integrity_triggered', 'historical_adjudication_reused', 'stage3_status', 'stage3_reason')
CONTENT_MANIFEST_FIELDS = ('path', 'size_bytes', 'sha256')

class Stage3WrapperError(RuntimeError):
    """Raised when Stage 3 orchestration evidence fails closed."""

@dataclass(frozen=True)
class Stage2DecisionBundle:
    all_accessions: tuple[str, ...]
    continue_source_sha256: Mapping[str, str]
    all_membership_sha256: str
    continue_membership_sha256: str
    status_counts: Mapping[str, int]
    reason_counts: Mapping[str, int]
    decision_artifact_sha256: str

def sha256_file(path: Path) -> str:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise Stage3WrapperError(f'required regular file missing: {path}')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def load_stage2_wrapper(repo: Path) -> ModuleType:
    """Load only the exact frozen Stage 2 orchestration implementation."""
    path = Path(repo).resolve() / STAGE2_WRAPPER_RELATIVE
    if sha256_file(path) != EXPECTED_STAGE2_WRAPPER_SHA256:
        raise Stage3WrapperError('frozen Stage 2 wrapper SHA256 mismatch')
    module_name = '_bacselect_frozen_stage2_repeated_biosample_execution'
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise Stage3WrapperError('cannot load frozen Stage 2 wrapper')
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module

def _nonempty_text(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise Stage3WrapperError(f'{label} must be a string')
    cleaned = value.strip()
    if not cleaned:
        raise Stage3WrapperError(f'{label} must not be empty')
    return cleaned

def load_stage2_completion(repo: Path, *, stage1: ModuleType) -> Mapping[str, object]:
    """Load the exact blinded Stage 2 completion checkpoint."""
    path = Path(repo).resolve() / STAGE2_COMPLETION_RELATIVE
    stage1.require_sha256(path, EXPECTED_STAGE2_COMPLETION_SHA256, 'Stage 2 completion evidence')
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Stage3WrapperError('cannot parse Stage 2 completion evidence') from exc
    if not isinstance(payload, dict):
        raise Stage3WrapperError('Stage 2 completion evidence must be a JSON object')
    if payload.get('schema_version') != 1:
        raise Stage3WrapperError('unexpected Stage 2 completion schema version')
    if payload.get('status') != 'STAGE2_REPEATED_BIOSAMPLE_COMPLETE':
        raise Stage3WrapperError('Stage 2 completion status mismatch')
    if payload.get('execution_git_commit') != EXPECTED_STAGE2_EXECUTION_COMMIT:
        raise Stage3WrapperError('Stage 2 execution commit mismatch')
    if payload.get('decision_row_count') != EXPECTED_STAGE2_TOTAL or payload.get('stage2_input_candidate_count') != EXPECTED_STAGE2_TOTAL or payload.get('continue_count') != EXPECTED_STAGE3_TOTAL:
        raise Stage3WrapperError('Stage 2 completion candidate accounting mismatch')
    if payload.get('status_counts') != EXPECTED_STAGE2_STATUS_COUNTS:
        raise Stage3WrapperError('Stage 2 completion status counts mismatch')
    artifacts = payload.get('artifacts_sha256')
    if not isinstance(artifacts, dict):
        raise Stage3WrapperError('Stage 2 completion artifacts are malformed')
    if artifacts.get('stage2-repeated-biosample-decisions.tsv') != EXPECTED_STAGE2_DECISIONS_SHA256:
        raise Stage3WrapperError('Stage 2 decision artifact identity mismatch')
    stage1.require_lower_sha256(payload.get('stage2_input_membership_sha256'), 'Stage 2 input membership SHA256')
    later_stage = payload.get('later_stage')
    expected_later = {'chromosome_integrity_generated': False, 'complete_universe_generated': False, 'holdout_membership_generated': False, 'selector_outcomes_calculated': False, 'structural_features_calculated': False, 'taxonomy_resolution_generated': False}
    if later_stage != expected_later:
        raise Stage3WrapperError('Stage 2 completion later-stage boundary mismatch')
    return payload

def load_stage2_decisions(path: Path, *, stage1: ModuleType, stage2: ModuleType, completion: Mapping[str, object], expected_sha256: str=EXPECTED_STAGE2_DECISIONS_SHA256, expected_total: int=EXPECTED_STAGE2_TOTAL, expected_continue: int=EXPECTED_STAGE3_TOTAL) -> Stage2DecisionBundle:
    """Load and filter the exact frozen Stage 2 decision table."""
    stage1.require_sha256(path, expected_sha256, 'Stage 2 repeated-BioSample decisions')
    fields, rows = stage1.read_tsv(path)
    stage1.require_exact_fields(fields, stage2.STAGE2_DECISION_FIELDS, 'Stage 2 repeated-BioSample decisions')
    if len(rows) != expected_total:
        raise Stage3WrapperError('Stage 2 decision row count mismatch')
    if completion.get('decision_row_count') != expected_total:
        raise Stage3WrapperError('Stage 2 completion/decision row count mismatch')
    if completion.get('continue_count') != expected_continue:
        raise Stage3WrapperError('Stage 2 completion/CONTINUE count mismatch')
    artifacts = completion.get('artifacts_sha256')
    if not isinstance(artifacts, Mapping) or artifacts.get('stage2-repeated-biosample-decisions.tsv') != expected_sha256:
        raise Stage3WrapperError('Stage 2 completion does not bind decision artifact')
    seen: set[str] = set()
    continue_source: dict[str, str] = {}
    status_counts = Counter()
    reason_counts = Counter()
    allowed_statuses = {BIOSAMPLE_CONTINUE, BIOSAMPLE_NONREPRESENTATIVE, BIOSAMPLE_UNRESOLVED}
    for row in rows:
        accession = stage1.require_accession(row['canonical_genbank_assembly_accession'], 'Stage 2 decisions')
        if accession in seen:
            raise Stage3WrapperError('duplicate accession in Stage 2 decisions')
        seen.add(accession)
        biosample = _nonempty_text(row['biosample'], label='Stage 2 BioSample')
        if stage2.BIOSAMPLE_RE.fullmatch(biosample) is None:
            raise Stage3WrapperError('malformed BioSample in Stage 2 decisions')
        source_sha = stage1.require_lower_sha256(row['source_evidence_sha256'], 'Stage 2 source-evidence SHA256')
        stage1.require_lower_sha256(row['assembly_fingerprint'], 'Stage 2 assembly fingerprint')
        status = _nonempty_text(row['stage2_status'], label='Stage 2 status')
        if status not in allowed_statuses:
            raise Stage3WrapperError('unexpected Stage 2 status')
        reason = _nonempty_text(row['stage2_reason'], label='Stage 2 reason')
        status_counts[status] += 1
        reason_counts[reason] += 1
        if status == BIOSAMPLE_CONTINUE:
            continue_source[accession] = source_sha
    if len(continue_source) != expected_continue:
        raise Stage3WrapperError('Stage 3 CONTINUE input count mismatch')
    expected_status_counts = completion.get('status_counts')
    if not isinstance(expected_status_counts, Mapping) or dict(sorted(status_counts.items())) != dict(sorted(expected_status_counts.items())):
        raise Stage3WrapperError('Stage 2 decision status accounting mismatch')
    expected_reason_counts = completion.get('reason_counts')
    if not isinstance(expected_reason_counts, Mapping) or dict(sorted(reason_counts.items())) != dict(sorted(expected_reason_counts.items())):
        raise Stage3WrapperError('Stage 2 decision reason accounting mismatch')
    all_accessions = tuple(sorted(seen))
    all_membership_sha = accession_membership_sha256(all_accessions)
    if all_membership_sha != completion.get('stage2_input_membership_sha256'):
        raise Stage3WrapperError('Stage 2 input membership SHA256 mismatch')
    continue_membership_sha = accession_membership_sha256(continue_source)
    return Stage2DecisionBundle(all_accessions=all_accessions, continue_source_sha256=dict(sorted(continue_source.items())), all_membership_sha256=all_membership_sha, continue_membership_sha256=continue_membership_sha, status_counts=dict(sorted(status_counts.items())), reason_counts=dict(sorted(reason_counts.items())), decision_artifact_sha256=expected_sha256)

def verify_stage3_population_binding(*, bundle, decisions: Stage2DecisionBundle, expected_stage1_total: int=EXPECTED_STAGE1_TOTAL, expected_stage2_total: int=EXPECTED_STAGE2_TOTAL, expected_stage3_total: int=EXPECTED_STAGE3_TOTAL) -> Mapping[str, str]:
    """Require exact Stage 1/Stage 2/Stage 3 population agreement."""
    reconstructed = tuple((candidate.accession for candidate in (*bundle.historical_candidates, *bundle.fresh_candidates)))
    if len(reconstructed) != expected_stage1_total:
        raise Stage3WrapperError('reconstructed Stage 1 candidate count mismatch')
    if len(set(reconstructed)) != len(reconstructed):
        raise Stage3WrapperError('duplicate accession in reconstructed Stage 1 population')
    reconstructed_set = set(reconstructed)
    if accession_membership_sha256(reconstructed_set) != bundle.combined_membership_sha256:
        raise Stage3WrapperError('reconstructed Stage 1 membership SHA256 mismatch')
    if len(decisions.all_accessions) != expected_stage2_total:
        raise Stage3WrapperError('Stage 2 decision membership count mismatch')
    if not set(decisions.all_accessions) <= reconstructed_set:
        raise Stage3WrapperError('Stage 2 decisions are not a subset of reconstructed Stage 1')
    wanted = set(decisions.continue_source_sha256)
    if len(wanted) != expected_stage3_total:
        raise Stage3WrapperError('Stage 3 input membership count mismatch')
    if not wanted <= set(decisions.all_accessions):
        raise Stage3WrapperError('Stage 3 input is not a subset of Stage 2 decisions')
    batch_seen: set[str] = set()
    source_group_by_accession: dict[str, str] = {}
    allowed_source_groups = {'historical', 'fresh', 'fresh-recovery'}
    for batch in bundle.batches:
        if batch.source_group not in allowed_source_groups:
            raise Stage3WrapperError('unexpected Stage 1 package source group')
        for candidate in batch.candidates:
            accession = candidate.accession
            if accession in batch_seen:
                raise Stage3WrapperError('duplicate candidate across Stage 1 batch specifications')
            batch_seen.add(accession)
            if accession in wanted:
                source_group_by_accession[accession] = batch.source_group
    if batch_seen != reconstructed_set:
        raise Stage3WrapperError('Stage 1 batch specifications do not cover reconstructed population')
    if set(source_group_by_accession) != wanted:
        raise Stage3WrapperError('Stage 3 candidate source-provider mapping incomplete')
    return dict(sorted(source_group_by_accession.items()))

class HistoricalAdjudicationStore:
    """Lazy exact loader for the frozen Project Finch adjudication artifact."""

    def __init__(self, *, path: Path, stage1: ModuleType, expected_sha256: str=EXPECTED_HISTORICAL_ADJUDICATION_SHA256) -> None:
        self.path = Path(path)
        self.stage1 = stage1
        self.expected_sha256 = expected_sha256
        self._records: dict[str, str] | None = None
        self._load_count = 0

    @property
    def loaded(self) -> bool:
        return self._records is not None

    @property
    def load_count(self) -> int:
        return self._load_count

    def _load(self) -> None:
        if self._records is not None:
            return
        self.stage1.require_sha256(self.path, self.expected_sha256, 'Project Finch chromosome-integrity adjudications')
        fields, rows = self.stage1.read_tsv(self.path)
        self.stage1.require_exact_fields(fields, HISTORICAL_ADJUDICATION_FIELDS, 'Project Finch chromosome-integrity adjudications')
        records: dict[str, str] = {}
        for row in rows:
            _nonempty_text(row['review_order'], label='historical adjudication review order')
            accession = self.stage1.require_accession(row['canonical_genbank_assembly_accession'], 'historical adjudication')
            if accession in records:
                raise Stage3WrapperError('duplicate accession in historical adjudications')
            outcome = _nonempty_text(row['outcome'], label='historical adjudication outcome')
            if outcome not in source_chromosome_integrity.VALID_HISTORICAL_OUTCOMES:
                raise Stage3WrapperError('unknown historical adjudication outcome')
            _nonempty_text(row['adjudication_reason'], label='historical adjudication reason')
            records[accession] = outcome
        self._records = records
        self._load_count += 1

    def lookup(self, accession: str) -> tuple[str, str] | None:
        self._load()
        current = self.stage1.require_accession(accession, 'historical adjudication lookup')
        outcome = self._records.get(current)
        if outcome is None:
            return None
        return (current, outcome)

def build_historical_provider(*, source_group: str, adjudications):
    """Build a provider that remains lazy until the execution helper calls it."""
    if source_group not in {'historical', 'fresh', 'fresh-recovery'}:
        raise Stage3WrapperError('unexpected candidate package source group')

    def provide(accession: str) -> source_chromosome_integrity.HistoricalReuseEvidence:
        if source_group != 'historical':
            return source_chromosome_integrity.HistoricalReuseEvidence(uses_historical_project_finch_package=False, cache_content_verification=None, adjudication_accession=None, adjudication_outcome=None)
        record = adjudications.lookup(accession)
        if record is None:
            return source_chromosome_integrity.HistoricalReuseEvidence(uses_historical_project_finch_package=True, cache_content_verification='pass', adjudication_accession=None, adjudication_outcome=None)
        adjudication_accession, outcome = record
        return source_chromosome_integrity.HistoricalReuseEvidence(uses_historical_project_finch_package=True, cache_content_verification='pass', adjudication_accession=adjudication_accession, adjudication_outcome=outcome)
    return provide

def evaluate_population(*, bundle, decisions: Stage2DecisionBundle, adjudications) -> tuple[Stage3CandidateEvaluation, ...]:
    """Evaluate exactly the Stage 2 CONTINUE population."""
    wanted = set(decisions.continue_source_sha256)
    observed: list[Stage3CandidateEvaluation] = []
    seen: set[str] = set()
    for batch in bundle.batches:
        selected = tuple((candidate for candidate in batch.candidates if candidate.accession in wanted))
        if not selected:
            continue
        selected_accessions = tuple((candidate.accession for candidate in selected))
        component_index = load_component_index(batch.component_audit, accessions=selected_accessions)
        package_manifest = load_package_manifest(batch.package_manifest)
        historical_provider = build_historical_provider(source_group=batch.source_group, adjudications=adjudications)
        for candidate in sorted(selected, key=lambda item: item.accession):
            accession = candidate.accession
            if accession in seen:
                raise Stage3WrapperError('duplicate candidate across Stage 3 batch specifications')
            seen.add(accession)
            component_rows = component_index.get(accession)
            if component_rows is None:
                raise Stage3WrapperError('Stage 3 candidate lacks component evidence')
            try:
                result = evaluate_stage3_candidate(candidate=candidate, component_rows=component_rows, package_manifest=package_manifest, expected_source_evidence_sha256=decisions.continue_source_sha256[accession], historical_provider=historical_provider)
            except Stage3ExecutionError as exc:
                raise Stage3WrapperError('Stage 3 candidate evaluation failed') from exc
            if result.accession != accession:
                raise Stage3WrapperError('Stage 3 evaluation accession mismatch')
            observed.append(result)
    if seen != wanted:
        raise Stage3WrapperError('Stage 3 evaluated population incomplete')
    if len(observed) != len(wanted):
        raise Stage3WrapperError('Stage 3 evaluation count mismatch')
    return tuple(sorted(observed, key=lambda item: item.accession))

def build_decision_rows(records: Sequence[Stage3CandidateEvaluation], *, expected_total: int=EXPECTED_STAGE3_TOTAL) -> tuple[tuple[dict[str, object], ...], Counter, Counter, Counter]:
    """Build deterministic identity-bearing decisions and aggregate counts."""
    if len(records) != expected_total:
        raise Stage3WrapperError('Stage 3 decision record count mismatch')
    allowed_statuses = {source_chromosome_integrity.PASS, source_chromosome_integrity.EXCLUDE, source_chromosome_integrity.UNRESOLVED}
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    status_counts = Counter()
    reason_counts = Counter()
    trigger_counts = Counter()
    reuse_counts = Counter()
    for record in sorted(records, key=lambda item: item.accession):
        if not isinstance(record, Stage3CandidateEvaluation):
            raise Stage3WrapperError('unexpected Stage 3 evaluation record type')
        if record.accession in seen:
            raise Stage3WrapperError('duplicate Stage 3 decision accession')
        seen.add(record.accession)
        if record.decision.status not in allowed_statuses:
            raise Stage3WrapperError('unexpected Stage 3 decision status')
        if not record.decision.reason:
            raise Stage3WrapperError('empty Stage 3 decision reason')
        if record.decision.triggered != record.trigger.triggered:
            raise Stage3WrapperError('Stage 3 trigger/decision disagreement')
        if record.trigger.closure_supported_chromosome_count + record.trigger.closure_unsupported_chromosome_count != record.trigger.chromosome_component_count:
            raise Stage3WrapperError('Stage 3 chromosome accounting mismatch')
        if record.decision.historical_adjudication_reused and (not record.trigger.triggered):
            raise Stage3WrapperError('historical adjudication reused for non-triggered candidate')
        status_counts[record.decision.status] += 1
        reason_counts[record.decision.reason] += 1
        trigger_counts['triggered' if record.trigger.triggered else 'nontriggered'] += 1
        reuse_counts['reused' if record.decision.historical_adjudication_reused else 'not_reused'] += 1
        rows.append({'canonical_genbank_assembly_accession': record.accession, 'source_evidence_sha256': record.source_evidence_sha256, 'stage2_status': BIOSAMPLE_CONTINUE, 'chromosome_component_count': record.trigger.chromosome_component_count, 'closure_supported_chromosome_count': record.trigger.closure_supported_chromosome_count, 'closure_unsupported_chromosome_count': record.trigger.closure_unsupported_chromosome_count, 'chromosome_integrity_triggered': int(record.trigger.triggered), 'historical_adjudication_reused': int(record.decision.historical_adjudication_reused), 'stage3_status': record.decision.status, 'stage3_reason': record.decision.reason})
    if sum(status_counts.values()) != expected_total:
        raise Stage3WrapperError('Stage 3 status accounting mismatch')
    if trigger_counts['triggered'] + trigger_counts['nontriggered'] != expected_total:
        raise Stage3WrapperError('Stage 3 trigger accounting mismatch')
    return (tuple(rows), status_counts, reason_counts, Counter({**trigger_counts, **reuse_counts}))

def _ensure_output_root_outside_repo(output_root: Path, repo: Path) -> Path:
    output_root = Path(output_root).resolve()
    repo = Path(repo).resolve()
    if output_root == repo or repo in output_root.parents:
        raise Stage3WrapperError('Stage 3 output root must be outside the repository')
    return output_root

def execute_to_scratch(*, repo: Path, expected_commit: str, expected_wrapper_sha256: str, output_root: Path, stage1: ModuleType, bundle, decisions: Stage2DecisionBundle, adjudications, frozen_repo_sha256: Mapping[str, str], stage2_decisions_path: Path, cache_verification_path: Path, historical_adjudications_path: Path, historical_adjudication_sha256: str=EXPECTED_HISTORICAL_ADJUDICATION_SHA256, expected_stage3_total: int=EXPECTED_STAGE3_TOTAL) -> Path:
    """Write predecision provenance, evaluate Stage 3, and finalize atomically."""
    repo = Path(repo).resolve()
    if len(decisions.continue_source_sha256) != expected_stage3_total:
        raise Stage3WrapperError('Stage 3 input count differs from execution contract')
    if accession_membership_sha256(decisions.continue_source_sha256) != decisions.continue_membership_sha256:
        raise Stage3WrapperError('Stage 3 input membership changed before execution')
    wrapper_path = repo / STAGE3_WRAPPER_RELATIVE
    stage1.require_lower_sha256(expected_wrapper_sha256, 'Stage 3 wrapper SHA256')
    stage1.require_sha256(wrapper_path, expected_wrapper_sha256, 'Stage 3 production wrapper')
    if decisions.decision_artifact_sha256 != stage1.sha256_file(stage2_decisions_path):
        raise Stage3WrapperError('Stage 2 decision artifact changed after loading')
    stage1.require_sha256(historical_adjudications_path, historical_adjudication_sha256, 'Project Finch chromosome-integrity adjudications')
    cache_verification_sha = stage1.sha256_file(cache_verification_path)
    output_root = _ensure_output_root_outside_repo(output_root, repo)
    output_root.mkdir(parents=True, exist_ok=True)
    final_dir = output_root / expected_commit
    partial_dir = output_root / (expected_commit + '.partial')
    if final_dir.exists():
        raise Stage3WrapperError('final Stage 3 output directory already exists')
    if partial_dir.exists():
        raise Stage3WrapperError('partial Stage 3 output directory already exists')
    partial_dir.mkdir()
    evidence_rows = [dict(row) for row in bundle.input_evidence_rows]
    evidence_rows.extend((stage1.evidence_row('stage3-input', '', 'stage2_completion_evidence', repo / STAGE2_COMPLETION_RELATIVE), stage1.evidence_row('stage3-input', '', 'stage2_decisions', stage2_decisions_path), stage1.evidence_row('stage3-input', '', 'historical_cache_verification', cache_verification_path), stage1.evidence_row('stage3-input', '', 'historical_chromosome_adjudications', historical_adjudications_path)))
    evidence_rows = tuple(sorted(evidence_rows, key=lambda row: (row['source_group'], row['batch'], row['file_role'], row['file_name'])))
    input_manifest_path = partial_dir / 'stage3-input-evidence-manifest.tsv'
    input_manifest_sha = stage1.write_tsv_atomic(input_manifest_path, stage1.INPUT_EVIDENCE_FIELDS, evidence_rows)
    predecision_path = partial_dir / 'stage3-predecision-provenance.json'
    predecision = {'schema_version': 1, 'status': 'STAGE3_PREDECISION_FROZEN', 'bacselect_git_commit': expected_commit, 'stage3_method_sha256': EXPECTED_STAGE3_METHOD_SHA256, 'stage2_completion_evidence_sha256': EXPECTED_STAGE2_COMPLETION_SHA256, 'stage2_decision_artifact_sha256': decisions.decision_artifact_sha256, 'stage3_input_candidate_count': len(decisions.continue_source_sha256), 'stage3_input_membership_sha256': decisions.continue_membership_sha256, 'stage1_population_membership_sha256': bundle.combined_membership_sha256, 'source_truth_execution_sha256': EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256, 'chromosome_integrity_primitive_sha256': EXPECTED_CHROMOSOME_PRIMITIVE_SHA256, 'chromosome_integrity_execution_sha256': EXPECTED_STAGE3_EXECUTION_SHA256, 'chromosome_integrity_clarification_sha256': EXPECTED_CHROMOSOME_CLARIFICATION_SHA256, 'historical_cache_verification_sha256': cache_verification_sha, 'project_finch_adjudication_commit': PROJECT_FINCH_ADJUDICATION_COMMIT, 'project_finch_adjudication_sha256': historical_adjudication_sha256, 'stage3_wrapper_sha256': expected_wrapper_sha256, 'frozen_repo_sha256': dict(sorted(frozen_repo_sha256.items())), 'authoritative_acquisition_recovery_evidence_manifest_sha256': input_manifest_sha, 'historical_adjudication_rows_parsed': False, 'chromosome_integrity_generated': False, 'taxonomy_resolution_generated': False, 'complete_universe_generated': False, 'holdout_membership_generated': False, 'structural_features_calculated': False, 'selector_outcomes_calculated': False}
    predecision_sha = stage1.write_json_atomic(predecision_path, predecision)
    records = evaluate_population(bundle=bundle, decisions=decisions, adjudications=adjudications)
    decision_rows, status_counts, reason_counts, execution_counts = build_decision_rows(records, expected_total=expected_stage3_total)
    decisions_path = partial_dir / 'stage3-chromosome-integrity-decisions.tsv'
    decisions_sha = stage1.write_tsv_atomic(decisions_path, STAGE3_DECISION_FIELDS, decision_rows)
    triggered_count = execution_counts['triggered']
    nontriggered_count = execution_counts['nontriggered']
    reused_count = execution_counts['reused']
    execution_provenance_path = partial_dir / 'stage3-execution-provenance.json'
    execution_provenance = {'schema_version': 1, 'status': 'STAGE3_CHROMOSOME_INTEGRITY_COMPLETE', 'bacselect_git_commit': expected_commit, 'predecision_provenance_sha256': predecision_sha, 'input_evidence_manifest_sha256': input_manifest_sha, 'candidate_decisions_sha256': decisions_sha, 'stage3_input_candidate_count': len(decision_rows), 'stage3_input_membership_sha256': decisions.continue_membership_sha256, 'triggered_candidate_count': triggered_count, 'nontriggered_candidate_count': nontriggered_count, 'historical_adjudication_reuse_count': reused_count, 'historical_adjudication_artifact_parsed': bool(adjudications.loaded), 'chromosome_integrity_generated': True, 'taxonomy_resolution_generated': False, 'complete_universe_generated': False, 'holdout_membership_generated': False, 'structural_features_calculated': False, 'selector_outcomes_calculated': False}
    execution_provenance_sha = stage1.write_json_atomic(execution_provenance_path, execution_provenance)
    summary_path = partial_dir / 'stage3-aggregate-summary.json'
    summary = {'schema_version': 1, 'status': 'STAGE3_CHROMOSOME_INTEGRITY_COMPLETE', 'stage3_input_candidate_count': len(decision_rows), 'stage3_input_membership_sha256': decisions.continue_membership_sha256, 'decision_count': len(decision_rows), 'triggered_candidate_count': triggered_count, 'nontriggered_candidate_count': nontriggered_count, 'historical_adjudication_reuse_count': reused_count, 'status_counts': dict(sorted(status_counts.items())), 'reason_counts': dict(sorted(reason_counts.items())), 'candidate_decisions_sha256': decisions_sha, 'predecision_provenance_sha256': predecision_sha, 'execution_provenance_sha256': execution_provenance_sha, 'input_evidence_manifest_sha256': input_manifest_sha, 'chromosome_integrity_generated': True, 'taxonomy_resolution_generated': False, 'complete_universe_generated': False, 'holdout_membership_generated': False, 'structural_features_calculated': False, 'selector_outcomes_calculated': False}
    summary_sha = stage1.write_json_atomic(summary_path, summary)
    content_paths = (input_manifest_path, predecision_path, decisions_path, execution_provenance_path, summary_path)
    content_rows = tuple(({'path': path.name, 'size_bytes': str(path.stat().st_size), 'sha256': stage1.sha256_file(path)} for path in sorted(content_paths, key=lambda item: item.name)))
    content_manifest_path = partial_dir / 'stage3-content-manifest.tsv'
    content_manifest_sha = stage1.write_tsv_atomic(content_manifest_path, CONTENT_MANIFEST_FIELDS, content_rows)
    if final_dir.exists():
        raise Stage3WrapperError('final Stage 3 directory appeared before finalization')
    os.replace(partial_dir, final_dir)
    print('PASS | Stage 3 chromosome-integrity execution complete')
    print(f'stage3_input_candidate_count={len(decision_rows)}')
    print(f'stage3_input_membership_sha256={decisions.continue_membership_sha256}')
    print(f'triggered_candidate_count={triggered_count}')
    print(f'nontriggered_candidate_count={nontriggered_count}')
    print(f'historical_adjudication_reuse_count={reused_count}')
    print(f'candidate_decisions_sha256={decisions_sha}')
    print(f'predecision_provenance_sha256={predecision_sha}')
    print(f'execution_provenance_sha256={execution_provenance_sha}')
    print(f'aggregate_summary_sha256={summary_sha}')
    print(f'content_manifest_sha256={content_manifest_sha}')
    print(f'execution_dir={final_dir}')
    return final_dir

def parse_args(argv: list[str] | None=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Execute frozen BacSelect selector-v1 Stage 3 chromosome-integrity evaluation.')
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--expected-wrapper-sha256', required=True)
    parser.add_argument('--historical-root', type=Path, required=True)
    parser.add_argument('--cache-reuse-accessions', type=Path, required=True)
    parser.add_argument('--cache-reuse-manifest', type=Path, required=True)
    parser.add_argument('--cache-verification', type=Path, required=True)
    parser.add_argument('--fresh-root', type=Path, required=True)
    parser.add_argument('--recovery-root', type=Path, required=True)
    parser.add_argument('--stage2-decisions', type=Path, required=True)
    parser.add_argument('--historical-adjudications', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    return parser.parse_args(argv)

def main(argv: list[str] | None=None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    stage2 = load_stage2_wrapper(repo)
    stage1 = stage2.load_stage1_wrapper(repo)
    frozen_files = {**stage2.FROZEN_REPO_FILES, **FROZEN_REPO_FILES}
    frozen_repo_sha256 = stage1.preflight_repository(repo, args.expected_commit, frozen_files=frozen_files)
    stage1.require_sha256(repo / STAGE3_WRAPPER_RELATIVE, args.expected_wrapper_sha256, 'Stage 3 production wrapper')
    completion = load_stage2_completion(repo, stage1=stage1)
    decisions = load_stage2_decisions(args.stage2_decisions, stage1=stage1, stage2=stage2, completion=completion)
    bundle = stage2.reconstruct_stage1_population(repo=repo, stage1=stage1, historical_root=args.historical_root, cache_reuse_accessions=args.cache_reuse_accessions, cache_reuse_manifest=args.cache_reuse_manifest, cache_verification=args.cache_verification, fresh_root=args.fresh_root, recovery_root=args.recovery_root)
    verify_stage3_population_binding(bundle=bundle, decisions=decisions)
    stage1.require_sha256(args.historical_adjudications, EXPECTED_HISTORICAL_ADJUDICATION_SHA256, 'Project Finch chromosome-integrity adjudications')
    adjudications = HistoricalAdjudicationStore(path=args.historical_adjudications, stage1=stage1)
    print('PASS | Stage 3 input reconstructed and rebound')
    print(f'stage3_input_candidate_count={len(decisions.continue_source_sha256)}')
    print(f'stage3_input_membership_sha256={decisions.continue_membership_sha256}')
    print('historical_adjudication_rows_parsed=false')
    execute_to_scratch(repo=repo, expected_commit=args.expected_commit, expected_wrapper_sha256=args.expected_wrapper_sha256, output_root=args.output_root, stage1=stage1, bundle=bundle, decisions=decisions, adjudications=adjudications, frozen_repo_sha256=frozen_repo_sha256, stage2_decisions_path=args.stage2_decisions, cache_verification_path=args.cache_verification, historical_adjudications_path=args.historical_adjudications)
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
