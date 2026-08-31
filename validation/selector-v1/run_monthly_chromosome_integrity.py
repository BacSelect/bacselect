#!/usr/bin/env python3
"""Execute BacSelect monthly chromosome-component integrity.

Production monthly sequence provenance is BacSelect monthly provenance.
It is not historical Project Finch package provenance.

Accordingly, every monthly candidate is evaluated with explicit
HistoricalReuseEvidence declaring that it does not use the historical
Project Finch package. Historical adjudication is never imported into this
portable monthly executor.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
from types import ModuleType

from bacselect import monthly_biosample_reconciliation
from bacselect import monthly_chromosome_integrity
from bacselect import source_chromosome_integrity
from bacselect import source_chromosome_integrity_execution
from bacselect import source_post_sequence_eligibility
from bacselect import source_repeated_biosample_execution
from bacselect import source_truth


STAGE_NAME = "chromosome-integrity"
PARTIAL_NAME = "chromosome-integrity.partial"
MATERIALIZATION_NAME = (
    "chromosome-integrity-materialization.partial"
)

DECISIONS_NAME = (
    "chromosome-integrity-decisions.tsv"
)
RECORD_NAME = (
    "monthly-chromosome-integrity-record.json"
)

COMPLETION_NAME = (
    "chromosome-integrity-completion.json"
)
COMPLETION_TEMP_NAME = (
    ".chromosome-integrity-completion.json.tmp"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-chromosome-integrity-completion-v1"
)
COMPLETION_STATUS = (
    "CHROMOSOME_INTEGRITY_EXECUTION_COMPLETE"
)

STAGE5_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_biosample_reconciliation.py"
)

EXPECTED_STAGE5_WRAPPER_SHA256 = (
    "0787b77f2e0e734a0ec164fd9c020fd51fd8237355ae48c45e5c225666b9ee95"
)

FROZEN_DEPENDENCIES = {
    Path(
        "src/bacselect/monthly_chromosome_integrity.py"
    ):
        (
            "2ad69041143e10f19501406aac59bee4"
            "c071f2e2139a2ad2641ba54c1395a749"
        ),
    Path(
        "src/bacselect/monthly_biosample_reconciliation.py"
    ):
        (
            "af9f769ec03e838bc7322dc16a3daf7"
            "e45bab0be5d4db0bb6dfd0ff9c53e5446"
        ),
    Path(
        "src/bacselect/source_chromosome_integrity.py"
    ):
        (
            "04f1b580ec9480a20f3679b7eb996da0"
            "8a074c48ff246549df2e0ed20b97b9c0"
        ),
    Path(
        "src/bacselect/source_chromosome_integrity_execution.py"
    ):
        (
            "187816b76ae804ad2e682e036a5fb765"
            "28ac1762d6535062a566edd2fe6e4b9c"
        ),
    Path(
        "src/bacselect/source_repeated_biosample_execution.py"
    ):
        (
            "ee95fac744d1daf413742b39e9b7d8b5"
            "d4d65c52edce08dc0df2dc1ff776a222"
        ),
}

_RELEASE_RE = re.compile(
    r"^[0-9]{4}\.[0-9]{2}$"
)


class MonthlyChromosomeExecutionError(
    RuntimeError
):
    """Raised when portable monthly Stage 6 execution fails closed."""


@dataclass(
    frozen=True
)
class Stage5Context:
    release_id: str
    source_snapshot_id: str
    execution_commit: str

    stage4_context: object
    population: object
    build: object

    decisions_payload: bytes
    decision_rows: tuple[
        Mapping[
            str,
            str,
        ],
        ...
    ]

    record_payload: bytes

    completion_payload: bytes
    completion_record: Mapping[
        str,
        object,
    ]


@dataclass(
    frozen=True
)
class PackageFileObservation:
    path: Path
    sha256: str
    size_bytes: int


@dataclass(
    frozen=True
)
class AuthoritativePackageObservation:
    sha256: str
    size_bytes: int


@dataclass(
    frozen=True
)
class MonthlyChromosomeExecutionResult:
    release_id: str
    source_snapshot_id: str
    stage_path: Path
    decisions_sha256: str
    record_sha256: str
    completion_path: Path

    decision_count: int
    pass_count: int
    excluded_count: int
    unresolved_count: int
    triggered_count: int


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def _canonical_json(
    payload: Mapping[
        str,
        object,
    ],
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def _require_repository(
    path: Path,
) -> Path:
    root = Path(
        path
    ).resolve()

    if (
        root.is_symlink()
        or not root.is_dir()
    ):
        raise MonthlyChromosomeExecutionError(
            "repository root is not a real directory"
        )

    return root


def _load_module(
    path: Path,
    *,
    module_name: str,
    expected_sha256: str,
) -> ModuleType:
    file_path = Path(
        path
    )

    if (
        file_path.is_symlink()
        or not file_path.is_file()
    ):
        raise MonthlyChromosomeExecutionError(
            f"frozen module missing: {file_path}"
        )

    observed = sha256_file(
        file_path
    )

    if observed != expected_sha256:
        raise MonthlyChromosomeExecutionError(
            f"frozen module SHA256 mismatch: {file_path}"
        )

    spec = importlib.util.spec_from_file_location(
        module_name,
        file_path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise MonthlyChromosomeExecutionError(
            f"cannot load frozen module: {file_path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        module_name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


def verify_frozen_dependencies(
    repo: Path,
) -> None:
    for relative, expected in (
        FROZEN_DEPENDENCIES.items()
    ):
        path = (
            repo
            / relative
        )

        if (
            path.is_symlink()
            or not path.is_file()
        ):
            raise MonthlyChromosomeExecutionError(
                f"frozen dependency missing: {relative}"
            )

        observed = sha256_file(
            path
        )

        if observed != expected:
            raise MonthlyChromosomeExecutionError(
                "frozen dependency SHA256 mismatch: "
                f"{relative}"
            )


def load_frozen_stage5_execution(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo
        / STAGE5_WRAPPER_RELATIVE,
        module_name=(
            "_bacselect_frozen_monthly_"
            "biosample_reconciliation_execution"
        ),
        expected_sha256=(
            EXPECTED_STAGE5_WRAPPER_SHA256
        ),
    )


def _count_status(
    rows: Sequence[
        Mapping[
            str,
            str,
        ]
    ],
    status: str,
) -> int:
    return sum(
        row[
            "biosample_status"
        ]
        == status
        for row in rows
    )


def load_stage5_context(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    authoritative_root: Path,
    execution_commit: str,
    stage5_execution,
    stage4_execution,
    cache_execution,
    catalogue_execution,
) -> Stage5Context:
    """Rebuild and authenticate Stage 5 from Stage 4 and frozen contracts."""

    try:
        stage4 = (
            stage5_execution
            .load_stage4_context(
                repo=repo,
                production_root=(
                    production_root
                ),
                stage1_root=(
                    stage1_root
                ),
                authoritative_root=(
                    authoritative_root
                ),
                execution_commit=(
                    execution_commit
                ),
                stage4_execution=(
                    stage4_execution
                ),
                cache_execution=(
                    cache_execution
                ),
                catalogue_execution=(
                    catalogue_execution
                ),
            )
        )
    except Exception as exc:
        raise MonthlyChromosomeExecutionError(
            "Stage 4 context authentication failed"
        ) from exc

    stage = (
        stage1_root
        / stage5_execution.STAGE_NAME
    )

    try:
        stage5_execution._require_real_directory(
            stage,
            label="canonical Stage 5 stage",
        )

        stage5_execution._require_exact_inventory(
            stage,
            expected_files={
                stage5_execution.DECISIONS_NAME,
                stage5_execution.RECORD_NAME,
            },
            label="canonical Stage 5 stage",
        )

        decisions_path = (
            stage
            / stage5_execution.DECISIONS_NAME
        )

        record_path = (
            stage
            / stage5_execution.RECORD_NAME
        )

        completion_path = (
            stage1_root
            / stage5_execution.COMPLETION_NAME
        )

        decisions = (
            stage5_execution
            ._require_regular_file(
                decisions_path,
                label="Stage 5 decisions",
            )
            .read_bytes()
        )

        record = (
            stage5_execution
            ._require_regular_file(
                record_path,
                label="Stage 5 record",
            )
            .read_bytes()
        )

        completion = (
            stage5_execution
            ._require_regular_file(
                completion_path,
                label="Stage 5 completion",
            )
            .read_bytes()
        )
    except Exception as exc:
        raise MonthlyChromosomeExecutionError(
            "Stage 5 artifact loading failed"
        ) from exc

    try:
        population = (
            monthly_biosample_reconciliation
            .build_monthly_biosample_population(
                stage4.decisions_payload,
                expected_source_truth_decisions_sha256=(
                    stage4.completion_record[
                        "decisions_sha256"
                    ]
                ),
                current_metadata=(
                    stage4
                    .metadata_context
                    .retained_metadata
                ),
                release_id=(
                    stage4.release_id
                ),
                source_snapshot_id=(
                    stage4.source_snapshot_id
                ),
                origin_git_commit=(
                    execution_commit
                ),
            )
        )

        decision_rows = (
            monthly_biosample_reconciliation
            .audit_monthly_biosample_decisions(
                decisions
            )
        )

        fingerprints = tuple(
            source_repeated_biosample_execution
            .VerifiedBioSampleFingerprint(
                accession=(
                    row[
                        "canonical_genbank_assembly_accession"
                    ]
                ),
                biosample=(
                    row[
                        "biosample"
                    ]
                ),
                source_evidence_sha256=(
                    row[
                        "source_evidence_sha256"
                    ]
                ),
                assembly_fingerprint=(
                    row[
                        "assembly_fingerprint"
                    ]
                ),
            )
            for row in decision_rows
        )

        if tuple(
            value.accession
            for value in fingerprints
        ) != population.suitable_accessions:
            raise MonthlyChromosomeExecutionError(
                "Stage 5 decision membership differs "
                "from reconstructed Stage 4 SUITABLE population"
            )

        build = (
            monthly_biosample_reconciliation
            .build_monthly_biosample_reconciliation(
                population,
                fingerprints,
            )
        )

        expected_decisions = (
            monthly_biosample_reconciliation
            .serialize_monthly_biosample_decisions(
                build
            )
        )

        if decisions != expected_decisions:
            raise MonthlyChromosomeExecutionError(
                "Stage 5 decision bytes differ from "
                "reconstructed frozen Stage 5 contract"
            )

        expected_record = (
            monthly_biosample_reconciliation
            .serialize_monthly_biosample_record(
                build,
                source_truth_record_sha256=(
                    hashlib.sha256(
                        stage4.record_payload
                    ).hexdigest()
                ),
                source_truth_completion_sha256=(
                    hashlib.sha256(
                        stage4.completion_payload
                    ).hexdigest()
                ),
            )
        )

        if record != expected_record:
            raise MonthlyChromosomeExecutionError(
                "Stage 5 record bytes differ from "
                "reconstructed frozen Stage 5 contract"
            )

        monthly_biosample_reconciliation.audit_monthly_biosample_record(
            record,
            source_truth_decisions_payload=(
                stage4.decisions_payload
            ),
            expected_source_truth_decisions_sha256=(
                stage4.completion_record[
                    "decisions_sha256"
                ]
            ),
            current_metadata=(
                stage4
                .metadata_context
                .retained_metadata
            ),
            release_id=(
                stage4.release_id
            ),
            source_snapshot_id=(
                stage4.source_snapshot_id
            ),
            origin_git_commit=(
                execution_commit
            ),
            source_truth_record_sha256=(
                hashlib.sha256(
                    stage4.record_payload
                ).hexdigest()
            ),
            source_truth_completion_sha256=(
                hashlib.sha256(
                    stage4.completion_payload
                ).hexdigest()
            ),
            decisions_payload=(
                decisions
            ),
        )
    except MonthlyChromosomeExecutionError:
        raise
    except Exception as exc:
        raise MonthlyChromosomeExecutionError(
            "Stage 5 frozen contract reconstruction failed"
        ) from exc

    continue_count = _count_status(
        decision_rows,
        source_post_sequence_eligibility
        .BIOSAMPLE_CONTINUE,
    )

    nonrepresentative_count = _count_status(
        decision_rows,
        source_post_sequence_eligibility
        .BIOSAMPLE_NONREPRESENTATIVE,
    )

    unresolved_count = _count_status(
        decision_rows,
        source_post_sequence_eligibility
        .BIOSAMPLE_UNRESOLVED,
    )

    decisions_sha = hashlib.sha256(
        decisions
    ).hexdigest()

    record_sha = hashlib.sha256(
        record
    ).hexdigest()

    completion_kwargs = {
        "release_id":
            stage4.release_id,
        "source_snapshot_id":
            stage4.source_snapshot_id,
        "source_snapshot_record_sha256":
            stage4
            .metadata_context
            .source_snapshot_record_sha256,
        "execution_commit":
            execution_commit,
        "metadata_record_sha256":
            stage4
            .metadata_context
            .metadata_record_sha256,
        "metadata_completion_sha256":
            stage4
            .metadata_context
            .metadata_completion_sha256,
        "catalogue_chain_count":
            len(
                stage4.catalogue_chain
            ),
        "catalogue_chain_sha256_value":
            stage4.catalogue_chain_sha256,
        "sequence_cache_catalogue_sha256":
            stage4.catalogue_sha256,
        "sequence_cache_entries_sha256":
            stage4.catalogue_record[
                "entries_sha256"
            ],
        "source_truth_completion_sha256":
            hashlib.sha256(
                stage4.completion_payload
            ).hexdigest(),
        "source_truth_decisions_sha256":
            hashlib.sha256(
                stage4.decisions_payload
            ).hexdigest(),
        "source_truth_record_sha256":
            hashlib.sha256(
                stage4.record_payload
            ).hexdigest(),
        "suitable_count":
            len(
                population.suitable_accessions
            ),
        "suitable_accessions_sha256":
            population.suitable_accessions_sha256,
        "decision_count":
            len(
                build.decision_rows
            ),
        "continue_count":
            continue_count,
        "nonrepresentative_count":
            nonrepresentative_count,
        "unresolved_count":
            unresolved_count,
        "group_count":
            build.group_count,
        "singleton_group_count":
            build.singleton_group_count,
        "repeated_group_count":
            build.repeated_group_count,
        "identical_repeated_group_count":
            build.identical_repeated_group_count,
        "differing_repeated_group_count":
            build.differing_repeated_group_count,
        "decisions_sha256":
            decisions_sha,
        "record_sha256":
            record_sha,
    }

    try:
        expected_completion = (
            stage5_execution
            .build_completion_receipt(
                **completion_kwargs
            )
        )

        if completion != expected_completion:
            raise MonthlyChromosomeExecutionError(
                "Stage 5 completion differs from "
                "reconstructed Stage 5 evidence"
            )

        completion_record = (
            stage5_execution
            .audit_completion_receipt(
                completion,
                **completion_kwargs,
            )
        )
    except MonthlyChromosomeExecutionError:
        raise
    except Exception as exc:
        raise MonthlyChromosomeExecutionError(
            "Stage 5 completion authentication failed"
        ) from exc

    return Stage5Context(
        release_id=(
            stage4.release_id
        ),
        source_snapshot_id=(
            stage4.source_snapshot_id
        ),
        execution_commit=(
            execution_commit
        ),
        stage4_context=(
            stage4
        ),
        population=(
            population
        ),
        build=(
            build
        ),
        decisions_payload=(
            decisions
        ),
        decision_rows=tuple(
            decision_rows
        ),
        record_payload=(
            record
        ),
        completion_payload=(
            completion
        ),
        completion_record=(
            completion_record
        ),
    )


def stage5_identity(
    context: Stage5Context,
    *,
    stage5_execution,
    cache_execution,
) -> tuple[
    object,
    ...
]:
    return (
        stage5_execution._stage4_identity(
            context.stage4_context,
            cache_execution,
        ),
        hashlib.sha256(
            context.decisions_payload
        ).hexdigest(),
        hashlib.sha256(
            context.record_payload
        ).hexdigest(),
        hashlib.sha256(
            context.completion_payload
        ).hexdigest(),
    )


def monthly_historical_provider(
    accession: str,
) -> source_chromosome_integrity.HistoricalReuseEvidence:
    """Explicitly mark BacSelect monthly packages as non-Project-Finch."""

    if (
        not isinstance(
            accession,
            str,
        )
        or not accession
    ):
        raise MonthlyChromosomeExecutionError(
            "monthly historical provider received invalid accession"
        )

    return (
        source_chromosome_integrity
        .HistoricalReuseEvidence(
            uses_historical_project_finch_package=False,
            cache_content_verification=None,
            adjudication_accession=None,
            adjudication_outcome=None,
        )
    )


def _package_row_identity(
    row: Mapping[
        str,
        str,
    ],
    *,
    stage5_execution,
) -> tuple[
    str,
    int,
    str,
]:
    path = row[
        "path"
    ]

    relative = PurePosixPath(
        path
    )

    if (
        relative.is_absolute()
        or ".." in relative.parts
    ):
        raise MonthlyChromosomeExecutionError(
            "candidate package path is unsafe"
        )

    try:
        size = int(
            row[
                "size_bytes"
            ]
        )
    except ValueError as exc:
        raise MonthlyChromosomeExecutionError(
            "candidate package size is invalid"
        ) from exc

    if size < 0:
        raise MonthlyChromosomeExecutionError(
            "candidate package size is negative"
        )

    sha = (
        stage5_execution
        .validate_sha256(
            row[
                "sha256"
            ],
            label="candidate package SHA256",
        )
    )

    return (
        path,
        size,
        sha,
    )


def observe_current_package(
    *,
    batch_dir: Path,
    bridge,
    stage5_execution,
) -> tuple[
    PackageFileObservation,
    ...
]:
    observations = []

    for row in bridge.package_rows:
        path, size, sha = (
            _package_row_identity(
                row,
                stage5_execution=(
                    stage5_execution
                ),
            )
        )

        try:
            resolved = (
                stage5_execution
                .resolve_manifest_path(
                    batch_dir,
                    path,
                )
            )
        except Exception as exc:
            raise MonthlyChromosomeExecutionError(
                f"{bridge.accession} current package "
                "path resolution failed"
            ) from exc

        try:
            file_path = (
                stage5_execution
                ._require_regular_file(
                    resolved,
                    label=(
                        f"{bridge.accession} "
                        "current package file"
                    ),
                )
            )
        except Exception as exc:
            raise MonthlyChromosomeExecutionError(
                f"{bridge.accession} current package "
                "file is unsafe"
            ) from exc

        if (
            file_path.stat().st_size
            != size
            or sha256_file(
                file_path
            )
            != sha
        ):
            raise MonthlyChromosomeExecutionError(
                f"{bridge.accession} current package "
                "identity differs from authenticated manifest"
            )

        observations.append(
            PackageFileObservation(
                path=file_path,
                sha256=sha,
                size_bytes=size,
            )
        )

    if len(
        observations
    ) != len(
        bridge.package_rows
    ):
        raise MonthlyChromosomeExecutionError(
            "current package observation count changed"
        )

    return tuple(
        observations
    )


def materialize_prior_package(
    *,
    cache_execution,
    authoritative_root: Path,
    materialization_root: Path,
    bridge,
    stage5_execution,
) -> tuple[
    Path,
    tuple[
        AuthoritativePackageObservation,
        ...
    ],
]:
    candidate_root = (
        materialization_root
        / bridge.accession
    )

    if os.path.lexists(
        candidate_root
    ):
        raise MonthlyChromosomeExecutionError(
            "candidate materialization path already exists"
        )

    candidate_root.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    package_root = (
        candidate_root
        / "package"
    )

    package_root.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    observations = []

    try:
        for row in sorted(
            bridge.package_rows,
            key=lambda item:
                item[
                    "path"
                ],
        ):
            path, size, sha = (
                _package_row_identity(
                    row,
                    stage5_execution=(
                        stage5_execution
                    ),
                )
            )

            relative = PurePosixPath(
                path
            )

            prefix = (
                "ncbi_dataset",
                "data",
                bridge.accession,
            )

            if (
                len(
                    relative.parts
                )
                <= 3
                or relative.parts[
                    :3
                ]
                != prefix
            ):
                raise MonthlyChromosomeExecutionError(
                    "prior package row is not "
                    "accession scoped"
                )

            try:
                required = (
                    cache_execution
                    .read_required_object(
                        authoritative_root,
                        sha256=sha,
                        expected_size_bytes=size,
                        label=(
                            f"{bridge.accession} "
                            "authoritative package file"
                        ),
                    )
                )
            except Exception as exc:
                raise MonthlyChromosomeExecutionError(
                    f"{bridge.accession} authoritative "
                    "package object failed verification"
                ) from exc

            destination = (
                package_root
                / Path(
                    *relative.parts
                )
            )

            destination.parent.mkdir(
                mode=0o755,
                parents=True,
                exist_ok=True,
            )

            try:
                stage5_execution.write_no_clobber(
                    destination,
                    required.payload,
                )
            except Exception as exc:
                raise MonthlyChromosomeExecutionError(
                    f"{bridge.accession} prior package "
                    "materialization failed"
                ) from exc

            if (
                destination.stat().st_size
                != size
                or sha256_file(
                    destination
                )
                != sha
            ):
                raise MonthlyChromosomeExecutionError(
                    "materialized prior package identity changed"
                )

            observations.append(
                AuthoritativePackageObservation(
                    sha256=sha,
                    size_bytes=size,
                )
            )

        if len(
            observations
        ) != len(
            bridge.package_rows
        ):
            raise MonthlyChromosomeExecutionError(
                "prior package materialization is incomplete"
            )

        return (
            candidate_root,
            tuple(
                observations
            ),
        )

    except Exception:
        if (
            candidate_root.exists()
            and not candidate_root.is_symlink()
            and candidate_root.is_dir()
        ):
            shutil.rmtree(
                candidate_root
            )

        raise


def evaluate_population(
    *,
    context: Stage5Context,
    stage1_root: Path,
    authoritative_root: Path,
    materialization_root: Path,
    population,
    stage5_execution,
    stage4_execution,
    cache_execution,
    catalogue_execution,
) -> tuple[
    tuple[
        source_chromosome_integrity_execution
        .Stage3CandidateEvaluation,
        ...
    ],
    tuple[
        PackageFileObservation,
        ...
    ],
    tuple[
        AuthoritativePackageObservation,
        ...
    ],
    tuple[
        object,
        ...
    ],
    tuple[
        object,
        ...
    ],
]:
    """Reconstruct authenticated monthly packages and run frozen science."""

    evaluations = []

    local_observations = []
    authoritative_observations = []
    current_batch_observations = []
    prior_batch_observations = []

    current_batches = {}
    prior_batches = {}

    stage4 = (
        context.stage4_context
    )

    sequence_root_name = getattr(
        catalogue_execution,
        "SEQUENCE_ROOT_NAME",
        "sequence-acquisition",
    )

    for accession in (
        population.continue_accessions
    ):
        entry = (
            stage4.entries_by_accession.get(
                accession
            )
        )

        if entry is None:
            raise MonthlyChromosomeExecutionError(
                "Stage 6 candidate lacks current catalogue entry"
            )

        provenance_sha = (
            stage5_execution
            .validate_sha256(
                entry.get(
                    "origin_batch_provenance_sha256"
                ),
                label="origin batch-provenance SHA256",
            )
        )

        provenance = (
            stage4
            .provenance_by_sha
            .get(
                provenance_sha
            )
        )

        if provenance is None:
            raise MonthlyChromosomeExecutionError(
                "Stage 6 candidate provenance is missing"
            )

        origin_class = (
            stage5_execution
            .classify_origin_release(
                provenance.get(
                    "cache_origin_release_id"
                ),
                current_release_id=(
                    context.release_id
                ),
            )
        )

        if origin_class == "CURRENT":
            if provenance_sha not in (
                current_batches
            ):
                try:
                    current_batches[
                        provenance_sha
                    ] = (
                        stage4_execution
                        ._current_batch_evidence(
                            cache_execution=(
                                cache_execution
                            ),
                            completion_context=(
                                stage4
                                .completion_context
                            ),
                            provenance=(
                                provenance
                            ),
                            expected_commit=(
                                context.execution_commit
                            ),
                        )
                    )

                    current_batch_observations.append(
                        stage5_execution
                        .CurrentBatchObservation(
                            provenance=(
                                provenance
                            ),
                            batch=(
                                current_batches[
                                    provenance_sha
                                ]
                            ),
                        )
                    )
                except Exception as exc:
                    raise MonthlyChromosomeExecutionError(
                        "current-origin batch evidence "
                        "authentication failed"
                    ) from exc

            batch = (
                current_batches[
                    provenance_sha
                ]
            )

        else:
            if provenance_sha not in (
                prior_batches
            ):
                try:
                    prior_batches[
                        provenance_sha
                    ] = (
                        cache_execution
                        .load_batch_evidence(
                            authoritative_root,
                            provenance=(
                                provenance
                            ),
                        )
                    )

                    prior_batch_observations.append(
                        stage5_execution
                        .PriorBatchObservation(
                            provenance=(
                                provenance
                            ),
                            batch=(
                                prior_batches[
                                    provenance_sha
                                ]
                            ),
                        )
                    )
                except Exception as exc:
                    raise MonthlyChromosomeExecutionError(
                        "prior-origin batch evidence "
                        "authentication failed"
                    ) from exc

            batch = (
                prior_batches[
                    provenance_sha
                ]
            )

        try:
            bridge = (
                stage4_execution
                .validate_candidate_bridge(
                    cache_execution,
                    entry=entry,
                    batch=batch,
                )
            )
        except Exception as exc:
            raise MonthlyChromosomeExecutionError(
                f"{accession} candidate bridge audit failed"
            ) from exc

        if bridge.accession != accession:
            raise MonthlyChromosomeExecutionError(
                "candidate bridge accession changed"
            )

        expected_source_sha = (
            population
            .source_evidence_sha256_by_accession[
                accession
            ]
        )

        source_row = (
            stage4
            .decision_by_accession
            .get(
                accession
            )
        )

        if (
            source_row is None
            or source_row[
                "source_truth_status"
            ]
            != source_truth.SUITABLE
            or source_row[
                "source_evidence_sha256"
            ]
            != expected_source_sha
        ):
            raise MonthlyChromosomeExecutionError(
                "Stage 6 candidate differs from "
                "authenticated Stage 4 source truth"
            )

        candidate_root = None

        try:
            if origin_class == "CURRENT":
                batch_id = str(
                    provenance.get(
                        "batch_id",
                        "",
                    )
                )

                batch_dir = (
                    stage1_root
                    / sequence_root_name
                    / batch_id
                )

                try:
                    stage5_execution._require_real_directory(
                        batch_dir,
                        label=(
                            f"current sequence batch {batch_id}"
                        ),
                    )
                except Exception as exc:
                    raise MonthlyChromosomeExecutionError(
                        "current sequence batch is unsafe"
                    ) from exc

                current_files = (
                    observe_current_package(
                        batch_dir=(
                            batch_dir
                        ),
                        bridge=bridge,
                        stage5_execution=(
                            stage5_execution
                        ),
                    )
                )

                local_observations.extend(
                    current_files
                )

                audit_path = (
                    batch_dir
                    / "candidate-sequence-audit.tsv"
                )

            else:
                (
                    candidate_root,
                    prior_objects,
                ) = (
                    materialize_prior_package(
                        cache_execution=(
                            cache_execution
                        ),
                        authoritative_root=(
                            authoritative_root
                        ),
                        materialization_root=(
                            materialization_root
                        ),
                        bridge=bridge,
                        stage5_execution=(
                            stage5_execution
                        ),
                    )
                )

                authoritative_observations.extend(
                    prior_objects
                )

                audit_path = (
                    candidate_root
                    / "candidate-sequence-audit.tsv"
                )

            try:
                (
                    candidate,
                    components,
                    package_manifest,
                ) = (
                    stage4_execution
                    ._source_truth_objects(
                        bridge,
                        audit_path=(
                            audit_path
                        ),
                    )
                )
            except Exception as exc:
                raise MonthlyChromosomeExecutionError(
                    f"{accession} source-evidence "
                    "object reconstruction failed"
                ) from exc

            try:
                evaluated = (
                    source_chromosome_integrity_execution
                    .evaluate_stage3_candidate(
                        candidate=candidate,
                        component_rows=(
                            components
                        ),
                        package_manifest=(
                            package_manifest
                        ),
                        expected_source_evidence_sha256=(
                            expected_source_sha
                        ),
                        historical_provider=(
                            monthly_historical_provider
                        ),
                    )
                )
            except Exception as exc:
                raise MonthlyChromosomeExecutionError(
                    f"{accession} frozen chromosome "
                    "evaluation failed"
                ) from exc

            if (
                evaluated.accession
                != accession
                or evaluated.source_evidence_sha256
                != expected_source_sha
            ):
                raise MonthlyChromosomeExecutionError(
                    "frozen chromosome evaluation "
                    "identity changed"
                )

            evaluations.append(
                evaluated
            )

        finally:
            if candidate_root is not None:
                if (
                    candidate_root.is_symlink()
                    or not candidate_root.is_dir()
                ):
                    raise MonthlyChromosomeExecutionError(
                        "candidate materialization path "
                        "became unsafe"
                    )

                shutil.rmtree(
                    candidate_root
                )

    if tuple(
        value.accession
        for value in evaluations
    ) != population.continue_accessions:
        raise MonthlyChromosomeExecutionError(
            "chromosome evaluation population "
            "differs from Stage 5 CONTINUE population"
        )

    return (
        tuple(
            evaluations
        ),
        tuple(
            local_observations
        ),
        tuple(
            authoritative_observations
        ),
        tuple(
            current_batch_observations
        ),
        tuple(
            prior_batch_observations
        ),
    )


def verify_package_observations(
    *,
    stage5_execution,
    stage4_execution,
    cache_execution,
    current_completion_context,
    execution_commit: str,
    authoritative_root: Path,
    local_observations: Sequence[
        PackageFileObservation
    ],
    authoritative_observations: Sequence[
        AuthoritativePackageObservation
    ],
    current_batch_observations: Sequence[
        object
    ],
    prior_batch_observations: Sequence[
        object
    ],
) -> None:
    """Reauthenticate all package bytes and batch evidence before publication."""

    for observation in local_observations:
        try:
            path = (
                stage5_execution
                ._require_regular_file(
                    observation.path,
                    label=(
                        "observed current package file"
                    ),
                )
            )
        except Exception as exc:
            raise MonthlyChromosomeExecutionError(
                "current package file changed "
                "during Stage 6 execution"
            ) from exc

        if (
            path.stat().st_size
            != observation.size_bytes
            or sha256_file(
                path
            )
            != observation.sha256
        ):
            raise MonthlyChromosomeExecutionError(
                "current package file changed "
                "during Stage 6 execution"
            )

    for observation in (
        authoritative_observations
    ):
        try:
            cache_execution.read_required_object(
                authoritative_root,
                sha256=(
                    observation.sha256
                ),
                expected_size_bytes=(
                    observation.size_bytes
                ),
                label=(
                    "observed authoritative package object"
                ),
            )
        except Exception as exc:
            raise MonthlyChromosomeExecutionError(
                "authoritative package object changed "
                "during Stage 6 execution"
            ) from exc

    for observation in (
        current_batch_observations
    ):
        try:
            observed = (
                stage4_execution
                ._current_batch_evidence(
                    cache_execution=(
                        cache_execution
                    ),
                    completion_context=(
                        current_completion_context
                    ),
                    provenance=(
                        observation.provenance
                    ),
                    expected_commit=(
                        execution_commit
                    ),
                )
            )
        except Exception as exc:
            raise MonthlyChromosomeExecutionError(
                "current batch evidence changed "
                "during Stage 6 execution"
            ) from exc

        expected = (
            observation.batch
        )

        if (
            observed.provenance
            != expected.provenance
            or observed.candidate_rows
            != expected.candidate_rows
            or observed.component_rows
            != expected.component_rows
            or observed.package_rows
            != expected.package_rows
        ):
            raise MonthlyChromosomeExecutionError(
                "current batch evidence changed "
                "during Stage 6 execution"
            )

    for observation in (
        prior_batch_observations
    ):
        try:
            observed = (
                cache_execution
                .load_batch_evidence(
                    authoritative_root,
                    provenance=(
                        observation.provenance
                    ),
                )
            )
        except Exception as exc:
            raise MonthlyChromosomeExecutionError(
                "prior batch evidence changed "
                "during Stage 6 execution"
            ) from exc

        expected = (
            observation.batch
        )

        if (
            observed.provenance
            != expected.provenance
            or observed.candidate_rows
            != expected.candidate_rows
            or observed.component_rows
            != expected.component_rows
            or observed.package_rows
            != expected.package_rows
        ):
            raise MonthlyChromosomeExecutionError(
                "prior batch evidence changed "
                "during Stage 6 execution"
            )


def _release_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _RELEASE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyChromosomeExecutionError(
            "release_id must use YYYY.MM"
        )

    return value


def build_completion_receipt(
    *,
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    biosample_decisions_sha256: str,
    biosample_record_sha256: str,
    biosample_completion_sha256: str,
    continue_count: int,
    continue_accessions_sha256: str,
    decision_count: int,
    triggered_candidate_count: int,
    nontriggered_candidate_count: int,
    historical_adjudication_reuse_count: int,
    pass_count: int,
    excluded_count: int,
    unresolved_count: int,
    decisions_sha256: str,
    record_sha256: str,
    stage5_execution,
) -> bytes:
    release = _release_id(
        release_id
    )

    if (
        not isinstance(
            source_snapshot_id,
            str,
        )
        or not source_snapshot_id
        or source_snapshot_id.strip()
        != source_snapshot_id
    ):
        raise MonthlyChromosomeExecutionError(
            "source_snapshot_id is invalid"
        )

    commit = (
        stage5_execution
        .validate_commit(
            execution_commit
        )
    )

    counts = {
        "continue_count":
            stage5_execution.validate_count(
                continue_count,
                label="continue count",
            ),
        "decision_count":
            stage5_execution.validate_count(
                decision_count,
                label="decision count",
            ),
        "triggered_candidate_count":
            stage5_execution.validate_count(
                triggered_candidate_count,
                label="triggered candidate count",
            ),
        "nontriggered_candidate_count":
            stage5_execution.validate_count(
                nontriggered_candidate_count,
                label="nontriggered candidate count",
            ),
        "historical_adjudication_reuse_count":
            stage5_execution.validate_count(
                historical_adjudication_reuse_count,
                label="historical adjudication reuse count",
            ),
        "pass_count":
            stage5_execution.validate_count(
                pass_count,
                label="PASS count",
            ),
        "excluded_count":
            stage5_execution.validate_count(
                excluded_count,
                label="excluded count",
            ),
        "unresolved_count":
            stage5_execution.validate_count(
                unresolved_count,
                label="unresolved count",
            ),
    }

    if (
        counts[
            "continue_count"
        ]
        != counts[
            "decision_count"
        ]
    ):
        raise MonthlyChromosomeExecutionError(
            "completion population accounting changed"
        )

    if (
        counts[
            "triggered_candidate_count"
        ]
        + counts[
            "nontriggered_candidate_count"
        ]
        != counts[
            "decision_count"
        ]
    ):
        raise MonthlyChromosomeExecutionError(
            "completion trigger accounting changed"
        )

    if (
        counts[
            "pass_count"
        ]
        + counts[
            "excluded_count"
        ]
        + counts[
            "unresolved_count"
        ]
        != counts[
            "decision_count"
        ]
    ):
        raise MonthlyChromosomeExecutionError(
            "completion status accounting changed"
        )

    if (
        counts[
            "historical_adjudication_reuse_count"
        ]
        > counts[
            "triggered_candidate_count"
        ]
    ):
        raise MonthlyChromosomeExecutionError(
            "completion historical-reuse accounting changed"
        )

    if counts[
        "historical_adjudication_reuse_count"
    ] != 0:
        raise MonthlyChromosomeExecutionError(
            "monthly production must not reuse "
            "Project Finch adjudication"
        )

    payload = {
        "schema_version":
            COMPLETION_SCHEMA,
        "status":
            COMPLETION_STATUS,
        "release_id":
            release,
        "source_snapshot_id":
            source_snapshot_id,
        "execution_commit":
            commit,
        "biosample_decisions_sha256":
            stage5_execution.validate_sha256(
                biosample_decisions_sha256,
                label="Stage 5 decisions SHA256",
            ),
        "biosample_record_sha256":
            stage5_execution.validate_sha256(
                biosample_record_sha256,
                label="Stage 5 record SHA256",
            ),
        "biosample_completion_sha256":
            stage5_execution.validate_sha256(
                biosample_completion_sha256,
                label="Stage 5 completion SHA256",
            ),
        "continue_accessions_sha256":
            stage5_execution.validate_sha256(
                continue_accessions_sha256,
                label="CONTINUE membership SHA256",
            ),
        "decisions_sha256":
            stage5_execution.validate_sha256(
                decisions_sha256,
                label="chromosome decisions SHA256",
            ),
        "record_sha256":
            stage5_execution.validate_sha256(
                record_sha256,
                label="chromosome record SHA256",
            ),
        **counts,
    }

    return _canonical_json(
        payload
    )


def audit_completion_receipt(
    payload: bytes,
    **kwargs,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise MonthlyChromosomeExecutionError(
            "completion receipt must be bytes"
        )

    expected = (
        build_completion_receipt(
            **kwargs
        )
    )

    if payload != expected:
        raise MonthlyChromosomeExecutionError(
            "chromosome completion receipt changed"
        )

    try:
        record = json.loads(
            payload
        )
    except json.JSONDecodeError as exc:
        raise MonthlyChromosomeExecutionError(
            "chromosome completion receipt is invalid JSON"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise MonthlyChromosomeExecutionError(
            "chromosome completion receipt must be an object"
        )

    if record.get(
        "schema_version"
    ) != COMPLETION_SCHEMA:
        raise MonthlyChromosomeExecutionError(
            "chromosome completion schema changed"
        )

    if record.get(
        "status"
    ) != COMPLETION_STATUS:
        raise MonthlyChromosomeExecutionError(
            "chromosome completion status changed"
        )

    return record


def _link_no_clobber(
    source: Path,
    destination: Path,
) -> None:
    if os.path.lexists(
        destination
    ):
        raise MonthlyChromosomeExecutionError(
            f"publication target already exists: {destination.name}"
        )

    try:
        os.link(
            source,
            destination,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise MonthlyChromosomeExecutionError(
            f"hard-link publication failed: {destination.name}"
        ) from exc


def _remove_owned_hard_link(
    *,
    source: Path,
    destination: Path,
    label: str,
) -> None:
    """Remove only a hard link demonstrably created from source."""

    if not os.path.lexists(
        destination
    ):
        return

    if (
        destination.is_symlink()
        or not destination.is_file()
    ):
        raise MonthlyChromosomeExecutionError(
            f"{label} cleanup target is unsafe"
        )

    try:
        source_stat = source.stat()
        destination_stat = (
            destination.stat()
        )
    except OSError as exc:
        raise MonthlyChromosomeExecutionError(
            f"{label} cleanup identity check failed"
        ) from exc

    if (
        source_stat.st_dev
        != destination_stat.st_dev
        or source_stat.st_ino
        != destination_stat.st_ino
    ):
        raise MonthlyChromosomeExecutionError(
            f"{label} cleanup target is not "
            "the created hard link"
        )

    try:
        destination.unlink()
    except OSError as exc:
        raise MonthlyChromosomeExecutionError(
            f"{label} cleanup unlink failed"
        ) from exc


def _remove_owned_file(
    *,
    path: Path,
    device: int,
    inode: int,
    label: str,
) -> None:
    """Remove one executor-created file only if its identity is unchanged."""

    if not os.path.lexists(
        path
    ):
        return

    if (
        path.is_symlink()
        or not path.is_file()
    ):
        raise MonthlyChromosomeExecutionError(
            f"{label} cleanup target is unsafe"
        )

    try:
        observed = path.stat()
    except OSError as exc:
        raise MonthlyChromosomeExecutionError(
            f"{label} cleanup identity check failed"
        ) from exc

    if (
        observed.st_dev != device
        or observed.st_ino != inode
    ):
        raise MonthlyChromosomeExecutionError(
            f"{label} cleanup target identity changed"
        )

    try:
        path.unlink()
    except OSError as exc:
        raise MonthlyChromosomeExecutionError(
            f"{label} cleanup unlink failed"
        ) from exc


def publish_stage(
    *,
    stage1_root: Path,
    partial: Path,
    final: Path,
    expected_decisions: bytes,
    expected_record: bytes,
    auditor: Callable[
        [
            bytes,
            bytes,
        ],
        object,
    ],
    stability_check: Callable[
        [],
        None,
    ],
    stage5_execution,
) -> None:
    if os.path.lexists(
        final
    ):
        raise MonthlyChromosomeExecutionError(
            "canonical chromosome stage already exists"
        )

    stage5_execution._require_real_directory(
        partial,
        label="partial chromosome stage",
    )

    stage5_execution._require_exact_inventory(
        partial,
        expected_files={
            DECISIONS_NAME,
            RECORD_NAME,
        },
        label="partial chromosome stage",
    )

    decisions_source = (
        stage5_execution
        ._require_regular_file(
            partial
            / DECISIONS_NAME,
            label="partial chromosome decisions",
        )
    )

    record_source = (
        stage5_execution
        ._require_regular_file(
            partial
            / RECORD_NAME,
            label="partial chromosome record",
        )
    )

    if (
        decisions_source.read_bytes()
        != expected_decisions
        or record_source.read_bytes()
        != expected_record
    ):
        raise MonthlyChromosomeExecutionError(
            "partial chromosome stage readback changed"
        )

    auditor(
        expected_decisions,
        expected_record,
    )

    stability_check()

    final.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    decisions_destination = (
        final
        / DECISIONS_NAME
    )

    record_destination = (
        final
        / RECORD_NAME
    )

    decisions_linked = False
    record_linked = False

    try:
        _link_no_clobber(
            decisions_source,
            decisions_destination,
        )

        decisions_linked = True

        _link_no_clobber(
            record_source,
            record_destination,
        )

        record_linked = True

        stage5_execution.fsync_directory(
            final
        )

        observed_decisions = (
            stage5_execution
            ._require_regular_file(
                decisions_destination,
                label="published chromosome decisions",
            )
            .read_bytes()
        )

        observed_record = (
            stage5_execution
            ._require_regular_file(
                record_destination,
                label="published chromosome record",
            )
            .read_bytes()
        )

        if (
            observed_decisions
            != expected_decisions
            or observed_record
            != expected_record
        ):
            raise MonthlyChromosomeExecutionError(
                "published chromosome stage readback changed"
            )

        auditor(
            observed_decisions,
            observed_record,
        )

        stability_check()

    except Exception as exc:
        cleanup_errors = []

        if record_linked:
            try:
                _remove_owned_hard_link(
                    source=record_source,
                    destination=(
                        record_destination
                    ),
                    label=(
                        "published chromosome record"
                    ),
                )
            except Exception as cleanup_exc:
                cleanup_errors.append(
                    cleanup_exc
                )

        if decisions_linked:
            try:
                _remove_owned_hard_link(
                    source=decisions_source,
                    destination=(
                        decisions_destination
                    ),
                    label=(
                        "published chromosome decisions"
                    ),
                )
            except Exception as cleanup_exc:
                cleanup_errors.append(
                    cleanup_exc
                )

        if os.path.lexists(
            final
        ):
            try:
                if (
                    final.is_symlink()
                    or not final.is_dir()
                ):
                    raise MonthlyChromosomeExecutionError(
                        "canonical chromosome stage "
                        "cleanup target is unsafe"
                    )

                final.rmdir()

            except Exception as cleanup_exc:
                cleanup_errors.append(
                    cleanup_exc
                )

        try:
            stage5_execution.fsync_directory(
                stage1_root
            )
        except Exception as cleanup_exc:
            cleanup_errors.append(
                cleanup_exc
            )

        if cleanup_errors:
            raise MonthlyChromosomeExecutionError(
                "chromosome stage publication failed "
                "and cleanup was incomplete"
            ) from exc

        raise

    decisions_source.unlink()
    record_source.unlink()
    partial.rmdir()

    stage5_execution.fsync_directory(
        stage1_root
    )


def publish_completion(
    *,
    stage1_root: Path,
    payload: bytes,
    auditor: Callable[
        [
            bytes,
        ],
        object,
    ],
    stability_check: Callable[
        [],
        None,
    ],
    stage5_execution,
) -> Path:
    final = (
        stage1_root
        / COMPLETION_NAME
    )

    temporary = (
        stage1_root
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlyChromosomeExecutionError(
            "chromosome completion already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlyChromosomeExecutionError(
            "chromosome completion temporary artifact already exists"
        )

    stage5_execution.write_no_clobber(
        temporary,
        payload,
    )

    stage5_execution.fsync_directory(
        stage1_root
    )

    temporary_file = (
        stage5_execution
        ._require_regular_file(
            temporary,
            label="temporary chromosome completion",
        )
    )

    temporary_stat = (
        temporary_file.stat()
    )

    final_linked = False

    try:
        temporary_payload = (
            temporary_file.read_bytes()
        )

        if temporary_payload != payload:
            raise MonthlyChromosomeExecutionError(
                "temporary chromosome completion readback changed"
            )

        auditor(
            temporary_payload
        )

        stability_check()

        _link_no_clobber(
            temporary,
            final,
        )

        final_linked = True

        stage5_execution.fsync_directory(
            stage1_root
        )

        final_payload = (
            stage5_execution
            ._require_regular_file(
                final,
                label="published chromosome completion",
            )
            .read_bytes()
        )

        if final_payload != payload:
            raise MonthlyChromosomeExecutionError(
                "published chromosome completion readback changed"
            )

        auditor(
            final_payload
        )

        stability_check()

    except Exception as exc:
        cleanup_errors = []

        if final_linked:
            try:
                _remove_owned_hard_link(
                    source=temporary,
                    destination=final,
                    label=(
                        "published chromosome completion"
                    ),
                )
            except Exception as cleanup_exc:
                cleanup_errors.append(
                    cleanup_exc
                )

        if not os.path.lexists(
            final
        ):
            try:
                _remove_owned_file(
                    path=temporary,
                    device=(
                        temporary_stat.st_dev
                    ),
                    inode=(
                        temporary_stat.st_ino
                    ),
                    label=(
                        "temporary chromosome completion"
                    ),
                )
            except Exception as cleanup_exc:
                cleanup_errors.append(
                    cleanup_exc
                )

        try:
            stage5_execution.fsync_directory(
                stage1_root
            )
        except Exception as cleanup_exc:
            cleanup_errors.append(
                cleanup_exc
            )

        if cleanup_errors:
            raise MonthlyChromosomeExecutionError(
                "chromosome completion publication "
                "failed and cleanup was incomplete"
            ) from exc

        raise

    temporary.unlink()

    stage5_execution.fsync_directory(
        stage1_root
    )

    return final


def execute_monthly_chromosome_integrity(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    authoritative_root: Path,
    execution_commit: str,
) -> MonthlyChromosomeExecutionResult:
    root = _require_repository(
        repo
    )

    verify_frozen_dependencies(
        root
    )

    stage5_execution = (
        load_frozen_stage5_execution(
            root
        )
    )

    try:
        production = (
            stage5_execution
            ._require_real_directory(
                Path(
                    production_root
                ),
                label="production root",
            )
        )

        stage1 = (
            stage5_execution
            ._require_real_directory(
                Path(
                    stage1_root
                ),
                label="Stage 1 root",
            )
            .resolve()
        )

        authoritative = (
            stage5_execution
            ._require_real_directory(
                Path(
                    authoritative_root
                ),
                label="authoritative root",
            )
            .resolve()
        )

        commit = (
            stage5_execution
            .validate_commit(
                execution_commit
            )
        )
    except Exception as exc:
        raise MonthlyChromosomeExecutionError(
            "Stage 6 execution input validation failed"
        ) from exc

    stage4_execution = (
        stage5_execution
        .load_frozen_stage4_execution(
            root
        )
    )

    cache_execution = (
        stage5_execution
        .load_frozen_cache_execution(
            root
        )
    )

    catalogue_execution = (
        stage5_execution
        .load_frozen_catalogue_execution(
            root
        )
    )

    context = load_stage5_context(
        repo=root,
        production_root=production,
        stage1_root=stage1,
        authoritative_root=authoritative,
        execution_commit=commit,
        stage5_execution=(
            stage5_execution
        ),
        stage4_execution=(
            stage4_execution
        ),
        cache_execution=(
            cache_execution
        ),
        catalogue_execution=(
            catalogue_execution
        ),
    )

    final = (
        stage1
        / STAGE_NAME
    )

    partial = (
        stage1
        / PARTIAL_NAME
    )

    materialization = (
        stage1
        / MATERIALIZATION_NAME
    )

    completion = (
        stage1
        / COMPLETION_NAME
    )

    completion_temp = (
        stage1
        / COMPLETION_TEMP_NAME
    )

    for path, label in (
        (
            final,
            "canonical chromosome stage",
        ),
        (
            partial,
            "partial chromosome stage",
        ),
        (
            materialization,
            "chromosome materialization",
        ),
        (
            completion,
            "chromosome completion",
        ),
        (
            completion_temp,
            "chromosome completion temporary artifact",
        ),
    ):
        if os.path.lexists(
            path
        ):
            raise MonthlyChromosomeExecutionError(
                f"{label} already exists"
            )

    try:
        population = (
            monthly_chromosome_integrity
            .build_monthly_chromosome_population(
                context.decisions_payload,
                expected_biosample_decisions_sha256=(
                    context.completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                origin_git_commit=(
                    commit
                ),
            )
        )
    except Exception as exc:
        raise MonthlyChromosomeExecutionError(
            "pure Stage 6 population construction failed"
        ) from exc

    materialization.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    try:
        (
            evaluations,
            local_observations,
            authoritative_observations,
            current_batch_observations,
            prior_batch_observations,
        ) = evaluate_population(
            context=context,
            stage1_root=stage1,
            authoritative_root=authoritative,
            materialization_root=materialization,
            population=population,
            stage5_execution=(
                stage5_execution
            ),
            stage4_execution=(
                stage4_execution
            ),
            cache_execution=(
                cache_execution
            ),
            catalogue_execution=(
                catalogue_execution
            ),
        )

        if any(
            materialization.iterdir()
        ):
            raise MonthlyChromosomeExecutionError(
                "Stage 6 materialization root is not empty"
            )

    finally:
        if (
            materialization.exists()
            and not materialization.is_symlink()
            and materialization.is_dir()
        ):
            shutil.rmtree(
                materialization
            )

    try:
        build = (
            monthly_chromosome_integrity
            .build_monthly_chromosome_integrity(
                population,
                evaluations,
            )
        )

        if (
            build
            .historical_adjudication_reuse_count
            != 0
        ):
            raise MonthlyChromosomeExecutionError(
                "monthly production unexpectedly "
                "reused historical adjudication"
            )

        decisions_payload = (
            monthly_chromosome_integrity
            .serialize_monthly_chromosome_decisions(
                build
            )
        )

        record_payload = (
            monthly_chromosome_integrity
            .serialize_monthly_chromosome_record(
                build,
                biosample_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                biosample_completion_sha256=(
                    hashlib.sha256(
                        context.completion_payload
                    ).hexdigest()
                ),
            )
        )

        monthly_chromosome_integrity.audit_monthly_chromosome_decisions(
            decisions_payload
        )

        record = (
            monthly_chromosome_integrity
            .audit_monthly_chromosome_record(
                record_payload,
                biosample_decisions_payload=(
                    context.decisions_payload
                ),
                expected_biosample_decisions_sha256=(
                    context.completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                origin_git_commit=(
                    commit
                ),
                biosample_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                biosample_completion_sha256=(
                    hashlib.sha256(
                        context.completion_payload
                    ).hexdigest()
                ),
                decisions_payload=(
                    decisions_payload
                ),
            )
        )
    except MonthlyChromosomeExecutionError:
        raise
    except Exception as exc:
        raise MonthlyChromosomeExecutionError(
            "pure monthly Stage 6 contract failed"
        ) from exc

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    try:
        stage5_execution.write_no_clobber(
            partial
            / DECISIONS_NAME,
            decisions_payload,
        )

        stage5_execution.write_no_clobber(
            partial
            / RECORD_NAME,
            record_payload,
        )

        stage5_execution.fsync_directory(
            partial
        )
    except Exception as exc:
        raise MonthlyChromosomeExecutionError(
            "Stage 6 partial artifact write failed"
        ) from exc

    initial_identity = stage5_identity(
        context,
        stage5_execution=(
            stage5_execution
        ),
        cache_execution=(
            cache_execution
        ),
    )

    def stability_check() -> None:
        observed = load_stage5_context(
            repo=root,
            production_root=(
                production
            ),
            stage1_root=(
                stage1
            ),
            authoritative_root=(
                authoritative
            ),
            execution_commit=(
                commit
            ),
            stage5_execution=(
                stage5_execution
            ),
            stage4_execution=(
                stage4_execution
            ),
            cache_execution=(
                cache_execution
            ),
            catalogue_execution=(
                catalogue_execution
            ),
        )

        if stage5_identity(
            observed,
            stage5_execution=(
                stage5_execution
            ),
            cache_execution=(
                cache_execution
            ),
        ) != initial_identity:
            raise MonthlyChromosomeExecutionError(
                "Stage 5 evidence changed during Stage 6 publication"
            )

        verify_package_observations(
            stage5_execution=(
                stage5_execution
            ),
            stage4_execution=(
                stage4_execution
            ),
            cache_execution=(
                cache_execution
            ),
            current_completion_context=(
                observed
                .stage4_context
                .completion_context
            ),
            execution_commit=(
                commit
            ),
            authoritative_root=(
                authoritative
            ),
            local_observations=(
                local_observations
            ),
            authoritative_observations=(
                authoritative_observations
            ),
            current_batch_observations=(
                current_batch_observations
            ),
            prior_batch_observations=(
                prior_batch_observations
            ),
        )

    def stage_auditor(
        observed_decisions: bytes,
        observed_record: bytes,
    ) -> object:
        monthly_chromosome_integrity.audit_monthly_chromosome_decisions(
            observed_decisions
        )

        return (
            monthly_chromosome_integrity
            .audit_monthly_chromosome_record(
                observed_record,
                biosample_decisions_payload=(
                    context.decisions_payload
                ),
                expected_biosample_decisions_sha256=(
                    context.completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                origin_git_commit=(
                    commit
                ),
                biosample_record_sha256=(
                    hashlib.sha256(
                        context.record_payload
                    ).hexdigest()
                ),
                biosample_completion_sha256=(
                    hashlib.sha256(
                        context.completion_payload
                    ).hexdigest()
                ),
                decisions_payload=(
                    observed_decisions
                ),
            )
        )

    publish_stage(
        stage1_root=(
            stage1
        ),
        partial=(
            partial
        ),
        final=(
            final
        ),
        expected_decisions=(
            decisions_payload
        ),
        expected_record=(
            record_payload
        ),
        auditor=(
            stage_auditor
        ),
        stability_check=(
            stability_check
        ),
        stage5_execution=(
            stage5_execution
        ),
    )

    pass_count = int(
        build.status_counts.get(
            source_chromosome_integrity.PASS,
            0,
        )
    )

    excluded_count = int(
        build.status_counts.get(
            source_chromosome_integrity.EXCLUDE,
            0,
        )
    )

    unresolved_count = int(
        build.status_counts.get(
            source_chromosome_integrity.UNRESOLVED,
            0,
        )
    )

    decisions_sha = hashlib.sha256(
        decisions_payload
    ).hexdigest()

    record_sha = hashlib.sha256(
        record_payload
    ).hexdigest()

    completion_kwargs = {
        "release_id":
            context.release_id,
        "source_snapshot_id":
            context.source_snapshot_id,
        "execution_commit":
            commit,
        "biosample_decisions_sha256":
            hashlib.sha256(
                context.decisions_payload
            ).hexdigest(),
        "biosample_record_sha256":
            hashlib.sha256(
                context.record_payload
            ).hexdigest(),
        "biosample_completion_sha256":
            hashlib.sha256(
                context.completion_payload
            ).hexdigest(),
        "continue_count":
            len(
                population.continue_accessions
            ),
        "continue_accessions_sha256":
            population.continue_accessions_sha256,
        "decision_count":
            len(
                build.decision_rows
            ),
        "triggered_candidate_count":
            build.triggered_candidate_count,
        "nontriggered_candidate_count":
            build.nontriggered_candidate_count,
        "historical_adjudication_reuse_count":
            build.historical_adjudication_reuse_count,
        "pass_count":
            pass_count,
        "excluded_count":
            excluded_count,
        "unresolved_count":
            unresolved_count,
        "decisions_sha256":
            decisions_sha,
        "record_sha256":
            record_sha,
        "stage5_execution":
            stage5_execution,
    }

    completion_payload = build_completion_receipt(
        **completion_kwargs
    )

    completion_path = publish_completion(
        stage1_root=(
            stage1
        ),
        payload=(
            completion_payload
        ),
        auditor=lambda payload:
            audit_completion_receipt(
                payload,
                **completion_kwargs,
            ),
        stability_check=(
            stability_check
        ),
        stage5_execution=(
            stage5_execution
        ),
    )

    return MonthlyChromosomeExecutionResult(
        release_id=(
            context.release_id
        ),
        source_snapshot_id=(
            context.source_snapshot_id
        ),
        stage_path=(
            final
        ),
        decisions_sha256=(
            decisions_sha
        ),
        record_sha256=(
            record_sha
        ),
        completion_path=(
            completion_path
        ),
        decision_count=len(
            build.decision_rows
        ),
        pass_count=(
            pass_count
        ),
        excluded_count=(
            excluded_count
        ),
        unresolved_count=(
            unresolved_count
        ),
        triggered_count=(
            build.triggered_candidate_count
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute BacSelect portable monthly "
            "chromosome-component integrity."
        )
    )

    parser.add_argument(
        "--repo",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--production-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--stage1-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--authoritative-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--execution-commit",
        required=True,
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.authorize_real_execution:
        raise SystemExit(
            "production chromosome-integrity execution "
            "requires explicit authorization"
        )

    result = execute_monthly_chromosome_integrity(
        repo=args.repo,
        production_root=(
            args.production_root
        ),
        stage1_root=(
            args.stage1_root
        ),
        authoritative_root=(
            args.authoritative_root
        ),
        execution_commit=(
            args.execution_commit
        ),
    )

    print(
        "PASS | BacSelect monthly "
        "chromosome integrity complete"
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        f"source_snapshot_id="
        f"{result.source_snapshot_id}"
    )

    print(
        f"decision_count="
        f"{result.decision_count}"
    )

    print(
        f"pass_count="
        f"{result.pass_count}"
    )

    print(
        f"excluded_count="
        f"{result.excluded_count}"
    )

    print(
        f"unresolved_count="
        f"{result.unresolved_count}"
    )

    print(
        f"triggered_count="
        f"{result.triggered_count}"
    )

    print(
        "decisions_sha256="
        f"{result.decisions_sha256}"
    )

    print(
        "record_sha256="
        f"{result.record_sha256}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
