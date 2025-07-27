from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def shed(started: Run) -> Run:
    started("product", "stock", "--on", "2025-01-15")
    started(
        "lot",
        "receive",
        "Bactilore G",
        "24G-1187",
        "400 lb",
        "--on",
        "2025-03-03",
        "--expires",
        "2026-03-31",
        "--held-at",
        "shop, north rack",
    )
    return started


def test_a_delivery_is_booked_in(shed: Run) -> None:
    result = shed("lot", "list")
    assert "LT-0001" in result.output
    assert "400 lb" in result.output


def test_the_same_code_twice_is_refused(shed: Run) -> None:
    result = shed(
        "lot",
        "receive",
        "Bactilore G",
        "24G-1187",
        "40 lb",
        "--on",
        "2025-03-03",
        expect=1,
    )
    assert result.exit_code != 0


def test_a_lot_shows_what_is_left(shed: Run) -> None:
    result = shed("lot", "show", "LT-0001")
    assert "400 lb" in result.output
    assert "shop, north rack" in result.output


def test_a_draw_comes_off_the_shelf(shed: Run) -> None:
    result = shed("lot", "draw", "LT-0001", "40 lb", "--at", "2025-06-04 09:00")
    assert "360 lb left" in result.output


def test_a_draw_bigger_than_the_shelf_is_refused(shed: Run) -> None:
    result = shed("lot", "draw", "LT-0001", "401 lb", expect=1)
    assert result.exit_code != 0


def test_the_draws_show_under_the_lot(shed: Run) -> None:
    shed("lot", "draw", "LT-0001", "40 lb", "--at", "2025-06-04 09:00", "--for", "TX-250604-01")
    result = shed("lot", "show", "LT-0001")
    assert "TX-250604-01" in result.output
    assert "disposed" in result.output


def test_the_lots_narrow_by_product(shed: Run) -> None:
    shed("lot", "receive", "Sphaerix WG", "24S-0042", "200 lb", "--on", "2025-03-03")
    assert "2 rows" in shed("lot", "list").output
    assert "1 row" in shed("lot", "list", "--product", "Sphaerix WG").output


def test_what_goes_out_of_date_soon_is_listed(shed: Run) -> None:
    result = shed("lot", "expiring", "--on", "2026-03-01", "--days", "60")
    assert "LT-0001" in result.output
    assert "1 row" in result.output


def test_nothing_goes_out_of_date_this_month(shed: Run) -> None:
    result = shed("lot", "expiring", "--on", "2025-06-01", "--days", "30")
    assert "0 rows" in result.output


def test_a_recall_names_every_draw(shed: Run) -> None:
    shed("lot", "draw", "LT-0001", "40 lb", "--at", "2025-06-04 09:00", "--for", "TX-250604-01")
    shed("lot", "draw", "LT-0001", "20 lb", "--at", "2025-06-05 09:00", "--for", "TX-250605-01")
    result = shed("lot", "recall", "Bactilore G", "24G-1187")
    assert "2 rows" in result.output
    assert "TX-250605-01" in result.output


def test_a_recall_on_a_code_that_is_not_there(shed: Run) -> None:
    result = shed("lot", "recall", "Bactilore G", "nothing", expect=1)
    assert result.exit_code != 0
