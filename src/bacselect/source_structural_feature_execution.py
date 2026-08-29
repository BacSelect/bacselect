"""Stage 6 raw structural-feature execution adapter.

This module contains orchestration and validation only.

Replicon loading and features 1-5 are delegated to the frozen Project Finch
implementation. Repeat coordinates and longest exact repeat are calculated only
by the frozen compiled C++ engine. No structural-feature mathematics is
reimplemented here.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import math
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Mapping, Protocol, Sequence

from bacselect.source_structural_features import (
    CandidatePackageBinding,
)


STAGE6_K_VALUES = (
    300,
    2400,
)

ENGINE_FIELDS = (
    "k",
    "valid_start_count",
    "non_unique_start_count",
    "non_unique_fraction",
    "maximum_multiplicity",
    "inter_replicon_shared_start_count",
    "inter_replicon_shared_fraction",
    "longest_exact_repeat_length",
)

FEATURE_FIELDS = (
    "01_total_genome_length",
    "02_whole_genome_gc_fraction",
    "03_replicon_count",
    "04_non_chromosomal_replicon_count",
    "05_non_chromosomal_sequence_fraction",
    "06_non_unique_canonical_300mer_fraction",
    "07_non_unique_canonical_2400mer_fraction",
    "08_maximum_canonical_300mer_multiplicity",
    "09_maximum_canonical_2400mer_multiplicity",
    "10_longest_exact_repeat_length",
    "11_inter_replicon_shared_canonical_300mer_fraction",
    "12_inter_replicon_shared_canonical_2400mer_fraction",
)


class StructuralFeatureExecutionError(
    RuntimeError
):
    """Raised when exact Stage 6 feature execution cannot be proven."""


class FinchModuleLike(Protocol):
    def load_replicons(
        self,
        candidate_dir: Path,
        candidate_audit_path: Path,
        component_audit_path: Path,
    ):
        ...


class BasicModuleLike(Protocol):
    def basic_structural_features(
        self,
        replicons,
    ) -> Mapping[str, int | float]:
        ...


@dataclass(frozen=True)
class RepeatEngineRow:
    k: int
    valid_start_count: int
    non_unique_start_count: int
    non_unique_fraction: float
    maximum_multiplicity: int
    inter_replicon_shared_start_count: int
    inter_replicon_shared_fraction: float
    longest_exact_repeat_length: int


@dataclass(frozen=True)
class Stage6FeatureRecord:
    accession: str
    species_taxid: str
    features: Mapping[
        str,
        int | float,
    ]
    retained_replicon_count: int
    total_sequence_length: int


def _nonempty(
    value: object,
    *,
    label: str,
) -> str:
    text = str(
        value
    ).strip()

    if not text:
        raise StructuralFeatureExecutionError(
            f"{label} must not be empty"
        )

    return text


def _nonnegative_int(
    value: object,
    *,
    label: str,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        raise StructuralFeatureExecutionError(
            f"{label} must be an integer"
        )

    try:
        result = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        raise StructuralFeatureExecutionError(
            f"{label} must be an integer"
        ) from None

    if str(result) != str(
        value
    ).strip():
        raise StructuralFeatureExecutionError(
            f"{label} must be canonical base-10 integer text"
        )

    if result < 0:
        raise StructuralFeatureExecutionError(
            f"{label} must be non-negative"
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

    if result == 0:
        raise StructuralFeatureExecutionError(
            f"{label} must be positive"
        )

    return result


def _finite_float(
    value: object,
    *,
    label: str,
) -> float:
    try:
        result = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        raise StructuralFeatureExecutionError(
            f"{label} must be numeric"
        ) from None

    if not math.isfinite(
        result
    ):
        raise StructuralFeatureExecutionError(
            f"{label} must be finite"
        )

    return result


def _unit_fraction(
    value: object,
    *,
    label: str,
) -> float:
    result = _finite_float(
        value,
        label=label,
    )

    if not (
        0.0
        <= result
        <= 1.0
    ):
        raise StructuralFeatureExecutionError(
            f"{label} must lie in [0, 1]"
        )

    return result


def _require_exact_fraction(
    *,
    numerator: int,
    denominator: int,
    observed: float,
    label: str,
) -> None:
    expected = (
        0.0
        if denominator == 0
        else numerator / denominator
    )

    if observed != expected:
        raise StructuralFeatureExecutionError(
            f"{label} does not agree with engine counts"
        )


def load_verified_replicons(
    *,
    binding: CandidatePackageBinding,
    finch: FinchModuleLike,
):
    """Load exact retained replicons through the frozen Finch loader."""

    try:
        result = finch.load_replicons(
            binding.candidate_dir,
            binding.candidate_audit,
            binding.component_audit,
        )
    except Exception as exc:
        raise StructuralFeatureExecutionError(
            "frozen Finch replicon loading failed"
        ) from exc

    if (
        not isinstance(
            result,
            tuple,
        )
        or len(
            result
        ) != 4
    ):
        raise StructuralFeatureExecutionError(
            "frozen Finch loader returned unexpected result"
        )

    (
        accession,
        replicons,
        fasta_path,
        sequence_report_path,
    ) = result

    if accession != binding.accession:
        raise StructuralFeatureExecutionError(
            "frozen Finch loader accession mismatch"
        )

    try:
        observed_fasta = Path(
            fasta_path
        ).resolve(
            strict=True
        )

        expected_fasta = (
            binding.fasta_path.resolve(
                strict=True
            )
        )

        observed_report = Path(
            sequence_report_path
        ).resolve(
            strict=True
        )

        expected_report = (
            binding.sequence_report_path.resolve(
                strict=True
            )
        )
    except OSError as exc:
        raise StructuralFeatureExecutionError(
            "verified source path could not be resolved"
        ) from exc

    if observed_fasta != expected_fasta:
        raise StructuralFeatureExecutionError(
            "frozen Finch loader FASTA path mismatch"
        )

    if observed_report != expected_report:
        raise StructuralFeatureExecutionError(
            "frozen Finch loader sequence-report path mismatch"
        )

    replicons = tuple(
        replicons
    )

    if not replicons:
        raise StructuralFeatureExecutionError(
            "frozen Finch loader returned no retained replicons"
        )

    return replicons


def _parse_engine_row(
    row: Mapping[
        str,
        str,
    ],
) -> RepeatEngineRow:
    k = _positive_int(
        row.get(
            "k",
            "",
        ),
        label="engine k",
    )

    valid = _nonnegative_int(
        row.get(
            "valid_start_count",
            "",
        ),
        label="valid start count",
    )

    non_unique = _nonnegative_int(
        row.get(
            "non_unique_start_count",
            "",
        ),
        label="non-unique start count",
    )

    if non_unique > valid:
        raise StructuralFeatureExecutionError(
            "non-unique start count exceeds valid start count"
        )

    non_unique_fraction = (
        _unit_fraction(
            row.get(
                "non_unique_fraction",
                "",
            ),
            label="non-unique fraction",
        )
    )

    _require_exact_fraction(
        numerator=non_unique,
        denominator=valid,
        observed=(
            non_unique_fraction
        ),
        label="non-unique fraction",
    )

    maximum = _nonnegative_int(
        row.get(
            "maximum_multiplicity",
            "",
        ),
        label="maximum multiplicity",
    )

    shared = _nonnegative_int(
        row.get(
            "inter_replicon_shared_start_count",
            "",
        ),
        label="inter-replicon shared start count",
    )

    if shared > valid:
        raise StructuralFeatureExecutionError(
            "inter-replicon shared count exceeds valid start count"
        )

    shared_fraction = (
        _unit_fraction(
            row.get(
                "inter_replicon_shared_fraction",
                "",
            ),
            label="inter-replicon shared fraction",
        )
    )

    _require_exact_fraction(
        numerator=shared,
        denominator=valid,
        observed=shared_fraction,
        label="inter-replicon shared fraction",
    )

    longest = _nonnegative_int(
        row.get(
            "longest_exact_repeat_length",
            "",
        ),
        label="longest exact repeat length",
    )

    return RepeatEngineRow(
        k=k,
        valid_start_count=valid,
        non_unique_start_count=(
            non_unique
        ),
        non_unique_fraction=(
            non_unique_fraction
        ),
        maximum_multiplicity=(
            maximum
        ),
        inter_replicon_shared_start_count=(
            shared
        ),
        inter_replicon_shared_fraction=(
            shared_fraction
        ),
        longest_exact_repeat_length=(
            longest
        ),
    )


def run_stage6_repeat_engine(
    *,
    engine: Path,
    replicons: Sequence,
) -> Mapping[
    int,
    RepeatEngineRow,
]:
    """Invoke the frozen repeat engine at exactly k=300 and k=2400."""

    engine = Path(
        engine
    )

    if (
        not engine.is_file()
        or not os.access(
            engine,
            os.X_OK,
        )
    ):
        raise StructuralFeatureExecutionError(
            "compiled structural-feature engine is unavailable"
        )

    replicons = tuple(
        replicons
    )

    if not replicons:
        raise StructuralFeatureExecutionError(
            "repeat engine requires at least one replicon"
        )

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="ascii",
            newline="",
            suffix=".tsv",
            delete=False,
        ) as handle:
            temporary_path = Path(
                handle.name
            )

            writer = csv.writer(
                handle,
                delimiter="\t",
                lineterminator="\n",
            )

            writer.writerow(
                (
                    "name",
                    "topology",
                    "sequence",
                )
            )

            for replicon in replicons:
                name = _nonempty(
                    replicon.name,
                    label="replicon name",
                )

                topology = _nonempty(
                    replicon.topology,
                    label="replicon topology",
                )

                sequence = _nonempty(
                    replicon.sequence,
                    label="replicon sequence",
                )

                if any(
                    character in name
                    for character in (
                        "\t",
                        "\r",
                        "\n",
                    )
                ):
                    raise StructuralFeatureExecutionError(
                        "replicon name contains TSV control character"
                    )

                writer.writerow(
                    (
                        name,
                        topology,
                        sequence,
                    )
                )

        try:
            completed = subprocess.run(
                (
                    str(
                        engine
                    ),
                    "--input",
                    str(
                        temporary_path
                    ),
                    "--k",
                    "300",
                    "--k",
                    "2400",
                    "--longest-repeat",
                ),
                check=True,
                text=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            raise StructuralFeatureExecutionError(
                "frozen structural-feature engine execution failed"
            ) from exc

    finally:
        if temporary_path is not None:
            temporary_path.unlink(
                missing_ok=True
            )

    reader = csv.DictReader(
        completed.stdout.splitlines(),
        delimiter="\t",
    )

    if tuple(
        reader.fieldnames
        or ()
    ) != ENGINE_FIELDS:
        raise StructuralFeatureExecutionError(
            "structural-feature engine output schema mismatch"
        )

    rows = list(
        reader
    )

    if len(
        rows
    ) != 2:
        raise StructuralFeatureExecutionError(
            "structural-feature engine must return exactly two rows"
        )

    parsed = tuple(
        _parse_engine_row(
            row
        )
        for row in rows
    )

    by_k: dict[
        int,
        RepeatEngineRow,
    ] = {}

    for row in parsed:
        if row.k in by_k:
            raise StructuralFeatureExecutionError(
                "duplicate structural-feature engine k row"
            )

        by_k[
            row.k
        ] = row

    if set(
        by_k
    ) != set(
        STAGE6_K_VALUES
    ):
        raise StructuralFeatureExecutionError(
            "structural-feature engine did not return exactly "
            "k=300 and k=2400"
        )

    longest_values = {
        row.longest_exact_repeat_length
        for row in by_k.values()
    }

    if len(
        longest_values
    ) != 1:
        raise StructuralFeatureExecutionError(
            "longest-repeat result differs between engine rows"
        )

    return dict(
        sorted(
            by_k.items()
        )
    )


def _validate_basic_features(
    value: Mapping[
        str,
        int | float,
    ],
) -> dict[
    str,
    int | float,
]:
    required = {
        "total_genome_length",
        "whole_genome_gc_fraction",
        "replicon_count",
        "non_chromosomal_replicon_count",
        "non_chromosomal_sequence_fraction",
    }

    missing = (
        required
        - set(
            value
        )
    )

    if missing:
        raise StructuralFeatureExecutionError(
            "frozen basic-feature result missing required field"
        )

    total_length = _positive_int(
        value[
            "total_genome_length"
        ],
        label="total genome length",
    )

    gc_fraction = _unit_fraction(
        value[
            "whole_genome_gc_fraction"
        ],
        label="whole-genome GC fraction",
    )

    replicon_count = _positive_int(
        value[
            "replicon_count"
        ],
        label="replicon count",
    )

    non_chromosomal_count = (
        _nonnegative_int(
            value[
                "non_chromosomal_replicon_count"
            ],
            label="non-chromosomal replicon count",
        )
    )

    if (
        non_chromosomal_count
        > replicon_count
    ):
        raise StructuralFeatureExecutionError(
            "non-chromosomal replicon count exceeds replicon count"
        )

    non_chromosomal_fraction = (
        _unit_fraction(
            value[
                "non_chromosomal_sequence_fraction"
            ],
            label="non-chromosomal sequence fraction",
        )
    )

    return {
        "total_genome_length":
            total_length,
        "whole_genome_gc_fraction":
            gc_fraction,
        "replicon_count":
            replicon_count,
        "non_chromosomal_replicon_count":
            non_chromosomal_count,
        "non_chromosomal_sequence_fraction":
            non_chromosomal_fraction,
    }


def _validate_feature_map(
    features: Mapping[
        str,
        int | float,
    ],
) -> dict[
    str,
    int | float,
]:
    if tuple(
        features
    ) != FEATURE_FIELDS:
        raise StructuralFeatureExecutionError(
            "Stage 6 feature schema/order mismatch"
        )

    integer_fields = {
        "01_total_genome_length",
        "03_replicon_count",
        "04_non_chromosomal_replicon_count",
        "08_maximum_canonical_300mer_multiplicity",
        "09_maximum_canonical_2400mer_multiplicity",
        "10_longest_exact_repeat_length",
    }

    fraction_fields = {
        "02_whole_genome_gc_fraction",
        "05_non_chromosomal_sequence_fraction",
        "06_non_unique_canonical_300mer_fraction",
        "07_non_unique_canonical_2400mer_fraction",
        "11_inter_replicon_shared_canonical_300mer_fraction",
        "12_inter_replicon_shared_canonical_2400mer_fraction",
    }

    validated: dict[
        str,
        int | float,
    ] = {}

    for name in FEATURE_FIELDS:
        value = features[
            name
        ]

        if name in integer_fields:
            if name in {
                "01_total_genome_length",
                "03_replicon_count",
            }:
                validated[
                    name
                ] = _positive_int(
                    value,
                    label=name,
                )
            else:
                validated[
                    name
                ] = _nonnegative_int(
                    value,
                    label=name,
                )

        elif name in fraction_fields:
            validated[
                name
            ] = _unit_fraction(
                value,
                label=name,
            )

        else:
            raise StructuralFeatureExecutionError(
                "unclassified Stage 6 feature field"
            )

    if (
        validated[
            "04_non_chromosomal_replicon_count"
        ]
        > validated[
            "03_replicon_count"
        ]
    ):
        raise StructuralFeatureExecutionError(
            "non-chromosomal count exceeds replicon count"
        )

    return validated


def compute_stage6_feature_record(
    *,
    binding: CandidatePackageBinding,
    species_taxid: object,
    finch: FinchModuleLike,
    basic: BasicModuleLike,
    engine: Path,
) -> Stage6FeatureRecord:
    """Calculate one exact Stage 6 twelve-coordinate raw feature record."""

    taxid = _positive_int(
        species_taxid,
        label="species TaxID",
    )

    replicons = load_verified_replicons(
        binding=binding,
        finch=finch,
    )

    try:
        basic_raw = (
            basic.basic_structural_features(
                replicons
            )
        )
    except Exception as exc:
        raise StructuralFeatureExecutionError(
            "frozen basic structural-feature calculation failed"
        ) from exc

    basic_features = (
        _validate_basic_features(
            basic_raw
        )
    )

    if (
        basic_features[
            "replicon_count"
        ]
        != len(
            replicons
        )
    ):
        raise StructuralFeatureExecutionError(
            "basic-feature replicon count differs from frozen loader"
        )

    observed_length = sum(
        len(
            replicon.sequence
        )
        for replicon in replicons
    )

    if (
        basic_features[
            "total_genome_length"
        ]
        != observed_length
    ):
        raise StructuralFeatureExecutionError(
            "basic-feature total length differs from retained replicons"
        )

    repeat_rows = (
        run_stage6_repeat_engine(
            engine=engine,
            replicons=replicons,
        )
    )

    row300 = repeat_rows[
        300
    ]

    row2400 = repeat_rows[
        2400
    ]

    longest = (
        row300.longest_exact_repeat_length
    )

    features = {
        "01_total_genome_length":
            basic_features[
                "total_genome_length"
            ],
        "02_whole_genome_gc_fraction":
            basic_features[
                "whole_genome_gc_fraction"
            ],
        "03_replicon_count":
            basic_features[
                "replicon_count"
            ],
        "04_non_chromosomal_replicon_count":
            basic_features[
                "non_chromosomal_replicon_count"
            ],
        "05_non_chromosomal_sequence_fraction":
            basic_features[
                "non_chromosomal_sequence_fraction"
            ],
        "06_non_unique_canonical_300mer_fraction":
            row300.non_unique_fraction,
        "07_non_unique_canonical_2400mer_fraction":
            row2400.non_unique_fraction,
        "08_maximum_canonical_300mer_multiplicity":
            row300.maximum_multiplicity,
        "09_maximum_canonical_2400mer_multiplicity":
            row2400.maximum_multiplicity,
        "10_longest_exact_repeat_length":
            longest,
        "11_inter_replicon_shared_canonical_300mer_fraction":
            row300.inter_replicon_shared_fraction,
        "12_inter_replicon_shared_canonical_2400mer_fraction":
            row2400.inter_replicon_shared_fraction,
    }

    validated = (
        _validate_feature_map(
            features
        )
    )

    return Stage6FeatureRecord(
        accession=(
            binding.accession
        ),
        species_taxid=str(
            taxid
        ),
        features=validated,
        retained_replicon_count=(
            len(
                replicons
            )
        ),
        total_sequence_length=(
            observed_length
        ),
    )
