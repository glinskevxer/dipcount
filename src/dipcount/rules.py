"""The rule book, written once and referred to by name.

Every refusal and every decision in this package names a clause from here, so
the question "why did it say that" has an answer that does not involve reading
the code. The names are what :class:`~dipcount.errors.RuleViolation` carries
and what the generated rule book prints.

The larval clauses are worth reading together, because two of them decide what
a third one measures. The action threshold is a number of larvae per dip. What
that number is depends on whether a virus vector was in the sample, so
``larval.vector`` changes the number ``larval.threshold`` is compared against.
And ``larval.pupal`` decides whether comparing anything to it is meaningful at
all, since a brood that is mostly pupae will not eat a larvicide however much
of it goes in the water. Reading the three as independent gives an answer that
is wrong in both directions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from dipcount import habitat as hb
from dipcount import species
from dipcount.errors import NotFound


@dataclass(frozen=True)
class Clause:
    """One numbered rule, its name and what it says."""

    name: str
    heading: str
    text: str

    @property
    def area(self) -> str:
        """Which part of the work this clause belongs to."""
        return self.name.split(".", 1)[0]


CLAUSES: Final[tuple[Clause, ...]] = (
    Clause(
        "larval.threshold",
        "when a site is worth treating",
        "A site is worth treating when the larvae per dip reach the figure for"
        " its habitat. Below that figure the visit is recorded and nothing is"
        " applied.",
    ),
    Clause(
        "larval.vector",
        "a vector in the sample halves the figure",
        "If any species in the sample carries a virus the district watches for,"
        " the habitat figure is halved before the count is compared to it.",
    ),
    Clause(
        "larval.pupal",
        "a brood that is mostly pupae is past treating",
        "When pupae are half or more of the immatures, a larvicide will not"
        " reach the brood. The site is not treated with one, and the next visit"
        " is set for the emergence rather than for the interval.",
    ),
    Clause(
        "larval.late",
        "third and fourth instars close the window",
        "When three quarters of the larvae are third or fourth instar the"
        " treatment has to go on within a day to be worth making at all.",
    ),
    Clause(
        "larval.raft",
        "egg rafts are a reason to come back, not to treat",
        "Egg rafts on their own do not meet any threshold. They shorten the"
        " interval to the next visit to four days.",
    ),
    Clause(
        "larval.dry",
        "a dry site is a result",
        "A site with no water is recorded as inspected. It is not treated, and"
        " it goes to the back of the round rather than off the list.",
    ),
    Clause(
        "site.extent",
        "a site is measured in the unit its habitat uses",
        "Structures are counted one at a time and ground is measured in acres."
        " A rate written for one cannot be applied over the other.",
    ),
    Clause(
        "site.retired",
        "a site comes off the list once",
        "A retired site is not retired again, and it cannot be retired before"
        " the day it was listed.",
    ),
    Clause(
        "site.zone",
        "a site belongs to one zone",
        "Moving a site to the zone it is already in is not a move, and a name"
        " already used in the receiving zone blocks one.",
    ),
)

BY_NAME: Final[dict[str, Clause]] = {clause.name: clause for clause in CLAUSES}


def clause(name: str) -> Clause:
    """One clause by name."""
    try:
        return BY_NAME[name]
    except KeyError as exc:
        raise NotFound("clause", name) from exc


def areas() -> list[str]:
    """Every part of the work the rule book covers."""
    return sorted({one.area for one in CLAUSES})


def clauses_in(area: str) -> list[Clause]:
    """Every clause belonging to one part of the work."""
    return [one for one in CLAUSES if one.area == area]


_LARVAL: Final[dict[str, str]] = {
    "catch_basin": "0.5",
    "roadside_ditch": "1.0",
    "floodplain": "1.0",
    "cattail_marsh": "0.5",
    "retention_pond": "0.5",
    "woodland_pool": "1.0",
    "tyre_pile": "0.2",
    "container": "0.2",
    "lagoon": "1.0",
    "tailwater": "1.0",
    "snowmelt_pool": "1.0",
    "livestock_trough": "0.2",
    "ornamental_pond": "0.2",
    "sump": "0.5",
}

PUPAL_STOP: Final = Decimal("0.5")
"""At or above this share of pupae, a larvicide is the wrong answer."""

LATE_URGENT: Final = Decimal("0.75")
"""At or above this share of late instars, the treatment cannot wait."""

RAFT_INTERVAL: Final = 4
"""Days to the next visit when egg rafts were the only thing found."""


def base_threshold(habitat: str) -> Decimal:
    """The larvae per dip a habitat is worth treating at, vectors aside."""
    hb.habitat(habitat)
    return Decimal(_LARVAL[habitat])


def threshold(habitat: str, vector_present: bool) -> Decimal:
    """The figure this sample is actually measured against.

    A vector in the sample halves it, which is ``larval.vector`` deciding what
    ``larval.threshold`` compares to.
    """
    figure = base_threshold(habitat)
    return figure / 2 if vector_present else figure


def carries_a_vector(codes: list[str]) -> bool:
    """Whether any of these species carries something worth halving for."""
    for code in codes:
        try:
            if species.species(code).is_vector:
                return True
        except NotFound:
            continue
    return False


def thresholds() -> dict[str, Decimal]:
    """Every habitat's base figure, for a report or a check."""
    return {key: Decimal(value) for key, value in _LARVAL.items()}
