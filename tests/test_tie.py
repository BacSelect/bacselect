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


def test_species_tie_key_matches_frozen_definition() -> None:
    from bacselect.tie import species_tie_key

    accessions = [
        "GCA_000005845.2",
        "GCA_000005825.2",
    ]

    expected = hashlib.sha256(
        (
            "BacSelect-selector-v1|species|"
            "GCA_000005825.2\n"
            "GCA_000005845.2"
        ).encode("utf-8")
    ).hexdigest()

    assert species_tie_key(accessions) == expected


def test_species_tie_key_is_membership_order_invariant() -> None:
    from bacselect.tie import species_tie_key

    forward = [
        "GCA_000005825.2",
        "GCA_000005845.2",
        "GCA_000006765.1",
    ]

    reverse = list(reversed(forward))

    assert species_tie_key(forward) == species_tie_key(reverse)


def test_species_tie_key_rejects_empty_species() -> None:
    from bacselect.tie import species_tie_key

    with pytest.raises(ValueError, match="must not be empty"):
        species_tie_key([])
