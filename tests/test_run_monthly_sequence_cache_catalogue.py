"""Tests for portable monthly sequence-cache catalogue execution."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

import pytest

from bacselect.monthly_sequence_cache_catalogue import (
    CHAINED,
    GENESIS,
    audit_sequence_cache_catalogue,
    serialize_sequence_cache_catalogue,
)


REPO = Path(
    __file__
).resolve().parents[
    1
]

WRAPPER_PATH = (
    REPO
    / "validation"
    / "selector-v1"
    / "run_monthly_sequence_cache_catalogue.py"
)


def load_wrapper():
    name = (
        "_bacselect_test_monthly_sequence_cache_catalogue_execution"
    )

    existing = sys.modules.get(
        name
    )

    if existing is not None:
        return existing

    spec = importlib.util.spec_from_file_location(
        name,
        WRAPPER_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


module = load_wrapper()


RELEASE_1 = "2032.03"
RELEASE_2 = "2032.04"
RELEASE_3 = "2032.05"

SNAPSHOT_1 = (
    "bacselect-source-2032.03-"
    "20320301T001700Z"
)

SNAPSHOT_2 = (
    "bacselect-source-2032.04-"
    "20320401T001700Z"
)

SNAPSHOT_3 = (
    "bacselect-source-2032.05-"
    "20320501T001700Z"
)

COMMIT_1 = "1" * 40
COMMIT_2 = "2" * 40
COMMIT_3 = "3" * 40
COMMIT_4 = "4" * 40


def canonical_json(
    value,
):
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )


def sha(
    payload,
):
    return hashlib.sha256(
        payload
    ).hexdigest()


def completion_payload(
    *,
    snapshot,
    commit,
):
    return canonical_json(
        {
            "batches":
                [],
            "completed_accession_count":
                0,
            "completed_batch_count":
                0,
            "environment_explicit_sha256":
                "a" * 64,
            "expected_batch_count":
                0,
            "fresh_acquisition_count":
                0,
            "fresh_batch_size":
                500,
            "origin_git_commit":
                commit,
            "schema_version":
                (
                    "bacselect-monthly-sequence-"
                    "acquisition-completion-v1"
                ),
            "source_snapshot_id":
                snapshot,
            "source_snapshot_record_sha256":
                "b" * 64,
            "stage2_fresh_target_manifest_sha256":
                "c" * 64,
            "stage2_sequence_plan_record_sha256":
                "d" * 64,
            "status":
                "SEQUENCE_ACQUISITION_COMPLETE",
        }
    )


def catalogue_payload(
    *,
    release,
    snapshot,
    commit,
    previous=None,
):
    return serialize_sequence_cache_catalogue(
        release_id=release,
        source_snapshot_id=snapshot,
        origin_git_commit=commit,
        sequence_acquisition_completion_payload=(
            completion_payload(
                snapshot=snapshot,
                commit=commit,
            )
        ),
        current_batches=(),
        previous_catalogue_payload=(
            previous
        ),
    )


def stage1_path(
    root,
    release,
    commit,
):
    return (
        root
        / release
        / "production"
        / commit
    )


def write_catalogue(
    root,
    *,
    release,
    commit,
    payload,
):
    stage1 = stage1_path(
        root,
        release,
        commit,
    )

    stage1.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        stage1
        / module.CATALOGUE_NAME
    )

    path.write_bytes(
        payload
    )

    return path


def zero_context(
    stage1,
    *,
    release,
    snapshot,
    commit,
):
    payload = completion_payload(
        snapshot=snapshot,
        commit=commit,
    )

    return module.AuditedCompletionContext(
        release_id=release,
        source_snapshot_id=snapshot,
        stage1_root=stage1,
        completion_payload=payload,
        completion_record=(
            json.loads(
                payload
            )
        ),
        batch_evidence=(),
        fresh_acquisition_count=0,
    )


def test_repository_preflight_accepts_exact_dependencies():
    wrapper_sha = module.sha256_file(
        WRAPPER_PATH
    )

    test_sha = module.sha256_file(
        Path(
            __file__
        )
    )

    def git_reader(
        repo,
        *args,
    ):
        if args == (
            "rev-parse",
            "HEAD",
        ):
            return COMMIT_1

        if args == (
            "rev-parse",
            "origin/main",
        ):
            return COMMIT_1

        if args == (
            "status",
            "--porcelain",
        ):
            return ""

        raise AssertionError(
            args
        )

    module.repository_preflight(
        REPO,
        expected_commit=COMMIT_1,
        expected_wrapper_sha256=(
            wrapper_sha
        ),
        expected_wrapper_test_sha256=(
            test_sha
        ),
        git_reader=git_reader,
    )


def test_repository_preflight_rejects_dirty_tree():
    wrapper_sha = module.sha256_file(
        WRAPPER_PATH
    )

    test_sha = module.sha256_file(
        Path(
            __file__
        )
    )

    def git_reader(
        repo,
        *args,
    ):
        if args in {
            (
                "rev-parse",
                "HEAD",
            ),
            (
                "rev-parse",
                "origin/main",
            ),
        }:
            return COMMIT_1

        if args == (
            "status",
            "--porcelain",
        ):
            return "M dirty"

        raise AssertionError(
            args
        )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="preflight",
    ):
        module.repository_preflight(
            REPO,
            expected_commit=COMMIT_1,
            expected_wrapper_sha256=(
                wrapper_sha
            ),
            expected_wrapper_test_sha256=(
                test_sha
            ),
            git_reader=git_reader,
        )


def test_discovery_empty_history_proves_genesis(
    tmp_path,
):
    assert module.discover_catalogue_chain(
        tmp_path,
        current_release_id=(
            RELEASE_1
        ),
    ) == ()


def test_discovery_accepts_one_genesis_catalogue(
    tmp_path,
):
    first = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_1,
        commit=COMMIT_1,
        payload=first,
    )

    chain = module.discover_catalogue_chain(
        tmp_path,
        current_release_id=(
            RELEASE_2
        ),
    )

    assert len(
        chain
    ) == 1

    assert chain[
        0
    ].catalogue_record[
        "catalogue_mode"
    ] == GENESIS


def test_discovery_accepts_valid_multirelease_chain(
    tmp_path,
):
    first = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    second = catalogue_payload(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
        previous=first,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_1,
        commit=COMMIT_1,
        payload=first,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_2,
        commit=COMMIT_2,
        payload=second,
    )

    chain = module.discover_catalogue_chain(
        tmp_path,
        current_release_id=(
            RELEASE_3
        ),
    )

    assert [
        item.release_id
        for item in chain
    ] == [
        RELEASE_1,
        RELEASE_2,
    ]


def test_discovery_rejects_current_release_catalogue(
    tmp_path,
):
    payload = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_1,
        commit=COMMIT_1,
        payload=payload,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="current release",
    ):
        module.discover_catalogue_chain(
            tmp_path,
            current_release_id=(
                RELEASE_1
            ),
        )


def test_discovery_rejects_later_catalogue(
    tmp_path,
):
    payload = catalogue_payload(
        release=RELEASE_3,
        snapshot=SNAPSHOT_3,
        commit=COMMIT_3,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_3,
        commit=COMMIT_3,
        payload=payload,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="later",
    ):
        module.discover_catalogue_chain(
            tmp_path,
            current_release_id=(
                RELEASE_2
            ),
        )


def test_discovery_rejects_multiple_catalogues_same_release(
    tmp_path,
):
    first = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    second = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_4,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_1,
        commit=COMMIT_1,
        payload=first,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_1,
        commit=COMMIT_4,
        payload=second,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="multiple canonical catalogues",
    ):
        module.discover_catalogue_chain(
            tmp_path,
            current_release_id=(
                RELEASE_2
            ),
        )


def test_discovery_rejects_missing_genesis_predecessor(
    tmp_path,
):
    first = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    second = catalogue_payload(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
        previous=first,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_2,
        commit=COMMIT_2,
        payload=second,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="GENESIS",
    ):
        module.discover_catalogue_chain(
            tmp_path,
            current_release_id=(
                RELEASE_3
            ),
        )


def test_discovery_rejects_broken_predecessor_sha(
    tmp_path,
):
    first = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    second = catalogue_payload(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
        previous=first,
    )

    changed = json.loads(
        second
    )

    changed[
        "previous_catalogue_sha256"
    ] = "9" * 64

    # Standalone audit accounting remains structurally valid, but the
    # exact historical predecessor binding no longer does.
    changed_payload = canonical_json(
        changed
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_1,
        commit=COMMIT_1,
        payload=first,
    )

    path = write_catalogue(
        tmp_path,
        release=RELEASE_2,
        commit=COMMIT_2,
        payload=changed_payload,
    )

    # The pure audit accepts the predecessor SHA as an identity field;
    # chain discovery is responsible for proving it against real history.
    audit_sequence_cache_catalogue(
        path.read_bytes()
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="predecessor SHA256",
    ):
        module.discover_catalogue_chain(
            tmp_path,
            current_release_id=(
                RELEASE_3
            ),
        )


def test_discovery_rejects_release_directory_symlink(
    tmp_path,
):
    target = (
        tmp_path
        / "real-release"
    )

    target.mkdir()

    os.symlink(
        target,
        tmp_path
        / RELEASE_1,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="release directory",
    ):
        module.discover_catalogue_chain(
            tmp_path,
            current_release_id=(
                RELEASE_2
            ),
        )


def test_discovery_rejects_catalogue_symlink(
    tmp_path,
):
    stage1 = stage1_path(
        tmp_path,
        RELEASE_1,
        COMMIT_1,
    )

    stage1.mkdir(
        parents=True
    )

    target = (
        tmp_path
        / "target.json"
    )

    target.write_bytes(
        b"{}\n"
    )

    os.symlink(
        target,
        stage1
        / module.CATALOGUE_NAME,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="non-symlink",
    ):
        module.discover_catalogue_chain(
            tmp_path,
            current_release_id=(
                RELEASE_2
            ),
        )


def test_discovery_rejects_directory_identity_mismatch(
    tmp_path,
):
    payload = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_1,
        commit=COMMIT_2,
        payload=payload,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="Git identity",
    ):
        module.discover_catalogue_chain(
            tmp_path,
            current_release_id=(
                RELEASE_2
            ),
        )


def test_write_catalogue_is_no_clobber_and_mode_0644(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    stage1.mkdir()

    payload = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    final, readback = (
        module.write_audited_catalogue(
            stage1_root=stage1,
            payload=payload,
            auditor=(
                audit_sequence_cache_catalogue
            ),
            prepublication_check=lambda:
                None,
            postpublication_check=lambda:
                None,
        )
    )

    assert readback == payload

    assert final.read_bytes() == payload

    assert stat.S_IMODE(
        final.stat().st_mode
    ) == 0o644

    assert not (
        stage1
        / module.CATALOGUE_TEMP_NAME
    ).exists()


def test_write_catalogue_refuses_existing_final(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    stage1.mkdir()

    final = (
        stage1
        / module.CATALOGUE_NAME
    )

    final.write_text(
        "existing\n",
        encoding="utf-8",
    )

    payload = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="already exists",
    ):
        module.write_audited_catalogue(
            stage1_root=stage1,
            payload=payload,
            auditor=(
                audit_sequence_cache_catalogue
            ),
            prepublication_check=lambda:
                None,
            postpublication_check=lambda:
                None,
        )

    assert final.read_text(
        encoding="utf-8"
    ) == "existing\n"


def test_write_catalogue_refuses_dangling_temporary_symlink(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    stage1.mkdir()

    os.symlink(
        stage1
        / "missing",
        stage1
        / module.CATALOGUE_TEMP_NAME,
    )

    payload = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="temporary",
    ):
        module.write_audited_catalogue(
            stage1_root=stage1,
            payload=payload,
            auditor=(
                audit_sequence_cache_catalogue
            ),
            prepublication_check=lambda:
                None,
            postpublication_check=lambda:
                None,
        )


def test_postpublication_failure_removes_only_final_link(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    stage1.mkdir()

    payload = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    def fail_post():
        raise module.MonthlySequenceCacheCatalogueExecutionError(
            "synthetic postpublication failure"
        )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="synthetic",
    ):
        module.write_audited_catalogue(
            stage1_root=stage1,
            payload=payload,
            auditor=(
                audit_sequence_cache_catalogue
            ),
            prepublication_check=lambda:
                None,
            postpublication_check=(
                fail_post
            ),
        )

    assert not (
        stage1
        / module.CATALOGUE_NAME
    ).exists()

    temporary = (
        stage1
        / module.CATALOGUE_TEMP_NAME
    )

    assert temporary.is_file()

    assert temporary.read_bytes() == payload


def test_execute_zero_fresh_genesis(
    tmp_path,
):
    stage1 = stage1_path(
        tmp_path,
        RELEASE_1,
        COMMIT_1,
    )

    stage1.mkdir(
        parents=True
    )

    context = zero_context(
        stage1,
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    def loader(
        **kwargs,
    ):
        return context

    result = (
        module.execute_monthly_sequence_cache_catalogue(
            repo=REPO,
            production_root=tmp_path,
            stage1_root=stage1,
            sequence_plan_record=(
                stage1
                / "unused-plan.json"
            ),
            fresh_target_manifest=(
                stage1
                / "unused-targets.tsv"
            ),
            execution_commit=COMMIT_1,
            completion_context_loader=(
                loader
            ),
        )
    )

    assert result.catalogue_mode == GENESIS

    assert result.catalogue_entry_count == 0

    assert result.current_acquisition_count == 0

    assert result.catalogue_path.is_file()

    record = audit_sequence_cache_catalogue(
        result.catalogue_path.read_bytes()
    )

    assert record[
        "catalogue_mode"
    ] == GENESIS


def test_execute_zero_fresh_chains_latest_valid_predecessor(
    tmp_path,
):
    first = catalogue_payload(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_1,
        commit=COMMIT_1,
        payload=first,
    )

    stage1 = stage1_path(
        tmp_path,
        RELEASE_2,
        COMMIT_2,
    )

    stage1.mkdir(
        parents=True
    )

    context = zero_context(
        stage1,
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
    )

    def loader(
        **kwargs,
    ):
        return context

    result = (
        module.execute_monthly_sequence_cache_catalogue(
            repo=REPO,
            production_root=tmp_path,
            stage1_root=stage1,
            sequence_plan_record=(
                stage1
                / "unused-plan.json"
            ),
            fresh_target_manifest=(
                stage1
                / "unused-targets.tsv"
            ),
            execution_commit=COMMIT_2,
            completion_context_loader=(
                loader
            ),
        )
    )

    assert result.catalogue_mode == CHAINED

    assert (
        result.previous_catalogue_release_id
        == RELEASE_1
    )

    assert (
        result.previous_catalogue_sha256
        == sha(
            first
        )
    )


def test_execute_refuses_existing_current_catalogue(
    tmp_path,
):
    stage1 = stage1_path(
        tmp_path,
        RELEASE_1,
        COMMIT_1,
    )

    stage1.mkdir(
        parents=True
    )

    (
        stage1
        / module.CATALOGUE_NAME
    ).write_text(
        "existing\n",
        encoding="utf-8",
    )

    context = zero_context(
        stage1,
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="already exists",
    ):
        module.execute_monthly_sequence_cache_catalogue(
            repo=REPO,
            production_root=tmp_path,
            stage1_root=stage1,
            sequence_plan_record=(
                stage1
                / "unused-plan.json"
            ),
            fresh_target_manifest=(
                stage1
                / "unused-targets.tsv"
            ),
            execution_commit=COMMIT_1,
            completion_context_loader=(
                lambda **kwargs:
                    context
            ),
        )


def test_execute_refuses_competing_same_release_catalogue(
    tmp_path,
):
    competing = catalogue_payload(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_4,
    )

    write_catalogue(
        tmp_path,
        release=RELEASE_2,
        commit=COMMIT_4,
        payload=competing,
    )

    stage1 = stage1_path(
        tmp_path,
        RELEASE_2,
        COMMIT_2,
    )

    stage1.mkdir(
        parents=True
    )

    context = zero_context(
        stage1,
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="current release",
    ):
        module.execute_monthly_sequence_cache_catalogue(
            repo=REPO,
            production_root=tmp_path,
            stage1_root=stage1,
            sequence_plan_record=(
                stage1
                / "unused-plan.json"
            ),
            fresh_target_manifest=(
                stage1
                / "unused-targets.tsv"
            ),
            execution_commit=COMMIT_2,
            completion_context_loader=(
                lambda **kwargs:
                    context
            ),
        )


def test_main_requires_explicit_authorization():
    with pytest.raises(
        module.MonthlySequenceCacheCatalogueExecutionError,
        match="explicit authorization",
    ):
        module.main(
            (
                "--expected-commit",
                COMMIT_1,
                "--expected-wrapper-sha256",
                "a" * 64,
                "--expected-wrapper-test-sha256",
                "b" * 64,
                "--production-root",
                "/tmp/production",
                "--stage1-root",
                "/tmp/stage1",
                "--sequence-plan-record",
                "/tmp/plan.json",
                "--fresh-target-manifest",
                "/tmp/targets.tsv",
            )
        )


def test_wrapper_contains_no_network_or_historical_bindings():
    text = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "requests",
        "urllib",
        "boto3",
        "google.cloud",
        "azure.storage",
        "/NGS/",
        "Rhys_wkdir",
        "SLURM_",
        "sbatch",
        "srun",
        "Project Finch",
        "finch-ncbi-datasets",
    )

    for token in forbidden:
        assert token not in text


def test_authoritative_storage_is_pinned_not_claimed_as_transport():
    text = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        "monthly_authoritative_storage.py"
        in text
    )

    assert "boto3" not in text
    assert "upload_file" not in text
    assert "put_object" not in text
