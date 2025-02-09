"""Reading and writing sites."""

from __future__ import annotations

import datetime as dt

from dipcount import habitat as hb
from dipcount import ids
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.site import Site
from dipcount.store import zones
from dipcount.store.book import Book
from dipcount.units import Quantity

_COLUMNS = (
    "id, zone, name, habitat, extent, listed_on, access, latitude, longitude, retired_on, note"
)
_VALUES = (
    ":id, :zone, :name, :habitat, :extent, :listed_on, :access,"
    " :latitude, :longitude, :retired_on, :note"
)


def numbers(book: Book) -> list[str]:
    """Every site id already issued."""
    return [str(row["id"]) for row in book.all("SELECT id FROM site")]


def add(
    book: Book,
    zone_id: str,
    name: str,
    habitat: str,
    extent: Quantity,
    listed_on: dt.date,
    *,
    access: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    note: str = "",
) -> Site:
    """Put a new site on the list."""
    zone = zones.resolve(book, zone_id)
    if find_by_name(book, zone.id, name) is not None:
        raise Duplicate("site", f"{zone.name}/{name}")
    site = Site(
        id=ids.next_serial("site", numbers(book)),
        zone=zone.id,
        name=name,
        habitat=habitat,
        extent=extent,
        listed_on=listed_on,
        access=access,
        latitude=latitude,
        longitude=longitude,
        note=note,
    )
    book.run(f"INSERT INTO site ({_COLUMNS}) VALUES ({_VALUES})", site.to_row())
    return site


def get(book: Book, site_id: str) -> Site:
    """One site by id."""
    row = book.one(f"SELECT {_COLUMNS} FROM site WHERE id = ?", (site_id,))
    if row is None:
        raise NotFound("site", site_id)
    return Site.from_row(row)


def find_by_name(book: Book, zone_id: str, name: str) -> Site | None:
    """One site by zone and name, or nothing."""
    row = book.one(
        f"SELECT {_COLUMNS} FROM site WHERE zone = ? AND name = ?",
        (zone_id, name),
    )
    return None if row is None else Site.from_row(row)


def all_sites(book: Book, *, zone_id: str | None = None, habitat: str | None = None) -> list[Site]:
    """Every site, narrowed by zone or habitat if asked."""
    clauses: list[str] = []
    params: list[object] = []
    if zone_id is not None:
        clauses.append("zone = ?")
        params.append(zone_id)
    if habitat is not None:
        clauses.append("habitat = ?")
        params.append(habitat)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = book.all(f"SELECT {_COLUMNS} FROM site{where} ORDER BY id", params)
    return [Site.from_row(row) for row in rows]


def open_on(book: Book, on: dt.date, *, zone_id: str | None = None) -> list[Site]:
    """Every site that was on the list on a given day."""
    return [site for site in all_sites(book, zone_id=zone_id) if site.is_open(on)]


def retire(book: Book, site_id: str, on: dt.date, why: str = "") -> Site:
    """Take a site off the list from a given day."""
    site = get(book, site_id)
    if site.retired_on is not None:
        raise RuleViolation("site.retired", f"{site_id} was retired on {site.retired_on}")
    if on < site.listed_on:
        raise RuleViolation("site.retired", "a site cannot be retired before it was listed")
    note = f"{site.note}\nretired: {why}".strip() if why else site.note
    book.run(
        "UPDATE site SET retired_on = ?, note = ? WHERE id = ?",
        (on.isoformat(), note, site_id),
    )
    return get(book, site_id)


def remeasure(book: Book, site_id: str, extent: Quantity) -> Site:
    """Write a new extent against a site, keeping the habitat's unit."""
    site = get(book, site_id)
    if extent.unit != site.kind.extent_unit:
        raise RuleViolation(
            "site.extent",
            f"a {site.kind.name} is measured in {site.kind.extent_unit}",
        )
    book.run("UPDATE site SET extent = ? WHERE id = ?", (str(extent), site_id))
    return get(book, site_id)


def total_extent(book: Book, habitat: str, *, zone_id: str | None = None) -> Quantity:
    """How much of one habitat the district holds."""
    sites = all_sites(book, zone_id=zone_id, habitat=habitat)
    if not sites:
        return Quantity.parse(f"0 {hb.habitat(habitat).extent_unit}")
    total = sites[0].extent
    for site in sites[1:]:
        total = total + site.extent
    return total
