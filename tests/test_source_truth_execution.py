from __future__ import annotations

import csv
import hashlib
import json
from itertools import product
from pathlib import Path

import pytest

from bacselect.source_truth import (
    EXCLUDE,
    SUITABLE,
    UNRESOLVED,
    sha256_text,
)
from bacselect.source_truth_execution import (
    CandidateAudit,
    ComponentAudit,
    ContainmentEvidence,
    adjudicate_relations,
    decision_rows,
    evaluate_candidate,
    evaluate_components,
    load_candidate_population,
    load_component_index,
    load_package_manifest,
    load_primary_components,
    relation_rows,
    source_evidence_sha256,
)


def write_tsv(
    path: Path,
    fields: tuple[str, ...],
    rows: list[dict[str, str]],
) -> None:
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_fasta(
    path: Path,
    records: list[tuple[str, str]],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        "".join(
            f">{name} synthetic\n{sequence}\n"
            for name, sequence in records
        ),
        encoding="ascii",
    )


def make_candidate_batch(
    tmp_path: Path,
    *,
    accession: str = "GCA_000000001.1",
    components: tuple[
        tuple[str, str, str],
        ...,
    ] = (
        (
            "CP000001.1",
            "AACCGG",
            "linear",
        ),
    ),
    auxiliary: tuple[
        tuple[str, str],
        ...,
    ] = (),
) -> tuple[
    Path,
    Path,
    Path,
]:
    batch = (
        tmp_path
        / "batch-001"
    )

    batch.mkdir()

    relative_fasta = (
        f"ncbi_dataset/data/"
        f"{accession}/"
        f"{accession}_genomic.fna"
    )

    fasta = (
        batch
        / "package"
        / relative_fasta
    )

    write_fasta(
        fasta,
        [
            (
                name,
                sequence,
            )
            for name, sequence, _ in components
        ]
        + list(auxiliary),
    )

    fasta_sha = hashlib.sha256(
        fasta.read_bytes()
    ).hexdigest()

    candidate = (
        batch
        / "candidate-sequence-audit.tsv"
    )

    write_tsv(
        candidate,
        (
            "canonical_genbank_assembly_accession",
            "sequence_eligibility",
            "fasta_file",
            "fasta_sha256",
            "primary_assembly_records",
        ),
        [
            {
                "canonical_genbank_assembly_accession": accession,
                "sequence_eligibility": "eligible",
                "fasta_file": relative_fasta,
                "fasta_sha256": fasta_sha,
                "primary_assembly_records": str(
                    len(components)
                ),
            }
        ],
    )

    component = (
        batch
        / "component-sequence-audit.tsv"
    )

    write_tsv(
        component,
        (
            "canonical_genbank_assembly_accession",
            "component_genbank_accession",
            "length",
            "topology",
            "ambiguous_base_count",
            "ambiguous_symbols",
            "sequence_sha256",
        ),
        [
            {
                "canonical_genbank_assembly_accession": accession,
                "component_genbank_accession": name,
                "length": str(
                    len(sequence)
                ),
                "topology": topology,
                "ambiguous_base_count": "0",
                "ambiguous_symbols": "",
                "sequence_sha256": sha256_text(
                    sequence
                ),
            }
            for name, sequence, topology in components
        ],
    )

    manifest = (
        batch
        / "package-files.tsv"
    )

    write_tsv(
        manifest,
        (
            "path",
            "size_bytes",
            "sha256",
        ),
        [
            {
                "path": relative_fasta,
                "size_bytes": str(
                    fasta.stat().st_size
                ),
                "sha256": fasta_sha,
            }
        ],
    )

    return (
        candidate,
        component,
        manifest,
    )


