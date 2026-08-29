#!/usr/bin/env python3
"""Execute frozen BacSelect Stage 5A complete-universe composition.

Stage 5A consumes only the already-frozen Stage 1-4 decision chain.

Before any candidate decision row is parsed, the wrapper verifies physical
decision-artifact identities and writes Stage 5A predecision provenance.

Stage 5A does not consult baseline membership, reconstruct historical absence
membership, generate the final external holdout, calculate structural
features, or calculate selector outcomes.
"""

from __future__ import annotations

import argparse
from collections import Counter
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

from bacselect import source_chromosome_integrity
from bacselect import source_complete_universe
from bacselect import source_truth
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    BIOSAMPLE_NONREPRESENTATIVE,
    BIOSAMPLE_UNRESOLVED,
    TAXONOMY_PASS,
    TAXONOMY_UNRESOLVED,
    BioSampleDecision,
    TaxonomyDecision,
)
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


STAGE5_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-stage5-complete-universe-baseline-intersection.md"
)

STAGE5A_HELPER_RELATIVE = Path(
    "src/bacselect/source_complete_universe.py"
)

STAGE5A_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/run_complete_universe_execution.py"
)

STAGE5A_WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_complete_universe_execution.py"
)

SOURCE_TRUTH_EXECUTION_RELATIVE = Path(
    "src/bacselect/source_truth_execution.py"
)

POST_SEQUENCE_RELATIVE = Path(
    "src/bacselect/source_post_sequence_eligibility.py"
)

CHROMOSOME_PRIMITIVE_RELATIVE = Path(
    "src/bacselect/source_chromosome_integrity.py"
)

TAXONOMY_EXECUTION_RELATIVE = Path(
    "src/bacselect/source_taxonomy_execution.py"
)

STAGE1_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/run_source_truth_execution.py"
)

STAGE2_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/run_repeated_biosample_execution.py"
)

STAGE3_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/run_chromosome_integrity_execution.py"
)

STAGE4_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/run_taxonomy_resolution_execution.py"
)

STAGE1_COMPLETION_RELATIVE = Path(
    "validation/selector-v1/"
    "stage1-source-truth-completion-evidence.json"
)

STAGE2_COMPLETION_RELATIVE = Path(
    "validation/selector-v1/"
    "stage2-repeated-biosample-completion-evidence.json"
)

STAGE3_COMPLETION_RELATIVE = Path(
    "validation/selector-v1/"
    "stage3-chromosome-integrity-completion-evidence.json"
)

STAGE4_COMPLETION_RELATIVE = Path(
    "validation/selector-v1/"
    "stage4-taxonomy-resolution-completion-evidence.json"
)


EXPECTED_STAGE5_METHOD_SHA256 = (
    "a1741531205778b6db2c97554d598216"
    "ff3396359b77ba431444e1f96f014718"
)

EXPECTED_STAGE5A_HELPER_SHA256 = (
    "024354a0e909e5a048fa1a408c809a3c"
    "772892c9cf9b517263bdbbe90c476bce"
)

EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256 = (
    "83b8ec7fce774c0b68cb2af982aef139"
    "04c6b64b3ee695512c578f98e5de9b92"
)

EXPECTED_POST_SEQUENCE_SHA256 = (
    "62fa1e2f7d806f94b5f5eca73fb768745"
    "d3913a4b218a4d354562033cd300fe8"
)

EXPECTED_CHROMOSOME_PRIMITIVE_SHA256 = (
    "04f1b580ec9480a20f3679b7eb996da08"
    "a074c48ff246549df2e0ed20b97b9c0"
)

EXPECTED_TAXONOMY_EXECUTION_SHA256 = (
    "426e42c87a58f454fbc8107b275623426"
    "81bea06cc38428bd884d8372b1e43a1"
)

EXPECTED_STAGE1_WRAPPER_SHA256 = (
    "59dd3ea140ee9a49c86dbed8106397280"
    "00add8ac30121ab41d2c59e328961d5"
)

EXPECTED_STAGE2_WRAPPER_SHA256 = (
    "5e5f51891e5348e62bc53dfacc28f572"
    "16f2e0f38ef69d3ce686121ed6aff355"
)

EXPECTED_STAGE3_WRAPPER_SHA256 = (
    "b08610d72e1ff0ba5c06561c537c4f51"
    "50bae7698f1d9c7fdfef57720f4eed80"
)

EXPECTED_STAGE4_WRAPPER_SHA256 = (
    "c010a5c224ca57b961d6fe69468dfbaa7"
    "5b38a74e405192cc90c6fa3e6137661"
)

EXPECTED_STAGE1_COMPLETION_SHA256 = (
    "b459801d832137fb0399bc34dfe361163"
    "6ca1ffc0339c802a16a6216f9595dd2"
)

EXPECTED_STAGE2_COMPLETION_SHA256 = (
    "d00801b1833c6c3cdee44a8c981d9eb1"
    "fc900f6becabc6d59e996877462d76a6"
)

EXPECTED_STAGE3_COMPLETION_SHA256 = (
    "c5aff0e1e5cca6202688198a49069b1a"
    "e3e7b35d19f4939538d7c3f01ff562d2"
)

EXPECTED_STAGE4_COMPLETION_SHA256 = (
    "b878dd9f20c01867b87265b9d35c23db"
    "5ad556621c5750a0193d9e1f2b5960ad"
)

EXPECTED_STAGE1_DECISIONS_SHA256 = (
    "530ccec7679db9866ae04e81f05080094"
    "ace563a530a122c8ae97251801ea96d"
)

EXPECTED_STAGE2_DECISIONS_SHA256 = (
    "3613195996b8d8d1a5d6cbb23976a541"
    "8d97666054aa8ef33601b5ac31a7979a"
)

EXPECTED_STAGE3_DECISIONS_SHA256 = (
    "13d66c0febb809d30862730eff0b419c3"
    "568fc9cdd113970ac441b0fce748f04"
)

EXPECTED_STAGE4_DECISIONS_SHA256 = (
    "74ddebdb1ff0d2f9aedaf564c2622ce74"
    "8795fdb43aa19e2bcef0c4b35788ade"
)

EXPECTED_STAGE1_MEMBERSHIP_SHA256 = (
    "810c584d578bad678e3a9ef3131e13777"
    "444961b906a57f5b2cbdcafd691e324"
)

EXPECTED_STAGE2_INPUT_MEMBERSHIP_SHA256 = (
    "8ce5d8c03029beb6934aad8688ac63d75"
    "026be6f1377a96de43d3b41db8ba5f3"
)

EXPECTED_STAGE3_INPUT_MEMBERSHIP_SHA256 = (
    "e86944d3e8b0407a7901c1a996f7adb4"
    "2eeda3efffd3384fec7a8d87859209f4"
)

EXPECTED_STAGE4_INPUT_MEMBERSHIP_SHA256 = (
    "05c81053608a4c21fcacc80f774c92503"
    "979ee510098b8072c9e103ef07e798a"
)


STAGE1_DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "source_evidence_sha256",
    "sequence_set_sha256",
    "duplicate_relation_count",
    "containment_relation_count",
    "source_truth_status",
    "source_truth_reason",
)

STAGE2_DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "biosample",
    "source_evidence_sha256",
    "assembly_fingerprint",
    "stage2_status",
    "stage2_reason",
)

STAGE3_DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "source_evidence_sha256",
    "stage2_status",
    "chromosome_component_count",
    "closure_supported_chromosome_count",
    "closure_unsupported_chromosome_count",
    "chromosome_integrity_triggered",
    "historical_adjudication_reused",
    "stage3_status",
    "stage3_reason",
)

