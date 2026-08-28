from __future__ import annotations
from collections import Counter
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
from bacselect import source_chromosome_integrity
from bacselect.source_chromosome_integrity_execution import Stage3CandidateEvaluation
from bacselect.source_post_sequence_eligibility import BIOSAMPLE_CONTINUE, BIOSAMPLE_NONREPRESENTATIVE, BIOSAMPLE_UNRESOLVED
from bacselect.source_truth_execution import CandidateAudit, accession_membership_sha256
REPO = Path(__file__).resolve().parents[1]
WRAPPER = REPO / 'validation/selector-v1/run_chromosome_integrity_execution.py'

def load_wrapper():
    name = '_bacselect_test_stage3_chromosome_integrity_wrapper'
    spec = importlib.util.spec_from_file_location(name, WRAPPER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def frozen_modules():
    module = load_wrapper()
    stage2 = module.load_stage2_wrapper(REPO)
    stage1 = stage2.load_stage1_wrapper(REPO)
    return (module, stage2, stage1)

def write_tsv(path, fields, rows):
    lines = ['\t'.join(fields)]
    for row in rows:
        lines.append('\t'.join((str(row[field]) for field in fields)))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

def decision_row(accession, *, status=BIOSAMPLE_CONTINUE, reason='BIOSAMPLE_SINGLETON', source_char='a', fingerprint_char='b', biosample='SAMN10000001'):
    return {'canonical_genbank_assembly_accession': accession, 'biosample': biosample, 'source_evidence_sha256': source_char * 64, 'assembly_fingerprint': fingerprint_char * 64, 'stage2_status': status, 'stage2_reason': reason}

def synthetic_completion(*, rows, decision_sha256):
    status_counts = Counter((row['stage2_status'] for row in rows))
    reason_counts = Counter((row['stage2_reason'] for row in rows))
    accessions = tuple(sorted((row['canonical_genbank_assembly_accession'] for row in rows)))
    return {'schema_version': 1, 'status': 'STAGE2_REPEATED_BIOSAMPLE_COMPLETE', 'decision_row_count': len(rows), 'stage2_input_candidate_count': len(rows), 'continue_count': status_counts[BIOSAMPLE_CONTINUE], 'status_counts': dict(status_counts), 'reason_counts': dict(reason_counts), 'stage2_input_membership_sha256': accession_membership_sha256(accessions), 'artifacts_sha256': {'stage2-repeated-biosample-decisions.tsv': decision_sha256}}

def candidate(tmp_path, accession, *, batch='batch-001'):
    audit_path = tmp_path / batch / 'candidate-sequence-audit.tsv'
    return CandidateAudit(accession=accession, audit_path=audit_path, fasta_file=f'ncbi_dataset/data/{accession}/{accession}_genomic.fna', fasta_sha256='c' * 64, primary_assembly_records=1)

def synthetic_decisions(module, accessions):
    accessions = tuple(sorted(accessions))
    source = {accession: format(index + 1, '064x') for index, accession in enumerate(accessions)}
    return module.Stage2DecisionBundle(all_accessions=accessions, continue_source_sha256=source, all_membership_sha256=accession_membership_sha256(accessions), continue_membership_sha256=accession_membership_sha256(accessions), status_counts={BIOSAMPLE_CONTINUE: len(accessions)}, reason_counts={'BIOSAMPLE_SINGLETON': len(accessions)}, decision_artifact_sha256='d' * 64)

def evaluation(accession, *, source_char='a', triggered=False, status=None, reason=None, reused=False):
    if triggered:
        trigger = source_chromosome_integrity.TriggerAssessment(triggered=True, chromosome_component_count=2, closure_supported_chromosome_count=1, closure_unsupported_chromosome_count=1)
        if status is None:
            status = source_chromosome_integrity.UNRESOLVED
        if reason is None:
            reason = 'NO_REUSABLE_HISTORICAL_ADJUDICATION'
    else:
        trigger = source_chromosome_integrity.TriggerAssessment(triggered=False, chromosome_component_count=1, closure_supported_chromosome_count=1, closure_unsupported_chromosome_count=0)
        if status is None:
            status = source_chromosome_integrity.PASS
        if reason is None:
            reason = 'NO_CHROMOSOME_INTEGRITY_TRIGGER'
    decision = source_chromosome_integrity.ChromosomeIntegrityDecision(status=status, reason=reason, triggered=triggered, historical_adjudication_reused=reused)
    return Stage3CandidateEvaluation(accession=accession, source_evidence_sha256=source_char * 64, primary_component_count=trigger.chromosome_component_count, trigger=trigger, decision=decision)

def test_frozen_stage2_wrapper_load_is_exact_and_side_effect_free():
    module = load_wrapper()
    stage2 = module.load_stage2_wrapper(REPO)
    assert stage2.EXPECTED_STAGE1_TOTAL == 68480

def test_blinded_stage2_completion_checkpoint_loads_exactly():
    module, _, stage1 = frozen_modules()
    payload = module.load_stage2_completion(REPO, stage1=stage1)
    assert payload['continue_count'] == 68278
    assert payload['artifacts_sha256']['stage2-repeated-biosample-decisions.tsv'] == module.EXPECTED_STAGE2_DECISIONS_SHA256

def test_stage2_decision_loader_filters_exact_continue_membership(tmp_path):
    module, stage2, stage1 = frozen_modules()
    rows = [decision_row('GCA_000000001.1', source_char='1', fingerprint_char='2', biosample='SAMN10000001'), decision_row('GCA_000000002.1', source_char='3', fingerprint_char='4', biosample='SAMN10000002'), decision_row('GCA_000000003.1', status=BIOSAMPLE_NONREPRESENTATIVE, reason='BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE', source_char='5', fingerprint_char='6', biosample='SAMN10000003'), decision_row('GCA_000000004.1', status=BIOSAMPLE_UNRESOLVED, reason='BIOSAMPLE_FINGERPRINTS_DIFFER', source_char='7', fingerprint_char='8', biosample='SAMN10000004')]
    path = tmp_path / 'stage2.tsv'
    write_tsv(path, stage2.STAGE2_DECISION_FIELDS, rows)
    decision_sha = module.sha256_file(path)
    completion = synthetic_completion(rows=rows, decision_sha256=decision_sha)
    observed = module.load_stage2_decisions(path, stage1=stage1, stage2=stage2, completion=completion, expected_sha256=decision_sha, expected_total=4, expected_continue=2)
    assert tuple(observed.continue_source_sha256) == ('GCA_000000001.1', 'GCA_000000002.1')
    assert observed.continue_membership_sha256 == accession_membership_sha256(('GCA_000000001.1', 'GCA_000000002.1'))

def test_stage2_decision_loader_rejects_duplicate_accession(tmp_path):
    module, stage2, stage1 = frozen_modules()
    rows = [decision_row('GCA_000000001.1'), decision_row('GCA_000000001.1', biosample='SAMN10000002')]
    path = tmp_path / 'stage2.tsv'
    write_tsv(path, stage2.STAGE2_DECISION_FIELDS, rows)
    decision_sha = module.sha256_file(path)
    completion_rows = [rows[0], decision_row('GCA_000000002.1', biosample='SAMN10000002')]
    completion = synthetic_completion(rows=completion_rows, decision_sha256=decision_sha)
    with pytest.raises(module.Stage3WrapperError, match='duplicate accession'):
        module.load_stage2_decisions(path, stage1=stage1, stage2=stage2, completion=completion, expected_sha256=decision_sha, expected_total=2, expected_continue=2)

def test_stage2_decision_loader_rejects_membership_drift(tmp_path):
    module, stage2, stage1 = frozen_modules()
    rows = [decision_row('GCA_000000001.1'), decision_row('GCA_000000002.1', biosample='SAMN10000002')]
    path = tmp_path / 'stage2.tsv'
    write_tsv(path, stage2.STAGE2_DECISION_FIELDS, rows)
    decision_sha = module.sha256_file(path)
    completion = synthetic_completion(rows=rows, decision_sha256=decision_sha)
    completion['stage2_input_membership_sha256'] = '0' * 64
    with pytest.raises(module.Stage3WrapperError, match='membership SHA256 mismatch'):
        module.load_stage2_decisions(path, stage1=stage1, stage2=stage2, completion=completion, expected_sha256=decision_sha, expected_total=2, expected_continue=2)

def test_population_binding_requires_exact_stage3_membership(tmp_path):
    module, _, stage1 = frozen_modules()
    first = candidate(tmp_path, 'GCA_000000001.1', batch='historical-001')
    second = candidate(tmp_path, 'GCA_000000002.1', batch='fresh-001')
    third = candidate(tmp_path, 'GCA_000000003.1', batch='fresh-001')
    batches = (stage1.BatchSpec(source_group='historical', batch='historical-001', candidate_audit=first.audit_path, component_audit=first.audit_path.parent / 'component-sequence-audit.tsv', package_manifest=first.audit_path.parent / 'package-files.tsv', candidates=(first,)), stage1.BatchSpec(source_group='fresh', batch='fresh-001', candidate_audit=second.audit_path, component_audit=second.audit_path.parent / 'component-sequence-audit.tsv', package_manifest=second.audit_path.parent / 'package-files.tsv', candidates=(second, third)))
    combined = (first.accession, second.accession, third.accession)
    bundle = SimpleNamespace(historical_candidates=(first,), fresh_candidates=(second, third), batches=batches, combined_membership_sha256=accession_membership_sha256(combined))
    decisions = synthetic_decisions(module, combined)
    mapping = module.verify_stage3_population_binding(bundle=bundle, decisions=decisions, expected_stage1_total=3, expected_stage2_total=3, expected_stage3_total=3)
    assert mapping == {first.accession: 'historical', second.accession: 'fresh', third.accession: 'fresh'}

def test_population_binding_rejects_missing_batch_candidate(tmp_path):
    module, _, stage1 = frozen_modules()
    first = candidate(tmp_path, 'GCA_000000001.1')
    second = candidate(tmp_path, 'GCA_000000002.1')
    batch = stage1.BatchSpec(source_group='fresh', batch='batch-001', candidate_audit=first.audit_path, component_audit=first.audit_path.parent / 'component-sequence-audit.tsv', package_manifest=first.audit_path.parent / 'package-files.tsv', candidates=(first,))
    bundle = SimpleNamespace(historical_candidates=(), fresh_candidates=(first, second), batches=(batch,), combined_membership_sha256=accession_membership_sha256((first.accession, second.accession)))
    decisions = synthetic_decisions(module, (first.accession, second.accession))
    with pytest.raises(module.Stage3WrapperError, match='batch specifications do not cover'):
        module.verify_stage3_population_binding(bundle=bundle, decisions=decisions, expected_stage1_total=2, expected_stage2_total=2, expected_stage3_total=2)

class FakeAdjudications:

    def __init__(self, values=None, *, poison=False):
        self.values = values or {}
        self.poison = poison
        self.calls = []
        self.loaded = False

    def lookup(self, accession):
        if self.poison:
            raise AssertionError('historical adjudication lookup was consulted')
        self.loaded = True
        self.calls.append(accession)
        value = self.values.get(accession)
        if value is None:
            return None
        return (accession, value)

@pytest.mark.parametrize('source_group', ['fresh', 'fresh-recovery'])
def test_fresh_providers_never_consult_historical_store(source_group):
    module = load_wrapper()
    store = FakeAdjudications(poison=True)
    provider = module.build_historical_provider(source_group=source_group, adjudications=store)
    observed = provider('GCA_000000001.1')
    assert observed.uses_historical_project_finch_package is False
    assert store.calls == []
    assert store.loaded is False

def test_historical_provider_uses_exact_accession_lookup():
    module = load_wrapper()
    store = FakeAdjudications({'GCA_000000001.1': source_chromosome_integrity.HISTORICAL_RETAIN})
    provider = module.build_historical_provider(source_group='historical', adjudications=store)
    observed = provider('GCA_000000001.1')
    assert store.calls == ['GCA_000000001.1']
    assert observed.uses_historical_project_finch_package is True
    assert observed.cache_content_verification == 'pass'
    assert observed.adjudication_accession == 'GCA_000000001.1'

def test_historical_provider_marks_absent_adjudication_without_inference():
    module = load_wrapper()
    store = FakeAdjudications()
    provider = module.build_historical_provider(source_group='historical', adjudications=store)
    observed = provider('GCA_000000001.1')
    assert observed.adjudication_accession is None
    assert observed.adjudication_outcome is None

def test_lazy_historical_store_validates_exact_schema_and_outcome(tmp_path):
    module, _, stage1 = frozen_modules()
    path = tmp_path / 'adjudications.tsv'
    rows = [{'review_order': '1', 'canonical_genbank_assembly_accession': 'GCA_000000001.1', 'outcome': source_chromosome_integrity.HISTORICAL_RETAIN, 'adjudication_reason': 'synthetic'}]
    write_tsv(path, module.HISTORICAL_ADJUDICATION_FIELDS, rows)
    expected_sha = module.sha256_file(path)
    store = module.HistoricalAdjudicationStore(path=path, stage1=stage1, expected_sha256=expected_sha)
    assert store.loaded is False
    assert store.load_count == 0
    assert store.lookup('GCA_000000001.1') == ('GCA_000000001.1', source_chromosome_integrity.HISTORICAL_RETAIN)
    assert store.loaded is True
    assert store.load_count == 1
    store.lookup('GCA_000000001.1')
    assert store.load_count == 1

def test_lazy_historical_store_rejects_unknown_outcome(tmp_path):
    module, _, stage1 = frozen_modules()
    path = tmp_path / 'adjudications.tsv'
    rows = [{'review_order': '1', 'canonical_genbank_assembly_accession': 'GCA_000000001.1', 'outcome': 'UNKNOWN', 'adjudication_reason': 'synthetic'}]
    write_tsv(path, module.HISTORICAL_ADJUDICATION_FIELDS, rows)
    store = module.HistoricalAdjudicationStore(path=path, stage1=stage1, expected_sha256=module.sha256_file(path))
    with pytest.raises(module.Stage3WrapperError, match='unknown historical adjudication outcome'):
        store.lookup('GCA_000000001.1')

def test_evaluate_population_preserves_source_provider_classes(tmp_path, monkeypatch):
    module, _, stage1 = frozen_modules()
    historical = candidate(tmp_path, 'GCA_000000001.1', batch='historical-001')
    fresh = candidate(tmp_path, 'GCA_000000002.1', batch='fresh-001')
    recovery = candidate(tmp_path, 'GCA_000000003.1', batch='recovery-001')
    batches = []
    for source_group, item in (('historical', historical), ('fresh', fresh), ('fresh-recovery', recovery)):
        batches.append(stage1.BatchSpec(source_group=source_group, batch=item.audit_path.parent.name, candidate_audit=item.audit_path, component_audit=item.audit_path.parent / 'component-sequence-audit.tsv', package_manifest=item.audit_path.parent / 'package-files.tsv', candidates=(item,)))
    bundle = SimpleNamespace(batches=tuple(batches))
    decisions = synthetic_decisions(module, (historical.accession, fresh.accession, recovery.accession))
    monkeypatch.setattr(module, 'load_component_index', lambda path, accessions: {accession: ('synthetic-component',) for accession in accessions})
    monkeypatch.setattr(module, 'load_package_manifest', lambda path: {})
    provider_flags = {}

    def fake_evaluate(*, candidate, component_rows, package_manifest, expected_source_evidence_sha256, historical_provider):
        evidence = historical_provider(candidate.accession)
        provider_flags[candidate.accession] = evidence.uses_historical_project_finch_package
        return evaluation(candidate.accession)
    monkeypatch.setattr(module, 'evaluate_stage3_candidate', fake_evaluate)
    store = FakeAdjudications()
    observed = module.evaluate_population(bundle=bundle, decisions=decisions, adjudications=store)
    assert [record.accession for record in observed] == ['GCA_000000001.1', 'GCA_000000002.1', 'GCA_000000003.1']
    assert provider_flags == {historical.accession: True, fresh.accession: False, recovery.accession: False}
    assert store.calls == [historical.accession]

def test_decision_rows_are_deterministically_sorted_and_accounted():
    module = load_wrapper()
    records = (evaluation('GCA_000000003.1', triggered=True, status=source_chromosome_integrity.UNRESOLVED, reason='HISTORICAL_UNRESOLVED', reused=True), evaluation('GCA_000000001.1'), evaluation('GCA_000000002.1', triggered=True, status=source_chromosome_integrity.EXCLUDE, reason='HISTORICAL_FRAGMENTED_CHROMOSOME_SET', reused=True))
    rows, status_counts, reason_counts, execution_counts = module.build_decision_rows(records, expected_total=3)
    assert [row['canonical_genbank_assembly_accession'] for row in rows] == ['GCA_000000001.1', 'GCA_000000002.1', 'GCA_000000003.1']
    assert sum(status_counts.values()) == 3
    assert sum(reason_counts.values()) == 3
    assert execution_counts['triggered'] + execution_counts['nontriggered'] == 3
    assert execution_counts['reused'] == 2

def scratch_fixture(tmp_path):
    module, _, stage1 = frozen_modules()
    accessions = ('GCA_000000001.1', 'GCA_000000002.1', 'GCA_000000003.1')
    candidates = tuple((candidate(tmp_path, accession, batch='synthetic-batch') for accession in accessions))
    bundle = SimpleNamespace(historical_candidates=(), fresh_candidates=candidates, batches=(), combined_membership_sha256=accession_membership_sha256(accessions), input_evidence_rows=())
    decisions = synthetic_decisions(module, accessions)
    stage2_path = tmp_path / 'stage2-decisions.tsv'
    stage2_path.write_text('synthetic\n', encoding='utf-8')
    decisions = module.Stage2DecisionBundle(all_accessions=decisions.all_accessions, continue_source_sha256=decisions.continue_source_sha256, all_membership_sha256=decisions.all_membership_sha256, continue_membership_sha256=decisions.continue_membership_sha256, status_counts=decisions.status_counts, reason_counts=decisions.reason_counts, decision_artifact_sha256=stage1.sha256_file(stage2_path))
    cache_path = tmp_path / 'cache-verification.tsv'
    cache_path.write_text('synthetic\n', encoding='utf-8')
    adjudication_path = tmp_path / 'adjudications.tsv'
    adjudication_path.write_text('synthetic\n', encoding='utf-8')
    wrapper_sha = stage1.sha256_file(WRAPPER)
    adjudication_sha = stage1.sha256_file(adjudication_path)
    return SimpleNamespace(module=module, stage1=stage1, bundle=bundle, decisions=decisions, stage2_path=stage2_path, cache_path=cache_path, adjudication_path=adjudication_path, wrapper_sha=wrapper_sha, adjudication_sha=adjudication_sha, accessions=accessions)

def test_predecision_exists_before_first_evaluation_and_finalizes_atomically(tmp_path, monkeypatch):
    fixture = scratch_fixture(tmp_path)
    module = fixture.module
    output_root = tmp_path / 'outside'
    expected_commit = '1' * 40
    observed = {'predecision': False}

    def fake_population(*, bundle, decisions, adjudications):
        predecision_path = output_root / (expected_commit + '.partial') / 'stage3-predecision-provenance.json'
        assert predecision_path.is_file()
        payload = json.loads(predecision_path.read_text(encoding='utf-8'))
        assert payload['chromosome_integrity_generated'] is False
        assert payload['historical_adjudication_rows_parsed'] is False
        assert payload['stage3_method_sha256'] == module.EXPECTED_STAGE3_METHOD_SHA256
        assert payload['stage2_completion_evidence_sha256'] == module.EXPECTED_STAGE2_COMPLETION_SHA256
        assert payload['stage3_input_candidate_count'] == 3
        assert payload['source_truth_execution_sha256'] == module.EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256
        assert payload['chromosome_integrity_execution_sha256'] == module.EXPECTED_STAGE3_EXECUTION_SHA256
        assert payload['chromosome_integrity_clarification_sha256'] == module.EXPECTED_CHROMOSOME_CLARIFICATION_SHA256
        assert payload['stage3_wrapper_sha256'] == fixture.wrapper_sha
        assert payload['project_finch_adjudication_sha256'] == fixture.adjudication_sha
        observed['predecision'] = True
        return (evaluation(fixture.accessions[0]), evaluation(fixture.accessions[1], triggered=True, status=source_chromosome_integrity.EXCLUDE, reason='HISTORICAL_FRAGMENTED_CHROMOSOME_SET', reused=True), evaluation(fixture.accessions[2], triggered=True, status=source_chromosome_integrity.UNRESOLVED, reason='HISTORICAL_UNRESOLVED', reused=True))
    monkeypatch.setattr(module, 'evaluate_population', fake_population)
    store = FakeAdjudications()
    final_dir = module.execute_to_scratch(repo=REPO, expected_commit=expected_commit, expected_wrapper_sha256=fixture.wrapper_sha, output_root=output_root, stage1=fixture.stage1, bundle=fixture.bundle, decisions=fixture.decisions, adjudications=store, frozen_repo_sha256={}, stage2_decisions_path=fixture.stage2_path, cache_verification_path=fixture.cache_path, historical_adjudications_path=fixture.adjudication_path, historical_adjudication_sha256=fixture.adjudication_sha, expected_stage3_total=3)
    assert observed['predecision']
    assert final_dir.is_dir()
    assert not (output_root / (expected_commit + '.partial')).exists()
    expected_names = {'stage3-input-evidence-manifest.tsv', 'stage3-predecision-provenance.json', 'stage3-chromosome-integrity-decisions.tsv', 'stage3-execution-provenance.json', 'stage3-aggregate-summary.json', 'stage3-content-manifest.tsv'}
    assert {path.name for path in final_dir.iterdir()} == expected_names
    summary = json.loads((final_dir / 'stage3-aggregate-summary.json').read_text(encoding='utf-8'))
    assert summary['decision_count'] == 3
    assert summary['triggered_candidate_count'] == 2
    assert summary['nontriggered_candidate_count'] == 1
    assert summary['historical_adjudication_reuse_count'] == 2
    summary_text = json.dumps(summary, sort_keys=True)
    assert 'GCA_' not in summary_text
    assert 'SAMN' not in summary_text

def test_failed_execution_preserves_partial_predecision(tmp_path, monkeypatch):
    fixture = scratch_fixture(tmp_path)
    module = fixture.module
    output_root = tmp_path / 'outside'
    expected_commit = '2' * 40

    def fail_population(*, bundle, decisions, adjudications):
        raise module.Stage3WrapperError('synthetic execution failure')
    monkeypatch.setattr(module, 'evaluate_population', fail_population)
    with pytest.raises(module.Stage3WrapperError, match='synthetic execution failure'):
        module.execute_to_scratch(repo=REPO, expected_commit=expected_commit, expected_wrapper_sha256=fixture.wrapper_sha, output_root=output_root, stage1=fixture.stage1, bundle=fixture.bundle, decisions=fixture.decisions, adjudications=FakeAdjudications(), frozen_repo_sha256={}, stage2_decisions_path=fixture.stage2_path, cache_verification_path=fixture.cache_path, historical_adjudications_path=fixture.adjudication_path, historical_adjudication_sha256=fixture.adjudication_sha, expected_stage3_total=3)
    partial = output_root / (expected_commit + '.partial')
    assert partial.is_dir()
    assert (partial / 'stage3-predecision-provenance.json').is_file()
    assert not (output_root / expected_commit).exists()

@pytest.mark.parametrize('existing_kind', ['final', 'partial'])
def test_atomic_finalization_rejects_existing_output_state(tmp_path, existing_kind):
    fixture = scratch_fixture(tmp_path)
    module = fixture.module
    output_root = tmp_path / 'outside'
    output_root.mkdir()
    expected_commit = '3' * 40
    if existing_kind == 'final':
        existing = output_root / expected_commit
    else:
        existing = output_root / (expected_commit + '.partial')
    existing.mkdir()
    with pytest.raises(module.Stage3WrapperError, match='final Stage 3 output directory already exists' if existing_kind == 'final' else 'partial Stage 3 output directory already exists'):
        module.execute_to_scratch(repo=REPO, expected_commit=expected_commit, expected_wrapper_sha256=fixture.wrapper_sha, output_root=output_root, stage1=fixture.stage1, bundle=fixture.bundle, decisions=fixture.decisions, adjudications=FakeAdjudications(), frozen_repo_sha256={}, stage2_decisions_path=fixture.stage2_path, cache_verification_path=fixture.cache_path, historical_adjudications_path=fixture.adjudication_path, historical_adjudication_sha256=fixture.adjudication_sha, expected_stage3_total=3)

def test_poisoned_later_stage_attributes_are_never_consulted(tmp_path):
    module, _, stage1 = frozen_modules()
    item = candidate(tmp_path, 'GCA_000000001.1')

    class PoisonBundle:
        historical_candidates = ()
        fresh_candidates = (item,)
        batches = (stage1.BatchSpec(source_group='fresh', batch='batch-001', candidate_audit=item.audit_path, component_audit=item.audit_path.parent / 'component-sequence-audit.tsv', package_manifest=item.audit_path.parent / 'package-files.tsv', candidates=(item,)),)
        combined_membership_sha256 = accession_membership_sha256((item.accession,))

        @property
        def taxonomy(self):
            raise AssertionError('taxonomy must not be consulted')

        @property
        def structural_features(self):
            raise AssertionError('structural features must not be consulted')

        @property
        def holdout(self):
            raise AssertionError('holdout must not be consulted')
    decisions = synthetic_decisions(module, (item.accession,))
    observed = module.verify_stage3_population_binding(bundle=PoisonBundle(), decisions=decisions, expected_stage1_total=1, expected_stage2_total=1, expected_stage3_total=1)
    assert observed == {item.accession: 'fresh'}

def test_output_root_inside_repository_fails_closed():
    module = load_wrapper()
    with pytest.raises(module.Stage3WrapperError, match='outside the repository'):
        module._ensure_output_root_outside_repo(REPO / 'synthetic-stage3-output', REPO)
