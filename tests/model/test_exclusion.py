from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock
from dipcount.errors import UsageError
from dipcount.model.exclusion import (
    APIARY,
    AQUACULTURE,
    ORGANIC,
    SENSITIVE,
    WATER,
    Exclusion,
    kinds,
    sort_of,
)

LISTED = dt.date(2025, 3, 1)


def an_entry(**changes: object) -> Exclusion:
    fields: dict[str, object] = {
        "id": "EX-0001",
        "kind": APIARY,
        "name": "Ferrand apiary, Kettle Road",
        "zone": "ZN-001",
        "listed_on": LISTED,
        "contact": "M. Ferrand",
    }
    fields.update(changes)
    return Exclusion(**fields)  # type: ignore[arg-type]


def test_every_kind_says_why_it_is_on_the_register() -> None:
    for key in kinds():
        assert sort_of(key).why


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(UsageError):
        sort_of("difficult neighbour")
    with pytest.raises(UsageError):
        an_entry(kind="difficult neighbour")


def test_notice_kinds_and_absolute_kinds_are_different_things() -> None:
    assert not sort_of(APIARY).absolute
    assert not sort_of(ORGANIC).absolute
    assert not sort_of(SENSITIVE).absolute
    assert sort_of(AQUACULTURE).absolute
    assert sort_of(WATER).absolute


def test_an_entry_takes_its_kind_defaults() -> None:
    entry = an_entry()
    assert entry.hours == 48
    assert entry.buffer == 1000
    assert not entry.absolute


def test_an_entry_can_ask_for_more_than_its_kind() -> None:
    entry = an_entry(notice_hours=72, buffer_ft=1500)
    assert entry.hours == 72
    assert entry.buffer == 1500


def test_an_entry_needs_a_name_and_a_real_zone() -> None:
    with pytest.raises(UsageError):
        an_entry(name=" ")
    with pytest.raises(UsageError):
        an_entry(zone="SI-0001")


def test_a_negative_buffer_or_notice_is_refused() -> None:
    with pytest.raises(UsageError):
        an_entry(buffer_ft=-1)
    with pytest.raises(UsageError):
        an_entry(notice_hours=-1)


def test_an_aquaculture_entry_needs_somebody_to_talk_to() -> None:
    with pytest.raises(UsageError, match="somebody to talk to"):
        an_entry(kind=AQUACULTURE, contact="")
    assert an_entry(kind=AQUACULTURE, contact="J. Prewitt").absolute


def test_an_entry_cannot_come_off_before_it_went_on() -> None:
    with pytest.raises(UsageError):
        an_entry(removed_on=LISTED - dt.timedelta(days=1))


def test_an_entry_is_on_the_register_between_its_dates() -> None:
    entry = an_entry(removed_on=dt.date(2025, 9, 1))
    assert not entry.on_register(dt.date(2025, 2, 1))
    assert entry.on_register(dt.date(2025, 6, 1))
    assert not entry.on_register(dt.date(2025, 9, 2))


def test_the_notice_deadline_counts_back_from_the_run() -> None:
    entry = an_entry()
    spray = clock.moment("2025-07-10 21:30")
    assert clock.stamp(entry.notice_by(spray)) == "2025-07-08 21:30"


def test_an_organic_farm_wants_less_warning_than_an_apiary() -> None:
    farm = an_entry(kind=ORGANIC, name="Halloran organics")
    assert farm.hours < an_entry().hours


def test_the_line_says_which_sort_of_entry_it_is() -> None:
    assert "48 hours notice" in an_entry().line()
    water = an_entry(kind=WATER, name="Kettle river")
    assert "never sprayed over" in water.line()
