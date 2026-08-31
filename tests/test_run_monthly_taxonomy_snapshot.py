from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from bacselect import monthly_release_start
from bacselect import monthly_taxonomy_snapshot_execution as support


WRAPPER_PATH = (
    Path(
        __file__
    ).resolve().parents[
        1
    ]
    / "validation"
    / "selector-v1"
    / "run_monthly_taxonomy_snapshot.py"
)

COMMIT = (
    "a" * 40
)

WRAPPER_SHA = None


def load_module():
    name = (
        "_test_run_monthly_taxonomy_snapshot"
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            name,
            WRAPPER_PATH,
        )
    )

    assert spec is not None
    assert spec.loader is not None

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


module = load_module()

WRAPPER_SHA = hashlib.sha256(
    WRAPPER_PATH.read_bytes()
).hexdigest()


def canonical_json(
    value,
):
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def source_payload():
    raw = b'{"reports":[]}\n'

    snapshot_start = (
        "2026-09-01T00:17:00Z"
    )

    payload = canonical_json(
        {
            "architecture_schema_version":
                monthly_release_start
                .ARCHITECTURE_SCHEMA_VERSION,
            "expected_git_commit":
                COMMIT,
            "ncbi_datasets_environment_sha256":
                "1" * 64,
            "ncbi_datasets_version":
                "18.35.0",
            "raw_response_bytes":
                len(
                    raw
                ),
            "raw_response_sha256":
                hashlib.sha256(
                    raw
                ).hexdigest(),
            "release_id":
                "2026.09",
            "release_start_checkpoint_sha256":
                "3" * 64,
            "schema_version":
                monthly_release_start
                .SOURCE_SNAPSHOT_SCHEMA_VERSION,
            "selector":
                monthly_release_start
                .SELECTOR,
            "selector_version":
                monthly_release_start
                .SELECTOR_VERSION,
            "snapshot_start_utc":
                snapshot_start,
            "source_query_command":
                [
                    "datasets",
                    "summary",
                    "genome",
                    "taxon",
                    "2",
                ],
            "source_query_completed_utc":
                "2026-09-01T00:18:00Z",
            "source_query_specification":
                {},
            "source_query_started_utc":
                "2026-09-01T00:17:01Z",
            "source_snapshot_id":
                (
                    monthly_release_start
                    .source_snapshot_id_from_start(
                        snapshot_start
                    )
                ),
            "status":
                monthly_release_start
                .SOURCE_SNAPSHOT_STATUS,
        }
    )

    return payload, raw


def support_upstream():
    payload, raw = source_payload()

    return (
        support
        .build_authenticated_upstream_context(
            source_snapshot_record_payload=(
                payload
            ),
            raw_source_response_payload=(
                raw
            ),
            expected_release_id="2026.09",
            expected_source_snapshot_id=(
                "bacselect-source-2026.09-"
                "20260901T001700Z"
            ),
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            chromosome_integrity_decisions_sha256=(
                "4" * 64
            ),
            chromosome_integrity_record_sha256=(
                "5" * 64
            ),
            chromosome_integrity_completion_sha256=(
                "6" * 64
            ),
            execution_git_commit=COMMIT,
        )
    )


def support_result(
    workspace,
):
    return (
        support
        .MonthlyTaxonomySupportResult(
            workspace=(
                Path(
                    workspace
                ).resolve()
            ),
            release_id="2026.09",
            source_snapshot_id=(
                "bacselect-source-2026.09-"
                "20260901T001700Z"
            ),
            taxonomy_snapshot_id=(
                "bacselect-taxonomy-2026.09-"
                "20260901T003000Z-"
                + "7" * 64
            ),
            acquisition_provenance_sha256=(
                "8" * 64
            ),
            content_manifest_sha256=(
                "9" * 64
            ),
            record_sha256=(
                "b" * 64
            ),
            archive_sha256=(
                "c" * 64
            ),
            nodes_sha256=(
                "d" * 64
            ),
            merged_sha256=(
                "e" * 64
            ),
            delnodes_sha256=(
                "f" * 64
            ),
            authoritative_manifest_sha256=(
                "1" * 64
            ),
            authoritative_manifest_key=(
                "manifests/monthly/"
                "2026.09/production/"
                + COMMIT
                + "/taxonomy-snapshot/"
                "sha256/"
                + "1" * 64
                + ".json"
            ),
            authoritative_receipt_sha256=(
                "2" * 64
            ),
            authoritative_receipt_key=(
                "receipts/monthly/"
                "2026.09/production/"
                + COMMIT
                + "/taxonomy-snapshot/"
                "sha256/"
                + "2" * 64
                + ".json"
            ),
            authoritative_verified_object_count=8,
        )
    )


