"""Frozen source-truth sequence-redundancy primitives for BacSelect.

These functions implement the prospectively frozen BacSelect selector-v1
source-truth rules using the exact Project Finch sequence-equivalence and
full-containment semantics bound in the post-sequence provenance checkpoint.

This module performs no acquisition, taxonomy resolution, baseline comparison,
chromosome-integrity adjudication, feature calculation, or selector analysis.
"""

from __future__ import annotations

import hashlib
from typing import Mapping, Sequence


SUITABLE = "SUITABLE"
EXCLUDE = "EXCLUDE_SOURCE_TRUTH"
UNRESOLVED = "REVIEW_UNRESOLVED"

SUPPORTED_TOPOLOGIES = frozenset(
    {
        "linear",
        "circular",
    }
)


def reverse_complement(sequence: str) -> str:
    """Return the reverse complement of an A/C/G/T sequence."""

    return sequence.translate(
        str.maketrans(
            "ACGT",
            "TGCA",
        )
    )[::-1]


def _component(
    value: Mapping[str, object],
) -> tuple[str, str]:
    """Validate and return sequence and topology for one source component."""

    sequence = value.get("sequence")
    topology = value.get("topology")

    if not isinstance(sequence, str) or not sequence:
        raise ValueError(
            "component sequence must be a non-empty string"
        )

    invalid = set(sequence) - set("ACGT")

    if invalid:
        raise ValueError(
            "component sequence contains unsupported symbols: "
            f"{sorted(invalid)!r}"
        )

    if topology not in SUPPORTED_TOPOLOGIES:
        raise ValueError(
            f"unsupported topology: {topology!r}"
        )

    return sequence, str(topology)


def duplicate_relation(
    left: Mapping[str, object],
    right: Mapping[str, object],
) -> str | None:
    """Return the frozen complete-molecule equivalence relation, if any."""

    left_sequence, left_topology = _component(left)
    right_sequence, right_topology = _component(right)

    if len(left_sequence) != len(right_sequence):
        return None

    if left_sequence == right_sequence:
        return "exact_forward"

    right_rc = reverse_complement(
        right_sequence
    )

    if left_sequence == right_rc:
        return "exact_reverse_complement"

    if (
        left_topology == "circular"
        and right_topology == "circular"
    ):
        doubled = (
            right_sequence
            + right_sequence
        )

        position = doubled.find(
            left_sequence,
            1,
            len(doubled) - 1,
        )

        if position != -1:
            return "circular_rotation_forward"

        doubled_rc = (
            right_rc
            + right_rc
        )

        position = doubled_rc.find(
            left_sequence,
            1,
            len(doubled_rc) - 1,
        )

        if position != -1:
            return "circular_rotation_reverse_complement"

    return None


def circular_inner_containment(
    oriented_inner: str,
    outer_sequence: str,
    outer_circular: bool,
) -> bool | None:
    """Return outer-origin crossing for any rotation of a circular inner."""

    inner_length = len(
        oriented_inner
    )
    outer_length = len(
        outer_sequence
    )

    if inner_length >= outer_length:
        return None

    anchor_count = min(
        8,
        inner_length,
    )

    anchor_length = min(
        64,
        max(
            1,
            inner_length
            // (2 * anchor_count),
        ),
    )

    anchor_starts = sorted(
        {
            min(
                inner_length
                - anchor_length,
                (
                    index
                    * inner_length
                )
                // anchor_count,
            )
            for index in range(
                anchor_count
            )
        }
    )

    search_sequence = outer_sequence

    if (
        outer_circular
        and anchor_length > 1
    ):
        search_sequence = (
            outer_sequence
            + outer_sequence[
                : anchor_length - 1
            ]
        )

    anchors = [
        (
            search_sequence.count(
                oriented_inner[
                    start
                    : start + anchor_length
                ]
            ),
            start,
            oriented_inner[
                start
                : start + anchor_length
            ],
        )
        for start in anchor_starts
    ]

    for (
        _,
        inner_anchor_start,
        anchor,
    ) in sorted(anchors):
        search_start = 0

        while True:
            outer_anchor_start = (
                search_sequence.find(
                    anchor,
                    search_start,
                )
            )

            if outer_anchor_start == -1:
                break

            if (
                outer_anchor_start
                >= outer_length
            ):
                break

            left_match = 0

            maximum_extra = (
                inner_length
                - anchor_length
            )

            while (
                left_match
                < maximum_extra
            ):
                outer_index = (
                    outer_anchor_start
                    - left_match
                    - 1
                )

                if (
                    not outer_circular
                    and outer_index < 0
                ):
                    break

                inner_index = (
                    inner_anchor_start
                    - left_match
                    - 1
                ) % inner_length

                if (
                    outer_sequence[
                        outer_index
                        % outer_length
                    ]
                    != oriented_inner[
                        inner_index
                    ]
                ):
                    break

                left_match += 1

            right_match = 0

            while (
                right_match
                < maximum_extra
            ):
                outer_index = (
                    outer_anchor_start
                    + anchor_length
                    + right_match
                )

                if (
                    not outer_circular
                    and outer_index
                    >= outer_length
                ):
                    break

                inner_index = (
                    inner_anchor_start
                    + anchor_length
                    + right_match
                ) % inner_length

                if (
                    outer_sequence[
                        outer_index
                        % outer_length
                    ]
                    != oriented_inner[
                        inner_index
                    ]
                ):
                    break

                right_match += 1

            required_extra = (
                inner_length
                - anchor_length
            )

            if (
                left_match
                + right_match
                >= required_extra
            ):
                minimum_left = max(
                    0,
                    required_extra
                    - right_match,
                )

                maximum_left = min(
                    left_match,
                    required_extra,
                )

                if (
                    minimum_left
                    <= maximum_left
                ):
                    used_left = (
                        maximum_left
                    )

                    contained_start = (
                        outer_anchor_start
                        - used_left
                    )

                    crossing = (
                        outer_circular
                        and (
                            contained_start
                            < 0
                            or (
                                contained_start
                                + inner_length
                                > outer_length
                            )
                        )
                    )

                    return crossing

            search_start = (
                outer_anchor_start
                + 1
            )

    return None


