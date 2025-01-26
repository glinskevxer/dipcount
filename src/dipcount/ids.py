"""The identifiers the district writes on paper.

Two shapes, and the shape says something about the record. A thing that sits
still and keeps its number for years gets a plain serial: ``SI-0042`` is site
forty two and will be site forty two next season. A thing that happens on a
day gets the day in the middle: ``DP-250604-03`` is the third dip round of the
fourth of June. Field crews read these off tags and write them on cards, so
they are short, they are upper case, and the letters are never ambiguous with
the digits beside them.

Nothing here reaches a database. The store hands in what it already holds and
gets back the next free number, which keeps minting testable and keeps the
uniqueness rule in one place instead of in every table.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Final

from dipcount.errors import UsageError

SERIAL: Final = "serial"
DATED: Final = "dated"


@dataclass(frozen=True)
class Kind:
    """One kind of record, its prefix and the shape of its numbers."""

    name: str
    prefix: str
    style: str
    width: int = 4

    def pattern(self) -> re.Pattern[str]:
        """The regular expression an id of this kind has to match."""
        if self.style == SERIAL:
            return re.compile(rf"^{self.prefix}-\d{{{self.width}}}$")
        return re.compile(rf"^{self.prefix}-\d{{6}}-\d{{2}}$")


KINDS: Final[dict[str, Kind]] = {
    kind.name: kind
    for kind in (
        Kind("site", "SI", SERIAL),
        Kind("zone", "ZN", SERIAL, width=3),
        Kind("trap", "TR", SERIAL),
        Kind("station", "ST", SERIAL),
        Kind("block", "BK", SERIAL),
        Kind("product", "PD", SERIAL),
        Kind("lot", "LT", SERIAL),
        Kind("applicator", "AP", SERIAL, width=3),
        Kind("equipment", "EQ", SERIAL, width=3),
        Kind("request", "SR", SERIAL),
        Kind("notice", "NT", SERIAL),
        Kind("dip", "DP", DATED),
        Kind("collection", "CO", DATED),
        Kind("pool", "PL", DATED),
        Kind("treatment", "TX", DATED),
        Kind("run", "RN", DATED),
        Kind("bioassay", "BA", DATED),
        Kind("inspection", "IN", DATED),
        Kind("observation", "WX", DATED),
    )
}


def kind_of(name: str) -> Kind:
    """The record kind by name, refused if this package does not mint it."""
    try:
        return KINDS[name]
    except KeyError as exc:
        raise UsageError(f"{name} is not a kind of record this district numbers") from exc


def looks_like(name: str, text: str) -> bool:
    """Whether ``text`` is shaped like an id of this kind."""
    return bool(kind_of(name).pattern().match(text))


def require(name: str, text: str) -> str:
    """Return ``text`` if it is an id of this kind, and refuse it if not."""
    if not looks_like(name, text):
        raise UsageError(f"{text} is not a {name} id")
    return text


def kind_from(text: str) -> str:
    """Which kind an id belongs to, read off the prefix and the shape."""
    for name in KINDS:
        if looks_like(name, text):
            return name
    raise UsageError(f"{text} is not an id this district issues")


def _serial_of(kind: Kind, text: str) -> int | None:
    match = kind.pattern().match(text)
    if match is None:
        return None
    return int(text.rsplit("-", 1)[1])


def next_serial(name: str, taken: list[str]) -> str:
    """The next free serial id of this kind, given the ones already issued."""
    kind = kind_of(name)
    if kind.style != SERIAL:
        raise UsageError(f"{name} ids carry a date, so they are not minted by serial alone")
    highest = 0
    for text in taken:
        found = _serial_of(kind, text)
        if found is not None and found > highest:
            highest = found
    number = highest + 1
    if number >= 10**kind.width:
        raise UsageError(f"the {name} numbers are used up at {highest}")
    return f"{kind.prefix}-{number:0{kind.width}d}"


def next_dated(name: str, on: dt.date, taken: list[str]) -> str:
    """The next free dated id for a day, given the ones already issued."""
    kind = kind_of(name)
    if kind.style != DATED:
        raise UsageError(f"{name} ids do not carry a date")
    stem = f"{kind.prefix}-{on:%y%m%d}"
    highest = 0
    for text in taken:
        if text.startswith(f"{stem}-") and kind.pattern().match(text):
            found = int(text.rsplit("-", 1)[1])
            highest = max(highest, found)
    number = highest + 1
    if number > 99:
        raise UsageError(f"a hundred {name} records on {on.isoformat()} is more than the day holds")
    return f"{stem}-{number:02d}"


def day_of(text: str) -> dt.date:
    """The day a dated id was issued for."""
    name = kind_from(text)
    if kind_of(name).style != DATED:
        raise UsageError(f"{text} does not carry a date")
    stamp = text.split("-")[1]
    return dt.date(2000 + int(stamp[0:2]), int(stamp[2:4]), int(stamp[4:6]))


def sort_key(text: str) -> tuple[str, str, int]:
    """A sort key that puts ids of a kind in the order they were issued."""
    name = kind_from(text)
    parts = text.split("-")
    if kind_of(name).style == SERIAL:
        return (parts[0], "", int(parts[1]))
    return (parts[0], parts[1], int(parts[2]))
