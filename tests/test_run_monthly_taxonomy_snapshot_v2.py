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

WRAPPER_PATH = (
    ROOT
    / "validation"
    / "selector-v1"
    / "run_monthly_taxonomy_snapshot_v2.py"
)

STAGE7_V1_PATH = (
    ROOT
    / "validation"
    / "selector-v1"
    / "run_monthly_taxonomy_snapshot.py"
)

STAGE6_V2_PATH = (
    ROOT
    / "validation"
    / "selector-v1"
    / "run_monthly_chromosome_integrity_v2.py"
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
        "_test_monthly_taxonomy_v2",
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
    spec.name
] = module

spec.loader.exec_module(
    module
)


SOURCE_COMMIT = (
    "abefc3b70d7fe7e079eeb52b762542dae565edf6"
)

COMPLETION_COMMIT = (
    "10f86bf8fe079b284d52128e1b29f977e2214f7f"
)

CACHE_COMMIT = (
    "80bd001371f430cfbc044f4a048f34689c2defdd"
)

SOURCE_TRUTH_COMMIT = (
    "6ff6bc3edb48489167571c9e0ef883992e0db4cf"
)

BIOSAMPLE_COMMIT = (
    "e8d01bb93eb496859aeb02ffd89695ad10032435"
)

CHROMOSOME_COMMIT = (
    "822441ae3f08e1ca31d286f10b6b4a0d5b7d9f64"
)

TAXONOMY_COMMIT = (
    "0123456789abcdef0123456789abcdef01234567"
)


