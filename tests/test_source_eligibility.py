import pytest

from bacselect.source_eligibility import (
    AUTOMATIC_WARNING_EXCLUSIONS,
    DISCOVERY_ARGS,
    EXCLUDE,
    RETAIN,
    WITHHOLD,
    assess_records,
    assess_summary_record,
    blinded_metadata_summary,
    normalize_warning,
    validate_datasets_version_text,
    validate_discovery_args,
)


def valid_record():
    return {
        "accession": "GCA_000000001.1",
        "current_accession": "GCA_000000001.1",
        "source_database": "SOURCE_DATABASE_GENBANK",
        "assembly_info": {
            "assembly_status": "current",
            "assembly_level": "Complete Genome",
            "biosample": {
                "accession": "SAMN12345678",
            },
        },
        "organism": {
            "organism_name": "not used by eligibility",
            "tax_id": 123,
        },
    }


def test_discovery_args_match_frozen_query():
    assert DISCOVERY_ARGS == (
        "summary",
        "genome",
        "taxon",
        "2",
        "--assembly-source",
        "GenBank",
        "--assembly-level",
        "complete",
        "--assembly-version",
        "current",
        "--mag",
        "exclude",
        "--exclude-multi-isolate",
        "--limit",
        "all",
        "--as-json-lines",
    )


def test_validate_discovery_args_accepts_exact_query():
    validate_discovery_args(DISCOVERY_ARGS)


def test_validate_discovery_args_rejects_change():
    changed = list(DISCOVERY_ARGS)
    changed[6] = "RefSeq"

    with pytest.raises(ValueError, match="differ"):
        validate_discovery_args(changed)


def test_frozen_datasets_version_accepts_18_35_0():
    validate_datasets_version_text(
        "datasets version: 18.35.0\n"
        "New version of client available\n"
    )


def test_frozen_datasets_version_rejects_upgrade():
    with pytest.raises(ValueError, match="18.35.0"):
        validate_datasets_version_text("datasets version: 18.36.0\n")


def test_warning_normalization_is_exactly_frozen():
    assert normalize_warning(" \tMiXeD CULTURE\r\n") == "mixed culture"


def test_warning_normalization_does_not_rewrite_internal_space():
    assert normalize_warning("mixed  culture") == "mixed  culture"


def test_warning_normalization_rejects_non_string():
    with pytest.raises(ValueError, match="must be a string"):
        normalize_warning(7)


def test_automatic_warning_set_is_exact():
    assert AUTOMATIC_WARNING_EXCLUSIONS == {
        "chimeric",
        "contaminated",
        "mixed culture",
    }


def test_valid_record_is_retained_at_metadata_stage():
    result = assess_summary_record(valid_record())

    assert result.decision == RETAIN
    assert result.reasons == ()
    assert result.biosample == "SAMN12345678"


@pytest.mark.parametrize(
    "accession",
    [
        "GCF_000000001.1",
        "GCA_000000001",
        "",
        None,
    ],
)
def test_invalid_canonical_accession_is_excluded(accession):
    record = valid_record()
    record["accession"] = accession
    record["current_accession"] = accession

    result = assess_summary_record(record)

    assert result.decision == EXCLUDE
    assert "invalid_canonical_GCA_accession" in result.reasons


def test_current_accession_mismatch_is_excluded():
    record = valid_record()
    record["current_accession"] = "GCA_000000002.1"

    result = assess_summary_record(record)

    assert result.decision == EXCLUDE
    assert "current_accession_mismatch" in result.reasons


def test_non_genbank_source_is_excluded():
    record = valid_record()
    record["source_database"] = "SOURCE_DATABASE_REFSEQ"

    result = assess_summary_record(record)

    assert result.decision == EXCLUDE
    assert "source_database_not_GenBank" in result.reasons


@pytest.mark.parametrize(
    "status",
    [
        "previous",
        "suppressed",
        "retired",
        None,
        "unknown",
    ],
)
def test_noncurrent_assembly_status_is_excluded(status):
    record = valid_record()
    record["assembly_info"]["assembly_status"] = status

    result = assess_summary_record(record)

    assert result.decision == EXCLUDE
    assert "assembly_status_not_current" in result.reasons


def test_noncomplete_assembly_level_is_excluded():
    record = valid_record()
    record["assembly_info"]["assembly_level"] = "Chromosome"

    result = assess_summary_record(record)

    assert result.decision == EXCLUDE
    assert "assembly_level_not_Complete_Genome" in result.reasons


