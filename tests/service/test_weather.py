from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import rules, species
from dipcount.errors import RuleViolation
from dipcount.model.weather import AVERAGE, MODIFIED, SINE
from dipcount.service import weather as service
from dipcount.store import Book, sites, upgrade, weather, zones
from dipcount.units import quantity

OPENED = dt.date(2025, 1, 1)
LISTED = dt.date(2025, 3, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    weather.add_station(book, "Ambrose airport", "north", OPENED)
    sites.add(book, "north", "Kettle bottom", "floodplain", quantity("40 acre"), LISTED)
    sites.add(book, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    sites.add(book, "south", "Rowe bottom", "floodplain", quantity("22 acre"), LISTED)
    return book


def fill(book: Book, station: str, start: dt.date, days: int, high: float, low: float) -> None:
    for offset in range(days):
        weather.record(book, station, start + dt.timedelta(days=offset), high, low)


def test_a_full_window_adds_up(district: Book) -> None:
    fill(district, "ST-0001", dt.date(2025, 6, 1), 5, 84.0, 62.0)
    found = service.accumulate(district, "ST-0001", dt.date(2025, 6, 1), dt.date(2025, 6, 5))
    assert found.total == Decimal("115")
    assert found.complete
    assert found.counted == 5
    assert found.days == 5


def test_the_method_changes_the_total(district: Book) -> None:
    fill(district, "ST-0001", dt.date(2025, 6, 1), 5, 70.0, 38.0)
    window = (dt.date(2025, 6, 1), dt.date(2025, 6, 5))
    plain = service.accumulate(district, "ST-0001", *window, method=AVERAGE)
    modified = service.accumulate(district, "ST-0001", *window, method=MODIFIED)
    sine = service.accumulate(district, "ST-0001", *window, method=SINE)
    assert plain.total < sine.total < modified.total


def test_the_base_changes_the_total(district: Book) -> None:
    fill(district, "ST-0001", dt.date(2025, 6, 1), 5, 84.0, 62.0)
    window = (dt.date(2025, 6, 1), dt.date(2025, 6, 5))
    low = service.accumulate(district, "ST-0001", *window, base=50.0)
    high = service.accumulate(district, "ST-0001", *window, base=60.0)
    assert high.total < low.total


def test_a_gap_travels_with_the_figure(district: Book) -> None:
    weather.record(district, "ST-0001", dt.date(2025, 6, 1), 84.0, 62.0)
    weather.record(district, "ST-0001", dt.date(2025, 6, 3), 84.0, 62.0)
    found = service.accumulate(district, "ST-0001", dt.date(2025, 6, 1), dt.date(2025, 6, 3))
    assert not found.complete
    assert found.gaps == (dt.date(2025, 6, 2),)
    assert "1 missing" in found.line()


def test_a_strict_accumulation_refuses_a_gap(district: Book) -> None:
    weather.record(district, "ST-0001", dt.date(2025, 6, 1), 84.0, 62.0)
    with pytest.raises(RuleViolation, match="missing"):
        service.accumulate(
            district,
            "ST-0001",
            dt.date(2025, 6, 1),
            dt.date(2025, 6, 3),
            strict=True,
        )


def test_a_window_that_ends_before_it_starts(district: Book) -> None:
    with pytest.raises(RuleViolation):
        service.accumulate(district, "ST-0001", dt.date(2025, 6, 5), dt.date(2025, 6, 1))


def test_the_crossing_day_is_the_one_the_total_is_reached_on(district: Book) -> None:
    fill(district, "ST-0001", dt.date(2025, 6, 1), 10, 80.0, 60.0)
    # twenty units a day, so fifty units lands part way through the third day
    when = service.crossing(district, "ST-0001", dt.date(2025, 6, 1), Decimal(50))
    assert when == dt.date(2025, 6, 3)


def test_a_total_never_reached_gives_nothing(district: Book) -> None:
    fill(district, "ST-0001", dt.date(2025, 6, 1), 3, 52.0, 48.0)
    assert service.crossing(district, "ST-0001", dt.date(2025, 6, 1), Decimal(500)) is None


def test_a_floodwater_brood_flies_before_a_container_one(district: Book) -> None:
    fill(district, "ST-0001", dt.date(2025, 6, 1), 30, 80.0, 60.0)
    flood = service.emergence(district, "ST-0001", species.FLOODWATER, dt.date(2025, 6, 1))
    container = service.emergence(district, "ST-0001", species.CONTAINER, dt.date(2025, 6, 1))
    assert flood is not None
    assert container is not None
    assert flood < container


def test_the_forecast_covers_every_guild(district: Book) -> None:
    fill(district, "ST-0001", dt.date(2025, 6, 1), 30, 80.0, 60.0)
    forecast = service.guild_forecast(district, "ST-0001", dt.date(2025, 6, 1))
    assert set(forecast) == set(rules.guilds())
    assert all(day is not None for day in forecast.values())


def test_a_cold_spell_leaves_the_forecast_open(district: Book) -> None:
    fill(district, "ST-0001", dt.date(2025, 6, 1), 30, 48.0, 40.0)
    assert service.emergence(district, "ST-0001", species.FLOODWATER, dt.date(2025, 6, 1)) is None


def test_only_the_wet_enough_days_come_back(district: Book) -> None:
    weather.record(district, "ST-0001", dt.date(2025, 6, 1), 80.0, 60.0, rain_in=0.2)
    weather.record(district, "ST-0001", dt.date(2025, 6, 2), 80.0, 60.0, rain_in=0.6)
    found = service.wet_days(district, "ST-0001", dt.date(2025, 6, 1), dt.date(2025, 6, 3))
    assert [one.on.day for one in found] == [2]


def test_the_rainfall_over_a_window_adds_up(district: Book) -> None:
    weather.record(district, "ST-0001", dt.date(2025, 6, 1), 80.0, 60.0, rain_in=0.2)
    weather.record(district, "ST-0001", dt.date(2025, 6, 2), 80.0, 60.0, rain_in=0.6)
    total = service.rainfall(district, "ST-0001", dt.date(2025, 6, 1), dt.date(2025, 6, 3))
    assert total == Decimal("0.8")


def test_a_soaking_puts_the_floodwater_sites_of_that_zone_on_the_round(district: Book) -> None:
    weather.record(district, "ST-0001", dt.date(2025, 6, 2), 80.0, 60.0, rain_in=0.7)
    found = service.flooded(district, dt.date(2025, 6, 4))
    assert [site.id for site in found] == ["SI-0001"]


def test_a_light_shower_puts_nothing_on_the_round(district: Book) -> None:
    weather.record(district, "ST-0001", dt.date(2025, 6, 2), 80.0, 60.0, rain_in=0.2)
    assert service.flooded(district, dt.date(2025, 6, 4)) == []


def test_a_rain_a_fortnight_ago_is_not_this_week(district: Book) -> None:
    weather.record(district, "ST-0001", dt.date(2025, 5, 20), 80.0, 60.0, rain_in=0.9)
    assert service.flooded(district, dt.date(2025, 6, 4)) == []


def test_the_zone_with_no_station_stays_off_the_round(district: Book) -> None:
    weather.record(district, "ST-0001", dt.date(2025, 6, 2), 80.0, 60.0, rain_in=0.7)
    found = service.flooded(district, dt.date(2025, 6, 4))
    assert "SI-0003" not in [site.id for site in found]


def test_a_second_station_brings_its_own_zone_in(district: Book) -> None:
    weather.add_station(district, "Rowe levee", "south", OPENED)
    weather.record(district, "ST-0002", dt.date(2025, 6, 2), 80.0, 60.0, rain_in=0.7)
    found = service.flooded(district, dt.date(2025, 6, 4))
    assert [site.id for site in found] == ["SI-0003"]


def test_the_habitats_a_guild_comes_out_of_are_named() -> None:
    assert "floodplain" in service.habitats_at_risk(species.FLOODWATER)
    assert "catch_basin" not in service.habitats_at_risk(species.FLOODWATER)
