from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bacselect import source_chromosome_integrity
from bacselect.source_chromosome_integrity import (
    ChromosomeIntegrityDecision,
    HistoricalReuseEvidence,
)
from bacselect.source_chromosome_integrity_execution import (
    Stage3ExecutionError,
    evaluate_stage3_candidate,
)
from bacselect.source_truth_execution import (
    CandidateAudit,
    ComponentAudit,
    PackageFile,
    source_evidence_sha256,
)


def sha256_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def sha256_text(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("ascii")
    ).hexdigest()


def gbff_record(
    *,
    accession: str,
    sequence: str,
    topology: str,
    definition: str,
) -> str:
    definition_lines = (
        definition.split(
            "\n"
        )
    )

    definition_text = (
        "DEFINITION  "
        + definition_lines[0]
        + "\n"
    )

    for continuation in (
        definition_lines[1:]
    ):
        definition_text += (
            " " * 12
            + continuation
            + "\n"
        )

    return (
        f"LOCUS       {accession.split('.')[0]} "
        f"{len(sequence)} bp DNA {topology} BCT 01-JAN-2000\n"
        f"{definition_text}"
        f"ACCESSION   {accession.split('.')[0]}\n"
        f"VERSION     {accession}\n"
        "ORIGIN\n"
        f"        1 {sequence.lower()}\n"
        "//\n"
    )


def make_fixture(
    tmp_path: Path,
    *,
    accession: str = "GCA_000000001.1",
    components=(
        {
            "accession": "CP000001.1",
            "sequence": "AACCGGTT",
            "topology": "linear",
            "molecule_class": "Chromosome",
            "definition": "chromosome, complete sequence",
            "assembly_unit": "Primary Assembly",
        },
    ),
    layout: str = "nested",
    gbff_name: str = "genomic.gbff",
):
    batch = (
        tmp_path
        / "batch-001"
    )

    batch.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit_path = (
        batch
        / "candidate-sequence-audit.tsv"
    )

    audit_path.write_text(
        "synthetic fixture\n",
        encoding="utf-8",
    )

    relative_root = (
        Path("ncbi_dataset")
        / "data"
        / accession
    )

    physical_root = (
        batch
        / relative_root
        if layout == "direct"
        else batch
        / "package"
        / relative_root
    )

    physical_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    fasta_name = (
        f"{accession}_genomic.fna"
    )

    fasta_path = (
        physical_root
        / fasta_name
    )

    fasta_text = "".join(
        (
            f">{component['accession']}\n"
            f"{component['sequence']}\n"
        )
        for component in components
        if component[
            "assembly_unit"
        ] == "Primary Assembly"
    )

    fasta_path.write_text(
        fasta_text,
        encoding="ascii",
    )

    sequence_report_path = (
        physical_root
        / "sequence_report.jsonl"
    )

    sequence_rows = []

    for component in components:
        sequence_rows.append(
            {
                "assemblyAccession":
                    accession,
                "assemblyUnit":
                    component[
                        "assembly_unit"
                    ],
                "genbankAccession":
                    component[
                        "accession"
                    ],
                "length":
                    len(
                        component[
                            "sequence"
                        ]
                    ),
                "assignedMoleculeLocationType":
                    component[
                        "molecule_class"
                    ],
            }
        )

    sequence_report_path.write_text(
        "".join(
            json.dumps(
                row,
                sort_keys=True,
            )
            + "\n"
            for row in sequence_rows
        ),
        encoding="utf-8",
    )

    gbff_path = (
        physical_root
        / gbff_name
    )

    gbff_path.write_text(
        "".join(
            gbff_record(
                accession=(
                    component[
                        "accession"
                    ]
                ),
                sequence=(
                    component[
                        "sequence"
                    ]
                ),
                topology=(
                    component[
                        "topology"
                    ]
                ),
                definition=(
                    component[
                        "definition"
                    ]
                ),
            )
            for component in components
        ),
        encoding="utf-8",
    )

    primary_components = tuple(
        component
        for component in components
        if component[
            "assembly_unit"
        ] == "Primary Assembly"
    )

    fasta_sha = sha256_bytes(
        fasta_path.read_bytes()
    )

    candidate = CandidateAudit(
        accession=accession,
        audit_path=audit_path,
        fasta_file=fasta_name,
        fasta_sha256=fasta_sha,
        primary_assembly_records=len(
            primary_components
        ),
    )

    component_rows = tuple(
        ComponentAudit(
            accession=accession,
            component_accession=(
                component[
                    "accession"
                ]
            ),
            length=len(
                component[
                    "sequence"
                ]
            ),
            topology=(
                component[
                    "topology"
                ]
            ),
            sequence_sha256=(
                sha256_text(
                    component[
                        "sequence"
                    ]
                )
            ),
        )
        for component in primary_components
    )

    relative_fasta = (
        relative_root
        / fasta_name
    )

    relative_sequence_report = (
        relative_root
        / "sequence_report.jsonl"
    )

    relative_gbff = (
        relative_root
        / gbff_name
    )

    package_manifest = {
        relative_fasta.as_posix():
            PackageFile(
                relative_path=(
                    relative_fasta.as_posix()
                ),
                size_bytes=(
                    fasta_path.stat().st_size
                ),
                sha256=fasta_sha,
            ),
        relative_sequence_report.as_posix():
            PackageFile(
                relative_path=(
                    relative_sequence_report.as_posix()
                ),
                size_bytes=(
                    sequence_report_path.stat().st_size
                ),
                sha256=sha256_bytes(
                    sequence_report_path.read_bytes()
                ),
            ),
        relative_gbff.as_posix():
            PackageFile(
                relative_path=(
                    relative_gbff.as_posix()
                ),
                size_bytes=(
                    gbff_path.stat().st_size
                ),
                sha256=sha256_bytes(
                    gbff_path.read_bytes()
                ),
            ),
    }

    expected_source_sha = (
        source_evidence_sha256(
            candidate,
            component_rows,
            package_manifest,
        )
    )

    return {
        "candidate":
            candidate,
        "component_rows":
            component_rows,
        "package_manifest":
            package_manifest,
        "expected_source_sha":
            expected_source_sha,
        "sequence_report_path":
            sequence_report_path,
        "gbff_path":
            gbff_path,
    }


