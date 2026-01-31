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
from dipcount.report import sheet
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
        """Put the option on one command."""
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


def echo_pairs(entries: list[tuple[str, str]]) -> None:
    """Print a record as aligned label and value lines."""
    if entries:
        click.echo(sheet.pairs(entries))


def echo_rows(headings: list[str], rows: list[list[str]], *, title: str = "") -> None:
    """Print a table with the columns lined up under their headings."""
    click.echo(sheet.table(headings, rows, title=title).render())


def echo_sheet(made: sheet.Sheet) -> None:
    """Print a sheet a report has already built."""
    click.echo(made.render())


def one_of(name: str, value: str, allowed: list[str]) -> str:
    """Refuse a value that is not in a fixed list, naming what is."""
    if value not in allowed:
        raise UsageError(f"{value} is not a {name}: try {', '.join(allowed)}")
    return value
