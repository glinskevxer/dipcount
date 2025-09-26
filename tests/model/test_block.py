from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock
from dipcount.errors import UsageError
from dipcount.model.block import CARD, PHONE, Block, Notice, Run
from dipcount.units import quantity, rate

LISTED = dt.date(2025, 4, 1)
GIVEN = clock.moment("2025-07-08 09:00")
FROM = clock.moment("2025-07-10 21:00")
TO = clock.moment("2025-07-11 01:00")


def a_block(**changes: object) -> Block:
    fields: dict[str, object] = {
        "id": "BK-0001",
        "zone": "ZN-001",
        "name": "Ardmore east grid",
        "acres": 640.0,
        "listed_on": LISTED,
    }
    fields.update(changes)
    return Block(**fields)  # type: ignore[arg-type]


def a_notice(**changes: object) -> Notice:
    fields: dict[str, object] = {
        "id": "NT-0001",
        "exclusion": "EX-0001",
        "block": "BK-0001",
        "given_at": GIVEN,
        "spray_from": FROM,
        "spray_to": TO,
        "how": PHONE,
        "given_by": "T. Okwuosa",
    }
    fields.update(changes)
    return Notice(**fields)  # type: ignore[arg-type]


def a_run(**changes: object) -> Run:
    fields: dict[str, object] = {
        "id": "RN-250710-01",
        "block": "BK-0001",
        "product": "PD-0009",
        "lot": "LT-0004",
        "applicator": "K. Brennaman",
        "started_at": clock.moment("2025-07-10 21:10"),
        "finished_at": clock.moment("2025-07-10 22:40"),
        "amount": quantity("1.4 fl oz"),
        "acres": 640.0,
    }
    fields.update(changes)
    return Run(**fields)  # type: ignore[arg-type]


def test_a_block_is_measured_in_acres_and_driven_in_miles() -> None:
    made = a_block(road_miles=18.4)
    assert made.extent == quantity("640 acre")
    assert made.road_miles == 18.4


def test_a_block_with_no_acres_is_not_a_block() -> None:
    with pytest.raises(UsageError):
        a_block(acres=0.0)
    with pytest.raises(UsageError):
        a_block(road_miles=-1.0)


def test_a_block_needs_a_name_and_a_zone() -> None:
    with pytest.raises(UsageError):
        a_block(name=" ")
    with pytest.raises(UsageError):
        a_block(zone="SI-0001")


def test_a_block_is_open_between_its_dates() -> None:
    made = a_block(retired_on=dt.date(2025, 9, 1))
    assert not made.is_open(dt.date(2025, 3, 1))
    assert made.is_open(dt.date(2025, 7, 10))
    assert not made.is_open(dt.date(2025, 9, 2))
    with pytest.raises(UsageError):
        a_block(retired_on=dt.date(2025, 3, 1))


def test_a_notice_says_how_much_warning_it_gave() -> None:
    assert a_notice().hours_given == Decimal("60")


def test_a_notice_given_after_the_window_opens_is_not_notice() -> None:
    with pytest.raises(UsageError, match="after the window"):
        a_notice(given_at=clock.moment("2025-07-10 22:00"))


def test_a_window_that_ends_before_it_starts() -> None:
    with pytest.raises(UsageError):
        a_notice(spray_to=FROM)


def test_a_notice_covers_a_run_inside_its_window() -> None:
    made = a_notice()
    assert made.covers(clock.moment("2025-07-10 21:10"))
    assert not made.covers(clock.moment("2025-07-11 21:10"))
    assert not made.covers(clock.moment("2025-07-10 20:00"))


def test_an_unknown_way_of_telling_is_refused() -> None:
    with pytest.raises(UsageError):
        a_notice(how="carrier pigeon")
    assert a_notice(how=CARD).how == CARD


def test_a_notice_needs_a_name_and_zones_on_its_moments() -> None:
    with pytest.raises(UsageError):
        a_notice(given_by=" ")
    with pytest.raises(UsageError):
        a_notice(given_at=GIVEN.replace(tzinfo=None))


def test_the_notice_line_carries_the_window() -> None:
    line = a_notice().line()
    assert "2025-07-10 21:00 to 2025-07-11 01:00" in line
    assert "phone" in line


def test_a_run_works_out_its_own_rate_and_length() -> None:
    made = a_run()
    assert made.minutes == Decimal("90.0")
    assert made.rate.per == "acre"
    assert made.on == dt.date(2025, 7, 10)


def test_a_run_over_a_smaller_part_of_the_block_has_a_higher_rate() -> None:
    whole = a_run()
    part = a_run(acres=320.0)
    assert part.rate.amount > whole.rate.amount


def test_a_run_that_finishes_before_it_starts() -> None:
    with pytest.raises(UsageError):
        a_run(finished_at=clock.moment("2025-07-10 21:00"))


def test_a_run_of_nothing_or_over_nothing() -> None:
    with pytest.raises(UsageError):
        a_run(acres=0.0)
    with pytest.raises(UsageError):
        a_run(amount=quantity("0 fl oz"))


def test_a_run_carries_the_weather_it_was_made_in() -> None:
    made = a_run(temperature=74.0, wind_mph=4.5, wind_from="SW")
    assert made.wind_mph == 4.5
    assert made.wind_from == "SW"
    assert a_run().wind_mph is None


def test_the_run_line_reads_like_a_use_report_row() -> None:
    line = a_run().line()
    assert "1.4 fl oz over 640 acre" in line
    assert "K. Brennaman" in line


def test_a_run_stores_utc_on_both_moments() -> None:
    row = a_run().to_row()
    assert str(row["started_at"]).endswith("+00:00")
    assert str(row["finished_at"]).endswith("+00:00")


def test_the_rate_is_what_the_label_would_be_checked_against() -> None:
    made = a_run(amount=quantity("4.8 fl oz"), acres=640.0)
    assert made.rate.amount.to("fl oz").rounded(4) == rate("0.0075 fl oz/acre").amount
