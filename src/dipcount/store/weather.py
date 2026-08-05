"""Reading and writing weather stations and their observations."""

from __future__ import annotations

import datetime as dt

from dipcount import ids
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.weather import Observation, Station
from dipcount.store import numbering, zones
from dipcount.store.book import Book

_STATION = "id, name, zone, elevation, opened_on, closed_on, note"
_OBSERVATION = "id, station, on_day, high_f, low_f, rain_in, wind_mph, note"


def add_station(
    book: Book,
    name: str,
    zone_id: str,
    opened_on: dt.date,
    *,
    elevation: int = 0,
    note: str = "",
) -> Station:
    """Put a weather station on the books."""
    zone = zones.resolve(book, zone_id)
    if find_station(book, name) is not None:
        raise Duplicate("station", name)
    station = Station(
        id=numbering.next_serial(book, "station", "station"),
        name=name,
        zone=zone.id,
        opened_on=opened_on,
        elevation=elevation,
        note=note,
    )
    book.run(
        f"INSERT INTO station ({_STATION})"
        " VALUES (:id, :name, :zone, :elevation, :opened_on, :closed_on, :note)",
        station.to_row(),
    )
    return station


def get_station(book: Book, station_id: str) -> Station:
    """One station by id."""
    row = book.one(f"SELECT {_STATION} FROM station WHERE id = ?", (station_id,))
    if row is None:
        raise NotFound("station", station_id)
    return Station.from_row(row)


def find_station(book: Book, name: str) -> Station | None:
    """One station by name, or nothing."""
    row = book.one(f"SELECT {_STATION} FROM station WHERE name = ?", (name,))
    return None if row is None else Station.from_row(row)


def resolve_station(book: Book, text: str) -> Station:
    """A station by id or by name."""
    if ids.looks_like("station", text):
        return get_station(book, text)
    found = find_station(book, text)
    if found is None:
        raise NotFound("station", text)
    return found


def all_stations(book: Book, *, zone_id: str | None = None) -> list[Station]:
    """Every station, optionally in one zone."""
    where = " WHERE zone = ?" if zone_id else ""
    params = (zone_id,) if zone_id else ()
    rows = book.all(f"SELECT {_STATION} FROM station{where} ORDER BY id", params)
    return [Station.from_row(row) for row in rows]


def close_station(book: Book, station_id: str, on: dt.date) -> Station:
    """Stop reading a station from a day."""
    station = get_station(book, station_id)
    if station.closed_on is not None:
        raise RuleViolation("weather.station", f"{station_id} closed on {station.closed_on}")
    if on < station.opened_on:
        raise RuleViolation("weather.station", "a station cannot close before it opened")
    book.run("UPDATE station SET closed_on = ? WHERE id = ?", (on.isoformat(), station_id))
    return get_station(book, station_id)


def record(
    book: Book,
    station_id: str,
    on: dt.date,
    high_f: float,
    low_f: float,
    *,
    rain_in: float = 0.0,
    wind_mph: float = 0.0,
    note: str = "",
) -> Observation:
    """Write one day's reading from one station."""
    station = resolve_station(book, station_id)
    if not station.is_open(on):
        raise RuleViolation(
            "weather.station",
            f"{station.name} was not reading on {on.isoformat()}",
        )
    if reading(book, station.id, on) is not None:
        raise Duplicate("observation", f"{station.id} on {on.isoformat()}")
    made = Observation(
        id=numbering.next_dated(book, "observation", "observation", on),
        station=station.id,
        on=on,
        high_f=high_f,
        low_f=low_f,
        rain_in=rain_in,
        wind_mph=wind_mph,
        note=note,
    )
    book.run(
        f"INSERT INTO observation ({_OBSERVATION})"
        " VALUES (:id, :station, :on_day, :high_f, :low_f, :rain_in, :wind_mph, :note)",
        made.to_row(),
    )
    return made


def get(book: Book, observation_id: str) -> Observation:
    """One observation by id."""
    row = book.one(f"SELECT {_OBSERVATION} FROM observation WHERE id = ?", (observation_id,))
    if row is None:
        raise NotFound("observation", observation_id)
    return Observation.from_row(row)


def reading(book: Book, station_id: str, on: dt.date) -> Observation | None:
    """What one station recorded on one day, or nothing."""
    row = book.one(
        f"SELECT {_OBSERVATION} FROM observation WHERE station = ? AND on_day = ?",
        (station_id, on.isoformat()),
    )
    return None if row is None else Observation.from_row(row)


def series(
    book: Book,
    station_id: str,
    start: dt.date,
    end: dt.date,
) -> list[Observation]:
    """Every reading from one station over a run of days."""
    rows = book.all(
        f"SELECT {_OBSERVATION} FROM observation"
        " WHERE station = ? AND on_day >= ? AND on_day <= ? ORDER BY on_day",
        (station_id, start.isoformat(), end.isoformat()),
    )
    return [Observation.from_row(row) for row in rows]


def on_day(book: Book, on: dt.date) -> list[Observation]:
    """Every station's reading for one day."""
    rows = book.all(
        f"SELECT {_OBSERVATION} FROM observation WHERE on_day = ? ORDER BY station",
        (on.isoformat(),),
    )
    return [Observation.from_row(row) for row in rows]


def missing_days(book: Book, station_id: str, start: dt.date, end: dt.date) -> list[dt.date]:
    """The days in a window this station filed nothing for.

    A gap in the record is not the same as a day with no heat in it, and an
    accumulation that treats it as one runs low for the rest of the season.
    """
    station = get_station(book, station_id)
    have = {one.on for one in series(book, station_id, start, end)}
    out: list[dt.date] = []
    at = start
    while at <= end:
        if station.is_open(at) and at not in have:
            out.append(at)
        at += dt.timedelta(days=1)
    return out