def write_stage_files(
    directory,
    result,
):
    directory.mkdir()

    expected = (
        module
        ._expected_stage_hashes(
            result
        )
    )

    for number, (
        name,
        _
    ) in enumerate(
        sorted(
            expected.items()
        ),
        start=1,
    ):
        payload = (
            f"{name}:{number}\n"
        ).encode()

        (
            directory
            / name
        ).write_bytes(
            payload
        )

        expected[
            name
        ] = hashlib.sha256(
            payload
        ).hexdigest()

    return expected


def result_for_directory(
    directory,
):
    base = support_result(
        directory
    )

    expected = {}

    for number, name in enumerate(
        sorted(
            support.LOCAL_STAGE_FILES
        ),
        start=1,
    ):
        payload = (
            f"{name}:{number}\n"
        ).encode()

        expected[
            name
        ] = hashlib.sha256(
            payload
        ).hexdigest()

    return (
        support
        .MonthlyTaxonomySupportResult(
            workspace=(
                Path(
                    directory
                ).resolve()
            ),
            release_id=(
                base.release_id
            ),
            source_snapshot_id=(
                base.source_snapshot_id
            ),
            taxonomy_snapshot_id=(
                base.taxonomy_snapshot_id
            ),
            acquisition_provenance_sha256=(
                expected[
                    support
                    .ACQUISITION_PROVENANCE_NAME
                ]
            ),
            content_manifest_sha256=(
                expected[
                    support
                    .CONTENT_MANIFEST_NAME
                ]
            ),
            record_sha256=(
                expected[
                    support.RECORD_NAME
                ]
            ),
            archive_sha256=(
                expected[
                    support.ARCHIVE_NAME
                ]
            ),
            nodes_sha256=(
                expected[
                    "nodes.dmp"
                ]
            ),
            merged_sha256=(
                expected[
                    "merged.dmp"
                ]
            ),
            delnodes_sha256=(
                expected[
                    "delnodes.dmp"
                ]
            ),
            authoritative_manifest_sha256=(
                expected[
                    support
                    .AUTHORITATIVE_MANIFEST_LOCAL_NAME
                ]
            ),
            authoritative_manifest_key=(
                base.authoritative_manifest_key
            ),
            authoritative_receipt_sha256=(
                expected[
                    support
                    .AUTHORITATIVE_RECEIPT_LOCAL_NAME
                ]
            ),
            authoritative_receipt_key=(
                base.authoritative_receipt_key
            ),
            authoritative_verified_object_count=8,
        )
    )


def materialize_support_workspace(
    directory,
):
    if not directory.is_dir():
        raise AssertionError(
            "support workspace must already exist"
        )

    if any(
        directory.iterdir()
    ):
        raise AssertionError(
            "support workspace must start empty"
        )

    for number, name in enumerate(
        sorted(
            support.LOCAL_STAGE_FILES
        ),
        start=1,
    ):
        (
            directory
            / name
        ).write_bytes(
            (
                f"{name}:{number}\n"
            ).encode()
        )

    return result_for_directory(
        directory
    )


