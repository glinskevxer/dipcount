from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def ready(started: Run) -> Run:
    started("product", "stock", "--on", "2025-01-15")
    started(
        "site",
        "add",
        "north",
        "Sawyer marsh",
        "--habitat",
        "cattail_marsh",
        "--extent",
        "6 acre",
        "--on",
        "2025-03-01",
    )
    started(
        "site",
        "add",
        "north",
        "Weller Road",
        "--habitat",
        "catch_basin",
        "--extent",
        "14 each",
        "--on",
        "2025-03-01",
    )
    started("lot", "receive", "Bactilore G", "24G-1187", "400 lb", "--on", "2025-03-03")
    started("lot", "receive", "Bactilore WSP", "24W-0801", "500 each", "--on", "2025-03-03")
    return started


def test_a_plan_says_what_would_go_on(ready: Run) -> None:
    result = ready("treat", "plan", "SI-0001", "Bactilore G", "--on", "2025-06-04")
    assert "6.25 lb/acre" in result.output
    assert "37.5 lb" in result.output
    assert "yes" in result.output


def test_a_plan_at_the_top_of_the_range(ready: Run) -> None:
    result = ready(
        "treat",
        "plan",
        "SI-0001",
        "Bactilore G",
        "--on",
        "2025-06-04",
        "--strength",
        "high",
    )
    assert "10 lb/acre" in result.output


def test_a_plan_that_cannot_go_ahead_names_the_clause(ready: Run) -> None:
    result = ready("treat", "plan", "SI-0002", "Bactilore G", "--on", "2025-06-04")
    assert "no" in result.output
    assert "label." in result.output


def test_a_rate_over_the_label_is_refused_in_the_plan(ready: Run) -> None:
    result = ready(
        "treat",
        "plan",
        "SI-0001",
        "Bactilore G",
        "--on",
        "2025-06-04",
        "--rate",
        "40 lb",
    )
    assert "label.rate" in result.output


def test_the_choices_for_a_site_are_ranked(ready: Run) -> None:
    result = ready("treat", "choices", "SI-0002", "--on", "2025-06-04")
    assert "Bactilore WSP" in result.output
    assert "yes" in result.output


def test_an_application_is_made_and_drawn_off_the_lot(ready: Run) -> None:
    result = ready("treat", "apply", "SI-0001", "LT-0001", "--at", "2025-06-04 10:40")
    assert "TX-250604-01" in result.output
    assert "37.5 lb over 6 acre" in result.output
    left = ready("lot", "show", "LT-0001")
    assert "362.5 lb" in left.output


def test_an_application_with_the_wrong_product_named_is_refused(ready: Run) -> None:
    result = ready(
        "treat",
        "apply",
        "SI-0001",
        "LT-0001",
        "--at",
        "2025-06-04 10:40",
        "--product",
        "Bactilore WSP",
        expect=1,
    )
    assert result.exit_code != 0


def test_an_application_of_a_product_not_labelled_for_the_site(ready: Run) -> None:
    result = ready(
        "treat",
        "apply",
        "SI-0002",
        "LT-0001",
        "--at",
        "2025-06-04 10:40",
        expect=1,
    )
    assert result.exit_code != 0


def test_the_label_interval_holds_the_second_one_back(ready: Run) -> None:
    ready("treat", "apply", "SI-0001", "LT-0001", "--at", "2025-06-04 10:40")
    result = ready(
        "treat",
        "apply",
        "SI-0001",
        "LT-0001",
        "--at",
        "2025-06-08 10:40",
        expect=1,
    )
    assert result.exit_code != 0


def test_the_treatments_over_a_window_are_listed(ready: Run) -> None:
    ready("treat", "apply", "SI-0001", "LT-0001", "--at", "2025-06-04 10:40")
    ready("treat", "apply", "SI-0002", "LT-0002", "--at", "2025-06-04 11:40")
    result = ready("treat", "list", "--from", "2025-06-01", "--to", "2025-06-30")
    assert "2 rows" in result.output
    result = ready(
        "treat",
        "list",
        "--from",
        "2025-06-01",
        "--to",
        "2025-06-30",
        "--site",
        "SI-0001",
    )
    assert "1 row" in result.output


def test_a_treatment_is_shown_in_full(ready: Run) -> None:
    ready("treat", "apply", "SI-0001", "LT-0001", "--at", "2025-06-04 10:40")
    result = ready("treat", "show", "TX-250604-01")
    assert "73049-20" in result.output
    assert "Bacillus thuringiensis" in result.output
    assert "1.6875 lb" in result.output


def test_the_season_adds_the_active_up(ready: Run) -> None:
    ready("treat", "apply", "SI-0001", "LT-0001", "--at", "2025-06-04 10:40")
    result = ready("treat", "season", "SI-0001", "2025")
    assert "Bacillus thuringiensis" in result.output
    assert "1.6875 lb" in result.output


def test_a_season_with_nothing_on_it(ready: Run) -> None:
    result = ready("treat", "season", "SI-0002", "2025")
    assert "0 rows" in result.output
