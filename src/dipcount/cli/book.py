"""Commands about the book itself."""

from __future__ import annotations

from contextlib import closing

import click

from dipcount.cli.options import Desk, echo_pairs, echo_rows, pass_desk
from dipcount.store import Book, latest, upgrade
from dipcount.store.migrate import pending


@click.group()
def book() -> None:
    """Make a book, look at it, and check it over."""


@book.command("init")
@pass_desk
def init(desk: Desk) -> None:
    """Make the book if it is not there, and bring it up to date."""
    with desk.new_book() as opened:
        ran = upgrade(opened)
        if ran:
            for step in ran:
                click.echo(f"ran {step.number:03d} {step.name}")
        else:
            click.echo("already up to date")
        click.echo(f"{desk.path} is at schema {opened.version}")


@book.command("counts")
@pass_desk
def counts(desk: Desk) -> None:
    """How many rows each table holds."""
    with desk.book() as opened:
        rows = [[name, str(opened.count(name))] for name in opened.tables()]
    echo_rows(["table", "rows"], rows)


@book.command("check")
@pass_desk
def check(desk: Desk) -> None:
    """Say whether the book is sound and up to date."""
    with closing(Book(desk.path)) as opened:
        waiting = pending(opened)
        echo_pairs(
            [
                ("book", str(desk.path)),
                ("schema", f"{opened.version} of {latest()}"),
                ("pending", str(len(waiting))),
                ("integrity", opened.integrity()),
                ("tables", str(len(opened.tables()))),
            ],
        )