STAGE4_DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "organism_taxid",
    "normalized_organism_taxid",
    "species_taxid",
    "stage4_status",
    "stage4_reason",
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

GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)


class Stage5AWrapperError(RuntimeError):
    """Raised when Stage 5A orchestration fails closed."""


@dataclass(frozen=True)
class Stage5AExpectations:
    stage1_total: int
    stage1_suitable: int
    stage1_excluded: int
    stage1_unresolved: int
    stage2_total: int
    stage2_continue: int
    stage2_nonrepresentative: int
    stage2_unresolved: int
    stage3_total: int
    stage3_pass: int
    stage3_excluded: int
    stage3_unresolved: int
    stage4_total: int
    stage4_pass: int
    stage4_unresolved: int
    complete_species_count: int
    stage1_membership_sha256: str
    stage2_input_membership_sha256: str
    stage3_input_membership_sha256: str
    stage4_input_membership_sha256: str


PRODUCTION_EXPECTATIONS = Stage5AExpectations(
    stage1_total=68_480,
    stage1_suitable=68_359,
    stage1_excluded=121,
    stage1_unresolved=0,
    stage2_total=68_359,
    stage2_continue=68_278,
    stage2_nonrepresentative=6,
    stage2_unresolved=75,
    stage3_total=68_278,
    stage3_pass=68_175,
    stage3_excluded=33,
    stage3_unresolved=70,
    stage4_total=68_175,
    stage4_pass=67_957,
    stage4_unresolved=218,
    complete_species_count=16_144,
    stage1_membership_sha256=EXPECTED_STAGE1_MEMBERSHIP_SHA256,
    stage2_input_membership_sha256=(
        EXPECTED_STAGE2_INPUT_MEMBERSHIP_SHA256
    ),
    stage3_input_membership_sha256=(
        EXPECTED_STAGE3_INPUT_MEMBERSHIP_SHA256
    ),
    stage4_input_membership_sha256=(
        EXPECTED_STAGE4_INPUT_MEMBERSHIP_SHA256
    ),
)


@dataclass(frozen=True)
class DecisionArtifactIdentities:
    stage1: str
    stage2: str
    stage3: str
    stage4: str


PRODUCTION_DECISION_IDENTITIES = DecisionArtifactIdentities(
    stage1=EXPECTED_STAGE1_DECISIONS_SHA256,
    stage2=EXPECTED_STAGE2_DECISIONS_SHA256,
    stage3=EXPECTED_STAGE3_DECISIONS_SHA256,
    stage4=EXPECTED_STAGE4_DECISIONS_SHA256,
)


@dataclass(frozen=True)
class DecisionPaths:
    stage1: Path
    stage2: Path
    stage3: Path
    stage4: Path


@dataclass(frozen=True)
class Stage1Decision:
    status: str
    reason: str


@dataclass(frozen=True)
class Stage3Decision:
    status: str
    reason: str
    triggered: bool
    historical_adjudication_reused: bool


@dataclass(frozen=True)
class Stage1Bundle:
    decisions: Mapping[str, Stage1Decision]
    all_membership_sha256: str
    suitable_membership_sha256: str


@dataclass(frozen=True)
class Stage2Bundle:
    decisions: Mapping[str, BioSampleDecision]
    all_membership_sha256: str
    continue_membership_sha256: str


@dataclass(frozen=True)
class Stage3Bundle:
    decisions: Mapping[str, Stage3Decision]
    all_membership_sha256: str
    pass_membership_sha256: str


@dataclass(frozen=True)
class Stage4Bundle:
    decisions: Mapping[str, TaxonomyDecision]
    all_membership_sha256: str
    pass_membership_sha256: str
    pass_species_count: int


@dataclass(frozen=True)
class DecisionChain:
    stage1: Stage1Bundle
    stage2: Stage2Bundle
    stage3: Stage3Bundle
    stage4: Stage4Bundle


FROZEN_REPO_FILES = {
    STAGE5_METHOD_RELATIVE:
        EXPECTED_STAGE5_METHOD_SHA256,
    STAGE5A_HELPER_RELATIVE:
        EXPECTED_STAGE5A_HELPER_SHA256,
    SOURCE_TRUTH_EXECUTION_RELATIVE:
        EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256,
    POST_SEQUENCE_RELATIVE:
        EXPECTED_POST_SEQUENCE_SHA256,
    CHROMOSOME_PRIMITIVE_RELATIVE:
        EXPECTED_CHROMOSOME_PRIMITIVE_SHA256,
    TAXONOMY_EXECUTION_RELATIVE:
        EXPECTED_TAXONOMY_EXECUTION_SHA256,
    STAGE1_WRAPPER_RELATIVE:
        EXPECTED_STAGE1_WRAPPER_SHA256,
    STAGE2_WRAPPER_RELATIVE:
        EXPECTED_STAGE2_WRAPPER_SHA256,
    STAGE3_WRAPPER_RELATIVE:
        EXPECTED_STAGE3_WRAPPER_SHA256,
    STAGE4_WRAPPER_RELATIVE:
        EXPECTED_STAGE4_WRAPPER_SHA256,
    STAGE1_COMPLETION_RELATIVE:
        EXPECTED_STAGE1_COMPLETION_SHA256,
    STAGE2_COMPLETION_RELATIVE:
        EXPECTED_STAGE2_COMPLETION_SHA256,
    STAGE3_COMPLETION_RELATIVE:
        EXPECTED_STAGE3_COMPLETION_SHA256,
    STAGE4_COMPLETION_RELATIVE:
        EXPECTED_STAGE4_COMPLETION_SHA256,
}


def sha256_file(
    path: Path | str,
) -> str:
    """Return SHA256 for one required regular file."""

    source = Path(path)

    if (
        not source.is_file()
        or source.is_symlink()
    ):
        raise Stage5AWrapperError(
            f"required regular file missing: {source}"
        )

    digest = hashlib.sha256()

    with source.open("rb") as handle:
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
    expected: str,
    label: str,
) -> str:
    """Fail unless a file has exactly the expected SHA256."""

    if (
        not isinstance(expected, str)
        or LOWER_SHA256_RE.fullmatch(
            expected
        ) is None
    ):
        raise Stage5AWrapperError(
            f"{label} expected SHA256 malformed"
        )

    observed = sha256_file(
        path
    )

    if observed != expected:
        raise Stage5AWrapperError(
            f"{label} SHA256 mismatch"
        )

    return observed