class FakeStage7V1:
    @staticmethod
    def build_completion_receipt(
        *,
        upstream,
        support_result,
        validation_wrapper_sha256,
    ):
        del upstream
        del support_result

        return (
            json.dumps(
                {
                    "schema_version":
                        "bacselect-monthly-"
                        "taxonomy-snapshot-completion-v1",
                    "status":
                        "TAXONOMY_SNAPSHOT_EXECUTION_COMPLETE",
                    "release_id":
                        "2026.09",
                    "source_snapshot_id":
                        "bacselect-source-2026.09-"
                        "20260901T021652Z",
                    "execution_git_commit":
                        SOURCE_COMMIT,
                    "validation_wrapper_sha256":
                        validation_wrapper_sha256,
                    "chromosome_integrity_decisions_sha256":
                        "1" * 64,
                    "chromosome_integrity_record_sha256":
                        "2" * 64,
                    "chromosome_integrity_completion_sha256":
                        "3" * 64,
                    "taxonomy_snapshot_id":
                        "taxonomy-id",
                    "monthly_taxonomy_snapshot_record_sha256":
                        "4" * 64,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode(
            "ascii"
        )

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


def fake_upstream():
    stage4 = SimpleNamespace(
        completion_v2_sha256=(
            "5" * 64
        ),
        catalogue_sha256=(
            "6" * 64
        ),
        source_truth_completion_sha256=(
            "7" * 64
        ),
    )

    stage5 = SimpleNamespace(
        stage4_context=stage4,
        completion_sha256=(
            "8" * 64
        ),
    )

    return SimpleNamespace(
        support_upstream=object(),
        stage5_context=stage5,
    )


def completion_kwargs():
    return {
        "upstream":
            fake_upstream(),
        "support_result":
            object(),
        "validation_wrapper_sha256":
            "9" * 64,
        "source_production_commit":
            SOURCE_COMMIT,
        "completion_execution_commit":
            COMPLETION_COMMIT,
        "cache_execution_commit":
            CACHE_COMMIT,
        "source_truth_execution_commit":
            SOURCE_TRUTH_COMMIT,
        "biosample_execution_commit":
            BIOSAMPLE_COMMIT,
        "chromosome_execution_commit":
            CHROMOSOME_COMMIT,
        "taxonomy_execution_commit":
            TAXONOMY_COMMIT,
    }


def test_frozen_dependency_identities():
    assert (
        sha256_file(
            STAGE7_V1_PATH
        )
        == module.STAGE7_V1_WRAPPER_SHA256
        == (
            "e40d626e82992bdfb716e927945d72a7"
            "b337a981cf54942353a43b43e02df5bc"
        )
    )

    assert (
        sha256_file(
            STAGE6_V2_PATH
        )
        == module.STAGE6_V2_WRAPPER_SHA256
        == (
            "df5ba50c5b7f3df2c5a823ddd35d5727"
            "3b61c4a1e1bc145bb34fc7e23a9b7ec8"
        )
    )


def test_wrapper_never_executes_or_reevaluates_stage6():
    tree = ast.parse(
        WRAPPER_PATH.read_text(
            encoding="utf-8"
        )
    )

    forbidden = {
        "execute_monthly_chromosome_integrity",
        "execute_monthly_chromosome_integrity_v2",
        "evaluate_population_v2",
    }

    observed = set()

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        function = node.func

        if isinstance(
            function,
            ast.Attribute,
        ):
            observed.add(
                function.attr
            )

        elif isinstance(
            function,
            ast.Name,
        ):
            observed.add(
                function.id
            )

    assert forbidden.isdisjoint(
        observed
    )


def test_support_legacy_commit_is_source_production_commit():
    tree = ast.parse(
        WRAPPER_PATH.read_text(
            encoding="utf-8"
        )
    )

    matching_calls = []

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        function = node.func

        if (
            isinstance(
                function,
                ast.Attribute,
            )
            and function.attr
            == "build_authenticated_upstream_context"
        ):
            matching_calls.append(
                node
            )

    assert len(
        matching_calls
    ) == 1

    call = matching_calls[
        0
    ]

    keyword = next(
        (
            value
            for value in call.keywords
            if value.arg
            == "execution_git_commit"
        ),
        None,
    )

    assert keyword is not None

    assert isinstance(
        keyword.value,
        ast.Name,
    )

    assert (
        keyword.value.id
        == "source_production_commit"
    )


def test_completion_v2_disambiguates_all_execution_identities():
    payload = (
        module
        .build_completion_receipt_v2(
            FakeStage7V1,
            **completion_kwargs(),
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
        "execution_git_commit"
        not in record
    )

    assert (
        record[
            "source_production_commit"
        ]
        == SOURCE_COMMIT
    )

    assert (
        record[
            "legacy_support_execution_git_commit"
        ]
        == SOURCE_COMMIT
    )

    assert (
        record[
            "completion_execution_commit"
        ]
        == COMPLETION_COMMIT
    )

    assert (
        record[
            "cache_execution_commit"
        ]
        == CACHE_COMMIT
    )

    assert (
        record[
            "source_truth_execution_commit"
        ]
        == SOURCE_TRUTH_COMMIT
    )

    assert (
        record[
            "biosample_execution_commit"
        ]
        == BIOSAMPLE_COMMIT
    )

    assert (
        record[
            "chromosome_execution_commit"
        ]
        == CHROMOSOME_COMMIT
    )

    assert (
        record[
            "taxonomy_execution_commit"
        ]
        == TAXONOMY_COMMIT
    )

    assert (
        record[
            "sequence_acquisition_completion_sha256"
        ]
        == "5" * 64
    )

    assert (
        record[
            "sequence_cache_catalogue_sha256"
        ]
        == "6" * 64
    )

    assert (
        record[
            "source_truth_completion_sha256"
        ]
        == "7" * 64
    )

    assert (
        record[
            "biosample_completion_sha256"
        ]
        == "8" * 64
    )

    # Existing Stage 7-v1 evidence remains
    # present in the v2 receipt.
    assert (
        record[
            "chromosome_integrity_decisions_sha256"
        ]
        == "1" * 64
    )

    assert (
        record[
            "chromosome_integrity_record_sha256"
        ]
        == "2" * 64
    )

    assert (
        record[
            "chromosome_integrity_completion_sha256"
        ]
        == "3" * 64
    )


def test_completion_v2_audits_exact_bytes():
    kwargs = (
        completion_kwargs()
    )

    payload = (
        module
        .build_completion_receipt_v2(
            FakeStage7V1,
            **kwargs,
        )
    )

    record = (
        module
        .audit_completion_receipt_v2(
            FakeStage7V1,
            payload,
            **kwargs,
        )
    )

    assert (
        record[
            "taxonomy_execution_commit"
        ]
        == TAXONOMY_COMMIT
    )

    changed = json.loads(
        payload.decode(
            "ascii"
        )
    )

    changed[
        "taxonomy_execution_commit"
    ] = (
        "f" * 40
    )

    changed_payload = (
        FakeStage7V1
        ._canonical_json(
            changed
        )
    )

    with pytest.raises(
        module.MonthlyTaxonomyV2ExecutionError,
        match=(
            "taxonomy completion-v2 "
            "receipt changed"
        ),
    ):
        (
            module
            .audit_completion_receipt_v2(
                FakeStage7V1,
                changed_payload,
                **kwargs,
            )
        )


def test_completion_v2_rejects_ambiguous_execution_commit(
    monkeypatch,
):
    kwargs = (
        completion_kwargs()
    )

    value = {
        "schema_version":
            module.COMPLETION_SCHEMA,
        "status":
            module.COMPLETION_STATUS,
        "source_production_commit":
            SOURCE_COMMIT,
        "legacy_support_execution_git_commit":
            SOURCE_COMMIT,
        "execution_git_commit":
            TAXONOMY_COMMIT,
    }

    payload = (
        FakeStage7V1
        ._canonical_json(
            value
        )
    )

    monkeypatch.setattr(
        module,
        "build_completion_receipt_v2",
        lambda *args, **inner_kwargs:
            payload,
    )

    with pytest.raises(
        module.MonthlyTaxonomyV2ExecutionError,
        match=(
            "reintroduced ambiguous "
            "execution_git_commit"
        ),
    ):
        (
            module
            .audit_completion_receipt_v2(
                FakeStage7V1,
                payload,
                **kwargs,
            )
        )


def test_completion_v2_rejects_legacy_source_commit_divergence(
    monkeypatch,
):
    kwargs = (
        completion_kwargs()
    )

    value = {
        "schema_version":
            module.COMPLETION_SCHEMA,
        "status":
            module.COMPLETION_STATUS,
        "source_production_commit":
            SOURCE_COMMIT,
        "legacy_support_execution_git_commit":
            TAXONOMY_COMMIT,
    }

    payload = (
        FakeStage7V1
        ._canonical_json(
            value
        )
    )

    monkeypatch.setattr(
        module,
        "build_completion_receipt_v2",
        lambda *args, **inner_kwargs:
            payload,
    )

    with pytest.raises(
        module.MonthlyTaxonomyV2ExecutionError,
        match=(
            "legacy support commit differs "
            "from source production commit"
        ),
    ):
        (
            module
            .audit_completion_receipt_v2(
                FakeStage7V1,
                payload,
                **kwargs,
            )
        )


def test_real_execution_requires_explicit_authorization(
    monkeypatch,
):
    args = SimpleNamespace(
        authorize_real_execution=False,
    )

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda:
            args,
    )

    with pytest.raises(
        module.MonthlyTaxonomyV2ExecutionError,
        match="explicit authorization",
    ):
        module.main()


def test_canonical_stage6_inventory_is_exact(
    tmp_path,
):
    stage = (
        tmp_path
        / "chromosome-integrity"
    )

    stage.mkdir()

    (
        stage
        / "chromosome-integrity-decisions.tsv"
    ).write_text(
        "x\n",
        encoding="utf-8",
    )

    (
        stage
        / "monthly-chromosome-integrity-record.json"
    ).write_text(
        "{}\n",
        encoding="utf-8",
    )

    expected = {
        "chromosome-integrity-decisions.tsv",
        "monthly-chromosome-integrity-record.json",
    }

    assert (
        module._require_exact_stage(
            stage,
            expected=expected,
        )
        == stage
    )

    (
        stage
        / "unexpected"
    ).write_text(
        "x",
        encoding="utf-8",
    )

    with pytest.raises(
        module.MonthlyTaxonomyV2ExecutionError,
        match="inventory changed",
    ):
        module._require_exact_stage(
            stage,
            expected=expected,
        )


def test_stage6_v2_completion_audit_supplies_stage5_execution():
    tree = ast.parse(
        WRAPPER_PATH.read_text(
            encoding="utf-8"
        )
    )

    target_function = next(
        node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == "authenticate_stage6_v2"
        )
    )

    assignments = []

    for node in ast.walk(
        target_function
    ):
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if any(
            isinstance(
                target,
                ast.Name,
            )
            and target.id
            == "completion_kwargs"
            for target in node.targets
        ):
            assignments.append(
                node
            )

    assert len(
        assignments
    ) == 1

    value = assignments[
        0
    ].value

    assert isinstance(
        value,
        ast.Dict,
    )

    entries = {}

    for key, item in zip(
        value.keys,
        value.values,
    ):
        if (
            isinstance(
                key,
                ast.Constant,
            )
            and isinstance(
                key.value,
                str,
            )
        ):
            entries[
                key.value
            ] = item

    assert (
        "stage5_execution"
        in entries
    )

    supplied = entries[
        "stage5_execution"
    ]

    assert isinstance(
        supplied,
        ast.Name,
    )

    assert (
        supplied.id
        == "stage5_v1"
    )
