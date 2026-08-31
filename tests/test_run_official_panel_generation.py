"""Synthetic tests for the official selector-v1 panel execution wrapper."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import stat
import sys

import pytest

from bacselect.official_panels import (
    ALL_ARTIFACTS,
    BASELINE_BINDING_KEYS,
    CONTENT_MANIFEST_FILENAME,
    PANEL_FILENAMES,
    PANEL_SIZES,
)


REPO = Path(
    __file__
).resolve().parents[1]

WRAPPER_PATH = (
    REPO
    / "validation/selector-v1/run_official_panel_generation.py"
)


def load_wrapper():
    name = "_bacselect_test_official_panel_execution"

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


wrapper = load_wrapper()


def sha256(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def synthetic_accessions() -> tuple[str, ...]:
    return tuple(
        f"GCA_{800000000 + index:09d}.1"
        for index in range(
            1,
            501,
        )
    )


def synthetic_baseline_bindings() -> dict[str, str]:
    return {
        key:
            format(
                index,
                "064x",
            )
        for index, key in enumerate(
            sorted(
                BASELINE_BINDING_KEYS
            ),
            start=1,
        )
    }


def scientific_inputs():
    return wrapper.ScientificInputs(
        accessions=synthetic_accessions(),
        final_geometry_helper_sha256=(
            "7" * 64
        ),
        baseline_bindings=(
            synthetic_baseline_bindings()
        ),
        environment_lock_sha256=(
            "8" * 64
        ),
    )


def write_fixture(
    repo: Path,
    relative: Path,
    payload: bytes,
) -> str:
    path = (
        repo
        / relative
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        payload
    )

    return sha256(
        payload
    )


def synthetic_preflight_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    Path,
    str,
    str,
    str,
]:
    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir()

    method_sha = write_fixture(
        repo,
        wrapper.METHOD_RELATIVE,
        b"synthetic method\n",
    )

    core_sha = write_fixture(
        repo,
        wrapper.CORE_RELATIVE,
        b"synthetic core\n",
    )

    core_test_sha = write_fixture(
        repo,
        wrapper.CORE_TEST_RELATIVE,
        b"synthetic core test\n",
    )

    decision_sha = write_fixture(
        repo,
        wrapper.DECISION_RELATIVE,
        b"synthetic decision\n",
    )

    stage7_sha = write_fixture(
        repo,
        wrapper.STAGE7_WRAPPER_RELATIVE,
        b"synthetic stage7 wrapper\n",
    )

    stage7_test_sha = write_fixture(
        repo,
        wrapper.STAGE7_WRAPPER_TEST_RELATIVE,
        b"synthetic stage7 test\n",
    )

    adapter_sha = write_fixture(
        repo,
        wrapper.STAGE7_ADAPTER_RELATIVE,
        b"synthetic stage7 adapter\n",
    )

    runtime_wrapper_sha = write_fixture(
        repo,
        wrapper.WRAPPER_RELATIVE,
        b"synthetic panel wrapper\n",
    )

    runtime_wrapper_test_sha = write_fixture(
        repo,
        wrapper.WRAPPER_TEST_RELATIVE,
        b"synthetic panel wrapper test\n",
    )

    monkeypatch.setattr(
        wrapper,
        "EXPECTED_METHOD_SHA256",
        method_sha,
    )

    monkeypatch.setattr(
        wrapper,
        "EXPECTED_CORE_SHA256",
        core_sha,
    )

    monkeypatch.setattr(
        wrapper,
        "EXPECTED_CORE_TEST_SHA256",
        core_test_sha,
    )

    monkeypatch.setattr(
        wrapper,
        "EXPECTED_DECISION_SHA256",
        decision_sha,
    )

    monkeypatch.setattr(
        wrapper,
        "EXPECTED_STAGE7_WRAPPER_SHA256",
        stage7_sha,
    )

    monkeypatch.setattr(
        wrapper,
        "EXPECTED_STAGE7_WRAPPER_TEST_SHA256",
        stage7_test_sha,
    )

    monkeypatch.setattr(
        wrapper,
        "EXPECTED_STAGE7_ADAPTER_SHA256",
        adapter_sha,
    )

    commit = "a" * 40

    state = {
        "head":
            commit,
        "origin":
            commit,
        "status":
            "",
    }

    def fake_git_output(
        requested_repo: Path,
        *arguments: str,
    ) -> str:
        assert requested_repo == repo

        if arguments == (
            "rev-parse",
            "HEAD",
        ):
            return state[
                "head"
            ]

        if arguments == (
            "rev-parse",
            "origin/main",
        ):
            return state[
                "origin"
            ]

        if arguments == (
            "status",
            "--porcelain",
        ):
            return state[
                "status"
            ]

        raise AssertionError(
            arguments
        )

    monkeypatch.setattr(
        wrapper,
        "_git_output",
        fake_git_output,
    )

    monkeypatch.setattr(
        wrapper,
        "_synthetic_git_state",
        state,
        raising=False,
    )

    return (
        repo,
        commit,
        runtime_wrapper_sha,
        runtime_wrapper_test_sha,
    )


def test_frozen_wrapper_constants_match_contract() -> None:
    assert wrapper.EXPECTED_METHOD_SHA256 == (
        "a55daffbaac0ea10f92195f96959fa3ab4da3aef023727ce388e74b2a86dab3c"
    )

    assert wrapper.EXPECTED_CORE_SHA256 == (
        "01859f21d7d8653e8ff671f1c5d74a9469a251470258d742edc9b09c14448356"
    )

    assert wrapper.EXPECTED_CORE_TEST_SHA256 == (
        "491f0f0ee237583c04ef3357ad7b9118ae1cc028fde8f2ce49748224dfcbbecc"
    )

    assert wrapper.EXPECTED_FINAL_LADDER_SHA256[
        "OPS"
    ] == (
        "c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13"
    )


def test_output_mode_paths_are_commit_scoped() -> None:
    commit = "b" * 40

    production = wrapper.output_root_for_mode(
        "production",
        commit,
    )

    rebuild = wrapper.output_root_for_mode(
        "rebuild",
        commit,
    )

    assert production.name == commit
    assert rebuild.name == commit
    assert production != rebuild


def test_invalid_execution_mode_is_refused() -> None:
    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="production or rebuild",
    ):
        wrapper.output_root_for_mode(
            "other",
            "b" * 40,
        )


def test_repository_preflight_accepts_exact_synthetic_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repo,
        commit,
        wrapper_sha,
        wrapper_test_sha,
    ) = synthetic_preflight_repo(
        tmp_path,
        monkeypatch,
    )

    wrapper.repository_preflight(
        repo=repo,
        expected_commit=commit,
        expected_wrapper_sha256=wrapper_sha,
        expected_wrapper_test_sha256=(
            wrapper_test_sha
        ),
    )


def test_wrong_head_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repo,
        commit,
        wrapper_sha,
        wrapper_test_sha,
    ) = synthetic_preflight_repo(
        tmp_path,
        monkeypatch,
    )

    wrapper._synthetic_git_state[
        "head"
    ] = "b" * 40

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="HEAD",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_commit=commit,
            expected_wrapper_sha256=wrapper_sha,
            expected_wrapper_test_sha256=(
                wrapper_test_sha
            ),
        )


def test_wrong_local_origin_main_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repo,
        commit,
        wrapper_sha,
        wrapper_test_sha,
    ) = synthetic_preflight_repo(
        tmp_path,
        monkeypatch,
    )

    wrapper._synthetic_git_state[
        "origin"
    ] = "b" * 40

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="origin/main",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_commit=commit,
            expected_wrapper_sha256=wrapper_sha,
            expected_wrapper_test_sha256=(
                wrapper_test_sha
            ),
        )


def test_dirty_repository_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repo,
        commit,
        wrapper_sha,
        wrapper_test_sha,
    ) = synthetic_preflight_repo(
        tmp_path,
        monkeypatch,
    )

    wrapper._synthetic_git_state[
        "status"
    ] = "?? synthetic.txt"

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="not clean",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_commit=commit,
            expected_wrapper_sha256=wrapper_sha,
            expected_wrapper_test_sha256=(
                wrapper_test_sha
            ),
        )


def test_runtime_wrapper_sha_mismatch_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repo,
        commit,
        _,
        wrapper_test_sha,
    ) = synthetic_preflight_repo(
        tmp_path,
        monkeypatch,
    )

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="execution wrapper SHA256 mismatch",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_commit=commit,
            expected_wrapper_sha256=(
                "f" * 64
            ),
            expected_wrapper_test_sha256=(
                wrapper_test_sha
            ),
        )


def test_runtime_wrapper_test_sha_mismatch_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repo,
        commit,
        wrapper_sha,
        _,
    ) = synthetic_preflight_repo(
        tmp_path,
        monkeypatch,
    )

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="wrapper test SHA256 mismatch",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_commit=commit,
            expected_wrapper_sha256=(
                wrapper_sha
            ),
            expected_wrapper_test_sha256=(
                "f" * 64
            ),
        )


def test_frozen_core_sha_mismatch_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repo,
        commit,
        wrapper_sha,
        wrapper_test_sha,
    ) = synthetic_preflight_repo(
        tmp_path,
        monkeypatch,
    )

    (
        repo
        / wrapper.CORE_RELATIVE
    ).write_bytes(
        b"changed core\n"
    )

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="generator core SHA256 mismatch",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_commit=commit,
            expected_wrapper_sha256=(
                wrapper_sha
            ),
            expected_wrapper_test_sha256=(
                wrapper_test_sha
            ),
        )


def test_frozen_core_test_sha_mismatch_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repo,
        commit,
        wrapper_sha,
        wrapper_test_sha,
    ) = synthetic_preflight_repo(
        tmp_path,
        monkeypatch,
    )

    (
        repo
        / wrapper.CORE_TEST_RELATIVE
    ).write_bytes(
        b"changed test\n"
    )

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="generator-core test SHA256 mismatch",
    ):
        wrapper.repository_preflight(
            repo=repo,
            expected_commit=commit,
            expected_wrapper_sha256=(
                wrapper_sha
            ),
            expected_wrapper_test_sha256=(
                wrapper_test_sha
            ),
        )


def test_existing_output_root_is_refused(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "already-there"
    )

    output.mkdir()

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="already exists",
    ):
        wrapper.output_preflight(
            output
        )


def test_missing_output_parent_is_refused(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "missing-parent"
        / "run"
    )

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="parent does not exist",
    ):
        wrapper.output_preflight(
            output
        )


def test_exclusive_writer_creates_exact_files_and_modes(
    tmp_path: Path,
) -> None:
    from bacselect.official_panels import (
        build_reference_panel_artifacts,
    )

    artifacts = dict(
        build_reference_panel_artifacts(
            synthetic_accessions(),
            execution_commit=(
                "c" * 40
            ),
            implementation_sha256=(
                wrapper.EXPECTED_CORE_SHA256
            ),
            implementation_test_sha256=(
                wrapper.EXPECTED_CORE_TEST_SHA256
            ),
            stage7_wrapper_sha256=(
                wrapper.EXPECTED_STAGE7_WRAPPER_SHA256
            ),
            stage7_execution_adapter_sha256=(
                wrapper.EXPECTED_STAGE7_ADAPTER_SHA256
            ),
            final_geometry_helper_sha256=(
                "7" * 64
            ),
            baseline_bindings=(
                synthetic_baseline_bindings()
            ),
            environment_lock_sha256=(
                "8" * 64
            ),
        )
    )

    output = (
        tmp_path
        / "run"
    )

    wrapper.write_artifacts_exclusive(
        output,
        artifacts,
    )

    assert {
        path.name
        for path in output.iterdir()
        if path.is_file()
    } == set(
        ALL_ARTIFACTS
    )

    for artifact in ALL_ARTIFACTS:
        path = (
            output
            / artifact
        )

        assert path.read_bytes() == artifacts[
            artifact
        ]

        assert stat.S_IMODE(
            path.stat().st_mode
        ) == 0o644


def test_exclusive_writer_refuses_overwrite(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    output.mkdir()

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="already exists",
    ):
        wrapper.write_artifacts_exclusive(
            output,
            {
                artifact:
                    b"x\n"
                for artifact in ALL_ARTIFACTS
            },
        )


def test_execute_panel_generation_uses_only_injected_synthetic_science(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        wrapper,
        "repository_preflight",
        lambda **kwargs: None,
    )

    calls = []

    def fake_scientific_builder(
        repo: Path,
    ):
        calls.append(
            repo
        )

        return scientific_inputs()

    output = (
        tmp_path
        / "production"
    )

    result = wrapper.execute_panel_generation(
        repo=tmp_path,
        expected_commit=(
            "d" * 40
        ),
        mode="production",
        expected_wrapper_sha256=(
            "9" * 64
        ),
        expected_wrapper_test_sha256=(
            "a" * 64
        ),
        scientific_builder=(
            fake_scientific_builder
        ),
        output_root_override=output,
    )

    assert calls == [
        tmp_path
    ]

    assert result.output_root == output

    assert set(
        result.artifact_sha256
    ) == set(
        ALL_ARTIFACTS
    )

    assert result.content_manifest_sha256 == (
        result.artifact_sha256[
            CONTENT_MANIFEST_FILENAME
        ]
    )

    for panel_size in PANEL_SIZES:
        assert (
            output
            / PANEL_FILENAMES[
                panel_size
            ]
        ).is_file()


def test_existing_output_is_refused_before_scientific_builder_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        wrapper,
        "repository_preflight",
        lambda **kwargs: None,
    )

    output = (
        tmp_path
        / "existing"
    )

    output.mkdir()

    called = False

    def forbidden_builder(
        repo: Path,
    ):
        nonlocal called

        called = True

        raise AssertionError(
            "scientific builder must not run"
        )

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="already exists",
    ):
        wrapper.execute_panel_generation(
            repo=tmp_path,
            expected_commit=(
                "d" * 40
            ),
            mode="production",
            expected_wrapper_sha256=(
                "9" * 64
            ),
            expected_wrapper_test_sha256=(
                "a" * 64
            ),
            scientific_builder=(
                forbidden_builder
            ),
            output_root_override=output,
        )

    assert called is False


def test_synthetic_production_and_rebuild_are_byte_identical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        wrapper,
        "repository_preflight",
        lambda **kwargs: None,
    )

    production = (
        tmp_path
        / "production"
    )

    rebuild = (
        tmp_path
        / "rebuild"
    )

    common = {
        "repo":
            tmp_path,
        "expected_commit":
            "e" * 40,
        "expected_wrapper_sha256":
            "9" * 64,
        "expected_wrapper_test_sha256":
            "a" * 64,
        "scientific_builder":
            lambda repo: scientific_inputs(),
    }

    wrapper.execute_panel_generation(
        mode="production",
        output_root_override=production,
        **common,
    )

    wrapper.execute_panel_generation(
        mode="rebuild",
        output_root_override=rebuild,
        **common,
    )

    wrapper.compare_execution_roots(
        production,
        rebuild,
    )

    for artifact in ALL_ARTIFACTS:
        assert (
            production
            / artifact
        ).read_bytes() == (
            rebuild
            / artifact
        ).read_bytes()


def test_production_rebuild_byte_mismatch_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        wrapper,
        "repository_preflight",
        lambda **kwargs: None,
    )

    production = (
        tmp_path
        / "production"
    )

    rebuild = (
        tmp_path
        / "rebuild"
    )

    common = {
        "repo":
            tmp_path,
        "expected_commit":
            "e" * 40,
        "expected_wrapper_sha256":
            "9" * 64,
        "expected_wrapper_test_sha256":
            "a" * 64,
        "scientific_builder":
            lambda repo: scientific_inputs(),
    }

    wrapper.execute_panel_generation(
        mode="production",
        output_root_override=production,
        **common,
    )

    wrapper.execute_panel_generation(
        mode="rebuild",
        output_root_override=rebuild,
        **common,
    )

    target = (
        rebuild
        / PANEL_FILENAMES[
            10
        ]
    )

    target.write_bytes(
        target.read_bytes()
        + b"GCA_999999999.1\n"
    )

    with pytest.raises(
        wrapper.OfficialPanelExecutionError,
        match="byte-identity",
    ):
        wrapper.compare_execution_roots(
            production,
            rebuild,
        )


def test_real_execution_requires_explicit_authorization() -> None:
    result = wrapper.main(
        [
            "--mode",
            "production",
            "--expected-commit",
            "f" * 40,
            "--expected-wrapper-sha256",
            "1" * 64,
            "--expected-wrapper-test-sha256",
            "2" * 64,
        ]
    )

    assert result == 2


def test_console_implementation_has_no_membership_dump() -> None:
    source = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    assert "print(accessions" not in source
    assert "print(scientific.accessions" not in source
    assert "for accession in scientific.accessions" not in source


def test_wrapper_tests_do_not_name_real_scientific_inputs() -> None:
    source = Path(
        __file__
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "/"
        + "NGS"
        + "/",
        "stage7-selector-resolution-"
        + "production",
        "stage7-selector-resolution-"
        + "rebuild",
        "stage6-structural-feature-"
        + "execution",
        "external-decision-"
        + "holdout",
        "GCA_"
        + "000016065"
        + ".1",
    )

    for token in forbidden:
        assert token not in source
