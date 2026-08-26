#!/usr/bin/env python3
"""Run frozen BacSelect selector-v1 Stage 2 repeated-BioSample execution.

Importing this module performs no production evidence access.

The wrapper reuses the frozen Stage 1 acquisition/population reconstruction,
binds that population to the frozen Stage 1 source-truth decisions and frozen
BioSample manifests, writes Stage 2 predecision provenance, and only then
invokes the frozen Stage 2 fingerprint and reconciliation implementation.

Identity-bearing Stage 2 outputs are written only beneath a caller-supplied
scratch output root.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Mapping, Sequence

from bacselect.source_eligibility import (
    BIOSAMPLE_RE,
)
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    BIOSAMPLE_NONREPRESENTATIVE,
    BIOSAMPLE_UNRESOLVED,
    BioSampleDecision,
)
from bacselect.source_repeated_biosample_execution import (
    VerifiedBioSampleFingerprint,
    fingerprint_stage2_candidate,
    reconcile_verified_candidates,
)
from bacselect.source_truth_execution import (
    accession_membership_sha256,
    load_component_index,
    load_package_manifest,
)


# ---------------------------------------------------------------------------
# Frozen repository identities
# ---------------------------------------------------------------------------

STAGE1_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_source_truth_execution.py"
)

STAGE1_TEST_RELATIVE = Path(
    "tests/test_run_source_truth_execution.py"
)

STAGE2_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-stage2-repeated-biosample-execution.md"
)

STAGE2_IMPLEMENTATION_RELATIVE = Path(
    "src/bacselect/"
    "source_repeated_biosample_execution.py"
)

STAGE2_TEST_RELATIVE = Path(
    "tests/test_source_repeated_biosample_execution.py"
)

SOURCE_ELIGIBILITY_RELATIVE = Path(
    "src/bacselect/source_eligibility.py"
)

SOURCE_TRUTH_EXECUTION_RELATIVE = Path(
    "src/bacselect/source_truth_execution.py"
)

SOURCE_FINGERPRINT_RELATIVE = Path(
    "src/bacselect/source_fingerprint.py"
)

POST_SEQUENCE_RELATIVE = Path(
    "src/bacselect/"
    "source_post_sequence_eligibility.py"
)

SOURCE_TRUTH_RELATIVE = Path(
    "src/bacselect/source_truth.py"
)

STAGE1_COMPLETION_RELATIVE = Path(
    "validation/selector-v1/"
    "stage1-source-truth-completion-evidence.json"
)


EXPECTED_STAGE1_WRAPPER_SHA256 = (
    "59dd3ea140ee9a49c86dbed810639728000add8ac30121ab41d2c59e328961d5"
)

EXPECTED_STAGE1_TEST_SHA256 = (
    "03bb88613a0689bc67b9e388a0b40fdf298174ff18b948a1ff0572bdb0b9954a"
)

EXPECTED_STAGE2_METHOD_SHA256 = (
    "9350a33ba303efa1b90ce505e0e530ecfdbad8cb293b9934cbc906674c91ed14"
)

EXPECTED_STAGE2_IMPLEMENTATION_SHA256 = (
    "ee95fac744d1daf413742b39e9b7d8b5d4d65c52edce08dc0df2dc1ff776a222"
)

EXPECTED_STAGE2_TEST_SHA256 = (
    "b52760e76787fbca791a30c8070e80d831a231f2aea70204f922127c8623e5e1"
)

EXPECTED_SOURCE_ELIGIBILITY_SHA256 = (
    "6e57dd950f972a9883e8fcbc78a18c694a5fabda58b03835f268eef681a03cc2"
)

EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256 = (
    "83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92"
)

EXPECTED_SOURCE_FINGERPRINT_SHA256 = (
    "6c994d243709abdbe9d7c8949e156009b9f31f3fcef3247cc3c5679e2fff41c9"
)

EXPECTED_POST_SEQUENCE_SHA256 = (
    "62fa1e2f7d806f94b5f5eca73fb768745d3913a4b218a4d354562033cd300fe8"
)

EXPECTED_SOURCE_TRUTH_SHA256 = (
    "6aac349e591daebfc2569c14633cc807b5d7186ed4ed3e79f37f6627f5184486"
)

EXPECTED_STAGE1_COMPLETION_SHA256 = (
    "b459801d832137fb0399bc34dfe3611636ca1ffc0339c802a16a6216f9595dd2"
)


FROZEN_REPO_FILES = {
    STAGE1_WRAPPER_RELATIVE:
        EXPECTED_STAGE1_WRAPPER_SHA256,
    STAGE1_TEST_RELATIVE:
        EXPECTED_STAGE1_TEST_SHA256,
    STAGE2_METHOD_RELATIVE:
        EXPECTED_STAGE2_METHOD_SHA256,
    STAGE2_IMPLEMENTATION_RELATIVE:
        EXPECTED_STAGE2_IMPLEMENTATION_SHA256,
    STAGE2_TEST_RELATIVE:
        EXPECTED_STAGE2_TEST_SHA256,
    SOURCE_ELIGIBILITY_RELATIVE:
        EXPECTED_SOURCE_ELIGIBILITY_SHA256,
    SOURCE_TRUTH_EXECUTION_RELATIVE:
        EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256,
    SOURCE_FINGERPRINT_RELATIVE:
        EXPECTED_SOURCE_FINGERPRINT_SHA256,
    POST_SEQUENCE_RELATIVE:
        EXPECTED_POST_SEQUENCE_SHA256,
    SOURCE_TRUTH_RELATIVE:
        EXPECTED_SOURCE_TRUTH_SHA256,
    STAGE1_COMPLETION_RELATIVE:
        EXPECTED_STAGE1_COMPLETION_SHA256,
}


# ---------------------------------------------------------------------------
# Frozen production contracts
# ---------------------------------------------------------------------------

EXPECTED_STAGE1_DECISIONS_SHA256 = (
    "530ccec7679db9866ae04e81f05080094ace563a530a122c8ae97251801ea96d"
)

EXPECTED_CACHE_MANIFEST_SHA256 = (
    "32a61975f99b973c3e7a2f58ac98beafe7b63c437c4bf0e3f7f51872680faff1"
)

EXPECTED_FRESH_MANIFEST_SHA256 = (
    "1c9a73231d6b8ebfed76fb60621616588a4f51b1144e5d7880f14ddf26d1863b"
)

EXPECTED_STAGE1_TOTAL = 68_480
EXPECTED_STAGE1_SUITABLE = 68_359
EXPECTED_STAGE1_EXCLUDED = 121
EXPECTED_STAGE1_UNRESOLVED = 0

EXPECTED_CACHE_MANIFEST_ROWS = 55_151
EXPECTED_FRESH_MANIFEST_ROWS = 15_326
EXPECTED_METADATA_RETAINED = 70_477


CACHE_BIOSAMPLE_FIELDS = (
    "canonical_genbank_assembly_accession",
    "fresh_biosample",
    "historical_batch",
    "historical_sequence_eligibility",
    "historical_exclusion_reasons",
)

FRESH_BIOSAMPLE_FIELDS = (
    "canonical_genbank_assembly_accession",
    "fresh_biosample",
    "acquisition_reason",
)

STAGE2_DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "biosample",
    "source_evidence_sha256",
    "assembly_fingerprint",
    "stage2_status",
    "stage2_reason",
)

STAGE2_GROUP_FIELDS = (
    "biosample",
    "member_count",
    "distinct_fingerprint_count",
    "group_class",
)

CONTENT_MANIFEST_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
)


class Stage2WrapperError(RuntimeError):
    """Raised when Stage 2 orchestration evidence fails closed."""


@dataclass(frozen=True)
class Stage1DecisionBundle:
    all_accessions: tuple[str, ...]
    suitable_source_sha256: Mapping[str, str]
    all_membership_sha256: str
    suitable_membership_sha256: str
    status_counts: Mapping[str, int]


@dataclass(frozen=True)
class BioSampleMappingBundle:
    biosample_by_accession: Mapping[str, str]
    cache_row_count: int
    fresh_row_count: int


def sha256_file(
    path: Path,
) -> str:
    path = Path(path)

    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise Stage2WrapperError(
            f"required regular file missing: {path}"
        )

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_stage1_wrapper(
    repo: Path,
) -> ModuleType:
    """Load only the exact frozen Stage 1 orchestration implementation."""

    path = (
        Path(repo).resolve()
        / STAGE1_WRAPPER_RELATIVE
    )

    observed = sha256_file(
        path
    )

    if observed != EXPECTED_STAGE1_WRAPPER_SHA256:
        raise Stage2WrapperError(
            "frozen Stage 1 wrapper SHA256 mismatch"
        )

    module_name = (
        "_bacselect_frozen_stage1_source_truth_execution"
    )

    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise Stage2WrapperError(
            "cannot load frozen Stage 1 wrapper"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        module_name
    ] = module

    try:
        spec.loader.exec_module(
            module
        )
    except BaseException:
        sys.modules.pop(
            module_name,
            None,
        )
        raise

    return module


def _nonnegative_int(
    value: str,
    *,
    label: str,
) -> int:
    try:
        parsed = int(
            value
        )
    except (TypeError, ValueError):
        raise Stage2WrapperError(
            f"{label} must be a nonnegative integer"
        ) from None

    if parsed < 0:
        raise Stage2WrapperError(
            f"{label} must be a nonnegative integer"
        )

    return parsed


def load_stage1_decisions(
    path: Path,
    *,
    stage1: ModuleType,
    expected_sha256: str = (
        EXPECTED_STAGE1_DECISIONS_SHA256
    ),
    expected_total: int = EXPECTED_STAGE1_TOTAL,
    expected_suitable: int = EXPECTED_STAGE1_SUITABLE,
    expected_excluded: int = EXPECTED_STAGE1_EXCLUDED,
    expected_unresolved: int = EXPECTED_STAGE1_UNRESOLVED,
) -> Stage1DecisionBundle:
    """Load the exact frozen Stage 1 terminal decision table."""

    stage1.require_sha256(
        path,
        expected_sha256,
        "Stage 1 source-truth decisions",
    )

    fields, rows = stage1.read_tsv(
        path
    )

    stage1.require_exact_fields(
        fields,
        stage1.DECISION_FIELDS,
        "Stage 1 source-truth decisions",
    )

    if len(rows) != expected_total:
        raise Stage2WrapperError(
            "Stage 1 decision row count mismatch"
        )

    seen: set[str] = set()
    suitable: dict[str, str] = {}
    statuses = Counter()

    for row in rows:
        accession = stage1.require_accession(
            row[
                "canonical_genbank_assembly_accession"
            ],
            "Stage 1 decisions",
        )

        if accession in seen:
            raise Stage2WrapperError(
                "duplicate accession in Stage 1 decisions"
            )

        seen.add(
            accession
        )

        source_sha = stage1.require_lower_sha256(
            row[
                "source_evidence_sha256"
            ],
            "Stage 1 source evidence",
        )

        stage1.require_lower_sha256(
            row[
                "sequence_set_sha256"
            ],
            "Stage 1 sequence-set evidence",
        )

        _nonnegative_int(
            row[
                "duplicate_relation_count"
            ],
            label="Stage 1 duplicate relation count",
        )

        _nonnegative_int(
            row[
                "containment_relation_count"
            ],
            label="Stage 1 containment relation count",
        )

        status = row[
            "source_truth_status"
        ]

        if status not in (
            stage1.TERMINAL_STATUSES
        ):
            raise Stage2WrapperError(
                "unexpected Stage 1 source-truth status"
            )

        if not row[
            "source_truth_reason"
        ]:
            raise Stage2WrapperError(
                "empty Stage 1 source-truth reason"
            )

        statuses[
            status
        ] += 1

        if status == "SUITABLE":
            suitable[
                accession
            ] = source_sha

    expected_counts = Counter(
        {
            "SUITABLE":
                expected_suitable,
            "EXCLUDE_SOURCE_TRUTH":
                expected_excluded,
        }
    )

    if expected_unresolved:
        expected_counts[
            "REVIEW_UNRESOLVED"
        ] = expected_unresolved

    if statuses != expected_counts:
        raise Stage2WrapperError(
            "Stage 1 terminal status counts mismatch"
        )

    if len(suitable) != expected_suitable:
        raise Stage2WrapperError(
            "Stage 2 input candidate count mismatch"
        )

    all_accessions = tuple(
        sorted(
            seen
        )
    )

    suitable_accessions = tuple(
        sorted(
            suitable
        )
    )

    return Stage1DecisionBundle(
        all_accessions=all_accessions,
        suitable_source_sha256=dict(
            suitable
        ),
        all_membership_sha256=(
            accession_membership_sha256(
                all_accessions
            )
        ),
        suitable_membership_sha256=(
            accession_membership_sha256(
                suitable_accessions
            )
        ),
        status_counts=dict(
            sorted(
                statuses.items()
            )
        ),
    )


def _validate_biosample(
    value: str,
) -> str:
    if (
        not isinstance(value, str)
        or BIOSAMPLE_RE.fullmatch(
            value
        ) is None
    ):
        raise Stage2WrapperError(
            "malformed frozen BioSample accession"
        )

    return value


def load_biosample_mapping(
    *,
    cache_manifest_path: Path,
    fresh_manifest_path: Path,
    stage1: ModuleType,
    expected_cache_sha256: str = (
        EXPECTED_CACHE_MANIFEST_SHA256
    ),
    expected_fresh_sha256: str = (
        EXPECTED_FRESH_MANIFEST_SHA256
    ),
    expected_cache_rows: int = (
        EXPECTED_CACHE_MANIFEST_ROWS
    ),
    expected_fresh_rows: int = (
        EXPECTED_FRESH_MANIFEST_ROWS
    ),
    expected_total: int = (
        EXPECTED_METADATA_RETAINED
    ),
) -> BioSampleMappingBundle:
    """Load the frozen accession-to-BioSample mapping."""

    stage1.require_sha256(
        cache_manifest_path,
        expected_cache_sha256,
        "cache-reuse manifest",
    )

    stage1.require_sha256(
        fresh_manifest_path,
        expected_fresh_sha256,
        "fresh-download manifest",
    )

    cache_fields, cache_rows = (
        stage1.read_tsv(
            cache_manifest_path
        )
    )

    fresh_fields, fresh_rows = (
        stage1.read_tsv(
            fresh_manifest_path
        )
    )

    stage1.require_exact_fields(
        cache_fields,
        CACHE_BIOSAMPLE_FIELDS,
        "cache-reuse BioSample manifest",
    )

    stage1.require_exact_fields(
        fresh_fields,
        FRESH_BIOSAMPLE_FIELDS,
        "fresh-download BioSample manifest",
    )

    if len(
        cache_rows
    ) != expected_cache_rows:
        raise Stage2WrapperError(
            "cache-reuse BioSample manifest row count mismatch"
        )

    if len(
        fresh_rows
    ) != expected_fresh_rows:
        raise Stage2WrapperError(
            "fresh-download BioSample manifest row count mismatch"
        )

    cache_map: dict[str, str] = {}
    fresh_map: dict[str, str] = {}

    for row in cache_rows:
        accession = stage1.require_accession(
            row[
                "canonical_genbank_assembly_accession"
            ],
            "cache-reuse BioSample manifest",
        )

        if accession in cache_map:
            raise Stage2WrapperError(
                "duplicate accession in cache-reuse BioSample manifest"
            )

        biosample = _validate_biosample(
            row[
                "fresh_biosample"
            ]
        )

        if not row[
            "historical_batch"
        ]:
            raise Stage2WrapperError(
                "empty historical batch in cache-reuse manifest"
            )

        if row[
            "historical_sequence_eligibility"
        ] not in {
            "eligible",
            "ineligible",
        }:
            raise Stage2WrapperError(
                "unexpected historical sequence eligibility"
            )

        cache_map[
            accession
        ] = biosample

    for row in fresh_rows:
        accession = stage1.require_accession(
            row[
                "canonical_genbank_assembly_accession"
            ],
            "fresh-download BioSample manifest",
        )

        if accession in fresh_map:
            raise Stage2WrapperError(
                "duplicate accession in fresh-download BioSample manifest"
            )

        biosample = _validate_biosample(
            row[
                "fresh_biosample"
            ]
        )

        if not row[
            "acquisition_reason"
        ]:
            raise Stage2WrapperError(
                "empty fresh acquisition reason"
            )

        fresh_map[
            accession
        ] = biosample

    overlap = (
        set(
            cache_map
        )
        & set(
            fresh_map
        )
    )

    if overlap:
        raise Stage2WrapperError(
            "cache/fresh BioSample accession overlap"
        )

    combined = {
        **cache_map,
        **fresh_map,
    }

    if len(
        combined
    ) != expected_total:
        raise Stage2WrapperError(
            "combined frozen BioSample mapping count mismatch"
        )

    return BioSampleMappingBundle(
        biosample_by_accession=combined,
        cache_row_count=len(
            cache_map
        ),
        fresh_row_count=len(
            fresh_map
        ),
    )


def reconstruct_stage1_population(
    *,
    repo: Path,
    stage1: ModuleType,
    historical_root: Path,
    cache_reuse_accessions: Path,
    cache_reuse_manifest: Path,
    cache_verification: Path,
    fresh_root: Path,
    recovery_root: Path,
):
    """Reuse the exact frozen Stage 1 population reconstruction."""

    acquisition_evidence = (
        stage1.load_final_acquisition_evidence(
            repo
        )
    )

    (
        historical_eligible_batches,
        historical_ineligible_batches,
        handoff_evidence_rows,
    ) = stage1.load_cache_handoff(
        cache_accessions_path=(
            cache_reuse_accessions
        ),
        cache_manifest_path=(
            cache_reuse_manifest
        ),
        cache_verification_path=(
            cache_verification
        ),
        acquisition_evidence=(
            acquisition_evidence
        ),
        contract=(
            stage1.PRODUCTION_CONTRACT
        ),
    )

    historical_candidate_manifest = (
        cache_reuse_manifest.resolve().parent
        / "historical-candidate-audits-sha256.tsv"
    )

    (
        historical_candidate_sha256,
        historical_candidate_manifest_evidence,
    ) = (
        stage1.load_historical_candidate_audit_manifest(
            historical_candidate_manifest,
            expected_sha256=(
                stage1.EXPECTED_HISTORICAL_CANDIDATE_AUDITS_SHA256
            ),
            expected_count=111,
        )
    )

    (
        historical_candidates,
        historical_specs,
        historical_evidence_rows,
    ) = stage1.build_historical_population(
        historical_root=historical_root,
        eligible_batches=(
            historical_eligible_batches
        ),
        ineligible_batches=(
            historical_ineligible_batches
        ),
        candidate_audit_sha256_by_batch=(
            historical_candidate_sha256
        ),
        contract=(
            stage1.PRODUCTION_CONTRACT
        ),
    )

    (
        fresh_candidates,
        fresh_specs,
        fresh_evidence_rows,
    ) = stage1.build_fresh_population(
        fresh_root=fresh_root,
        recovery_root=recovery_root,
        contract=(
            stage1.PRODUCTION_CONTRACT
        ),
        recovery_expected_sha256=(
            stage1.RECOVERY_EXPECTED_SHA256
        ),
        recovery_summary_sha256=(
            stage1.EXPECTED_FRESH_RECOVERY_SUMMARY_SHA256
        ),
    )

    bundle = stage1.build_population_bundle(
        historical_candidates=(
            historical_candidates
        ),
        fresh_candidates=(
            fresh_candidates
        ),
        historical_specs=(
            historical_specs
        ),
        fresh_specs=(
            fresh_specs
        ),
        input_evidence_rows=(
            *handoff_evidence_rows,
            historical_candidate_manifest_evidence,
            *historical_evidence_rows,
            *fresh_evidence_rows,
        ),
        expected_total=(
            stage1.EXPECTED_STAGE1_TOTAL
        ),
    )

    stage1.verify_recovery_001_membership(
        bundle
    )

    return bundle


def verify_stage2_population_binding(
    *,
    bundle,
    decisions: Stage1DecisionBundle,
    biosamples: BioSampleMappingBundle,
    expected_stage1_total: int = EXPECTED_STAGE1_TOTAL,
    expected_stage2_total: int = EXPECTED_STAGE1_SUITABLE,
) -> None:
    """Require exact agreement among reconstruction, Stage 1, and BioSamples."""

    reconstructed = tuple(
        candidate.accession
        for candidate in (
            *bundle.historical_candidates,
            *bundle.fresh_candidates,
        )
    )

    if len(
        reconstructed
    ) != expected_stage1_total:
        raise Stage2WrapperError(
            "reconstructed Stage 1 candidate count mismatch"
        )

    if len(
        set(
            reconstructed
        )
    ) != len(
        reconstructed
    ):
        raise Stage2WrapperError(
            "duplicate accession in reconstructed Stage 1 population"
        )

    reconstructed_set = set(
        reconstructed
    )

    if reconstructed_set != set(
        decisions.all_accessions
    ):
        raise Stage2WrapperError(
            "Stage 1 decisions and reconstructed population differ"
        )

    if (
        bundle.combined_membership_sha256
        != decisions.all_membership_sha256
    ):
        raise Stage2WrapperError(
            "Stage 1 reconstructed membership SHA256 mismatch"
        )

    suitable = set(
        decisions.suitable_source_sha256
    )

    if len(
        suitable
    ) != expected_stage2_total:
        raise Stage2WrapperError(
            "Stage 2 suitable membership count mismatch"
        )

    if not suitable <= set(
        biosamples.biosample_by_accession
    ):
        raise Stage2WrapperError(
            "Stage 2 candidate missing frozen BioSample mapping"
        )


def fingerprint_population(
    *,
    bundle,
    decisions: Stage1DecisionBundle,
    biosamples: BioSampleMappingBundle,
) -> tuple[
    VerifiedBioSampleFingerprint,
    ...,
]:
    """Fingerprint exactly the Stage 1 SUITABLE candidates."""

    wanted = set(
        decisions.suitable_source_sha256
    )

    observed: list[
        VerifiedBioSampleFingerprint
    ] = []

    seen: set[str] = set()

    for batch in bundle.batches:
        selected = tuple(
            candidate
            for candidate in batch.candidates
            if candidate.accession in wanted
        )

        if not selected:
            continue

        selected_accessions = tuple(
            candidate.accession
            for candidate in selected
        )

        component_index = (
            load_component_index(
                batch.component_audit,
                accessions=selected_accessions,
            )
        )

        package_manifest = (
            load_package_manifest(
                batch.package_manifest
            )
        )

        for candidate in sorted(
            selected,
            key=lambda item:
                item.accession,
        ):
            accession = (
                candidate.accession
            )

            if accession in seen:
                raise Stage2WrapperError(
                    "duplicate candidate across Stage 2 batch specifications"
                )

            seen.add(
                accession
            )

            component_rows = (
                component_index.get(
                    accession
                )
            )

            if component_rows is None:
                raise Stage2WrapperError(
                    "Stage 2 candidate lacks component evidence"
                )

            biosample = (
                biosamples.biosample_by_accession.get(
                    accession
                )
            )

            if biosample is None:
                raise Stage2WrapperError(
                    "Stage 2 candidate lacks BioSample evidence"
                )

            observed.append(
                fingerprint_stage2_candidate(
                    candidate=candidate,
                    component_rows=component_rows,
                    package_manifest=package_manifest,
                    expected_source_evidence_sha256=(
                        decisions.suitable_source_sha256[
                            accession
                        ]
                    ),
                    biosample=biosample,
                )
            )

    if seen != wanted:
        raise Stage2WrapperError(
            "Stage 2 fingerprint population incomplete"
        )

    if len(
        observed
    ) != len(
        wanted
    ):
        raise Stage2WrapperError(
            "Stage 2 fingerprint count mismatch"
        )

    return tuple(
        sorted(
            observed,
            key=lambda item:
                item.accession,
        )
    )


def build_group_rows(
    records: Sequence[
        VerifiedBioSampleFingerprint
    ],
    decisions: Mapping[
        str,
        BioSampleDecision,
    ],
) -> tuple[
    tuple[dict[str, object], ...],
    Counter,
]:
    """Report BioSample groups from frozen reconciliation decisions.

    Group class is derived from the already-frozen Stage 2 decisions.
    Fingerprint cardinality is retained only as descriptive evidence and
    as a fail-closed consistency check. It is not used to choose the
    scientific Stage 2 disposition.
    """

    grouped: dict[
        str,
        list[
            VerifiedBioSampleFingerprint
        ],
    ] = defaultdict(list)

    seen_accessions: set[str] = set()

    for record in records:
        if record.accession in seen_accessions:
            raise Stage2WrapperError(
                "duplicate accession in Stage 2 group reporting"
            )

        seen_accessions.add(
            record.accession
        )

        decision = decisions.get(
            record.accession
        )

        if not isinstance(
            decision,
            BioSampleDecision,
        ):
            raise Stage2WrapperError(
                "Stage 2 group member lacks frozen reconciliation decision"
            )

        grouped[
            record.biosample
        ].append(
            record
        )

    if set(
        decisions
    ) != seen_accessions:
        raise Stage2WrapperError(
            "Stage 2 group reporting decision membership mismatch"
        )

    counts = Counter()

    rows: list[
        dict[str, object]
    ] = []

    for biosample in sorted(
        grouped
    ):
        members = tuple(
            sorted(
                grouped[
                    biosample
                ],
                key=lambda item:
                    item.accession,
            )
        )

        member_decisions = tuple(
            decisions[
                member.accession
            ]
            for member in members
        )

        status_counts = Counter(
            decision.status
            for decision in member_decisions
        )

        fingerprints = {
            member.assembly_fingerprint
            for member in members
        }

        distinct_fingerprint_count = len(
            fingerprints
        )

        if len(
            members
        ) == 1:
            expected_statuses = Counter(
                {
                    BIOSAMPLE_CONTINUE:
                        1,
                }
            )

            if status_counts != expected_statuses:
                raise Stage2WrapperError(
                    "singleton BioSample disagrees with frozen reconciliation"
                )

            group_class = (
                "SINGLETON"
            )

            counts[
                "singleton"
            ] += 1

            if distinct_fingerprint_count != 1:
                raise Stage2WrapperError(
                    "singleton BioSample fingerprint accounting mismatch"
                )

        elif status_counts == Counter(
            {
                BIOSAMPLE_CONTINUE:
                    1,
                BIOSAMPLE_NONREPRESENTATIVE:
                    len(
                        members
                    )
                    - 1,
            }
        ):
            group_class = (
                "IDENTICAL_REPEAT"
            )

            counts[
                "identical_repeated"
            ] += 1

            counts[
                "repeated"
            ] += 1

            if distinct_fingerprint_count != 1:
                raise Stage2WrapperError(
                    "identical repeated BioSample disagrees with fingerprint evidence"
                )

        elif status_counts == Counter(
            {
                BIOSAMPLE_UNRESOLVED:
                    len(
                        members
                    ),
            }
        ):
            group_class = (
                "DIFFERING_REPEAT"
            )

            counts[
                "differing_repeated"
            ] += 1

            counts[
                "repeated"
            ] += 1

            if distinct_fingerprint_count < 2:
                raise Stage2WrapperError(
                    "differing repeated BioSample disagrees with fingerprint evidence"
                )

        else:
            raise Stage2WrapperError(
                "BioSample group has impossible frozen decision pattern"
            )

        counts[
            "all"
        ] += 1

        rows.append(
            {
                "biosample":
                    biosample,
                "member_count":
                    len(
                        members
                    ),
                "distinct_fingerprint_count":
                    distinct_fingerprint_count,
                "group_class":
                    group_class,
            }
        )

    if (
        counts[
            "singleton"
        ]
        + counts[
            "repeated"
        ]
        != counts[
            "all"
        ]
    ):
        raise Stage2WrapperError(
            "Stage 2 BioSample group accounting mismatch"
        )

    if (
        counts[
            "identical_repeated"
        ]
        + counts[
            "differing_repeated"
        ]
        != counts[
            "repeated"
        ]
    ):
        raise Stage2WrapperError(
            "Stage 2 repeated-group accounting mismatch"
        )

    return (
        tuple(
            rows
        ),
        counts,
    )


def execute_to_scratch(
    *,
    repo: Path,
    expected_commit: str,
    output_root: Path,
    stage1: ModuleType,
    bundle,
    decisions: Stage1DecisionBundle,
    biosamples: BioSampleMappingBundle,
    frozen_repo_sha256: Mapping[str, str],
    stage1_decisions_path: Path,
    fresh_manifest_path: Path,
) -> Path:
    """Write predecision provenance, then execute Stage 2."""

    output_root = (
        stage1.ensure_output_root_outside_repo(
            repo,
            output_root,
        )
    )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_dir = (
        output_root
        / expected_commit
    )

    partial_dir = (
        output_root
        / f".{expected_commit}.partial"
    )

    if final_dir.exists():
        raise Stage2WrapperError(
            "final Stage 2 execution directory already exists"
        )

    if partial_dir.exists():
        raise Stage2WrapperError(
            "partial Stage 2 execution directory already exists"
        )

    partial_dir.mkdir()

    evidence_rows = tuple(
        sorted(
            (
                *bundle.input_evidence_rows,
                stage1.evidence_row(
                    "stage2-handoff",
                    "",
                    "stage1_source_truth_decisions",
                    stage1_decisions_path,
                ),
                stage1.evidence_row(
                    "stage2-handoff",
                    "",
                    "fresh_download_manifest",
                    fresh_manifest_path,
                ),
            ),
            key=lambda row: (
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

    input_manifest_path = (
        partial_dir
        / "stage2-input-evidence-manifest.tsv"
    )

    input_manifest_sha = (
        stage1.write_tsv_atomic(
            input_manifest_path,
            stage1.INPUT_EVIDENCE_FIELDS,
            evidence_rows,
        )
    )

    predecision_path = (
        partial_dir
        / "stage2-predecision-provenance.json"
    )

    predecision = {
        "schema_version":
            1,
        "status":
            "STAGE2_PREDECISION_FROZEN",
        "bacselect_git_commit":
            expected_commit,
        "frozen_repo_sha256":
            dict(
                sorted(
                    frozen_repo_sha256.items()
                )
            ),
        "stage1_decisions_sha256":
            EXPECTED_STAGE1_DECISIONS_SHA256,
        "stage1_candidate_count":
            len(
                decisions.all_accessions
            ),
        "stage1_membership_sha256":
            decisions.all_membership_sha256,
        "stage2_input_candidate_count":
            len(
                decisions.suitable_source_sha256
            ),
        "stage2_input_membership_sha256":
            decisions.suitable_membership_sha256,
        "cache_reuse_manifest_sha256":
            EXPECTED_CACHE_MANIFEST_SHA256,
        "fresh_download_manifest_sha256":
            EXPECTED_FRESH_MANIFEST_SHA256,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "fingerprints_generated":
            False,
        "repeated_biosample_decisions_generated":
            False,
        "chromosome_integrity_generated":
            False,
        "taxonomy_resolution_generated":
            False,
        "complete_universe_generated":
            False,
        "holdout_membership_generated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    predecision_sha = (
        stage1.write_json_atomic(
            predecision_path,
            predecision,
        )
    )

    # No Stage 2 fingerprint may be generated before the
    # predecision provenance above exists on disk.
    verified = fingerprint_population(
        bundle=bundle,
        decisions=decisions,
        biosamples=biosamples,
    )

    stage2_decisions = (
        reconcile_verified_candidates(
            verified
        )
    )

    if set(
        stage2_decisions
    ) != {
        record.accession
        for record in verified
    }:
        raise Stage2WrapperError(
            "Stage 2 reconciliation did not classify every candidate"
        )

    group_rows, group_counts = (
        build_group_rows(
            verified,
            stage2_decisions,
        )
    )

    decision_rows: list[
        dict[str, str]
    ] = []

    status_counts = Counter()
    reason_counts = Counter()

    allowed_statuses = {
        BIOSAMPLE_CONTINUE,
        BIOSAMPLE_NONREPRESENTATIVE,
        BIOSAMPLE_UNRESOLVED,
    }

    verified_by_accession = {
        record.accession:
            record
        for record in verified
    }

    for accession in sorted(
        stage2_decisions
    ):
        decision = (
            stage2_decisions[
                accession
            ]
        )

        if decision.status not in (
            allowed_statuses
        ):
            raise Stage2WrapperError(
                "unexpected Stage 2 reconciliation status"
            )

        if not decision.reason:
            raise Stage2WrapperError(
                "empty Stage 2 reconciliation reason"
            )

        record = (
            verified_by_accession[
                accession
            ]
        )

        status_counts[
            decision.status
        ] += 1

        reason_counts[
            decision.reason
        ] += 1

        decision_rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "biosample":
                    record.biosample,
                "source_evidence_sha256":
                    record.source_evidence_sha256,
                "assembly_fingerprint":
                    record.assembly_fingerprint,
                "stage2_status":
                    decision.status,
                "stage2_reason":
                    decision.reason,
            }
        )

    if sum(
        status_counts.values()
    ) != len(
        decisions.suitable_source_sha256
    ):
        raise Stage2WrapperError(
            "Stage 2 candidate status accounting mismatch"
        )

    decisions_path = (
        partial_dir
        / "stage2-repeated-biosample-decisions.tsv"
    )

    decisions_sha = (
        stage1.write_tsv_atomic(
            decisions_path,
            STAGE2_DECISION_FIELDS,
            decision_rows,
        )
    )

    groups_path = (
        partial_dir
        / "stage2-biosample-groups.tsv"
    )

    groups_sha = (
        stage1.write_tsv_atomic(
            groups_path,
            STAGE2_GROUP_FIELDS,
            group_rows,
        )
    )

    execution_provenance_path = (
        partial_dir
        / "stage2-execution-provenance.json"
    )

    execution_provenance = {
        "schema_version":
            1,
        "status":
            "STAGE2_REPEATED_BIOSAMPLE_COMPLETE",
        "bacselect_git_commit":
            expected_commit,
        "predecision_provenance_sha256":
            predecision_sha,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "candidate_decisions_sha256":
            decisions_sha,
        "biosample_groups_sha256":
            groups_sha,
        "candidate_count":
            len(
                decision_rows
            ),
        "stage2_input_membership_sha256":
            decisions.suitable_membership_sha256,
        "chromosome_integrity_generated":
            False,
        "taxonomy_resolution_generated":
            False,
        "complete_universe_generated":
            False,
        "holdout_membership_generated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    execution_provenance_sha = (
        stage1.write_json_atomic(
            execution_provenance_path,
            execution_provenance,
        )
    )

    summary_path = (
        partial_dir
        / "stage2-aggregate-summary.json"
    )

    summary = {
        "schema_version":
            1,
        "status":
            "STAGE2_REPEATED_BIOSAMPLE_COMPLETE",
        "stage2_input_candidate_count":
            len(
                decision_rows
            ),
        "stage2_input_membership_sha256":
            decisions.suitable_membership_sha256,
        "biosample_group_count":
            group_counts[
                "all"
            ],
        "singleton_group_count":
            group_counts[
                "singleton"
            ],
        "repeated_group_count":
            group_counts[
                "repeated"
            ],
        "identical_repeated_group_count":
            group_counts[
                "identical_repeated"
            ],
        "differing_repeated_group_count":
            group_counts[
                "differing_repeated"
            ],
        "status_counts":
            dict(
                sorted(
                    status_counts.items()
                )
            ),
        "reason_counts":
            dict(
                sorted(
                    reason_counts.items()
                )
            ),
        "candidate_decisions_sha256":
            decisions_sha,
        "biosample_groups_sha256":
            groups_sha,
        "predecision_provenance_sha256":
            predecision_sha,
        "execution_provenance_sha256":
            execution_provenance_sha,
        "input_evidence_manifest_sha256":
            input_manifest_sha,
        "chromosome_integrity_generated":
            False,
        "taxonomy_resolution_generated":
            False,
        "complete_universe_generated":
            False,
        "holdout_membership_generated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    summary_sha = (
        stage1.write_json_atomic(
            summary_path,
            summary,
        )
    )

    content_paths = (
        input_manifest_path,
        predecision_path,
        decisions_path,
        groups_path,
        execution_provenance_path,
        summary_path,
    )

    content_rows = tuple(
        {
            "path":
                path.name,
            "size_bytes":
                str(
                    path.stat().st_size
                ),
            "sha256":
                stage1.sha256_file(
                    path
                ),
        }
        for path in sorted(
            content_paths,
            key=lambda item:
                item.name,
        )
    )

    content_manifest_path = (
        partial_dir
        / "stage2-content-manifest.tsv"
    )

    content_manifest_sha = (
        stage1.write_tsv_atomic(
            content_manifest_path,
            CONTENT_MANIFEST_FIELDS,
            content_rows,
        )
    )

    if final_dir.exists():
        raise Stage2WrapperError(
            "final Stage 2 directory appeared before finalization"
        )

    os.replace(
        partial_dir,
        final_dir,
    )

    print(
        "PASS | Stage 2 repeated-BioSample execution complete"
    )
    print(
        "stage2_input_candidate_count="
        f"{len(decision_rows)}"
    )
    print(
        "stage2_input_membership_sha256="
        f"{decisions.suitable_membership_sha256}"
    )
    print(
        "biosample_group_count="
        f"{group_counts['all']}"
    )
    print(
        "singleton_group_count="
        f"{group_counts['singleton']}"
    )
    print(
        "repeated_group_count="
        f"{group_counts['repeated']}"
    )
    print(
        "identical_repeated_group_count="
        f"{group_counts['identical_repeated']}"
    )
    print(
        "differing_repeated_group_count="
        f"{group_counts['differing_repeated']}"
    )
    print(
        f"candidate_decisions_sha256={decisions_sha}"
    )
    print(
        f"biosample_groups_sha256={groups_sha}"
    )
    print(
        f"predecision_provenance_sha256={predecision_sha}"
    )
    print(
        f"execution_provenance_sha256={execution_provenance_sha}"
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
            "Stage 2 repeated-BioSample reconciliation."
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
        "--fresh-download-manifest",
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
        "--stage1-decisions",
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

    stage1 = load_stage1_wrapper(
        repo
    )

    frozen_repo_sha256 = (
        stage1.preflight_repository(
            repo,
            args.expected_commit,
            frozen_files=(
                FROZEN_REPO_FILES
            ),
        )
    )

    decisions = load_stage1_decisions(
        args.stage1_decisions,
        stage1=stage1,
    )

    bundle = reconstruct_stage1_population(
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

    biosamples = load_biosample_mapping(
        cache_manifest_path=(
            args.cache_reuse_manifest
        ),
        fresh_manifest_path=(
            args.fresh_download_manifest
        ),
        stage1=stage1,
    )

    verify_stage2_population_binding(
        bundle=bundle,
        decisions=decisions,
        biosamples=biosamples,
    )

    print(
        "PASS | Stage 1 population reconstructed and rebound"
    )
    print(
        "stage1_candidate_count="
        f"{len(decisions.all_accessions)}"
    )
    print(
        "stage2_input_candidate_count="
        f"{len(decisions.suitable_source_sha256)}"
    )
    print(
        "stage2_input_membership_sha256="
        f"{decisions.suitable_membership_sha256}"
    )

    execute_to_scratch(
        repo=repo,
        expected_commit=(
            args.expected_commit
        ),
        output_root=(
            args.output_root
        ),
        stage1=stage1,
        bundle=bundle,
        decisions=decisions,
        biosamples=biosamples,
        frozen_repo_sha256=(
            frozen_repo_sha256
        ),
        stage1_decisions_path=(
            args.stage1_decisions
        ),
        fresh_manifest_path=(
            args.fresh_download_manifest
        ),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
