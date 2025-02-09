from __future__ import annotations

import datetime as dt

import pytest

from dipcount.errors import UsageError
from dipcount.model import Site, Zone
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)


def a_site(**changes: object) -> Site:
    fields: dict[str, object] = {
        "id": "SI-0001",
        "zone": "ZN-001",
        "name": "Weller Road basins",
        "habitat": "catch_basin",
        "extent": quantity("14 each"),
        "listed_on": LISTED,
    }
    fields.update(changes)
    return Site(**fields)  # type: ignore[arg-type]


def test_a_site_holds_what_it_was_given() -> None:
    site = a_site()
    assert site.zone == "ZN-001"
    assert site.kind.key == "catch_basin"


def test_the_id_has_to_be_a_site_id() -> None:
    with pytest.raises(UsageError):
        a_site(id="TR-0001")
    with pytest.raises(UsageError):
        a_site(zone="SI-0001")


def test_a_site_needs_a_name() -> None:
    with pytest.raises(UsageError):
        a_site(name="   ")


def test_the_extent_unit_has_to_match_the_habitat() -> None:
    with pytest.raises(UsageError, match="measured in each"):
        a_site(extent=quantity("6 acre"))
    with pytest.raises(UsageError, match="measured in acre"):
        a_site(habitat="cattail_marsh", extent=quantity("14 each"))


def test_a_marsh_in_acres_is_fine() -> None:
    site = a_site(habitat="cattail_marsh", extent=quantity("6.5 acre"))
    assert site.extent.unit == "acre"


def test_a_site_with_no_extent_is_not_a_site() -> None:
    with pytest.raises(UsageError):
        a_site(extent=quantity("0 each"))


def test_an_unknown_habitat_is_refused() -> None:
    with pytest.raises(Exception, match="habitat"):
        a_site(habitat="swimming pool")


def test_retiring_before_listing_is_refused() -> None:
    with pytest.raises(UsageError):
        a_site(retired_on=LISTED - dt.timedelta(days=1))


def test_coordinates_are_checked() -> None:
    with pytest.raises(UsageError):
        a_site(latitude=91.0)
    with pytest.raises(UsageError):
        a_site(longitude=-181.0)
    assert a_site(latitude=41.87, longitude=-93.09).latitude == 41.87


def test_a_site_is_open_between_its_two_dates() -> None:
    site = a_site(retired_on=dt.date(2025, 9, 1))
    assert not site.is_open(dt.date(2025, 2, 28))
    assert site.is_open(LISTED)
    assert site.is_open(dt.date(2025, 9, 1))
    assert not site.is_open(dt.date(2025, 9, 2))


def test_a_site_never_retired_stays_open() -> None:
    assert a_site().is_open(dt.date(2030, 1, 1))


def test_the_next_inspection_comes_off_the_habitat() -> None:
    basin = a_site()
    assert basin.due_after(dt.date(2025, 6, 2)) == dt.date(2025, 6, 23)
    flood = a_site(habitat="floodplain", extent=quantity("40 acre"))
    assert flood.due_after(dt.date(2025, 6, 2)) == dt.date(2025, 6, 6)


def test_a_zone_needs_a_name() -> None:
    with pytest.raises(UsageError):
        Zone("ZN-001", "  ")
    assert Zone("ZN-001", "north").name == "north"