def load_synthetic_components(
    tmp_path: Path,
    *,
    components: tuple[
        tuple[str, str, str],
        ...,
    ],
    auxiliary: tuple[
        tuple[str, str],
        ...,
    ] = (),
):
    candidate_path, component_path, manifest_path = (
        make_candidate_batch(
            tmp_path,
            components=components,
            auxiliary=auxiliary,
        )
    )

    population = load_candidate_population(
        [candidate_path],
        expected_total=1,
        expected_eligible=1,
        expected_ineligible=0,
    )

    candidate = population.candidates[
        0
    ]

    index = load_component_index(
        component_path,
        accessions={
            candidate.accession,
        },
    )

    manifest = load_package_manifest(
        manifest_path
    )

    reconstructed = load_primary_components(
        candidate,
        index[candidate.accession],
        manifest,
    )

    return (
        candidate,
        reconstructed,
    )


def test_population_reconstruction_and_membership_hash(
    tmp_path,
):
    candidate, _, _ = make_candidate_batch(
        tmp_path
    )

    population = load_candidate_population(
        [candidate],
        expected_total=1,
        expected_eligible=1,
        expected_ineligible=0,
    )

    assert population.total_records == 1
    assert population.eligible_records == 1
    assert population.ineligible_records == 0

    expected = hashlib.sha256(
        b"GCA_000000001.1\n"
    ).hexdigest()

    assert (
        population.membership_sha256
        == expected
    )


def test_population_accounting_fails_closed(
    tmp_path,
):
    candidate, _, _ = make_candidate_batch(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="eligible record count",
    ):
        load_candidate_population(
            [candidate],
            expected_total=1,
            expected_eligible=2,
            expected_ineligible=0,
        )


def test_duplicate_candidate_accession_fails_closed(
    tmp_path,
):
    first, _, _ = make_candidate_batch(
        tmp_path
    )

    second_dir = tmp_path / "second"
    second_dir.mkdir()

    second = (
        second_dir
        / "candidate-sequence-audit.tsv"
    )

    second.write_bytes(
        first.read_bytes()
    )

    with pytest.raises(
        ValueError,
        match="duplicate GCA",
    ):
        load_candidate_population(
            [
                first,
                second,
            ]
        )


def test_auxiliary_fasta_record_is_not_primary_component(
    tmp_path,
):
    _, components = load_synthetic_components(
        tmp_path,
        components=(
            (
                "CP000001.1",
                "AACCGG",
                "linear",
            ),
        ),
        auxiliary=(
            (
                "JUNK0001.1",
                "TTTT",
            ),
        ),
    )

    assert tuple(
        components
    ) == (
        "CP000001.1",
    )


def test_missing_candidate_fasta_manifest_entry_fails_closed(
    tmp_path,
):
    candidate_path, component_path, manifest_path = (
        make_candidate_batch(
            tmp_path
        )
    )

    population = load_candidate_population(
        [candidate_path]
    )

    candidate = population.candidates[
        0
    ]

    index = load_component_index(
        component_path,
        accessions={
            candidate.accession,
        },
    )

    write_tsv(
        manifest_path,
        (
            "path",
            "size_bytes",
            "sha256",
        ),
        [
            {
                "path": "other.file",
                "size_bytes": "0",
                "sha256": "0" * 64,
            }
        ],
    )

    manifest = load_package_manifest(
        manifest_path
    )

    with pytest.raises(
        ValueError,
        match="absent from package manifest",
    ):
        load_primary_components(
            candidate,
            index[candidate.accession],
            manifest,
        )


def test_component_sequence_sha_mismatch_fails_closed(
    tmp_path,
):
    candidate_path, component_path, manifest_path = (
        make_candidate_batch(
            tmp_path
        )
    )

    rows = list(
        csv.DictReader(
            component_path.open(
                newline="",
                encoding="utf-8",
            ),
            delimiter="\t",
        )
    )

    rows[0]["sequence_sha256"] = (
        "0" * 64
    )

    write_tsv(
        component_path,
        (
            "canonical_genbank_assembly_accession",
            "component_genbank_accession",
            "length",
            "topology",
            "ambiguous_base_count",
            "ambiguous_symbols",
            "sequence_sha256",
        ),
        rows,
    )

    population = load_candidate_population(
        [candidate_path]
    )

    candidate = population.candidates[
        0
    ]

    index = load_component_index(
        component_path,
        accessions={
            candidate.accession,
        },
    )

    manifest = load_package_manifest(
        manifest_path
    )

    with pytest.raises(
        ValueError,
        match="component SHA256 mismatch",
    ):
        load_primary_components(
            candidate,
            index[candidate.accession],
            manifest,
        )


