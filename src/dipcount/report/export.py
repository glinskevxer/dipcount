"""Getting the registers out of the book and into somebody's spreadsheet.

Every register the district keeps comes out as one comma separated file with
its own columns. That sounds like a convenience and it is really an insurance
policy: a district that can only read its records through this program has
made itself a hostage to it, and the first thing anybody asks for when the
state audits is the raw data in something they can open.

The exports are deliberately flat. No nesting, no repeated header rows, one
row per record, and the identifiers spelled out so the files can be joined
back up by anybody with a spreadsheet.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from pathlib import Path

from dipcount import clock, species
from dipcount.errors import NotFound
from dipcount.report.sheet import Sheet, table
from dipcount.store import (
    applicators,
    blocks,
    exclusions,
    inspections,
    inventory,
    pools,
    products,
    requests,
    runs,
    sites,
    traps,
    treatments,
)
from dipcount.store.book import Book

Window = tuple[dt.date, dt.date]


def sites_sheet(book: Book) -> Sheet:
    """The site list."""
    rows = [
        [
            one.id,
            one.zone,
            one.name,
            one.habitat,
            str(one.extent),
            one.listed_on.isoformat(),
            one.retired_on.isoformat() if one.retired_on else "",
            "" if one.latitude is None else f"{one.latitude:.5f}",
            "" if one.longitude is None else f"{one.longitude:.5f}",
        ]
        for one in sites.all_sites(book)
    ]
    return table(
        ["site", "zone", "name", "habitat", "extent", "listed", "retired", "lat", "lon"],
        rows,
    )


def traps_sheet(book: Book) -> Sheet:
    """The trap list."""
    rows = [
        [
            one.id,
            one.zone,
            one.name,
            one.kind,
            one.listed_on.isoformat(),
            one.retired_on.isoformat() if one.retired_on else "",
        ]
        for one in traps.all_traps(book)
    ]
    return table(["trap", "zone", "name", "kind", "listed", "retired"], rows)


def inspections_sheet(book: Book, window: Window) -> Sheet:
    """Every larval visit over a window, one row a visit."""
    rows = [
        [
            one.id,
            one.site,
            one.on.isoformat(),
            one.week,
            one.inspector,
            "yes" if one.water else "no",
            str(one.dips),
            str(one.larvae),
            str(one.pupae),
            str(one.rafts),
            f"{one.per_dip:.2f}",
            " ".join(one.species_seen()),
        ]
        for one in inspections.between(book, *window)
    ]
    return table(
        [
            "inspection",
            "site",
            "day",
            "week",
            "inspector",
            "water",
            "dips",
            "larvae",
            "pupae",
            "rafts",
            "per dip",
            "species",
        ],
        rows,
    )


def collections_sheet(book: Book, window: Window) -> Sheet:
    """Every jar over a window, one row a jar."""
    rows = [
        [
            one.id,
            one.trap,
            one.on.isoformat(),
            one.week,
            clock.stamp(one.set_at),
            clock.stamp(one.pulled_at),
            str(one.nights),
            "yes" if one.worked else "no",
            str(one.females),
            str(one.males),
            f"{one.index:.2f}",
        ]
        for one in traps.between(book, *window)
    ]
    return table(
        [
            "collection",
            "trap",
            "day",
            "week",
            "set",
            "pulled",
            "nights",
            "worked",
            "females",
            "males",
            "per night",
        ],
        rows,
    )


def pools_sheet(book: Book, window: Window) -> Sheet:
    """Every pool sent over a window, with each virus result."""
    viruses = species.viruses()
    rows = []
    for one in pools.submitted_between(book, *window):
        rows.append(
            [
                one.id,
                one.collection,
                one.species,
                str(one.size),
                one.submitted_on.isoformat(),
                one.lab,
                *[one.outcome(virus) for virus in viruses],
            ],
        )
    return table(
        ["pool", "collection", "species", "size", "submitted", "lab", *viruses],
        rows,
    )


def treatments_sheet(book: Book, window: Window) -> Sheet:
    """Every larval treatment over a window."""
    rows = [
        [
            one.id,
            one.site,
            one.product,
            one.lot,
            one.on.isoformat(),
            one.week,
            str(one.extent),
            str(one.amount),
            str(one.rate),
            one.applicator,
            one.licence,
        ]
        for one in treatments.between(book, *window)
    ]
    return table(
        [
            "treatment",
            "site",
            "product",
            "lot",
            "day",
            "week",
            "extent",
            "amount",
            "rate",
            "applicator",
            "licence",
        ],
        rows,
    )


def runs_sheet(book: Book, window: Window) -> Sheet:
    """Every spray run over a window."""
    rows = [
        [
            one.id,
            one.block,
            one.product,
            one.lot,
            one.on.isoformat(),
            clock.stamp(one.started_at),
            clock.stamp(one.finished_at),
            f"{one.acres:g}",
            str(one.amount),
            "" if one.wind_mph is None else f"{one.wind_mph:g}",
            "" if one.temperature is None else f"{one.temperature:g}",
            one.applicator,
            one.licence,
        ]
        for one in runs.between(book, *window)
    ]
    return table(
        [
            "run",
            "block",
            "product",
            "lot",
            "day",
            "started",
            "finished",
            "acres",
            "amount",
            "wind",
            "temperature",
            "applicator",
            "licence",
        ],
        rows,
    )


def requests_sheet(book: Book, window: Window) -> Sheet:
    """Every call over a window."""
    rows = [
        [
            one.id,
            one.kind,
            one.zone,
            one.address,
            clock.stamp(one.taken_at),
            clock.stamp(one.visited_at) if one.visited_at else "",
            clock.stamp(one.closed_at) if one.closed_at else "",
            one.site or "",
            one.outcome,
        ]
        for one in requests.between(book, *window)
    ]
    return table(
        ["call", "kind", "zone", "address", "taken", "visited", "closed", "site", "outcome"],
        rows,
    )


def products_sheet(book: Book) -> Sheet:
    """The product shelf."""
    rows = [
        [
            one.id,
            one.name,
            one.registration,
            one.maker,
            one.active,
            f"{one.percent:g}",
            one.form,
            one.purpose,
            "yes" if one.restricted else "",
            one.signal,
        ]
        for one in products.all_products(book)
    ]
    return table(
        [
            "product",
            "name",
            "registration",
            "maker",
            "active",
            "percent",
            "form",
            "purpose",
            "restricted",
            "signal",
        ],
        rows,
    )


def lots_sheet(book: Book) -> Sheet:
    """The shed, with what is left of each lot."""
    rows = [
        [
            one.lot.id,
            one.lot.product,
            one.lot.code,
            one.lot.received_on.isoformat(),
            one.lot.expires_on.isoformat() if one.lot.expires_on else "",
            str(one.lot.quantity),
            str(one.drawn),
            str(one.left),
        ]
        for one in inventory.holdings(book)
    ]
    return table(
        ["lot", "product", "code", "received", "expires", "in", "drawn", "left"],
        rows,
    )


def crew_sheet(book: Book) -> Sheet:
    """The licence register."""
    rows = [
        [
            one.id,
            one.name,
            one.licence,
            one.grade,
            " ".join(one.categories),
            one.certified_on.isoformat(),
            one.expires_on.isoformat(),
            one.supervisor or "",
            one.left_on.isoformat() if one.left_on else "",
        ]
        for one in applicators.all_applicators(book)
    ]
    return table(
        [
            "applicator",
            "name",
            "licence",
            "grade",
            "categories",
            "certified",
            "expires",
            "supervisor",
            "left",
        ],
        rows,
    )


def register_sheet(book: Book) -> Sheet:
    """The no spray register, with the blocks each entry falls in."""
    rows = [
        [
            one.id,
            one.kind,
            one.name,
            one.zone,
            one.contact,
            one.phone,
            str(one.buffer),
            "never" if one.absolute else str(one.hours),
            " ".join(two.id for two in blocks.blocks_for(book, one.id)),
            one.listed_on.isoformat(),
            one.removed_on.isoformat() if one.removed_on else "",
        ]
        for one in exclusions.all_entries(book)
    ]
    return table(
        [
            "entry",
            "kind",
            "name",
            "zone",
            "contact",
            "phone",
            "buffer",
            "notice",
            "blocks",
            "listed",
            "removed",
        ],
        rows,
    )


_WINDOWED: dict[str, Callable[[Book, Window], Sheet]] = {
    "inspections": inspections_sheet,
    "collections": collections_sheet,
    "pools": pools_sheet,
    "treatments": treatments_sheet,
    "runs": runs_sheet,
    "requests": requests_sheet,
}

_WHOLE: dict[str, Callable[[Book], Sheet]] = {
    "sites": sites_sheet,
    "traps": traps_sheet,
    "products": products_sheet,
    "lots": lots_sheet,
    "crew": crew_sheet,
    "register": register_sheet,
}


def names() -> list[str]:
    """Every register that can be exported."""
    return sorted([*_WINDOWED, *_WHOLE])


def sheet_for(book: Book, name: str, window: Window) -> Sheet:
    """One register as a sheet."""
    if name in _WHOLE:
        return _WHOLE[name](book)
    if name in _WINDOWED:
        return _WINDOWED[name](book, window)
    raise NotFound("export", name)


def write(book: Book, name: str, window: Window, into: Path) -> Path:
    """Write one register to a file and say where it went."""
    into.mkdir(parents=True, exist_ok=True)
    path = into / f"{name}.csv"
    path.write_text(sheet_for(book, name, window).csv())
    return path


def write_all(book: Book, window: Window, into: Path) -> list[Path]:
    """Write every register to a directory."""
    return [write(book, name, window, into) for name in names()]
