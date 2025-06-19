"""The kinds of water the district inspects, and what each kind implies.

A habitat is not a label on a map pin. It decides how the site is measured, how
often it is looked at, what can legally be put in it, and which species are
worth looking for when the dipper comes up with something. A catch basin is
counted one structure at a time and treated with a briquet. A cattail marsh is
counted in acres, and nothing that floats will reach larvae breathing off the
roots. Getting this wrong is not a rounding error, it is a treatment that does
nothing and a use report that says otherwise.

The ``extent_unit`` field is the one that catches people out. Sites measured in
structures take a per structure rate, sites measured in acres take a per acre
rate, and a rate written for one cannot be applied over the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from dipcount import species
from dipcount.errors import NotFound

PERMANENT: Final = "permanent"
SEMI: Final = "semi permanent"
TEMPORARY: Final = "temporary"

DIPPER: Final = "dipper"
PIPETTE: Final = "pipette"
NET: Final = "net"
VISUAL: Final = "visual"

BRIQUET: Final = "briquet"
GRANULE: Final = "granule"
LIQUID: Final = "liquid"
PELLET: Final = "pellet"
POUCH: Final = "water soluble pouch"
OIL: Final = "surface oil"
FILM: Final = "monomolecular film"


@dataclass(frozen=True)
class Habitat:
    """One kind of standing water, and how the district works it."""

    key: str
    name: str
    permanence: str
    extent_unit: str
    dip_method: str
    interval_days: int
    guilds: tuple[str, ...]
    forms: tuple[str, ...]
    fish: bool = False
    public: bool = True
    note: str = ""

    @property
    def counted_one_at_a_time(self) -> bool:
        """Whether the site is measured in structures rather than in ground."""
        return self.extent_unit == "each"

    def allows(self, form: str) -> bool:
        """Whether a formulation can be put into this kind of water at all."""
        return form in self.forms

    def species_here(self) -> list[species.Species]:
        """Every species whose larvae would be expected in this water."""
        return [one for guild in self.guilds for one in species.in_guild(guild)]


_TABLE: Final[tuple[Habitat, ...]] = (
    Habitat(
        "catch_basin",
        "storm drain catch basin",
        SEMI,
        "each",
        PIPETTE,
        21,
        (species.PERMANENT,),
        (BRIQUET, PELLET, GRANULE, POUCH),
        note="the sump holds water all summer and the whole route is one visit",
    ),
    Habitat(
        "roadside_ditch",
        "roadside ditch",
        TEMPORARY,
        "acre",
        DIPPER,
        7,
        (species.FLOODWATER, species.PERMANENT),
        (GRANULE, LIQUID, POUCH),
    ),
    Habitat(
        "floodplain",
        "river floodplain",
        TEMPORARY,
        "acre",
        DIPPER,
        4,
        (species.FLOODWATER,),
        (GRANULE, LIQUID),
        note="dry most of the year and a brood four days after the river drops",
    ),
    Habitat(
        "cattail_marsh",
        "cattail marsh",
        PERMANENT,
        "acre",
        DIPPER,
        14,
        (species.PERMANENT,),
        (GRANULE, PELLET),
        fish=True,
        note="larvae breathe off the roots, so nothing that floats reaches them",
    ),
    Habitat(
        "retention_pond",
        "stormwater retention pond",
        PERMANENT,
        "acre",
        DIPPER,
        14,
        (species.PERMANENT,),
        (GRANULE, LIQUID, PELLET),
        fish=True,
    ),
    Habitat(
        "woodland_pool",
        "woodland vernal pool",
        TEMPORARY,
        "acre",
        DIPPER,
        7,
        (species.WOODLAND,),
        (GRANULE, LIQUID),
        public=False,
        note="one brood in spring and the pool is gone by the middle of June",
    ),
    Habitat(
        "tyre_pile",
        "scrap tyre pile",
        SEMI,
        "each",
        PIPETTE,
        14,
        (species.CONTAINER,),
        (POUCH, LIQUID, PELLET),
        public=False,
        note="the reason triseriatus is a district problem and not a nuisance",
    ),
    Habitat(
        "container",
        "artificial container",
        TEMPORARY,
        "each",
        PIPETTE,
        14,
        (species.CONTAINER,),
        (POUCH, LIQUID),
        public=False,
        note="tip it out if you can, and treat it only if you cannot",
    ),
    Habitat(
        "lagoon",
        "sewage lagoon",
        PERMANENT,
        "acre",
        DIPPER,
        14,
        (species.PERMANENT,),
        (GRANULE, LIQUID, OIL, FILM),
        note="organic load eats bacterial products, so the rate goes to the top",
    ),
    Habitat(
        "tailwater",
        "irrigation tailwater",
        TEMPORARY,
        "acre",
        DIPPER,
        5,
        (species.PERMANENT, species.FLOODWATER),
        (GRANULE, LIQUID),
        public=False,
        note="tarsalis water, and it refills every time the field is watered",
    ),
    Habitat(
        "snowmelt_pool",
        "snowmelt pool",
        TEMPORARY,
        "acre",
        DIPPER,
        7,
        (species.WOODLAND, species.FLOODWATER),
        (GRANULE, LIQUID),
        note="the first larvae of the year and the ones nobody has budgeted for",
    ),
    Habitat(
        "livestock_trough",
        "livestock trough",
        SEMI,
        "each",
        PIPETTE,
        21,
        (species.PERMANENT,),
        (POUCH, LIQUID),
        public=False,
        note="stock drink out of it, so only what the label clears for that",
    ),
    Habitat(
        "ornamental_pond",
        "ornamental pond",
        PERMANENT,
        "each",
        VISUAL,
        21,
        (species.PERMANENT,),
        (POUCH, PELLET, LIQUID),
        fish=True,
        public=False,
        note="fish in it, so nothing that strips the surface",
    ),
    Habitat(
        "sump",
        "construction sump",
        TEMPORARY,
        "each",
        PIPETTE,
        7,
        (species.PERMANENT, species.CONTAINER),
        (POUCH, LIQUID, PELLET, BRIQUET),
        public=False,
        note="it sits for a season, so a briquet is worth the walk",
    ),
)

BY_KEY: Final[dict[str, Habitat]] = {one.key: one for one in _TABLE}


def habitat(key: str) -> Habitat:
    """One habitat by key."""
    try:
        return BY_KEY[key]
    except KeyError as exc:
        raise NotFound("habitat", key) from exc


def known() -> list[Habitat]:
    """Every habitat, in key order."""
    return sorted(_TABLE, key=lambda one: one.key)


def keys() -> list[str]:
    """Every habitat key, for a command line choice."""
    return [one.key for one in known()]


def counted_one_at_a_time() -> list[Habitat]:
    """Every habitat measured in structures rather than in ground."""
    return [one for one in known() if one.counted_one_at_a_time]


def holding_fish() -> list[Habitat]:
    """Every habitat where something is likely to be swimming."""
    return [one for one in known() if one.fish]


def accepting(form: str) -> list[Habitat]:
    """Every habitat a formulation may be put into."""
    return [one for one in known() if one.allows(form)]


def forms() -> list[str]:
    """Every formulation any habitat accepts."""
    return sorted({form for one in _TABLE for form in one.forms})