@pytest.mark.parametrize(
    (
        "components",
        "expected_status",
        "expected_reason",
    ),
    [
        (
            {
                "A": {
                    "sequence": "AACCGG",
                    "topology": "linear",
                },
                "B": {
                    "sequence": "TTGCAA",
                    "topology": "linear",
                },
            },
            SUITABLE,
            "NO_SOURCE_REDUNDANCY",
        ),
        (
            {
                "A": {
                    "sequence": "AACG",
                    "topology": "linear",
                },
                "B": {
                    "sequence": "AACG",
                    "topology": "linear",
                },
            },
            EXCLUDE,
            "EXACT_DUPLICATE_PRIMARY_COMPONENTS",
        ),
        (
            {
                "A": {
                    "sequence": "AACG",
                    "topology": "linear",
                },
                "B": {
                    "sequence": "CGTT",
                    "topology": "linear",
                },
            },
            EXCLUDE,
            "EXACT_DUPLICATE_PRIMARY_COMPONENTS",
        ),
        (
            {
                "A": {
                    "sequence": "AACG",
                    "topology": "circular",
                },
                "B": {
                    "sequence": "CGAA",
                    "topology": "circular",
                },
            },
            EXCLUDE,
            "EXACT_DUPLICATE_PRIMARY_COMPONENTS",
        ),
        (
            {
                "A": {
                    "sequence": "AACG",
                    "topology": "circular",
                },
                "B": {
                    "sequence": "TCGT",
                    "topology": "circular",
                },
            },
            EXCLUDE,
            "EXACT_DUPLICATE_PRIMARY_COMPONENTS",
        ),
        (
            {
                "A": {
                    "sequence": "AAC",
                    "topology": "linear",
                },
                "B": {
                    "sequence": "GGAACGG",
                    "topology": "linear",
                },
            },
            EXCLUDE,
            "LINEAR_COMPONENT_FULLY_CONTAINED",
        ),
        (
            {
                "A": {
                    "sequence": "AAC",
                    "topology": "circular",
                },
                "B": {
                    "sequence": "GGAACGG",
                    "topology": "linear",
                },
            },
            SUITABLE,
            "CIRCULAR_CONTAINMENT_RETAINED",
        ),
        (
            {
                "A": {
                    "sequence": "GGAA",
                    "topology": "linear",
                },
                "B": {
                    "sequence": "AACCGG",
                    "topology": "circular",
                },
            },
            EXCLUDE,
            "LINEAR_COMPONENT_FULLY_CONTAINED",
        ),
        (
            {
                "A": {
                    "sequence": "AACG",
                    "topology": "linear",
                },
                "B": {
                    "sequence": "AACG",
                    "topology": "linear",
                },
                "C": {
                    "sequence": "TTAACGTT",
                    "topology": "linear",
                },
            },
            EXCLUDE,
            "EXACT_DUPLICATE_PRIMARY_COMPONENTS",
        ),
    ],
)
def test_source_truth_execution_cases(
    components,
    expected_status,
    expected_reason,
):
    decision = evaluate_components(
        "GCA_000000001.1",
        components,
    )

    assert decision.status == expected_status
    assert decision.reason == expected_reason


def test_circular_outer_origin_crossing_is_recorded():
    decision = evaluate_components(
        "GCA_000000001.1",
        {
            "A": {
                "sequence": "GGAA",
                "topology": "linear",
            },
            "B": {
                "sequence": "AACCGG",
                "topology": "circular",
            },
        },
    )

    assert len(
        decision.containment_relations
    ) == 1

    assert (
        decision
        .containment_relations[0]
        .outer_origin_crossing
        is True
    )


