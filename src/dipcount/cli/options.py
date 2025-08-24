"""Shared options, argument readers and the printing helpers."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import click

from dipcount import clock
from dipcount.errors import UsageError
from dipcount.store import Book, require_ready
from dipcount.units import Quantity

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class Desk:
    """What every command needs: which book, and who is asking."""

    path: Path
    actor: str
    zone_name: str = clock.DEFAULT_ZONE

    def open(self) -> Book:
        """Open the book and refuse it if it is not migrated."""
        opened = Book(self.path)
        try:
            require_ready(opened)
        except BaseException:
            opened.close()
            raise
        return opened

    def create(self) -> Book:
        """Open the book, making the file if it is not there."""
        return Book.create(self.path)

    @contextmanager
    def book(self) -> Iterator[Book]:
        """The migrated book, closed however the command ends.

        Every command used to open the book, wrap its work in a try, and
        close in a finally. Four of them got the finally wrong at some point,
        which on 3.13 shows up as a ResourceWarning against whichever command
        the test runner reached next rather than against the one that leaked.
        """
        opened = self.open()
        try:
            yield opened
        finally:
            opened.close()

    @contextmanager
    def new_book(self) -> Iterator[Book]:
        """The book, made if it is not there, closed however this ends."""
        opened = self.create()
        try:
            yield opened
        finally:
            opened.close()


pass_desk = click.make_pass_decorator(Desk)


def read_day(text: str) -> dt.date:
    """A ``YYYY-MM-DD`` argument."""
    return clock.day(text)


def read_moment(text: str, zone: str = clock.DEFAULT_ZONE) -> dt.datetime:
    """A ``YYYY-MM-DD HH:MM`` argument in the district's zone."""
    return clock.moment(text, zone)


def read_quantity(text: str) -> Quantity:
    """An amount and a unit, such as ``6.5 acre``."""
    return Quantity.parse(text)


def today_option(help_text: str = "The day this happened.") -> Callable[[F], F]:
    """A ``--on`` option defaulting to today in the district's zone."""

    def decorate(command: F) -> F:
        return click.option(
            "--on",
            "on_text",
            default=None,
            metavar="YYYY-MM-DD",
            help=help_text,
        )(command)

    return decorate


def day_or_today(text: str | None, zone: str = clock.DEFAULT_ZONE) -> dt.date:
    """Read a ``--on`` value, or take today in the district's zone."""
    if text is None:
        return clock.now(zone).date()
    return clock.day(text)


def moment_or_now(text: str | None, zone: str = clock.DEFAULT_ZONE) -> dt.datetime:
    """Read an ``--at`` value, or take the current moment."""
    if text is None:
        return clock.now(zone)
    return clock.moment(text, zone)


def echo_pairs(pairs: list[tuple[str, str]]) -> None:
    """Print a record as aligned label and value lines."""
    if not pairs:
        return
    width = max(len(label) for label, _ in pairs)
    for label, value in pairs:
        click.echo(f"{label.rjust(width)}  {value}")


def echo_rows(headings: list[str], rows: list[list[str]]) -> None:
    """Print a table with the columns lined up under their headings."""
    widths = [len(head) for head in headings]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    click.echo("  ".join(head.ljust(widths[index]) for index, head in enumerate(headings)))
    click.echo("  ".join("-" * width for width in widths))
    for row in rows:
        click.echo("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))
    click.echo(f"\n{len(rows)} row{'' if len(rows) == 1 else 's'}")


def one_of(name: str, value: str, allowed: list[str]) -> str:
    """Refuse a value that is not in a fixed list, naming what is."""
    if value not in allowed:
        raise UsageError(f"{value} is not a {name}: try {', '.join(allowed)}")
    return value
