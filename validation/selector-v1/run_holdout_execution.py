#!/usr/bin/env python3
"""Execute frozen BacSelect Stage 5B external-holdout composition.

Stage 5B consumes the already-finalized Stage 5A complete eligible universe,
reconstructs the historically frozen metadata-retained membership relative to
the authoritative baseline, intersects that absence membership with the
immutable Stage 5A universe, and evaluates the frozen adequacy gate.

Physical SHA256 verification of all production identity-bearing inputs occurs
before the Stage 5B predecision checkpoint. No candidate row from the Stage 5A
universe, frozen raw metadata snapshot, or baseline matrix is parsed until the
predecision artifact exists on disk.

Stage 5B does not calculate structural features, OPS/SR distances, selector
scores, or panel membership.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable, Mapping, Sequence

from bacselect import source_eligibility
from bacselect import source_holdout
from bacselect import source_membership
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


STAGE5_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-stage5-complete-universe-baseline-intersection.md"
)

STAGE5A_COMPLETION_RELATIVE = Path(
    "validation/selector-v1/"
    "stage5a-complete-universe-completion-evidence.json"
)

STAGE5B_HELPER_RELATIVE = Path(
    "src/bacselect/source_holdout.py"
)

STAGE5B_HELPER_TEST_RELATIVE = Path(
    "tests/test_source_holdout.py"
)

SOURCE_ELIGIBILITY_RELATIVE = Path(
    "src/bacselect/source_eligibility.py"
)

SOURCE_MEMBERSHIP_RELATIVE = Path(
    "src/bacselect/source_membership.py"
)

SOURCE_TRUTH_EXECUTION_RELATIVE = Path(
    "src/bacselect/source_truth_execution.py"
)

STAGE5B_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/run_holdout_execution.py"
)

STAGE5B_WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_holdout_execution.py"
)

HISTORICAL_METADATA_RUN_RELATIVE = Path(
    "validation/selector-v1/results/"
    "external-holdout-metadata-eligibility-run.tsv"
)

HISTORICAL_METADATA_FREEZE_RELATIVE = Path(
    "validation/selector-v1/results/"
    "external-holdout-metadata-eligibility-freeze.tsv"
)

HISTORICAL_METADATA_SUMMARY_RELATIVE = Path(
    "validation/selector-v1/results/"
    "external-holdout-metadata-eligibility-summary.json"
)

HISTORICAL_METADATA_FILES_RELATIVE = Path(
    "validation/selector-v1/results/"
    "external-holdout-metadata-eligibility-files.sha256"
)

HISTORICAL_MEMBERSHIP_RUN_RELATIVE = Path(
    "validation/selector-v1/results/"
    "external-holdout-baseline-membership-run.tsv"
)

HISTORICAL_MEMBERSHIP_FREEZE_RELATIVE = Path(
    "validation/selector-v1/results/"
    "external-holdout-baseline-membership-freeze.tsv"
)

HISTORICAL_MEMBERSHIP_SUMMARY_RELATIVE = Path(
    "validation/selector-v1/results/"
    "external-holdout-baseline-membership-summary.json"
)

HISTORICAL_MEMBERSHIP_FILES_RELATIVE = Path(
    "validation/selector-v1/results/"
    "external-holdout-baseline-membership-files.sha256"
)


EXPECTED_STAGE5_METHOD_SHA256 = (
    "a1741531205778b6db2c97554d598216"
    "ff3396359b77ba431444e1f96f014718"
)

EXPECTED_STAGE5A_COMPLETION_SHA256 = (
    "cae7153614256a134b1f63dc200ee336"
    "15ae3b27351a0c6fd659eafde2db06d5"
)

EXPECTED_STAGE5B_HELPER_SHA256 = (
    "9509fba9af898c1475ff40a83ccd31e0"
    "2dc2da3819f36bd3481336e3ac81b2bf"
)

EXPECTED_STAGE5B_HELPER_TEST_SHA256 = (
    "e2c7df70479992ec4c17c70c908af552"
    "3681f87843e6796f49072878c606fa0a"
)

EXPECTED_SOURCE_ELIGIBILITY_SHA256 = (
    "6e57dd950f972a9883e8fcbc78a18c69"
    "4a5fabda58b03835f268eef681a03cc2"
)

EXPECTED_SOURCE_MEMBERSHIP_SHA256 = (
    "ffd4bb04f913df3d658b591739f3ad87"
    "6c24d9a8d795242c926c97987dffce4e"
)

EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256 = (
    "83b8ec7fce774c0b68cb2af982aef139"
    "04c6b64b3ee695512c578f98e5de9b92"
)

EXPECTED_HISTORICAL_METADATA_RUN_SHA256 = (
    "e8bd35f491299ab716c9c61654705581"
    "8d718bcf9bdcaa1ac34d4207b3b4b1c6"
)

EXPECTED_HISTORICAL_METADATA_FREEZE_SHA256 = (
    "0113b2ba31a1c1af82d302c7ffec81e4"
    "0100a6b2bc7be751ebef2cef951b9bbe"
)

EXPECTED_HISTORICAL_METADATA_SUMMARY_SHA256 = (
    "108b631e1ce0c6344b4c39b6249f59ba"
    "05c8e922078548b7a9624703bd082adf"
)

EXPECTED_HISTORICAL_METADATA_FILES_SHA256 = (
    "2992971075d508df9964f0def91c2bc2"
    "d6ac756e10c53db60f0c7d3f8a52eb4c"
)

EXPECTED_HISTORICAL_MEMBERSHIP_RUN_SHA256 = (
    "6b96daf2b3d22f130492e5054d576956"
    "93d946ee847f6a51fadb6e1c3d7a99ba"
)

EXPECTED_HISTORICAL_MEMBERSHIP_FREEZE_SHA256 = (
    "9e719301f3adcec92d6d019ce6cdc1d8"
    "30507f651ff4b99ba965c4655e43a767"
)

EXPECTED_HISTORICAL_MEMBERSHIP_SUMMARY_SHA256 = (
    "4f0440fc4231e511033e06c82b2b5e44"
    "4aae5bfb189b487632ef58dab23aaedb"
)

EXPECTED_HISTORICAL_MEMBERSHIP_FILES_SHA256 = (
    "d5fd5aa445d2f26f49c747ed4e6e3ac"
    "741f477922b2779539a595f6853bfac9d"
)

EXPECTED_RAW_SOURCE_SHA256 = (
    "b1b016891ae4e976d03606dfb2f35f74"
    "b03d21cf3ec82832f77f4d113bd622d5"
)

EXPECTED_BASELINE_MATRIX_SHA256 = (
    "86c0c3d49317dfc3cc452114e3863666"
    "fe2112b6a3ae8dae2090b60a2a598948"
)

EXPECTED_STAGE5A_CONTENT_MANIFEST_SHA256 = (
    "2080bd396cf030c0d38f3742db2d832c"
    "b0dd4518ebe647d0480e161c0a052246"
)

EXPECTED_STAGE5A_EXECUTION_PROVENANCE_SHA256 = (
    "92b7cef6cee0032a7eb7d73ab282bea1"
    "77d6bac3fdb8e887bb6607f5dbce1ca8"
)

EXPECTED_COMPLETE_UNIVERSE_ARTIFACT_SHA256 = (
    "96118ff6556f5cdc69c1cf912a3daab5"
    "b58fa97a39a7cee96326b8819ea098e4"
)

EXPECTED_COMPLETE_UNIVERSE_MEMBERSHIP_SHA256 = (
    "53cf615ab9d89a3457574f340f31c605"
    "76a88360608b74c419728be8e82d578a"
)


COMPLETE_UNIVERSE_FIELDS = (
    "canonical_genbank_assembly_accession",
    "species_taxid",
)

INPUT_EVIDENCE_FIELDS = (
    "label",
    "path",
    "size_bytes",
    "sha256",
)

CONTENT_MANIFEST_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
)

LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

LOWER_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)


class Stage5BWrapperError(RuntimeError):
    """Fail-closed Stage 5B execution error."""


@dataclass(frozen=True)
class Stage5AExpectations:
    complete_universe_count: int
    complete_universe_species_count: int
    complete_universe_membership_sha256: str


@dataclass(frozen=True)
class HistoricalExpectations:
    raw_records: int
    metadata_retained: int
    metadata_excluded: int
    metadata_unresolved: int
    baseline_accessions: int
    retained_present_in_baseline: int
    retained_absent_from_baseline: int
    baseline_not_in_metadata_retained: int

    def membership_summary(
        self,
    ) -> source_membership.MembershipSummary:
        return source_membership.MembershipSummary(
            baseline_accessions=self.baseline_accessions,
            metadata_retained=self.metadata_retained,
            retained_present_in_baseline=(
                self.retained_present_in_baseline
            ),
            retained_absent_from_baseline=(
                self.retained_absent_from_baseline
            ),
            baseline_not_in_metadata_retained=(
                self.baseline_not_in_metadata_retained
            ),
        )


@dataclass(frozen=True)
class InputPaths:
    stage5a_execution_dir: Path
    raw_source: Path
    baseline_matrix: Path

    @property
    def complete_universe(
        self,
    ) -> Path:
        return (
            self.stage5a_execution_dir
            / "complete-eligible-fresh-universe.tsv"
        )

    @property
    def stage5a_content_manifest(
        self,
    ) -> Path:
        return (
            self.stage5a_execution_dir
            / "stage5a-content-manifest.tsv"
        )

    @property
    def stage5a_execution_provenance(
        self,
    ) -> Path:
        return (
            self.stage5a_execution_dir
            / "stage5a-execution-provenance.json"
        )


@dataclass(frozen=True)
class InputIdentities:
    complete_universe: str
    stage5a_content_manifest: str
    stage5a_execution_provenance: str
    raw_source: str
    baseline_matrix: str


PRODUCTION_STAGE5A_EXPECTATIONS = Stage5AExpectations(
    complete_universe_count=67_957,
    complete_universe_species_count=16_144,
    complete_universe_membership_sha256=(
        EXPECTED_COMPLETE_UNIVERSE_MEMBERSHIP_SHA256
    ),
)

PRODUCTION_HISTORICAL_EXPECTATIONS = HistoricalExpectations(
    raw_records=70_850,
    metadata_retained=70_477,
    metadata_excluded=373,
    metadata_unresolved=0,
    baseline_accessions=55_306,
    retained_present_in_baseline=55_032,
    retained_absent_from_baseline=15_445,
    baseline_not_in_metadata_retained=274,
)

PRODUCTION_INPUT_IDENTITIES = InputIdentities(
    complete_universe=(
        EXPECTED_COMPLETE_UNIVERSE_ARTIFACT_SHA256
    ),
    stage5a_content_manifest=(
        EXPECTED_STAGE5A_CONTENT_MANIFEST_SHA256
    ),
    stage5a_execution_provenance=(
        EXPECTED_STAGE5A_EXECUTION_PROVENANCE_SHA256
    ),
    raw_source=EXPECTED_RAW_SOURCE_SHA256,
    baseline_matrix=EXPECTED_BASELINE_MATRIX_SHA256,
)

FROZEN_REPO_FILES = {
    STAGE5_METHOD_RELATIVE:
        EXPECTED_STAGE5_METHOD_SHA256,
    STAGE5A_COMPLETION_RELATIVE:
        EXPECTED_STAGE5A_COMPLETION_SHA256,
    STAGE5B_HELPER_RELATIVE:
        EXPECTED_STAGE5B_HELPER_SHA256,
    STAGE5B_HELPER_TEST_RELATIVE:
        EXPECTED_STAGE5B_HELPER_TEST_SHA256,
    SOURCE_ELIGIBILITY_RELATIVE:
        EXPECTED_SOURCE_ELIGIBILITY_SHA256,
    SOURCE_MEMBERSHIP_RELATIVE:
        EXPECTED_SOURCE_MEMBERSHIP_SHA256,
    SOURCE_TRUTH_EXECUTION_RELATIVE:
        EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256,
    HISTORICAL_METADATA_RUN_RELATIVE:
        EXPECTED_HISTORICAL_METADATA_RUN_SHA256,
    HISTORICAL_METADATA_FREEZE_RELATIVE:
        EXPECTED_HISTORICAL_METADATA_FREEZE_SHA256,
    HISTORICAL_METADATA_SUMMARY_RELATIVE:
        EXPECTED_HISTORICAL_METADATA_SUMMARY_SHA256,
    HISTORICAL_METADATA_FILES_RELATIVE:
        EXPECTED_HISTORICAL_METADATA_FILES_SHA256,
    HISTORICAL_MEMBERSHIP_RUN_RELATIVE:
        EXPECTED_HISTORICAL_MEMBERSHIP_RUN_SHA256,
    HISTORICAL_MEMBERSHIP_FREEZE_RELATIVE:
        EXPECTED_HISTORICAL_MEMBERSHIP_FREEZE_SHA256,
    HISTORICAL_MEMBERSHIP_SUMMARY_RELATIVE:
        EXPECTED_HISTORICAL_MEMBERSHIP_SUMMARY_SHA256,
    HISTORICAL_MEMBERSHIP_FILES_RELATIVE:
        EXPECTED_HISTORICAL_MEMBERSHIP_FILES_SHA256,
}


def sha256_file(
    path: Path | str,
) -> str:
    digest = hashlib.sha256()

    with Path(path).open(
        "rb"
    ) as handle:
        for block in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                block
            )

    return digest.hexdigest()


def require_sha256(
    path: Path | str,
    expected_sha256: str,
    label: str,
) -> None:
    source = Path(
        path
    )

    if (
        not source.is_file()
        or source.is_symlink()
    ):
        raise Stage5BWrapperError(
            f"{label} is not a regular non-symlink file"
        )

    observed = sha256_file(
        source
    )

    if observed != expected_sha256:
        raise Stage5BWrapperError(
            f"{label} SHA256 mismatch"
        )


def _validate_sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or LOWER_SHA256_RE.fullmatch(
            value
        ) is None
    ):
        raise Stage5BWrapperError(
            f"{label} malformed"
        )

    return value


def write_json_atomic(
    path: Path,
    payload: Mapping[str, object],
) -> str:
    temporary = path.with_name(
        "." + path.name + ".tmp"
    )

    if temporary.exists():
        raise Stage5BWrapperError(
            "temporary JSON path already exists"
        )

    text = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    temporary.write_text(
        text,
        encoding="utf-8",
    )

    os.replace(
        temporary,
        path,
    )

    return sha256_file(
        path
    )


def write_tsv_atomic(
    path: Path,
    fields: Sequence[str],
    rows: Iterable[Mapping[str, object]],
) -> str:
    temporary = path.with_name(
        "." + path.name + ".tmp"
    )

    if temporary.exists():
        raise Stage5BWrapperError(
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
                fieldnames=tuple(
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
                    raise Stage5BWrapperError(
                        "TSV output row schema mismatch"
                    )

                writer.writerow(
                    {
                        field:
                            row[field]
                        for field in fields
                    }
                )

    except Exception:
        if temporary.exists():
            temporary.unlink()

        raise

    os.replace(
        temporary,
        path,
    )

    return sha256_file(
        path
    )


def read_tsv_exact(
    path: Path,
    fields: Sequence[str],
    *,
    label: str,
) -> list[dict[str, str]]:
    try:
        with Path(path).open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            reader = csv.DictReader(
                handle,
                delimiter="\t",
            )

            if tuple(
                reader.fieldnames or ()
            ) != tuple(
                fields
            ):
                raise Stage5BWrapperError(
                    f"{label} schema mismatch"
                )

            rows = [
                dict(
                    row
                )
                for row in reader
            ]

    except Stage5BWrapperError:
        raise

    except (
        OSError,
        UnicodeError,
        csv.Error,
    ) as exc:
        raise Stage5BWrapperError(
            f"cannot parse {label}"
        ) from exc

    return rows


def _load_json_exact(
    path: Path,
    *,
    expected_sha256: str,
    label: str,
) -> Mapping[str, object]:
    require_sha256(
        path,
        expected_sha256,
        label,
    )

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise Stage5BWrapperError(
            f"cannot parse {label}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise Stage5BWrapperError(
            f"{label} must be a JSON object"
        )

    return payload


def load_tracked_stage5b_evidence(
    repo: Path,
) -> Mapping[str, object]:
    repo = Path(
        repo
    ).resolve()

    stage5a = _load_json_exact(
        repo
        / STAGE5A_COMPLETION_RELATIVE,
        expected_sha256=(
            EXPECTED_STAGE5A_COMPLETION_SHA256
        ),
        label="Stage 5A completion evidence",
    )

    if (
        stage5a.get(
            "schema_version"
        ) != 1
        or stage5a.get(
            "status"
        )
        != "STAGE5A_COMPLETE_UNIVERSE_COMPLETE"
        or stage5a.get(
            "complete_universe_count"
        )
        != 67_957
        or stage5a.get(
            "complete_universe_species_count"
        )
        != 16_144
        or stage5a.get(
            "complete_universe_membership_sha256"
        )
        != EXPECTED_COMPLETE_UNIVERSE_MEMBERSHIP_SHA256
    ):
        raise Stage5BWrapperError(
            "Stage 5A completion checkpoint mismatch"
        )

    artifacts = stage5a.get(
        "artifacts_sha256"
    )

    if (
        not isinstance(
            artifacts,
            Mapping,
        )
        or artifacts.get(
            "complete-eligible-fresh-universe.tsv"
        )
        != EXPECTED_COMPLETE_UNIVERSE_ARTIFACT_SHA256
        or artifacts.get(
            "stage5a-content-manifest.tsv"
        )
        != EXPECTED_STAGE5A_CONTENT_MANIFEST_SHA256
        or artifacts.get(
            "stage5a-execution-provenance.json"
        )
        != EXPECTED_STAGE5A_EXECUTION_PROVENANCE_SHA256
    ):
        raise Stage5BWrapperError(
            "Stage 5A scratch-artifact binding mismatch"
        )

    later = stage5a.get(
        "later_stage"
    )

    if later != {
        "baseline_membership_consulted":
            False,
        "complete_universe_generated":
            True,
        "historical_absence_membership_reconstructed":
            False,
        "holdout_membership_generated":
            False,
        "selector_outcomes_calculated":
            False,
        "structural_features_calculated":
            False,
    }:
        raise Stage5BWrapperError(
            "Stage 5A downstream-state mismatch"
        )

    metadata_summary = _load_json_exact(
        repo
        / HISTORICAL_METADATA_SUMMARY_RELATIVE,
        expected_sha256=(
            EXPECTED_HISTORICAL_METADATA_SUMMARY_SHA256
        ),
        label="historical metadata summary",
    )

    membership_summary = _load_json_exact(
        repo
        / HISTORICAL_MEMBERSHIP_SUMMARY_RELATIVE,
        expected_sha256=(
            EXPECTED_HISTORICAL_MEMBERSHIP_SUMMARY_SHA256
        ),
        label="historical membership summary",
    )

    if metadata_summary.get(
        "records"
    ) != 70_850:
        raise Stage5BWrapperError(
            "historical metadata record count mismatch"
        )

    if metadata_summary.get(
        "decision_counts"
    ) != {
        "EXCLUDE_METADATA":
            373,
        "RETAIN_METADATA":
            70_477,
    }:
        raise Stage5BWrapperError(
            "historical metadata accounting mismatch"
        )

    if membership_summary != {
        "baseline_accessions":
            55_306,
        "baseline_not_in_metadata_retained":
            274,
        "metadata_retained":
            70_477,
        "retained_absent_from_baseline":
            15_445,
        "retained_present_in_baseline":
            55_032,
    }:
        raise Stage5BWrapperError(
            "historical membership accounting mismatch"
        )

    return {
        "stage5a":
            stage5a,
        "metadata_summary":
            metadata_summary,
        "membership_summary":
            membership_summary,
    }


def preflight_repository(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> Mapping[str, str]:
    repo = Path(
        repo
    ).resolve()

    if LOWER_COMMIT_RE.fullmatch(
        expected_commit
    ) is None:
        raise Stage5BWrapperError(
            "expected Git commit malformed"
        )

    try:
        head = subprocess.check_output(
            [
                "git",
                "-C",
                str(
                    repo
                ),
                "rev-parse",
                "HEAD",
            ],
            text=True,
        ).strip()

        origin_main = subprocess.check_output(
            [
                "git",
                "-C",
                str(
                    repo
                ),
                "rev-parse",
                "origin/main",
            ],
            text=True,
        ).strip()

        status = subprocess.check_output(
            [
                "git",
                "-C",
                str(
                    repo
                ),
                "status",
                "--porcelain",
            ],
            text=True,
        )

    except subprocess.CalledProcessError as exc:
        raise Stage5BWrapperError(
            "cannot verify repository state"
        ) from exc

    if (
        head != expected_commit
        or origin_main != expected_commit
    ):
        raise Stage5BWrapperError(
            "repository commit boundary mismatch"
        )

    if status:
        raise Stage5BWrapperError(
            "repository is not clean"
        )

    frozen: dict[
        str,
        str
    ] = {}

    for relative, expected_sha in (
        FROZEN_REPO_FILES.items()
    ):
        require_sha256(
            repo
            / relative,
            expected_sha,
            f"frozen repository file {relative}",
        )

        frozen[
            relative.as_posix()
        ] = expected_sha

    require_sha256(
        repo
        / STAGE5B_WRAPPER_RELATIVE,
        expected_wrapper_sha256,
        "Stage 5B production wrapper",
    )

    require_sha256(
        repo
        / STAGE5B_WRAPPER_TEST_RELATIVE,
        expected_wrapper_test_sha256,
        "Stage 5B production-wrapper tests",
    )

    frozen[
        STAGE5B_WRAPPER_RELATIVE.as_posix()
    ] = expected_wrapper_sha256

    frozen[
        STAGE5B_WRAPPER_TEST_RELATIVE.as_posix()
    ] = expected_wrapper_test_sha256

    return dict(
        sorted(
            frozen.items()
        )
    )


def _ensure_output_root_outside_repo(
    output_root: Path,
    repo: Path,
) -> Path:
    root = Path(
        output_root
    ).resolve()

    repository = Path(
        repo
    ).resolve()

    if (
        root == repository
        or repository in root.parents
    ):
        raise Stage5BWrapperError(
            "Stage 5B output root must be outside repository"
        )

    return root


def _physical_preflight(
    paths: InputPaths,
    identities: InputIdentities,
) -> None:
    for label, path, identity in (
        (
            "Stage 5A complete universe",
            paths.complete_universe,
            identities.complete_universe,
        ),
        (
            "Stage 5A content manifest",
            paths.stage5a_content_manifest,
            identities.stage5a_content_manifest,
        ),
        (
            "Stage 5A execution provenance",
            paths.stage5a_execution_provenance,
            identities.stage5a_execution_provenance,
        ),
        (
            "frozen raw metadata source",
            paths.raw_source,
            identities.raw_source,
        ),
        (
            "authoritative baseline matrix",
            paths.baseline_matrix,
            identities.baseline_matrix,
        ),
    ):
        _validate_sha256(
            identity,
            label=f"{label} SHA256",
        )

        require_sha256(
            path,
            identity,
            label,
        )


def _load_complete_universe(
    path: Path,
    *,
    expectations: Stage5AExpectations,
) -> tuple[
    source_holdout.CompleteUniverseMember,
    ...,
]:
    rows = read_tsv_exact(
        path,
        COMPLETE_UNIVERSE_FIELDS,
        label="Stage 5A complete universe",
    )

    members: list[
        source_holdout.CompleteUniverseMember
    ] = []

    for row in rows:
        accession = row[
            "canonical_genbank_assembly_accession"
        ]

        try:
            species_taxid = int(
                row[
                    "species_taxid"
                ]
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise Stage5BWrapperError(
                "Stage 5A complete-universe species TaxID malformed"
            ) from exc

        members.append(
            source_holdout.CompleteUniverseMember(
                accession=accession,
                species_taxid=species_taxid,
            )
        )

    try:
        return source_holdout.validate_complete_universe(
            members,
            expected_count=(
                expectations.complete_universe_count
            ),
            expected_species_count=(
                expectations.complete_universe_species_count
            ),
            expected_membership_sha256=(
                expectations.complete_universe_membership_sha256
            ),
        )

    except source_holdout.HoldoutError as exc:
        raise Stage5BWrapperError(
            "Stage 5A complete-universe validation failed closed"
        ) from exc


def _load_metadata_retained(
    path: Path,
    *,
    expectations: HistoricalExpectations,
) -> frozenset[str]:
    try:
        assessments = source_eligibility.assess_records(
            source_eligibility.iter_jsonl_records(
                path
            )
        )
    except Exception as exc:
        raise Stage5BWrapperError(
            "historical raw metadata parsing failed closed"
        ) from exc

    decision_counts: dict[
        str,
        int
    ] = {}

    for assessment in assessments:
        decision_counts[
            assessment.decision
        ] = (
            decision_counts.get(
                assessment.decision,
                0,
            )
            + 1
        )

    if len(
        assessments
    ) != expectations.raw_records:
        raise Stage5BWrapperError(
            "historical raw metadata record count mismatch"
        )

    if decision_counts.get(
        source_eligibility.RETAIN,
        0,
    ) != expectations.metadata_retained:
        raise Stage5BWrapperError(
            "historical metadata-retained count mismatch"
        )

    if decision_counts.get(
        source_eligibility.EXCLUDE,
        0,
    ) != expectations.metadata_excluded:
        raise Stage5BWrapperError(
            "historical metadata-excluded count mismatch"
        )

    if decision_counts.get(
        source_eligibility.WITHHOLD,
        0,
    ) != expectations.metadata_unresolved:
        raise Stage5BWrapperError(
            "historical metadata-unresolved count mismatch"
        )

    try:
        retained = (
            source_membership
            .metadata_retained_accessions(
                assessments
            )
        )
    except Exception as exc:
        raise Stage5BWrapperError(
            "historical metadata-retained membership failed closed"
        ) from exc

    if len(
        retained
    ) != expectations.metadata_retained:
        raise Stage5BWrapperError(
            "historical metadata-retained membership count mismatch"
        )

    return retained


def _load_baseline(
    path: Path,
    *,
    expected_sha256: str,
    expectations: HistoricalExpectations,
) -> frozenset[str]:
    try:
        baseline = (
            source_membership
            .load_baseline_accessions(
                path,
                expected_sha256=expected_sha256,
                expected_rows=(
                    expectations.baseline_accessions
                ),
            )
        )
    except Exception as exc:
        raise Stage5BWrapperError(
            "historical baseline parsing failed closed"
        ) from exc

    if len(
        baseline
    ) != expectations.baseline_accessions:
        raise Stage5BWrapperError(
            "historical baseline membership count mismatch"
        )

    return baseline


def _reconstruct_historical_absence(
    baseline: frozenset[str],
    retained: frozenset[str],
    *,
    expectations: HistoricalExpectations,
) -> source_holdout.HistoricalReconstruction:
    try:
        reconstruction = (
            source_holdout
            .reconstruct_retained_absent_from_baseline(
                baseline,
                retained,
                expected_summary=(
                    expectations.membership_summary()
                ),
            )
        )
    except Exception as exc:
        raise Stage5BWrapperError(
            "historical absence reconstruction failed closed"
        ) from exc

    if len(
        reconstruction.retained_absent_from_baseline
    ) != expectations.retained_absent_from_baseline:
        raise Stage5BWrapperError(
            "historical absence membership count mismatch"
        )

    return reconstruction


def _input_evidence_rows(
    repo: Path,
    paths: InputPaths,
    identities: InputIdentities,
    frozen_repo_sha256: Mapping[str, str],
) -> tuple[
    Mapping[str, object],
    ...,
]:
    items: list[
        tuple[
            str,
            Path,
            str,
        ]
    ] = [
        (
            "stage5a_complete_universe",
            paths.complete_universe,
            identities.complete_universe,
        ),
        (
            "stage5a_content_manifest",
            paths.stage5a_content_manifest,
            identities.stage5a_content_manifest,
        ),
        (
            "stage5a_execution_provenance",
            paths.stage5a_execution_provenance,
            identities.stage5a_execution_provenance,
        ),
        (
            "historical_raw_source",
            paths.raw_source,
            identities.raw_source,
        ),
        (
            "baseline_matrix",
            paths.baseline_matrix,
            identities.baseline_matrix,
        ),
    ]

    for relative, expected_sha in sorted(
        frozen_repo_sha256.items(),
    ):
        _validate_sha256(
            expected_sha,
            label=(
                "tracked repository evidence SHA256: "
                + relative
            ),
        )

        relative_path = Path(
            relative
        )

        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            raise Stage5BWrapperError(
                "tracked repository evidence path malformed"
            )

        items.append(
            (
                "tracked:"
                + relative,
                Path(
                    repo
                ).resolve()
                / relative_path,
                expected_sha,
            )
        )

    rows = []

    for label, path, identity in items:
        rows.append(
            {
                "label":
                    label,
                "path":
                    str(
                        Path(
                            path
                        ).resolve()
                    ),
                "size_bytes":
                    Path(
                        path
                    ).stat().st_size,
                "sha256":
                    identity,
            }
        )

    return tuple(
        sorted(
            rows,
            key=lambda row: str(
                row[
                    "label"
                ]
            ),
        )
    )


def _content_manifest_rows(
    directory: Path,
    names: Sequence[str],
) -> tuple[
    Mapping[str, object],
    ...,
]:
    rows = []

    for name in sorted(
        names
    ):
        path = (
            directory
            / name
        )

        if (
            not path.is_file()
            or path.is_symlink()
        ):
            raise Stage5BWrapperError(
                "Stage 5B content-manifest source invalid"
            )

        rows.append(
            {
                "path":
                    name,
                "size_bytes":
                    path.stat().st_size,
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
    input_paths: InputPaths,
    input_identities: InputIdentities,
    stage5a_expectations: Stage5AExpectations,
    historical_expectations: HistoricalExpectations,
    frozen_repo_sha256: Mapping[str, str],
) -> Path:
    """Execute Stage 5B with predecision-before-row-parsing ordering."""

    if LOWER_COMMIT_RE.fullmatch(
        expected_commit
    ) is None:
        raise Stage5BWrapperError(
            "expected execution commit malformed"
        )

    wrapper_sha = _validate_sha256(
        expected_wrapper_sha256,
        label="Stage 5B wrapper SHA256",
    )

    wrapper_test_sha = _validate_sha256(
        expected_wrapper_test_sha256,
        label="Stage 5B wrapper-test SHA256",
    )

    # Whole-file identity verification is expressly permitted before the
    # predecision checkpoint. No row from these files is parsed here.
    _physical_preflight(
        input_paths,
        input_identities,
    )

    root = _ensure_output_root_outside_repo(
        output_root,
        repo,
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
        raise Stage5BWrapperError(
            "final Stage 5B output directory already exists"
        )

    if partial_dir.exists():
        raise Stage5BWrapperError(
            "partial Stage 5B output directory already exists"
        )

    partial_dir.mkdir()

    predecision_path = (
        partial_dir
        / "stage5b-predecision-provenance.json"
    )

    predecision = {
        "schema_version":
            1,
        "status":
            "STAGE5B_PREDECISION_FROZEN",
        "bacselect_git_commit":
            expected_commit,
        "stage5_method_sha256":
            EXPECTED_STAGE5_METHOD_SHA256,
        "stage5a_completion_evidence_sha256":
            EXPECTED_STAGE5A_COMPLETION_SHA256,
        "stage5a_content_manifest_sha256":
            input_identities.stage5a_content_manifest,
        "stage5a_execution_provenance_sha256":
            input_identities.stage5a_execution_provenance,
        "complete_universe_artifact_sha256":
            input_identities.complete_universe,
        "complete_universe_membership_sha256":
            stage5a_expectations.complete_universe_membership_sha256,
        "complete_universe_count":
            stage5a_expectations.complete_universe_count,
        "complete_universe_species_count":
            stage5a_expectations.complete_universe_species_count,
        "raw_source_sha256":
            input_identities.raw_source,
        "metadata_parser_sha256":
            EXPECTED_SOURCE_ELIGIBILITY_SHA256,
        "baseline_matrix_sha256":
            input_identities.baseline_matrix,
        "membership_comparator_sha256":
            EXPECTED_SOURCE_MEMBERSHIP_SHA256,
        "stage5b_helper_sha256":
            EXPECTED_STAGE5B_HELPER_SHA256,
        "stage5b_wrapper_sha256":
            wrapper_sha,
        "stage5b_wrapper_test_sha256":
            wrapper_test_sha,
        "frozen_repository_sha256":
            dict(
                sorted(
                    frozen_repo_sha256.items()
                )
            ),
        "stage5a_finalized_and_immutable":
            True,
        "complete_universe_rows_parsed":
            False,
        "raw_source_records_parsed":
            False,
        "baseline_matrix_rows_parsed":
            False,
        "historical_absence_membership_reconstructed":
            False,
        "holdout_membership_generated":
            False,
        "adequacy_gate_evaluated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    predecision_sha = write_json_atomic(
        predecision_path,
        predecision,
    )

    # Identity-bearing rows may only be parsed after the predecision artifact
    # above exists on disk.
    universe = _load_complete_universe(
        input_paths.complete_universe,
        expectations=stage5a_expectations,
    )

    retained = _load_metadata_retained(
        input_paths.raw_source,
        expectations=historical_expectations,
    )

    baseline = _load_baseline(
        input_paths.baseline_matrix,
        expected_sha256=(
            input_identities.baseline_matrix
        ),
        expectations=historical_expectations,
    )

    reconstruction = (
        _reconstruct_historical_absence(
            baseline,
            retained,
            expectations=historical_expectations,
        )
    )

    absence_path = (
        partial_dir
        / "reconstructed-retained-absent-from-baseline.tsv"
    )

    absence_sha = write_tsv_atomic(
        absence_path,
        source_holdout.RECONSTRUCTED_ABSENCE_FIELDS,
        source_holdout.reconstructed_absence_rows(
            reconstruction
        ),
    )

    try:
        holdout = (
            source_holdout
            .derive_external_holdout(
                universe,
                reconstruction.retained_absent_from_baseline,
            )
        )

        holdout_summary = (
            source_holdout
            .summarize_holdout(
                holdout
            )
        )

        adequacy = (
            source_holdout
            .evaluate_adequacy(
                holdout
            )
        )

    except source_holdout.HoldoutError as exc:
        raise Stage5BWrapperError(
            "external holdout derivation failed closed"
        ) from exc

    holdout_path = (
        partial_dir
        / "external-decision-holdout.tsv"
    )

    holdout_sha = write_tsv_atomic(
        holdout_path,
        source_holdout.EXTERNAL_HOLDOUT_FIELDS,
        source_holdout.external_holdout_rows(
            holdout
        ),
    )

    input_manifest_path = (
        partial_dir
        / "stage5b-input-evidence-manifest.tsv"
    )

    input_manifest_sha = write_tsv_atomic(
        input_manifest_path,
        INPUT_EVIDENCE_FIELDS,
        _input_evidence_rows(
            repo,
            input_paths,
            input_identities,
            frozen_repo_sha256,
        ),
    )

    execution_provenance_path = (
        partial_dir
        / "stage5b-execution-provenance.json"
    )

    execution_provenance = {
        "schema_version":
            1,
        "status":
            "STAGE5B_EXTERNAL_HOLDOUT_COMPLETE",
        "bacselect_git_commit":
            expected_commit,
        "stage5_method_sha256":
            EXPECTED_STAGE5_METHOD_SHA256,
        "stage5a_completion_evidence_sha256":
            EXPECTED_STAGE5A_COMPLETION_SHA256,
        "stage5b_helper_sha256":
            EXPECTED_STAGE5B_HELPER_SHA256,
        "stage5b_wrapper_sha256":
            wrapper_sha,
        "stage5b_wrapper_test_sha256":
            wrapper_test_sha,
        "predecision_provenance_sha256":
            predecision_sha,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "complete_universe_rows_parsed":
            True,
        "raw_source_records_parsed":
            True,
        "baseline_matrix_rows_parsed":
            True,
        "historical_absence_membership_reconstructed":
            True,
        "holdout_membership_generated":
            True,
        "adequacy_gate_evaluated":
            True,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
        "complete_universe_count":
            len(
                universe
            ),
        "complete_universe_species_count":
            len(
                {
                    item.species_taxid
                    for item in universe
                }
            ),
        "historical_reconstruction":
            reconstruction.summary.as_dict(),
        "reconstructed_absence_count":
            len(
                reconstruction.retained_absent_from_baseline
            ),
        "reconstructed_absence_membership_sha256":
            reconstruction.membership_sha256,
        "reconstructed_absence_artifact_sha256":
            absence_sha,
        "external_holdout_count":
            holdout_summary.genome_count,
        "external_holdout_species_count":
            holdout_summary.distinct_species_count,
        "external_holdout_membership_sha256":
            holdout_summary.membership_sha256,
        "external_holdout_artifact_sha256":
            holdout_sha,
        "adequacy":
            adequacy.as_dict(),
    }

    execution_provenance_sha = write_json_atomic(
        execution_provenance_path,
        execution_provenance,
    )

    summary_path = (
        partial_dir
        / "stage5b-aggregate-summary.json"
    )

    summary = {
        "schema_version":
            1,
        "status":
            "STAGE5B_EXTERNAL_HOLDOUT_COMPLETE",
        "complete_universe_count":
            len(
                universe
            ),
        "complete_universe_species_count":
            len(
                {
                    item.species_taxid
                    for item in universe
                }
            ),
        "complete_universe_membership_sha256":
            stage5a_expectations.complete_universe_membership_sha256,
        "historical_reconstruction":
            reconstruction.summary.as_dict(),
        "reconstructed_absence_count":
            len(
                reconstruction.retained_absent_from_baseline
            ),
        "reconstructed_absence_membership_sha256":
            reconstruction.membership_sha256,
        "reconstructed_absence_artifact_sha256":
            absence_sha,
        "external_holdout_count":
            holdout_summary.genome_count,
        "external_holdout_species_count":
            holdout_summary.distinct_species_count,
        "external_holdout_membership_sha256":
            holdout_summary.membership_sha256,
        "external_holdout_artifact_sha256":
            holdout_sha,
        "adequacy":
            adequacy.as_dict(),
        "predecision_provenance_sha256":
            predecision_sha,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "execution_provenance_sha256":
            execution_provenance_sha,
        "structural_features_calculated":
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
        / "stage5b-content-manifest.tsv"
    )

    covered_names = (
        "stage5b-predecision-provenance.json",
        "reconstructed-retained-absent-from-baseline.tsv",
        "external-decision-holdout.tsv",
        "stage5b-input-evidence-manifest.tsv",
        "stage5b-execution-provenance.json",
        "stage5b-aggregate-summary.json",
    )

    content_manifest_sha = write_tsv_atomic(
        content_manifest_path,
        CONTENT_MANIFEST_FIELDS,
        _content_manifest_rows(
            partial_dir,
            covered_names,
        ),
    )

    expected_final_files = {
        "stage5b-predecision-provenance.json",
        "reconstructed-retained-absent-from-baseline.tsv",
        "external-decision-holdout.tsv",
        "stage5b-input-evidence-manifest.tsv",
        "stage5b-execution-provenance.json",
        "stage5b-aggregate-summary.json",
        "stage5b-content-manifest.tsv",
    }

    observed_final_files = {
        path.name
        for path in partial_dir.iterdir()
        if path.is_file()
    }

    if observed_final_files != expected_final_files:
        raise Stage5BWrapperError(
            "Stage 5B final artifact set mismatch"
        )

    os.replace(
        partial_dir,
        final_dir,
    )

    print(
        "PASS | Stage 5B external-holdout execution complete"
    )
    print(
        "historical_metadata_retained="
        f"{historical_expectations.metadata_retained}"
    )
    print(
        "historical_absent_from_baseline="
        f"{len(reconstruction.retained_absent_from_baseline)}"
    )
    print(
        "reconstructed_absence_membership_sha256="
        f"{reconstruction.membership_sha256}"
    )
    print(
        f"reconstructed_absence_artifact_sha256={absence_sha}"
    )
    print(
        f"external_holdout_count={holdout_summary.genome_count}"
    )
    print(
        "external_holdout_species_count="
        f"{holdout_summary.distinct_species_count}"
    )
    print(
        "external_holdout_membership_sha256="
        f"{holdout_summary.membership_sha256}"
    )
    print(
        f"external_holdout_artifact_sha256={holdout_sha}"
    )
    print(
        f"adequacy_status={adequacy.status}"
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
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute frozen BacSelect selector-v1 "
            "Stage 5B external-holdout composition."
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
        "--stage5a-execution-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--raw-source",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--baseline-matrix",
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
    argv: list[str] | None = None,
) -> int:
    args = parse_args(
        argv
    )

    repo = args.repo.resolve()

    try:
        frozen_repo_sha256 = preflight_repository(
            repo,
            expected_commit=(
                args.expected_commit
            ),
            expected_wrapper_sha256=(
                args.expected_wrapper_sha256
            ),
            expected_wrapper_test_sha256=(
                args.expected_wrapper_test_sha256
            ),
        )

        load_tracked_stage5b_evidence(
            repo
        )

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
            input_paths=InputPaths(
                stage5a_execution_dir=(
                    args.stage5a_execution_dir
                ),
                raw_source=(
                    args.raw_source
                ),
                baseline_matrix=(
                    args.baseline_matrix
                ),
            ),
            input_identities=(
                PRODUCTION_INPUT_IDENTITIES
            ),
            stage5a_expectations=(
                PRODUCTION_STAGE5A_EXPECTATIONS
            ),
            historical_expectations=(
                PRODUCTION_HISTORICAL_EXPECTATIONS
            ),
            frozen_repo_sha256=(
                frozen_repo_sha256
            ),
        )

    except Stage5BWrapperError:
        print(
            "ERROR | Stage 5B execution failed closed",
            file=sys.stderr,
        )

        return 1

    except Exception:
        print(
            "ERROR | Stage 5B execution failed closed",
            file=sys.stderr,
        )

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