def test_unresolved_containment_topology_adjudication():
    status, reason, _ = adjudicate_relations(
        (),
        (
            ContainmentEvidence(
                inner_component="A",
                outer_component="B",
                inner_topology="unknown",
                outer_topology="linear",
                orientation="forward",
                outer_origin_crossing=False,
            ),
        ),
    )

    assert status == UNRESOLVED
    assert reason == "UNRESOLVED_SOURCE_TRUTH"


def test_unsupported_component_topology_fails_closed():
    with pytest.raises(
        ValueError,
        match="unsupported topology",
    ):
        evaluate_components(
            "GCA_000000001.1",
            {
                "A": {
                    "sequence": "AACG",
                    "topology": "unknown",
                },
            },
        )


def test_malformed_component_sequence_fails_closed():
    with pytest.raises(
        ValueError,
        match="unsupported symbols",
    ):
        evaluate_components(
            "GCA_000000001.1",
            {
                "A": {
                    "sequence": "AACN",
                    "topology": "linear",
                },
            },
        )


def test_decision_and_relation_rows_are_deterministic():
    first = evaluate_components(
        "GCA_000000002.1",
        {
            "Z": {
                "sequence": "AACG",
                "topology": "linear",
            },
            "A": {
                "sequence": "AACG",
                "topology": "linear",
            },
        },
        source_evidence_sha256="2" * 64,
    )

    second = evaluate_components(
        "GCA_000000001.1",
        {
            "B": {
                "sequence": "AAC",
                "topology": "linear",
            },
            "A": {
                "sequence": "GGAACGG",
                "topology": "linear",
            },
        },
        source_evidence_sha256="1" * 64,
    )

    decisions_forward = decision_rows(
        [
            first,
            second,
        ]
    )

    decisions_reverse = decision_rows(
        [
            second,
            first,
        ]
    )

    assert (
        decisions_forward
        == decisions_reverse
    )

    relations_forward = relation_rows(
        [
            first,
            second,
        ]
    )

    relations_reverse = relation_rows(
        [
            second,
            first,
        ]
    )

    assert (
        relations_forward
        == relations_reverse
    )


def reverse_complement_oracle(
    sequence: str,
) -> str:
    table = str.maketrans(
        "ACGT",
        "TGCA",
    )

    return sequence.translate(
        table
    )[::-1]


def rotations(
    sequence: str,
) -> set[str]:
    return {
        sequence[index:]
        + sequence[:index]
        for index in range(
            len(sequence)
        )
    }


def duplicate_oracle(
    left_sequence: str,
    left_topology: str,
    right_sequence: str,
    right_topology: str,
) -> bool:
    if len(left_sequence) != len(
        right_sequence
    ):
        return False

    if (
        left_sequence
        == right_sequence
    ):
        return True

    right_rc = reverse_complement_oracle(
        right_sequence
    )

    if left_sequence == right_rc:
        return True

    if not (
        left_topology == "circular"
        and right_topology == "circular"
    ):
        return False

    return (
        left_sequence
        in rotations(
            right_sequence
        )
        or left_sequence
        in rotations(
            right_rc
        )
    )


def test_duplicate_detection_matches_independent_oracle_exhaustively():
    sequences = [
        "".join(symbols)
        for length in range(
            1,
            4,
        )
        for symbols in product(
            "ACGT",
            repeat=length,
        )
    ]

    for left_sequence in sequences:
        for right_sequence in sequences:
            if len(left_sequence) != len(
                right_sequence
            ):
                continue

            for left_topology in (
                "linear",
                "circular",
            ):
                for right_topology in (
                    "linear",
                    "circular",
                ):
                    expected = duplicate_oracle(
                        left_sequence,
                        left_topology,
                        right_sequence,
                        right_topology,
                    )

                    decision = evaluate_components(
                        "GCA_000000001.1",
                        {
                            "A": {
                                "sequence": left_sequence,
                                "topology": left_topology,
                            },
                            "B": {
                                "sequence": right_sequence,
                                "topology": right_topology,
                            },
                        },
                    )

                    observed = bool(
                        decision.duplicate_relations
                    )

                    assert observed is expected


