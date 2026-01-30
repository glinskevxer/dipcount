"""The words this district uses, and what it means by them.

Half the arguments in mosquito control are about vocabulary. A "treatment" to
one district is anything put in water and to another is a work order covering
a round of forty catch basins. An "index" is females per trap night here and
larvae per dip somewhere else. None of that matters until two districts add
their numbers together, at which point it is the only thing that matters.

So the terms are written down once, in one place, with the module that owns
each one named beside it. A term nobody can point at a definition for is a
term two people are using differently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from dipcount.errors import NotFound


@dataclass(frozen=True)
class Term:
    """One word and what the district means by it."""

    word: str
    owner: str
    meaning: str

    @property
    def area(self) -> str:
        """Which part of the package owns the definition."""
        return self.owner.split(".")[1] if "." in self.owner else self.owner


TERMS: Final[tuple[Term, ...]] = (
    Term(
        "reporting week",
        "dipcount.clock",
        "Sunday to Saturday, numbered so that week one holds four or more days"
        " of January. Everything the state adds up is keyed on it.",
    ),
    Term(
        "site",
        "dipcount.model.site",
        "A piece of water on the inspection list. Measured in acres or in"
        " structures depending on its habitat, and never in both.",
    ),
    Term(
        "habitat",
        "dipcount.habitat",
        "What kind of water a site is. It decides how the site is measured,"
        " how often it is looked at, and what may legally go into it.",
    ),
    Term(
        "dip",
        "dipcount.model.inspection",
        "One stroke of the dipper. The count of larvae over the count of dips"
        " is the figure the larval threshold is written in.",
    ),
    Term(
        "instar",
        "dipcount.model.inspection",
        "One of the four larval stages. First and second mean the treatment"
        " window is open; third and fourth mean it is closing.",
    ),
    Term(
        "pupa",
        "dipcount.model.inspection",
        "The stage after the fourth instar. It does not feed, so no larvicide"
        " reaches it, and a brood that is mostly pupae is past treating.",
    ),
    Term(
        "trap night",
        "dipcount.model.trap",
        "One trap out for one night. The denominator of every adult index,"
        " and it excludes any trap that did not run.",
    ),
    Term(
        "index",
        "dipcount.service.trapping",
        "Females per trap night. Males are counted and left out of it,"
        " because a male mosquito neither bites nor carries anything.",
    ),
    Term(
        "pool",
        "dipcount.model.pool",
        "Up to fifty females of one species out of one jar, tested together."
        " A positive pool says at least one was carrying, not how many.",
    ),
    Term(
        "infection rate",
        "dipcount.estimate",
        "An estimate, not a count, because pools are tested rather than"
        " mosquitoes. Quoted per thousand.",
    ),
    Term(
        "vector index",
        "dipcount.estimate",
        "Abundance times infection rate: how many infected females a trap"
        " would take in a night. The response ladder reads this.",
    ),
    Term(
        "response level",
        "dipcount.rules",
        "Where the vector index puts the district, from none to emergency."
        " It shortens two of the service request clocks.",
    ),
    Term(
        "label",
        "dipcount.model.product",
        "What the product may be applied to, at what rate range, how often,"
        " and how much one place may take in a season. Federal law.",
    ),
    Term(
        "season cap",
        "dipcount.service.larvicide",
        "The most one acre or one structure may receive in a year. What is"
        " left of it limits the rate, and can leave no legal rate at all.",
    ),
    Term(
        "lot",
        "dipcount.model.lot",
        "One batch of one product as it arrived, under one manufacturer code."
        " Everything applied comes out of a lot, so a recall can be answered.",
    ),
    Term(
        "block",
        "dipcount.model.block",
        "The ground a fogging truck covers in one pass of a street grid."
        " Measured in acres for the rate and in road miles for the driving.",
    ),
    Term(
        "register",
        "dipcount.model.exclusion",
        "The places the district does not spray over. Some want notice and"
        " some take the block off the run whatever anybody was told.",
    ),
    Term(
        "notice",
        "dipcount.model.block",
        "One place told about one block for one window, far enough ahead for"
        " the kind of entry it is.",
    ),
    Term(
        "calibration",
        "dipcount.model.equipment",
        "Flow, droplet size and swath measured together. With the driving"
        " speed they say what actually went on the ground.",
    ),
    Term(
        "diagnostic time",
        "dipcount.model.bioassay",
        "The minute a susceptible population is flat by. What is still"
        " standing then is the resistance finding.",
    ),
    Term(
        "mode of action",
        "dipcount.rules",
        "The group an active ingredient belongs to. Rotation is over these"
        " and not over brand names.",
    ),
    Term(
        "answer time",
        "dipcount.model.request",
        "How long the district has to get out to a call. It comes off the"
        " kind of call, and a busy virus week shortens two of them.",
    ),
)

BY_WORD: Final[dict[str, Term]] = {one.word: one for one in TERMS}


def term(word: str) -> Term:
    """One term by word."""
    try:
        return BY_WORD[word.lower()]
    except KeyError as exc:
        raise NotFound("term", word) from exc


def words() -> list[str]:
    """Every term, in alphabetical order."""
    return sorted(BY_WORD)


def owners() -> list[str]:
    """Every module that owns a definition."""
    return sorted({one.owner for one in TERMS})


def in_area(area: str) -> list[Term]:
    """Every term owned by one part of the package."""
    return [one for one in TERMS if one.area == area]


def as_lines() -> list[str]:
    """The glossary as one line per term, for a generated document."""
    return [f"**{one.word}** ({one.owner})  {one.meaning}" for one in TERMS]
