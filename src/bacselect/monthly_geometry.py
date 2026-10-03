"""Pure monthly species-balanced percentile geometry for BacSelect."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Mapping, Sequence

import numpy as np
import numpy.typing as npt

from bacselect.geometry import (
    species_balanced_percentile_matrix,
)
from bacselect.monthly_structural_features import (
    FEATURE_FIELDS,
    accession_membership_sha256,
)


ACCESSION_FIELD = (
    "canonical_genbank_assembly_accession"
)

SPECIES_FIELD = "species_taxid"

MATRIX_FIELDS = (
    ACCESSION_FIELD,
    SPECIES_FIELD,
    *FEATURE_FIELDS,
)

_GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

_TAXID_RE = re.compile(
    r"^[1-9][0-9]*$"
)


class MonthlyGeometryError(RuntimeError):
    """Raised when monthly geometry inputs or outputs are invalid."""


@dataclass(frozen=True)
class MonthlyGeometryRow:
    """One monthly genome in species-balanced percentile space."""

    accession: str
    species_taxid: str
    coordinates: Mapping[str, float]


@dataclass(frozen=True)
class MonthlyGeometryBuild:
    """Validated monthly species-balanced geometry."""

    rows: tuple[MonthlyGeometryRow, ...]
    species_count: int
    membership_sha256: str
    species_mapping_sha256: str
    raw_numeric_array_sha256: str
    percentile_numeric_array_sha256: str


def _numeric_array_sha256(
    matrix: npt.NDArray[np.floating],
) -> str:
    """Hash canonical little-endian float64 C-order matrix bytes."""
    canonical = np.ascontiguousarray(
        matrix,
        dtype="<f8",
    )

    return hashlib.sha256(
        canonical.tobytes(
            order="C"
        )
    ).hexdigest()


def _species_mapping_sha256(
    accessions: Sequence[str],
    species_ids: Sequence[str],
) -> str:
    """Hash ordered accession-to-species assignments."""
    digest = hashlib.sha256()

    digest.update(
        b"BacSelect-monthly-geometry|"
        b"species-mapping-v1\n"
    )

    for accession, species_taxid in zip(
        accessions,
        species_ids,
        strict=True,
    ):
        digest.update(
            accession.encode(
                "ascii"
            )
        )
        digest.update(b"\t")
        digest.update(
            species_taxid.encode(
                "ascii"
            )
        )
        digest.update(b"\n")

    return digest.hexdigest()


def build_monthly_geometry(
    accessions: Sequence[str],
    species_ids: Sequence[str],
    raw_values: (
        Sequence[Sequence[float]]
        | npt.NDArray[np.floating]
    ),
) -> MonthlyGeometryBuild:
    """Build current monthly species-balanced percentile geometry.

    The operation always recomputes all percentile coordinates from the
    complete current monthly raw feature matrix and current species mapping.
    No previous-release coordinate is accepted as input.
    """
    accession_rows = tuple(
        accessions
    )

    species_rows = tuple(
        species_ids
    )

    if not accession_rows:
        raise MonthlyGeometryError(
            "monthly geometry population must not be empty"
        )

    if (
        len(accession_rows)
        != len(species_rows)
    ):
        raise MonthlyGeometryError(
            "accession and species row counts differ"
        )

    if (
        len(set(accession_rows))
        != len(accession_rows)
    ):
        raise MonthlyGeometryError(
            "monthly geometry contains duplicate accessions"
        )

    for accession in accession_rows:
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
            raise MonthlyGeometryError(
                "monthly geometry contains malformed accession"
            )

    for species_taxid in species_rows:
        if (
            not isinstance(
                species_taxid,
                str,
            )
            or _TAXID_RE.fullmatch(
                species_taxid
            )
            is None
        ):
            raise MonthlyGeometryError(
                "monthly geometry contains malformed species TaxID"
            )

    raw = np.asarray(
        raw_values,
        dtype=np.float64,
    )

    expected_shape = (
        len(
            accession_rows
        ),
        len(
            FEATURE_FIELDS
        ),
    )

    if raw.shape != expected_shape:
        raise MonthlyGeometryError(
            "monthly raw feature matrix shape mismatch"
        )

    if not np.all(
        np.isfinite(
            raw
        )
    ):
        raise MonthlyGeometryError(
            "monthly raw feature matrix contains non-finite values"
        )

    coordinates = (
        species_balanced_percentile_matrix(
            raw,
            species_rows,
        )
    )

    if coordinates.shape != raw.shape:
        raise MonthlyGeometryError(
            "monthly percentile matrix shape changed"
        )

    if not np.all(
        np.isfinite(
            coordinates
        )
    ):
        raise MonthlyGeometryError(
            "monthly percentile matrix contains non-finite values"
        )

    if not np.all(
        (
            coordinates
            >= 0.0
        )
        & (
            coordinates
            <= 1.0
        )
    ):
        raise MonthlyGeometryError(
            "monthly percentile coordinate outside [0,1]"
        )

    for column, field in enumerate(
        FEATURE_FIELDS
    ):
        raw_unique = np.unique(
            raw[
                :,
                column,
            ]
        ).size

        coordinate_unique = np.unique(
            coordinates[
                :,
                column,
            ]
        ).size

        if (
            raw_unique
            != coordinate_unique
        ):
            raise MonthlyGeometryError(
                "monthly percentile transform changed "
                f"tie classes for {field}"
            )

    rows = tuple(
        MonthlyGeometryRow(
            accession=accession,
            species_taxid=species_taxid,
            coordinates={
                field:
                    float(
                        coordinates[
                            row_index,
                            column,
                        ]
                    )
                for column, field
                in enumerate(
                    FEATURE_FIELDS
                )
            },
        )
        for row_index, (
            accession,
            species_taxid,
        )
        in enumerate(
            zip(
                accession_rows,
                species_rows,
                strict=True,
            )
        )
    )

    return MonthlyGeometryBuild(
        rows=rows,
        species_count=len(
            set(
                species_rows
            )
        ),
        membership_sha256=(
            accession_membership_sha256(
                accession_rows
            )
        ),
        species_mapping_sha256=(
            _species_mapping_sha256(
                accession_rows,
                species_rows,
            )
        ),
        raw_numeric_array_sha256=(
            _numeric_array_sha256(
                raw
            )
        ),
        percentile_numeric_array_sha256=(
            _numeric_array_sha256(
                coordinates
            )
        ),
    )


def _format_coordinate(
    value: float,
) -> str:
    numeric = float(
        value
    )

    if not math.isfinite(
        numeric
    ):
        raise MonthlyGeometryError(
            "percentile coordinate is non-finite"
        )

    if (
        numeric < 0.0
        or numeric > 1.0
    ):
        raise MonthlyGeometryError(
            "percentile coordinate outside [0,1]"
        )

    return format(
        numeric,
        ".17g",
    )


def serialize_monthly_geometry_matrix(
    build: MonthlyGeometryBuild,
) -> bytes:
    """Serialize monthly percentile coordinates deterministically."""
    if not isinstance(
        build,
        MonthlyGeometryBuild,
    ):
        raise TypeError(
            "monthly geometry build has wrong type"
        )

    output = [
        "\t".join(
            MATRIX_FIELDS
        )
        + "\n"
    ]

    for row in build.rows:
        values = [
            row.accession,
            row.species_taxid,
        ]

        values.extend(
            _format_coordinate(
                row.coordinates[
                    field
                ]
            )
            for field in (
                FEATURE_FIELDS
            )
        )

        output.append(
            "\t".join(
                values
            )
            + "\n"
        )

    return "".join(
        output
    ).encode(
        "ascii"
    )


def parse_monthly_geometry_matrix(
    payload: bytes,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    npt.NDArray[np.float64],
]:
    """Parse a serialized monthly percentile matrix for exact readback."""
    try:
        text = payload.decode(
            "ascii"
        )
    except UnicodeDecodeError as exc:
        raise MonthlyGeometryError(
            "monthly percentile matrix is not ASCII"
        ) from exc

    lines = text.splitlines()

    if not lines:
        raise MonthlyGeometryError(
            "monthly percentile matrix is empty"
        )

    if tuple(
        lines[0].split(
            "\t"
        )
    ) != MATRIX_FIELDS:
        raise MonthlyGeometryError(
            "monthly percentile matrix header changed"
        )

    accessions: list[str] = []
    species_ids: list[str] = []
    values: list[list[float]] = []

    for line in lines[1:]:
        fields = line.split(
            "\t"
        )

        if len(
            fields
        ) != len(
            MATRIX_FIELDS
        ):
            raise MonthlyGeometryError(
                "monthly percentile matrix row width changed"
            )

        accessions.append(
            fields[0]
        )

        species_ids.append(
            fields[1]
        )

        try:
            values.append(
                [
                    float(
                        value
                    )
                    for value in fields[
                        2:
                    ]
                ]
            )
        except ValueError as exc:
            raise MonthlyGeometryError(
                "monthly percentile matrix contains invalid numeric value"
            ) from exc

    matrix = np.asarray(
        values,
        dtype=np.float64,
    )

    expected_shape = (
        len(
            accessions
        ),
        len(
            FEATURE_FIELDS
        ),
    )

    if matrix.shape != expected_shape:
        raise MonthlyGeometryError(
            "parsed monthly percentile matrix shape mismatch"
        )

    if not np.all(
        np.isfinite(
            matrix
        )
    ):
        raise MonthlyGeometryError(
            "parsed monthly percentile matrix contains non-finite values"
        )

    return (
        tuple(
            accessions
        ),
        tuple(
            species_ids
        ),
        matrix,
    )
