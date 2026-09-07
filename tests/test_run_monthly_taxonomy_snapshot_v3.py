from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]

WRAPPER = (
    ROOT
    / "validation/selector-v1/"
      "run_monthly_taxonomy_snapshot_v3.py"
)

V2_WRAPPER = (
    ROOT
    / "validation/selector-v1/"
      "run_monthly_taxonomy_snapshot_v2.py"
)

V2_TEST = (
    ROOT
    / "tests/"
      "test_run_monthly_taxonomy_snapshot_v2.py"
)


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


spec = (
    importlib.util
    .spec_from_file_location(
        "_test_stage7_v3",
        WRAPPER,
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
    spec.name
] = module

spec.loader.exec_module(
    module
)


SOURCE_COMMIT = (
    "abefc3b70d7fe7e079eeb52b762542dae565edf6"
)

TAXONOMY_COMMIT = (
    "0123456789abcdef0123456789abcdef01234567"
)


class FakeStage7V1:
    @staticmethod
    def _canonical_json(
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
            "ascii"
        )


class FakeStage7V2:
    @staticmethod
    def build_completion_receipt_v2(
        stage7_v1,
        **kwargs,
    ):
        del stage7_v1
        del kwargs

        value = {
            "schema_version":
                "bacselect-monthly-taxonomy-snapshot-completion-v2",

            "status":
                "TAXONOMY_SNAPSHOT_EXECUTION_COMPLETE",

            "source_production_commit":
                SOURCE_COMMIT,

            "legacy_support_execution_git_commit":
                SOURCE_COMMIT,

            "taxonomy_execution_commit":
                TAXONOMY_COMMIT,

            "taxonomy_snapshot_id":
                "taxonomy-id",

            "authoritative_storage_manifest_sha256":
                "1" * 64,

            "authoritative_storage_manifest_key":
                "manifests/monthly/x",

            "authoritative_storage_receipt_sha256":
                "2" * 64,

            "authoritative_storage_receipt_key":
                "receipts/monthly/x",

            "authoritative_verified_object_count":
                8,
        }

        return (
            FakeStage7V1
            ._canonical_json(
                value
            )
        )


def test_frozen_v2_dependency_identities():
    assert (
        sha256_file(
            V2_WRAPPER
        )
        == module.STAGE7_V2_WRAPPER_SHA256
    )

    assert (
        sha256_file(
            V2_TEST
        )
        == module.STAGE7_V2_TEST_SHA256
    )


def test_v3_completion_reclassifies_local_storage():
    payload = (
        module
        .build_completion_receipt_v3(
            FakeStage7V2,
            FakeStage7V1,
        )
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    assert (
        record[
            "schema_version"
        ]
        == module.COMPLETION_SCHEMA
    )

    assert (
        record[
            "status"
        ]
        == module.COMPLETION_STATUS
    )

    assert (
        record[
            "local_cas_status"
        ]
        == module.LOCAL_CAS_STATUS
    )

    assert (
        record[
            "local_cas_manifest_sha256"
        ]
        == "1" * 64
    )

    assert (
        record[
            "local_cas_receipt_sha256"
        ]
        == "2" * 64
    )

    assert (
        record[
            "local_cas_verified_object_count"
        ]
        == 8
    )

    assert (
        record[
            "durable_archive_boundary"
        ]
        == module.DURABLE_ARCHIVE_BOUNDARY
    )


def test_v3_completion_exposes_no_authoritative_storage_claim():
    payload = (
        module
        .build_completion_receipt_v3(
            FakeStage7V2,
            FakeStage7V1,
        )
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    assert not any(
        key.startswith(
            "authoritative_storage_"
        )
        for key in record
    )

    assert (
        "authoritative_verified_object_count"
        not in record
    )


def test_v3_audit_is_byte_exact():
    payload = (
        module
        .build_completion_receipt_v3(
            FakeStage7V2,
            FakeStage7V1,
        )
    )

    observed = (
        module
        .audit_completion_receipt_v3(
            FakeStage7V2,
            FakeStage7V1,
            payload,
        )
    )

    assert (
        observed[
            "local_cas_status"
        ]
        == module.LOCAL_CAS_STATUS
    )

    changed = json.loads(
        payload.decode(
            "ascii"
        )
    )

    changed[
        "durable_archive_boundary"
    ] = "WRONG"

    changed_payload = (
        FakeStage7V1
        ._canonical_json(
            changed
        )
    )

    with pytest.raises(
        module.MonthlyTaxonomyV3ExecutionError,
        match="receipt changed",
    ):
        (
            module
            .audit_completion_receipt_v3(
                FakeStage7V2,
                FakeStage7V1,
                changed_payload,
            )
        )


def test_v3_never_calls_v2_execution_entrypoint():
    tree = ast.parse(
        WRAPPER.read_text(
            encoding="utf-8"
        )
    )

    forbidden = {
        "execute_monthly_taxonomy_snapshot_v2",
        "execute_monthly_chromosome_integrity_v2",
        "evaluate_population_v2",
    }

    called = set()

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if isinstance(
            node.func,
            ast.Attribute,
        ):
            called.add(
                node.func.attr
            )

        elif isinstance(
            node.func,
            ast.Name,
        ):
            called.add(
                node.func.id
            )

    assert forbidden.isdisjoint(
        called
    )


def test_cli_uses_local_cas_not_authoritative_root():
    tree = ast.parse(
        WRAPPER.read_text(
            encoding="utf-8"
        )
    )

    options = []

    for node in ast.walk(
        tree
    ):
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr
            == "add_argument"
            and node.args
            and isinstance(
                node.args[0],
                ast.Constant,
            )
        ):
            options.append(
                node.args[0].value
            )

    assert (
        "--local-cas-root"
        in options
    )

    assert (
        "--authoritative-root"
        not in options
    )


def test_main_requires_real_execution_authorization(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda:
            SimpleNamespace(
                authorize_real_execution=False
            ),
    )

    with pytest.raises(
        module.MonthlyTaxonomyV3ExecutionError,
        match="explicit authorization",
    ):
        module.main()


def test_v3_support_receives_local_cas_as_legacy_storage_parameter():
    tree = ast.parse(
        WRAPPER.read_text(
            encoding="utf-8"
        )
    )

    calls = []

    for node in ast.walk(
        tree
    ):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr
            == "execute_monthly_taxonomy_support"
        ):
            calls.append(node)

    assert len(calls) == 1

    keyword = next(
        (
            item
            for item in calls[0].keywords
            if item.arg == "authoritative_root"
        ),
        None,
    )

    assert keyword is not None
    assert isinstance(keyword.value, ast.Name)
    assert keyword.value.id == "local_cas"


def test_v3_scientific_core_remains_frozen():
    expected = {
        (
            ROOT
            / "src/bacselect/"
              "monthly_taxonomy_snapshot.py"
        ):
            (
                "3e82dfeab3778a29bc4be9f04234c612"
                "44b30b284003b67d6114b45051a5816e"
            ),
        (
            ROOT
            / "src/bacselect/"
              "monthly_taxonomy_snapshot_execution.py"
        ):
            (
                "4cb58becd9b1dc6428f0614262c0d55c"
                "05673395dc41acdf358ff251d990e263"
            ),
        (
            ROOT
            / "src/bacselect/source_taxonomy.py"
        ):
            (
                "9c8c4149c5db2a757e8c201a6523bdb1"
                "13511b5f72a4dd2893572dd8c7928e4d"
            ),
        (
            ROOT
            / "src/bacselect/"
              "source_taxonomy_acquisition.py"
        ):
            (
                "c76f04ab3ab0149d5ede2e1069e547e9"
                "9588ebba98f6ac1aac0ee5727015cef9"
            ),
    }

    for path, identity in expected.items():
        assert sha256_file(path) == identity


def test_v3_completion_retains_nonstorage_v2_provenance(
    monkeypatch,
):
    original = (
        FakeStage7V2
        .build_completion_receipt_v2
    )

    def richer(
        stage7_v1,
        **kwargs,
    ):
        record = json.loads(
            original(
                stage7_v1,
                **kwargs,
            ).decode(
                "ascii"
            )
        )

        record.update(
            {
                "chromosome_execution_commit":
                    "a" * 40,
                "biosample_execution_commit":
                    "b" * 40,
                "source_truth_execution_commit":
                    "c" * 40,
                "cache_execution_commit":
                    "d" * 40,
                "completion_execution_commit":
                    "e" * 40,
            }
        )

        return (
            FakeStage7V1
            ._canonical_json(
                record
            )
        )

    monkeypatch.setattr(
        FakeStage7V2,
        "build_completion_receipt_v2",
        richer,
    )

    payload = (
        module
        .build_completion_receipt_v3(
            FakeStage7V2,
            FakeStage7V1,
        )
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    assert (
        record[
            "chromosome_execution_commit"
        ]
        == "a" * 40
    )

    assert (
        record[
            "biosample_execution_commit"
        ]
        == "b" * 40
    )

    assert (
        record[
            "source_truth_execution_commit"
        ]
        == "c" * 40
    )

    assert (
        record[
            "cache_execution_commit"
        ]
        == "d" * 40
    )

    assert (
        record[
            "completion_execution_commit"
        ]
        == "e" * 40
    )