def evaluate_fixture(
    fixture,
    *,
    historical=None,
    historical_provider=None,
):
    if historical is not None:
        assert historical_provider is None

        def historical_provider(
            accession,
        ):
            return historical

    return evaluate_stage3_candidate(
        candidate=fixture[
            "candidate"
        ],
        component_rows=fixture[
            "component_rows"
        ],
        package_manifest=fixture[
            "package_manifest"
        ],
        expected_source_evidence_sha256=(
            fixture[
                "expected_source_sha"
            ]
        ),
        historical_provider=historical_provider,
    )


@pytest.mark.parametrize(
    "layout",
    [
        "direct",
        "nested",
    ],
)
def test_verified_manifest_layouts_are_supported(
    tmp_path,
    layout,
):
    fixture = make_fixture(
        tmp_path,
        layout=layout,
    )

    observed = evaluate_fixture(
        fixture
    )

    assert observed.decision.status == (
        source_chromosome_integrity.PASS
    )

    assert observed.decision.reason == (
        "NO_CHROMOSOME_INTEGRITY_TRIGGER"
    )


def test_stage1_source_evidence_is_rebound(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    observed = evaluate_fixture(
        fixture
    )

    assert (
        observed.source_evidence_sha256
        == fixture[
            "expected_source_sha"
        ]
    )


def test_stage1_source_evidence_mismatch_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="Stage 1 source-evidence SHA256 mismatch",
    ):
        evaluate_stage3_candidate(
            candidate=fixture[
                "candidate"
            ],
            component_rows=fixture[
                "component_rows"
            ],
            package_manifest=fixture[
                "package_manifest"
            ],
            expected_source_evidence_sha256=(
                "0" * 64
            ),
        )


