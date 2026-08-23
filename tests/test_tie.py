import hashlib

import pytest

from bacselect.tie import tie_key


def test_tie_key_matches_frozen_definition() -> None:
    accession = "GCA_000005825.2"

    expected = hashlib.sha256(
        b"BacSelect-selector-v1|GCA_000005825.2"
    ).hexdigest()

    assert tie_key(accession) == expected


def test_tie_key_is_deterministic() -> None:
    accession = "GCA_000005845.2"

    assert tie_key(accession) == tie_key(accession)


def test_tie_key_distinguishes_accessions() -> None:
    assert tie_key("GCA_000005825.2") != tie_key("GCA_000005845.2")


def test_tie_key_rejects_empty_accession() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        tie_key("")