def test_wrapper_result_is_frozen():
    value = (
        module
        .MonthlyTaxonomyExecutionResult(
            release_id="2026.09",
            source_snapshot_id="snapshot",
            taxonomy_snapshot_id="taxonomy",
            stage_path=Path(
                "/tmp/stage"
            ),
            completion_path=Path(
                "/tmp/completion"
            ),
            record_sha256="1" * 64,
            completion_sha256="2" * 64,
            authoritative_manifest_sha256=(
                "3" * 64
            ),
            authoritative_receipt_sha256=(
                "4" * 64
            ),
        )
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        value.release_id = "2026.10"


def test_wrapper_binds_frozen_method_and_support():
    assert (
        module.EXPECTED_EXECUTION_METHOD_SHA256
        == support.EXECUTION_METHOD_SHA256
    )

    assert (
        module.EXPECTED_EXECUTION_SUPPORT_SHA256
        == hashlib.sha256(
            Path(
                support.__file__
            ).read_bytes()
        ).hexdigest()
    )


def test_completion_schema_is_closed():
    assert len(
        module.COMPLETION_FIELDS
    ) == 26

    assert (
        "authoritative_verified_object_count"
        in module.COMPLETION_FIELDS
    )

    assert (
        "validation_wrapper_sha256"
        in module.COMPLETION_FIELDS
    )


def test_completion_roundtrip(
    tmp_path,
):
    result = support_result(
        tmp_path
    )

    payload = (
        module
        .build_completion_receipt(
            upstream=(
                support_upstream()
            ),
            support_result=(
                result
            ),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
        )
    )

    observed = (
        module
        .audit_completion_receipt(
            payload,
            upstream=(
                support_upstream()
            ),
            support_result=(
                result
            ),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
        )
    )

    assert set(
        observed
    ) == module.COMPLETION_FIELDS

    assert (
        observed[
            "schema_version"
        ]
        == module.COMPLETION_SCHEMA
    )

    assert (
        observed[
            "status"
        ]
        == module.COMPLETION_STATUS
    )

    assert (
        observed[
            "authoritative_verified_object_count"
        ]
        == 8
    )


def test_completion_rejects_extra_field(
    tmp_path,
):
    result = support_result(
        tmp_path
    )

    payload = (
        module
        .build_completion_receipt(
            upstream=(
                support_upstream()
            ),
            support_result=(
                result
            ),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
        )
    )

    record = json.loads(
        payload
    )

    record[
        "unexpected"
    ] = True

    with pytest.raises(
        module.MonthlyTaxonomyWrapperError,
        match="schema changed",
    ):
        module.audit_completion_receipt(
            canonical_json(
                record
            ),
            upstream=(
                support_upstream()
            ),
            support_result=(
                result
            ),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
        )


def test_completion_requires_exact_authoritative_count(
    tmp_path,
):
    base = support_result(
        tmp_path
    )

    changed = (
        support
        .MonthlyTaxonomySupportResult(
            **{
                **base.__dict__,
                "authoritative_verified_object_count":
                    7,
            }
        )
    )

    with pytest.raises(
        module.MonthlyTaxonomyWrapperError,
        match="verified-object count changed",
    ):
        module.build_completion_receipt(
            upstream=(
                support_upstream()
            ),
            support_result=(
                changed
            ),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
        )


def test_publish_stage_moves_exact_nine_file_bundle_by_hard_link(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "release"
    )

    stage1.mkdir()

    partial = (
        stage1
        / module.PARTIAL_NAME
    )

    partial.mkdir()

    result = (
        materialize_support_workspace(
            partial
        )
    )

    original = {
        name:
            (
                partial
                / name
            ).stat()
        for name in support.LOCAL_STAGE_FILES
    }

    final = (
        stage1
        / module.STAGE_NAME
    )

    stability = []

    published = (
        module.publish_stage(
            stage1_root=(
                stage1.resolve()
            ),
            partial=(
                partial.resolve()
            ),
            final=final,
            support_result=result,
            stability_check=(
                lambda:
                    stability.append(
                        "checked"
                    )
            ),
        )
    )

    assert published == final

    assert not partial.exists()

    assert {
        child.name
        for child in final.iterdir()
    } == support.LOCAL_STAGE_FILES

    for name in support.LOCAL_STAGE_FILES:
        observed = (
            final
            / name
        ).stat()

        assert (
            observed.st_dev
            == original[
                name
            ].st_dev
        )

        assert (
            observed.st_ino
            == original[
                name
            ].st_ino
        )

    assert stability == [
        "checked",
        "checked",
    ]


def test_publish_stage_refuses_existing_canonical_directory(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "release"
    )

    stage1.mkdir()

    partial = (
        stage1
        / module.PARTIAL_NAME
    )

    partial.mkdir()

    result = (
        materialize_support_workspace(
            partial
        )
    )

    final = (
        stage1
        / module.STAGE_NAME
    )

    final.mkdir()

    with pytest.raises(
        module.MonthlyTaxonomyWrapperError,
        match="already exists",
    ):
        module.publish_stage(
            stage1_root=(
                stage1.resolve()
            ),
            partial=(
                partial.resolve()
            ),
            final=final,
            support_result=result,
            stability_check=(
                lambda: None
            ),
        )

    assert partial.is_dir()
    assert final.is_dir()


def test_publish_stage_stability_failure_removes_owned_canonical_paths(
    tmp_path,
):
    stage1 = (
        tmp_path
        / "release"
    )

    stage1.mkdir()

    partial = (
        stage1
        / module.PARTIAL_NAME
    )

    partial.mkdir()

    result = (
        materialize_support_workspace(
            partial
        )
    )

    final = (
        stage1
        / module.STAGE_NAME
    )

    calls = []

    def stability():
        calls.append(
            "checked"
        )

        if len(
            calls
        ) == 2:
            raise RuntimeError(
                "synthetic stability failure"
            )

    with pytest.raises(
        RuntimeError,
        match="synthetic stability failure",
    ):
        module.publish_stage(
            stage1_root=(
                stage1.resolve()
            ),
            partial=(
                partial.resolve()
            ),
            final=final,
            support_result=result,
            stability_check=stability,
        )

    assert calls == [
        "checked",
        "checked",
    ]

    assert partial.is_dir()
    assert not final.exists()


def test_completion_publication_is_last_and_no_clobber(
    tmp_path,
):
    stage1 = tmp_path.resolve()

    payload = b'{"test":true}\n'

    calls = []

    path = (
        module.publish_completion(
            stage1_root=stage1,
            payload=payload,
            auditor=lambda value:
                calls.append(
                    (
                        "audit",
                        value,
                    )
                ),
            stability_check=lambda:
                calls.append(
                    (
                        "stability",
                        None,
                    )
                ),
        )
    )

    assert path == (
        stage1
        / module.COMPLETION_NAME
    )

    assert path.read_bytes() == payload

    assert not (
        stage1
        / module.COMPLETION_TEMP_NAME
    ).exists()

    assert calls == [
        (
            "audit",
            payload,
        ),
        (
            "stability",
            None,
        ),
        (
            "audit",
            payload,
        ),
        (
            "stability",
            None,
        ),
    ]


def test_completion_stability_failure_cleans_owned_paths(
    tmp_path,
):
    stage1 = tmp_path.resolve()

    calls = []

    def stability():
        calls.append(
            "checked"
        )

        if len(
            calls
        ) == 2:
            raise RuntimeError(
                "synthetic completion failure"
            )

    with pytest.raises(
        RuntimeError,
        match="synthetic completion failure",
    ):
        module.publish_completion(
            stage1_root=stage1,
            payload=b"{}\n",
            auditor=lambda value:
                value,
            stability_check=(
                stability
            ),
        )

    assert calls == [
        "checked",
        "checked",
    ]

    assert not (
        stage1
        / module.COMPLETION_NAME
    ).exists()

    assert not (
        stage1
        / module.COMPLETION_TEMP_NAME
    ).exists()


def test_owned_file_cleanup_refuses_replacement(
    tmp_path,
):
    path = (
        tmp_path
        / "owned"
    )

    path.write_bytes(
        b"first"
    )

    observed = path.stat()

    path.unlink()

    path.write_bytes(
        b"replacement"
    )

    with pytest.raises(
        module.MonthlyTaxonomyWrapperError,
        match="identity changed",
    ):
        module._remove_owned_file(
            path=path,
            device=(
                observed.st_dev
            ),
            inode=(
                observed.st_ino
            ),
            label="synthetic",
        )

    assert path.read_bytes() == b"replacement"


def test_stage6_count_derivation():
    rows = (
        {
            "chromosome_integrity_triggered":
                "1",
        },
        {
            "chromosome_integrity_triggered":
                "0",
        },
        {
            "chromosome_integrity_triggered":
                "1",
        },
    )

    assert (
        module._stage6_count(
            rows,
            field=(
                "chromosome_integrity_triggered"
            ),
            value="1",
        )
        == 2
    )


def test_wrapper_source_never_calls_stage6_execution_entrypoint():
    source = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        ".execute_monthly_chromosome_integrity("
        not in source
    )

    assert (
        "execute_monthly_chromosome_integrity("
        not in source
    )


