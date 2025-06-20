from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def shelved(started: Run) -> Run:
    started("product", "stock", "--on", "2025-01-15")
    return started


def test_stocking_reports_what_went_on(started: Run) -> None:
    result = started("product", "stock", "--on", "2025-01-15")
    assert "products added" in result.output
    assert "PD-0001" in result.output


def test_stocking_twice_says_so(shelved: Run) -> None:
    result = shelved("product", "stock")
    assert "already stocked" in result.output


def test_the_shelf_is_listed(shelved: Run) -> None:
    result = shelved("product", "list")
    assert "Bactilore G" in result.output
    assert "Kestrel ULV" in result.output


def test_the_shelf_narrows_by_purpose(shelved: Run) -> None:
    result = shelved("product", "list", "--purpose", "adulticide")
    assert "2 rows" in result.output
    assert "Kestrel ULV" in result.output


def test_a_product_shows_its_label(shelved: Run) -> None:
    result = shelved("product", "show", "Bactilore G")
    assert "cattail_marsh" in result.output
    assert "80 lb" in result.output


def test_a_product_is_found_by_registration(shelved: Run) -> None:
    result = shelved("product", "show", "73049-20")
    assert "Bactilore G" in result.output


def test_the_products_for_a_habitat_are_listed(shelved: Run) -> None:
    result = shelved("product", "for", "catch_basin")
    assert "storm drain catch basin" in result.output
    assert "Hesper 30 briquets" in result.output
    assert "Bactilore WSP" in result.output


def test_a_habitat_with_nothing_labelled_for_it(shelved: Run) -> None:
    result = shelved("product", "for", "cattail_marsh", "--purpose", "pupicide")
    assert "0 rows" in result.output


def test_a_product_is_added_by_hand(shelved: Run) -> None:
    result = shelved(
        "product",
        "add",
        "Ridgeline G",
        "99999-4",
        "--maker",
        "Ridgeline",
        "--active",
        "Bacillus sphaericus",
        "--percent",
        "7.5",
        "--form",
        "granule",
        "--purpose",
        "larvicide",
        "--on",
        "2025-03-01",
    )
    assert "Ridgeline G" in result.output


def test_a_duplicate_registration_is_refused(shelved: Run) -> None:
    result = shelved(
        "product",
        "add",
        "Something else",
        "73049-20",
        "--maker",
        "Ridgeline",
        "--active",
        "Bti",
        "--percent",
        "7.5",
        "--form",
        "granule",
        "--purpose",
        "larvicide",
        expect=1,
    )
    assert result.exit_code != 0


def test_a_label_is_written_by_hand(shelved: Run) -> None:
    shelved(
        "product",
        "add",
        "Ridgeline G",
        "99999-4",
        "--maker",
        "Ridgeline",
        "--active",
        "Bacillus sphaericus",
        "--percent",
        "7.5",
        "--form",
        "granule",
        "--purpose",
        "larvicide",
        "--on",
        "2025-03-01",
    )
    result = shelved(
        "product",
        "label",
        "Ridgeline G",
        "cattail_marsh",
        "--low",
        "3 lb",
        "--high",
        "12 lb",
        "--season-max",
        "40 lb",
        "--interval",
        "7",
    )
    assert "3 lb to 12 lb per acre" in result.output


def test_a_label_a_habitat_could_never_take_is_refused(shelved: Run) -> None:
    result = shelved(
        "product",
        "label",
        "Bactilore G",
        "container",
        "--low",
        "1 lb",
        "--high",
        "2 lb",
        expect=1,
    )
    assert result.exit_code != 0


def test_a_product_is_withdrawn(shelved: Run) -> None:
    result = shelved("product", "withdraw", "Bactilore G", "--on", "2025-09-01")
    assert "2025-09-01" in result.output
    later = shelved("product", "list", "--on", "2025-09-02")
    assert "Bactilore G" not in later.output
