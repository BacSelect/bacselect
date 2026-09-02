from __future__ import annotations

import hashlib
import importlib.util
import sys

from pathlib import Path

import pytest

from bacselect import monthly_sequence_cache_catalogue as cache_v1
from bacselect import monthly_sequence_cache_catalogue_v2 as cache_v2


ROOT = Path(
    __file__
).resolve().parents[
    1
]

WRAPPER_PATH = (
    ROOT
    / "validation"
    / "selector-v1"
    / "run_monthly_sequence_cache_catalogue_v2.py"
)

CORE_TEST_PATH = (
    ROOT
    / "tests"
    / "test_monthly_sequence_cache_catalogue_v2.py"
)


def load_module(
    path,
    name,
):
    spec = (
        importlib.util
        .spec_from_file_location(
            name,
            path,
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


module = load_module(
    WRAPPER_PATH,
    "_cache_v2_wrapper_under_test",
)

fixture = load_module(
    CORE_TEST_PATH,
    "_cache_v2_core_fixture_for_wrapper",
)


def make_current_values():
    return fixture.make_current()


def make_core_kwargs(
    values,
    *,
    previous=None,
):
    return fixture.build_kwargs(
        values,
        previous=previous,
    )


def make_context(
    stage1_root,
):
    values = (
        make_current_values()
    )

    kwargs = (
        make_core_kwargs(
            values
        )
    )

    return (
        module.AuditedCompletionV2Context(
            release_id=(
                kwargs[
                    "release_id"
                ]
            ),
            source_snapshot_id=(
                kwargs[
                    "source_snapshot_id"
                ]
            ),
            stage1_root=Path(
                stage1_root
            ),
            completion_payload=(
                kwargs[
                    "sequence_acquisition_completion_payload"
                ]
            ),
            completion_record={},
            batch_evidence=tuple(
                kwargs[
                    "current_batches"
                ]
            ),
            fresh_acquisition_count=(
                len(
                    values[
                        "targets"
                    ]
                )
            ),
            source_production_commit=(
                kwargs[
                    "source_production_commit"
                ]
            ),
            completion_execution_commit=(
                kwargs[
                    "completion_execution_commit"
                ]
            ),
        ),
        values,
        kwargs,
    )


def write_catalogue(
    root,
    *,
    release,
    commit,
    name,
    payload,
):
    directory = (
        Path(
            root
        )
        / release
        / "production"
        / commit
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        directory
        / name
    )

    path.write_bytes(
        payload
    )

    return path


def test_distinct_v2_artifact_names():
    assert (
        module.CATALOGUE_V1_NAME
        == "sequence-cache-catalogue.json"
    )

    assert (
        module.CATALOGUE_V2_NAME
        == "sequence-cache-catalogue-v2.json"
    )

    assert (
        module.CATALOGUE_V2_TEMP_NAME
        == ".sequence-cache-catalogue-v2.json.tmp"
    )


def test_wrapper_binds_frozen_core_identity():
    assert (
        module.EXPECTED_CACHE_V2_CORE_SHA256
        == (
            "1a7f9c2015c73e0cbada26064ad137fd"
            "6468ce5592dd5c518095d8f20d2937ca"
        )
    )


def test_history_accepts_single_v1_catalogue(
    tmp_path,
):
    payload, _, _ = (
        fixture.make_legacy_v1_catalogue(
            accession="GCA_900000001.1",
            biosample="SAMN90000001",
        )
    )

    commit = fixture.fixture.COMMIT

    write_catalogue(
        tmp_path,
        release="2026.08",
        commit=commit,
        name=(
            module.CATALOGUE_V1_NAME
        ),
        payload=payload,
    )

    chain = (
        module.discover_catalogue_chain_v2(
            tmp_path,
            current_release_id="2026.09",
        )
    )

    assert len(
        chain
    ) == 1

    assert (
        chain[
            0
        ].release_id
        == "2026.08"
    )

    assert (
        chain[
            0
        ].catalogue_record[
            "schema_version"
        ]
        == cache_v1
        .MONTHLY_SEQUENCE_CACHE_CATALOGUE_SCHEMA
    )


def test_history_accepts_single_v2_catalogue(
    tmp_path,
):
    values = (
        make_current_values()
    )

    kwargs = (
        make_core_kwargs(
            values
        )
    )

    payload = (
        cache_v2
        .serialize_sequence_cache_catalogue_v2(
            **kwargs
        )
    )

    commit = kwargs[
        "cache_execution_commit"
    ]

    write_catalogue(
        tmp_path,
        release=(
            kwargs[
                "release_id"
            ]
        ),
        commit=commit,
        name=(
            module.CATALOGUE_V2_NAME
        ),
        payload=payload,
    )

    chain = (
        module.discover_catalogue_chain_v2(
            tmp_path,
            current_release_id="2032.05",
        )
    )

    assert len(
        chain
    ) == 1

    assert (
        chain[
            0
        ].catalogue_record[
            "schema_version"
        ]
        == cache_v2
        .MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA
    )


def test_history_rejects_v1_and_v2_same_commit(
    tmp_path,
):
    values = (
        make_current_values()
    )

    kwargs = (
        make_core_kwargs(
            values
        )
    )

    v2_payload = (
        cache_v2
        .serialize_sequence_cache_catalogue_v2(
            **kwargs
        )
    )

    v1_payload, _, _ = (
        fixture.make_legacy_v1_catalogue(
            accession="GCA_900000001.1",
            biosample="SAMN90000001",
        )
    )

    commit = kwargs[
        "cache_execution_commit"
    ]

    write_catalogue(
        tmp_path,
        release=(
            kwargs[
                "release_id"
            ]
        ),
        commit=commit,
        name=(
            module.CATALOGUE_V2_NAME
        ),
        payload=v2_payload,
    )

    write_catalogue(
        tmp_path,
        release=(
            kwargs[
                "release_id"
            ]
        ),
        commit=commit,
        name=(
            module.CATALOGUE_V1_NAME
        ),
        payload=v1_payload,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueV2ExecutionError,
        match="both cache-v1 and cache-v2",
    ):
        module.discover_catalogue_chain_v2(
            tmp_path,
            current_release_id="2032.05",
        )


def test_history_rejects_multiple_catalogues_one_release(
    tmp_path,
    monkeypatch,
):
    release = "2026.08"

    first_commit = (
        "a"
        * 40
    )

    second_commit = (
        "b"
        * 40
    )

    first_payload = b"first catalogue\n"
    second_payload = b"second catalogue\n"

    write_catalogue(
        tmp_path,
        release=release,
        commit=first_commit,
        name=(
            module.CATALOGUE_V2_NAME
        ),
        payload=first_payload,
    )

    write_catalogue(
        tmp_path,
        release=release,
        commit=second_commit,
        name=(
            module.CATALOGUE_V2_NAME
        ),
        payload=second_payload,
    )

    records = {
        first_payload:
            {
                "cache_execution_commit":
                    first_commit,
                "catalogue_mode":
                    cache_v2.GENESIS,
                "previous_catalogue_release_id":
                    None,
                "previous_catalogue_sha256":
                    None,
                "release_id":
                    release,
                "schema_version":
                    (
                        cache_v2
                        .MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA
                    ),
            },
        second_payload:
            {
                "cache_execution_commit":
                    second_commit,
                "catalogue_mode":
                    cache_v2.GENESIS,
                "previous_catalogue_release_id":
                    None,
                "previous_catalogue_sha256":
                    None,
                "release_id":
                    release,
                "schema_version":
                    (
                        cache_v2
                        .MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA
                    ),
            },
    }

    monkeypatch.setattr(
        module,
        "_audit_catalogue_payload",
        lambda payload:
            dict(
                records[
                    payload
                ]
            ),
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueV2ExecutionError,
        match="multiple canonical catalogues exist",
    ):
        module.discover_catalogue_chain_v2(
            tmp_path,
            current_release_id="2026.09",
        )



def test_history_rejects_current_without_include(
    tmp_path,
):
    values = (
        make_current_values()
    )

    kwargs = (
        make_core_kwargs(
            values
        )
    )

    payload = (
        cache_v2
        .serialize_sequence_cache_catalogue_v2(
            **kwargs
        )
    )

    write_catalogue(
        tmp_path,
        release=(
            kwargs[
                "release_id"
            ]
        ),
        commit=(
            kwargs[
                "cache_execution_commit"
            ]
        ),
        name=(
            module.CATALOGUE_V2_NAME
        ),
        payload=payload,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueV2ExecutionError,
        match="current release",
    ):
        module.discover_catalogue_chain_v2(
            tmp_path,
            current_release_id=(
                kwargs[
                    "release_id"
                ]
            ),
        )


def test_history_rejects_later_release(
    tmp_path,
):
    values = (
        make_current_values()
    )

    kwargs = (
        make_core_kwargs(
            values
        )
    )

    payload = (
        cache_v2
        .serialize_sequence_cache_catalogue_v2(
            **kwargs
        )
    )

    write_catalogue(
        tmp_path,
        release=(
            kwargs[
                "release_id"
            ]
        ),
        commit=(
            kwargs[
                "cache_execution_commit"
            ]
        ),
        name=(
            module.CATALOGUE_V2_NAME
        ),
        payload=payload,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueV2ExecutionError,
        match="later canonical",
    ):
        module.discover_catalogue_chain_v2(
            tmp_path,
            current_release_id="2032.03",
        )


def test_atomic_writer_round_trip(
    tmp_path,
):
    values = (
        make_current_values()
    )

    kwargs = (
        make_core_kwargs(
            values
        )
    )

    payload = (
        cache_v2
        .serialize_sequence_cache_catalogue_v2(
            **kwargs
        )
    )

    final, observed = (
        module.write_audited_catalogue_v2(
            stage1_root=(
                tmp_path
            ),
            payload=payload,
            auditor=(
                cache_v2
                .audit_sequence_cache_catalogue_v2
            ),
            prepublication_check=(
                lambda:
                    None
            ),
            postpublication_check=(
                lambda:
                    None
            ),
        )
    )

    assert (
        final.name
        == module.CATALOGUE_V2_NAME
    )

    assert observed == payload

    assert not (
        tmp_path
        / module.CATALOGUE_V2_TEMP_NAME
    ).exists()


def test_atomic_writer_refuses_existing_final(
    tmp_path,
):
    (
        tmp_path
        / module.CATALOGUE_V2_NAME
    ).write_bytes(
        b"existing"
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueV2ExecutionError,
        match="already exists",
    ):
        module.write_audited_catalogue_v2(
            stage1_root=(
                tmp_path
            ),
            payload=b"x",
            auditor=(
                lambda payload:
                    payload
            ),
            prepublication_check=(
                lambda:
                    None
            ),
            postpublication_check=(
                lambda:
                    None
            ),
        )


def test_execute_genesis_with_injected_audited_context(
    tmp_path,
):
    context_root = (
        tmp_path
        / "2032.04"
        / "production"
        / (
            "c"
            * 40
        )
    )

    context_root.mkdir(
        parents=True
    )

    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir()

    context, values, kwargs = (
        make_context(
            context_root
        )
    )

    def loader(
        **loader_kwargs,
    ):
        assert (
            loader_kwargs[
                "source_production_commit"
            ]
            == context.source_production_commit
        )

        assert (
            loader_kwargs[
                "completion_execution_commit"
            ]
            == context.completion_execution_commit
        )

        return context

    result = (
        module
        .execute_monthly_sequence_cache_catalogue_v2(
            repo=repo,
            production_root=(
                tmp_path
            ),
            stage1_root=(
                context_root
            ),
            sequence_plan_record=(
                tmp_path
                / "unused-plan"
            ),
            fresh_target_manifest=(
                tmp_path
                / "unused-targets"
            ),
            source_production_commit=(
                context.source_production_commit
            ),
            completion_execution_commit=(
                context.completion_execution_commit
            ),
            cache_execution_commit=(
                kwargs[
                    "cache_execution_commit"
                ]
            ),
            completion_context_loader=(
                loader
            ),
            preflight=(
                lambda *args, **kw:
                    None
            ),
        )
    )

    assert (
        result.catalogue_mode
        == cache_v2.GENESIS
    )

    assert (
        result.catalogue_path
        == (
            context_root
            / module.CATALOGUE_V2_NAME
        ).resolve()
    )

    payload = (
        result.catalogue_path
        .read_bytes()
    )

    audited = (
        cache_v2
        .audit_sequence_cache_catalogue_v2(
            payload
        )
    )

    assert (
        audited[
            "cache_execution_commit"
        ]
        == kwargs[
            "cache_execution_commit"
        ]
    )


def test_execute_rejects_context_commit_mismatch(
    tmp_path,
):
    context_root = (
        tmp_path
        / "2032.04"
        / "production"
        / (
            "c"
            * 40
        )
    )

    context_root.mkdir(
        parents=True
    )

    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir()

    context, _, kwargs = (
        make_context(
            context_root
        )
    )

    changed = (
        module
        .AuditedCompletionV2Context(
            release_id=(
                context.release_id
            ),
            source_snapshot_id=(
                context.source_snapshot_id
            ),
            stage1_root=(
                context.stage1_root
            ),
            completion_payload=(
                context.completion_payload
            ),
            completion_record=(
                context.completion_record
            ),
            batch_evidence=(
                context.batch_evidence
            ),
            fresh_acquisition_count=(
                context.fresh_acquisition_count
            ),
            source_production_commit=(
                "d"
                * 40
            ),
            completion_execution_commit=(
                context.completion_execution_commit
            ),
        )
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueV2ExecutionError,
        match="source-production",
    ):
        module.execute_monthly_sequence_cache_catalogue_v2(
            repo=repo,
            production_root=(
                tmp_path
            ),
            stage1_root=(
                context_root
            ),
            sequence_plan_record=(
                tmp_path
                / "unused-plan"
            ),
            fresh_target_manifest=(
                tmp_path
                / "unused-targets"
            ),
            source_production_commit=(
                context.source_production_commit
            ),
            completion_execution_commit=(
                context.completion_execution_commit
            ),
            cache_execution_commit=(
                kwargs[
                    "cache_execution_commit"
                ]
            ),
            completion_context_loader=(
                lambda **kw:
                    changed
            ),
            preflight=(
                lambda *args, **kw:
                    None
            ),
        )


def test_wrapper_has_no_network_calls():
    text = (
        WRAPPER_PATH
        .read_text(
            encoding="utf-8"
        )
    ).lower()

    for token in (
        "requests.",
        "urllib.",
        "urlopen(",
        "curl ",
        "wget ",
    ):
        assert token not in text


def test_wrapper_does_not_execute_recovery():
    text = (
        WRAPPER_PATH
        .read_text(
            encoding="utf-8"
        )
    )

    forbidden = (
        "execute_monthly_missing_datasets",
        "execute_monthly_post_snapshot",
        "run_monthly_missing_datasets",
        "run_monthly_post_snapshot",
    )

    for token in forbidden:
        assert token not in text


def test_wrapper_invokes_full_completion_v2_auditor():
    text = (
        WRAPPER_PATH
        .read_text(
            encoding="utf-8"
        )
    )

    assert (
        ".audit_sequence_acquisition_completion_v2_record("
        in text
    )

    assert (
        "**contract_kwargs"
        in text
    )


def test_wrapper_resolves_authority_independently():
    text = (
        WRAPPER_PATH
        .read_text(
            encoding="utf-8"
        )
    )

    assert (
        ".resolve_authoritative_sequence_batches("
        in text
    )


def test_wrapper_passes_raw_snapshot_report_to_recovery():
    text = (
        WRAPPER_PATH
        .read_text(
            encoding="utf-8"
        )
    )

    assert (
        "source_snapshot_report = ("
        in text
    )

    assert (
        "/ v1_execution.RAW_RESPONSE_NAME"
        in text
    )

    assert (
        "source_snapshot_report=("
        in text
    )


def test_history_accepts_mixed_v1_to_v2_chain(
    tmp_path,
):
    legacy_payload, _, _ = (
        fixture.make_legacy_v1_catalogue(
            accession="GCA_900000001.1",
            biosample="SAMN90000001",
        )
    )

    legacy_record = (
        cache_v1
        .audit_sequence_cache_catalogue(
            legacy_payload
        )
    )

    legacy_path = write_catalogue(
        tmp_path,
        release=(
            legacy_record[
                "release_id"
            ]
        ),
        commit=(
            legacy_record[
                "origin_git_commit"
            ]
        ),
        name=(
            module.CATALOGUE_V1_NAME
        ),
        payload=legacy_payload,
    )

    assert legacy_path.is_file()

    values = (
        make_current_values()
    )

    kwargs = (
        make_core_kwargs(
            values,
            previous=(
                legacy_payload
            ),
        )
    )

    v2_payload = (
        cache_v2
        .serialize_sequence_cache_catalogue_v2(
            **kwargs
        )
    )

    write_catalogue(
        tmp_path,
        release=(
            kwargs[
                "release_id"
            ]
        ),
        commit=(
            kwargs[
                "cache_execution_commit"
            ]
        ),
        name=(
            module.CATALOGUE_V2_NAME
        ),
        payload=v2_payload,
    )

    chain = (
        module.discover_catalogue_chain_v2(
            tmp_path,
            current_release_id="2032.05",
        )
    )

    assert len(
        chain
    ) == 2

    assert (
        chain[
            0
        ].catalogue_record[
            "schema_version"
        ]
        == cache_v1
        .MONTHLY_SEQUENCE_CACHE_CATALOGUE_SCHEMA
    )

    assert (
        chain[
            1
        ].catalogue_record[
            "schema_version"
        ]
        == cache_v2
        .MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA
    )

    assert (
        chain[
            1
        ].catalogue_record[
            "previous_catalogue_release_id"
        ]
        == chain[
            0
        ].release_id
    )

    assert (
        chain[
            1
        ].catalogue_record[
            "previous_catalogue_sha256"
        ]
        == chain[
            0
        ].catalogue_sha256
    )


def test_history_rejects_valid_catalogues_with_broken_predecessor_sha(
    tmp_path,
):
    visible_previous, _, _ = (
        fixture.make_legacy_v1_catalogue(
            accession="GCA_900000001.1",
            biosample="SAMN90000001",
        )
    )

    linked_previous, _, _ = (
        fixture.make_legacy_v1_catalogue(
            accession="GCA_900000002.1",
            biosample="SAMN90000002",
        )
    )

    visible_record = (
        cache_v1
        .audit_sequence_cache_catalogue(
            visible_previous
        )
    )

    linked_record = (
        cache_v1
        .audit_sequence_cache_catalogue(
            linked_previous
        )
    )

    assert (
        visible_record[
            "release_id"
        ]
        == linked_record[
            "release_id"
        ]
    )

    assert (
        visible_previous
        != linked_previous
    )

    write_catalogue(
        tmp_path,
        release=(
            visible_record[
                "release_id"
            ]
        ),
        commit=(
            visible_record[
                "origin_git_commit"
            ]
        ),
        name=(
            module.CATALOGUE_V1_NAME
        ),
        payload=visible_previous,
    )

    values = (
        make_current_values()
    )

    kwargs = (
        make_core_kwargs(
            values,
            previous=(
                linked_previous
            ),
        )
    )

    v2_payload = (
        cache_v2
        .serialize_sequence_cache_catalogue_v2(
            **kwargs
        )
    )

    write_catalogue(
        tmp_path,
        release=(
            kwargs[
                "release_id"
            ]
        ),
        commit=(
            kwargs[
                "cache_execution_commit"
            ]
        ),
        name=(
            module.CATALOGUE_V2_NAME
        ),
        payload=v2_payload,
    )

    with pytest.raises(
        module.MonthlySequenceCacheCatalogueV2ExecutionError,
        match="predecessor SHA256 link is broken",
    ):
        module.discover_catalogue_chain_v2(
            tmp_path,
            current_release_id="2032.05",
        )
