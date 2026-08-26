"""NCBI taxonomy resolution primitives for BacSelect selector-v1.

This module implements the frozen Project Finch taxonomy-resolution
semantics reused prospectively by BacSelect.

It parses nodes.dmp, merged.dmp and delnodes.dmp, normalizes merged TaxIDs,
rejects deleted or missing TaxIDs, and resolves the first lineage ancestor
whose rank is exactly ``species``.

It performs no network access and contains no frozen historical taxonomy
snapshot identities. BacSelect taxonomy snapshot acquisition and provenance
are separate prospective stages.
"""

from __future__ import annotations

from array import array
from pathlib import Path


class TaxonomyError(RuntimeError):
    """Raised when frozen taxonomy input structure is invalid."""


def fail(message: str) -> None:
    """Fail closed on malformed taxonomy evidence."""

    raise TaxonomyError(message)


def dmp_fields(line: str) -> list[str]:
    """Parse one NCBI taxonomy dump line using the frozen field semantics."""

    return [
        field.strip()
        for field in line.rstrip("\n").split("|")
    ]


class Taxonomy:
    """Frozen merged/deleted/lineage resolver for NCBI taxonomy."""

    def __init__(
        self,
        *,
        nodes_path: Path,
        merged_path: Path,
        delnodes_path: Path,
    ) -> None:
        self.merged: dict[int, int] = {}

        with merged_path.open(
            encoding="utf-8"
        ) as handle:
            for line in handle:
                fields = dmp_fields(
                    line
                )

                if (
                    len(fields) < 2
                    or not fields[0]
                    or not fields[1]
                ):
                    fail(
                        f"{merged_path}: malformed merged.dmp line"
                    )

                self.merged[
                    int(fields[0])
                ] = int(fields[1])

        self.deleted: set[int] = set()

        with delnodes_path.open(
            encoding="utf-8"
        ) as handle:
            for line in handle:
                fields = dmp_fields(
                    line
                )

                if (
                    not fields
                    or not fields[0]
                ):
                    fail(
                        f"{delnodes_path}: malformed delnodes.dmp line"
                    )

                self.deleted.add(
                    int(fields[0])
                )

        self.parents = array(
            "I",
            [0],
        )

        self.is_species = bytearray(
            1
        )

        with nodes_path.open(
            encoding="utf-8"
        ) as handle:
            for line in handle:
                fields = dmp_fields(
                    line
                )

                if len(fields) < 3:
                    fail(
                        f"{nodes_path}: malformed nodes.dmp line"
                    )

                taxid = int(
                    fields[0]
                )

                parent = int(
                    fields[1]
                )

                rank = fields[2]

                if taxid >= len(
                    self.parents
                ):
                    new_length = (
                        (
                            taxid
                            // 100000
                        )
                        + 1
                    ) * 100000

                    growth = (
                        new_length
                        - len(
                            self.parents
                        )
                    )

                    self.parents.extend(
                        array(
                            "I",
                            [0],
                        )
                        * growth
                    )

                    self.is_species.extend(
                        b"\x00"
                        * growth
                    )

                self.parents[
                    taxid
                ] = parent

                if rank == "species":
                    self.is_species[
                        taxid
                    ] = 1

        if (
            len(self.parents) <= 1
            or self.parents[1] != 1
        ):
            fail(
                f"{nodes_path}: taxonomy root TaxID 1 "
                "is missing or malformed"
            )

    def normalize(
        self,
        taxid: int,
    ) -> tuple[
        int | None,
        str,
        int,
    ]:
        """Normalize merged TaxIDs and reject deleted or missing nodes."""

        current = int(
            taxid
        )

        seen: set[int] = set()

        steps = 0

        while current in self.merged:
            if current in seen:
                return (
                    None,
                    "MERGED_CYCLE",
                    steps,
                )

            seen.add(
                current
            )

            current = self.merged[
                current
            ]

            steps += 1

        if current in self.deleted:
            return (
                None,
                "DELETED",
                steps,
            )

        if (
            current
            >= len(
                self.parents
            )
            or self.parents[
                current
            ] == 0
        ):
            return (
                None,
                "MISSING",
                steps,
            )

        return (
            current,
            "PASS",
            steps,
        )

    def species_ancestor(
        self,
        taxid: int,
    ) -> tuple[
        int | None,
        str,
    ]:
        """Return the first lineage ancestor ranked exactly ``species``."""

        current = int(
            taxid
        )

        seen: set[int] = set()

        while True:
            if current in seen:
                return (
                    None,
                    "LINEAGE_CYCLE",
                )

            seen.add(
                current
            )

            if (
                current
                >= len(
                    self.parents
                )
                or self.parents[
                    current
                ] == 0
            ):
                return (
                    None,
                    "MISSING_NODE",
                )

            if self.is_species[
                current
            ]:
                return (
                    current,
                    "PASS",
                )

            if current == 1:
                return (
                    None,
                    "NO_SPECIES_ANCESTOR",
                )

            current = self.parents[
                current
            ]
