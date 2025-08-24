"""Commands about zones."""

from __future__ import annotations

import click

from dipcount.cli.options import Desk, echo_pairs, echo_rows, pass_desk
from dipcount.service import district
from dipcount.store import zones


@click.group()
def zone() -> None:
    """Open zones and look at them."""


@zone.command("add")
@click.argument("name")
@click.option("--supervisor", default="", help="Who answers for this zone.")
@click.option("--note", default="", help="Anything worth knowing about it.")
@pass_desk
def add(desk: Desk, name: str, supervisor: str, note: str) -> None:
    """Open a new zone."""
    with desk.book() as opened:
        made = district.list_zone(opened, desk.actor, name, supervisor, note)
    click.echo(f"{made.id}  {made.name}")


@zone.command("list")
@pass_desk
def list_them(desk: Desk) -> None:
    """Every zone the district runs."""
    with desk.book() as opened:
        found = zones.all_zones(opened)
    echo_rows(
        ["id", "name", "supervisor"],
        [[one.id, one.name, one.supervisor or "-"] for one in found],
    )


@zone.command("show")
@click.argument("name")
@pass_desk
def show(desk: Desk, name: str) -> None:
    """One zone in full."""
    with desk.book() as opened:
        found = zones.resolve(opened, name)
    echo_pairs(
        [
            ("id", found.id),
            ("name", found.name),
            ("supervisor", found.supervisor or "-"),
            ("note", found.note or "-"),
        ],
    )