def test_wrapper_has_no_historical_top_level_taxonomy_acquisition():
    source = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        "acquire_taxonomy_snapshot("
        not in source
    )


def test_parse_args_requires_explicit_paths_and_commit():
    args = module.parse_args(
        [
            "--repo",
            "/repo",
            "--production-root",
            "/production",
            "--stage1-root",
            "/release",
            "--authoritative-root",
            "/authoritative",
            "--execution-commit",
            COMMIT,
        ]
    )

    assert args.repo == Path(
        "/repo"
    )

    assert (
        args.authorize_real_execution
        is False
    )


def test_main_requires_real_execution_authorization():
    with pytest.raises(
        module.MonthlyTaxonomyWrapperError,
        match="explicit authorization",
    ):
        module.main(
            [
                "--repo",
                "/repo",
                "--production-root",
                "/production",
                "--stage1-root",
                "/release",
                "--authoritative-root",
                "/authoritative",
                "--execution-commit",
                COMMIT,
            ]
        )


def test_execute_refuses_existing_partial_before_support(
    tmp_path,
    monkeypatch,
):
    repo = (
        tmp_path
        / "repo"
    )

    production = (
        tmp_path
        / "production"
    )

    release = (
        production
        / "2026.09"
        / "production"
        / COMMIT
    )

    authoritative = (
        tmp_path
        / "authoritative"
    )

    repo.mkdir()
    release.mkdir(
        parents=True
    )
    authoritative.mkdir()

    (
        release
        / module.PARTIAL_NAME
    ).mkdir()

    initial = (
        module
        .AuthenticatedCurrentUpstream(
            support_upstream=(
                support_upstream()
            ),
            stage6_decisions_payload=b"d",
            stage6_record_payload=b"r",
            stage6_completion_payload=b"c",
            identity=(
                "identity",
            ),
        )
    )

    monkeypatch.setattr(
        module,
        "repository_preflight",
        lambda *args, **kwargs:
            repo.resolve(),
    )

    monkeypatch.setattr(
        module,
        "load_frozen_stage6_execution",
        lambda root:
            object(),
    )

    monkeypatch.setattr(
        module,
        "authenticate_current_upstream",
        lambda **kwargs:
            initial,
    )

    support_called = []

    monkeypatch.setattr(
        support,
        "execute_monthly_taxonomy_support",
        lambda **kwargs:
            support_called.append(
                kwargs
            ),
    )

    with pytest.raises(
        module.MonthlyTaxonomyWrapperError,
        match="partial taxonomy stage already exists",
    ):
        module.execute_monthly_taxonomy_snapshot(
            repo=repo,
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                release.resolve()
            ),
            authoritative_root=(
                authoritative.resolve()
            ),
            execution_commit=COMMIT,
        )

    assert support_called == []


