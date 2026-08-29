#!/usr/bin/env python3
"""Execute frozen BacSelect selector-v1 Stage 6 structural features.

The production ordering is deliberate:

1. verify immutable whole-file identities and compile the frozen engine;
2. create the commit-scoped .partial directory;
3. write Stage 6 predecision provenance;
4. only then parse holdout rows and reconstruct authoritative source packages;
5. calculate all twelve raw structural features for every frozen holdout member;
6. validate complete membership and deterministic identities;
7. atomically finalize exactly seven files.

No percentile geometry or selector outcome is calculated here.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from types import ModuleType
from typing import Callable, Iterable, Mapping, Sequence

from bacselect import source_structural_feature_execution
from bacselect import source_structural_features
from bacselect import source_truth_execution


WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_structural_feature_execution.py"
)

WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_structural_feature_execution.py"
)

METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-stage6-structural-feature-execution.md"
)

STAGE5B_COMPLETION_RELATIVE = Path(
    "validation/selector-v1/"
    "stage5b-holdout-completion-evidence.json"
)

STAGE1_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_source_truth_execution.py"
)

STAGE2_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_repeated_biosample_execution.py"
)

SOURCE_TRUTH_RELATIVE = Path(
    "src/bacselect/source_truth_execution.py"
)

SOURCE_CACHE_VERIFY_RELATIVE = Path(
    "src/bacselect/source_cache_verify.py"
)

SOURCE_TRUTH_PRIMITIVE_RELATIVE = Path(
    "src/bacselect/source_truth.py"
)

SOURCE_FINGERPRINT_RELATIVE = Path(
    "src/bacselect/source_fingerprint.py"
)

CHROMOSOME_EXECUTION_RELATIVE = Path(
    "src/bacselect/source_chromosome_integrity_execution.py"
)

BINDING_HELPER_RELATIVE = Path(
    "src/bacselect/source_structural_features.py"
)

FEATURE_EXECUTION_RELATIVE = Path(
    "src/bacselect/source_structural_feature_execution.py"
)

FINCH_DRIVER_RELATIVE = Path(
    "vendor/project-finch/experiment-0/"
    "compute_structural_features.py"
)

FINCH_BASIC_RELATIVE = Path(
    "vendor/project-finch/experiment-0/"
    "basic_structural_features.py"
)

FINCH_REFERENCE_RELATIVE = Path(
    "vendor/project-finch/experiment-0/"
    "structural_features.py"
)

ENGINE_SOURCE_RELATIVE = Path(
    "vendor/project-finch/experiment-0/"
    "structural_features_fast.cpp"
)

ENV_LOCK_RELATIVE = Path(
    "envs/bacselect-repeat-linux-64.lock"
)


EXPECTED_STAGE6_METHOD_SHA256 = (
    "38c69bce5ed8a42849b5f68a0c282199"
    "9f3e122c46cbc6dd45943a6a6f0ca1e7"
)

EXPECTED_STAGE5B_COMPLETION_SHA256 = (
    "a8969754ee928bbfe31c5b10c51ac72"
    "d3602533ee411e01cd290048f2acf1a2b"
)

EXPECTED_STAGE1_WRAPPER_SHA256 = (
    "59dd3ea140ee9a49c86dbed810639728"
    "000add8ac30121ab41d2c59e328961d5"
)

EXPECTED_STAGE2_WRAPPER_SHA256 = (
    "5e5f51891e5348e62bc53dfacc28f572"
    "16f2e0f38ef69d3ce686121ed6aff355"
)

EXPECTED_SOURCE_TRUTH_SHA256 = (
    "83b8ec7fce774c0b68cb2af982aef139"
    "04c6b64b3ee695512c578f98e5de9b92"
)

EXPECTED_SOURCE_CACHE_VERIFY_SHA256 = (
    "c0f2114907111ae9f7f89695fefcafa7"
    "9fe4da3e3ed71acc597c5101db13963d"
)

EXPECTED_SOURCE_TRUTH_PRIMITIVE_SHA256 = (
    "6aac349e591daebfc2569c14633cc807b"
    "5d7186ed4ed3e79f37f6627f5184486"
)

EXPECTED_SOURCE_FINGERPRINT_SHA256 = (
    "6c994d243709abdbe9d7c8949e156009"
    "b9f31f3fcef3247cc3c5679e2fff41c9"
)

EXPECTED_CHROMOSOME_EXECUTION_SHA256 = (
    "187816b76ae804ad2e682e036a5fb765"
    "28ac1762d6535062a566edd2fe6e4b9c"
)

EXPECTED_BINDING_HELPER_SHA256 = (
    "80970d76fe3c36429eaecb3b35aed481"
    "4695b08f68237417e1c44049fb0bc669"
)

EXPECTED_FEATURE_EXECUTION_SHA256 = (
    "9b92d4869eac338f10499011006cec29"
    "ea4e55f05ce9cdc17c5543f70e21fae1"
)

EXPECTED_FINCH_DRIVER_SHA256 = (
    "e4d76a44731000dc8330d6f3289aca7"
    "6ce6562329dd371f6f63ec090ab42db50"
)

EXPECTED_FINCH_BASIC_SHA256 = (
    "30bc3f52fdf68cf7b6433262935b3ed"
    "2bb189b256672687bea56f3a4f4cc043a"
)

EXPECTED_FINCH_REFERENCE_SHA256 = (
    "c1e7388ba7db82d1b937a16e1a1be9e8"
    "c65d8779ce8691a2f0097cb5b6af6786"
)

EXPECTED_ENGINE_SOURCE_SHA256 = (
    "bea979167a353c41e51bb96c83acebfb"
    "8e8136269d2902d99142c0780bf46925"
)

EXPECTED_ENV_LOCK_SHA256 = (
    "aa6984b17e86f7d0627379e295fabed8"
    "37cf7d43cc6a9fd80f32b7092ac5f64f"
)

EXPECTED_ENGINE_BINARY_SHA256 = (
    "e0b5ea3a892aee3f9af80e5676010f1"
    "e1145563ca900058485e07d6433988968"
)

EXPECTED_HOLDOUT_ARTIFACT_SHA256 = (
    "ed0950e973d7d1bd2e7d294d1e5fde9c"
    "b7087e41cd54f021ac2ffe94262716c3"
)

EXPECTED_HOLDOUT_MEMBERSHIP_SHA256 = (
    "0998a65f617e6c1b951b52990c0e2cf8"
    "110b6327992110d862d9338f0fa06bbd"
)

EXPECTED_HOLDOUT_COUNT = 12_952
EXPECTED_HOLDOUT_SPECIES_COUNT = 3_542


LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

LOWER_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

POSITIVE_INTEGER_TEXT_RE = re.compile(
    r"^[1-9][0-9]*$"
)

HOLDOUT_FIELDS = (
    "canonical_genbank_assembly_accession",
    "species_taxid",
)

MATRIX_FIELDS = (
    "canonical_genbank_assembly_accession",
    "species_taxid",
    *source_structural_feature_execution.FEATURE_FIELDS,
)

INTEGER_FEATURE_FIELDS = frozenset(
    {
        "01_total_genome_length",
        "03_replicon_count",
        "04_non_chromosomal_replicon_count",
        "08_maximum_canonical_300mer_multiplicity",
        "09_maximum_canonical_2400mer_multiplicity",
        "10_longest_exact_repeat_length",
    }
)

CANDIDATE_EVIDENCE_FIELDS = (
    "canonical_genbank_assembly_accession",
    "source_group",
    "batch",
    "source_evidence_sha256",
    "genomic_fasta_sha256",
    "sequence_report_sha256",
    "retained_primary_assembly_replicon_count",
    "total_retained_sequence_length",
    "topology_circular_records",
    "topology_linear_records",
    "feature_record_sha256",
)

INPUT_EVIDENCE_FIELDS = (
    "source_group",
    "batch",
    "file_role",
    "file_name",
    "size_bytes",
    "sha256",
)

CONTENT_MANIFEST_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
)

FINAL_FILES = frozenset(
    {
        "stage6-predecision-provenance.json",
        "structural-feature-matrix-300-2400.tsv",
        "stage6-candidate-evidence.tsv",
        "stage6-input-evidence-manifest.tsv",
        "stage6-execution-provenance.json",
        "stage6-aggregate-summary.json",
        "stage6-content-manifest.tsv",
    }
)

CONTENT_COVERED_FILES = (
    "stage6-predecision-provenance.json",
    "structural-feature-matrix-300-2400.tsv",
    "stage6-candidate-evidence.tsv",
    "stage6-input-evidence-manifest.tsv",
    "stage6-execution-provenance.json",
    "stage6-aggregate-summary.json",
)


FROZEN_REPO_FILES = {
    METHOD_RELATIVE:
        EXPECTED_STAGE6_METHOD_SHA256,
    STAGE5B_COMPLETION_RELATIVE:
        EXPECTED_STAGE5B_COMPLETION_SHA256,
    STAGE1_WRAPPER_RELATIVE:
        EXPECTED_STAGE1_WRAPPER_SHA256,
    STAGE2_WRAPPER_RELATIVE:
        EXPECTED_STAGE2_WRAPPER_SHA256,
    SOURCE_TRUTH_RELATIVE:
        EXPECTED_SOURCE_TRUTH_SHA256,
    SOURCE_CACHE_VERIFY_RELATIVE:
        EXPECTED_SOURCE_CACHE_VERIFY_SHA256,
    SOURCE_TRUTH_PRIMITIVE_RELATIVE:
        EXPECTED_SOURCE_TRUTH_PRIMITIVE_SHA256,
    SOURCE_FINGERPRINT_RELATIVE:
        EXPECTED_SOURCE_FINGERPRINT_SHA256,
    CHROMOSOME_EXECUTION_RELATIVE:
        EXPECTED_CHROMOSOME_EXECUTION_SHA256,
    BINDING_HELPER_RELATIVE:
        EXPECTED_BINDING_HELPER_SHA256,
    FEATURE_EXECUTION_RELATIVE:
        EXPECTED_FEATURE_EXECUTION_SHA256,
    FINCH_DRIVER_RELATIVE:
        EXPECTED_FINCH_DRIVER_SHA256,
    FINCH_BASIC_RELATIVE:
        EXPECTED_FINCH_BASIC_SHA256,
    FINCH_REFERENCE_RELATIVE:
        EXPECTED_FINCH_REFERENCE_SHA256,
    ENGINE_SOURCE_RELATIVE:
        EXPECTED_ENGINE_SOURCE_SHA256,
    ENV_LOCK_RELATIVE:
        EXPECTED_ENV_LOCK_SHA256,
}


def _implementation_sha256() -> str:
    payload = (
        f"{EXPECTED_BINDING_HELPER_SHA256}  "
        f"{BINDING_HELPER_RELATIVE.as_posix()}\n"
        f"{EXPECTED_FEATURE_EXECUTION_SHA256}  "
        f"{FEATURE_EXECUTION_RELATIVE.as_posix()}\n"
    ).encode(
        "ascii"
    )

    return hashlib.sha256(
        payload
    ).hexdigest()


EXPECTED_STAGE6_IMPLEMENTATION_SHA256 = (
    _implementation_sha256()
)


class Stage6WrapperError(
    RuntimeError
):
    """Stage 6 wrapper failed closed."""


@dataclass(frozen=True)
class HoldoutExpectations:
    artifact_sha256: str
    count: int
    distinct_species_count: int
    membership_sha256: str


@dataclass(frozen=True)
class SourceMetadata:
    accession: str
    source_group: str
    batch: str
    source_evidence_sha256: str
    topology_circular_records: int
    topology_linear_records: int


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        for chunk in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def _validate_sha256(
    value: object,
    *,
    label: str,
) -> str:
    text = str(
        value
    ).strip()

    if LOWER_SHA256_RE.fullmatch(
        text
    ) is None:
        raise Stage6WrapperError(
            f"{label} is not a lowercase SHA256"
        )

    return text


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    expected = _validate_sha256(
        expected,
        label=f"{label} expected SHA256",
    )

    current = Path(
        path
    )

    if (
        not current.is_file()
        or current.is_symlink()
    ):
        raise Stage6WrapperError(
            f"{label} is not a regular non-symlink file"
        )

    observed = sha256_file(
        current
    )

    if observed != expected:
        raise Stage6WrapperError(
            f"{label} SHA256 mismatch"
        )

    return observed


def _run_git(
    repo: Path,
    *arguments: str,
) -> str:
    try:
        completed = subprocess.run(
            (
                "git",
                "-C",
                str(
                    repo
                ),
                *arguments,
            ),
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise Stage6WrapperError(
            "repository Git command failed"
        ) from None

    return completed.stdout.strip()


def write_json_atomic(
    path: Path,
    payload: object,
) -> str:
    path = Path(
        path
    )

    temporary = path.with_name(
        "."
        + path.name
        + ".tmp"
    )

    if temporary.exists():
        raise Stage6WrapperError(
            "temporary JSON path already exists"
        )

    data = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    try:
        temporary.write_bytes(
            data
        )

        os.replace(
            temporary,
            path,
        )
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise

    return sha256_file(
        path
    )


def write_bytes_atomic(
    path: Path,
    payload: bytes,
) -> str:
    path = Path(
        path
    )

    temporary = path.with_name(
        "."
        + path.name
        + ".tmp"
    )

    if temporary.exists():
        raise Stage6WrapperError(
            "temporary byte-output path already exists"
        )

    try:
        temporary.write_bytes(
            payload
        )

        os.replace(
            temporary,
            path,
        )
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise

    return sha256_file(
        path
    )


def write_tsv_atomic(
    path: Path,
    fields: Sequence[str],
    rows: Iterable[
        Mapping[
            str,
            object,
        ]
    ],
) -> str:
    path = Path(
        path
    )

    temporary = path.with_name(
        "."
        + path.name
        + ".tmp"
    )

    if temporary.exists():
        raise Stage6WrapperError(
            "temporary TSV path already exists"
        )

    try:
        with temporary.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(
                    fields
                ),
                delimiter="\t",
                lineterminator="\n",
                extrasaction="raise",
            )

            writer.writeheader()

            for row in rows:
                if set(
                    row
                ) != set(
                    fields
                ):
                    raise Stage6WrapperError(
                        "TSV row field set mismatch"
                    )

                writer.writerow(
                    row
                )

        os.replace(
            temporary,
            path,
        )
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise

    return sha256_file(
        path
    )


def _ensure_output_root_outside_repo(
    output_root: Path,
    repo: Path,
) -> Path:
    root = Path(
        output_root
    ).expanduser().resolve()

    repository = Path(
        repo
    ).resolve()

    try:
        root.relative_to(
            repository
        )
    except ValueError:
        pass
    else:
        raise Stage6WrapperError(
            "Stage 6 output root must be outside repository"
        )

    return root


def preflight_repository(
    repo: Path,
    expected_commit: str,
    *,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> dict[
    str,
    str,
]:
    repo = Path(
        repo
    ).resolve()

    if LOWER_COMMIT_RE.fullmatch(
        expected_commit
    ) is None:
        raise Stage6WrapperError(
            "expected Stage 6 execution commit malformed"
        )

    wrapper_sha = _validate_sha256(
        expected_wrapper_sha256,
        label="Stage 6 wrapper SHA256",
    )

    wrapper_test_sha = _validate_sha256(
        expected_wrapper_test_sha256,
        label="Stage 6 wrapper-test SHA256",
    )

    if _run_git(
        repo,
        "rev-parse",
        "HEAD",
    ) != expected_commit:
        raise Stage6WrapperError(
            "repository HEAD differs from expected execution commit"
        )

    if _run_git(
        repo,
        "rev-parse",
        "origin/main",
    ) != expected_commit:
        raise Stage6WrapperError(
            "origin/main differs from expected execution commit"
        )

    if _run_git(
        repo,
        "status",
        "--porcelain",
    ):
        raise Stage6WrapperError(
            "repository working tree is not clean"
        )

    observed: dict[
        str,
        str,
    ] = {}

    for relative, expected_sha in (
        sorted(
            FROZEN_REPO_FILES.items(),
            key=lambda item:
                item[0].as_posix(),
        )
    ):
        path = (
            repo
            / relative
        )

        observed[
            relative.as_posix()
        ] = require_sha256(
            path,
            expected_sha,
            relative.as_posix(),
        )

    observed[
        WRAPPER_RELATIVE.as_posix()
    ] = require_sha256(
        repo
        / WRAPPER_RELATIVE,
        wrapper_sha,
        "Stage 6 production wrapper",
    )

    observed[
        WRAPPER_TEST_RELATIVE.as_posix()
    ] = require_sha256(
        repo
        / WRAPPER_TEST_RELATIVE,
        wrapper_test_sha,
        "Stage 6 production-wrapper tests",
    )

    return dict(
        sorted(
            observed.items()
        )
    )


def load_stage5b_completion(
    repo: Path,
) -> HoldoutExpectations:
    path = (
        Path(
            repo
        )
        / STAGE5B_COMPLETION_RELATIVE
    )

    require_sha256(
        path,
        EXPECTED_STAGE5B_COMPLETION_SHA256,
        "Stage 5B completion evidence",
    )

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        raise Stage6WrapperError(
            "Stage 5B completion evidence could not be parsed"
        ) from None

    if not isinstance(
        payload,
        dict,
    ):
        raise Stage6WrapperError(
            "Stage 5B completion evidence root is not an object"
        )

    holdout = payload.get(
        "external_holdout"
    )

    if not isinstance(
        holdout,
        dict,
    ):
        raise Stage6WrapperError(
            "Stage 5B completion evidence lacks external_holdout"
        )

    expected = HoldoutExpectations(
        artifact_sha256=(
            EXPECTED_HOLDOUT_ARTIFACT_SHA256
        ),
        count=(
            EXPECTED_HOLDOUT_COUNT
        ),
        distinct_species_count=(
            EXPECTED_HOLDOUT_SPECIES_COUNT
        ),
        membership_sha256=(
            EXPECTED_HOLDOUT_MEMBERSHIP_SHA256
        ),
    )

    observed = HoldoutExpectations(
        artifact_sha256=_validate_sha256(
            holdout.get(
                "artifact_sha256"
            ),
            label="Stage 5B holdout artifact SHA256",
        ),
        count=holdout.get(
            "count"
        ),
        distinct_species_count=holdout.get(
            "distinct_species_count"
        ),
        membership_sha256=_validate_sha256(
            holdout.get(
                "membership_sha256"
            ),
            label="Stage 5B holdout membership SHA256",
        ),
    )

    if observed != expected:
        raise Stage6WrapperError(
            "Stage 5B holdout completion binding mismatch"
        )

    artifacts = payload.get(
        "artifacts_sha256"
    )

    if not isinstance(
        artifacts,
        dict,
    ):
        raise Stage6WrapperError(
            "Stage 5B artifact identity map missing"
        )

    if (
        artifacts.get(
            "external-decision-holdout.tsv"
        )
        != expected.artifact_sha256
    ):
        raise Stage6WrapperError(
            "Stage 5B holdout artifact map mismatch"
        )

    later_stage = payload.get(
        "later_stage"
    )

    if not isinstance(
        later_stage,
        dict,
    ):
        raise Stage6WrapperError(
            "Stage 5B later-stage boundary missing"
        )

    if (
        later_stage.get(
            "structural_features_calculated"
        )
        is not False
        or later_stage.get(
            "selector_outcomes_calculated"
        )
        is not False
    ):
        raise Stage6WrapperError(
            "Stage 5B later-stage boundary is not intact"
        )

    return expected


def _physical_holdout_preflight(
    holdout_path: Path,
    expectations: HoldoutExpectations,
) -> None:
    require_sha256(
        holdout_path,
        expectations.artifact_sha256,
        "frozen Stage 5B holdout artifact",
    )


def load_stage2_wrapper(
    repo: Path,
) -> ModuleType:
    path = (
        Path(
            repo
        )
        / STAGE2_WRAPPER_RELATIVE
    )

    require_sha256(
        path,
        EXPECTED_STAGE2_WRAPPER_SHA256,
        "Stage 2 operational wrapper",
    )

    spec = importlib.util.spec_from_file_location(
        "_bacselect_frozen_stage2_for_stage6",
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise Stage6WrapperError(
            "could not load frozen Stage 2 wrapper"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        spec.name
    ] = module

    try:
        spec.loader.exec_module(
            module
        )
    except Exception:
        raise Stage6WrapperError(
            "frozen Stage 2 wrapper import failed"
        ) from None

    return module


def load_finch_driver(
    repo: Path,
) -> ModuleType:
    path = (
        Path(
            repo
        )
        / FINCH_DRIVER_RELATIVE
    )

    require_sha256(
        path,
        EXPECTED_FINCH_DRIVER_SHA256,
        "vendored Finch structural-feature driver",
    )

    require_sha256(
        Path(
            repo
        )
        / FINCH_BASIC_RELATIVE,
        EXPECTED_FINCH_BASIC_SHA256,
        "vendored Finch basic structural-feature module",
    )

    spec = importlib.util.spec_from_file_location(
        "_bacselect_frozen_finch_stage6_driver",
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise Stage6WrapperError(
            "could not load frozen Finch driver"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        spec.name
    ] = module

    try:
        spec.loader.exec_module(
            module
        )
    except Exception:
        raise Stage6WrapperError(
            "frozen Finch driver import failed"
        ) from None

    return module


def compile_frozen_engine(
    *,
    repo: Path,
    env_prefix: Path,
    build_dir: Path,
) -> tuple[
    Path,
    str,
]:
    source = (
        Path(
            repo
        )
        / ENGINE_SOURCE_RELATIVE
    )

    require_sha256(
        source,
        EXPECTED_ENGINE_SOURCE_SHA256,
        "frozen structural-feature engine source",
    )

    require_sha256(
        Path(
            repo
        )
        / ENV_LOCK_RELATIVE,
        EXPECTED_ENV_LOCK_SHA256,
        "frozen repeat environment lock",
    )

    prefix = Path(
        env_prefix
    ).expanduser().resolve()

    compiler = (
        prefix
        / "bin"
        / "x86_64-conda-linux-gnu-c++"
    )

    header = (
        prefix
        / "include"
        / "divsufsort.h"
    )

    library = (
        prefix
        / "lib"
        / "libdivsufsort.so"
    )

    if (
        not compiler.is_file()
        or not os.access(
            compiler,
            os.X_OK,
        )
    ):
        raise Stage6WrapperError(
            "frozen repeat compiler unavailable"
        )

    if not header.is_file():
        raise Stage6WrapperError(
            "frozen repeat divsufsort header unavailable"
        )

    if not library.is_file():
        raise Stage6WrapperError(
            "frozen repeat divsufsort library unavailable"
        )

    build_dir = Path(
        build_dir
    )

    build_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    engine = (
        build_dir
        / "structural_features_fast"
    )

    try:
        subprocess.run(
            (
                str(
                    compiler
                ),
                "-std=c++17",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-Werror",
                f"-I{prefix / 'include'}",
                str(
                    source
                ),
                f"-L{prefix / 'lib'}",
                (
                    "-Wl,-rpath,"
                    + str(
                        prefix
                        / "lib"
                    )
                ),
                "-ldivsufsort",
                "-o",
                str(
                    engine
                ),
            ),
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        raise Stage6WrapperError(
            "frozen structural-feature engine compilation failed"
        ) from None

    observed = require_sha256(
        engine,
        EXPECTED_ENGINE_BINARY_SHA256,
        "compiled structural-feature engine",
    )

    if not os.access(
        engine,
        os.X_OK,
    ):
        raise Stage6WrapperError(
            "compiled structural-feature engine is not executable"
        )

    return (
        engine,
        observed,
    )


def _load_holdout(
    path: Path,
    *,
    expectations: HoldoutExpectations,
    stage1: ModuleType,
) -> dict[
    str,
    str,
]:
    try:
        with Path(
            path
        ).open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            reader = csv.DictReader(
                handle,
                delimiter="\t",
            )

            if tuple(
                reader.fieldnames
                or ()
            ) != HOLDOUT_FIELDS:
                raise Stage6WrapperError(
                    "frozen holdout schema mismatch"
                )

            rows = list(
                reader
            )
    except Stage6WrapperError:
        raise
    except Exception:
        raise Stage6WrapperError(
            "frozen holdout could not be parsed"
        ) from None

    if len(
        rows
    ) != expectations.count:
        raise Stage6WrapperError(
            "frozen holdout row count mismatch"
        )

    observed: dict[
        str,
        str,
    ] = {}

    for row in rows:
        accession = stage1.require_accession(
            row.get(
                "canonical_genbank_assembly_accession"
            ),
            "Stage 6 holdout accession",
        )

        if accession in observed:
            raise Stage6WrapperError(
                "duplicate accession in frozen holdout"
            )

        species_taxid = str(
            row.get(
                "species_taxid",
                ""
            )
        ).strip()

        if POSITIVE_INTEGER_TEXT_RE.fullmatch(
            species_taxid
        ) is None:
            raise Stage6WrapperError(
                "frozen holdout species TaxID is not canonical positive integer text"
            )

        observed[
            accession
        ] = species_taxid

    membership_sha = (
        stage1.accession_membership_sha256(
            observed
        )
    )

    if (
        membership_sha
        != expectations.membership_sha256
    ):
        raise Stage6WrapperError(
            "frozen holdout membership SHA256 mismatch"
        )

    species_count = len(
        set(
            observed.values()
        )
    )

    if (
        species_count
        != expectations.distinct_species_count
    ):
        raise Stage6WrapperError(
            "frozen holdout species-count mismatch"
        )

    return dict(
        sorted(
            observed.items()
        )
    )


def _build_source_metadata(
    *,
    bundle,
    accessions: Sequence[str],
    stage1: ModuleType,
) -> dict[
    str,
    SourceMetadata,
]:
    wanted = set(
        accessions
    )

    observed: dict[
        str,
        SourceMetadata,
    ] = {}

    all_batch_accessions: set[
        str
    ] = set()

    for batch in bundle.batches:
        if (
            batch.source_group
            not in source_structural_features.ALLOWED_SOURCE_GROUPS
        ):
            raise Stage6WrapperError(
                "unexpected authoritative source package class"
            )

        selected = tuple(
            candidate
            for candidate in batch.candidates
            if candidate.accession in wanted
        )

        for candidate in batch.candidates:
            accession = (
                candidate.accession
            )

            if accession in all_batch_accessions:
                raise Stage6WrapperError(
                    "duplicate candidate across authoritative package batches"
                )

            all_batch_accessions.add(
                accession
            )

        if not selected:
            continue

        selected_accessions = tuple(
            candidate.accession
            for candidate in selected
        )

        try:
            component_index = (
                stage1.load_component_index(
                    batch.component_audit,
                    accessions=(
                        selected_accessions
                    ),
                )
            )

            package_manifest = (
                stage1.load_package_manifest(
                    batch.package_manifest
                )
            )
        except Exception:
            raise Stage6WrapperError(
                "authoritative source evidence could not be loaded"
            ) from None

        for candidate in sorted(
            selected,
            key=lambda item:
                item.accession,
        ):
            accession = (
                candidate.accession
            )

            if accession in observed:
                raise Stage6WrapperError(
                    "holdout accession resolved to multiple source packages"
                )

            component_rows = (
                component_index.get(
                    accession
                )
            )

            if component_rows is None:
                raise Stage6WrapperError(
                    "holdout accession lacks component evidence"
                )

            try:
                source_sha = (
                    source_truth_execution
                    .source_evidence_sha256(
                        candidate,
                        component_rows,
                        package_manifest,
                    )
                )
            except Exception:
                raise Stage6WrapperError(
                    "upstream source-evidence fingerprint could not be reproduced"
                ) from None

            _validate_sha256(
                source_sha,
                label="upstream source-evidence SHA256",
            )

            circular = 0
            linear = 0

            for component in component_rows:
                if component.topology == "circular":
                    circular += 1
                elif component.topology == "linear":
                    linear += 1
                else:
                    raise Stage6WrapperError(
                        "component evidence contains unsupported topology"
                    )

            if (
                circular
                + linear
                != candidate.primary_assembly_records
            ):
                raise Stage6WrapperError(
                    "component topology count differs from candidate audit"
                )

            observed[
                accession
            ] = SourceMetadata(
                accession=accession,
                source_group=(
                    batch.source_group
                ),
                batch=batch.batch,
                source_evidence_sha256=(
                    source_sha
                ),
                topology_circular_records=(
                    circular
                ),
                topology_linear_records=(
                    linear
                ),
            )

    if set(
        observed
    ) != wanted:
        raise Stage6WrapperError(
            "holdout source-metadata binding incomplete"
        )

    return dict(
        sorted(
            observed.items()
        )
    )


def _format_feature(
    field: str,
    value: int | float,
) -> str:
    if field in INTEGER_FEATURE_FIELDS:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
        ):
            raise Stage6WrapperError(
                "integer Stage 6 feature has non-integer value"
            )

        return str(
            value
        )

    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            (
                int,
                float,
            ),
        )
    ):
        raise Stage6WrapperError(
            "floating Stage 6 feature is not numeric"
        )

    current = float(
        value
    )

    if not math.isfinite(
        current
    ):
        raise Stage6WrapperError(
            "Stage 6 matrix feature is non-finite"
        )

    return format(
        current,
        ".17g",
    )


def _feature_row_bytes(
    *,
    accession: str,
    species_taxid: str,
    features: Mapping[
        str,
        int | float,
    ],
) -> bytes:
    if tuple(
        features
    ) != (
        source_structural_feature_execution
        .FEATURE_FIELDS
    ):
        raise Stage6WrapperError(
            "Stage 6 feature record schema/order mismatch"
        )

    values = [
        accession,
        species_taxid,
    ]

    values.extend(
        _format_feature(
            field,
            features[
                field
            ],
        )
        for field in (
            source_structural_feature_execution
            .FEATURE_FIELDS
        )
    )

    return (
        "\t".join(
            values
        )
        + "\n"
    ).encode(
        "ascii"
    )


def _numeric_array_sha256(
    records: Sequence[
        source_structural_feature_execution.Stage6FeatureRecord
    ],
) -> str:
    digest = hashlib.sha256()

    for record in records:
        for field in (
            source_structural_feature_execution
            .FEATURE_FIELDS
        ):
            value = float(
                record.features[
                    field
                ]
            )

            if not math.isfinite(
                value
            ):
                raise Stage6WrapperError(
                    "non-finite value in Stage 6 numeric array"
                )

            digest.update(
                struct.pack(
                    "<d",
                    value,
                )
            )

    return digest.hexdigest()


def _evidence_row(
    *,
    source_group: str,
    batch: str,
    file_role: str,
    path: Path,
) -> dict[
    str,
    str,
]:
    current = Path(
        path
    )

    if (
        not current.is_file()
        or current.is_symlink()
    ):
        raise Stage6WrapperError(
            "input-evidence file is not a regular non-symlink file"
        )

    return {
        "source_group":
            source_group,
        "batch":
            batch,
        "file_role":
            file_role,
        "file_name":
            current.name,
        "size_bytes":
            str(
                current.stat().st_size
            ),
        "sha256":
            sha256_file(
                current
            ),
    }


def _validate_input_evidence_row(
    row: Mapping[
        str,
        object,
    ],
) -> dict[
    str,
    str,
]:
    if set(
        row
    ) != set(
        INPUT_EVIDENCE_FIELDS
    ):
        raise Stage6WrapperError(
            "authoritative input-evidence row schema mismatch"
        )

    result = {
        field:
            str(
                row[
                    field
                ]
            )
        for field in INPUT_EVIDENCE_FIELDS
    }

    try:
        size = int(
            result[
                "size_bytes"
            ]
        )
    except ValueError:
        raise Stage6WrapperError(
            "input-evidence size is not an integer"
        ) from None

    if size < 0:
        raise Stage6WrapperError(
            "input-evidence size is negative"
        )

    _validate_sha256(
        result[
            "sha256"
        ],
        label="input-evidence SHA256",
    )

    return result


def _input_evidence_rows(
    *,
    repo: Path,
    holdout_path: Path,
    frozen_repo_sha256: Mapping[
        str,
        str,
    ],
    bundle,
) -> tuple[
    dict[
        str,
        str,
    ],
    ...,
]:
    rows: list[
        dict[
            str,
            str,
        ]
    ] = []

    rows.append(
        _evidence_row(
            source_group="stage6-input",
            batch="",
            file_role="external_holdout",
            path=holdout_path,
        )
    )

    for relative in sorted(
        frozen_repo_sha256
    ):
        path = (
            repo
            / relative
        )

        observed = _evidence_row(
            source_group="stage6-repository",
            batch="",
            file_role=relative,
            path=path,
        )

        if (
            observed[
                "sha256"
            ]
            != frozen_repo_sha256[
                relative
            ]
        ):
            raise Stage6WrapperError(
                "frozen repository evidence identity changed"
            )

        rows.append(
            observed
        )

    for row in (
        bundle.input_evidence_rows
    ):
        rows.append(
            _validate_input_evidence_row(
                row
            )
        )

    return tuple(
        sorted(
            rows,
            key=lambda row:
                (
                    row[
                        "source_group"
                    ],
                    row[
                        "batch"
                    ],
                    row[
                        "file_role"
                    ],
                    row[
                        "file_name"
                    ],
                ),
        )
    )


def _content_manifest_rows(
    partial_dir: Path,
) -> tuple[
    dict[
        str,
        str,
    ],
    ...,
]:
    rows = []

    for name in sorted(
        CONTENT_COVERED_FILES
    ):
        path = (
            partial_dir
            / name
        )

        if not path.is_file():
            raise Stage6WrapperError(
                "Stage 6 content-manifest input missing"
            )

        rows.append(
            {
                "path":
                    name,
                "size_bytes":
                    str(
                        path.stat().st_size
                    ),
                "sha256":
                    sha256_file(
                        path
                    ),
            }
        )

    return tuple(
        rows
    )


def execute_to_scratch(
    *,
    repo: Path,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    output_root: Path,
    holdout_path: Path,
    holdout_expectations: HoldoutExpectations,
    frozen_repo_sha256: Mapping[
        str,
        str,
    ],
    stage1: ModuleType,
    finch,
    basic,
    engine: Path,
    expected_engine_sha256: str,
    population_factory: Callable[
        [],
        object,
    ],
    binding_builder: Callable = (
        source_structural_features
        .build_package_bindings
    ),
    source_metadata_builder: Callable = (
        _build_source_metadata
    ),
    feature_computer: Callable = (
        source_structural_feature_execution
        .compute_stage6_feature_record
    ),
) -> Path:
    """Execute Stage 6 with predecision-before-row-parsing ordering."""

    if LOWER_COMMIT_RE.fullmatch(
        expected_commit
    ) is None:
        raise Stage6WrapperError(
            "expected Stage 6 execution commit malformed"
        )

    wrapper_sha = _validate_sha256(
        expected_wrapper_sha256,
        label="Stage 6 wrapper SHA256",
    )

    wrapper_test_sha = _validate_sha256(
        expected_wrapper_test_sha256,
        label="Stage 6 wrapper-test SHA256",
    )

    expected_engine_sha = (
        _validate_sha256(
            expected_engine_sha256,
            label="compiled engine SHA256",
        )
    )

    observed_engine_sha = (
        require_sha256(
            engine,
            expected_engine_sha,
            "Stage 6 compiled engine",
        )
    )

    if not os.access(
        engine,
        os.X_OK,
    ):
        raise Stage6WrapperError(
            "Stage 6 compiled engine is not executable"
        )

    # Whole-file identity verification is allowed before predecision.
    # No holdout row is parsed here.
    _physical_holdout_preflight(
        holdout_path,
        holdout_expectations,
    )

    root = (
        _ensure_output_root_outside_repo(
            output_root,
            repo,
        )
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_dir = (
        root
        / expected_commit
    )

    partial_dir = (
        root
        / (
            "."
            + expected_commit
            + ".partial"
        )
    )

    if final_dir.exists():
        raise Stage6WrapperError(
            "final Stage 6 output directory already exists"
        )

    if partial_dir.exists():
        raise Stage6WrapperError(
            "partial Stage 6 output directory already exists"
        )

    partial_dir.mkdir()

    predecision_path = (
        partial_dir
        / "stage6-predecision-provenance.json"
    )

    predecision = {
        "schema_version":
            1,
        "status":
            "STAGE6_PREDECISION_FROZEN",
        "bacselect_git_commit":
            expected_commit,
        "stage5b_completion_evidence_sha256":
            EXPECTED_STAGE5B_COMPLETION_SHA256,
        "external_holdout_artifact_sha256":
            holdout_expectations.artifact_sha256,
        "external_holdout_count":
            holdout_expectations.count,
        "external_holdout_species_count":
            holdout_expectations.distinct_species_count,
        "external_holdout_membership_sha256":
            holdout_expectations.membership_sha256,
        "stage6_method_sha256":
            EXPECTED_STAGE6_METHOD_SHA256,
        "stage6_implementation_sha256":
            EXPECTED_STAGE6_IMPLEMENTATION_SHA256,
        "stage6_package_binding_helper_sha256":
            EXPECTED_BINDING_HELPER_SHA256,
        "stage6_feature_execution_sha256":
            EXPECTED_FEATURE_EXECUTION_SHA256,
        "stage6_wrapper_sha256":
            wrapper_sha,
        "stage6_wrapper_test_sha256":
            wrapper_test_sha,
        "stage1_operational_wrapper_sha256":
            EXPECTED_STAGE1_WRAPPER_SHA256,
        "stage2_operational_wrapper_sha256":
            EXPECTED_STAGE2_WRAPPER_SHA256,
        "source_truth_execution_sha256":
            EXPECTED_SOURCE_TRUTH_SHA256,
        "source_cache_verify_sha256":
            EXPECTED_SOURCE_CACHE_VERIFY_SHA256,
        "source_truth_primitive_sha256":
            EXPECTED_SOURCE_TRUTH_PRIMITIVE_SHA256,
        "source_fingerprint_sha256":
            EXPECTED_SOURCE_FINGERPRINT_SHA256,
        "chromosome_integrity_execution_sha256":
            EXPECTED_CHROMOSOME_EXECUTION_SHA256,
        "finch_driver_sha256":
            EXPECTED_FINCH_DRIVER_SHA256,
        "finch_basic_sha256":
            EXPECTED_FINCH_BASIC_SHA256,
        "finch_semantic_reference_sha256":
            EXPECTED_FINCH_REFERENCE_SHA256,
        "repeat_engine_source_sha256":
            EXPECTED_ENGINE_SOURCE_SHA256,
        "compiled_repeat_engine_sha256":
            observed_engine_sha,
        "repeat_environment_lock_sha256":
            EXPECTED_ENV_LOCK_SHA256,
        "frozen_repository_sha256":
            dict(
                sorted(
                    frozen_repo_sha256.items()
                )
            ),
        "holdout_rows_parsed":
            False,
        "source_package_manifests_parsed":
            False,
        "fasta_sequence_opened":
            False,
        "sequence_report_rows_opened":
            False,
        "structural_features_calculated":
            False,
        "percentile_coordinates_calculated":
            False,
        "ops_sr_distances_calculated":
            False,
        "panel_identities_generated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    predecision_sha = (
        write_json_atomic(
            predecision_path,
            predecision,
        )
    )

    # Identity-bearing work starts only after predecision exists on disk.
    try:
        holdout = _load_holdout(
            holdout_path,
            expectations=(
                holdout_expectations
            ),
            stage1=stage1,
        )

        bundle = population_factory()

        bindings = binding_builder(
            bundle=bundle,
            accessions=tuple(
                holdout
            ),
        )

        binding_by_accession = {
            binding.accession:
                binding
            for binding in bindings
        }

        if (
            len(
                binding_by_accession
            )
            != len(
                bindings
            )
        ):
            raise Stage6WrapperError(
                "duplicate accession in Stage 6 package bindings"
            )

        if set(
            binding_by_accession
        ) != set(
            holdout
        ):
            raise Stage6WrapperError(
                "Stage 6 package binding membership mismatch"
            )

        source_metadata = (
            source_metadata_builder(
                bundle=bundle,
                accessions=tuple(
                    holdout
                ),
                stage1=stage1,
            )
        )
    except Stage6WrapperError:
        raise
    except Exception:
        raise Stage6WrapperError(
            "Stage 6 holdout/package reconstruction failed closed"
        ) from None

    records: list[
        source_structural_feature_execution.Stage6FeatureRecord
    ] = []

    candidate_rows: list[
        dict[
            str,
            object,
        ]
    ] = []

    matrix_rows: list[
        bytes
    ] = []

    for accession in sorted(
        holdout
    ):
        binding = (
            binding_by_accession[
                accession
            ]
        )

        metadata = (
            source_metadata[
                accession
            ]
        )

        if (
            metadata.source_group
            != binding.source_group
            or metadata.batch
            != binding.batch
        ):
            raise Stage6WrapperError(
                "Stage 6 package/source metadata binding mismatch"
            )

        try:
            record = feature_computer(
                binding=binding,
                species_taxid=(
                    holdout[
                        accession
                    ]
                ),
                finch=finch,
                basic=basic,
                engine=engine,
            )
        except Exception:
            raise Stage6WrapperError(
                "candidate structural-feature execution failed closed"
            ) from None

        if record.accession != accession:
            raise Stage6WrapperError(
                "Stage 6 feature-record accession mismatch"
            )

        if (
            record.species_taxid
            != holdout[
                accession
            ]
        ):
            raise Stage6WrapperError(
                "Stage 6 feature-record species TaxID changed"
            )

        if (
            record.retained_replicon_count
            != (
                metadata.topology_circular_records
                + metadata.topology_linear_records
            )
        ):
            raise Stage6WrapperError(
                "Stage 6 retained replicon/topology count mismatch"
            )

        row_bytes = _feature_row_bytes(
            accession=accession,
            species_taxid=(
                holdout[
                    accession
                ]
            ),
            features=record.features,
        )

        feature_record_sha = (
            hashlib.sha256(
                row_bytes
            ).hexdigest()
        )

        records.append(
            record
        )

        matrix_rows.append(
            row_bytes
        )

        candidate_rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "source_group":
                    binding.source_group,
                "batch":
                    binding.batch,
                "source_evidence_sha256":
                    metadata.source_evidence_sha256,
                "genomic_fasta_sha256":
                    binding.fasta_sha256,
                "sequence_report_sha256":
                    binding.sequence_report_sha256,
                "retained_primary_assembly_replicon_count":
                    str(
                        record.retained_replicon_count
                    ),
                "total_retained_sequence_length":
                    str(
                        record.total_sequence_length
                    ),
                "topology_circular_records":
                    str(
                        metadata.topology_circular_records
                    ),
                "topology_linear_records":
                    str(
                        metadata.topology_linear_records
                    ),
                "feature_record_sha256":
                    feature_record_sha,
            }
        )

    if len(
        records
    ) != holdout_expectations.count:
        raise Stage6WrapperError(
            "Stage 6 feature-row count mismatch"
        )

    matrix_membership_sha = (
        stage1.accession_membership_sha256(
            record.accession
            for record in records
        )
    )

    if (
        matrix_membership_sha
        != holdout_expectations.membership_sha256
    ):
        raise Stage6WrapperError(
            "Stage 6 feature-matrix membership mismatch"
        )

    observed_species_count = len(
        {
            record.species_taxid
            for record in records
        }
    )

    if (
        observed_species_count
        != holdout_expectations.distinct_species_count
    ):
        raise Stage6WrapperError(
            "Stage 6 feature-matrix species count mismatch"
        )

    matrix_header = (
        "\t".join(
            MATRIX_FIELDS
        )
        + "\n"
    ).encode(
        "ascii"
    )

    matrix_payload = (
        matrix_header
        + b"".join(
            matrix_rows
        )
    )

    matrix_path = (
        partial_dir
        / "structural-feature-matrix-300-2400.tsv"
    )

    matrix_sha = write_bytes_atomic(
        matrix_path,
        matrix_payload,
    )

    numeric_array_sha = (
        _numeric_array_sha256(
            records
        )
    )

    candidate_evidence_path = (
        partial_dir
        / "stage6-candidate-evidence.tsv"
    )

    candidate_evidence_sha = (
        write_tsv_atomic(
            candidate_evidence_path,
            CANDIDATE_EVIDENCE_FIELDS,
            candidate_rows,
        )
    )

    input_manifest_path = (
        partial_dir
        / "stage6-input-evidence-manifest.tsv"
    )

    input_manifest_rows = (
        _input_evidence_rows(
            repo=repo,
            holdout_path=holdout_path,
            frozen_repo_sha256=(
                frozen_repo_sha256
            ),
            bundle=bundle,
        )
    )

    input_manifest_sha = (
        write_tsv_atomic(
            input_manifest_path,
            INPUT_EVIDENCE_FIELDS,
            input_manifest_rows,
        )
    )

    execution_provenance_path = (
        partial_dir
        / "stage6-execution-provenance.json"
    )

    execution_provenance = {
        "schema_version":
            1,
        "status":
            "STAGE6_RAW_STRUCTURAL_FEATURES_COMPLETE",
        "bacselect_git_commit":
            expected_commit,
        "stage6_method_sha256":
            EXPECTED_STAGE6_METHOD_SHA256,
        "stage6_implementation_sha256":
            EXPECTED_STAGE6_IMPLEMENTATION_SHA256,
        "stage6_package_binding_helper_sha256":
            EXPECTED_BINDING_HELPER_SHA256,
        "stage6_feature_execution_sha256":
            EXPECTED_FEATURE_EXECUTION_SHA256,
        "source_truth_execution_sha256":
            EXPECTED_SOURCE_TRUTH_SHA256,
        "source_cache_verify_sha256":
            EXPECTED_SOURCE_CACHE_VERIFY_SHA256,
        "source_truth_primitive_sha256":
            EXPECTED_SOURCE_TRUTH_PRIMITIVE_SHA256,
        "source_fingerprint_sha256":
            EXPECTED_SOURCE_FINGERPRINT_SHA256,
        "stage6_wrapper_sha256":
            wrapper_sha,
        "stage6_wrapper_test_sha256":
            wrapper_test_sha,
        "predecision_provenance_sha256":
            predecision_sha,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "compiled_repeat_engine_sha256":
            observed_engine_sha,
        "repeat_engine_source_sha256":
            EXPECTED_ENGINE_SOURCE_SHA256,
        "repeat_environment_lock_sha256":
            EXPECTED_ENV_LOCK_SHA256,
        "finch_driver_sha256":
            EXPECTED_FINCH_DRIVER_SHA256,
        "finch_basic_sha256":
            EXPECTED_FINCH_BASIC_SHA256,
        "finch_semantic_reference_sha256":
            EXPECTED_FINCH_REFERENCE_SHA256,
        "raw_feature_matrix_artifact_sha256":
            matrix_sha,
        "raw_feature_matrix_membership_sha256":
            matrix_membership_sha,
        "raw_feature_matrix_row_count":
            len(
                records
            ),
        "raw_feature_matrix_species_count":
            observed_species_count,
        "raw_feature_matrix_numeric_array_sha256":
            numeric_array_sha,
        "candidate_evidence_artifact_sha256":
            candidate_evidence_sha,
        "holdout_rows_parsed":
            True,
        "source_package_manifests_parsed":
            True,
        "fasta_sequence_opened":
            True,
        "sequence_report_rows_opened":
            True,
        "structural_features_calculated":
            True,
        "percentile_coordinates_calculated":
            False,
        "ops_sr_distances_calculated":
            False,
        "panel_identities_generated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    execution_provenance_sha = (
        write_json_atomic(
            execution_provenance_path,
            execution_provenance,
        )
    )

    summary_path = (
        partial_dir
        / "stage6-aggregate-summary.json"
    )

    summary = {
        "schema_version":
            1,
        "status":
            "STAGE6_RAW_STRUCTURAL_FEATURES_COMPLETE",
        "external_holdout_count":
            holdout_expectations.count,
        "external_holdout_species_count":
            holdout_expectations.distinct_species_count,
        "external_holdout_membership_sha256":
            holdout_expectations.membership_sha256,
        "successful_feature_row_count":
            len(
                records
            ),
        "raw_feature_matrix_artifact_sha256":
            matrix_sha,
        "raw_feature_matrix_membership_sha256":
            matrix_membership_sha,
        "raw_feature_matrix_numeric_array_sha256":
            numeric_array_sha,
        "candidate_evidence_artifact_sha256":
            candidate_evidence_sha,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "predecision_provenance_sha256":
            predecision_sha,
        "execution_provenance_sha256":
            execution_provenance_sha,
        "structural_features_calculated":
            True,
        "percentile_coordinates_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    summary_sha = write_json_atomic(
        summary_path,
        summary,
    )

    content_manifest_path = (
        partial_dir
        / "stage6-content-manifest.tsv"
    )

    content_manifest_sha = (
        write_tsv_atomic(
            content_manifest_path,
            CONTENT_MANIFEST_FIELDS,
            _content_manifest_rows(
                partial_dir
            ),
        )
    )

    observed_final_files = {
        path.name
        for path in partial_dir.iterdir()
        if path.is_file()
    }

    if observed_final_files != FINAL_FILES:
        raise Stage6WrapperError(
            "Stage 6 final artifact set mismatch"
        )

    if final_dir.exists():
        raise Stage6WrapperError(
            "final Stage 6 output appeared during execution"
        )

    os.replace(
        partial_dir,
        final_dir,
    )

    print(
        "PASS | Stage 6 raw structural-feature execution complete"
    )
    print(
        f"external_holdout_count={holdout_expectations.count}"
    )
    print(
        "external_holdout_species_count="
        f"{holdout_expectations.distinct_species_count}"
    )
    print(
        "external_holdout_membership_sha256="
        f"{holdout_expectations.membership_sha256}"
    )
    print(
        f"successful_feature_row_count={len(records)}"
    )
    print(
        f"raw_feature_matrix_artifact_sha256={matrix_sha}"
    )
    print(
        "raw_feature_matrix_membership_sha256="
        f"{matrix_membership_sha}"
    )
    print(
        "raw_feature_matrix_numeric_array_sha256="
        f"{numeric_array_sha}"
    )
    print(
        f"candidate_evidence_artifact_sha256={candidate_evidence_sha}"
    )
    print(
        f"predecision_provenance_sha256={predecision_sha}"
    )
    print(
        f"input_evidence_manifest_sha256={input_manifest_sha}"
    )
    print(
        "execution_provenance_sha256="
        f"{execution_provenance_sha}"
    )
    print(
        f"aggregate_summary_sha256={summary_sha}"
    )
    print(
        f"content_manifest_sha256={content_manifest_sha}"
    )
    print(
        f"execution_dir={final_dir}"
    )

    return final_dir


def parse_args(
    argv: list[
        str
    ] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute frozen BacSelect selector-v1 Stage 6 "
            "raw structural-feature calculation."
        )
    )

    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--expected-commit",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-test-sha256",
        required=True,
    )

    parser.add_argument(
        "--holdout",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--historical-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--cache-reuse-accessions",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--cache-reuse-manifest",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--cache-verification",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--fresh-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--recovery-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--repeat-env-prefix",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )

    return parser.parse_args(
        argv
    )


def main(
    argv: list[
        str
    ] | None = None,
) -> int:
    args = parse_args(
        argv
    )

    repo = (
        args.repo
        .expanduser()
        .resolve()
    )

    holdout_expectations = (
        load_stage5b_completion(
            repo
        )
    )

    frozen_repo_sha256 = (
        preflight_repository(
            repo,
            args.expected_commit,
            expected_wrapper_sha256=(
                args.expected_wrapper_sha256
            ),
            expected_wrapper_test_sha256=(
                args.expected_wrapper_test_sha256
            ),
        )
    )

    stage2 = load_stage2_wrapper(
        repo
    )

    try:
        stage1 = (
            stage2.load_stage1_wrapper(
                repo
            )
        )
    except Exception:
        raise Stage6WrapperError(
            "frozen Stage 1 wrapper could not be loaded"
        ) from None

    finch = load_finch_driver(
        repo
    )

    basic = finch.basic

    with tempfile.TemporaryDirectory(
        prefix=(
            "bacselect-stage6-engine-"
        )
    ) as temporary:
        build_dir = (
            Path(
                temporary
            )
            / "build"
        )

        engine, engine_sha = (
            compile_frozen_engine(
                repo=repo,
                env_prefix=(
                    args.repeat_env_prefix
                ),
                build_dir=(
                    build_dir
                ),
            )
        )

        if (
            engine_sha
            != EXPECTED_ENGINE_BINARY_SHA256
        ):
            raise Stage6WrapperError(
                "compiled engine identity mismatch"
            )

        def population_factory():
            try:
                return (
                    stage2
                    .reconstruct_stage1_population(
                        repo=repo,
                        stage1=stage1,
                        historical_root=(
                            args.historical_root
                        ),
                        cache_reuse_accessions=(
                            args.cache_reuse_accessions
                        ),
                        cache_reuse_manifest=(
                            args.cache_reuse_manifest
                        ),
                        cache_verification=(
                            args.cache_verification
                        ),
                        fresh_root=(
                            args.fresh_root
                        ),
                        recovery_root=(
                            args.recovery_root
                        ),
                    )
                )
            except Exception:
                raise Stage6WrapperError(
                    "authoritative Stage 1 population reconstruction failed"
                ) from None

        execute_to_scratch(
            repo=repo,
            expected_commit=(
                args.expected_commit
            ),
            expected_wrapper_sha256=(
                args.expected_wrapper_sha256
            ),
            expected_wrapper_test_sha256=(
                args.expected_wrapper_test_sha256
            ),
            output_root=(
                args.output_root
            ),
            holdout_path=(
                args.holdout
            ),
            holdout_expectations=(
                holdout_expectations
            ),
            frozen_repo_sha256=(
                frozen_repo_sha256
            ),
            stage1=stage1,
            finch=finch,
            basic=basic,
            engine=engine,
            expected_engine_sha256=(
                engine_sha
            ),
            population_factory=(
                population_factory
            ),
        )

    return 0


def cli() -> int:
    try:
        return main()
    except Exception:
        print(
            "ERROR | Stage 6 structural-feature execution failed closed",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        cli()
    )
