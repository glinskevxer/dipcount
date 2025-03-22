from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount.errors import UsageError
from dipcount.model.weather import (
    AVERAGE,
    MODIFIED,
    SINE,
    Observation,
    Station,
    degree_days,
)

DAY = dt.date(2025, 6, 4)


def an_observation(**changes: object) -> Observation:
    fields: dict[str, object] = {
        "id": "WX-250604-01",
        "station": "ST-0001",
        "on": DAY,
        "high_f": 84.0,
        "low_f": 62.0,
    }
    fields.update(changes)
    return Observation(**fields)  # type: ignore[arg-type]


def test_a_warm_day_gives_the_same_answer_three_ways_when_the_low_is_over_the_base() -> None:
    plain = degree_days(84, 62, 50, AVERAGE)
    modified = degree_days(84, 62, 50, MODIFIED)
    sine = degree_days(84, 62, 50, SINE)
    assert plain == modified == sine == Decimal("23")


def test_a_cold_night_is_where_the_methods_part() -> None:
    plain = degree_days(70, 38, 50, AVERAGE)
    modified = degree_days(70, 38, 50, MODIFIED)
    sine = degree_days(70, 38, 50, SINE)
    assert plain == Decimal("4")
    assert modified == Decimal("10")
    assert plain < sine < modified


def test_a_day_that_never_reaches_the_base_gives_nothing() -> None:
    for method in (AVERAGE, MODIFIED, SINE):
        assert degree_days(46, 30, 50, method) == 0


def test_the_plain_method_never_goes_below_zero() -> None:
    assert degree_days(52, 20, 50, AVERAGE) == 0


def test_a_flat_day_at_the_base_gives_nothing() -> None:
    assert degree_days(50, 50, 50, SINE) == 0


def test_a_flat_warm_day_gives_the_difference() -> None:
    assert degree_days(60, 60, 50, SINE) == Decimal("10")


def test_an_unknown_method_is_refused() -> None:
    with pytest.raises(UsageError):
        degree_days(84, 62, 50, "guesswork")


def test_a_low_above_the_high_is_refused() -> None:
    with pytest.raises(UsageError):
        degree_days(60, 70, 50)
    with pytest.raises(UsageError):
        an_observation(high_f=60.0, low_f=70.0)


def test_a_higher_base_gives_fewer_units() -> None:
    assert degree_days(84, 62, 60, MODIFIED) < degree_days(84, 62, 50, MODIFIED)


def test_an_observation_carries_its_own_day_in_its_id() -> None:
    with pytest.raises(UsageError, match="does not carry"):
        an_observation(on=dt.date(2025, 6, 5))


def test_measurable_rain_starts_at_a_hundredth() -> None:
    assert not an_observation(rain_in=0.0).wet
    assert not an_observation(rain_in=0.009).wet
    assert an_observation(rain_in=0.01).wet


def test_negative_rain_or_wind_is_refused() -> None:
    with pytest.raises(UsageError):
        an_observation(rain_in=-0.1)
    with pytest.raises(UsageError):
        an_observation(wind_mph=-3.0)


def test_the_mean_is_the_middle_of_the_two() -> None:
    assert an_observation().mean_f == 73.0


def test_an_observation_works_out_its_own_units() -> None:
    assert an_observation().degree_days() == Decimal("23")


def test_a_station_needs_a_name_and_cannot_close_before_it_opened() -> None:
    with pytest.raises(UsageError):
        Station("ST-0001", " ", "ZN-001", DAY)
    with pytest.raises(UsageError):
        Station("ST-0001", "Airport", "ZN-001", DAY, closed_on=DAY - dt.timedelta(days=1))


def test_a_station_is_open_between_its_dates() -> None:
    station = Station("ST-0001", "Airport", "ZN-001", DAY, closed_on=DAY + dt.timedelta(days=30))
    assert not station.is_open(DAY - dt.timedelta(days=1))
    assert station.is_open(DAY)
    assert not station.is_open(DAY + dt.timedelta(days=31))


def test_a_station_never_closed_stays_open() -> None:
    assert Station("ST-0001", "Airport", "ZN-001", DAY).is_open(dt.date(2030, 1, 1))