def test_missing_assembly_info_is_withheld():
    record = valid_record()
    record.pop("assembly_info")

    result = assess_summary_record(record)

    assert result.decision == WITHHOLD
    assert result.reasons == ("assembly_info_missing_or_malformed",)


def test_missing_biosample_object_is_excluded():
    record = valid_record()
    record["assembly_info"].pop("biosample")

    result = assess_summary_record(record)

    assert result.decision == EXCLUDE
    assert "biosample_object_missing_or_malformed" in result.reasons


@pytest.mark.parametrize(
    "biosample",
    [
        "",
        "NOT_A_BIOSAMPLE",
        "SAMNABC",
        None,
    ],
)
def test_malformed_biosample_accession_is_excluded(biosample):
    record = valid_record()
    record["assembly_info"]["biosample"]["accession"] = biosample

    result = assess_summary_record(record)

    assert result.decision == EXCLUDE
    assert "biosample_accession_missing_or_malformed" in result.reasons


@pytest.mark.parametrize(
    "biosample",
    [
        "SAMN123",
        "SAMEA456",
        "SAMD789",
    ],
)
def test_supported_biosample_namespaces_are_retained(biosample):
    record = valid_record()
    record["assembly_info"]["biosample"]["accession"] = biosample

    result = assess_summary_record(record)

    assert result.decision == RETAIN
    assert result.biosample == biosample


@pytest.mark.parametrize(
    "warning",
    [
        "chimeric",
        "Chimeric",
        " contaminated ",
        "MIXED CULTURE",
    ],
)
def test_frozen_automatic_warnings_are_excluded(warning):
    record = valid_record()
    record["assembly_info"]["atypical"] = {
        "is_atypical": True,
        "warnings": [warning],
    }

    result = assess_summary_record(record)

    assert result.decision == EXCLUDE
    assert any(
        reason.startswith("automatic_atypical_exclusion:")
        for reason in result.reasons
    )


@pytest.mark.parametrize(
    "warning",
    [
        "genome length too large",
        "genome length too small",
        "low quality sequence",
        "misassembled",
        "unverified source organism",
        "future unknown warning",
    ],
)
def test_nonlisted_atypical_warning_is_not_auto_excluded(warning):
    record = valid_record()
    record["assembly_info"]["atypical"] = {
        "is_atypical": True,
        "warnings": [warning],
    }

    result = assess_summary_record(record)

    assert result.decision == RETAIN


def test_atypical_flag_without_warning_is_not_auto_excluded():
    record = valid_record()
    record["assembly_info"]["atypical"] = {
        "is_atypical": True,
        "warnings": [],
    }

    assert assess_summary_record(record).decision == RETAIN


def test_nonstring_warning_fails_closed():
    record = valid_record()
    record["assembly_info"]["atypical"] = {
        "is_atypical": True,
        "warnings": [7],
    }

    result = assess_summary_record(record)

    assert result.decision == WITHHOLD
    assert "atypical_warning_non_string" in result.reasons


def test_warning_container_must_be_list():
    record = valid_record()
    record["assembly_info"]["atypical"] = {
        "is_atypical": True,
        "warnings": "contaminated",
    }

    result = assess_summary_record(record)

    assert result.decision == WITHHOLD
    assert "atypical_warnings_not_list" in result.reasons


def test_duplicate_accession_collection_fails_closed():
    records = [valid_record(), valid_record()]

    with pytest.raises(ValueError, match="duplicate canonical accession"):
        assess_records(records)


def test_blinded_summary_contains_no_record_identity():
    first = assess_summary_record(valid_record())

    second_record = valid_record()
    second_record["accession"] = "GCA_000000002.1"
    second_record["current_accession"] = "GCA_000000002.1"
    second_record["assembly_info"]["biosample"]["accession"] = "SAMN2"
    second_record["assembly_info"]["atypical"] = {
        "is_atypical": True,
        "warnings": ["contaminated"],
    }
    second = assess_summary_record(second_record)

    summary = blinded_metadata_summary([first, second])
    text = repr(summary)

    assert summary["records"] == 2
    assert summary["decision_counts"][RETAIN] == 1
    assert summary["decision_counts"][EXCLUDE] == 1
    assert "GCA_" not in text
    assert "SAMN" not in text
    assert "organism" not in text.lower()
