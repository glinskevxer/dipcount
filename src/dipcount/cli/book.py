"""Commands about the book itself."""

from __future__ import annotations

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
    opened = desk.create()
    try:
        ran = upgrade(opened)
        if ran:
            for step in ran:
                click.echo(f"ran {step.number:03d} {step.name}")
        else:
            click.echo("already up to date")
        click.echo(f"{desk.path} is at schema {opened.version}")
    finally:
        opened.close()


@book.command("counts")
@pass_desk
def counts(desk: Desk) -> None:
    """How many rows each table holds."""
    opened = desk.open()
    try:
        rows = [[name, str(opened.count(name))] for name in opened.tables()]
    finally:
        opened.close()
    echo_rows(["table", "rows"], rows)


@book.command("check")
@pass_desk
def check(desk: Desk) -> None:
    """Say whether the book is sound and up to date."""
    opened = Book(desk.path)
    try:
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
    finally:
        opened.close()
