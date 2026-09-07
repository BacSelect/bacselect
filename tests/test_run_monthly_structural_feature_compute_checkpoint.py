from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "run_monthly_structural_feature_compute_checkpoint.py"
)

SPEC = importlib.util.spec_from_file_location(
    "_stage10_checkpoint_test",
    PATH,
)

assert SPEC is not None
assert SPEC.loader is not None

module = importlib.util.module_from_spec(
    SPEC
)

sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_frozen_compute_contract():
    assert module.EXPECTED_COMPUTE_COUNT == 333

    assert (
        module.EXPECTED_COMPUTE_MEMBERSHIP_SHA256
        == (
            "8eaead6f7ad348864b63d2574fc1e4fa590ac698c123bf2aa9e498e2e382b4c5"
        )
    )

    assert (
        module.EXPECTED_ENGINE_SHA256
        == (
            "e0b5ea3a892aee3f9af80e5676010f1e1145563ca900058485e07d6433988968"
        )
    )


def test_atomic_write_refuses_existing(
    tmp_path,
):
    path = tmp_path / "x"

    module.atomic_write_fresh(
        path,
        b"a",
    )

    with pytest.raises(
        module.CheckpointError,
        match="existing path",
    ):
        module.atomic_write_fresh(
            path,
            b"b",
        )


def test_exact_provenance_is_resumable(
    tmp_path,
):
    path = tmp_path / "run.json"

    payload = b'{"a":1}\n'

    module.ensure_exact_file(
        path,
        payload,
    )

    module.ensure_exact_file(
        path,
        payload,
    )

    with pytest.raises(
        module.CheckpointError,
        match="changed",
    ):
        module.ensure_exact_file(
            path,
            b'{"a":2}\n',
        )


def test_checkpoint_validation(
    tmp_path,
):
    fields = (
        "a",
        "b",
    )

    record = {
        "schema_version":
            module.SCHEMA,
        "accession":
            "GCA_000000001.1",
        "species_taxid":
            "1",
        "component_identity_sha256":
            "1" * 64,
        "execution_commit":
            "a" * 40,
        "engine_sha256":
            module.EXPECTED_ENGINE_SHA256,
        "retained_replicon_count":
            1,
        "total_sequence_length":
            100,
        "features": {
            "a": 1,
            "b": 2,
        },
    }

    observed = (
        module
        .validate_checkpoint_record(
            module.canonical_json(
                record
            ),
            accession=(
                "GCA_000000001.1"
            ),
            species_taxid="1",
            component_identity_sha256=(
                "1" * 64
            ),
            execution_commit=(
                "a" * 40
            ),
            feature_fields=fields,
        )
    )

    assert observed == record


def test_checkpoint_rejects_wrong_engine():
    record = {
        "schema_version":
            module.SCHEMA,
        "accession":
            "GCA_000000001.1",
        "species_taxid":
            "1",
        "component_identity_sha256":
            "1" * 64,
        "execution_commit":
            "a" * 40,
        "engine_sha256":
            "2" * 64,
        "retained_replicon_count":
            1,
        "total_sequence_length":
            100,
        "features": {
            "a": 1,
        },
    }

    with pytest.raises(
        module.CheckpointError,
        match="engine_sha256 changed",
    ):
        module.validate_checkpoint_record(
            module.canonical_json(
                record
            ),
            accession=(
                "GCA_000000001.1"
            ),
            species_taxid="1",
            component_identity_sha256=(
                "1" * 64
            ),
            execution_commit=(
                "a" * 40
            ),
            feature_fields=(
                "a",
            ),
        )


def test_runner_contains_no_stage10_publication_call():
    text = PATH.read_text(
        encoding="utf-8"
    )

    assert (
        "execute_monthly_structural_features("
        not in text
    )

    assert "publish_stage(" not in text
    assert "publish_completion(" not in text


def test_checkpoint_schema_is_canonical_json():
    payload = module.canonical_json(
        {
            "z": 1,
            "a": 2,
        }
    )

    assert payload == b'{"a":2,"z":1}\n'

    assert json.loads(
        payload
    ) == {
        "a": 2,
        "z": 1,
    }
