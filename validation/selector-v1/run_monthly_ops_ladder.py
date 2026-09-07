#!/usr/bin/env python3
"""Monthly Stage 13 complete OPS diversity ladder for BacSelect.

Stage 13 authenticates the closed monthly percentile geometry and closed
monthly species-representative population, then ranks every current species
representative with the frozen selector-v1 OPS ladder primitive.

The complete monthly ladder is not limited to N=500. Public panels are later
derived as prefixes by Stage 14.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Callable, Iterable, Mapping

import numpy as np
import numpy.typing as npt

from bacselect import monthly_geometry
from bacselect.monthly_structural_features import (
    accession_membership_sha256,
)
from bacselect.ops import ops_ladder
from bacselect.tie import tie_key


RELEASE_ID = "2026.09"

SOURCE_SNAPSHOT_ID = (
    "bacselect-source-2026.09-20260901T021652Z"
)

REMOTE_BRANCH = (
    "origin/recovery/monthly-missing-datasets-gbff"
)

STAGE11_STAGE_NAME = "percentile-geometry"
STAGE11_MATRIX_NAME = (
    "species-balanced-percentile-feature-matrix-300-2400.tsv"
)
STAGE11_RECORD_NAME = (
    "monthly-percentile-geometry-record.json"
)
STAGE11_COMPLETION_NAME = (
    "percentile-geometry-completion-v1.json"
)

STAGE12_STAGE_NAME = "species-representatives"
STAGE12_TABLE_NAME = "species-representatives.tsv"
STAGE12_RECORD_NAME = (
    "monthly-species-representative-record.json"
)
STAGE12_COMPLETION_NAME = (
    "species-representatives-completion-v1.json"
)

STAGE_NAME = "ops-ladder"
PARTIAL_NAME = "ops-ladder.partial"
TABLE_NAME = "complete-ops-ladder.tsv"
RECORD_NAME = "monthly-ops-ladder-record.json"
COMPLETION_NAME = "ops-ladder-completion-v1.json"
COMPLETION_TEMP_NAME = (
    "ops-ladder-completion-v1.json.partial"
)

STAGE_FILES = frozenset(
    {
        TABLE_NAME,
        RECORD_NAME,
    }
)

TABLE_FIELDS = (
    "rank",
    "species_taxid",
    "canonical_genbank_assembly_accession",
)

RECORD_SCHEMA = (
    "bacselect-monthly-complete-ops-ladder-record-v1"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-complete-ops-ladder-completion-v1"
)

STATUS = (
    "MONTHLY_COMPLETE_OPS_LADDER_COMPLETE"
)

SELECTOR = "OPS"
SELECTOR_VERSION = "1.0.0"

PANEL_SIZES = (
    10,
    20,
    50,
    100,
    200,
    500,
)

EXPECTED_STAGE11_EXECUTION_COMMIT = (
    "add30c92a95f1c12cef630676e7f419614d34684"
)

EXPECTED_STAGE11_MATRIX_SHA256 = (
    "cb3c8d14e8d0bd4982de4a92219a7a4b"
    "d307663bf22d9e4234690d34367f0935"
)

EXPECTED_STAGE11_RECORD_SHA256 = (
    "d7e231455a3208d8cf4a48bf105d6c60"
    "8e766b42273795577a1daf2f900411be"
)

EXPECTED_STAGE11_COMPLETION_SHA256 = (
    "901508c9bf074e3d557c93d9636e8f2c"
    "3fee98f51ba78e3a5bc8a070dbc4ba87"
)

EXPECTED_STAGE11_MEMBERSHIP_SHA256 = (
    "6e6b44bd598bf472ea2a74686aaabcd23"
    "058832938279fb13a4d8ae6cdf7607d"
)

EXPECTED_STAGE11_SPECIES_MAPPING_SHA256 = (
    "103c0539c4e55863f43e756e64c3d9c3"
    "0ab2c49ef205e12cc640bb53a92e68d8"
)

EXPECTED_STAGE11_PERCENTILE_ARRAY_SHA256 = (
    "da76cc78da56c06524923c1977bbc671"
    "d31f5149ea9f9f103b2fc52d051cfc78"
)

EXPECTED_STAGE12_EXECUTION_COMMIT = (
    "2779c932f361df2d45d6044ecc09be668fa2131c"
)

EXPECTED_STAGE12_TABLE_SHA256 = (
    "93bc7de1da0e20688cc5c6d72ed01215"
    "f643e4a047442c2ba606e84dc354f584"
)

EXPECTED_STAGE12_RECORD_SHA256 = (
    "2f40254f452b33de34745030d2bd9211e"
    "7fe9d1cf2c081eea23dd245ea1558d5"
)

EXPECTED_STAGE12_COMPLETION_SHA256 = (
    "5f6a6f4ffc6e8b07c49f64778dd9f178"
    "94e3a45555a920eaea3da7957ab7298b"
)

EXPECTED_REPRESENTATIVE_SEQUENCE_SHA256 = (
    "48bf6ec422cdea831f9648b6a3e17c4a"
    "6c58fcb07c9aa2f7d4cd5fd1f7326144"
)

EXPECTED_REPRESENTATIVE_MEMBERSHIP_SHA256 = (
    "bbeb032ba83561d4b02c1ec582691ec9"
    "aab690828b2e23def9a5be679cf70052"
)

EXPECTED_TOTAL_COUNT = 68164
EXPECTED_SPECIES_COUNT = 16223
EXPECTED_REPRESENTATIVE_COUNT = 16223
EXPECTED_FEATURE_COUNT = 12

EXPECTED_OPS_SHA256 = (
    "eb6c1b8edab3e694b0f3825bb5ab0eaf"
    "44fdd95fdbb6a6e3e41439c18c828c0f"
)

EXPECTED_OPS_TEST_SHA256 = (
    "7eec19ebcfda97a3423b9c1c8b50ed22"
    "0bcbd81f79f5f38ca865359269307f58"
)

EXPECTED_TIE_SHA256 = (
    "a5746d3d40e3d267398f80eb83ab2f4b"
    "1ee84808f3d9a7715dade7fc0824f73e"
)

EXPECTED_TIE_TEST_SHA256 = (
    "b08954d007af923eebd44c4ca4909f10"
    "4d49e389069deb24398f6ec13f6af192"
)

EXPECTED_ENVIRONMENT_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207eaef"
    "5c2435e1b6feeddc1e4654686bc2a8c"
)

EXPECTED_SELECTOR_DECISION_SHA256 = (
    "d0cf63ad4d933194e3e782912a2a2a3c"
    "617353758d2c87c1b1198681a75869e2"
)

FROZEN_REPO_FILES: Mapping[str, str] = {
    "src/bacselect/ops.py":
        EXPECTED_OPS_SHA256,
    "tests/test_ops.py":
        EXPECTED_OPS_TEST_SHA256,
    "src/bacselect/tie.py":
        EXPECTED_TIE_SHA256,
    "tests/test_tie.py":
        EXPECTED_TIE_TEST_SHA256,
    "envs/bacselect-dev-linux-64.lock":
        EXPECTED_ENVIRONMENT_LOCK_SHA256,
    "validation/selector-v1/stage7-selector-decision-record.json":
        EXPECTED_SELECTOR_DECISION_SHA256,
}

_GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

_TAXID_RE = re.compile(
    r"^[1-9][0-9]*$"
)

_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_SHA_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class MonthlyOpsLadderError(RuntimeError):
    """Raised when monthly Stage 13 cannot be authenticated."""


@dataclass(frozen=True)
class Stage11Authority:
    accessions: tuple[str, ...]
    species_ids: tuple[str, ...]
    coordinates: npt.NDArray[np.float64]


@dataclass(frozen=True)
class Stage12Authority:
    species_ids: tuple[str, ...]
    accessions: tuple[str, ...]


@dataclass(frozen=True)
class OpsLadderRow:
    rank: int
    species_taxid: str
    accession: str


@dataclass(frozen=True)
class OpsLadderBuild:
    rows: tuple[OpsLadderRow, ...]
    complete_ladder_sha256: str
    ladder_membership_sha256: str
    n500_prefix_sha256: str


@dataclass(frozen=True)
class MonthlyOpsLadderExecutionResult:
    stage_path: Path
    completion_path: Path
    table_sha256: str
    record_sha256: str
    completion_sha256: str
    complete_ladder_sha256: str
    ladder_membership_sha256: str
    n500_prefix_sha256: str
    ladder_count: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def sequence_sha256(
    namespace: str,
    values: Iterable[str],
) -> str:
    payload = (
        namespace
        + "\n"
        + "\n".join(values)
        + "\n"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def ladder_namespace(
    count: int,
) -> str:
    if (
        not isinstance(count, int)
        or count < 1
    ):
        raise MonthlyOpsLadderError(
            "ladder count must be a positive integer"
        )

    return (
        "BacSelect-selector-v1|"
        "final300-2400|OPS|ladder|"
        f"N={count}"
    )


def _canonical_json(
    payload: Mapping[str, object],
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _git(
    repo: Path,
    *args: str,
) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    resolved = Path(path).resolve()

    if (
        not resolved.is_dir()
        or resolved.is_symlink()
    ):
        raise MonthlyOpsLadderError(
            f"{label} is not a real directory: {resolved}"
        )

    return resolved


def _require_sha(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA_RE.fullmatch(value) is None
    ):
        raise MonthlyOpsLadderError(
            f"{label} is not a lowercase SHA256"
        )

    return value


def repository_preflight(
    repo: Path,
    *,
    execution_commit: str,
) -> Path:
    root = _require_real_directory(
        repo,
        label="repository",
    )

    if _COMMIT_RE.fullmatch(
        execution_commit
    ) is None:
        raise MonthlyOpsLadderError(
            "Stage 13 execution commit is malformed"
        )

    if _git(
        root,
        "rev-parse",
        "HEAD",
    ) != execution_commit:
        raise MonthlyOpsLadderError(
            "repository HEAD differs from Stage 13 execution commit"
        )

    if _git(
        root,
        "rev-parse",
        REMOTE_BRANCH,
    ) != execution_commit:
        raise MonthlyOpsLadderError(
            "remote Stage 13 branch differs from execution commit"
        )

    if _git(
        root,
        "status",
        "--porcelain",
    ):
        raise MonthlyOpsLadderError(
            "repository working tree is not clean"
        )

    return root


def verify_frozen_dependencies(
    repo: Path,
) -> Mapping[str, str]:
    observed: dict[str, str] = {}

    for relative, expected in (
        FROZEN_REPO_FILES.items()
    ):
        path = repo / relative

        if (
            not path.is_file()
            or path.is_symlink()
        ):
            raise MonthlyOpsLadderError(
                f"frozen Stage 13 dependency missing: {relative}"
            )

        digest = sha256_file(path)

        if digest != expected:
            raise MonthlyOpsLadderError(
                f"frozen Stage 13 dependency changed: {relative}"
            )

        observed[relative] = digest

    return dict(
        sorted(observed.items())
    )


def verify_selector_decision(
    repo: Path,
) -> Mapping[str, object]:
    path = (
        repo
        / "validation"
        / "selector-v1"
        / "stage7-selector-decision-record.json"
    )

    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise MonthlyOpsLadderError(
            "selector decision record missing"
        )

    if (
        sha256_file(path)
        != EXPECTED_SELECTOR_DECISION_SHA256
    ):
        raise MonthlyOpsLadderError(
            "selector decision record SHA256 changed"
        )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if (
        payload.get("status")
        != "STAGE7_SELECTOR_DECISION_FINALIZED"
        or payload.get("decision")
        != "OPS"
    ):
        raise MonthlyOpsLadderError(
            "frozen production selector decision changed"
        )

    return payload


def _require_artifact(
    path: Path,
    expected_sha256: str,
    *,
    label: str,
) -> None:
    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise MonthlyOpsLadderError(
            f"{label} missing: {path}"
        )

    if sha256_file(path) != expected_sha256:
        raise MonthlyOpsLadderError(
            f"{label} SHA256 changed"
        )


def _load_json(
    path: Path,
    *,
    label: str,
) -> Mapping[str, object]:
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise MonthlyOpsLadderError(
            f"cannot parse {label}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise MonthlyOpsLadderError(
            f"{label} must be a JSON object"
        )

    return payload


def authenticate_stage11(
    stage1_root: Path,
) -> Stage11Authority:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    stage = (
        stage1
        / STAGE11_STAGE_NAME
    )

    matrix_path = (
        stage
        / STAGE11_MATRIX_NAME
    )

    record_path = (
        stage
        / STAGE11_RECORD_NAME
    )

    completion_path = (
        stage1
        / STAGE11_COMPLETION_NAME
    )

    _require_artifact(
        matrix_path,
        EXPECTED_STAGE11_MATRIX_SHA256,
        label="Stage 11 matrix",
    )

    _require_artifact(
        record_path,
        EXPECTED_STAGE11_RECORD_SHA256,
        label="Stage 11 record",
    )

    _require_artifact(
        completion_path,
        EXPECTED_STAGE11_COMPLETION_SHA256,
        label="Stage 11 completion",
    )

    record = _load_json(
        record_path,
        label="Stage 11 record",
    )

    completion = _load_json(
        completion_path,
        label="Stage 11 completion",
    )

    expected = {
        "status":
            "MONTHLY_SPECIES_BALANCED_PERCENTILE_GEOMETRY_COMPLETE",
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "execution_commit":
            EXPECTED_STAGE11_EXECUTION_COMMIT,
        "percentile_matrix_sha256":
            EXPECTED_STAGE11_MATRIX_SHA256,
        "membership_sha256":
            EXPECTED_STAGE11_MEMBERSHIP_SHA256,
        "species_mapping_sha256":
            EXPECTED_STAGE11_SPECIES_MAPPING_SHA256,
        "percentile_numeric_array_sha256":
            EXPECTED_STAGE11_PERCENTILE_ARRAY_SHA256,
        "total_count":
            EXPECTED_TOTAL_COUNT,
        "species_count":
            EXPECTED_SPECIES_COUNT,
        "feature_count":
            EXPECTED_FEATURE_COUNT,
    }

    for key, value in expected.items():
        if record.get(key) != value:
            raise MonthlyOpsLadderError(
                f"Stage 11 record {key} mismatch"
            )

        if completion.get(key) != value:
            raise MonthlyOpsLadderError(
                f"Stage 11 completion {key} mismatch"
            )

    (
        accessions,
        species_ids,
        coordinates,
    ) = (
        monthly_geometry
        .parse_monthly_geometry_matrix(
            matrix_path.read_bytes()
        )
    )

    if len(accessions) != EXPECTED_TOTAL_COUNT:
        raise MonthlyOpsLadderError(
            "Stage 11 row count changed"
        )

    if coordinates.shape != (
        EXPECTED_TOTAL_COUNT,
        EXPECTED_FEATURE_COUNT,
    ):
        raise MonthlyOpsLadderError(
            "Stage 11 coordinate shape changed"
        )

    if (
        accession_membership_sha256(
            accessions
        )
        != EXPECTED_STAGE11_MEMBERSHIP_SHA256
    ):
        raise MonthlyOpsLadderError(
            "Stage 11 membership changed"
        )

    if (
        monthly_geometry
        ._species_mapping_sha256(
            accessions,
            species_ids,
        )
        != EXPECTED_STAGE11_SPECIES_MAPPING_SHA256
    ):
        raise MonthlyOpsLadderError(
            "Stage 11 species mapping changed"
        )

    if (
        monthly_geometry
        ._numeric_array_sha256(
            coordinates
        )
        != EXPECTED_STAGE11_PERCENTILE_ARRAY_SHA256
    ):
        raise MonthlyOpsLadderError(
            "Stage 11 percentile array changed"
        )

    return Stage11Authority(
        accessions=accessions,
        species_ids=species_ids,
        coordinates=coordinates,
    )


def authenticate_stage12(
    stage1_root: Path,
) -> Stage12Authority:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    stage = (
        stage1
        / STAGE12_STAGE_NAME
    )

    table_path = (
        stage
        / STAGE12_TABLE_NAME
    )

    record_path = (
        stage
        / STAGE12_RECORD_NAME
    )

    completion_path = (
        stage1
        / STAGE12_COMPLETION_NAME
    )

    _require_artifact(
        table_path,
        EXPECTED_STAGE12_TABLE_SHA256,
        label="Stage 12 table",
    )

    _require_artifact(
        record_path,
        EXPECTED_STAGE12_RECORD_SHA256,
        label="Stage 12 record",
    )

    _require_artifact(
        completion_path,
        EXPECTED_STAGE12_COMPLETION_SHA256,
        label="Stage 12 completion",
    )

    record = _load_json(
        record_path,
        label="Stage 12 record",
    )

    completion = _load_json(
        completion_path,
        label="Stage 12 completion",
    )

    expected = {
        "status":
            "MONTHLY_SPECIES_REPRESENTATIVES_COMPLETE",
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "execution_commit":
            EXPECTED_STAGE12_EXECUTION_COMMIT,
        "representative_count":
            EXPECTED_REPRESENTATIVE_COUNT,
        "species_count":
            EXPECTED_SPECIES_COUNT,
        "representative_sequence_sha256":
            EXPECTED_REPRESENTATIVE_SEQUENCE_SHA256,
        "representative_membership_sha256":
            EXPECTED_REPRESENTATIVE_MEMBERSHIP_SHA256,
        "representative_table_sha256":
            EXPECTED_STAGE12_TABLE_SHA256,
    }

    for key, value in expected.items():
        if record.get(key) != value:
            raise MonthlyOpsLadderError(
                f"Stage 12 record {key} mismatch"
            )

        if completion.get(key) != value:
            raise MonthlyOpsLadderError(
                f"Stage 12 completion {key} mismatch"
            )

    text = table_path.read_text(
        encoding="ascii"
    )

    lines = text.splitlines()

    if not lines:
        raise MonthlyOpsLadderError(
            "Stage 12 table is empty"
        )

    if tuple(
        lines[0].split("\t")
    ) != (
        "species_taxid",
        "canonical_genbank_assembly_accession",
    ):
        raise MonthlyOpsLadderError(
            "Stage 12 table header changed"
        )

    species_ids: list[str] = []
    accessions: list[str] = []

    for line in lines[1:]:
        fields = line.split("\t")

        if len(fields) != 2:
            raise MonthlyOpsLadderError(
                "Stage 12 table row width changed"
            )

        species_taxid, accession = fields

        if _TAXID_RE.fullmatch(
            species_taxid
        ) is None:
            raise MonthlyOpsLadderError(
                "Stage 12 malformed species TaxID"
            )

        if _GCA_RE.fullmatch(
            accession
        ) is None:
            raise MonthlyOpsLadderError(
                "Stage 12 malformed accession"
            )

        species_ids.append(
            species_taxid
        )

        accessions.append(
            accession
        )

    if len(accessions) != EXPECTED_REPRESENTATIVE_COUNT:
        raise MonthlyOpsLadderError(
            "Stage 12 representative count changed"
        )

    if len(set(accessions)) != EXPECTED_REPRESENTATIVE_COUNT:
        raise MonthlyOpsLadderError(
            "Stage 12 contains duplicate representatives"
        )

    if len(set(species_ids)) != EXPECTED_SPECIES_COUNT:
        raise MonthlyOpsLadderError(
            "Stage 12 species count changed"
        )

    if (
        accession_membership_sha256(
            accessions
        )
        != EXPECTED_REPRESENTATIVE_MEMBERSHIP_SHA256
    ):
        raise MonthlyOpsLadderError(
            "Stage 12 representative membership changed"
        )

    sequence = sequence_sha256(
        "BacSelect-selector-v1|OPS|representatives",
        accessions,
    )

    if (
        sequence
        != EXPECTED_REPRESENTATIVE_SEQUENCE_SHA256
    ):
        raise MonthlyOpsLadderError(
            "Stage 12 representative sequence changed"
        )

    return Stage12Authority(
        species_ids=tuple(species_ids),
        accessions=tuple(accessions),
    )


def build_complete_ops_ladder(
    stage11: Stage11Authority,
    stage12: Stage12Authority,
) -> OpsLadderBuild:
    index_by_accession = {
        accession: index
        for index, accession
        in enumerate(
            stage11.accessions
        )
    }

    representative_indices: list[int] = []

    for species_taxid, accession in zip(
        stage12.species_ids,
        stage12.accessions,
        strict=True,
    ):
        try:
            index = index_by_accession[
                accession
            ]
        except KeyError as exc:
            raise MonthlyOpsLadderError(
                "Stage 12 representative absent from Stage 11"
            ) from exc

        if (
            stage11.species_ids[
                index
            ]
            != species_taxid
        ):
            raise MonthlyOpsLadderError(
                "Stage 12 representative species differs from Stage 11"
            )

        representative_indices.append(
            index
        )

    representative_coordinates = (
        stage11.coordinates[
            np.asarray(
                representative_indices,
                dtype=np.int64,
            )
        ]
    )

    representative_species = (
        stage12.species_ids
    )

    representative_accessions = (
        stage12.accessions
    )

    ladder_local = ops_ladder(
        representative_coordinates,
        representative_species,
        representative_accessions,
        max_n=(
            EXPECTED_REPRESENTATIVE_COUNT
        ),
    )

    if ladder_local.shape != (
        EXPECTED_REPRESENTATIVE_COUNT,
    ):
        raise MonthlyOpsLadderError(
            "complete OPS ladder length changed"
        )

    if (
        np.unique(
            ladder_local
        ).size
        != EXPECTED_REPRESENTATIVE_COUNT
    ):
        raise MonthlyOpsLadderError(
            "complete OPS ladder contains duplicate indices"
        )

    ladder_accessions = tuple(
        representative_accessions[
            int(index)
        ]
        for index in ladder_local
    )

    ladder_species = tuple(
        representative_species[
            int(index)
        ]
        for index in ladder_local
    )

    if set(
        ladder_accessions
    ) != set(
        representative_accessions
    ):
        raise MonthlyOpsLadderError(
            "complete OPS ladder does not rank every representative exactly once"
        )

    if len(
        set(
            ladder_species
        )
    ) != EXPECTED_SPECIES_COUNT:
        raise MonthlyOpsLadderError(
            "complete OPS ladder does not rank every species exactly once"
        )

    rows = tuple(
        OpsLadderRow(
            rank=rank,
            species_taxid=species_taxid,
            accession=accession,
        )
        for rank, (
            species_taxid,
            accession,
        )
        in enumerate(
            zip(
                ladder_species,
                ladder_accessions,
                strict=True,
            ),
            start=1,
        )
    )

    complete_hash = sequence_sha256(
        ladder_namespace(
            EXPECTED_REPRESENTATIVE_COUNT
        ),
        ladder_accessions,
    )

    membership_hash = (
        accession_membership_sha256(
            ladder_accessions
        )
    )

    stage12_membership_hash = (
        accession_membership_sha256(
            representative_accessions
        )
    )

    if (
        membership_hash
        != stage12_membership_hash
    ):
        raise MonthlyOpsLadderError(
            "complete OPS ladder membership differs from authenticated Stage 12"
        )

    n500_hash = sequence_sha256(
        ladder_namespace(500),
        ladder_accessions[:500],
    )

    return OpsLadderBuild(
        rows=rows,
        complete_ladder_sha256=(
            complete_hash
        ),
        ladder_membership_sha256=(
            membership_hash
        ),
        n500_prefix_sha256=(
            n500_hash
        ),
    )


def serialize_ladder_table(
    build: OpsLadderBuild,
) -> bytes:
    output = [
        "\t".join(
            TABLE_FIELDS
        )
        + "\n"
    ]

    for row in build.rows:
        output.append(
            "\t".join(
                (
                    str(row.rank),
                    row.species_taxid,
                    row.accession,
                )
            )
            + "\n"
        )

    return "".join(
        output
    ).encode("ascii")


def parse_ladder_table(
    payload: bytes,
) -> tuple[
    tuple[int, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    try:
        text = payload.decode(
            "ascii"
        )
    except UnicodeDecodeError as exc:
        raise MonthlyOpsLadderError(
            "OPS ladder table is not ASCII"
        ) from exc

    lines = text.splitlines()

    if not lines:
        raise MonthlyOpsLadderError(
            "OPS ladder table is empty"
        )

    if tuple(
        lines[0].split("\t")
    ) != TABLE_FIELDS:
        raise MonthlyOpsLadderError(
            "OPS ladder table header changed"
        )

    ranks: list[int] = []
    species_ids: list[str] = []
    accessions: list[str] = []

    for line in lines[1:]:
        fields = line.split("\t")

        if len(fields) != 3:
            raise MonthlyOpsLadderError(
                "OPS ladder table row width changed"
            )

        rank_text, species_taxid, accession = fields

        try:
            rank = int(
                rank_text
            )
        except ValueError as exc:
            raise MonthlyOpsLadderError(
                "OPS ladder rank is not an integer"
            ) from exc

        if _TAXID_RE.fullmatch(
            species_taxid
        ) is None:
            raise MonthlyOpsLadderError(
                "OPS ladder malformed species TaxID"
            )

        if _GCA_RE.fullmatch(
            accession
        ) is None:
            raise MonthlyOpsLadderError(
                "OPS ladder malformed accession"
            )

        ranks.append(rank)
        species_ids.append(
            species_taxid
        )
        accessions.append(
            accession
        )

    expected_ranks = tuple(
        range(
            1,
            len(ranks) + 1,
        )
    )

    if tuple(ranks) != expected_ranks:
        raise MonthlyOpsLadderError(
            "OPS ladder ranks are not contiguous from 1"
        )

    if len(
        set(
            species_ids
        )
    ) != len(
        species_ids
    ):
        raise MonthlyOpsLadderError(
            "OPS ladder contains duplicate species"
        )

    if len(
        set(
            accessions
        )
    ) != len(
        accessions
    ):
        raise MonthlyOpsLadderError(
            "OPS ladder contains duplicate accessions"
        )

    return (
        tuple(ranks),
        tuple(species_ids),
        tuple(accessions),
    )


def _validate_roundtrip(
    build: OpsLadderBuild,
    payload: bytes,
) -> None:
    (
        ranks,
        species_ids,
        accessions,
    ) = parse_ladder_table(
        payload
    )

    if ranks != tuple(
        row.rank
        for row in build.rows
    ):
        raise MonthlyOpsLadderError(
            "written OPS ladder rank order changed"
        )

    if species_ids != tuple(
        row.species_taxid
        for row in build.rows
    ):
        raise MonthlyOpsLadderError(
            "written OPS ladder species order changed"
        )

    if accessions != tuple(
        row.accession
        for row in build.rows
    ):
        raise MonthlyOpsLadderError(
            "written OPS ladder accession order changed"
        )

    if (
        sequence_sha256(
            ladder_namespace(
                len(accessions)
            ),
            accessions,
        )
        != build.complete_ladder_sha256
    ):
        raise MonthlyOpsLadderError(
            "written complete OPS ladder identity changed"
        )

    if (
        sequence_sha256(
            ladder_namespace(500),
            accessions[:500],
        )
        != build.n500_prefix_sha256
    ):
        raise MonthlyOpsLadderError(
            "written N=500 prefix identity changed"
        )


def build_execution_record(
    *,
    execution_commit: str,
    stage12: Stage12Authority,
    build: OpsLadderBuild,
    table_sha256: str,
) -> bytes:
    _require_sha(
        table_sha256,
        label="Stage 13 ladder table SHA256",
    )

    payload = {
        "schema_version":
            RECORD_SCHEMA,
        "status":
            STATUS,
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "execution_commit":
            execution_commit,
        "selector":
            SELECTOR,
        "selector_version":
            SELECTOR_VERSION,
        "selector_decision_record_sha256":
            EXPECTED_SELECTOR_DECISION_SHA256,
        "ops_sha256":
            EXPECTED_OPS_SHA256,
        "tie_sha256":
            EXPECTED_TIE_SHA256,
        "stage11_matrix_sha256":
            EXPECTED_STAGE11_MATRIX_SHA256,
        "stage11_record_sha256":
            EXPECTED_STAGE11_RECORD_SHA256,
        "stage11_completion_sha256":
            EXPECTED_STAGE11_COMPLETION_SHA256,
        "stage11_percentile_numeric_array_sha256":
            EXPECTED_STAGE11_PERCENTILE_ARRAY_SHA256,
        "stage12_table_sha256":
            EXPECTED_STAGE12_TABLE_SHA256,
        "stage12_record_sha256":
            EXPECTED_STAGE12_RECORD_SHA256,
        "stage12_completion_sha256":
            EXPECTED_STAGE12_COMPLETION_SHA256,
        "stage12_representative_sequence_sha256":
            EXPECTED_REPRESENTATIVE_SEQUENCE_SHA256,
        "stage12_representative_membership_sha256":
            EXPECTED_REPRESENTATIVE_MEMBERSHIP_SHA256,
        "representative_count":
            len(stage12.accessions),
        "ladder_count":
            len(build.rows),
        "complete_ladder_sha256":
            build.complete_ladder_sha256,
        "ladder_membership_sha256":
            build.ladder_membership_sha256,
        "n500_prefix_sha256":
            build.n500_prefix_sha256,
        "ladder_table_sha256":
            table_sha256,
        "ranking_limited_to_500":
            False,
        "all_species_representatives_ranked":
            True,
        "sr_executed":
            False,
        "ag_executed":
            False,
        "selector_resolution_rerun":
            False,
        "panels_generated":
            False,
        "coverage_generated":
            False,
    }

    return _canonical_json(
        payload
    )


def build_completion_receipt(
    *,
    execution_commit: str,
    build: OpsLadderBuild,
    table_sha256: str,
    record_sha256: str,
) -> bytes:
    _require_sha(
        table_sha256,
        label="Stage 13 ladder table SHA256",
    )

    _require_sha(
        record_sha256,
        label="Stage 13 record SHA256",
    )

    payload = {
        "schema_version":
            COMPLETION_SCHEMA,
        "status":
            STATUS,
        "release_id":
            RELEASE_ID,
        "source_snapshot_id":
            SOURCE_SNAPSHOT_ID,
        "execution_commit":
            execution_commit,
        "representative_count":
            EXPECTED_REPRESENTATIVE_COUNT,
        "ladder_count":
            len(build.rows),
        "complete_ladder_sha256":
            build.complete_ladder_sha256,
        "ladder_membership_sha256":
            build.ladder_membership_sha256,
        "n500_prefix_sha256":
            build.n500_prefix_sha256,
        "ladder_table_sha256":
            table_sha256,
        "record_sha256":
            record_sha256,
    }

    return _canonical_json(
        payload
    )


def _fsync_directory(
    path: Path,
) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY,
    )

    try:
        os.fsync(
            descriptor
        )
    finally:
        os.close(
            descriptor
        )


def _write_fresh(
    path: Path,
    payload: bytes,
) -> None:
    if os.path.lexists(path):
        raise MonthlyOpsLadderError(
            f"refusing to overwrite existing artifact: {path}"
        )

    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def publish_stage(
    *,
    stage1_root: Path,
    table_payload: bytes,
    record_payload: bytes,
    stability_check: Callable[[], None],
) -> Path:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    final = (
        stage1
        / STAGE_NAME
    )

    partial = (
        stage1
        / PARTIAL_NAME
    )

    if os.path.lexists(final):
        raise MonthlyOpsLadderError(
            "canonical Stage 13 directory already exists"
        )

    if os.path.lexists(partial):
        raise MonthlyOpsLadderError(
            "partial Stage 13 directory already exists"
        )

    partial.mkdir()

    _write_fresh(
        partial
        / TABLE_NAME,
        table_payload,
    )

    _write_fresh(
        partial
        / RECORD_NAME,
        record_payload,
    )

    if {
        path.name
        for path in partial.iterdir()
    } != STAGE_FILES:
        raise MonthlyOpsLadderError(
            "partial Stage 13 artifact inventory changed"
        )

    stability_check()

    _fsync_directory(
        partial
    )

    os.rename(
        partial,
        final,
    )

    _fsync_directory(
        stage1
    )

    return final


def publish_completion(
    *,
    stage1_root: Path,
    payload: bytes,
    stability_check: Callable[[], None],
) -> Path:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    final = (
        stage1
        / COMPLETION_NAME
    )

    temporary = (
        stage1
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(final):
        raise MonthlyOpsLadderError(
            "Stage 13 completion already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlyOpsLadderError(
            "Stage 13 completion temporary artifact already exists"
        )

    _write_fresh(
        temporary,
        payload,
    )

    stability_check()

    os.rename(
        temporary,
        final,
    )

    _fsync_directory(
        stage1
    )

    return final


def execute_monthly_ops_ladder(
    *,
    repo: Path,
    stage1_root: Path,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    stability_check: Callable[[], None] | None = None,
) -> MonthlyOpsLadderExecutionResult:
    root = repository_preflight(
        repo,
        execution_commit=execution_commit,
    )

    verify_frozen_dependencies(
        root
    )

    verify_selector_decision(
        root
    )

    if release_id != RELEASE_ID:
        raise MonthlyOpsLadderError(
            "unexpected monthly release ID"
        )

    if (
        source_snapshot_id
        != SOURCE_SNAPSHOT_ID
    ):
        raise MonthlyOpsLadderError(
            "unexpected monthly source snapshot"
        )

    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    for path in (
        stage1 / STAGE_NAME,
        stage1 / PARTIAL_NAME,
        stage1 / COMPLETION_NAME,
        stage1 / COMPLETION_TEMP_NAME,
    ):
        if os.path.lexists(path):
            raise MonthlyOpsLadderError(
                f"Stage 13 output already exists: {path}"
            )

    stage11 = authenticate_stage11(
        stage1
    )

    stage12 = authenticate_stage12(
        stage1
    )

    build = build_complete_ops_ladder(
        stage11,
        stage12,
    )

    table_payload = (
        serialize_ladder_table(
            build
        )
    )

    _validate_roundtrip(
        build,
        table_payload,
    )

    table_sha = hashlib.sha256(
        table_payload
    ).hexdigest()

    record_payload = (
        build_execution_record(
            execution_commit=(
                execution_commit
            ),
            stage12=stage12,
            build=build,
            table_sha256=(
                table_sha
            ),
        )
    )

    record_sha = hashlib.sha256(
        record_payload
    ).hexdigest()

    completion_payload = (
        build_completion_receipt(
            execution_commit=(
                execution_commit
            ),
            build=build,
            table_sha256=(
                table_sha
            ),
            record_sha256=(
                record_sha
            ),
        )
    )

    completion_sha = hashlib.sha256(
        completion_payload
    ).hexdigest()

    check = (
        stability_check
        if stability_check is not None
        else lambda: None
    )

    stage_path = publish_stage(
        stage1_root=stage1,
        table_payload=table_payload,
        record_payload=record_payload,
        stability_check=check,
    )

    completion_path = (
        publish_completion(
            stage1_root=stage1,
            payload=completion_payload,
            stability_check=check,
        )
    )

    return MonthlyOpsLadderExecutionResult(
        stage_path=stage_path,
        completion_path=completion_path,
        table_sha256=table_sha,
        record_sha256=record_sha,
        completion_sha256=completion_sha,
        complete_ladder_sha256=(
            build.complete_ladder_sha256
        ),
        ladder_membership_sha256=(
            build.ladder_membership_sha256
        ),
        n500_prefix_sha256=(
            build.n500_prefix_sha256
        ),
        ladder_count=len(
            build.rows
        ),
    )
