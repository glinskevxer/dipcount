from __future__ import annotations

import pytest

from dipcount.errors import UsageError
from dipcount.model.zone import Zone


def test_a_zone_holds_what_it_was_given() -> None:
    made = Zone("ZN-001", "north", "R. Vandeburg", "the river side")
    assert made.name == "north"
    assert made.supervisor == "R. Vandeburg"
    assert made.note == "the river side"


def test_a_zone_needs_a_name() -> None:
    with pytest.raises(UsageError):
        Zone("ZN-001", "   ")


def test_the_id_has_to_be_a_zone_id() -> None:
    with pytest.raises(UsageError):
        Zone("SI-0001", "north")
    with pytest.raises(UsageError):
        Zone("ZN-1", "north")


def test_a_zone_can_go_without_a_supervisor() -> None:
    made = Zone("ZN-002", "south")
    assert made.supervisor == ""
    assert made.note == ""


def test_the_row_is_what_the_book_stores() -> None:
    row = Zone("ZN-001", "north", "R. Vandeburg").to_row()
    assert row == {
        "id": "ZN-001",
        "name": "north",
        "supervisor": "R. Vandeburg",
        "note": "",
    }
