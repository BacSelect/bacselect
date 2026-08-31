"""Deterministic selector-v1 official reference-panel serialization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from numbers import Integral
import re
from typing import Any


PANEL_SIZES: tuple[int, ...] = (
    10,
    20,
    50,
    100,
    200,
    500,
)

CUSTOM_N_MIN = 10
CUSTOM_N_MAX = 500
WINNING_LADDER_N = 500

SELECTOR = "OPS"
SELECTOR_VERSION = "1.0.0"
ARCHITECTURE_SCHEMA_VERSION = 1

PANEL_ARTIFACT_SCHEMA_VERSION = (
    "bacselect-selector-v1-official-panels-v1"
)

PANEL_PROVENANCE_SCHEMA_VERSION = (
    "bacselect-selector-v1-official-panel-provenance-v1"
)

GENERATION_STATUS = (
    "OFFICIAL_SELECTOR_V1_REFERENCE_PANELS_GENERATED"
)

COMPLETION_STATUS = (
    "OFFICIAL_SELECTOR_V1_REFERENCE_PANELS_COMPLETE"
)

WINNING_LADDER_SHA256 = (
    "c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13"
)

SELECTOR_DECISION_RECORD_SHA256 = (
    "d0cf63ad4d933194e3e782912a2a2a3c617353758d2c87c1b1198681a75869e2"
)

SELECTOR_DECISION_COMMIT = (
    "d4ba45468baf34b094e7f4bbda8b21a6d8a9de3a"
)

WINNING_LADDER_FILENAME = (
    "selector-v1-winning-ladder-n500.tsv"
)

MEMBERSHIP_MANIFEST_FILENAME = (
    "panel-membership-manifest.tsv"
)

SUMMARY_FILENAME = (
    "panel-generation-summary.json"
)

PROVENANCE_FILENAME = (
    "panel-generation-provenance.json"
)

CONTENT_MANIFEST_FILENAME = (
    "panel-content-manifest.tsv"
)

PANEL_FILENAMES: Mapping[int, str] = {
    10: "panel-n10.txt",
    20: "panel-n20.txt",
    50: "panel-n50.txt",
    100: "panel-n100.txt",
    200: "panel-n200.txt",
    500: "panel-n500.txt",
}

BASELINE_BINDING_KEYS = frozenset(
    {
        "manifest_sha256",
        "raw_file_sha256",
        "raw_array_sha256",
        "percentile_file_sha256",
        "percentile_array_sha256",
        "species_file_sha256",
    }
)

CONTENT_SOURCE_ARTIFACTS = (
    PROVENANCE_FILENAME,
    SUMMARY_FILENAME,
    MEMBERSHIP_MANIFEST_FILENAME,
    PANEL_FILENAMES[10],
    PANEL_FILENAMES[20],
    PANEL_FILENAMES[50],
    PANEL_FILENAMES[100],
    PANEL_FILENAMES[200],
    PANEL_FILENAMES[500],
    WINNING_LADDER_FILENAME,
)

ALL_ARTIFACTS = (
    *CONTENT_SOURCE_ARTIFACTS,
    CONTENT_MANIFEST_FILENAME,
)

_GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

_GIT_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_LADDER_HEADER = (
    "rank\taccession\tfirst_public_panel_n"
)

_MEMBERSHIP_MANIFEST_HEADER = (
    "panel_size\tmember_count\taccession_list_sha256"
)

_CONTENT_MANIFEST_HEADER = (
    "artifact\tsha256\tbytes\tdata_rows"
)

_PROVENANCE_KEYS = frozenset(
    {
        "schema_version",
        "execution_commit",
        "implementation_sha256",
        "implementation_test_sha256",
        "selector_decision_record_sha256",
        "selector_decision_commit",
        "winning_selector",
        "winning_ladder_sha256",
        "stage7_wrapper_sha256",
        "stage7_execution_adapter_sha256",
        "final_geometry_helper_sha256",
        "baseline_bindings",
        "environment_lock_sha256",
    }
)


class OfficialPanelError(ValueError):
    """Raised when the frozen official-panel contract is violated."""


def sha256_bytes(
    payload: bytes,
) -> str:
    """Return lowercase SHA256 for exact bytes."""
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "payload must be bytes"
        )

    return hashlib.sha256(
        payload
    ).hexdigest()


def validate_sha256(
    value: str,
    *,
    label: str,
) -> str:
    """Validate one lowercase SHA256 string."""
    if (
        not isinstance(
            value,
            str,
        )
        or _SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise OfficialPanelError(
            f"{label} must be a lowercase SHA256"
        )

    return value


def validate_git_commit(
    value: str,
    *,
    label: str,
) -> str:
    """Validate one lowercase 40-character Git commit."""
    if (
        not isinstance(
            value,
            str,
        )
        or _GIT_COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise OfficialPanelError(
            f"{label} must be a lowercase 40-character Git commit"
        )

    return value


def canonical_json_bytes(
    payload: Mapping[str, Any],
) -> bytes:
    """Serialize canonical deterministic JSON."""
    if not isinstance(
        payload,
        Mapping,
    ):
        raise TypeError(
            "JSON payload must be a mapping"
        )

    return (
        json.dumps(
            dict(payload),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def verify_selector_decision_bytes(
    payload: bytes,
    *,
    expected_sha256: str,
    expected_final_ladder_sha256: Mapping[str, str],
) -> Mapping[str, Any]:
    """Verify the pushed selector decision relevant to panel generation."""
    validate_sha256(
        expected_sha256,
        label="selector decision record SHA256",
    )

    if sha256_bytes(
        payload
    ) != expected_sha256:
        raise OfficialPanelError(
            "selector decision record SHA256 mismatch"
        )

    try:
        record = json.loads(
            payload.decode(
                "utf-8"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise OfficialPanelError(
            "selector decision record is not valid UTF-8 JSON"
        ) from None

    if not isinstance(
        record,
        dict,
    ):
        raise OfficialPanelError(
            "selector decision record must be a JSON object"
        )

    decision = record.get(
        "decision"
    )

    if decision != SELECTOR:
        raise OfficialPanelError(
            "selector decision must be exactly OPS"
        )

    if set(
        expected_final_ladder_sha256
    ) != {
        "OPS",
        "SR",
    }:
        raise OfficialPanelError(
            "expected final ladder hashes must contain exactly OPS and SR"
        )

    expected_hashes: dict[str, str] = {}

    for selector in (
        "OPS",
        "SR",
    ):
        expected_hashes[
            selector
        ] = validate_sha256(
            expected_final_ladder_sha256[
                selector
            ],
            label=(
                f"{selector} final ladder SHA256"
            ),
        )

    if record.get(
        "final_ladder_sha256"
    ) != expected_hashes:
        raise OfficialPanelError(
            "selector decision final ladder fingerprints mismatch"
        )

    if expected_hashes[
        "OPS"
    ] != WINNING_LADDER_SHA256:
        raise OfficialPanelError(
            "OPS final ladder fingerprint is not the frozen winner"
        )

    return record


def validate_panel_size(
    panel_size: int,
) -> int:
    """Validate one custom public panel size."""
    if (
        isinstance(
            panel_size,
            bool,
        )
        or not isinstance(
            panel_size,
            Integral,
        )
    ):
        raise TypeError(
            "panel size must be an integer"
        )

    value = int(
        panel_size
    )

    if not (
        CUSTOM_N_MIN
        <= value
        <= CUSTOM_N_MAX
    ):
        raise OfficialPanelError(
            "panel size must satisfy 10 <= N <= 500"
        )

    return value


def first_public_panel_n(
    rank: int,
) -> int:
    """Return the first preset public panel containing one rank."""
    if (
        isinstance(
            rank,
            bool,
        )
        or not isinstance(
            rank,
            Integral,
        )
    ):
        raise TypeError(
            "rank must be an integer"
        )

    value = int(
        rank
    )

    if not (
        1
        <= value
        <= WINNING_LADDER_N
    ):
        raise OfficialPanelError(
            "rank must satisfy 1 <= rank <= 500"
        )

    for panel_size in PANEL_SIZES:
        if value <= panel_size:
            return panel_size

    raise AssertionError(
        "unreachable public-panel boundary"
    )


def _validate_accession(
    accession: str,
) -> str:
    """Validate one canonical GenBank assembly accession."""
    if (
        not isinstance(
            accession,
            str,
        )
        or _GCA_RE.fullmatch(
            accession
        )
        is None
    ):
        raise OfficialPanelError(
            "panel members must be canonical GCA accessions"
        )

    return accession


def validate_verified_accessions(
    accessions: Sequence[str],
) -> tuple[str, ...]:
    """Validate the fully resolved verified OPS N=500 accession ladder."""
    values = tuple(
        accessions
    )

    if len(
        values
    ) != WINNING_LADDER_N:
        raise OfficialPanelError(
            "winning ladder must contain exactly 500 accessions"
        )

    validated = tuple(
        _validate_accession(
            accession
        )
        for accession in values
    )

    if len(
        set(
            validated
        )
    ) != WINNING_LADDER_N:
        raise OfficialPanelError(
            "winning ladder accessions must be unique"
        )

    return validated


def resolve_verified_ops_accessions(
    ladder_indices: Sequence[int],
    baseline_accessions: Sequence[str],
) -> tuple[str, ...]:
    """Resolve a verified N=500 OPS index ladder to canonical accessions."""
    raw_indices = tuple(
        ladder_indices
    )

    if len(
        raw_indices
    ) != WINNING_LADDER_N:
        raise OfficialPanelError(
            "verified OPS ladder must contain exactly 500 indices"
        )

    indices: list[int] = []

    for index in raw_indices:
        if (
            isinstance(
                index,
                bool,
            )
            or not isinstance(
                index,
                Integral,
            )
        ):
            raise TypeError(
                "verified OPS ladder indices must be integers"
            )

        indices.append(
            int(
                index
            )
        )

    if len(
        set(
            indices
        )
    ) != WINNING_LADDER_N:
        raise OfficialPanelError(
            "verified OPS ladder indices must be unique"
        )

    baseline = tuple(
        baseline_accessions
    )

    if any(
        index < 0
        or index >= len(
            baseline
        )
        for index in indices
    ):
        raise OfficialPanelError(
            "verified OPS ladder index outside baseline"
        )

    selected = tuple(
        baseline[
            index
        ]
        for index in indices
    )

    return validate_verified_accessions(
        selected
    )


def serialize_custom_accession_list(
    accessions: Sequence[str],
    panel_size: int,
) -> bytes:
    """Serialize any valid custom N as an exact OPS prefix."""
    values = validate_verified_accessions(
        accessions
    )

    n = validate_panel_size(
        panel_size
    )

    return (
        "\n".join(
            values[
                :n
            ]
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def serialize_winning_ladder(
    accessions: Sequence[str],
) -> bytes:
    """Serialize the canonical ordered N=500 winning ladder TSV."""
    values = validate_verified_accessions(
        accessions
    )

    lines = [
        _LADDER_HEADER
    ]

    for rank, accession in enumerate(
        values,
        start=1,
    ):
        lines.append(
            "\t".join(
                (
                    str(
                        rank
                    ),
                    accession,
                    str(
                        first_public_panel_n(
                            rank
                        )
                    ),
                )
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def _preset_panel_bytes(
    accessions: Sequence[str],
) -> dict[int, bytes]:
    """Return exact bytes for all six preset panels."""
    values = validate_verified_accessions(
        accessions
    )

    return {
        panel_size:
            serialize_custom_accession_list(
                values,
                panel_size,
            )
        for panel_size in PANEL_SIZES
    }


def serialize_membership_manifest(
    panel_bytes: Mapping[int, bytes],
) -> bytes:
    """Serialize hashes for the six canonical preset accession lists."""
    if set(
        panel_bytes
    ) != set(
        PANEL_SIZES
    ):
        raise OfficialPanelError(
            "preset panel mapping must contain exactly 10,20,50,100,200,500"
        )

    lines = [
        _MEMBERSHIP_MANIFEST_HEADER
    ]

    for panel_size in PANEL_SIZES:
        payload = panel_bytes[
            panel_size
        ]

        if not isinstance(
            payload,
            bytes,
        ):
            raise TypeError(
                "preset panel payloads must be bytes"
            )

        lines.append(
            "\t".join(
                (
                    str(
                        panel_size
                    ),
                    str(
                        panel_size
                    ),
                    sha256_bytes(
                        payload
                    ),
                )
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def generation_summary_payload() -> Mapping[str, Any]:
    """Return the exact fixed selector-v1 reference-panel summary."""
    return {
        "architecture_schema_version":
            ARCHITECTURE_SCHEMA_VERSION,
        "custom_n_max":
            CUSTOM_N_MAX,
        "custom_n_min":
            CUSTOM_N_MIN,
        "monthly_release_assigned":
            False,
        "nested_prefix_property":
            True,
        "preset_panel_sizes":
            list(
                PANEL_SIZES
            ),
        "schema_version":
            PANEL_ARTIFACT_SCHEMA_VERSION,
        "selector":
            SELECTOR,
        "selector_decision_commit":
            SELECTOR_DECISION_COMMIT,
        "selector_decision_record_sha256":
            SELECTOR_DECISION_RECORD_SHA256,
        "selector_version":
            SELECTOR_VERSION,
        "status":
            GENERATION_STATUS,
        "winning_ladder_accession_count":
            WINNING_LADDER_N,
        "winning_ladder_n":
            WINNING_LADDER_N,
        "winning_ladder_sha256":
            WINNING_LADDER_SHA256,
    }


def serialize_generation_summary() -> bytes:
    """Serialize the exact fixed selector-v1 generation summary."""
    return canonical_json_bytes(
        generation_summary_payload()
    )


def _validate_baseline_bindings(
    bindings: Mapping[str, str],
) -> dict[str, str]:
    """Validate the exact Stage 7 baseline-binding key set."""
    if set(
        bindings
    ) != BASELINE_BINDING_KEYS:
        raise OfficialPanelError(
            "baseline bindings have changed"
        )

    return {
        key:
            validate_sha256(
                bindings[
                    key
                ],
                label=(
                    f"baseline binding {key}"
                ),
            )
        for key in sorted(
            BASELINE_BINDING_KEYS
        )
    }


def provenance_payload(
    *,
    execution_commit: str,
    implementation_sha256: str,
    implementation_test_sha256: str,
    stage7_wrapper_sha256: str,
    stage7_execution_adapter_sha256: str,
    final_geometry_helper_sha256: str,
    baseline_bindings: Mapping[str, str],
    environment_lock_sha256: str,
) -> Mapping[str, Any]:
    """Build exact machine-readable provenance for one execution."""
    return {
        "baseline_bindings":
            _validate_baseline_bindings(
                baseline_bindings
            ),
        "environment_lock_sha256":
            validate_sha256(
                environment_lock_sha256,
                label="environment lock SHA256",
            ),
        "execution_commit":
            validate_git_commit(
                execution_commit,
                label="execution commit",
            ),
        "final_geometry_helper_sha256":
            validate_sha256(
                final_geometry_helper_sha256,
                label="final geometry helper SHA256",
            ),
        "implementation_sha256":
            validate_sha256(
                implementation_sha256,
                label="implementation SHA256",
            ),
        "implementation_test_sha256":
            validate_sha256(
                implementation_test_sha256,
                label="implementation test SHA256",
            ),
        "schema_version":
            PANEL_PROVENANCE_SCHEMA_VERSION,
        "selector_decision_commit":
            SELECTOR_DECISION_COMMIT,
        "selector_decision_record_sha256":
            SELECTOR_DECISION_RECORD_SHA256,
        "stage7_execution_adapter_sha256":
            validate_sha256(
                stage7_execution_adapter_sha256,
                label="Stage 7 execution adapter SHA256",
            ),
        "stage7_wrapper_sha256":
            validate_sha256(
                stage7_wrapper_sha256,
                label="Stage 7 wrapper SHA256",
            ),
        "winning_ladder_sha256":
            WINNING_LADDER_SHA256,
        "winning_selector":
            SELECTOR,
    }


def serialize_generation_provenance(
    *,
    execution_commit: str,
    implementation_sha256: str,
    implementation_test_sha256: str,
    stage7_wrapper_sha256: str,
    stage7_execution_adapter_sha256: str,
    final_geometry_helper_sha256: str,
    baseline_bindings: Mapping[str, str],
    environment_lock_sha256: str,
) -> bytes:
    """Serialize exact machine-readable generation provenance."""
    return canonical_json_bytes(
        provenance_payload(
            execution_commit=execution_commit,
            implementation_sha256=implementation_sha256,
            implementation_test_sha256=implementation_test_sha256,
            stage7_wrapper_sha256=stage7_wrapper_sha256,
            stage7_execution_adapter_sha256=(
                stage7_execution_adapter_sha256
            ),
            final_geometry_helper_sha256=(
                final_geometry_helper_sha256
            ),
            baseline_bindings=baseline_bindings,
            environment_lock_sha256=(
                environment_lock_sha256
            ),
        )
    )


def _data_rows_for_artifact(
    artifact: str,
) -> int:
    """Return frozen content-manifest data-row semantics."""
    if artifact == WINNING_LADDER_FILENAME:
        return WINNING_LADDER_N

    if artifact == MEMBERSHIP_MANIFEST_FILENAME:
        return len(
            PANEL_SIZES
        )

    for panel_size, filename in PANEL_FILENAMES.items():
        if artifact == filename:
            return panel_size

    if artifact in {
        SUMMARY_FILENAME,
        PROVENANCE_FILENAME,
    }:
        return 1

    raise OfficialPanelError(
        f"unknown content-manifest artifact: {artifact}"
    )


def serialize_content_manifest(
    artifacts: Mapping[str, bytes],
) -> bytes:
    """Serialize hashes, byte sizes and row counts for ten source artefacts."""
    if set(
        artifacts
    ) != set(
        CONTENT_SOURCE_ARTIFACTS
    ):
        raise OfficialPanelError(
            "content manifest source artifact set changed"
        )

    lines = [
        _CONTENT_MANIFEST_HEADER
    ]

    for artifact in sorted(
        CONTENT_SOURCE_ARTIFACTS
    ):
        payload = artifacts[
            artifact
        ]

        if not isinstance(
            payload,
            bytes,
        ):
            raise TypeError(
                "artifact payloads must be bytes"
            )

        lines.append(
            "\t".join(
                (
                    artifact,
                    sha256_bytes(
                        payload
                    ),
                    str(
                        len(
                            payload
                        )
                    ),
                    str(
                        _data_rows_for_artifact(
                            artifact
                        )
                    ),
                )
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def _decode_text(
    payload: bytes,
    *,
    label: str,
) -> str:
    """Decode required UTF-8 text and require exactly one final newline."""
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            f"{label} must be bytes"
        )

    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError:
        raise OfficialPanelError(
            f"{label} is not UTF-8"
        ) from None

    if (
        not text.endswith(
            "\n"
        )
        or text.endswith(
            "\n\n"
        )
    ):
        raise OfficialPanelError(
            f"{label} must end with exactly one final newline"
        )

    return text


def _parse_canonical_json(
    payload: bytes,
    *,
    label: str,
) -> Mapping[str, Any]:
    """Parse and require byte-canonical JSON."""
    text = _decode_text(
        payload,
        label=label,
    )

    try:
        value = json.loads(
            text
        )
    except json.JSONDecodeError:
        raise OfficialPanelError(
            f"{label} is invalid JSON"
        ) from None

    if not isinstance(
        value,
        dict,
    ):
        raise OfficialPanelError(
            f"{label} must contain a JSON object"
        )

    if canonical_json_bytes(
        value
    ) != payload:
        raise OfficialPanelError(
            f"{label} is not canonically serialized"
        )

    return value


def _audit_provenance(
    payload: bytes,
) -> None:
    """Audit dynamic provenance without knowing execution identities."""
    value = _parse_canonical_json(
        payload,
        label=PROVENANCE_FILENAME,
    )

    if set(
        value
    ) != _PROVENANCE_KEYS:
        raise OfficialPanelError(
            "generation provenance key set changed"
        )

    if value.get(
        "schema_version"
    ) != PANEL_PROVENANCE_SCHEMA_VERSION:
        raise OfficialPanelError(
            "generation provenance schema version changed"
        )

    if value.get(
        "winning_selector"
    ) != SELECTOR:
        raise OfficialPanelError(
            "generation provenance selector changed"
        )

    if value.get(
        "winning_ladder_sha256"
    ) != WINNING_LADDER_SHA256:
        raise OfficialPanelError(
            "generation provenance winning ladder changed"
        )

    if value.get(
        "selector_decision_record_sha256"
    ) != SELECTOR_DECISION_RECORD_SHA256:
        raise OfficialPanelError(
            "generation provenance decision record changed"
        )

    if value.get(
        "selector_decision_commit"
    ) != SELECTOR_DECISION_COMMIT:
        raise OfficialPanelError(
            "generation provenance decision commit changed"
        )

    validate_git_commit(
        value.get(
            "execution_commit"
        ),
        label="generation provenance execution commit",
    )

    for key in (
        "implementation_sha256",
        "implementation_test_sha256",
        "stage7_wrapper_sha256",
        "stage7_execution_adapter_sha256",
        "final_geometry_helper_sha256",
        "environment_lock_sha256",
    ):
        validate_sha256(
            value.get(
                key
            ),
            label=(
                f"generation provenance {key}"
            ),
        )

    baseline_bindings = value.get(
        "baseline_bindings"
    )

    if not isinstance(
        baseline_bindings,
        dict,
    ):
        raise OfficialPanelError(
            "generation provenance baseline bindings must be an object"
        )

    _validate_baseline_bindings(
        baseline_bindings
    )


def audit_reference_panel_artifacts(
    artifacts: Mapping[str, bytes],
) -> tuple[str, ...]:
    """Audit all eleven deterministic reference-panel artefacts."""
    if set(
        artifacts
    ) != set(
        ALL_ARTIFACTS
    ):
        raise OfficialPanelError(
            "official reference-panel artifact set changed"
        )

    for artifact, payload in artifacts.items():
        _decode_text(
            payload,
            label=artifact,
        )

    ladder_text = _decode_text(
        artifacts[
            WINNING_LADDER_FILENAME
        ],
        label=WINNING_LADDER_FILENAME,
    )

    ladder_lines = ladder_text.splitlines()

    if (
        len(
            ladder_lines
        )
        != WINNING_LADDER_N + 1
        or ladder_lines[
            0
        ]
        != _LADDER_HEADER
    ):
        raise OfficialPanelError(
            "winning ladder TSV schema changed"
        )

    accessions: list[str] = []

    for expected_rank, line in enumerate(
        ladder_lines[
            1:
        ],
        start=1,
    ):
        fields = line.split(
            "\t"
        )

        if len(
            fields
        ) != 3:
            raise OfficialPanelError(
                "winning ladder TSV field count changed"
            )

        rank_text, accession, first_n_text = fields

        if rank_text != str(
            expected_rank
        ):
            raise OfficialPanelError(
                "winning ladder rank order changed"
            )

        _validate_accession(
            accession
        )

        if first_n_text != str(
            first_public_panel_n(
                expected_rank
            )
        ):
            raise OfficialPanelError(
                "winning ladder first-public-panel boundary changed"
            )

        accessions.append(
            accession
        )

    validated_accessions = validate_verified_accessions(
        accessions
    )

    panel_payloads: dict[int, bytes] = {}

    for panel_size in PANEL_SIZES:
        filename = PANEL_FILENAMES[
            panel_size
        ]

        payload = artifacts[
            filename
        ]

        panel_payloads[
            panel_size
        ] = payload

        lines = _decode_text(
            payload,
            label=filename,
        ).splitlines()

        if len(
            lines
        ) != panel_size:
            raise OfficialPanelError(
                f"{filename} member count changed"
            )

        if tuple(
            lines
        ) != validated_accessions[
            :panel_size
        ]:
            raise OfficialPanelError(
                f"{filename} is not the exact winning-ladder prefix"
            )

    membership_text = _decode_text(
        artifacts[
            MEMBERSHIP_MANIFEST_FILENAME
        ],
        label=MEMBERSHIP_MANIFEST_FILENAME,
    )

    membership_lines = membership_text.splitlines()

    if (
        len(
            membership_lines
        )
        != len(
            PANEL_SIZES
        )
        + 1
        or membership_lines[
            0
        ]
        != _MEMBERSHIP_MANIFEST_HEADER
    ):
        raise OfficialPanelError(
            "panel membership manifest schema changed"
        )

    for line, panel_size in zip(
        membership_lines[
            1:
        ],
        PANEL_SIZES,
        strict=True,
    ):
        fields = line.split(
            "\t"
        )

        expected = (
            str(
                panel_size
            ),
            str(
                panel_size
            ),
            sha256_bytes(
                panel_payloads[
                    panel_size
                ]
            ),
        )

        if tuple(
            fields
        ) != expected:
            raise OfficialPanelError(
                "panel membership manifest row mismatch"
            )

    summary_payload = artifacts[
        SUMMARY_FILENAME
    ]

    if summary_payload != serialize_generation_summary():
        raise OfficialPanelError(
            "generation summary bytes changed"
        )

    _audit_provenance(
        artifacts[
            PROVENANCE_FILENAME
        ]
    )

    content_text = _decode_text(
        artifacts[
            CONTENT_MANIFEST_FILENAME
        ],
        label=CONTENT_MANIFEST_FILENAME,
    )

    content_lines = content_text.splitlines()

    if (
        len(
            content_lines
        )
        != len(
            CONTENT_SOURCE_ARTIFACTS
        )
        + 1
        or content_lines[
            0
        ]
        != _CONTENT_MANIFEST_HEADER
    ):
        raise OfficialPanelError(
            "content manifest schema changed"
        )

    observed_names: list[str] = []

    for line in content_lines[
        1:
    ]:
        fields = line.split(
            "\t"
        )

        if len(
            fields
        ) != 4:
            raise OfficialPanelError(
                "content manifest field count changed"
            )

        artifact, observed_sha, observed_bytes, observed_rows = fields

        observed_names.append(
            artifact
        )

        if artifact not in CONTENT_SOURCE_ARTIFACTS:
            raise OfficialPanelError(
                "content manifest contains unexpected artifact"
            )

        payload = artifacts[
            artifact
        ]

        expected = (
            sha256_bytes(
                payload
            ),
            str(
                len(
                    payload
                )
            ),
            str(
                _data_rows_for_artifact(
                    artifact
                )
            ),
        )

        if (
            observed_sha,
            observed_bytes,
            observed_rows,
        ) != expected:
            raise OfficialPanelError(
                "content manifest artifact identity mismatch"
            )

    if observed_names != sorted(
        CONTENT_SOURCE_ARTIFACTS
    ):
        raise OfficialPanelError(
            "content manifest artifact ordering changed"
        )

    return validated_accessions


def build_reference_panel_artifacts(
    accessions: Sequence[str],
    *,
    execution_commit: str,
    implementation_sha256: str,
    implementation_test_sha256: str,
    stage7_wrapper_sha256: str,
    stage7_execution_adapter_sha256: str,
    final_geometry_helper_sha256: str,
    baseline_bindings: Mapping[str, str],
    environment_lock_sha256: str,
) -> Mapping[str, bytes]:
    """Build and self-audit all eleven official reference-panel artefacts."""
    values = validate_verified_accessions(
        accessions
    )

    panel_bytes = _preset_panel_bytes(
        values
    )

    artifacts: dict[str, bytes] = {
        WINNING_LADDER_FILENAME:
            serialize_winning_ladder(
                values
            ),
        MEMBERSHIP_MANIFEST_FILENAME:
            serialize_membership_manifest(
                panel_bytes
            ),
        SUMMARY_FILENAME:
            serialize_generation_summary(),
        PROVENANCE_FILENAME:
            serialize_generation_provenance(
                execution_commit=execution_commit,
                implementation_sha256=implementation_sha256,
                implementation_test_sha256=(
                    implementation_test_sha256
                ),
                stage7_wrapper_sha256=stage7_wrapper_sha256,
                stage7_execution_adapter_sha256=(
                    stage7_execution_adapter_sha256
                ),
                final_geometry_helper_sha256=(
                    final_geometry_helper_sha256
                ),
                baseline_bindings=baseline_bindings,
                environment_lock_sha256=(
                    environment_lock_sha256
                ),
            ),
    }

    for panel_size in PANEL_SIZES:
        artifacts[
            PANEL_FILENAMES[
                panel_size
            ]
        ] = panel_bytes[
            panel_size
        ]

    content_sources = {
        artifact:
            artifacts[
                artifact
            ]
        for artifact in CONTENT_SOURCE_ARTIFACTS
    }

    artifacts[
        CONTENT_MANIFEST_FILENAME
    ] = serialize_content_manifest(
        content_sources
    )

    audit_reference_panel_artifacts(
        artifacts
    )

    return artifacts


def require_artifact_sets_byte_identical(
    production: Mapping[str, bytes],
    rebuild: Mapping[str, bytes],
) -> None:
    """Require exact artifact-name and byte identity between two builds."""
    if set(
        production
    ) != set(
        ALL_ARTIFACTS
    ):
        raise OfficialPanelError(
            "production artifact set changed"
        )

    if set(
        rebuild
    ) != set(
        ALL_ARTIFACTS
    ):
        raise OfficialPanelError(
            "rebuild artifact set changed"
        )

    for artifact in ALL_ARTIFACTS:
        if production[
            artifact
        ] != rebuild[
            artifact
        ]:
            raise OfficialPanelError(
                f"production/rebuild byte mismatch: {artifact}"
            )