def test_execute_orchestration_publishes_stage_then_completion(
    tmp_path,
    monkeypatch,
):
    repo = (
        tmp_path
        / "repo"
    )

    production = (
        tmp_path
        / "production"
    )

    release = (
        production
        / "2026.09"
        / "production"
        / COMMIT
    )

    authoritative = (
        tmp_path
        / "authoritative"
    )

    repo.mkdir()
    release.mkdir(
        parents=True
    )
    authoritative.mkdir()

    initial = (
        module
        .AuthenticatedCurrentUpstream(
            support_upstream=(
                support_upstream()
            ),
            stage6_decisions_payload=b"d",
            stage6_record_payload=b"r",
            stage6_completion_payload=b"c",
            identity=(
                "identity",
            ),
        )
    )

    authentications = []

    def authenticate(**kwargs):
        authentications.append(
            kwargs
        )

        return initial

    monkeypatch.setattr(
        module,
        "repository_preflight",
        lambda *args, **kwargs:
            repo.resolve(),
    )

    monkeypatch.setattr(
        module,
        "load_frozen_stage6_execution",
        lambda root:
            object(),
    )

    monkeypatch.setattr(
        module,
        "authenticate_current_upstream",
        authenticate,
    )

    def execute_support(
        **kwargs,
    ):
        workspace = kwargs[
            "workspace"
        ]

        result = (
            materialize_support_workspace(
                workspace
            )
        )

        kwargs[
            "upstream_stability_check"
        ]()

        kwargs[
            "upstream_stability_check"
        ]()

        return result

    monkeypatch.setattr(
        support,
        "execute_monthly_taxonomy_support",
        execute_support,
    )

    result = (
        module
        .execute_monthly_taxonomy_snapshot(
            repo=repo,
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                release.resolve()
            ),
            authoritative_root=(
                authoritative.resolve()
            ),
            execution_commit=COMMIT,
            opener=lambda *args, **kwargs:
                None,
        )
    )

    assert result.stage_path == (
        release
        / module.STAGE_NAME
    )

    assert result.stage_path.is_dir()

    assert result.completion_path == (
        release
        / module.COMPLETION_NAME
    )

    assert result.completion_path.is_file()

    assert not (
        release
        / module.PARTIAL_NAME
    ).exists()

    assert not (
        release
        / module.COMPLETION_TEMP_NAME
    ).exists()

    assert (
        len(
            authentications
        )
        >= 7
    )


def test_wrapper_mode_is_executable():
    mode = WRAPPER_PATH.stat().st_mode

    assert mode & 0o111


def test_no_caller_supplied_wrapper_identity_cli_options():
    source = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        "--expected-wrapper-sha256"
        not in source
    )

    assert (
        "--expected-wrapper-test-sha256"
        not in source
    )
