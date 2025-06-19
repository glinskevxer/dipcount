"""The shelf the district actually buys from.

This is the starting stock, not a fixed list. Registrations lapse, makers
reformulate and a district picks up whatever its neighbours have had luck
with, so the shelf lives in the book and this module only puts the first
entries in it. Everything here is written the way it is on the container:
the registration number, the share of active ingredient, and a rate range for
each kind of water the label names.

The rate ranges are the part worth being careful with. The low end is for
clean shallow water and the high end is for a lagoon or a ditch full of
organics, where the bacteria get eaten before the larvae find them. A product
labelled for both reads as one product and behaves like two.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from dipcount import habitat as hb
from dipcount.errors import NotFound
from dipcount.model.product import ADULTICIDE, LARVICIDE, PUPICIDE
from dipcount.store import products
from dipcount.store.book import Book
from dipcount.units import Quantity, Rate, quantity


@dataclass(frozen=True)
class Entry:
    """One product as it comes off the container, with its label."""

    name: str
    registration: str
    maker: str
    active: str
    percent: str
    form: str
    purpose: str
    rates: tuple[tuple[str, str, str, str | None, int], ...] = field(default_factory=tuple)
    restricted: bool = False
    signal: str = "caution"
    reentry: int = 0
    note: str = ""


SHELF: Final[tuple[Entry, ...]] = (
    Entry(
        "Bactilore G",
        "73049-20",
        "Vestrum Biologicals",
        "Bacillus thuringiensis subspecies israelensis",
        "4.5",
        "granule",
        LARVICIDE,
        (
            ("cattail_marsh", "2.5 lb", "10 lb", "40 lb", 7),
            ("retention_pond", "2.5 lb", "10 lb", "40 lb", 7),
            ("roadside_ditch", "2.5 lb", "10 lb", "40 lb", 7),
            ("floodplain", "5 lb", "20 lb", "60 lb", 7),
            ("woodland_pool", "2.5 lb", "10 lb", "30 lb", 7),
            ("snowmelt_pool", "2.5 lb", "10 lb", "30 lb", 7),
            ("tailwater", "5 lb", "20 lb", "60 lb", 7),
            ("lagoon", "10 lb", "20 lb", "80 lb", 7),
        ),
        note="the workhorse, and the granules carry through cattail cover",
    ),
    Entry(
        "Bactilore WSP",
        "73049-38",
        "Vestrum Biologicals",
        "Bacillus thuringiensis subspecies israelensis",
        "37",
        "water soluble pouch",
        LARVICIDE,
        (
            ("catch_basin", "1 each", "2 each", "8 each", 30),
            ("tyre_pile", "1 each", "2 each", "8 each", 30),
            ("container", "1 each", "1 each", "6 each", 30),
            ("livestock_trough", "1 each", "1 each", "6 each", 30),
            ("sump", "1 each", "2 each", "8 each", 30),
        ),
        note="one pouch to a structure, and two where the sump runs deep",
    ),
    Entry(
        "Hesper 30 briquets",
        "8329-114",
        "Hesper Chemical",
        "S-methoprene",
        "1.8",
        "briquet",
        LARVICIDE,
        (
            ("catch_basin", "1 each", "1 each", "2 each", 120),
            ("sump", "1 each", "2 each", "4 each", 120),
        ),
        note="a hundred and fifty days out of one briquet, so the basin round is twice a year",
    ),
    Entry(
        "Hesper flowable",
        "8329-129",
        "Hesper Chemical",
        "S-methoprene",
        "5",
        "liquid",
        LARVICIDE,
        (
            ("roadside_ditch", "3 fl oz", "6 fl oz", "24 fl oz", 10),
            ("floodplain", "3 fl oz", "6 fl oz", "24 fl oz", 10),
            ("tailwater", "3 fl oz", "6 fl oz", "24 fl oz", 10),
            ("woodland_pool", "3 fl oz", "4 fl oz", "16 fl oz", 10),
        ),
        note="stops the pupa becoming an adult, so a late brood is still worth treating",
    ),
    Entry(
        "Sphaerix WG",
        "73049-57",
        "Vestrum Biologicals",
        "Bacillus sphaericus",
        "6.5",
        "granule",
        LARVICIDE,
        (
            ("lagoon", "10 lb", "20 lb", "60 lb", 14),
            ("catch_basin", "0.2 lb", "0.4 lb", "1.6 lb", 21),
            ("retention_pond", "5 lb", "10 lb", "40 lb", 14),
        ),
        note="holds up where the organic load eats the other one, and it recycles in the carcass",
    ),
    Entry(
        "Spinolux SC",
        "62719-291",
        "Ardleigh Crop Science",
        "spinosad",
        "22.5",
        "liquid",
        LARVICIDE,
        (
            ("roadside_ditch", "1.6 fl oz", "3.2 fl oz", "12 fl oz", 21),
            ("livestock_trough", "0.1 fl oz", "0.2 fl oz", "0.8 fl oz", 21),
            ("ornamental_pond", "0.1 fl oz", "0.2 fl oz", "0.8 fl oz", 21),
        ),
        note="cleared for water stock drink out of, which the bacterials mostly are not",
    ),
    Entry(
        "Larvasheen oil",
        "8329-72",
        "Hesper Chemical",
        "mineral oil",
        "99",
        "surface oil",
        PUPICIDE,
        (("lagoon", "3 gal", "5 gal", "20 gal", 7),),
        note="reaches pupae, which nothing bacterial does, and it goes on the surface",
    ),
    Entry(
        "Skimfilm",
        "53263-28",
        "Corbin Surfactants",
        "isostearyl alcohol ethoxylate",
        "100",
        "monomolecular film",
        PUPICIDE,
        (("lagoon", "0.2 gal", "0.5 gal", "2 gal", 7),),
        note="a film one molecule thick, and wind pushes it into the lee corner",
    ),
    Entry(
        "Kestrel ULV",
        "1021-1873",
        "Kestrel Vector Products",
        "permethrin",
        "4.6",
        "liquid",
        ADULTICIDE,
        (),
        restricted=True,
        signal="warning",
        reentry=0,
        note="ground ultra low volume, and the block rate is on the run rather than a site",
    ),
    Entry(
        "Marrowmist",
        "1021-1901",
        "Kestrel Vector Products",
        "sumithrin",
        "3",
        "liquid",
        ADULTICIDE,
        (),
        restricted=False,
        signal="caution",
        note="the one that goes out where the beekeepers are, because it breaks down faster",
    ),
)


def _rate(text: str, per: str) -> Rate:
    return Rate(quantity(text), per)


def _per_for(habitat: str) -> str:
    return hb.habitat(habitat).extent_unit


def stock(book: Book, on: dt.date, *, only: tuple[str, ...] = ()) -> list[str]:
    """Put the starting shelf in a book, and say what went on it.

    A product already on the shelf under the same name is left alone, so this
    can be run against a book that has been going for years without touching
    what is there.
    """
    added: list[str] = []
    for entry in SHELF:
        if only and entry.name not in only:
            continue
        if products.find_by_name(book, entry.name) is not None:
            continue
        made = products.add(
            book,
            entry.name,
            entry.registration,
            entry.maker,
            entry.active,
            Decimal(entry.percent),
            entry.form,
            entry.purpose,
            on,
            restricted=entry.restricted,
            signal=entry.signal,
            reentry=entry.reentry,
            note=entry.note,
        )
        for habitat, low, high, cap, gap in entry.rates:
            per = _per_for(habitat)
            products.label(
                book,
                made.id,
                habitat,
                _rate(low, per),
                _rate(high, per),
                season_max=None if cap is None else quantity(cap),
                interval_days=gap,
            )
        added.append(made.id)
    return added


def entry(name: str) -> Entry:
    """One entry off the starting shelf by name."""
    for one in SHELF:
        if one.name == name:
            return one
    raise NotFound("formulary entry", name)


def actives() -> list[str]:
    """Every active ingredient the starting shelf holds."""
    return sorted({one.active for one in SHELF})


def season_cap(entry_name: str, habitat: str) -> Quantity | None:
    """What one entry's label allows in a season for one habitat."""
    for habitat_key, _, _, cap, _ in entry(entry_name).rates:
        if habitat_key == habitat:
            return None if cap is None else quantity(cap)
    return None