def test_evidence_bound_candidate_decision(
    tmp_path,
):
    candidate_path, component_path, manifest_path = (
        make_candidate_batch(
            tmp_path
        )
    )

    population = load_candidate_population(
        [candidate_path],
        expected_total=1,
        expected_eligible=1,
        expected_ineligible=0,
    )

    candidate = population.candidates[0]

    component_index = load_component_index(
        component_path,
        accessions={
            candidate.accession,
        },
    )

    package_manifest = load_package_manifest(
        manifest_path
    )

    decision = evaluate_candidate(
        candidate,
        component_index[candidate.accession],
        package_manifest,
    )

    assert (
        decision.source_evidence_sha256
        is not None
    )

    assert (
        decision.source_evidence_sha256
        != candidate.fasta_sha256
    )

    rows = decision_rows(
        [decision]
    )

    assert (
        rows[0]["source_evidence_sha256"]
        == decision.source_evidence_sha256
    )

    assert (
        rows[0]["sequence_set_sha256"]
        == decision.sequence_set_sha256
    )


def test_unbound_candidate_cannot_be_written():
    decision = evaluate_components(
        "GCA_000000001.1",
        {
            "A": {
                "sequence": "AACCGG",
                "topology": "linear",
            },
        },
    )

    with pytest.raises(
        ValueError,
        match="lacks frozen source-evidence identity",
    ):
        decision_rows(
            [decision]
        )


def test_primary_component_count_mismatch_fails_closed(
    tmp_path,
):
    candidate_path, component_path, manifest_path = (
        make_candidate_batch(
            tmp_path
        )
    )

    rows = list(
        csv.DictReader(
            candidate_path.open(
                newline="",
                encoding="utf-8",
            ),
            delimiter="\t",
        )
    )

    rows[0]["primary_assembly_records"] = "2"

    write_tsv(
        candidate_path,
        tuple(rows[0]),
        rows,
    )

    population = load_candidate_population(
        [candidate_path]
    )

    candidate = population.candidates[0]

    component_index = load_component_index(
        component_path,
        accessions={
            candidate.accession,
        },
    )

    package_manifest = load_package_manifest(
        manifest_path
    )

    with pytest.raises(
        ValueError,
        match="component count mismatch",
    ):
        evaluate_candidate(
            candidate,
            component_index[candidate.accession],
            package_manifest,
        )


def test_post_audit_fasta_mutation_fails_closed(
    tmp_path,
):
    candidate_path, component_path, manifest_path = (
        make_candidate_batch(
            tmp_path
        )
    )

    population = load_candidate_population(
        [candidate_path]
    )

    candidate = population.candidates[0]

    component_index = load_component_index(
        component_path,
        accessions={
            candidate.accession,
        },
    )

    package_manifest = load_package_manifest(
        manifest_path
    )

    fasta_path = (
        candidate.batch_dir
        / "package"
        / candidate.fasta_file
    )

    original = fasta_path.read_text(
        encoding="ascii",
    )

    mutated = original.replace(
        "AACCGG",
        "AACCGT",
    )

    assert len(mutated) == len(original)

    fasta_path.write_text(
        mutated,
        encoding="ascii",
    )

    with pytest.raises(
        ValueError,
        match="FASTA SHA differs from package manifest",
    ):
        evaluate_candidate(
            candidate,
            component_index[candidate.accession],
            package_manifest,
        )


def containment_oracle(
    inner_sequence: str,
    inner_topology: str,
    outer_sequence: str,
    outer_topology: str,
) -> bool:
    """Independent brute-force full-containment oracle."""

    if len(inner_sequence) >= len(
        outer_sequence
    ):
        return False

    orientations = (
        inner_sequence,
        reverse_complement_oracle(
            inner_sequence
        ),
    )

    variants: set[str] = set()

    for oriented in orientations:
        if inner_topology == "circular":
            variants.update(
                rotations(
                    oriented
                )
            )
        else:
            variants.add(
                oriented
            )

    for variant in variants:
        if outer_topology == "linear":
            if variant in outer_sequence:
                return True

            continue

        for start in range(
            len(outer_sequence)
        ):
            window = "".join(
                outer_sequence[
                    (start + offset)
                    % len(outer_sequence)
                ]
                for offset in range(
                    len(variant)
                )
            )

            if window == variant:
                return True

    return False


