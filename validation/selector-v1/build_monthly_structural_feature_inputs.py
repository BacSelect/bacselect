#!/usr/bin/env python3
"""Build authenticated monthly Stage 10 structural-feature inputs.

This adapter performs no Stage 10 publication.

It binds:

* the closed monthly Stage 9 universe;
* exact current component identities;
* the two frozen structural-feature cache authorities; and
* the exact candidate packages requiring fresh structural-feature execution.

For September 2026 the authenticated Stage 4-v2 catalogue is GENESIS-only,
therefore every current candidate is provided by the current release.  Both
ordinary ``fresh`` and accepted ``fresh-recovery`` providers are supported.

Fresh structural-feature calculation is exposed as a separate function so
planning and cache/partition validation can be completed without compiling or
running the repeat engine.

No percentile geometry, representative selection, OPS calculation or panel
construction occurs here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import csv
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import ModuleType
from typing import Callable, Iterable, Mapping, Sequence

from bacselect import monthly_cache_verification
from bacselect import monthly_structural_features as monthly
from bacselect import source_structural_feature_execution as feature_execution
from bacselect import source_structural_features
from bacselect.source_truth_execution import (
    load_component_index,
)


# ---------------------------------------------------------------------------
# Frozen code identities
# ---------------------------------------------------------------------------

STAGE10_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_structural_features.py"
)

STAGE6_V2_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_chromosome_integrity_v2.py"
)

STAGE5_V2_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_biosample_reconciliation_v2.py"
)

STAGE4_V2_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_source_truth_v2.py"
)

HISTORICAL_STRUCTURAL_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_structural_feature_execution.py"
)

EXPECTED_STAGE10_WRAPPER_SHA256 = (
    "ebcfd7e9a2548cde1e5adc87e0fda9ea970cdb8b04512ec3fff5e5a9a43c315d"
)

EXPECTED_STAGE6_V2_SHA256 = (
    "df5ba50c5b7f3df2c5a823ddd35d57273b61c4a1e1bc145bb34fc7e23a9b7ec8"
)

EXPECTED_STAGE5_V2_SHA256 = (
    "40d0ec3710e55ae7c1141ad857210c5382148f36fa236418aca306be8e3e6d43"
)

EXPECTED_STAGE4_V2_SHA256 = (
    "3cb27073570ba351089a7e1b0eb0620d2c1c1e8127f52bca3fa8e197e3d8ca91"
)

EXPECTED_HISTORICAL_STRUCTURAL_WRAPPER_SHA256 = (
    "899cf1c4b2aab3d62d187e45e09be308ef91fda6cf734dd0083f8ea3849ac1c2"
)

EXPECTED_ENGINE_BINARY_SHA256 = (
    "e0b5ea3a892aee3f9af80e5676010f1e1145563ca900058485e07d6433988968"
)

EXPECTED_COMPONENT_IDENTITY_MAPPING_SHA256 = (
    "6467e9252d1f3080a7fc6b1d3d11eca6df744c912779d49e81c2867d4b140ec0"
)

EXPECTED_TIER1_FEATURE_VALUES_SHA256 = (
    "ec50bfa51b526f5a8a66102064768cb38cbed931f9e88c92b821514a8b199550"
)

EXPECTED_TIER2_FEATURE_VALUES_SHA256 = (
    "9d703a8a7e28db09120709fd7911afd578bc9c492f31ab35fa17e707494cc507"
)

EXPECTED_TIER2_TAXONOMY_RELABELS = (
    "GCA_052938085.1",
    "GCA_056688935.1",
)

COMPONENT_AUDIT_NAME = (
    "component-sequence-audit.tsv"
)

ALLOWED_CURRENT_SOURCE_GROUPS = frozenset(
    {
        "fresh",
        "fresh-recovery",
    }
)


class MonthlyStructuralFeatureInputError(
    RuntimeError
):
    """Stage 10 input construction failed closed."""


@dataclass(
    frozen=True,
)
class FileObservation:
    path: Path
    sha256: str
    size_bytes: int


@dataclass(
    frozen=True,
)
class MonthlyBatchSpec:
    """Minimum frozen structural-feature BatchSpec interface."""

    source_group: str
    batch: str
    candidate_audit: Path
    component_audit: Path
    package_manifest: Path
    candidates: tuple[
        object,
        ...,
    ]


@dataclass(
    frozen=True,
)
class ProviderState:
    provenance_sha256: str
    provenance: Mapping[
        str,
        object,
    ]
    completion_batch: Mapping[
        str,
        object,
    ]
    provider: object
    source_group: str
    component_audit: Path
    package_manifest: Path
    observations: tuple[
        FileObservation,
        ...,
    ]


@dataclass(
    frozen=True,
)
class Stage10InputPlan:
    stage9: object

    context: object
    stage6_v2: ModuleType
    stage5_v2: ModuleType
    stage4_v2: ModuleType
    stage4_v1: ModuleType

    current_component_identity_by_accession: Mapping[
        str,
        str,
    ]

    tier1_cache: Mapping[
        str,
        monthly.CachedFeatureRow,
    ]

    tier2_cache: Mapping[
        str,
        monthly.CachedFeatureRow,
    ]

    compute_accessions: tuple[
        str,
        ...,
    ]

    providers_by_provenance: Mapping[
        str,
        ProviderState,
    ]

    tier1_raw_rows: Mapping[
        str,
        Mapping[
            str,
            str,
        ],
    ]

    tier2_raw_rows: Mapping[
        str,
        Mapping[
            str,
            str,
        ],
    ]


@dataclass(
    frozen=True,
)
class Stage10ComputedInputs:
    plan: Stage10InputPlan
    computed_rows: Mapping[
        str,
        feature_execution.Stage6FeatureRecord,
    ]
    execution_inputs: object
    build: monthly.MonthlyStructuralFeatureBuild


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        for block in iter(
            lambda:
                handle.read(
                    8
                    * 1024
                    * 1024
                ),
            b"",
        ):
            digest.update(
                block
            )

    return digest.hexdigest()


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    if (
        value.is_symlink()
        or not value.is_file()
    ):
        raise MonthlyStructuralFeatureInputError(
            f"{label} is not a regular file"
        )

    return value


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    if (
        value.is_symlink()
        or not value.is_dir()
    ):
        raise MonthlyStructuralFeatureInputError(
            f"{label} is not a real directory"
        )

    return value


def _load_module(
    repo: Path,
    relative: Path,
    *,
    module_name: str,
    expected_sha256: str,
) -> ModuleType:
    path = _require_regular_file(
        Path(
            repo
        )
        / relative,
        label=module_name,
    )

    if sha256_file(
        path
    ) != expected_sha256:
        raise MonthlyStructuralFeatureInputError(
            f"{module_name} SHA256 changed"
        )

    spec = (
        importlib.util
        .spec_from_file_location(
            module_name,
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise MonthlyStructuralFeatureInputError(
            f"cannot load {module_name}"
        )

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

    return module


def load_stage10_wrapper(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo,
        STAGE10_WRAPPER_RELATIVE,
        module_name=(
            "_bacselect_stage10_execution_contract"
        ),
        expected_sha256=(
            EXPECTED_STAGE10_WRAPPER_SHA256
        ),
    )


def load_stage6_v2(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo,
        STAGE6_V2_RELATIVE,
        module_name=(
            "_bacselect_stage10_stage6_v2"
        ),
        expected_sha256=(
            EXPECTED_STAGE6_V2_SHA256
        ),
    )


def load_stage5_v2(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo,
        STAGE5_V2_RELATIVE,
        module_name=(
            "_bacselect_stage10_stage5_v2"
        ),
        expected_sha256=(
            EXPECTED_STAGE5_V2_SHA256
        ),
    )


def load_stage4_v2(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo,
        STAGE4_V2_RELATIVE,
        module_name=(
            "_bacselect_stage10_stage4_v2"
        ),
        expected_sha256=(
            EXPECTED_STAGE4_V2_SHA256
        ),
    )


def load_historical_structural_wrapper(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo,
        HISTORICAL_STRUCTURAL_WRAPPER_RELATIVE,
        module_name=(
            "_bacselect_stage10_historical_"
            "structural_wrapper"
        ),
        expected_sha256=(
            EXPECTED_HISTORICAL_STRUCTURAL_WRAPPER_SHA256
        ),
    )


# ---------------------------------------------------------------------------
# Component identity
# ---------------------------------------------------------------------------


def component_identity_sha256(
    accession: str,
    components: Sequence[
        object,
    ],
) -> str:
    """Use exactly the frozen monthly component-identity payload semantics."""

    if (
        not isinstance(
            accession,
            str,
        )
        or not accession
    ):
        raise MonthlyStructuralFeatureInputError(
            "component identity accession is invalid"
        )

    rows = []

    for component in sorted(
        components,
        key=lambda item:
            item.component_accession,
    ):
        try:
            component_accession = (
                component
                .component_accession
            )

            length = int(
                component.length
            )

            sequence_sha = (
                component
                .sequence_sha256
            )

            topology = (
                component
                .topology
            )

        except (
            AttributeError,
            TypeError,
            ValueError,
        ) as exc:
            raise MonthlyStructuralFeatureInputError(
                "component identity row is malformed"
            ) from exc

        if (
            not isinstance(
                component_accession,
                str,
            )
            or not component_accession
            or length <= 0
            or not isinstance(
                sequence_sha,
                str,
            )
            or len(
                sequence_sha
            )
            != 64
            or topology
            not in {
                "linear",
                "circular",
            }
        ):
            raise MonthlyStructuralFeatureInputError(
                "component identity row is invalid"
            )

        rows.append(
            {
                "component_genbank_accession":
                    component_accession,
                "length":
                    length,
                "sequence_sha256":
                    sequence_sha,
                "topology":
                    topology,
            }
        )

    if not rows:
        raise MonthlyStructuralFeatureInputError(
            "component identity has no components"
        )

    payload = (
        monthly_cache_verification
        ._canonical_json_bytes(
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "components":
                    rows,
                "schema_version":
                    (
                        "bacselect-monthly-cache-"
                        "component-identity-v1"
                    ),
            }
        )
    )

    return hashlib.sha256(
        payload
    ).hexdigest()


def component_identity_mapping_sha256(
    mapping: Mapping[
        str,
        str,
    ],
) -> str:
    payload = "".join(
        accession
        + "\t"
        + mapping[
            accession
        ]
        + "\n"
        for accession in sorted(
            mapping
        )
    ).encode(
        "ascii"
    )

    return hashlib.sha256(
        payload
    ).hexdigest()


# ---------------------------------------------------------------------------
# Matrix/cache parsing
# ---------------------------------------------------------------------------


def _parse_feature_values(
    row: Mapping[
        str,
        str,
    ],
) -> dict[
    str,
    int | float,
]:
    result = {}

    for field in (
        monthly.FEATURE_FIELDS
    ):
        text = row[
            field
        ]

        if field in (
            monthly
            .INTEGER_FEATURE_FIELDS
        ):
            result[
                field
            ] = int(
                text
            )

        else:
            result[
                field
            ] = float(
                text
            )

    return result


def _read_matrix(
    path: Path,
    *,
    expected_fields: tuple[
        str,
        ...,
    ],
) -> dict[
    str,
    Mapping[
        str,
        str,
    ],
]:
    with _require_regular_file(
        path,
        label="structural-feature matrix",
    ).open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        if tuple(
            reader.fieldnames
            or ()
        ) != expected_fields:
            raise MonthlyStructuralFeatureInputError(
                "structural-feature matrix schema changed"
            )

        rows = list(
            reader
        )

    result = {}

    for row in rows:
        accession = row[
            "canonical_genbank_assembly_accession"
        ]

        if accession in result:
            raise MonthlyStructuralFeatureInputError(
                "duplicate accession in structural-feature matrix"
            )

        result[
            accession
        ] = row

    return result


def build_tier1_cache(
    *,
    matrix_path: Path,
    historical_component_root: Path,
) -> tuple[
    Mapping[
        str,
        monthly.CachedFeatureRow,
    ],
    Mapping[
        str,
        Mapping[
            str,
            str,
        ],
    ],
]:
    raw = _read_matrix(
        matrix_path,
        expected_fields=(
            "batch",
            "batch_index",
            "canonical_genbank_assembly_accession",
            *monthly.FEATURE_FIELDS,
        ),
    )

    if len(
        raw
    ) != 55306:
        raise MonthlyStructuralFeatureInputError(
            "Tier 1 matrix row count changed"
        )

    wanted = set(
        raw
    )

    components_by_accession = {}

    for path in sorted(
        _require_real_directory(
            historical_component_root,
            label=(
                "Tier 1 historical component root"
            ),
        ).glob(
            "batch-*/component-sequence-audit.tsv"
        )
    ):
        index = load_component_index(
            path
        )

        for accession, components in (
            index.items()
        ):
            if accession not in wanted:
                continue

            if accession in (
                components_by_accession
            ):
                raise MonthlyStructuralFeatureInputError(
                    "duplicate Tier 1 component provider"
                )

            components_by_accession[
                accession
            ] = components

    if set(
        components_by_accession
    ) != wanted:
        raise MonthlyStructuralFeatureInputError(
            "Tier 1 component membership changed"
        )

    cache = {
        accession:
            monthly.CachedFeatureRow(
                accession=accession,
                component_identity_sha256=(
                    component_identity_sha256(
                        accession,
                        components_by_accession[
                            accession
                        ],
                    )
                ),
                features=(
                    _parse_feature_values(
                        raw[
                            accession
                        ]
                    )
                ),
            )
        for accession in raw
    }

    return (
        cache,
        raw,
    )


def _read_tsv(
    path: Path,
) -> tuple[
    tuple[
        str,
        ...,
    ],
    list[
        Mapping[
            str,
            str,
        ]
    ],
]:
    with _require_regular_file(
        path,
        label="TSV input",
    ).open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        fields = tuple(
            reader.fieldnames
            or ()
        )

        rows = list(
            reader
        )

    return (
        fields,
        rows,
    )


def resolve_tier2_component_providers(
    *,
    input_manifest_path: Path,
    search_roots: Sequence[
        Path,
    ],
) -> Mapping[
    tuple[
        str,
        str,
    ],
    Path,
]:
    fields, rows = _read_tsv(
        input_manifest_path
    )

    required = {
        "source_group",
        "batch",
        "file_role",
        "file_name",
        "size_bytes",
        "sha256",
    }

    if not required <= set(
        fields
    ):
        raise MonthlyStructuralFeatureInputError(
            "Tier 2 input-manifest schema changed"
        )

    manifest = {}

    for row in rows:
        if Path(
            row[
                "file_name"
            ]
        ).name != (
            COMPONENT_AUDIT_NAME
        ):
            continue

        key = (
            row[
                "source_group"
            ],
            row[
                "batch"
            ],
        )

        if key in manifest:
            raise MonthlyStructuralFeatureInputError(
                "duplicate Tier 2 component manifest row"
            )

        try:
            size = int(
                row[
                    "size_bytes"
                ]
            )
        except ValueError as exc:
            raise MonthlyStructuralFeatureInputError(
                "Tier 2 component size is invalid"
            ) from exc

        manifest[
            key
        ] = (
            size,
            row[
                "sha256"
            ],
        )

    if not manifest:
        raise MonthlyStructuralFeatureInputError(
            "Tier 2 component manifest is empty"
        )

    needed_by_size = defaultdict(
        set
    )

    for size, digest in (
        manifest.values()
    ):
        needed_by_size[
            size
        ].add(
            digest
        )

    provider_by_identity = {}

    for root in search_roots:
        directory = _require_real_directory(
            root,
            label="Tier 2 provider search root",
        )

        for path in directory.rglob(
            COMPONENT_AUDIT_NAME
        ):
            if (
                path.is_symlink()
                or not path.is_file()
            ):
                continue

            size = path.stat().st_size

            wanted = (
                needed_by_size.get(
                    size
                )
            )

            if not wanted:
                continue

            digest = sha256_file(
                path
            )

            if digest not in wanted:
                continue

            provider_by_identity.setdefault(
                (
                    size,
                    digest,
                ),
                path,
            )

    result = {}

    for key, identity in (
        manifest.items()
    ):
        path = (
            provider_by_identity
            .get(
                identity
            )
        )

        if path is None:
            raise MonthlyStructuralFeatureInputError(
                "authenticated Tier 2 component provider is missing"
            )

        result[
            key
        ] = path

    return result


def build_tier2_cache(
    *,
    matrix_path: Path,
    candidate_evidence_path: Path,
    input_manifest_path: Path,
    provider_search_roots: Sequence[
        Path,
    ],
) -> tuple[
    Mapping[
        str,
        monthly.CachedFeatureRow,
    ],
    Mapping[
        str,
        Mapping[
            str,
            str,
        ],
    ],
]:
    raw = _read_matrix(
        matrix_path,
        expected_fields=(
            "canonical_genbank_assembly_accession",
            "species_taxid",
            *monthly.FEATURE_FIELDS,
        ),
    )

    if len(
        raw
    ) != 12952:
        raise MonthlyStructuralFeatureInputError(
            "Tier 2 matrix row count changed"
        )

    fields, candidate_rows = (
        _read_tsv(
            candidate_evidence_path
        )
    )

    required_candidate_fields = {
        "canonical_genbank_assembly_accession",
        "source_group",
        "batch",
        "retained_primary_assembly_replicon_count",
        "total_retained_sequence_length",
        "topology_circular_records",
        "topology_linear_records",
        "feature_record_sha256",
    }

    if not (
        required_candidate_fields
        <= set(
            fields
        )
    ):
        raise MonthlyStructuralFeatureInputError(
            "Tier 2 candidate-evidence schema changed"
        )

    evidence = {}

    for row in candidate_rows:
        accession = row[
            "canonical_genbank_assembly_accession"
        ]

        if accession in evidence:
            raise MonthlyStructuralFeatureInputError(
                "duplicate Tier 2 candidate evidence"
            )

        evidence[
            accession
        ] = row

    if set(
        evidence
    ) != set(
        raw
    ):
        raise MonthlyStructuralFeatureInputError(
            "Tier 2 matrix/evidence membership changed"
        )

    providers = (
        resolve_tier2_component_providers(
            input_manifest_path=(
                input_manifest_path
            ),
            search_roots=(
                provider_search_roots
            ),
        )
    )

    wanted_by_batch = defaultdict(
        set
    )

    for accession, row in (
        evidence.items()
    ):
        wanted_by_batch[
            (
                row[
                    "source_group"
                ],
                row[
                    "batch"
                ],
            )
        ].add(
            accession
        )

    components_by_accession = {}

    for key, wanted in sorted(
        wanted_by_batch.items()
    ):
        path = providers.get(
            key
        )

        if path is None:
            raise MonthlyStructuralFeatureInputError(
                "Tier 2 candidate has no authenticated component provider"
            )

        index = load_component_index(
            path,
            accessions=wanted,
        )

        for accession, components in (
            index.items()
        ):
            if accession in (
                components_by_accession
            ):
                raise MonthlyStructuralFeatureInputError(
                    "duplicate Tier 2 component accession"
                )

            components_by_accession[
                accession
            ] = components

    if set(
        components_by_accession
    ) != set(
        raw
    ):
        raise MonthlyStructuralFeatureInputError(
            "Tier 2 component membership changed"
        )

    for accession, row in (
        evidence.items()
    ):
        components = (
            components_by_accession[
                accession
            ]
        )

        if (
            len(
                components
            )
            != int(
                row[
                    "retained_primary_assembly_replicon_count"
                ]
            )
        ):
            raise MonthlyStructuralFeatureInputError(
                "Tier 2 replicon count differs from component evidence"
            )

        if (
            sum(
                item.length
                for item in components
            )
            != int(
                row[
                    "total_retained_sequence_length"
                ]
            )
        ):
            raise MonthlyStructuralFeatureInputError(
                "Tier 2 sequence length differs from component evidence"
            )

        if (
            sum(
                item.topology
                == "circular"
                for item in components
            )
            != int(
                row[
                    "topology_circular_records"
                ]
            )
        ):
            raise MonthlyStructuralFeatureInputError(
                "Tier 2 circular-topology count changed"
            )

        if (
            sum(
                item.topology
                == "linear"
                for item in components
            )
            != int(
                row[
                    "topology_linear_records"
                ]
            )
        ):
            raise MonthlyStructuralFeatureInputError(
                "Tier 2 linear-topology count changed"
            )

    cache = {
        accession:
            monthly.CachedFeatureRow(
                accession=accession,
                component_identity_sha256=(
                    component_identity_sha256(
                        accession,
                        components_by_accession[
                            accession
                        ],
                    )
                ),
                features=(
                    _parse_feature_values(
                        raw[
                            accession
                        ]
                    )
                ),
            )
        for accession in raw
    }

    return (
        cache,
        raw,
    )


# ---------------------------------------------------------------------------
# Current September provider reconstruction
# ---------------------------------------------------------------------------


def _observation_tuple(
    value: object,
) -> FileObservation:
    try:
        path, digest, size = value
    except Exception as exc:
        raise MonthlyStructuralFeatureInputError(
            "provider observation has unexpected shape"
        ) from exc

    path = _require_regular_file(
        Path(
            path
        ),
        label="provider observation",
    )

    try:
        size_value = int(
            size
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlyStructuralFeatureInputError(
            "provider observation size is invalid"
        ) from exc

    if (
        path.stat().st_size
        != size_value
        or sha256_file(
            path
        )
        != digest
    ):
        raise MonthlyStructuralFeatureInputError(
            "provider observation identity changed"
        )

    return FileObservation(
        path=path,
        sha256=digest,
        size_bytes=size_value,
    )


def reauthenticate_observations(
    observations: Iterable[
        FileObservation,
    ],
) -> None:
    for observation in observations:
        path = _require_regular_file(
            observation.path,
            label="observed provider file",
        )

        if (
            path.stat().st_size
            != observation.size_bytes
            or sha256_file(
                path
            )
            != observation.sha256
        ):
            raise MonthlyStructuralFeatureInputError(
                "provider observation identity changed"
            )


def _provider_package_manifest_path(
    provider,
    completion_batch: Mapping[
        str,
        object,
    ],
) -> Path:
    name = completion_batch.get(
        "package_manifest_name"
    )

    if (
        not isinstance(
            name,
            str,
        )
        or not name
        or Path(
            name
        ).name
        != name
    ):
        raise MonthlyStructuralFeatureInputError(
            "provider package-manifest name is invalid"
        )

    expected = (
        Path(
            provider.provider_root
        )
        / name
    )

    path = _require_regular_file(
        expected,
        label="provider package manifest",
    )

    observed_paths = {
        Path(
            item.path
        ).resolve()
        for item in (
            _observation_tuple(
                value
            )
            for value in (
                provider.observations
            )
        )
    }

    if path.resolve() not in (
        observed_paths
    ):
        raise MonthlyStructuralFeatureInputError(
            "provider package manifest is not authenticated observation"
        )

    return path


def _provider_component_audit_path(
    provider,
) -> Path:
    matches = [
        item
        for item in (
            _observation_tuple(
                value
            )
            for value in (
                provider.observations
            )
        )
        if item.path.name
        == COMPONENT_AUDIT_NAME
    ]

    if len(
        matches
    ) != 1:
        raise MonthlyStructuralFeatureInputError(
            "provider component audit does not resolve uniquely"
        )

    return matches[
        0
    ].path


def build_current_provider_states(
    *,
    stage1_root: Path,
    stage4_context,
    stage4_v2,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    accessions: Sequence[
        str,
    ],
) -> Mapping[
    str,
    ProviderState,
]:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 root",
    )

    result = {}

    for accession in accessions:
        entry = (
            stage4_context
            .entries_by_accession
            .get(
                accession
            )
        )

        if entry is None:
            raise MonthlyStructuralFeatureInputError(
                "Stage 9 accession lacks Stage 4 catalogue entry"
            )

        provenance_sha = entry.get(
            "origin_batch_provenance_sha256"
        )

        if (
            not isinstance(
                provenance_sha,
                str,
            )
            or len(
                provenance_sha
            )
            != 64
        ):
            raise MonthlyStructuralFeatureInputError(
                "current provider provenance SHA256 is invalid"
            )

        if provenance_sha in result:
            continue

        provenance = (
            stage4_context
            .provenance_by_sha
            .get(
                provenance_sha
            )
        )

        if provenance is None:
            raise MonthlyStructuralFeatureInputError(
                "current provider provenance is missing"
            )

        if provenance.get(
            "cache_origin_release_id"
        ) != stage4_context.release_id:
            raise MonthlyStructuralFeatureInputError(
                "September Stage 10 encountered historical-origin provider"
            )

        batch_id = str(
            provenance.get(
                "batch_id",
                "",
            )
        )

        completion_batch = (
            stage4_context
            .completion_by_batch
            .get(
                batch_id
            )
        )

        if completion_batch is None:
            raise MonthlyStructuralFeatureInputError(
                "current provider batch is missing from completion-v2"
            )

        provider = (
            stage4_v2
            ._provider_batch_context_v2(
                stage1_root=stage1,
                cache_execution=(
                    stage4_context
                    .cache_execution
                ),
                provenance=provenance,
                completion_batch=(
                    completion_batch
                ),
                release_id=(
                    stage4_context
                    .release_id
                ),
                source_snapshot_id=(
                    stage4_context
                    .source_snapshot_id
                ),
                source_production_commit=(
                    source_production_commit
                ),
                completion_execution_commit=(
                    completion_execution_commit
                ),
                cache_execution_commit=(
                    cache_execution_commit
                ),
                completion_sha256=(
                    stage4_context
                    .completion_v2_sha256
                ),
            )
        )

        observations = tuple(
            _observation_tuple(
                value
            )
            for value in (
                provider.observations
            )
        )

        source_group = completion_batch.get(
            "source_class"
        )

        if source_group not in (
            ALLOWED_CURRENT_SOURCE_GROUPS
        ):
            raise MonthlyStructuralFeatureInputError(
                "current provider class is not fresh/fresh-recovery"
            )

        component_path = (
            _provider_component_audit_path(
                provider
            )
        )

        package_path = (
            _provider_package_manifest_path(
                provider,
                completion_batch,
            )
        )

        result[
            provenance_sha
        ] = ProviderState(
            provenance_sha256=(
                provenance_sha
            ),
            provenance=provenance,
            completion_batch=(
                completion_batch
            ),
            provider=provider,
            source_group=(
                source_group
            ),
            component_audit=(
                component_path
            ),
            package_manifest=(
                package_path
            ),
            observations=(
                observations
            ),
        )

    return result


def build_current_component_identities(
    *,
    stage4_context,
    providers_by_provenance: Mapping[
        str,
        ProviderState,
    ],
    accessions: Sequence[
        str,
    ],
) -> Mapping[
    str,
    str,
]:
    wanted_by_provider = defaultdict(
        set
    )

    for accession in accessions:
        entry = (
            stage4_context
            .entries_by_accession[
                accession
            ]
        )

        provenance_sha = entry[
            "origin_batch_provenance_sha256"
        ]

        if provenance_sha not in (
            providers_by_provenance
        ):
            raise MonthlyStructuralFeatureInputError(
                "current component provider is missing"
            )

        wanted_by_provider[
            provenance_sha
        ].add(
            accession
        )

    identities = {}

    for provenance_sha, wanted in (
        wanted_by_provider.items()
    ):
        provider = (
            providers_by_provenance[
                provenance_sha
            ]
        )

        index = load_component_index(
            provider.component_audit,
            accessions=wanted,
        )

        if set(
            index
        ) != wanted:
            raise MonthlyStructuralFeatureInputError(
                "current component provider membership changed"
            )

        for accession, components in (
            index.items()
        ):
            if accession in identities:
                raise MonthlyStructuralFeatureInputError(
                    "duplicate current component identity"
                )

            identities[
                accession
            ] = (
                component_identity_sha256(
                    accession,
                    components,
                )
            )

    if set(
        identities
    ) != set(
        accessions
    ):
        raise MonthlyStructuralFeatureInputError(
            "current component identity membership differs from Stage 9"
        )

    observed_sha = (
        component_identity_mapping_sha256(
            identities
        )
    )

    if observed_sha != (
        EXPECTED_COMPONENT_IDENTITY_MAPPING_SHA256
    ):
        raise MonthlyStructuralFeatureInputError(
            "September component-identity mapping differs from frozen partition"
        )

    return identities


# ---------------------------------------------------------------------------
# Partition
# ---------------------------------------------------------------------------


def required_compute_accessions(
    *,
    accessions: Sequence[
        str,
    ],
    current_component_identity_by_accession: Mapping[
        str,
        str,
    ],
    tier1_cache: Mapping[
        str,
        monthly.CachedFeatureRow,
    ],
    tier2_cache: Mapping[
        str,
        monthly.CachedFeatureRow,
    ],
) -> tuple[
    str,
    ...,
]:
    result = []

    for accession in accessions:
        identity = (
            current_component_identity_by_accession[
                accession
            ]
        )

        first = tier1_cache.get(
            accession
        )

        if (
            first is not None
            and first.component_identity_sha256
            == identity
        ):
            continue

        second = tier2_cache.get(
            accession
        )

        if (
            second is not None
            and second.component_identity_sha256
            == identity
        ):
            continue

        result.append(
            accession
        )

    return tuple(
        result
    )


def _cached_feature_values_sha256(
    raw_rows: Mapping[
        str,
        Mapping[
            str,
            str,
        ],
    ],
    accessions: Sequence[
        str,
    ],
) -> str:
    payload = "".join(
        accession
        + "\t"
        + "\t".join(
            raw_rows[
                accession
            ][field]
            for field in (
                monthly
                .FEATURE_FIELDS
            )
        )
        + "\n"
        for accession in sorted(
            accessions
        )
    ).encode(
        "ascii"
    )

    return hashlib.sha256(
        payload
    ).hexdigest()


def validate_partition_without_computation(
    *,
    stage10_wrapper,
    stage9,
    current_component_identity_by_accession: Mapping[
        str,
        str,
    ],
    tier1_cache: Mapping[
        str,
        monthly.CachedFeatureRow,
    ],
    tier2_cache: Mapping[
        str,
        monthly.CachedFeatureRow,
    ],
    tier1_raw_rows: Mapping[
        str,
        Mapping[
            str,
            str,
        ],
    ],
    tier2_raw_rows: Mapping[
        str,
        Mapping[
            str,
            str,
        ],
    ],
) -> tuple[
    str,
    ...,
]:
    accessions = tuple(
        item.accession
        for item in (
            stage9.universe
        )
    )

    compute = (
        required_compute_accessions(
            accessions=accessions,
            current_component_identity_by_accession=(
                current_component_identity_by_accession
            ),
            tier1_cache=(
                tier1_cache
            ),
            tier2_cache=(
                tier2_cache
            ),
        )
    )

    tier1 = []
    tier2 = []

    compute_set = set(
        compute
    )

    for accession in accessions:
        if accession in compute_set:
            continue

        identity = (
            current_component_identity_by_accession[
                accession
            ]
        )

        first = tier1_cache.get(
            accession
        )

        if (
            first is not None
            and first.component_identity_sha256
            == identity
        ):
            tier1.append(
                accession
            )
            continue

        second = tier2_cache.get(
            accession
        )

        if (
            second is not None
            and second.component_identity_sha256
            == identity
        ):
            tier2.append(
                accession
            )
            continue

        raise MonthlyStructuralFeatureInputError(
            "partition classification became inconsistent"
        )

    if (
        len(
            accessions
        )
        != stage10_wrapper.EXPECTED_TOTAL_COUNT
        or len(
            tier1
        )
        != stage10_wrapper.EXPECTED_TIER1_COUNT
        or len(
            tier2
        )
        != stage10_wrapper.EXPECTED_TIER2_COUNT
        or len(
            compute
        )
        != stage10_wrapper.EXPECTED_COMPUTE_COUNT
    ):
        raise MonthlyStructuralFeatureInputError(
            "September Stage 10 partition counts changed"
        )

    if (
        monthly
        .accession_membership_sha256(
            tier1
        )
        != stage10_wrapper
        .EXPECTED_TIER1_MEMBERSHIP_SHA256
    ):
        raise MonthlyStructuralFeatureInputError(
            "Tier 1 membership changed"
        )

    if (
        monthly
        .accession_membership_sha256(
            tier2
        )
        != stage10_wrapper
        .EXPECTED_TIER2_MEMBERSHIP_SHA256
    ):
        raise MonthlyStructuralFeatureInputError(
            "Tier 2 membership changed"
        )

    if (
        monthly
        .accession_membership_sha256(
            compute
        )
        != stage10_wrapper
        .EXPECTED_COMPUTE_MEMBERSHIP_SHA256
    ):
        raise MonthlyStructuralFeatureInputError(
            "COMPUTE membership changed"
        )

    partition_payload = "".join(
        accession
        + "\t"
        + (
            monthly.CACHE_TIER1
            if accession in set(
                tier1
            )
            else (
                monthly.CACHE_TIER2
                if accession in set(
                    tier2
                )
                else monthly.COMPUTED
            )
        )
        + "\t"
        + (
            current_component_identity_by_accession[
                accession
            ]
        )
        + "\n"
        for accession in sorted(
            accessions
        )
    ).encode(
        "ascii"
    )

    if hashlib.sha256(
        partition_payload
    ).hexdigest() != (
        stage10_wrapper
        .EXPECTED_PARTITION_MAPPING_SHA256
    ):
        raise MonthlyStructuralFeatureInputError(
            "Stage 10 partition mapping changed"
        )

    if (
        _cached_feature_values_sha256(
            tier1_raw_rows,
            tier1,
        )
        != EXPECTED_TIER1_FEATURE_VALUES_SHA256
    ):
        raise MonthlyStructuralFeatureInputError(
            "Tier 1 reusable feature values changed"
        )

    if (
        _cached_feature_values_sha256(
            tier2_raw_rows,
            tier2,
        )
        != EXPECTED_TIER2_FEATURE_VALUES_SHA256
    ):
        raise MonthlyStructuralFeatureInputError(
            "Tier 2 reusable feature values changed"
        )

    current_species = (
        stage9
        .species_by_accession
    )

    relabels = tuple(
        sorted(
            accession
            for accession in tier2
            if (
                tier2_raw_rows[
                    accession
                ][
                    "species_taxid"
                ]
                != current_species[
                    accession
                ]
            )
        )
    )

    if relabels != (
        EXPECTED_TIER2_TAXONOMY_RELABELS
    ):
        raise MonthlyStructuralFeatureInputError(
            "Tier 2 taxonomy relabel population changed"
        )

    if (
        stage10_wrapper
        .FORCED_COMPUTE_ACCESSION
        not in compute
    ):
        raise MonthlyStructuralFeatureInputError(
            "topology-revised accession is no longer COMPUTE"
        )

    return compute


# ---------------------------------------------------------------------------
# Production planning
# ---------------------------------------------------------------------------


def build_production_plan(
    *,
    repo: Path,
    source_repo: Path,
    production_root: Path,
    stage1_root: Path,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
    expected_source_truth_completion_sha256: str,
    expected_biosample_completion_sha256: str,
    tier1_matrix: Path,
    tier1_row_audit: Path,
    tier1_historical_component_root: Path,
    tier2_matrix: Path,
    tier2_candidate_evidence: Path,
    tier2_input_manifest: Path,
    tier2_execution_provenance: Path,
    tier2_provider_search_roots: Sequence[
        Path,
    ],
) -> Stage10InputPlan:
    root = _require_real_directory(
        Path(
            repo
        ).resolve(),
        label="BacSelect repository",
    )

    stage10_wrapper = (
        load_stage10_wrapper(
            root
        )
    )

    stage10_wrapper.verify_frozen_dependencies(
        root
    )

    stage6_v2 = load_stage6_v2(
        root
    )

    stage5_v2 = load_stage5_v2(
        root
    )

    stage4_v2 = load_stage4_v2(
        root
    )

    stage4_v1 = (
        stage4_v2
        .load_stage4_v1(
            root
        )
    )

    stage9 = (
        stage10_wrapper
        .authenticate_stage9(
            Path(
                stage1_root
            )
        )
    )

    stage10_wrapper.audit_cache_authority_files(
        tier1_matrix=(
            tier1_matrix
        ),
        tier1_row_audit=(
            tier1_row_audit
        ),
        tier2_matrix=(
            tier2_matrix
        ),
        tier2_candidate_evidence=(
            tier2_candidate_evidence
        ),
        tier2_input_manifest=(
            tier2_input_manifest
        ),
        tier2_execution_provenance=(
            tier2_execution_provenance
        ),
    )

    stage6_v1 = (
        stage6_v2
        .load_stage6_v1(
            root
        )
    )

    context = (
        stage6_v2
        .load_stage5_context_v2(
            repo=root,
            source_repo=(
                Path(
                    source_repo
                )
            ),
            production_root=(
                Path(
                    production_root
                )
            ),
            stage1_root=(
                Path(
                    stage1_root
                )
            ),
            source_production_commit=(
                source_production_commit
            ),
            completion_execution_commit=(
                completion_execution_commit
            ),
            cache_execution_commit=(
                cache_execution_commit
            ),
            source_truth_execution_commit=(
                source_truth_execution_commit
            ),
            biosample_execution_commit=(
                biosample_execution_commit
            ),
            expected_completion_sha256=(
                expected_completion_sha256
            ),
            expected_catalogue_sha256=(
                expected_catalogue_sha256
            ),
            expected_source_truth_completion_sha256=(
                expected_source_truth_completion_sha256
            ),
            expected_biosample_completion_sha256=(
                expected_biosample_completion_sha256
            ),
            stage6_v1=(
                stage6_v1
            ),
            stage5_v2=(
                stage5_v2
            ),
        )
    )

    if (
        context.release_id
        != "2026.09"
        or context.source_snapshot_id
        != (
            "bacselect-source-2026.09-"
            "20260901T021652Z"
        )
    ):
        raise MonthlyStructuralFeatureInputError(
            "authenticated upstream is not September 2026"
        )

    accessions = tuple(
        item.accession
        for item in (
            stage9.universe
        )
    )

    providers = (
        build_current_provider_states(
            stage1_root=(
                Path(
                    stage1_root
                )
            ),
            stage4_context=(
                context
                .stage4_context
            ),
            stage4_v2=(
                stage4_v2
            ),
            source_production_commit=(
                source_production_commit
            ),
            completion_execution_commit=(
                completion_execution_commit
            ),
            cache_execution_commit=(
                cache_execution_commit
            ),
            accessions=accessions,
        )
    )

    current_identity = (
        build_current_component_identities(
            stage4_context=(
                context
                .stage4_context
            ),
            providers_by_provenance=(
                providers
            ),
            accessions=(
                accessions
            ),
        )
    )

    tier1_cache, tier1_raw = (
        build_tier1_cache(
            matrix_path=(
                tier1_matrix
            ),
            historical_component_root=(
                tier1_historical_component_root
            ),
        )
    )

    tier2_cache, tier2_raw = (
        build_tier2_cache(
            matrix_path=(
                tier2_matrix
            ),
            candidate_evidence_path=(
                tier2_candidate_evidence
            ),
            input_manifest_path=(
                tier2_input_manifest
            ),
            provider_search_roots=(
                tier2_provider_search_roots
            ),
        )
    )

    compute = (
        validate_partition_without_computation(
            stage10_wrapper=(
                stage10_wrapper
            ),
            stage9=stage9,
            current_component_identity_by_accession=(
                current_identity
            ),
            tier1_cache=(
                tier1_cache
            ),
            tier2_cache=(
                tier2_cache
            ),
            tier1_raw_rows=(
                tier1_raw
            ),
            tier2_raw_rows=(
                tier2_raw
            ),
        )
    )

    reauthenticate_observations(
        observation
        for provider in (
            providers.values()
        )
        for observation in (
            provider.observations
        )
    )

    return Stage10InputPlan(
        stage9=stage9,
        context=context,
        stage6_v2=stage6_v2,
        stage5_v2=stage5_v2,
        stage4_v2=stage4_v2,
        stage4_v1=stage4_v1,
        current_component_identity_by_accession=(
            current_identity
        ),
        tier1_cache=(
            tier1_cache
        ),
        tier2_cache=(
            tier2_cache
        ),
        compute_accessions=(
            compute
        ),
        providers_by_provenance=(
            providers
        ),
        tier1_raw_rows=(
            tier1_raw
        ),
        tier2_raw_rows=(
            tier2_raw
        ),
    )


# ---------------------------------------------------------------------------
# Compute-only candidate binding
# ---------------------------------------------------------------------------


def _provider_for_accession(
    plan: Stage10InputPlan,
    accession: str,
) -> ProviderState:
    entry = (
        plan
        .context
        .stage4_context
        .entries_by_accession[
            accession
        ]
    )

    provenance_sha = entry[
        "origin_batch_provenance_sha256"
    ]

    provider = (
        plan
        .providers_by_provenance
        .get(
            provenance_sha
        )
    )

    if provider is None:
        raise MonthlyStructuralFeatureInputError(
            "COMPUTE accession provider is missing"
        )

    return provider


def build_compute_binding(
    *,
    plan: Stage10InputPlan,
    accession: str,
):
    if accession not in (
        plan.compute_accessions
    ):
        raise MonthlyStructuralFeatureInputError(
            "refusing feature binding for reusable accession"
        )

    stage4_context = (
        plan
        .context
        .stage4_context
    )

    entry = (
        stage4_context
        .entries_by_accession[
            accession
        ]
    )

    provider_state = (
        _provider_for_accession(
            plan,
            accession,
        )
    )

    provider = (
        provider_state
        .provider
    )

    bridge = (
        plan
        .stage4_v1
        .validate_candidate_bridge(
            stage4_context.cache_execution,
            entry=entry,
            batch=(
                provider.batch
            ),
        )
    )

    if bridge.accession != accession:
        raise MonthlyStructuralFeatureInputError(
            "COMPUTE bridge accession changed"
        )

    # Re-run the exact frozen Stage 4-v2 provider evaluation before
    # structural-feature execution.
    plan.stage4_v2._evaluate_provider_candidate(
        plan.stage4_v1,
        bridge=bridge,
        provider=provider,
    )

    (
        candidate,
        components,
        package_manifest,
    ) = (
        plan
        .stage4_v1
        ._source_truth_objects(
            bridge,
            audit_path=(
                provider
                .candidate_audit_path
            ),
        )
    )

    if candidate.accession != accession:
        raise MonthlyStructuralFeatureInputError(
            "reconstructed COMPUTE candidate accession changed"
        )

    source_group = (
        provider_state
        .source_group
    )

    if source_group not in (
        ALLOWED_CURRENT_SOURCE_GROUPS
    ):
        raise MonthlyStructuralFeatureInputError(
            "COMPUTE candidate source group changed"
        )

    batch_spec = MonthlyBatchSpec(
        source_group=source_group,
        batch=(
            provider.batch_id
        ),
        candidate_audit=(
            provider
            .candidate_audit_path
        ),
        component_audit=(
            provider_state
            .component_audit
        ),
        package_manifest=(
            provider_state
            .package_manifest
        ),
        candidates=(
            candidate,
        ),
    )

    binding = (
        source_structural_features
        .resolve_candidate_package(
            batch=batch_spec,
            candidate=candidate,
            package_manifest=(
                package_manifest
            ),
        )
    )

    if binding.accession != accession:
        raise MonthlyStructuralFeatureInputError(
            "structural-feature binding accession changed"
        )

    current_identity = (
        component_identity_sha256(
            accession,
            components,
        )
    )

    if current_identity != (
        plan
        .current_component_identity_by_accession[
            accession
        ]
    ):
        raise MonthlyStructuralFeatureInputError(
            "COMPUTE component identity changed during package reconstruction"
        )

    return binding


def compute_feature_records(
    *,
    plan: Stage10InputPlan,
    finch,
    basic,
    engine: Path,
    compute_one: Callable[
        ...,
        feature_execution.Stage6FeatureRecord,
    ] = (
        feature_execution
        .compute_stage6_feature_record
    ),
) -> Mapping[
    str,
    feature_execution.Stage6FeatureRecord,
]:
    results = {}

    for accession in (
        plan.compute_accessions
    ):
        binding = build_compute_binding(
            plan=plan,
            accession=accession,
        )

        record = compute_one(
            binding=binding,
            species_taxid=(
                plan
                .stage9
                .species_by_accession[
                    accession
                ]
            ),
            finch=finch,
            basic=basic,
            engine=engine,
        )

        if (
            record.accession
            != accession
            or record.species_taxid
            != (
                plan
                .stage9
                .species_by_accession[
                    accession
                ]
            )
        ):
            raise MonthlyStructuralFeatureInputError(
                "fresh structural-feature record identity changed"
            )

        if accession in results:
            raise MonthlyStructuralFeatureInputError(
                "duplicate fresh structural-feature result"
            )

        results[
            accession
        ] = record

    if set(
        results
    ) != set(
        plan.compute_accessions
    ):
        raise MonthlyStructuralFeatureInputError(
            "fresh structural-feature result membership changed"
        )

    return results


def compute_production_inputs(
    *,
    repo: Path,
    plan: Stage10InputPlan,
    repeat_env_prefix: Path,
) -> Stage10ComputedInputs:
    """Compute exactly the frozen COMPUTE membership.

    This function still does not publish Stage 10.
    """

    root = _require_real_directory(
        Path(
            repo
        ).resolve(),
        label="BacSelect repository",
    )

    structural_wrapper = (
        load_historical_structural_wrapper(
            root
        )
    )

    finch = (
        structural_wrapper
        .load_finch_driver(
            root
        )
    )

    basic = finch.basic

    with tempfile.TemporaryDirectory(
        prefix="bacselect-stage10-engine-"
    ) as temporary:
        engine, engine_sha = (
            structural_wrapper
            .compile_frozen_engine(
                repo=root,
                env_prefix=(
                    Path(
                        repeat_env_prefix
                    )
                ),
                build_dir=(
                    Path(
                        temporary
                    )
                    / "build"
                ),
            )
        )

        if engine_sha != (
            EXPECTED_ENGINE_BINARY_SHA256
        ):
            raise MonthlyStructuralFeatureInputError(
                "compiled structural-feature engine identity changed"
            )

        computed_rows = (
            compute_feature_records(
                plan=plan,
                finch=finch,
                basic=basic,
                engine=engine,
            )
        )

    # Reauthenticate every provider file used to establish September
    # package/component evidence after the potentially long computation.
    reauthenticate_observations(
        observation
        for provider in (
            plan
            .providers_by_provenance
            .values()
        )
        for observation in (
            provider.observations
        )
    )

    stage10_wrapper = (
        load_stage10_wrapper(
            root
        )
    )

    execution_inputs = (
        stage10_wrapper
        .Stage10ExecutionInputs(
            current_component_identity_by_accession=(
                plan
                .current_component_identity_by_accession
            ),
            tier1_cache=(
                plan
                .tier1_cache
            ),
            tier2_cache=(
                plan
                .tier2_cache
            ),
            computed_rows=(
                computed_rows
            ),
        )
    )

    build = (
        monthly
        .build_monthly_structural_features(
            plan.stage9.universe,
            current_component_identity_by_accession=(
                execution_inputs
                .current_component_identity_by_accession
            ),
            tier1_cache=(
                execution_inputs
                .tier1_cache
            ),
            tier2_cache=(
                execution_inputs
                .tier2_cache
            ),
            computed_rows=(
                execution_inputs
                .computed_rows
            ),
        )
    )

    stage10_wrapper.audit_frozen_partition(
        build
    )

    return Stage10ComputedInputs(
        plan=plan,
        computed_rows=(
            computed_rows
        ),
        execution_inputs=(
            execution_inputs
        ),
        build=build,
    )
