"""The mosquitoes the district identifies, and what each of them means.

A count is not a number until it is a number of something. The species is what
turns forty females in a trap into either a nuisance problem or a virus
problem, and the two get different answers, so the table below carries the
part of the biology the rest of the package reasons with: where the larvae
live, what the adults feed on, which viruses they carry, and how far they will
fly from where they hatched.

Four letter codes are what the identification bench writes on the vial, and
they are what everything downstream keys on. The Latin binomial is here so a
report can print something a state entomologist recognises.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from dipcount.errors import NotFound

FLOODWATER: Final = "floodwater"
CONTAINER: Final = "container"
PERMANENT: Final = "permanent"
WOODLAND: Final = "woodland pool"

BIRD: Final = "bird"
MAMMAL: Final = "mammal"
BOTH: Final = "bird and mammal"

WNV: Final = "West Nile"
EEE: Final = "eastern equine encephalitis"
LAC: Final = "La Crosse"
SLE: Final = "St Louis encephalitis"
WEE: Final = "western equine encephalitis"


@dataclass(frozen=True)
class Species:
    """One species, and the handful of facts the district acts on."""

    code: str
    genus: str
    name: str
    guild: str
    hosts: str
    flight_km: float
    overwinters: str
    broods: str
    carries: tuple[str, ...] = field(default_factory=tuple)
    biting: str = "dusk"
    note: str = ""

    @property
    def binomial(self) -> str:
        """The name a state entomologist expects to read."""
        return f"{self.genus} {self.name}"

    @property
    def is_vector(self) -> bool:
        """Whether this species carries anything the district watches for."""
        return bool(self.carries)

    def carries_virus(self, virus: str) -> bool:
        """Whether this species is a vector of a named virus."""
        return virus in self.carries


_TABLE: Final[tuple[Species, ...]] = (
    Species(
        "CXPP",
        "Culex",
        "pipiens",
        PERMANENT,
        BIRD,
        1.6,
        "adult",
        "many",
        (WNV, SLE),
        "night",
        "the catch basin mosquito, and the one that drives the virus season",
    ),
    Species(
        "CXRS",
        "Culex",
        "restuans",
        PERMANENT,
        BIRD,
        1.6,
        "adult",
        "many",
        (WNV,),
        "night",
        "early season, and hard to tell from pipiens on a rubbed specimen",
    ),
    Species(
        "CXTR",
        "Culex",
        "tarsalis",
        PERMANENT,
        BOTH,
        8.0,
        "adult",
        "many",
        (WNV, WEE, SLE),
        "night",
        "irrigation and tailwater, and it will fly a long way to find a host",
    ),
    Species(
        "CXSA",
        "Culex",
        "salinarius",
        PERMANENT,
        BOTH,
        3.0,
        "adult",
        "many",
        (WNV, EEE),
        "night",
    ),
    Species(
        "AEVX",
        "Aedes",
        "vexans",
        FLOODWATER,
        MAMMAL,
        16.0,
        "egg",
        "many",
        (),
        "dusk",
        "the flood nuisance species, and the one the complaints are about",
    ),
    Species(
        "AETV",
        "Aedes",
        "trivittatus",
        FLOODWATER,
        MAMMAL,
        3.0,
        "egg",
        "many",
        (LAC,),
    ),
    Species(
        "AEST",
        "Aedes",
        "sticticus",
        FLOODWATER,
        MAMMAL,
        10.0,
        "egg",
        "many",
        (),
    ),
    Species(
        "AECN",
        "Aedes",
        "canadensis",
        WOODLAND,
        MAMMAL,
        2.0,
        "egg",
        "one",
        (LAC,),
    ),
    Species(
        "AETR",
        "Aedes",
        "triseriatus",
        CONTAINER,
        MAMMAL,
        0.5,
        "egg",
        "many",
        (LAC,),
        "day",
        "tree holes and tyres, and the reason a tyre pile is a site",
    ),
    Species(
        "AEJP",
        "Aedes",
        "japonicus",
        CONTAINER,
        MAMMAL,
        0.8,
        "egg",
        "many",
        (),
        "day",
    ),
    Species(
        "AEAL",
        "Aedes",
        "albopictus",
        CONTAINER,
        MAMMAL,
        0.4,
        "egg",
        "many",
        (LAC,),
        "day",
        "not established here yet, and every collection is reported",
    ),
    Species(
        "ANQD",
        "Anopheles",
        "quadrimaculatus",
        PERMANENT,
        MAMMAL,
        2.0,
        "adult",
        "many",
        (),
        "night",
    ),
    Species(
        "ANPN",
        "Anopheles",
        "punctipennis",
        PERMANENT,
        MAMMAL,
        1.5,
        "adult",
        "many",
        (),
        "night",
    ),
    Species(
        "CQPR",
        "Coquillettidia",
        "perturbans",
        PERMANENT,
        BOTH,
        8.0,
        "larva",
        "one",
        (EEE,),
        "dusk",
        "the larvae breathe off cattail roots, so nothing floating reaches them",
    ),
    Species(
        "CSIN",
        "Culiseta",
        "inornata",
        PERMANENT,
        MAMMAL,
        2.0,
        "adult",
        "many",
        (),
        "night",
    ),
    Species(
        "CSML",
        "Culiseta",
        "melanura",
        WOODLAND,
        BIRD,
        1.5,
        "larva",
        "many",
        (EEE,),
        "night",
        "cedar swamp crypts, and the reason eastern equine is a bird problem first",
    ),
    Species(
        "PSCL",
        "Psorophora",
        "columbiae",
        FLOODWATER,
        MAMMAL,
        6.0,
        "egg",
        "many",
        (),
        "dusk",
    ),
    Species(
        "PSFX",
        "Psorophora",
        "ferox",
        WOODLAND,
        MAMMAL,
        2.0,
        "egg",
        "many",
        (),
        "day",
    ),
)

BY_CODE: Final[dict[str, Species]] = {one.code: one for one in _TABLE}


def species(code: str) -> Species:
    """One species by its four letter code."""
    try:
        return BY_CODE[code.upper()]
    except KeyError as exc:
        raise NotFound("species", code) from exc


def known() -> list[Species]:
    """Every species in the table, in code order."""
    return sorted(_TABLE, key=lambda one: one.code)


def in_guild(guild: str) -> list[Species]:
    """Every species whose larvae live in a kind of water."""
    return [one for one in known() if one.guild == guild]


def vectors_of(virus: str) -> list[Species]:
    """Every species that carries a named virus."""
    return [one for one in known() if one.carries_virus(virus)]


def viruses() -> list[str]:
    """Every virus any species in the table carries."""
    found = {virus for one in _TABLE for virus in one.carries}
    return sorted(found)


def resolve(text: str) -> Species:
    """Find a species by code, by binomial, or by the species word alone."""
    folded = text.strip().lower()
    if folded.upper() in BY_CODE:
        return BY_CODE[folded.upper()]
    for one in _TABLE:
        if folded in (one.binomial.lower(), one.name.lower()):
            return one
    abbreviated = folded.replace(".", "").replace(" ", "")
    for one in _TABLE:
        # The bench writes Cx. tarsalis, and the first two letters of the code
        # are the same abbreviation the bench uses for the genus.
        if abbreviated == f"{one.code[:2]}{one.name}".lower():
            return one
    raise NotFound("species", text)
