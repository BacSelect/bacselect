"""Synthetic-only tests for the Stage 7 selector-decision execution wrapper."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


WRAPPER_PATH = (
    Path(
        __file__
    ).resolve().parents[
        1
    ]
    / "validation/selector-v1/"
    "run_selector_decision_finalization.py"
)

SPEC = importlib.util.spec_from_file_location(
    "run_selector_decision_finalization",
    WRAPPER_PATH,
)

assert SPEC is not None
assert SPEC.loader is not None

wrapper = importlib.util.module_from_spec(
    SPEC
)

sys.modules[
    SPEC.name
] = wrapper

SPEC.loader.exec_module(
    wrapper
)


def digest(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def write_file(
    path: Path,
    payload: bytes,
) -> str:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        payload
    )

    return digest(
        payload
    )


def synthetic_repository_preflight(
    monkeypatch,
    tmp_path: Path,
):
    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir()

    wrapper_file = (
        tmp_path
        / "synthetic-wrapper.py"
    )

    wrapper_test = (
        repo
        / wrapper.WRAPPER_TEST_RELATIVE
    )

    wrapper_sha = write_file(
        wrapper_file,
        b"wrapper\n",
    )

    wrapper_test_sha = write_file(
        wrapper_test,
        b"wrapper-test\n",
    )

    monkeypatch.setattr(
        wrapper,
        "__file__",
        str(
            wrapper_file
        ),
    )

    monkeypatch.setattr(
        wrapper,
        "require_frozen_repo_bindings",
        lambda repo:
            None,
    )

    old_calls = []

    fake_stage7 = SimpleNamespace(
        repository_preflight=(
            lambda **kwargs:
                old_calls.append(
                    kwargs
                )
        )
    )

    monkeypatch.setattr(
        wrapper,
        "load_stage7_wrapper_module",
        lambda repo:
            fake_stage7,
    )

    return (
        repo,
        wrapper_sha,
        wrapper_test_sha,
        old_calls,
    )


def test_frozen_wrapper_constants_bind_finalizer_core() -> None:
    assert wrapper.EXPECTED_FINALIZER_CORE_SHA256 == (
        "d020cb862266e8dd3544c229dff0d77c3"
        "25d8de1c4f61b4360c9db5d97a6eab1"
    )

    assert wrapper.EXPECTED_FINALIZER_CORE_TEST_SHA256 == (
        "980a653f18389f672fdfe287781de5e14"
        "e582df3954cb61d0f79ddc0705b908c"
    )


def test_frozen_wrapper_constants_bind_prospective_method() -> None:
    assert wrapper.EXPECTED_FINALIZER_METHOD_SHA256 == (
        "25c36098903b5fa5a18da8c012a6e81a"
        "3b4c6836a6d008d042d8b0bf529e5d8e"
    )


def test_repository_preflight_requires_exact_head(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (
        repo,
        wrapper_sha,
        wrapper_test_sha,
        _,
    ) = synthetic_repository_preflight(
        monkeypatch,
        tmp_path,
    )

    monkeypatch.setattr(
        wrapper,
        "run_git",
        lambda repo, *arguments:
            (
                "b" * 40
                if arguments
                == (
                    "rev-parse",
                    "HEAD",
                )
                else ""
            ),
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="HEAD",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_execution_commit=(
                "a"
                * 40
            ),
            expected_wrapper_sha256=wrapper_sha,
            expected_wrapper_test_sha256=wrapper_test_sha,
        )


def test_repository_preflight_requires_exact_origin_main(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (
        repo,
        wrapper_sha,
        wrapper_test_sha,
        _,
    ) = synthetic_repository_preflight(
        monkeypatch,
        tmp_path,
    )

    def fake_git(
        repo,
        *arguments,
    ):
        if arguments == (
            "rev-parse",
            "HEAD",
        ):
            return "a" * 40

        if arguments == (
            "rev-parse",
            "origin/main",
        ):
            return "b" * 40

        return ""

    monkeypatch.setattr(
        wrapper,
        "run_git",
        fake_git,
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="origin/main",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_execution_commit=(
                "a"
                * 40
            ),
            expected_wrapper_sha256=wrapper_sha,
            expected_wrapper_test_sha256=wrapper_test_sha,
        )


def test_repository_preflight_rejects_dirty_tree(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (
        repo,
        wrapper_sha,
        wrapper_test_sha,
        _,
    ) = synthetic_repository_preflight(
        monkeypatch,
        tmp_path,
    )

    def fake_git(
        repo,
        *arguments,
    ):
        if arguments == (
            "status",
            "--porcelain",
        ):
            return "?? synthetic"

        return "a" * 40

    monkeypatch.setattr(
        wrapper,
        "run_git",
        fake_git,
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="not clean",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_execution_commit=(
                "a"
                * 40
            ),
            expected_wrapper_sha256=wrapper_sha,
            expected_wrapper_test_sha256=wrapper_test_sha,
        )


def test_repository_preflight_requires_exact_wrapper_sha(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (
        repo,
        _,
        wrapper_test_sha,
        _,
    ) = synthetic_repository_preflight(
        monkeypatch,
        tmp_path,
    )

    monkeypatch.setattr(
        wrapper,
        "run_git",
        lambda repo, *arguments:
            (
                ""
                if arguments
                == (
                    "status",
                    "--porcelain",
                )
                else "a" * 40
            ),
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="wrapper.*SHA256 mismatch",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_execution_commit=(
                "a"
                * 40
            ),
            expected_wrapper_sha256=(
                "0"
                * 64
            ),
            expected_wrapper_test_sha256=wrapper_test_sha,
        )


def test_repository_preflight_requires_exact_wrapper_test_sha(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (
        repo,
        wrapper_sha,
        _,
        _,
    ) = synthetic_repository_preflight(
        monkeypatch,
        tmp_path,
    )

    monkeypatch.setattr(
        wrapper,
        "run_git",
        lambda repo, *arguments:
            (
                ""
                if arguments
                == (
                    "status",
                    "--porcelain",
                )
                else "a" * 40
            ),
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="wrapper test SHA256 mismatch",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_execution_commit=(
                "a"
                * 40
            ),
            expected_wrapper_sha256=wrapper_sha,
            expected_wrapper_test_sha256=(
                "0"
                * 64
            ),
        )


def test_repository_preflight_uses_no_remote_network(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (
        repo,
        wrapper_sha,
        wrapper_test_sha,
        old_calls,
    ) = synthetic_repository_preflight(
        monkeypatch,
        tmp_path,
    )

    calls = []

    def fake_git(
        repo,
        *arguments,
    ):
        calls.append(
            arguments
        )

        if arguments == (
            "status",
            "--porcelain",
        ):
            return ""

        return "a" * 40

    monkeypatch.setattr(
        wrapper,
        "run_git",
        fake_git,
    )

    wrapper.repository_preflight(
        repo=repo,
        expected_execution_commit=(
            "a"
            * 40
        ),
        expected_wrapper_sha256=wrapper_sha,
        expected_wrapper_test_sha256=wrapper_test_sha,
    )

    assert calls == [
        (
            "rev-parse",
            "HEAD",
        ),
        (
            "rev-parse",
            "origin/main",
        ),
        (
            "status",
            "--porcelain",
        ),
    ]

    assert (
        "ls-remote",
    ) not in calls

    assert len(
        old_calls
    ) == 1


def test_repository_preflight_delegates_frozen_stage7_preflight(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (
        repo,
        wrapper_sha,
        wrapper_test_sha,
        old_calls,
    ) = synthetic_repository_preflight(
        monkeypatch,
        tmp_path,
    )

    monkeypatch.setattr(
        wrapper,
        "run_git",
        lambda repo, *arguments:
            (
                ""
                if arguments
                == (
                    "status",
                    "--porcelain",
                )
                else "a" * 40
            ),
    )

    wrapper.repository_preflight(
        repo=repo,
        expected_execution_commit=(
            "a"
            * 40
        ),
        expected_wrapper_sha256=wrapper_sha,
        expected_wrapper_test_sha256=wrapper_test_sha,
    )

    assert old_calls == [
        {
            "repo":
                repo,
            "expected_commit":
                "a" * 40,
            "expected_wrapper_sha256":
                wrapper.EXPECTED_STAGE7_PRODUCTION_WRAPPER_SHA256,
            "expected_wrapper_test_sha256":
                wrapper.EXPECTED_STAGE7_PRODUCTION_WRAPPER_TEST_SHA256,
        }
    ]


def test_output_preflight_rejects_path_inside_repo(
    tmp_path: Path,
) -> None:
    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir()

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="outside Git",
    ):
        wrapper.output_preflight(
            repo=repo,
            output_path=(
                repo
                / "decision.json"
            ),
        )


def test_output_preflight_rejects_existing_output(
    tmp_path: Path,
) -> None:
    repo = (
        tmp_path
        / "repo"
    )

    scratch = (
        tmp_path
        / "scratch"
    )

    repo.mkdir()
    scratch.mkdir()

    output = (
        scratch
        / "decision.json"
    )

    output.write_text(
        "existing",
        encoding="utf-8",
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="already exists",
    ):
        wrapper.output_preflight(
            repo=repo,
            output_path=output,
        )


def test_output_preflight_rejects_existing_temporary(
    tmp_path: Path,
) -> None:
    repo = (
        tmp_path
        / "repo"
    )

    scratch = (
        tmp_path
        / "scratch"
    )

    repo.mkdir()
    scratch.mkdir()

    output = (
        scratch
        / "decision.json"
    )

    temporary = (
        scratch
        / ".decision.json.tmp"
    )

    temporary.write_text(
        "failed-evidence",
        encoding="utf-8",
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="temporary",
    ):
        wrapper.output_preflight(
            repo=repo,
            output_path=output,
        )


def test_atomic_write_writes_exact_bytes_without_overwrite(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "decision.json"
    )

    payload = b'{"synthetic":true}\n'

    observed = wrapper.write_bytes_atomic(
        output,
        payload,
    )

    assert output.read_bytes() == payload

    assert observed == digest(
        payload
    )

    assert not (
        tmp_path
        / ".decision.json.tmp"
    ).exists()

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="already exists",
    ):
        wrapper.write_bytes_atomic(
            output,
            payload,
        )


def synthetic_run_envelope(
    root: Path,
):
    scientific = {}

    for name in wrapper.SCIENTIFIC_ARTIFACT_NAMES:
        scientific[
            name
        ] = write_file(
            root
            / name,
            (
                "scientific:"
                + name
                + "\n"
            ).encode(
                "utf-8"
            ),
        )

    provenance = {}

    for index, key in enumerate(
        (
            "content_manifest_sha256",
            "execution_provenance_sha256",
            "predecision_provenance_sha256",
        ),
        start=1,
    ):
        provenance[
            key
        ] = write_file(
            root
            / (
                "aggregate-"
                + str(
                    index
                )
                + ".json"
            ),
            (
                "provenance:"
                + key
                + "\n"
            ).encode(
                "utf-8"
            ),
        )

    return (
        scientific,
        provenance,
    )


def test_collect_run_envelope_requires_exact_nine_files(
    tmp_path: Path,
) -> None:
    run_dir = (
        tmp_path
        / "run"
    )

    run_dir.mkdir()

    scientific, provenance = synthetic_run_envelope(
        run_dir
    )

    envelope = wrapper.collect_run_envelope(
        run_dir=run_dir,
        expected_scientific_sha256=scientific,
        expected_provenance_sha256=provenance,
        label="synthetic",
    )

    assert envelope.scientific_sha256 == scientific

    assert envelope.provenance_sha256 == provenance


def test_collect_run_envelope_rejects_missing_file(
    tmp_path: Path,
) -> None:
    run_dir = (
        tmp_path
        / "run"
    )

    run_dir.mkdir()

    scientific, provenance = synthetic_run_envelope(
        run_dir
    )

    (
        run_dir
        / wrapper.SCIENTIFIC_ARTIFACT_NAMES[
            0
        ]
    ).unlink()

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="exactly nine",
    ):
        wrapper.collect_run_envelope(
            run_dir=run_dir,
            expected_scientific_sha256=scientific,
            expected_provenance_sha256=provenance,
            label="synthetic",
        )


def test_collect_run_envelope_rejects_extra_file(
    tmp_path: Path,
) -> None:
    run_dir = (
        tmp_path
        / "run"
    )

    run_dir.mkdir()

    scientific, provenance = synthetic_run_envelope(
        run_dir
    )

    (
        run_dir
        / "extra"
    ).write_text(
        "extra",
        encoding="utf-8",
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="exactly nine",
    ):
        wrapper.collect_run_envelope(
            run_dir=run_dir,
            expected_scientific_sha256=scientific,
            expected_provenance_sha256=provenance,
            label="synthetic",
        )


def test_scientific_pair_comparison_is_byte_exact(
    tmp_path: Path,
) -> None:
    production = (
        tmp_path
        / "production"
    )

    rebuild = (
        tmp_path
        / "rebuild"
    )

    production.mkdir()
    rebuild.mkdir()

    for name in wrapper.SCIENTIFIC_ARTIFACT_NAMES:
        payload = (
            name
            + "\n"
        ).encode(
            "utf-8"
        )

        write_file(
            production
            / name,
            payload,
        )

        write_file(
            rebuild
            / name,
            payload,
        )

    wrapper.require_scientific_pairs_byte_identical(
        production_dir=production,
        rebuild_dir=rebuild,
    )

    (
        rebuild
        / wrapper.SCIENTIFIC_ARTIFACT_NAMES[
            2
        ]
    ).write_bytes(
        b"different\n"
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="pair differs",
    ):
        wrapper.require_scientific_pairs_byte_identical(
            production_dir=production,
            rebuild_dir=rebuild,
        )


def test_ladder_manifest_requires_exact_structure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "ladders.tsv"
    )

    path.write_text(
        "\n".join(
            (
                "selector\tmax_n\tladder_sha256",
                (
                    "OPS\t500\t"
                    + wrapper.FINAL_LADDER_SHA256[
                        "OPS"
                    ]
                ),
                (
                    "SR\t500\t"
                    + wrapper.FINAL_LADDER_SHA256[
                        "SR"
                    ]
                ),
                (
                    "AG\t500\t"
                    + "a" * 64
                ),
                "",
            )
        ),
        encoding="utf-8",
    )

    assert wrapper.parse_final_ladder_manifest(
        path
    ) == wrapper.FINAL_LADDER_SHA256


def test_ladder_manifest_rejects_changed_max_n(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "ladders.tsv"
    )

    path.write_text(
        "\n".join(
            (
                "selector\tmax_n\tladder_sha256",
                (
                    "OPS\t499\t"
                    + wrapper.FINAL_LADDER_SHA256[
                        "OPS"
                    ]
                ),
                (
                    "SR\t500\t"
                    + wrapper.FINAL_LADDER_SHA256[
                        "SR"
                    ]
                ),
                (
                    "AG\t500\t"
                    + "a" * 64
                ),
                "",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="max_n",
    ):
        wrapper.parse_final_ladder_manifest(
            path
        )


def test_read_production_decision_inputs_reads_exactly_three_files(
    tmp_path: Path,
) -> None:
    production = (
        tmp_path
        / "production"
    )

    production.mkdir()

    expected = []

    for name in (
        wrapper.PRIMARY_METRIC_ARTIFACT,
        wrapper.EXACT_PRODUCT_ARTIFACT,
        wrapper.ANALYSIS_SUMMARY_ARTIFACT,
    ):
        payload = (
            "payload:"
            + name
        ).encode(
            "utf-8"
        )

        expected.append(
            payload
        )

        (
            production
            / name
        ).write_bytes(
            payload
        )

    observed = wrapper.read_production_decision_inputs(
        production
    )

    assert observed == tuple(
        expected
    )


def test_execute_finalization_predecision_occurs_before_interpreted_reads(
    monkeypatch,
    tmp_path: Path,
) -> None:
    order = []

    evidence = object()

    monkeypatch.setattr(
        wrapper,
        "predecision_verify",
        lambda **kwargs:
            (
                order.append(
                    "predecision"
                )
                or evidence
            ),
    )

    monkeypatch.setattr(
        wrapper,
        "output_preflight",
        lambda **kwargs:
            order.append(
                "output-preflight"
            ),
    )

    monkeypatch.setattr(
        wrapper,
        "read_production_decision_inputs",
        lambda production_dir:
            (
                order.append(
                    "interpreted-read"
                )
                or (
                    b"primary",
                    b"products",
                    b"summary",
                )
            ),
    )

    monkeypatch.setattr(
        wrapper,
        "finalize_selector_decision",
        lambda **kwargs:
            (
                order.append(
                    "resolve"
                )
                or b'{"synthetic":true}\n'
            ),
    )

    monkeypatch.setattr(
        wrapper,
        "write_bytes_atomic",
        lambda path, payload:
            (
                order.append(
                    "write"
                )
                or digest(
                    payload
                )
            ),
    )

    wrapper.execute_finalization(
        repo=(
            tmp_path
            / "repo"
        ),
        expected_execution_commit=(
            "a"
            * 40
        ),
        expected_wrapper_sha256=(
            "1"
            * 64
        ),
        expected_wrapper_test_sha256=(
            "2"
            * 64
        ),
        byte_identity_record=(
            tmp_path
            / "byte.json"
        ),
        production_dir=(
            tmp_path
            / "production"
        ),
        rebuild_dir=(
            tmp_path
            / "rebuild"
        ),
        output_path=(
            tmp_path
            / "out"
            / "decision.json"
        ),
    )

    assert order == [
        "predecision",
        "output-preflight",
        "interpreted-read",
        "resolve",
        "write",
    ]


def test_predecision_failure_prevents_interpreted_reads(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        wrapper,
        "predecision_verify",
        lambda **kwargs:
            (_ for _ in ()).throw(
                wrapper.SelectorDecisionWrapperError(
                    "synthetic failure"
                )
            ),
    )

    called = []

    monkeypatch.setattr(
        wrapper,
        "read_production_decision_inputs",
        lambda production_dir:
            called.append(
                production_dir
            ),
    )

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="synthetic failure",
    ):
        wrapper.execute_finalization(
            repo=(
                tmp_path
                / "repo"
            ),
            expected_execution_commit=(
                "a"
                * 40
            ),
            expected_wrapper_sha256=(
                "1"
                * 64
            ),
            expected_wrapper_test_sha256=(
                "2"
                * 64
            ),
            byte_identity_record=(
                tmp_path
                / "byte.json"
            ),
            production_dir=(
                tmp_path
                / "production"
            ),
            rebuild_dir=(
                tmp_path
                / "rebuild"
            ),
            output_path=(
                tmp_path
                / "decision.json"
            ),
        )

    assert called == []


def test_cli_requires_explicit_real_execution_authorization(
    tmp_path: Path,
) -> None:
    argv = [
        "--expected-execution-commit",
        "a" * 40,
        "--expected-wrapper-sha256",
        "1" * 64,
        "--expected-wrapper-test-sha256",
        "2" * 64,
        "--byte-identity-record",
        str(
            tmp_path
            / "byte.json"
        ),
        "--production-dir",
        str(
            tmp_path
            / "production"
        ),
        "--rebuild-dir",
        str(
            tmp_path
            / "rebuild"
        ),
        "--output-path",
        str(
            tmp_path
            / "decision.json"
        ),
    ]

    with pytest.raises(
        wrapper.SelectorDecisionWrapperError,
        match="--authorize-real-execution",
    ):
        wrapper.main(
            argv
        )


def test_cli_success_does_not_print_decision_or_products(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        wrapper,
        "execute_finalization",
        lambda **kwargs:
            wrapper.FinalizerExecutionResult(
                output_path=(
                    tmp_path
                    / "selector-decision.json"
                ),
                output_sha256=(
                    "f"
                    * 64
                ),
            ),
    )

    result = wrapper.main(
        [
            "--expected-execution-commit",
            "a" * 40,
            "--expected-wrapper-sha256",
            "1" * 64,
            "--expected-wrapper-test-sha256",
            "2" * 64,
            "--byte-identity-record",
            str(
                tmp_path
                / "byte.json"
            ),
            "--production-dir",
            str(
                tmp_path
                / "production"
            ),
            "--rebuild-dir",
            str(
                tmp_path
                / "rebuild"
            ),
            "--output-path",
            str(
                tmp_path
                / "selector-decision.json"
            ),
            "--authorize-real-execution",
        ]
    )

    assert result == 0

    stdout = capsys.readouterr().out

    assert "PASS | STAGE7_SELECTOR_DECISION_RECORD_WRITTEN" in stdout
    assert "OPS" not in stdout
    assert "SR" not in stdout
    assert "UNRESOLVED" not in stdout
    assert "numerator" not in stdout
    assert "denominator" not in stdout


def test_execute_binds_wrapper_and_core_identities(
    monkeypatch,
    tmp_path: Path,
) -> None:
    evidence = object()

    monkeypatch.setattr(
        wrapper,
        "predecision_verify",
        lambda **kwargs:
            evidence,
    )

    monkeypatch.setattr(
        wrapper,
        "output_preflight",
        lambda **kwargs:
            None,
    )

    monkeypatch.setattr(
        wrapper,
        "read_production_decision_inputs",
        lambda production_dir:
            (
                b"primary",
                b"products",
                b"summary",
            ),
    )

    observed = {}

    def fake_finalize(
        **kwargs,
    ):
        observed.update(
            kwargs
        )

        return b'{"synthetic":true}\n'

    monkeypatch.setattr(
        wrapper,
        "finalize_selector_decision",
        fake_finalize,
    )

    monkeypatch.setattr(
        wrapper,
        "write_bytes_atomic",
        lambda path, payload:
            digest(
                payload
            ),
    )

    wrapper.execute_finalization(
        repo=(
            tmp_path
            / "repo"
        ),
        expected_execution_commit=(
            "a"
            * 40
        ),
        expected_wrapper_sha256=(
            "1"
            * 64
        ),
        expected_wrapper_test_sha256=(
            "2"
            * 64
        ),
        byte_identity_record=(
            tmp_path
            / "byte.json"
        ),
        production_dir=(
            tmp_path
            / "production"
        ),
        rebuild_dir=(
            tmp_path
            / "rebuild"
        ),
        output_path=(
            tmp_path
            / "decision.json"
        ),
    )

    assert observed[
        "finalizer_execution_commit"
    ] == "a" * 40

    assert observed[
        "finalizer_method_sha256"
    ] == wrapper.EXPECTED_FINALIZER_METHOD_SHA256

    assert observed[
        "finalizer_implementation_sha256"
    ] == "1" * 64

    assert observed[
        "finalizer_test_sha256"
    ] == "2" * 64

    assert observed[
        "environment_bindings"
    ] == {
        "environment_lock_sha256":
            wrapper.EXPECTED_ENVIRONMENT_LOCK_SHA256,
        "finalizer_core_sha256":
            wrapper.EXPECTED_FINALIZER_CORE_SHA256,
        "finalizer_core_test_sha256":
            wrapper.EXPECTED_FINALIZER_CORE_TEST_SHA256,
    }