def _nonempty(
    value: object,
    *,
    label: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise Stage5AWrapperError(
            f"{label} must be a string"
        )

    cleaned = value.strip()

    if not cleaned:
        raise Stage5AWrapperError(
            f"{label} must not be empty"
        )

    return cleaned


def _canonical_accession(
    value: object,
    *,
    label: str,
) -> str:
    accession = _nonempty(
        value,
        label=label,
    )

    if GCA_RE.fullmatch(
        accession
    ) is None:
        raise Stage5AWrapperError(
            f"{label} must be a versioned GCA accession"
        )

    return accession


def _lower_sha256(
    value: object,
    *,
    label: str,
) -> str:
    sha = _nonempty(
        value,
        label=label,
    )

    if LOWER_SHA256_RE.fullmatch(
        sha
    ) is None:
        raise Stage5AWrapperError(
            f"{label} must be lowercase SHA256"
        )

    return sha


def _nonnegative_int(
    value: object,
    *,
    label: str,
) -> int:
    try:
        result = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise Stage5AWrapperError(
            f"{label} must be a non-negative integer"
        ) from exc

    if result < 0:
        raise Stage5AWrapperError(
            f"{label} must be a non-negative integer"
        )

    return result


def _positive_int(
    value: object,
    *,
    label: str,
) -> int:
    result = _nonnegative_int(
        value,
        label=label,
    )

    if result <= 0:
        raise Stage5AWrapperError(
            f"{label} must be a positive integer"
        )

    return result


def _optional_positive_int(
    value: object,
    *,
    label: str,
) -> int | None:
    if value in (
        "",
        None,
    ):
        return None

    return _positive_int(
        value,
        label=label,
    )


def _strict_bool(
    value: object,
    *,
    label: str,
) -> bool:
    if value in (
        True,
        "true",
        "True",
        "1",
    ):
        return True

    if value in (
        False,
        "false",
        "False",
        "0",
    ):
        return False

    raise Stage5AWrapperError(
        f"{label} must be a strict boolean"
    )


def _expected_counter(
    values: Mapping[str, int],
) -> Counter:
    return Counter(
        {
            key:
                value
            for key, value in values.items()
            if value
        }
    )


def read_tsv_exact(
    path: Path | str,
    fields: Sequence[str],
    *,
    label: str,
) -> list[dict[str, str]]:
    """Read one exact TSV schema."""

    source = Path(path)

    try:
        with source.open(
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
                raise Stage5AWrapperError(
                    f"{label} field schema mismatch"
                )

            rows = [
                dict(
                    row
                )
                for row in reader
            ]

    except (
        OSError,
        UnicodeError,
        csv.Error,
    ) as exc:
        raise Stage5AWrapperError(
            f"cannot parse {label}"
        ) from exc

    return rows


def write_json_atomic(
    path: Path,
    payload: Mapping[str, object],
) -> str:
    """Write deterministic JSON and return its SHA256."""

    path = Path(path)
    temporary = path.with_name(
        "." + path.name + ".tmp"
    )

    if temporary.exists():
        raise Stage5AWrapperError(
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
    """Write deterministic TSV and return its SHA256."""

    path = Path(path)
    temporary = path.with_name(
        "." + path.name + ".tmp"
    )

    if temporary.exists():
        raise Stage5AWrapperError(
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
                    raise Stage5AWrapperError(
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


def _load_json(
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
        raise Stage5AWrapperError(
            f"cannot parse {label}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise Stage5AWrapperError(
            f"{label} must be a JSON object"
        )

    return payload


def load_production_completion_evidence(
    repo: Path,
) -> Mapping[str, Mapping[str, object]]:
    """Load and validate aggregate-only frozen Stage 1-4 checkpoints."""

    repo = Path(
        repo
    ).resolve()

    stage1 = _load_json(
        repo / STAGE1_COMPLETION_RELATIVE,
        expected_sha256=(
            EXPECTED_STAGE1_COMPLETION_SHA256
        ),
        label="Stage 1 completion evidence",
    )

    stage2 = _load_json(
        repo / STAGE2_COMPLETION_RELATIVE,
        expected_sha256=(
            EXPECTED_STAGE2_COMPLETION_SHA256
        ),
        label="Stage 2 completion evidence",
    )

    stage3 = _load_json(
        repo / STAGE3_COMPLETION_RELATIVE,
        expected_sha256=(
            EXPECTED_STAGE3_COMPLETION_SHA256
        ),
        label="Stage 3 completion evidence",
    )

    stage4 = _load_json(
        repo / STAGE4_COMPLETION_RELATIVE,
        expected_sha256=(
            EXPECTED_STAGE4_COMPLETION_SHA256
        ),
        label="Stage 4 completion evidence",
    )

    if (
        stage1.get("schema_version") != 1
        or stage1.get("status")
        != "STAGE1_SOURCE_TRUTH_COMPLETE"
        or stage1.get("candidate_count")
        != PRODUCTION_EXPECTATIONS.stage1_total
        or stage1.get("decision_row_count")
        != PRODUCTION_EXPECTATIONS.stage1_total
        or stage1.get("status_counts")
        != {
            "EXCLUDE_SOURCE_TRUTH":
                PRODUCTION_EXPECTATIONS.stage1_excluded,
            "SUITABLE":
                PRODUCTION_EXPECTATIONS.stage1_suitable,
        }
    ):
        raise Stage5AWrapperError(
            "Stage 1 completion accounting mismatch"
        )

    stage1_membership = stage1.get(
        "membership_sha256"
    )

    if (
        not isinstance(
            stage1_membership,
            Mapping,
        )
        or stage1_membership.get(
            "combined"
        )
        != PRODUCTION_EXPECTATIONS.stage1_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 1 completion membership mismatch"
        )

    stage1_artifacts = stage1.get(
        "artifacts_sha256"
    )

    if (
        not isinstance(
            stage1_artifacts,
            Mapping,
        )
        or stage1_artifacts.get(
            "stage1-source-truth-decisions.tsv"
        )
        != EXPECTED_STAGE1_DECISIONS_SHA256
    ):
        raise Stage5AWrapperError(
            "Stage 1 completion decision binding mismatch"
        )

    if (
        stage2.get("schema_version") != 1
        or stage2.get("status")
        != "STAGE2_REPEATED_BIOSAMPLE_COMPLETE"
        or stage2.get("stage2_input_candidate_count")
        != PRODUCTION_EXPECTATIONS.stage2_total
        or stage2.get("decision_row_count")
        != PRODUCTION_EXPECTATIONS.stage2_total
        or stage2.get("continue_count")
        != PRODUCTION_EXPECTATIONS.stage2_continue
        or stage2.get("nonrepresentative_count")
        != PRODUCTION_EXPECTATIONS.stage2_nonrepresentative
        or stage2.get("review_unresolved_count")
        != PRODUCTION_EXPECTATIONS.stage2_unresolved
        or stage2.get("stage2_input_membership_sha256")
        != PRODUCTION_EXPECTATIONS.stage2_input_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 2 completion accounting mismatch"
        )

    if stage2.get(
        "status_counts"
    ) != {
        BIOSAMPLE_CONTINUE:
            PRODUCTION_EXPECTATIONS.stage2_continue,
        BIOSAMPLE_NONREPRESENTATIVE:
            PRODUCTION_EXPECTATIONS.stage2_nonrepresentative,
        BIOSAMPLE_UNRESOLVED:
            PRODUCTION_EXPECTATIONS.stage2_unresolved,
    }:
        raise Stage5AWrapperError(
            "Stage 2 completion status counts mismatch"
        )

    stage2_artifacts = stage2.get(
        "artifacts_sha256"
    )

    if (
        not isinstance(
            stage2_artifacts,
            Mapping,
        )
        or stage2_artifacts.get(
            "stage2-repeated-biosample-decisions.tsv"
        )
        != EXPECTED_STAGE2_DECISIONS_SHA256
    ):
        raise Stage5AWrapperError(
            "Stage 2 completion decision binding mismatch"
        )

    if (
        stage3.get("schema_version") != 1
        or stage3.get("status")
        != "STAGE3_CHROMOSOME_INTEGRITY_COMPLETE"
        or stage3.get("stage3_input_candidate_count")
        != PRODUCTION_EXPECTATIONS.stage3_total
        or stage3.get("decision_row_count")
        != PRODUCTION_EXPECTATIONS.stage3_total
        or stage3.get("pass_count")
        != PRODUCTION_EXPECTATIONS.stage3_pass
        or stage3.get("exclude_source_replicon_integrity_count")
        != PRODUCTION_EXPECTATIONS.stage3_excluded
        or stage3.get("review_unresolved_count")
        != PRODUCTION_EXPECTATIONS.stage3_unresolved
        or stage3.get("stage3_input_membership_sha256")
        != PRODUCTION_EXPECTATIONS.stage3_input_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 3 completion accounting mismatch"
        )

    if stage3.get(
        "status_counts"
    ) != {
        source_chromosome_integrity.EXCLUDE:
            PRODUCTION_EXPECTATIONS.stage3_excluded,
        source_chromosome_integrity.PASS:
            PRODUCTION_EXPECTATIONS.stage3_pass,
        source_chromosome_integrity.UNRESOLVED:
            PRODUCTION_EXPECTATIONS.stage3_unresolved,
    }:
        raise Stage5AWrapperError(
            "Stage 3 completion status counts mismatch"
        )

    stage3_artifacts = stage3.get(
        "artifacts_sha256"
    )

    if (
        not isinstance(
            stage3_artifacts,
            Mapping,
        )
        or stage3_artifacts.get(
            "stage3-chromosome-integrity-decisions.tsv"
        )
        != EXPECTED_STAGE3_DECISIONS_SHA256
    ):
        raise Stage5AWrapperError(
            "Stage 3 completion decision binding mismatch"
        )

    if (
        stage4.get("schema_version") != 1
        or stage4.get("status")
        != "STAGE4_TAXONOMY_RESOLUTION_COMPLETE"
        or stage4.get("stage4_input_candidate_count")
        != PRODUCTION_EXPECTATIONS.stage4_total
        or stage4.get("decision_row_count")
        != PRODUCTION_EXPECTATIONS.stage4_total
        or stage4.get("pass_count")
        != PRODUCTION_EXPECTATIONS.stage4_pass
        or stage4.get("review_unresolved_count")
        != PRODUCTION_EXPECTATIONS.stage4_unresolved
        or stage4.get("resolved_distinct_species_taxid_count")
        != PRODUCTION_EXPECTATIONS.complete_species_count
        or stage4.get("stage4_input_membership_sha256")
        != PRODUCTION_EXPECTATIONS.stage4_input_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 4 completion accounting mismatch"
        )

    if stage4.get(
        "status_counts"
    ) != {
        TAXONOMY_PASS:
            PRODUCTION_EXPECTATIONS.stage4_pass,
        TAXONOMY_UNRESOLVED:
            PRODUCTION_EXPECTATIONS.stage4_unresolved,
    }:
        raise Stage5AWrapperError(
            "Stage 4 completion status counts mismatch"
        )

    stage4_artifacts = stage4.get(
        "artifacts_sha256"
    )

    if (
        not isinstance(
            stage4_artifacts,
            Mapping,
        )
        or stage4_artifacts.get(
            "stage4-taxonomy-decisions.tsv"
        )
        != EXPECTED_STAGE4_DECISIONS_SHA256
    ):
        raise Stage5AWrapperError(
            "Stage 4 completion decision binding mismatch"
        )

    return {
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
        "stage4": stage4,
    }


def preflight_repository(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> Mapping[str, str]:
    """Require exact clean repository and frozen implementation identities."""

    repo = Path(
        repo
    ).resolve()

    if LOWER_COMMIT_RE.fullmatch(
        expected_commit
    ) is None:
        raise Stage5AWrapperError(
            "expected Git commit malformed"
        )

    try:
        head = subprocess.check_output(
            [
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "HEAD",
            ],
            text=True,
        ).strip()

        origin_main = subprocess.check_output(
            [
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "origin/main",
            ],
            text=True,
        ).strip()

        status = subprocess.check_output(
            [
                "git",
                "-C",
                str(repo),
                "status",
                "--porcelain",
            ],
            text=True,
        )

    except subprocess.CalledProcessError as exc:
        raise Stage5AWrapperError(
            "cannot verify repository state"
        ) from exc

    if (
        head != expected_commit
        or origin_main != expected_commit
    ):
        raise Stage5AWrapperError(
            "repository commit boundary mismatch"
        )

    if status:
        raise Stage5AWrapperError(
            "repository is not clean"
        )

    frozen: dict[str, str] = {}

    for relative, expected_sha in (
        FROZEN_REPO_FILES.items()
    ):
        require_sha256(
            repo / relative,
            expected_sha,
            f"frozen repository file {relative}",
        )

        frozen[
            relative.as_posix()
        ] = expected_sha

    require_sha256(
        repo / STAGE5A_WRAPPER_RELATIVE,
        expected_wrapper_sha256,
        "Stage 5A production wrapper",
    )

    require_sha256(
        repo / STAGE5A_WRAPPER_TEST_RELATIVE,
        expected_wrapper_test_sha256,
        "Stage 5A production-wrapper tests",
    )

    frozen[
        STAGE5A_WRAPPER_RELATIVE.as_posix()
    ] = expected_wrapper_sha256

    frozen[
        STAGE5A_WRAPPER_TEST_RELATIVE.as_posix()
    ] = expected_wrapper_test_sha256

    return dict(
        sorted(
            frozen.items()
        )
    )


def _load_stage1(
    path: Path,
    *,
    expected_sha256: str,
    expectations: Stage5AExpectations,
) -> Stage1Bundle:
    require_sha256(
        path,
        expected_sha256,
        "Stage 1 decisions",
    )

    rows = read_tsv_exact(
        path,
        STAGE1_DECISION_FIELDS,
        label="Stage 1 decisions",
    )

    if len(
        rows
    ) != expectations.stage1_total:
        raise Stage5AWrapperError(
            "Stage 1 decision row count mismatch"
        )

    decisions: dict[
        str,
        Stage1Decision
    ] = {}

    status_counts = Counter()

    for row in rows:
        accession = _canonical_accession(
            row[
                "canonical_genbank_assembly_accession"
            ],
            label="Stage 1 accession",
        )

        if accession in decisions:
            raise Stage5AWrapperError(
                "duplicate Stage 1 accession"
            )

        _lower_sha256(
            row[
                "source_evidence_sha256"
            ],
            label="Stage 1 source evidence SHA256",
        )

        _lower_sha256(
            row[
                "sequence_set_sha256"
            ],
            label="Stage 1 sequence-set SHA256",
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

        status = _nonempty(
            row[
                "source_truth_status"
            ],
            label="Stage 1 status",
        )

        if status not in {
            source_truth.SUITABLE,
            source_truth.EXCLUDE,
            source_truth.UNRESOLVED,
        }:
            raise Stage5AWrapperError(
                "unexpected Stage 1 status"
            )

        reason = _nonempty(
            row[
                "source_truth_reason"
            ],
            label="Stage 1 reason",
        )

        decisions[
            accession
        ] = Stage1Decision(
            status=status,
            reason=reason,
        )

        status_counts[
            status
        ] += 1

    expected_status = _expected_counter(
        {
            source_truth.SUITABLE:
                expectations.stage1_suitable,
            source_truth.EXCLUDE:
                expectations.stage1_excluded,
            source_truth.UNRESOLVED:
                expectations.stage1_unresolved,
        }
    )

    if status_counts != expected_status:
        raise Stage5AWrapperError(
            "Stage 1 status accounting mismatch"
        )

    all_accessions = tuple(
        sorted(
            decisions
        )
    )

    suitable_accessions = tuple(
        sorted(
            accession
            for accession, decision
            in decisions.items()
            if decision.status
            == source_truth.SUITABLE
        )
    )

    all_membership = accession_membership_sha256(
        all_accessions
    )

    suitable_membership = accession_membership_sha256(
        suitable_accessions
    )

    if (
        all_membership
        != expectations.stage1_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 1 population membership mismatch"
        )

    if (
        suitable_membership
        != expectations.stage2_input_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 1 suitable membership mismatch"
        )

    return Stage1Bundle(
        decisions=dict(
            sorted(
                decisions.items()
            )
        ),
        all_membership_sha256=all_membership,
        suitable_membership_sha256=suitable_membership,
    )


def _load_stage2(
    path: Path,
    *,
    expected_sha256: str,
    expectations: Stage5AExpectations,
) -> Stage2Bundle:
    require_sha256(
        path,
        expected_sha256,
        "Stage 2 decisions",
    )

    rows = read_tsv_exact(
        path,
        STAGE2_DECISION_FIELDS,
        label="Stage 2 decisions",
    )

    if len(
        rows
    ) != expectations.stage2_total:
        raise Stage5AWrapperError(
            "Stage 2 decision row count mismatch"
        )

    decisions: dict[
        str,
        BioSampleDecision
    ] = {}

    status_counts = Counter()

    for row in rows:
        accession = _canonical_accession(
            row[
                "canonical_genbank_assembly_accession"
            ],
            label="Stage 2 accession",
        )

        if accession in decisions:
            raise Stage5AWrapperError(
                "duplicate Stage 2 accession"
            )

        _nonempty(
            row[
                "biosample"
            ],
            label="Stage 2 BioSample",
        )

        _lower_sha256(
            row[
                "source_evidence_sha256"
            ],
            label="Stage 2 source evidence SHA256",
        )

        _lower_sha256(
            row[
                "assembly_fingerprint"
            ],
            label="Stage 2 assembly fingerprint",
        )

        status = _nonempty(
            row[
                "stage2_status"
            ],
            label="Stage 2 status",
        )

        if status not in {
            BIOSAMPLE_CONTINUE,
            BIOSAMPLE_NONREPRESENTATIVE,
            BIOSAMPLE_UNRESOLVED,
        }:
            raise Stage5AWrapperError(
                "unexpected Stage 2 status"
            )

        reason = _nonempty(
            row[
                "stage2_reason"
            ],
            label="Stage 2 reason",
        )

        decisions[
            accession
        ] = BioSampleDecision(
            status=status,
            reason=reason,
        )

        status_counts[
            status
        ] += 1

    expected_status = _expected_counter(
        {
            BIOSAMPLE_CONTINUE:
                expectations.stage2_continue,
            BIOSAMPLE_NONREPRESENTATIVE:
                expectations.stage2_nonrepresentative,
            BIOSAMPLE_UNRESOLVED:
                expectations.stage2_unresolved,
        }
    )

    if status_counts != expected_status:
        raise Stage5AWrapperError(
            "Stage 2 status accounting mismatch"
        )

    all_accessions = tuple(
        sorted(
            decisions
        )
    )

    continue_accessions = tuple(
        sorted(
            accession
            for accession, decision
            in decisions.items()
            if decision.status
            == BIOSAMPLE_CONTINUE
        )
    )

    all_membership = accession_membership_sha256(
        all_accessions
    )

    continue_membership = accession_membership_sha256(
        continue_accessions
    )

    if (
        all_membership
        != expectations.stage2_input_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 2 input membership mismatch"
        )

    if (
        continue_membership
        != expectations.stage3_input_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 2 CONTINUE membership mismatch"
        )

    return Stage2Bundle(
        decisions=dict(
            sorted(
                decisions.items()
            )
        ),
        all_membership_sha256=all_membership,
        continue_membership_sha256=continue_membership,
    )


def _load_stage3(
    path: Path,
    *,
    expected_sha256: str,
    expectations: Stage5AExpectations,
) -> Stage3Bundle:
    require_sha256(
        path,
        expected_sha256,
        "Stage 3 decisions",
    )

    rows = read_tsv_exact(
        path,
        STAGE3_DECISION_FIELDS,
        label="Stage 3 decisions",
    )

    if len(
        rows
    ) != expectations.stage3_total:
        raise Stage5AWrapperError(
            "Stage 3 decision row count mismatch"
        )

    decisions: dict[
        str,
        Stage3Decision
    ] = {}

    status_counts = Counter()

    for row in rows:
        accession = _canonical_accession(
            row[
                "canonical_genbank_assembly_accession"
            ],
            label="Stage 3 accession",
        )

        if accession in decisions:
            raise Stage5AWrapperError(
                "duplicate Stage 3 accession"
            )

        _lower_sha256(
            row[
                "source_evidence_sha256"
            ],
            label="Stage 3 source evidence SHA256",
        )

        if row[
            "stage2_status"
        ] != BIOSAMPLE_CONTINUE:
            raise Stage5AWrapperError(
                "Stage 3 row does not carry Stage 2 CONTINUE"
            )

        chromosome_count = _nonnegative_int(
            row[
                "chromosome_component_count"
            ],
            label="Stage 3 chromosome component count",
        )

        closure_supported = _nonnegative_int(
            row[
                "closure_supported_chromosome_count"
            ],
            label="Stage 3 closure-supported count",
        )

        closure_unsupported = _nonnegative_int(
            row[
                "closure_unsupported_chromosome_count"
            ],
            label="Stage 3 closure-unsupported count",
        )

        if (
            closure_supported
            + closure_unsupported
            != chromosome_count
        ):
            raise Stage5AWrapperError(
                "Stage 3 chromosome accounting mismatch"
            )

        triggered = _strict_bool(
            row[
                "chromosome_integrity_triggered"
            ],
            label="Stage 3 trigger",
        )

        reused = _strict_bool(
            row[
                "historical_adjudication_reused"
            ],
            label="Stage 3 historical reuse",
        )

        status = _nonempty(
            row[
                "stage3_status"
            ],
            label="Stage 3 status",
        )

        if status not in {
            source_chromosome_integrity.PASS,
            source_chromosome_integrity.EXCLUDE,
            source_chromosome_integrity.UNRESOLVED,
        }:
            raise Stage5AWrapperError(
                "unexpected Stage 3 status"
            )

        reason = _nonempty(
            row[
                "stage3_reason"
            ],
            label="Stage 3 reason",
        )

        decisions[
            accession
        ] = Stage3Decision(
            status=status,
            reason=reason,
            triggered=triggered,
            historical_adjudication_reused=reused,
        )

        status_counts[
            status
        ] += 1

    expected_status = _expected_counter(
        {
            source_chromosome_integrity.PASS:
                expectations.stage3_pass,
            source_chromosome_integrity.EXCLUDE:
                expectations.stage3_excluded,
            source_chromosome_integrity.UNRESOLVED:
                expectations.stage3_unresolved,
        }
    )

    if status_counts != expected_status:
        raise Stage5AWrapperError(
            "Stage 3 status accounting mismatch"
        )

    all_accessions = tuple(
        sorted(
            decisions
        )
    )

    pass_accessions = tuple(
        sorted(
            accession
            for accession, decision
            in decisions.items()
            if decision.status
            == source_chromosome_integrity.PASS
        )
    )

    all_membership = accession_membership_sha256(
        all_accessions
    )

    pass_membership = accession_membership_sha256(
        pass_accessions
    )

    if (
        all_membership
        != expectations.stage3_input_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 3 input membership mismatch"
        )

    if (
        pass_membership
        != expectations.stage4_input_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 3 PASS membership mismatch"
        )

    return Stage3Bundle(
        decisions=dict(
            sorted(
                decisions.items()
            )
        ),
        all_membership_sha256=all_membership,
        pass_membership_sha256=pass_membership,
    )


def _load_stage4(
    path: Path,
    *,
    expected_sha256: str,
    expectations: Stage5AExpectations,
) -> Stage4Bundle:
    require_sha256(
        path,
        expected_sha256,
        "Stage 4 decisions",
    )

    rows = read_tsv_exact(
        path,
        STAGE4_DECISION_FIELDS,
        label="Stage 4 decisions",
    )

    if len(
        rows
    ) != expectations.stage4_total:
        raise Stage5AWrapperError(
            "Stage 4 decision row count mismatch"
        )

    decisions: dict[
        str,
        TaxonomyDecision
    ] = {}

    status_counts = Counter()
    pass_species: set[int] = set()

    for row in rows:
        accession = _canonical_accession(
            row[
                "canonical_genbank_assembly_accession"
            ],
            label="Stage 4 accession",
        )

        if accession in decisions:
            raise Stage5AWrapperError(
                "duplicate Stage 4 accession"
            )

        _positive_int(
            row[
                "organism_taxid"
            ],
            label="Stage 4 organism TaxID",
        )

        normalized = _optional_positive_int(
            row[
                "normalized_organism_taxid"
            ],
            label="Stage 4 normalized organism TaxID",
        )

        species = _optional_positive_int(
            row[
                "species_taxid"
            ],
            label="Stage 4 species TaxID",
        )

        status = _nonempty(
            row[
                "stage4_status"
            ],
            label="Stage 4 status",
        )

        reason = _nonempty(
            row[
                "stage4_reason"
            ],
            label="Stage 4 reason",
        )

        if status == TAXONOMY_PASS:
            if (
                reason
                != "TAXONOMY_SPECIES_RESOLVED"
                or normalized is None
                or species is None
            ):
                raise Stage5AWrapperError(
                    "malformed Stage 4 PASS decision"
                )

            pass_species.add(
                species
            )

        elif status == TAXONOMY_UNRESOLVED:
            if species is not None:
                raise Stage5AWrapperError(
                    "unresolved Stage 4 row contains species TaxID"
                )

            if not reason.startswith(
                "TAXONOMY_"
            ):
                raise Stage5AWrapperError(
                    "malformed Stage 4 unresolved reason"
                )

        else:
            raise Stage5AWrapperError(
                "unexpected Stage 4 status"
            )

        decisions[
            accession
        ] = TaxonomyDecision(
            status=status,
            reason=reason,
            normalized_taxid=normalized,
            species_taxid=species,
        )

        status_counts[
            status
        ] += 1

    expected_status = _expected_counter(
        {
            TAXONOMY_PASS:
                expectations.stage4_pass,
            TAXONOMY_UNRESOLVED:
                expectations.stage4_unresolved,
        }
    )

    if status_counts != expected_status:
        raise Stage5AWrapperError(
            "Stage 4 status accounting mismatch"
        )

    if len(
        pass_species
    ) != expectations.complete_species_count:
        raise Stage5AWrapperError(
            "Stage 4 resolved species count mismatch"
        )

    all_accessions = tuple(
        sorted(
            decisions
        )
    )

    pass_accessions = tuple(
        sorted(
            accession
            for accession, decision
            in decisions.items()
            if decision.status
            == TAXONOMY_PASS
        )
    )

    all_membership = accession_membership_sha256(
        all_accessions
    )

    pass_membership = accession_membership_sha256(
        pass_accessions
    )

    if (
        all_membership
        != expectations.stage4_input_membership_sha256
    ):
        raise Stage5AWrapperError(
            "Stage 4 input membership mismatch"
        )

    return Stage4Bundle(
        decisions=dict(
            sorted(
                decisions.items()
            )
        ),
        all_membership_sha256=all_membership,
        pass_membership_sha256=pass_membership,
        pass_species_count=len(
            pass_species
        ),
    )


def load_decision_chain(
    paths: DecisionPaths,
    *,
    identities: DecisionArtifactIdentities,
    expectations: Stage5AExpectations,
) -> DecisionChain:
    """Parse and verify the exact chained Stage 1-4 decision populations."""

    stage1 = _load_stage1(
        paths.stage1,
        expected_sha256=identities.stage1,
        expectations=expectations,
    )

    stage2 = _load_stage2(
        paths.stage2,
        expected_sha256=identities.stage2,
        expectations=expectations,
    )

    stage3 = _load_stage3(
        paths.stage3,
        expected_sha256=identities.stage3,
        expectations=expectations,
    )

    stage4 = _load_stage4(
        paths.stage4,
        expected_sha256=identities.stage4,
        expectations=expectations,
    )

    stage1_suitable = {
        accession
        for accession, decision
        in stage1.decisions.items()
        if decision.status
        == source_truth.SUITABLE
    }

    if set(
        stage2.decisions
    ) != stage1_suitable:
        raise Stage5AWrapperError(
            "Stage 2 membership is not exactly Stage 1 SUITABLE"
        )

    stage2_continue = {
        accession
        for accession, decision
        in stage2.decisions.items()
        if decision.status
        == BIOSAMPLE_CONTINUE
    }

    if set(
        stage3.decisions
    ) != stage2_continue:
        raise Stage5AWrapperError(
            "Stage 3 membership is not exactly Stage 2 CONTINUE"
        )

    stage3_pass = {
        accession
        for accession, decision
        in stage3.decisions.items()
        if decision.status
        == source_chromosome_integrity.PASS
    }

    if set(
        stage4.decisions
    ) != stage3_pass:
        raise Stage5AWrapperError(
            "Stage 4 membership is not exactly Stage 3 PASS"
        )

    return DecisionChain(
        stage1=stage1,
        stage2=stage2,
        stage3=stage3,
        stage4=stage4,
    )


def compose_terminal_population(
    chain: DecisionChain,
    *,
    expectations: Stage5AExpectations,
) -> tuple[
    source_complete_universe.TerminalCompositionRecord,
    ...,
]:
    """Compose all Stage 1 candidates through their earliest terminal layer."""

    inputs: list[
        source_complete_universe.CandidateCompositionInput
    ] = []

    for accession in sorted(
        chain.stage1.decisions
    ):
        stage1 = chain.stage1.decisions[
            accession
        ]

        biosample = None
        chromosome = None
        taxonomy = None

        if stage1.status == source_truth.SUITABLE:
            try:
                stage2 = chain.stage2.decisions[
                    accession
                ]
            except KeyError as exc:
                raise Stage5AWrapperError(
                    "Stage 1 SUITABLE candidate lacks Stage 2 decision"
                ) from exc

            biosample = stage2

            if stage2.status == BIOSAMPLE_CONTINUE:
                try:
                    stage3 = chain.stage3.decisions[
                        accession
                    ]
                except KeyError as exc:
                    raise Stage5AWrapperError(
                        "Stage 2 CONTINUE candidate lacks Stage 3 decision"
                    ) from exc

                chromosome = (
                    source_chromosome_integrity
                    .ChromosomeIntegrityDecision(
                        status=stage3.status,
                        reason=stage3.reason,
                        triggered=stage3.triggered,
                        historical_adjudication_reused=(
                            stage3.historical_adjudication_reused
                        ),
                    )
                )

                if (
                    stage3.status
                    == source_chromosome_integrity.PASS
                ):
                    try:
                        taxonomy = chain.stage4.decisions[
                            accession
                        ]
                    except KeyError as exc:
                        raise Stage5AWrapperError(
                            "Stage 3 PASS candidate lacks Stage 4 decision"
                        ) from exc

        inputs.append(
            source_complete_universe.CandidateCompositionInput(
                accession=accession,
                source_truth_status=stage1.status,
                source_truth_reason=stage1.reason,
                biosample=biosample,
                chromosome=chromosome,
                taxonomy=taxonomy,
            )
        )

    try:
        records = (
            source_complete_universe
            .finalize_terminal_composition(
                inputs
            )
        )
    except ValueError as exc:
        raise Stage5AWrapperError(
            "Stage 5A terminal composition failed closed"
        ) from exc

    summary = (
        source_complete_universe
        .disposition_summary(
            records
        )
    )

    source_complete_universe.require_expected_accounting(
        summary,
        expected_total=expectations.stage1_total,
        expected_eligible=expectations.stage4_pass,
        expected_excluded=(
            expectations.stage1_excluded
            + expectations.stage3_excluded
        ),
        expected_withheld_unresolved=(
            expectations.stage1_unresolved
            + expectations.stage2_unresolved
            + expectations.stage3_unresolved
            + expectations.stage4_unresolved
        ),
        expected_nonrepresentative=(
            expectations.stage2_nonrepresentative
        ),
    )

    return records


def derive_and_validate_universe(
    records: Sequence[
        source_complete_universe.TerminalCompositionRecord
    ],
    *,
    expectations: Stage5AExpectations,
    expected_membership_sha256: str,
) -> tuple[
    tuple[
        source_complete_universe.CompleteUniverseRecord,
        ...
    ],
    str,
]:
    """Derive and validate the frozen complete eligible universe."""

    try:
        universe = (
            source_complete_universe
            .derive_complete_universe(
                records
            )
        )

        universe = (
            source_complete_universe
            .require_complete_universe(
                universe,
                expected_count=(
                    expectations.stage4_pass
                ),
                expected_species_count=(
                    expectations.complete_species_count
                ),
            )
        )

        membership_sha = (
            source_complete_universe
            .complete_universe_membership_sha256(
                universe
            )
        )

    except ValueError as exc:
        raise Stage5AWrapperError(
            "complete-universe validation failed closed"
        ) from exc

    if (
        membership_sha
        != expected_membership_sha256
    ):
        raise Stage5AWrapperError(
            "complete universe differs from Stage 4 PASS membership"
        )

    return (
        universe,
        membership_sha,
    )


def _ensure_output_root_outside_repo(
    output_root: Path,
    repo: Path,
) -> Path:
    root = Path(
        output_root
    ).resolve()

    repo = Path(
        repo
    ).resolve()

    if (
        root == repo
        or repo in root.parents
    ):
        raise Stage5AWrapperError(
            "Stage 5A output root must be outside repository"
        )

    return root


def _validate_external_sha(
    value: str,
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
        raise Stage5AWrapperError(
            f"{label} malformed"
        )

    return value


def execute_to_scratch(
    *,
    repo: Path,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    output_root: Path,
    decision_paths: DecisionPaths,
    decision_identities: DecisionArtifactIdentities,
    completion_sha256: Mapping[str, str],
    expectations: Stage5AExpectations,
    frozen_repo_sha256: Mapping[str, str],
) -> Path:
    """Execute Stage 5A with predecision-before-row-parsing ordering."""

    if LOWER_COMMIT_RE.fullmatch(
        expected_commit
    ) is None:
        raise Stage5AWrapperError(
            "expected execution commit malformed"
        )

    wrapper_sha = _validate_external_sha(
        expected_wrapper_sha256,
        label="Stage 5A wrapper SHA256",
    )

    wrapper_test_sha = _validate_external_sha(
        expected_wrapper_test_sha256,
        label="Stage 5A wrapper-test SHA256",
    )

    for label, value in (
        (
            "Stage 1 decision SHA256",
            decision_identities.stage1,
        ),
        (
            "Stage 2 decision SHA256",
            decision_identities.stage2,
        ),
        (
            "Stage 3 decision SHA256",
            decision_identities.stage3,
        ),
        (
            "Stage 4 decision SHA256",
            decision_identities.stage4,
        ),
    ):
        _validate_external_sha(
            value,
            label=label,
        )

    required_completion_labels = (
        "stage1",
        "stage2",
        "stage3",
        "stage4",
    )

    if set(
        completion_sha256
    ) != set(
        required_completion_labels
    ):
        raise Stage5AWrapperError(
            "completion-evidence SHA256 mapping malformed"
        )

    for label in required_completion_labels:
        _validate_external_sha(
            completion_sha256[
                label
            ],
            label=f"{label} completion SHA256",
        )

    # File identities may be verified before the predecision checkpoint,
    # but no decision row is parsed here.
    require_sha256(
        decision_paths.stage1,
        decision_identities.stage1,
        "Stage 1 decisions",
    )

    require_sha256(
        decision_paths.stage2,
        decision_identities.stage2,
        "Stage 2 decisions",
    )

    require_sha256(
        decision_paths.stage3,
        decision_identities.stage3,
        "Stage 3 decisions",
    )

    require_sha256(
        decision_paths.stage4,
        decision_identities.stage4,
        "Stage 4 decisions",
    )

    output_root = _ensure_output_root_outside_repo(
        output_root,
        repo,
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
        / (
            "."
            + expected_commit
            + ".partial"
        )
    )

    if final_dir.exists():
        raise Stage5AWrapperError(
            "final Stage 5A output directory already exists"
        )

    if partial_dir.exists():
        raise Stage5AWrapperError(
            "partial Stage 5A output directory already exists"
        )

    partial_dir.mkdir()

    predecision_path = (
        partial_dir
        / "stage5a-predecision-provenance.json"
    )

    predecision = {
        "schema_version":
            1,
        "status":
            "STAGE5A_PREDECISION_FROZEN",
        "bacselect_git_commit":
            expected_commit,
        "stage5_method_sha256":
            EXPECTED_STAGE5_METHOD_SHA256,
        "stage5a_helper_sha256":
            EXPECTED_STAGE5A_HELPER_SHA256,
        "stage5a_wrapper_sha256":
            wrapper_sha,
        "stage5a_wrapper_test_sha256":
            wrapper_test_sha,
        "stage1_completion_evidence_sha256":
            completion_sha256[
                "stage1"
            ],
        "stage2_completion_evidence_sha256":
            completion_sha256[
                "stage2"
            ],
        "stage3_completion_evidence_sha256":
            completion_sha256[
                "stage3"
            ],
        "stage4_completion_evidence_sha256":
            completion_sha256[
                "stage4"
            ],
        "stage1_decision_artifact_sha256":
            decision_identities.stage1,
        "stage2_decision_artifact_sha256":
            decision_identities.stage2,
        "stage3_decision_artifact_sha256":
            decision_identities.stage3,
        "stage4_decision_artifact_sha256":
            decision_identities.stage4,
        "stage1_population_candidate_count":
            expectations.stage1_total,
        "stage1_population_membership_sha256":
            expectations.stage1_membership_sha256,
        "stage2_input_candidate_count":
            expectations.stage2_total,
        "stage2_input_membership_sha256":
            expectations.stage2_input_membership_sha256,
        "stage3_input_candidate_count":
            expectations.stage3_total,
        "stage3_input_membership_sha256":
            expectations.stage3_input_membership_sha256,
        "stage4_input_candidate_count":
            expectations.stage4_total,
        "stage4_input_membership_sha256":
            expectations.stage4_input_membership_sha256,
        "expected_complete_universe_count":
            expectations.stage4_pass,
        "expected_complete_universe_species_count":
            expectations.complete_species_count,
        "frozen_repo_sha256":
            dict(
                sorted(
                    frozen_repo_sha256.items()
                )
            ),
        "stage1_candidate_rows_parsed":
            False,
        "stage2_candidate_rows_parsed":
            False,
        "stage3_candidate_rows_parsed":
            False,
        "stage4_candidate_rows_parsed":
            False,
        "terminal_composition_generated":
            False,
        "complete_eligible_universe_generated":
            False,
        "baseline_membership_consulted":
            False,
        "raw_metadata_source_parsed":
            False,
        "baseline_matrix_parsed":
            False,
        "historical_absence_membership_reconstructed":
            False,
        "holdout_membership_generated":
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

    # Candidate decision rows may only be parsed after the predecision
    # artifact above exists on disk.
    chain = load_decision_chain(
        decision_paths,
        identities=decision_identities,
        expectations=expectations,
    )

    records = compose_terminal_population(
        chain,
        expectations=expectations,
    )

    universe, universe_membership_sha = (
        derive_and_validate_universe(
            records,
            expectations=expectations,
            expected_membership_sha256=(
                chain.stage4.pass_membership_sha256
            ),
        )
    )

    terminal_path = (
        partial_dir
        / "stage5-terminal-composition.tsv"
    )

    terminal_sha = write_tsv_atomic(
        terminal_path,
        source_complete_universe.TERMINAL_COMPOSITION_FIELDS,
        source_complete_universe.terminal_composition_rows(
            records
        ),
    )

    universe_path = (
        partial_dir
        / "complete-eligible-fresh-universe.tsv"
    )

    universe_sha = write_tsv_atomic(
        universe_path,
        source_complete_universe.COMPLETE_UNIVERSE_FIELDS,
        source_complete_universe.complete_universe_rows(
            universe
        ),
    )

    summary_counts = (
        source_complete_universe
        .disposition_summary(
            records
        )
    )

    execution_provenance_path = (
        partial_dir
        / "stage5a-execution-provenance.json"
    )

    execution_provenance = {
        "schema_version":
            1,
        "status":
            "STAGE5A_COMPLETE_UNIVERSE_COMPLETE",
        "bacselect_git_commit":
            expected_commit,
        "predecision_provenance_sha256":
            predecision_sha,
        "stage5_method_sha256":
            EXPECTED_STAGE5_METHOD_SHA256,
        "stage5a_helper_sha256":
            EXPECTED_STAGE5A_HELPER_SHA256,
        "stage5a_wrapper_sha256":
            wrapper_sha,
        "stage5a_wrapper_test_sha256":
            wrapper_test_sha,
        "stage1_population_membership_sha256":
            chain.stage1.all_membership_sha256,
        "stage2_input_membership_sha256":
            chain.stage2.all_membership_sha256,
        "stage3_input_membership_sha256":
            chain.stage3.all_membership_sha256,
        "stage4_input_membership_sha256":
            chain.stage4.all_membership_sha256,
        "terminal_composition_row_count":
            len(
                records
            ),
        "terminal_disposition_counts":
            summary_counts.as_dict(),
        "terminal_composition_sha256":
            terminal_sha,
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
            universe_membership_sha,
        "complete_universe_artifact_sha256":
            universe_sha,
        "stage1_candidate_rows_parsed":
            True,
        "stage2_candidate_rows_parsed":
            True,
        "stage3_candidate_rows_parsed":
            True,
        "stage4_candidate_rows_parsed":
            True,
        "terminal_composition_generated":
            True,
        "complete_eligible_universe_generated":
            True,
        "baseline_membership_consulted":
            False,
        "raw_metadata_source_parsed":
            False,
        "baseline_matrix_parsed":
            False,
        "historical_absence_membership_reconstructed":
            False,
        "holdout_membership_generated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    execution_provenance_sha = write_json_atomic(
        execution_provenance_path,
        execution_provenance,
    )

    summary_path = (
        partial_dir
        / "stage5a-aggregate-summary.json"
    )

    aggregate_summary = {
        "schema_version":
            1,
        "status":
            "STAGE5A_COMPLETE_UNIVERSE_COMPLETE",
        "terminal_composition_row_count":
            len(
                records
            ),
        "terminal_disposition_counts":
            summary_counts.as_dict(),
        "terminal_composition_sha256":
            terminal_sha,
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
            universe_membership_sha,
        "complete_universe_artifact_sha256":
            universe_sha,
        "predecision_provenance_sha256":
            predecision_sha,
        "execution_provenance_sha256":
            execution_provenance_sha,
        "baseline_membership_consulted":
            False,
        "historical_absence_membership_reconstructed":
            False,
        "holdout_membership_generated":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }

    summary_sha = write_json_atomic(
        summary_path,
        aggregate_summary,
    )

    content_paths = (
        predecision_path,
        terminal_path,
        universe_path,
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
                sha256_file(
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
        / "stage5a-content-manifest.tsv"
    )

    content_manifest_sha = write_tsv_atomic(
        content_manifest_path,
        CONTENT_MANIFEST_FIELDS,
        content_rows,
    )

    final_names = {
        path.name
        for path in partial_dir.iterdir()
    }

    expected_final_names = {
        "stage5a-predecision-provenance.json",
        "stage5-terminal-composition.tsv",
        "complete-eligible-fresh-universe.tsv",
        "stage5a-execution-provenance.json",
        "stage5a-aggregate-summary.json",
        "stage5a-content-manifest.tsv",
    }

    if (
        final_names
        != expected_final_names
    ):
        raise Stage5AWrapperError(
            "Stage 5A final artifact set mismatch"
        )

    if final_dir.exists():
        raise Stage5AWrapperError(
            "final Stage 5A directory appeared before finalization"
        )

    os.replace(
        partial_dir,
        final_dir,
    )

    print(
        "PASS | Stage 5A complete-universe execution complete"
    )
    print(
        f"terminal_composition_row_count={len(records)}"
    )
    print(
        "terminal_disposition_counts="
        + json.dumps(
            summary_counts.as_dict(),
            sort_keys=True,
        )
    )
    print(
        f"terminal_composition_sha256={terminal_sha}"
    )
    print(
        f"complete_universe_count={len(universe)}"
    )
    print(
        "complete_universe_species_count="
        f"{expectations.complete_species_count}"
    )
    print(
        "complete_universe_membership_sha256="
        f"{universe_membership_sha}"
    )
    print(
        f"complete_universe_artifact_sha256={universe_sha}"
    )
    print(
        f"predecision_provenance_sha256={predecision_sha}"
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
            "Stage 5A complete-universe composition."
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
        "--stage1-decisions",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--stage2-decisions",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--stage3-decisions",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--stage4-decisions",
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
            expected_commit=args.expected_commit,
            expected_wrapper_sha256=(
                args.expected_wrapper_sha256
            ),
            expected_wrapper_test_sha256=(
                args.expected_wrapper_test_sha256
            ),
        )

        load_production_completion_evidence(
            repo
        )

        completion_sha256 = {
            "stage1":
                EXPECTED_STAGE1_COMPLETION_SHA256,
            "stage2":
                EXPECTED_STAGE2_COMPLETION_SHA256,
            "stage3":
                EXPECTED_STAGE3_COMPLETION_SHA256,
            "stage4":
                EXPECTED_STAGE4_COMPLETION_SHA256,
        }

        execute_to_scratch(
            repo=repo,
            expected_commit=args.expected_commit,
            expected_wrapper_sha256=(
                args.expected_wrapper_sha256
            ),
            expected_wrapper_test_sha256=(
                args.expected_wrapper_test_sha256
            ),
            output_root=args.output_root,
            decision_paths=DecisionPaths(
                stage1=args.stage1_decisions,
                stage2=args.stage2_decisions,
                stage3=args.stage3_decisions,
                stage4=args.stage4_decisions,
            ),
            decision_identities=(
                PRODUCTION_DECISION_IDENTITIES
            ),
            completion_sha256=completion_sha256,
            expectations=PRODUCTION_EXPECTATIONS,
            frozen_repo_sha256=frozen_repo_sha256,
        )

    except Stage5AWrapperError as exc:
        print(
            "ERROR | Stage 5A execution failed closed: "
            f"{exc}",
            file=sys.stderr,
        )

        return 1

    except Exception:
        print(
            "ERROR | Stage 5A execution failed closed",
            file=sys.stderr,
        )

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
