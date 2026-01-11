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
from dipcount.errors import LabelViolation, NotFound, RuleViolation


@dataclass(frozen=True)
class Refusal:
    """One named reason something may not be done.

    A refusal is a value rather than an exception, because most of the time
    the caller wants to gather every reason and show them together. When one
    does have to be raised, the clause decides the type: anything under
    ``label`` is federal law and gets its own class so nothing catches it by
    accident along with the ordinary refusals.
    """

    rule: str
    detail: str

    @property
    def clause(self) -> Clause:
        """The rule book entry this refusal names."""
        return clause(self.rule)

    def raise_it(self) -> None:
        """Raise this refusal as the error type its clause calls for."""
        if self.rule.startswith("label."):
            raise LabelViolation(self.rule, self.detail)
        raise RuleViolation(self.rule, self.detail)

    def line(self) -> str:
        """One line naming the clause and what it said."""
        return f"[{self.rule}] {self.detail}"


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
        "adult.threshold",
        "a trap kind has its own figure",
        "Each kind of trap has an action figure in females per trap night. A"
        " light trap catches everything that flies and a gravid trap catches"
        " the few that have already fed, so the two figures are not comparable"
        " and neither is a total taken across both.",
    ),
    Clause(
        "adult.broken",
        "a trap that did not run is not a night of nothing",
        "A collection off a trap that was knocked over, or whose battery was"
        " flat, is left out of both halves of the index. Counting it as a"
        " night of zero drags the figure down for the whole week.",
    ),
    Clause(
        "adult.baseline",
        "twice the usual is the thing worth reporting",
        "A week is elevated when its index is at least twice the mean of the"
        " same week in the seasons before it. A district with three seasons"
        " behind it has a baseline; one without has a figure and no baseline,"
        " and the difference is reported rather than hidden.",
    ),
    Clause(
        "virus.vector",
        "only what carries the virus is in the rate for it",
        "A pool is tested whatever species it holds, and the result is kept."
        " The infection rate for a virus is estimated over the pools of"
        " species that carry it, because a negative pool of something that"
        " could never have been positive says nothing about the rate.",
    ),
    Clause(
        "virus.pools",
        "an unreadable pool is neither positive nor negative",
        "A pool the laboratory reported as unsatisfactory is left out of both"
        " halves of the rate, and one still out at the laboratory has not"
        " happened yet.",
    ),
    Clause(
        "virus.week",
        "a pool belongs to the week it was caught in",
        "Results are reported against the reporting week the jar was pulled"
        " in, not the week the vial reached the laboratory. Two districts"
        " with different courier days have to be addable.",
    ),
    Clause(
        "virus.ladder",
        "the vector index is what the response level reads",
        "Abundance on its own and infection rate on its own each say half of"
        " it. The product is how many infected females a trap takes in a"
        " night, and the response level is read off that.",
    ),
    Clause(
        "weather.method",
        "a season is accumulated one way from end to end",
        "Degree days are counted by one method for the whole season. A total"
        " built one way cannot be compared with a total built another, and"
        " changing method part way through produces neither.",
    ),
    Clause(
        "weather.gap",
        "a missing day is not a day with no heat in it",
        "An accumulation over a window with missing readings is reported with"
        " the gaps named. Treating a gap as zero runs the total low for the"
        " rest of the season.",
    ),
    Clause(
        "weather.flood",
        "half an inch is a brood",
        "Rain of half an inch or more over a day puts every floodwater site"
        " in the zone on the round, ahead of its ordinary interval.",
    ),
    Clause(
        "label.site",
        "a product goes where its label says and nowhere else",
        "The label names the kinds of water the product may be put into. A"
        " site whose habitat is not on the label cannot be treated with it at"
        " any rate.",
    ),
    Clause(
        "label.rate",
        "the rate is inside the range, both ends",
        "Under the bottom of the range is a treatment that will not work and"
        " over the top is an offence. Neither is a judgement call.",
    ),
    Clause(
        "label.season",
        "a season cap is a cap on the place, not on the visit",
        "The label limits what one acre or one structure may receive in a"
        " season. What is left of that cap after earlier treatments limits"
        " this one, and a cap that leaves less than the bottom of the rate"
        " range leaves no legal treatment at all rather than a smaller one.",
    ),
    Clause(
        "label.interval",
        "applications are spaced the way the label spaces them",
        "The days between two applications of one product at one place are the"
        " label's to set. A site treated inside the interval waits, whatever"
        " the dipper found.",
    ),
    Clause(
        "label.shelf",
        "a product off the shelf cannot be applied",
        "A product withdrawn before the day of the application is not"
        " available for it, whatever is still in the shed.",
    ),
    Clause(
        "label.form",
        "a formulation goes into water that takes it",
        "A rate cannot be written, and an application cannot be made, for a"
        " formulation the habitat does not take.",
    ),
    Clause(
        "treat.extent",
        "nothing is treated over more ground than it has",
        "The extent treated is measured in the habitat's unit and cannot"
        " exceed what the site was measured at.",
    ),
    Clause(
        "stock.short",
        "the shelf is the limit",
        "A draw larger than what is left of a lot is a counting mistake, and"
        " letting it through turns one mistake into a stock figure nobody can"
        " reconcile.",
    ),
    Clause(
        "stock.expired",
        "an out of date lot is not stock",
        "A lot past its date may be disposed of and may not be applied.",
    ),
    Clause(
        "stock.unit",
        "a lot is drawn in the unit it was received in",
        "A draw in another dimension is not a smaller draw, it is a different substance.",
    ),
    Clause(
        "stock.product",
        "a lot belongs to one product",
        "A treatment names a lot, and the product is read off the lot rather"
        " than typed in beside it.",
    ),
    Clause(
        "spray.wind",
        "the wind has to be inside a band, not under a ceiling",
        "Over the top of the band the fog drifts off the block. Under the"
        " bottom of it there is nothing to carry the droplets and an"
        " inversion holds them where they were released. Still air is a"
        " refusal, not a perfect night.",
    ),
    Clause(
        "spray.temperature",
        "cold air does not carry a fog",
        "Below the floor the droplets fall out of the air and the mosquitoes"
        " are not flying to meet them anyway.",
    ),
    Clause(
        "spray.hours",
        "the truck runs at night",
        "Ground ultra low volume goes out when the target species are flying"
        " and the pollinators are not, which is after dusk and before the"
        " early hours.",
    ),
    Clause(
        "spray.notice",
        "everybody on the register inside the block is told first",
        "Notice is given for a place and a block together, covering a window"
        " the run falls inside, far enough ahead for the kind of entry. A"
        " notice for the neighbouring block is not notice.",
    ),
    Clause(
        "spray.absolute",
        "some entries take the block off the run",
        "An entry that no amount of notice gets round is not a delay. The"
        " block does not run, tonight or any night, until the entry comes"
        " off the register.",
    ),
    Clause(
        "spray.block",
        "a block comes off the run list once",
        "A retired block is not retired again, and it cannot be retired"
        " before the day it was listed.",
    ),
    Clause(
        "spray.register",
        "a register entry comes off once",
        "An entry is removed from the register once, and not before the day it went on.",
    ),
    Clause(
        "spray.acres",
        "a run covers no more than the block holds",
        "Part of a block may be run. More than the block is a measuring"
        " mistake and the rate that comes out of it is wrong in the"
        " comfortable direction.",
    ),
    Clause(
        "equipment.calibration",
        "a machine works to its last calibration",
        "A calibration stands for thirty days. Past that the machine has not"
        " been shown to do anything, and what went on the ground is a guess"
        " written down as a figure.",
    ),
    Clause(
        "equipment.flow",
        "the flow has to be near what the machine is rated at",
        "Ten percent either way. Outside that the nozzle is worn or blocked,"
        " and the rate the paperwork claims is not the rate applied.",
    ),
    Clause(
        "equipment.droplet",
        "an ultra low volume machine has to make small droplets",
        "Over the ceiling the cloud falls out of the air. The mosquitoes never"
        " meet it and what has happened is a pesticide application to"
        " somebody's lawn.",
    ),
    Clause(
        "equipment.retired",
        "a machine out of service applies nothing",
        "A retired machine takes no calibration and makes no run.",
    ),
    Clause(
        "request.clock",
        "the clock starts when the phone is put down",
        "The answer time runs from when the call was taken, not from when"
        " somebody got round to reading it, and a call answered late stays"
        " late however long afterwards it is closed.",
    ),
    Clause(
        "request.escalation",
        "a busy virus week shortens two of the clocks",
        "When the response level is high or above, dead bird and spray"
        " concern calls are answered in half the usual time. The other kinds"
        " do not move, because finding water does not get faster.",
    ),
    Clause(
        "request.visited",
        "a call is visited once",
        "The visit is the answer. A second visit is a second call.",
    ),
    Clause(
        "request.closed",
        "a closed call takes no more work",
        "Nothing is assigned to it, visited on it or closed again.",
    ),
    Clause(
        "resistance.species",
        "a finding is about the species it was run on",
        "Resistance in a catch basin Culex says nothing about a floodplain"
        " producing Aedes. A finding only bears on a site whose habitat"
        " produces the species the bottles held.",
    ),
    Clause(
        "resistance.stale",
        "a finding has a shelf life",
        "Two seasons on, a bottle assay is history rather than evidence. It"
        " is still reported, and it is reported as old.",
    ),
    Clause(
        "resistance.rotation",
        "modes of action are rotated, not products",
        "Two products with different names and the same mode of action are"
        " one product as far as resistance is concerned. Three applications"
        " running in one mode at one site is a rotation that is not"
        " happening.",
    ),
    Clause(
        "licence.date",
        "an expired licence makes no applications",
        "The licence has a date and after it the holder applies nothing, of any kind, at any rate.",
    ),
    Clause(
        "licence.category",
        "the category has to cover the work",
        "Permanent water needs an aquatic category and everything else in this"
        " programme needs public health. A licence in another category is a"
        " licence for other work.",
    ),
    Clause(
        "licence.grade",
        "a restricted use product needs a certified applicator",
        "A technician may apply anything not restricted, working under a"
        " certified applicator. A trainee applies nothing alone.",
    ),
    Clause(
        "licence.credits",
        "credits are for renewal, not for working today",
        "Somebody short of credit hours in October is still licensed and still"
        " working. They will not be renewed. Reporting them as unlicensed is"
        " wrong and reporting them as fine is worse.",
    ),
    Clause(
        "licence.supervision",
        "only a certified applicator supervises",
        "A technician cannot be somebody else's supervisor, whatever the"
        " staffing that week looks like.",
    ),
    Clause(
        "licence.renewal",
        "a renewal runs forward",
        "A new certification period ends after the one it replaces.",
    ),
    Clause(
        "licence.left",
        "somebody leaves once",
        "A leaving date is written once and not written again.",
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

WIND_LOW: Final = Decimal("1")
"""Miles an hour below which there is nothing to carry the fog."""

WIND_HIGH: Final = Decimal("10")
"""Miles an hour above which the fog leaves the block."""

TEMP_FLOOR: Final = Decimal("50")
"""Fahrenheit below which a ground fog is not worth making."""

NIGHT_FROM: Final = 20
"""The earliest hour, local, a run may start."""

NIGHT_TO: Final = 2
"""The hour, local, by which a run has finished."""

FLOOD_INCHES: Final = Decimal("0.5")
"""Rain over one day that puts the floodwater sites back on the round."""

FLOOD_INTERVAL: Final = 4
"""Days after a triggering rain that the floodwater brood is worth dipping."""

_DEVELOPMENT: Final[dict[str, str]] = {
    species.FLOODWATER: "110",
    species.PERMANENT: "145",
    species.WOODLAND: "125",
    species.CONTAINER: "165",
}


_ADULT: Final[dict[str, str]] = {
    "light": "50",
    "gravid": "10",
    "bg": "5",
    "resting": "5",
}

ESCALATED_LEVELS: Final[tuple[str, ...]] = ("high", "emergency")
"""Response levels that shorten the fast call clocks."""

ELEVATED: Final = Decimal("2")
"""How many times the baseline a week has to reach to be called elevated."""

BASELINE_SEASONS: Final = 3
"""How many earlier seasons a baseline is taken over."""


def adult_threshold(kind: str) -> Decimal:
    """The females per trap night a kind of trap is worth acting on."""
    try:
        return Decimal(_ADULT[kind])
    except KeyError as exc:
        raise NotFound("trap kind", kind) from exc


def adult_thresholds() -> dict[str, Decimal]:
    """Every trap kind's figure, for a report or a check."""
    return {key: Decimal(value) for key, value in _ADULT.items()}


_LADDER: Final[tuple[tuple[str, str], ...]] = (
    ("none", "0"),
    ("low", "0.05"),
    ("moderate", "0.25"),
    ("high", "0.75"),
    ("emergency", "1.5"),
)


def response_level(vector_index: Decimal) -> str:
    """The response level a vector index puts the district on."""
    if vector_index < 0:
        raise NotFound("response level", str(vector_index))
    level = _LADDER[0][0]
    for name, floor in _LADDER:
        if vector_index >= Decimal(floor):
            level = name
    return level


def ladder() -> list[tuple[str, Decimal]]:
    """The response ladder, lowest first."""
    return [(name, Decimal(floor)) for name, floor in _LADDER]


_MODES: Final[dict[str, str]] = {
    "Bacillus thuringiensis subspecies israelensis": "bacterial toxin",
    "Bacillus sphaericus": "bacterial toxin",
    "S-methoprene": "growth regulator",
    "spinosad": "spinosyn",
    "mineral oil": "surface film",
    "isostearyl alcohol ethoxylate": "surface film",
    "permethrin": "pyrethroid",
    "sumithrin": "pyrethroid",
    "deltamethrin": "pyrethroid",
    "malathion": "organophosphate",
    "naled": "organophosphate",
}

STALE_DAYS: Final = 730
"""How long a bottle assay stands as evidence rather than as history."""

ROTATION_RUN: Final = 3
"""Applications in one mode of action at one site before the rotation fails."""


def mode_of(active: str) -> str:
    """Which mode of action an active ingredient belongs to."""
    try:
        return _MODES[active]
    except KeyError as exc:
        raise NotFound("mode of action", active) from exc


def modes() -> list[str]:
    """Every mode of action the district works with."""
    return sorted(set(_MODES.values()))


def actives_in(mode: str) -> list[str]:
    """Every active ingredient in one mode of action."""
    return sorted(name for name, group in _MODES.items() if group == mode)


def development(guild: str) -> Decimal:
    """Heat units from egg to adult for a guild, base fifty."""
    try:
        return Decimal(_DEVELOPMENT[guild])
    except KeyError as exc:
        raise NotFound("guild", guild) from exc


def guilds() -> list[str]:
    """Every guild the development table covers."""
    return sorted(_DEVELOPMENT)


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
