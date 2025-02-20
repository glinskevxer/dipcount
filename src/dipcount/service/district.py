"""Putting zones and sites on the district's list, and taking them off.

Every call here writes the audit trail as part of the same grouped write as
the record itself. That is the point of doing it in a service rather than in a
store: a site that exists with nothing on the trail to say who listed it is a
record the district cannot defend, and it should not be possible to produce
one by calling the wrong function.
"""

from __future__ import annotations

import datetime as dt

from dipcount.errors import RuleViolation
from dipcount.model.audit import Entry
from dipcount.model.site import Site
from dipcount.model.zone import Zone
from dipcount.store import audit, sites, zones
from dipcount.store.book import Book
from dipcount.units import Quantity


def list_zone(
    book: Book,
    actor: str,
    name: str,
    supervisor: str = "",
    note: str = "",
    at: dt.datetime | None = None,
) -> Zone:
    """Open a new zone."""
    with book.writing():
        zone = zones.add(book, name, supervisor, note)
        audit.record(book, actor, "opened zone", zone.id, name, at=at)
    return zone


def list_site(
    book: Book,
    actor: str,
    zone: str,
    name: str,
    habitat: str,
    extent: Quantity,
    on: dt.date,
    *,
    access: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    note: str = "",
    at: dt.datetime | None = None,
) -> Site:
    """Put a piece of water on the inspection list."""
    with book.writing():
        site = sites.add(
            book,
            zone,
            name,
            habitat,
            extent,
            on,
            access=access,
            latitude=latitude,
            longitude=longitude,
            note=note,
        )
        audit.record(
            book,
            actor,
            "listed site",
            site.id,
            f"{site.kind.name}, {site.extent}",
            at=at,
        )
    return site


def retire_site(
    book: Book,
    actor: str,
    site_id: str,
    on: dt.date,
    why: str = "",
    at: dt.datetime | None = None,
) -> Site:
    """Take a site off the list from a given day."""
    with book.writing():
        site = sites.retire(book, site_id, on, why)
        audit.record(book, actor, "retired site", site_id, why or on.isoformat(), at=at)
    return site


def remeasure_site(
    book: Book,
    actor: str,
    site_id: str,
    extent: Quantity,
    at: dt.datetime | None = None,
) -> Site:
    """Write a new extent against a site, keeping what it used to be."""
    before = sites.get(book, site_id)
    if before.extent == extent:
        raise RuleViolation("site.extent", f"{site_id} already measures {extent}")
    with book.writing():
        site = sites.remeasure(book, site_id, extent)
        audit.record(book, actor, "remeasured site", site_id, f"{before.extent} to {extent}", at=at)
    return site


def move_site(
    book: Book,
    actor: str,
    site_id: str,
    zone: str,
    at: dt.datetime | None = None,
) -> Site:
    """Move a site into another zone, which happens when a boundary moves."""
    before = sites.get(book, site_id)
    target = zones.resolve(book, zone)
    if before.zone == target.id:
        raise RuleViolation("site.zone", f"{site_id} is already in {target.name}")
    with book.writing():
        site = sites.move(book, site_id, target.id)
        audit.record(book, actor, "moved site", site_id, f"{before.zone} to {target.id}", at=at)
    return site


def site_history(book: Book, site_id: str) -> list[Entry]:
    """Everything the trail holds about one site."""
    sites.get(book, site_id)
    return audit.about(book, site_id)
