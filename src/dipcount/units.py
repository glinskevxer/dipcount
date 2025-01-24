"""Quantities, and the rates a pesticide label is written in.

A label says eight fluid ounces per acre, or one briquet per catch basin, or
five parts per million in standing water, and a treatment record has to be
able to say what was actually applied in the same terms. So the amount and its
unit travel together and the arithmetic happens here rather than in whichever
service happened to need it.

The one rule worth stating out loud: ``oz`` is a unit of mass here and a fluid
ounce has to be written ``fl oz``. Labels are written both ways and reading
one as the other is off by a factor of nothing in particular. Nothing in this
package guesses which was meant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final

from dipcount.errors import UsageError

VOLUME: Final = "volume"
MASS: Final = "mass"
AREA: Final = "area"
LENGTH: Final = "length"
COUNT: Final = "count"

_BASE: Final[dict[str, str]] = {
    VOLUME: "mL",
    MASS: "g",
    AREA: "m2",
    LENGTH: "m",
    COUNT: "each",
}

_FACTORS: Final[dict[str, tuple[str, Decimal]]] = {
    "mL": (VOLUME, Decimal("1")),
    "L": (VOLUME, Decimal("1000")),
    "fl oz": (VOLUME, Decimal("29.5735295625")),
    "pt": (VOLUME, Decimal("473.176473")),
    "qt": (VOLUME, Decimal("946.352946")),
    "gal": (VOLUME, Decimal("3785.411784")),
    "tsp": (VOLUME, Decimal("4.92892159375")),
    "tbsp": (VOLUME, Decimal("14.78676478125")),
    "mg": (MASS, Decimal("0.001")),
    "g": (MASS, Decimal("1")),
    "kg": (MASS, Decimal("1000")),
    "oz": (MASS, Decimal("28.349523125")),
    "lb": (MASS, Decimal("453.59237")),
    "m2": (AREA, Decimal("1")),
    "ft2": (AREA, Decimal("0.09290304")),
    "acre": (AREA, Decimal("4046.8564224")),
    "ha": (AREA, Decimal("10000")),
    "mi2": (AREA, Decimal("2589988.110336")),
    "um": (LENGTH, Decimal("0.000001")),
    "mm": (LENGTH, Decimal("0.001")),
    "cm": (LENGTH, Decimal("0.01")),
    "m": (LENGTH, Decimal("1")),
    "in": (LENGTH, Decimal("0.0254")),
    "ft": (LENGTH, Decimal("0.3048")),
    "mi": (LENGTH, Decimal("1609.344")),
    "each": (COUNT, Decimal("1")),
}

_ALIASES: Final[dict[str, str]] = {
    "ml": "mL",
    "milliliter": "mL",
    "millilitre": "mL",
    "liter": "L",
    "litre": "L",
    "l": "L",
    "fluid ounce": "fl oz",
    "floz": "fl oz",
    "fl. oz.": "fl oz",
    "pint": "pt",
    "quart": "qt",
    "gallon": "gal",
    "gallons": "gal",
    "teaspoon": "tsp",
    "tablespoon": "tbsp",
    "gram": "g",
    "grams": "g",
    "kilogram": "kg",
    "milligram": "mg",
    "ounce": "oz",
    "ounces": "oz",
    "pound": "lb",
    "pounds": "lb",
    "lbs": "lb",
    "acres": "acre",
    "ac": "acre",
    "hectare": "ha",
    "sq ft": "ft2",
    "square feet": "ft2",
    "sq m": "m2",
    "sq mi": "mi2",
    "micron": "um",
    "microns": "um",
    "inch": "in",
    "inches": "in",
    "feet": "ft",
    "foot": "ft",
    "mile": "mi",
    "count": "each",
    "ea": "each",
    "basin": "each",
    "catch basin": "each",
    "structure": "each",
    "briquet": "each",
    "unit": "each",
    "units": "each",
}

_SPLIT = re.compile(r"^\s*(-?[0-9]*\.?[0-9]+)\s*(.*?)\s*$")


def canonical(unit: str) -> str:
    """The spelling of a unit this package stores it under."""
    text = unit.strip()
    if text in _FACTORS:
        return text
    folded = _ALIASES.get(text.lower())
    if folded is not None:
        return folded
    if text.lower() in _FACTORS:
        return text.lower()
    raise UsageError(f"{unit} is not a unit this district measures in")


def dimension_of(unit: str) -> str:
    """Which dimension a unit belongs to."""
    return _FACTORS[canonical(unit)][0]


def units_in(dimension: str) -> list[str]:
    """Every unit of a dimension, for a help message or a check."""
    return sorted(name for name, (dim, _) in _FACTORS.items() if dim == dimension)


@dataclass(frozen=True, order=False)
class Quantity:
    """An amount and the unit it was measured in."""

    amount: Decimal
    unit: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "unit", canonical(self.unit))

    @property
    def dimension(self) -> str:
        """The dimension this quantity measures."""
        return _FACTORS[self.unit][0]

    @classmethod
    def parse(cls, text: str) -> Quantity:
        """Read ``8 fl oz`` or ``2.5 acre`` into a quantity."""
        match = _SPLIT.match(text)
        if match is None:
            raise UsageError(f"{text!r} is not an amount with a unit")
        number, unit = match.group(1), match.group(2)
        if not unit:
            raise UsageError(f"{text!r} has no unit, and an amount without one is not a quantity")
        try:
            return cls(Decimal(number), unit)
        except InvalidOperation as exc:
            raise UsageError(f"{number!r} is not a number") from exc

    def base(self) -> Decimal:
        """This quantity in the base unit of its dimension."""
        return self.amount * _FACTORS[self.unit][1]

    def to(self, unit: str) -> Quantity:
        """The same quantity expressed in another unit of the same dimension."""
        want = canonical(unit)
        dim, factor = _FACTORS[want]
        if dim != self.dimension:
            raise UsageError(f"{self.unit} is {self.dimension} and {want} is {dim}")
        return Quantity(self.base() / factor, want)

    def __add__(self, other: Quantity) -> Quantity:
        return Quantity(self.amount + other.to(self.unit).amount, self.unit)

    def __sub__(self, other: Quantity) -> Quantity:
        return Quantity(self.amount - other.to(self.unit).amount, self.unit)

    def __mul__(self, factor: Decimal | int) -> Quantity:
        return Quantity(self.amount * Decimal(str(factor)), self.unit)

    def __truediv__(self, divisor: Decimal | int) -> Quantity:
        divisor = Decimal(str(divisor))
        if divisor == 0:
            raise UsageError("a quantity cannot be divided by nothing")
        return Quantity(self.amount / divisor, self.unit)

    def ratio(self, other: Quantity) -> Decimal:
        """How many of ``other`` fit in this quantity, as a plain number."""
        if other.dimension != self.dimension:
            raise UsageError(f"{self.dimension} does not divide by {other.dimension}")
        if other.base() == 0:
            raise UsageError("a quantity cannot be divided by nothing")
        return self.base() / other.base()

    def __lt__(self, other: Quantity) -> bool:
        return self.base() < other.to(self.unit).base()

    def __le__(self, other: Quantity) -> bool:
        return self.base() <= other.to(self.unit).base()

    def __gt__(self, other: Quantity) -> bool:
        return other < self

    def __ge__(self, other: Quantity) -> bool:
        return other <= self

    def rounded(self, places: int = 3) -> Quantity:
        """The same quantity with the amount rounded for printing."""
        return Quantity(round(self.amount, places), self.unit)

    def __str__(self) -> str:
        amount = self.amount.normalize()
        text = format(amount, "f")
        return f"{text} {self.unit}"


def quantity(text: str) -> Quantity:
    """Shorthand for :meth:`Quantity.parse`."""
    return Quantity.parse(text)


@dataclass(frozen=True)
class Rate:
    """An amount of product for each of something: per acre, per basin."""

    amount: Quantity
    per: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "per", canonical(self.per))

    @property
    def per_dimension(self) -> str:
        """The dimension of the thing the rate is written against."""
        return _FACTORS[self.per][0]

    @classmethod
    def parse(cls, text: str) -> Rate:
        """Read ``8 fl oz/acre`` or ``1 each per basin`` into a rate."""
        body = text.replace(" per ", "/")
        head, sep, tail = body.partition("/")
        if not sep or not tail.strip():
            raise UsageError(f"{text!r} is not a rate: an amount, a slash, and a unit")
        return cls(Quantity.parse(head), tail.strip())

    def over(self, extent: Quantity) -> Quantity:
        """What this rate comes to over an extent of ground or of anything."""
        if extent.dimension != self.per_dimension:
            raise UsageError(
                f"a rate per {self.per} cannot be applied to {extent.dimension}",
            )
        return self.amount * extent.to(self.per).amount

    def to(self, unit: str, per: str | None = None) -> Rate:
        """The same rate written in other units."""
        want_per = canonical(per) if per is not None else self.per
        moved = self.amount.to(unit)
        if want_per != self.per:
            scale = Quantity(Decimal(1), want_per).ratio(Quantity(Decimal(1), self.per))
            moved = moved * scale
        return Rate(moved, want_per)

    def __str__(self) -> str:
        return f"{self.amount}/{self.per}"


def rate(text: str) -> Rate:
    """Shorthand for :meth:`Rate.parse`."""
    return Rate.parse(text)