def test_nontriggered_candidate_passes(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    observed = evaluate_fixture(
        fixture
    )

    assert observed.trigger.triggered is False
    assert observed.trigger.chromosome_component_count == 1
    assert (
        observed.trigger.closure_supported_chromosome_count
        == 1
    )
    assert (
        observed.trigger.closure_unsupported_chromosome_count
        == 0
    )
    assert observed.decision.triggered is False
    assert observed.decision.historical_adjudication_reused is False


def test_nonchromosomal_components_do_not_trigger(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=(
            {
                "accession": "CP000001.1",
                "sequence": "AACCGGTT",
                "topology": "linear",
                "molecule_class": "Plasmid",
                "definition": "plasmid sequence",
                "assembly_unit": "Primary Assembly",
            },
            {
                "accession": "CP000002.1",
                "sequence": "AACCGGTA",
                "topology": "linear",
                "molecule_class": "Plasmid",
                "definition": "plasmid sequence",
                "assembly_unit": "Primary Assembly",
            },
        ),
    )

    observed = evaluate_fixture(
        fixture
    )

    assert observed.trigger.chromosome_component_count == 0
    assert observed.trigger.triggered is False


def trigger_components(
    *,
    first_definition="chromosome one, complete sequence",
    second_definition="chromosome two sequence",
):
    return (
        {
            "accession": "CP000001.1",
            "sequence": "AACCGGTT",
            "topology": "linear",
            "molecule_class": "Chromosome",
            "definition": first_definition,
            "assembly_unit": "Primary Assembly",
        },
        {
            "accession": "CP000002.1",
            "sequence": "AACCGGTA",
            "topology": "linear",
            "molecule_class": "Chromosome",
            "definition": second_definition,
            "assembly_unit": "Primary Assembly",
        },
    )


def test_trigger_without_historical_adjudication_is_unresolved(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    observed = evaluate_fixture(
        fixture
    )

    assert observed.trigger.triggered is True
    assert observed.trigger.chromosome_component_count == 2
    assert (
        observed.trigger.closure_supported_chromosome_count
        == 1
    )
    assert (
        observed.trigger.closure_unsupported_chromosome_count
        == 1
    )
    assert observed.decision.status == (
        source_chromosome_integrity.UNRESOLVED
    )
    assert observed.decision.reason == (
        "NO_REUSABLE_HISTORICAL_ADJUDICATION"
    )


@pytest.mark.parametrize(
    (
        "outcome",
        "status",
        "reason",
    ),
    [
        (
            source_chromosome_integrity.HISTORICAL_RETAIN,
            source_chromosome_integrity.PASS,
            "HISTORICAL_RETAIN_CONFIRMED_MULTIPARTITE",
        ),
        (
            source_chromosome_integrity.HISTORICAL_EXCLUDE,
            source_chromosome_integrity.EXCLUDE,
            "HISTORICAL_FRAGMENTED_CHROMOSOME_SET",
        ),
        (
            source_chromosome_integrity.HISTORICAL_UNRESOLVED,
            source_chromosome_integrity.UNRESOLVED,
            "HISTORICAL_UNRESOLVED",
        ),
    ],
)
def test_exact_historical_outcome_mapping(
    tmp_path,
    outcome,
    status,
    reason,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    historical = HistoricalReuseEvidence(
        uses_historical_project_finch_package=True,
        cache_content_verification="pass",
        adjudication_accession="GCA_000000001.1",
        adjudication_outcome=outcome,
    )

    observed = evaluate_fixture(
        fixture,
        historical=historical,
    )

    assert observed.decision.status == status
    assert observed.decision.reason == reason
    assert observed.decision.triggered is True
    assert observed.decision.historical_adjudication_reused is True


def test_fresh_package_trigger_remains_unresolved(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    historical = HistoricalReuseEvidence(
        uses_historical_project_finch_package=False,
        cache_content_verification=None,
        adjudication_accession=None,
        adjudication_outcome=None,
    )

    observed = evaluate_fixture(
        fixture,
        historical=historical,
    )

    assert observed.decision.status == (
        source_chromosome_integrity.UNRESOLVED
    )
    assert observed.decision.reason == (
        "NOT_HISTORICAL_PROJECT_FINCH_PACKAGE"
    )


def test_fallback_to_fresh_cache_state_remains_unresolved(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    historical = HistoricalReuseEvidence(
        uses_historical_project_finch_package=True,
        cache_content_verification="fallback_to_fresh",
        adjudication_accession="GCA_000000001.1",
        adjudication_outcome=(
            source_chromosome_integrity.HISTORICAL_RETAIN
        ),
    )

    observed = evaluate_fixture(
        fixture,
        historical=historical,
    )

    assert observed.decision.reason == (
        "HISTORICAL_CACHE_NOT_VERIFIED"
    )
    assert observed.decision.historical_adjudication_reused is False


def test_historical_adjudication_absence_remains_unresolved(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    historical = HistoricalReuseEvidence(
        uses_historical_project_finch_package=True,
        cache_content_verification="pass",
        adjudication_accession=None,
        adjudication_outcome=None,
    )

    observed = evaluate_fixture(
        fixture,
        historical=historical,
    )

    assert observed.decision.reason == (
        "HISTORICAL_ADJUDICATION_ABSENT"
    )


def test_historical_accession_mismatch_remains_unresolved(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    historical = HistoricalReuseEvidence(
        uses_historical_project_finch_package=True,
        cache_content_verification="pass",
        adjudication_accession="GCA_000000002.1",
        adjudication_outcome=(
            source_chromosome_integrity.HISTORICAL_RETAIN
        ),
    )

    observed = evaluate_fixture(
        fixture,
        historical=historical,
    )

    assert observed.decision.reason == (
        "HISTORICAL_ACCESSION_MISMATCH"
    )


def test_unknown_historical_outcome_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    historical = HistoricalReuseEvidence(
        uses_historical_project_finch_package=True,
        cache_content_verification="pass",
        adjudication_accession="GCA_000000001.1",
        adjudication_outcome="UNKNOWN",
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="unknown historical adjudication outcome",
    ):
        evaluate_fixture(
            fixture,
            historical=historical,
        )


def test_unknown_cache_state_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    historical = HistoricalReuseEvidence(
        uses_historical_project_finch_package=True,
        cache_content_verification="maybe",
        adjudication_accession="GCA_000000001.1",
        adjudication_outcome=(
            source_chromosome_integrity.HISTORICAL_RETAIN
        ),
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="unknown cache content verification state",
    ):
        evaluate_fixture(
            fixture,
            historical=historical,
        )


def test_multiline_definition_is_reconstructed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(
            first_definition=(
                "chromosome one,\n"
                "complete sequence"
            ),
            second_definition=(
                "chromosome two,\n"
                "complete sequence"
            ),
        ),
    )

    observed = evaluate_fixture(
        fixture
    )

    assert observed.trigger.triggered is False
    assert (
        observed.trigger.closure_supported_chromosome_count
        == 2
    )


@pytest.mark.parametrize(
    "word",
    [
        "incomplete",
        "incompletely",
        "completion",
        "completely",
    ],
)
def test_nonstandalone_complete_substrings_do_not_close(
    tmp_path,
    word,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(
            first_definition=(
                f"chromosome one {word} sequence"
            ),
            second_definition=(
                "chromosome two sequence"
            ),
        ),
    )

    observed = evaluate_fixture(
        fixture
    )

    assert observed.trigger.triggered is True
    assert (
        observed.trigger.closure_supported_chromosome_count
        == 0
    )


def test_circular_topology_supplies_closure(
    tmp_path,
):
    components = list(
        trigger_components(
            first_definition="chromosome one sequence",
            second_definition="chromosome two sequence",
        )
    )

    components[0] = {
        **components[0],
        "topology": "circular",
    }

    fixture = make_fixture(
        tmp_path,
        components=tuple(
            components
        ),
    )

    observed = evaluate_fixture(
        fixture
    )

    assert (
        observed.trigger.closure_supported_chromosome_count
        == 1
    )


def rewrite_manifest_identity(
    fixture,
    *,
    relative_path: str,
):
    physical = None

    for candidate in (
        fixture[
            "candidate"
        ].batch_dir
        / relative_path,
        fixture[
            "candidate"
        ].batch_dir
        / "package"
        / relative_path,
    ):
        if candidate.is_file():
            physical = candidate
            break

    assert physical is not None

    fixture[
        "package_manifest"
    ][
        relative_path
    ] = PackageFile(
        relative_path=relative_path,
        size_bytes=physical.stat().st_size,
        sha256=sha256_bytes(
            physical.read_bytes()
        ),
    )


def test_missing_molecule_class_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    path = fixture[
        "sequence_report_path"
    ]

    row = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    row.pop(
        "assignedMoleculeLocationType"
    )

    path.write_text(
        json.dumps(
            row,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    relative = next(
        key
        for key in fixture[
            "package_manifest"
        ]
        if key.endswith(
            "sequence_report.jsonl"
        )
    )

    rewrite_manifest_identity(
        fixture,
        relative_path=relative,
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="molecule class",
    ):
        evaluate_fixture(
            fixture
        )


def test_sequence_report_assembly_mismatch_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    path = fixture[
        "sequence_report_path"
    ]

    row = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    row[
        "assemblyAccession"
    ] = "GCA_000000002.1"

    path.write_text(
        json.dumps(
            row,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    relative = next(
        key
        for key in fixture[
            "package_manifest"
        ]
        if key.endswith(
            "sequence_report.jsonl"
        )
    )

    rewrite_manifest_identity(
        fixture,
        relative_path=relative,
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="assembly accession mismatch",
    ):
        evaluate_fixture(
            fixture
        )


def test_exact_component_version_mismatch_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    path = fixture[
        "gbff_path"
    ]

    text = path.read_text(
        encoding="utf-8"
    ).replace(
        "VERSION     CP000001.1",
        "VERSION     CP000001.2",
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    relative = next(
        key
        for key in fixture[
            "package_manifest"
        ]
        if key.endswith(
            ".gbff"
        )
    )

    rewrite_manifest_identity(
        fixture,
        relative_path=relative,
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="GBFF components do not match sequence report",
    ):
        evaluate_fixture(
            fixture
        )


def test_topology_disagreement_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    path = fixture[
        "gbff_path"
    ]

    path.write_text(
        path.read_text(
            encoding="utf-8"
        ).replace(
            " linear ",
            " circular ",
        ),
        encoding="utf-8",
    )

    relative = next(
        key
        for key in fixture[
            "package_manifest"
        ]
        if key.endswith(
            ".gbff"
        )
    )

    rewrite_manifest_identity(
        fixture,
        relative_path=relative,
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="GBFF topology differs",
    ):
        evaluate_fixture(
            fixture
        )


def test_missing_definition_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    path = fixture[
        "gbff_path"
    ]

    lines = [
        line
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if not line.startswith(
            "DEFINITION"
        )
    ]

    path.write_text(
        "\n".join(
            lines
        )
        + "\n",
        encoding="utf-8",
    )

    relative = next(
        key
        for key in fixture[
            "package_manifest"
        ]
        if key.endswith(
            ".gbff"
        )
    )

    rewrite_manifest_identity(
        fixture,
        relative_path=relative,
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="exactly one DEFINITION",
    ):
        evaluate_fixture(
            fixture
        )


def test_empty_definition_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    path = fixture[
        "gbff_path"
    ]

    lines = path.read_text(
        encoding="utf-8"
    ).splitlines()

    lines = [
        (
            "DEFINITION  "
            if line.startswith(
                "DEFINITION"
            )
            else line
        )
        for line in lines
    ]

    path.write_text(
        "\n".join(
            lines
        )
        + "\n",
        encoding="utf-8",
    )

    relative = next(
        key
        for key in fixture[
            "package_manifest"
        ]
        if key.endswith(
            ".gbff"
        )
    )

    rewrite_manifest_identity(
        fixture,
        relative_path=relative,
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="DEFINITION must not be empty",
    ):
        evaluate_fixture(
            fixture
        )


def test_duplicate_definition_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    path = fixture[
        "gbff_path"
    ]

    text = path.read_text(
        encoding="utf-8"
    ).replace(
        "ACCESSION",
        "DEFINITION  duplicate definition\nACCESSION",
        1,
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    relative = next(
        key
        for key in fixture[
            "package_manifest"
        ]
        if key.endswith(
            ".gbff"
        )
    )

    rewrite_manifest_identity(
        fixture,
        relative_path=relative,
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="exactly one DEFINITION",
    ):
        evaluate_fixture(
            fixture
        )


def test_sequence_report_component_set_mismatch_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    path = fixture[
        "sequence_report_path"
    ]

    row = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    row[
        "genbankAccession"
    ] = "CP999999.1"

    path.write_text(
        json.dumps(
            row,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    relative = next(
        key
        for key in fixture[
            "package_manifest"
        ]
        if key.endswith(
            "sequence_report.jsonl"
        )
    )

    rewrite_manifest_identity(
        fixture,
        relative_path=relative,
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="GBFF components do not match sequence report",
    ):
        evaluate_fixture(
            fixture
        )


def test_duplicate_sequence_report_component_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    path = fixture[
        "sequence_report_path"
    ]

    original = path.read_text(
        encoding="utf-8"
    )

    path.write_text(
        original
        + original,
        encoding="utf-8",
    )

    relative = next(
        key
        for key in fixture[
            "package_manifest"
        ]
        if key.endswith(
            "sequence_report.jsonl"
        )
    )

    rewrite_manifest_identity(
        fixture,
        relative_path=relative,
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="duplicate sequence-report component",
    ):
        evaluate_fixture(
            fixture
        )


def test_corrupt_sequence_report_is_rejected_by_manifest_sha(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    fixture[
        "sequence_report_path"
    ].write_text(
        "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="sequence report .* differs from package manifest",
    ):
        evaluate_fixture(
            fixture
        )


def test_corrupt_gbff_is_rejected_by_manifest_sha(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    fixture[
        "gbff_path"
    ].write_text(
        "corrupt\n",
        encoding="utf-8",
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="GBFF .* differs from package manifest",
    ):
        evaluate_fixture(
            fixture
        )


def test_efetch_gbff_name_is_accepted(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        gbff_name=(
            "GCA_000000001.1_efetch_components.gbff"
        ),
    )

    observed = evaluate_fixture(
        fixture
    )

    assert observed.decision.status == (
        source_chromosome_integrity.PASS
    )


def test_nontriggered_candidate_does_not_consult_poisoned_historical(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    calls = []

    def poisoned_provider(
        accession,
    ):
        calls.append(
            accession
        )

        raise AssertionError(
            "historical provider must not be called"
        )

    observed = evaluate_stage3_candidate(
        candidate=fixture[
            "candidate"
        ],
        component_rows=fixture[
            "component_rows"
        ],
        package_manifest=fixture[
            "package_manifest"
        ],
        expected_source_evidence_sha256=(
            fixture[
                "expected_source_sha"
            ]
        ),
        historical_provider=poisoned_provider,
    )

    assert calls == []

    assert observed.decision.reason == (
        "NO_CHROMOSOME_INTEGRITY_TRIGGER"
    )


def test_triggered_candidate_calls_historical_provider_once(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    historical = HistoricalReuseEvidence(
        uses_historical_project_finch_package=True,
        cache_content_verification="pass",
        adjudication_accession="GCA_000000001.1",
        adjudication_outcome=(
            source_chromosome_integrity.HISTORICAL_RETAIN
        ),
    )

    calls = []

    def provider(
        accession,
    ):
        calls.append(
            accession
        )

        return historical

    observed = evaluate_fixture(
        fixture,
        historical_provider=provider,
    )

    assert calls == [
        "GCA_000000001.1",
    ]

    assert observed.trigger.triggered is True
    assert observed.decision.historical_adjudication_reused is True


def test_triggered_candidate_rejects_bad_provider_result(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    def provider(
        accession,
    ):
        return object()

    with pytest.raises(
        Stage3ExecutionError,
        match=(
            "historical evidence provider returned "
            "unexpected type"
        ),
    ):
        evaluate_fixture(
            fixture,
            historical_provider=provider,
        )


def test_noncallable_historical_provider_fails_closed(
    tmp_path,
):
    fixture = make_fixture(
        tmp_path
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="historical evidence provider must be callable",
    ):
        evaluate_stage3_candidate(
            candidate=fixture[
                "candidate"
            ],
            component_rows=fixture[
                "component_rows"
            ],
            package_manifest=fixture[
                "package_manifest"
            ],
            expected_source_evidence_sha256=(
                fixture[
                    "expected_source_sha"
                ]
            ),
            historical_provider=object(),
        )


def test_trigger_crosscheck_fails_closed(
    tmp_path,
    monkeypatch,
):
    fixture = make_fixture(
        tmp_path,
        components=trigger_components(),
    )

    def inconsistent_evaluate(
        *,
        accession,
        components,
        historical=None,
    ):
        return ChromosomeIntegrityDecision(
            status=source_chromosome_integrity.PASS,
            reason="synthetic poisoned decision",
            triggered=False,
            historical_adjudication_reused=False,
        )

    monkeypatch.setattr(
        source_chromosome_integrity,
        "evaluate",
        inconsistent_evaluate,
    )

    with pytest.raises(
        Stage3ExecutionError,
        match="decision trigger disagrees",
    ):
        evaluate_fixture(
            fixture
        )


def test_primary_component_order_does_not_change_result(
    tmp_path,
):
    first = make_fixture(
        tmp_path / "first",
        components=trigger_components(),
    )

    reversed_components = tuple(
        reversed(
            trigger_components()
        )
    )

    second = make_fixture(
        tmp_path / "second",
        components=reversed_components,
    )

    first_result = evaluate_fixture(
        first
    )

    second_result = evaluate_fixture(
        second
    )

    assert first_result.trigger == (
        second_result.trigger
    )

    assert first_result.decision == (
        second_result.decision
    )