def containment_relation(
    inner: Mapping[str, object],
    outer: Mapping[str, object],
) -> tuple[str, bool] | None:
    """Return orientation and outer-origin crossing for full containment."""

    inner_sequence, inner_topology = (
        _component(inner)
    )

    outer_sequence, outer_topology = (
        _component(outer)
    )

    if (
        len(inner_sequence)
        >= len(outer_sequence)
    ):
        return None

    outer_circular = (
        outer_topology
        == "circular"
    )

    if inner_topology == "circular":
        forward_crossing = (
            circular_inner_containment(
                inner_sequence,
                outer_sequence,
                outer_circular,
            )
        )

        if forward_crossing is not None:
            return (
                "forward",
                forward_crossing,
            )

        reverse_crossing = (
            circular_inner_containment(
                reverse_complement(
                    inner_sequence
                ),
                outer_sequence,
                outer_circular,
            )
        )

        if reverse_crossing is not None:
            return (
                "reverse_complement",
                reverse_crossing,
            )

        return None

    search_sequence = outer_sequence

    if (
        outer_circular
        and len(inner_sequence) > 1
    ):
        search_sequence = (
            outer_sequence
            + outer_sequence[
                : len(inner_sequence) - 1
            ]
        )

    forward_position = (
        search_sequence.find(
            inner_sequence
        )
    )

    if forward_position != -1:
        crossing = (
            forward_position
            + len(inner_sequence)
            > len(outer_sequence)
        )

        return (
            "forward",
            crossing,
        )

    reverse_sequence = (
        reverse_complement(
            inner_sequence
        )
    )

    reverse_position = (
        search_sequence.find(
            reverse_sequence
        )
    )

    if reverse_position != -1:
        crossing = (
            reverse_position
            + len(inner_sequence)
            > len(outer_sequence)
        )

        return (
            "reverse_complement",
            crossing,
        )

    return None


def sha256_text(text: str) -> str:
    """Return SHA256 of ASCII text."""

    return hashlib.sha256(
        text.encode("ascii")
    ).hexdigest()


def sequence_set_sha256(
    components: Mapping[
        str,
        Mapping[str, object],
    ],
) -> str:
    """Return the frozen named-component sequence-set fingerprint."""

    if not components:
        raise ValueError(
            "sequence set must contain at least one component"
        )

    digest = hashlib.sha256()

    for name in sorted(
        components
    ):
        if not isinstance(name, str) or not name:
            raise ValueError(
                "component name must be a non-empty string"
            )

        component = components[
            name
        ]

        sequence, _ = _component(
            component
        )

        line = (
            f"{name}\t"
            f"{len(sequence)}\t"
            f"{sha256_text(sequence)}\n"
        )

        digest.update(
            line.encode("ascii")
        )

    return digest.hexdigest()


def classify(
    duplicate_count: int,
    containment_rows: Sequence[
        Mapping[str, object]
    ],
) -> tuple[str, str, str]:
    """Apply the frozen source-truth adjudication precedence."""

    if (
        not isinstance(
            duplicate_count,
            int,
        )
        or isinstance(
            duplicate_count,
            bool,
        )
        or duplicate_count < 0
    ):
        raise ValueError(
            "duplicate_count must be a non-negative integer"
        )

    if duplicate_count > 0:
        return (
            EXCLUDE,
            "EXACT_DUPLICATE_PRIMARY_COMPONENTS",
            (
                "one or more distinct Primary Assembly components "
                "have sequence-equivalent complete molecules"
            ),
        )

    if containment_rows:
        topologies = set()

        for row in containment_rows:
            topology = row.get(
                "inner_topology"
            )

            if not isinstance(
                topology,
                str,
            ):
                topology = ""

            topologies.add(
                topology
                .strip()
                .lower()
            )

        if "linear" in topologies:
            return (
                EXCLUDE,
                "LINEAR_COMPONENT_FULLY_CONTAINED",
                (
                    "at least one fully contained inner Primary "
                    "Assembly component has linear topology"
                ),
            )

        if topologies == {
            "circular"
        }:
            return (
                SUITABLE,
                "CIRCULAR_CONTAINMENT_RETAINED",
                (
                    "all fully contained inner Primary Assembly "
                    "components are circular and retain a "
                    "topology-specific closure adjacency"
                ),
            )

        return (
            UNRESOLVED,
            "UNRESOLVED_SOURCE_TRUTH",
            (
                "full-containment topology is missing, unknown, "
                "or not covered by the pre-specified rules"
            ),
        )

    return (
        SUITABLE,
        "NO_SOURCE_REDUNDANCY",
        (
            "no exact duplication or full component containment "
            "was detected"
        ),
    )