def test_containment_matches_independent_oracle_exhaustively():
    by_length = {
        length: [
            "".join(symbols)
            for symbols in product(
                "ACGT",
                repeat=length,
            )
        ]
        for length in (
            1,
            2,
            3,
        )
    }

    cases = 0

    for inner_length in (
        1,
        2,
    ):
        for outer_length in range(
            inner_length + 1,
            4,
        ):
            for inner_sequence in by_length[
                inner_length
            ]:
                for outer_sequence in by_length[
                    outer_length
                ]:
                    for inner_topology in (
                        "linear",
                        "circular",
                    ):
                        for outer_topology in (
                            "linear",
                            "circular",
                        ):
                            expected = containment_oracle(
                                inner_sequence,
                                inner_topology,
                                outer_sequence,
                                outer_topology,
                            )

                            decision = evaluate_components(
                                "GCA_000000001.1",
                                {
                                    "inner": {
                                        "sequence": inner_sequence,
                                        "topology": inner_topology,
                                    },
                                    "outer": {
                                        "sequence": outer_sequence,
                                        "topology": outer_topology,
                                    },
                                },
                            )

                            observed = bool(
                                decision.containment_relations
                            )

                            assert observed is expected

                            if not expected:
                                assert (
                                    decision.status
                                    == SUITABLE
                                )
                                assert (
                                    decision.reason
                                    == "NO_SOURCE_REDUNDANCY"
                                )
                            elif (
                                inner_topology
                                == "linear"
                            ):
                                assert (
                                    decision.status
                                    == EXCLUDE
                                )
                                assert (
                                    decision.reason
                                    == "LINEAR_COMPONENT_FULLY_CONTAINED"
                                )
                            else:
                                assert (
                                    decision.status
                                    == SUITABLE
                                )
                                assert (
                                    decision.reason
                                    == "CIRCULAR_CONTAINMENT_RETAINED"
                                )

                            cases += 1

    assert cases == 5376


def test_source_evidence_hash_binds_topology_and_exact_byte_contract(
    tmp_path,
):
    candidate_path, component_path, manifest_path = (
        make_candidate_batch(
            tmp_path
        )
    )

    population = load_candidate_population(
        [candidate_path]
    )

    candidate = population.candidates[0]

    component_index = load_component_index(
        component_path,
        accessions={
            candidate.accession,
        },
    )

    components = component_index[
        candidate.accession
    ]

    manifest = load_package_manifest(
        manifest_path
    )

    observed = source_evidence_sha256(
        candidate,
        components,
        manifest,
    )

    package_row = manifest[
        candidate.fasta_file
    ]

    expected_payload = {
        "candidate": {
            "canonical_genbank_assembly_accession": candidate.accession,
            "fasta_file": candidate.fasta_file,
            "fasta_sha256": candidate.fasta_sha256,
            "primary_assembly_records": 1,
        },
        "package": {
            "path": candidate.fasta_file,
            "size_bytes": package_row.size_bytes,
            "sha256": candidate.fasta_sha256,
        },
        "primary_assembly_components": [
            {
                "component_genbank_accession": "CP000001.1",
                "length": 6,
                "sequence_sha256": sha256_text(
                    "AACCGG"
                ),
                "topology": "linear",
            }
        ],
    }

    expected_bytes = json.dumps(
        expected_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")

    expected = hashlib.sha256(
        expected_bytes
    ).hexdigest()

    assert observed == expected

    original = components[0]

    changed_topology = (
        ComponentAudit(
            accession=original.accession,
            component_accession=original.component_accession,
            length=original.length,
            topology="circular",
            sequence_sha256=original.sequence_sha256,
        ),
    )

    topology_changed = source_evidence_sha256(
        candidate,
        changed_topology,
        manifest,
    )

    assert topology_changed != observed
