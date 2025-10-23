"""Commands for spray blocks and the no spray register."""

from __future__ import annotations

import click

from dipcount.cli.options import Desk, day_or_today, echo_pairs, echo_rows, pass_desk
from dipcount.model.exclusion import kinds
from dipcount.store import blocks as store
from dipcount.store import exclusions, zones


@click.group()
def block() -> None:
    """The blocks a truck runs, and what falls inside them."""


@block.command("add")
@click.argument("name")
@click.argument("zone_name")
@click.option("--acres", required=True, type=float, help="How much ground the block covers.")
@click.option("--road-miles", default=0.0, type=float, help="How much road the truck drives.")
@click.option("--on", "on_text", default=None, help="The day it went on the run list.")
@click.option("--note", default="", help="Anything worth knowing about it.")
@pass_desk
def add(
    desk: Desk,
    name: str,
    zone_name: str,
    acres: float,
    road_miles: float,
    on_text: str | None,
    note: str,
) -> None:
    """Put a block on the run list."""
    with desk.book() as opened:
        made = store.add(
            opened,
            zone_name,
            name,
            acres,
            day_or_today(on_text, desk.zone_name),
            road_miles=road_miles,
            note=note,
        )
    click.echo(f"{made.id}  {made.name}  {made.acres:g} acre")


@block.command("list")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@click.option("--on", "on_text", default=None, help="Only blocks on the list that day.")
@pass_desk
def list_them(desk: Desk, zone_name: str | None, on_text: str | None) -> None:
    """Every block."""
    with desk.book() as opened:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        found = store.all_blocks(opened, zone_id=zone_id)
        if on_text is not None:
            on = day_or_today(on_text, desk.zone_name)
            found = [one for one in found if one.is_open(on)]
        counts = {
            one.id: len(store.entries_in(opened, one.id, day_or_today(on_text, desk.zone_name)))
            for one in found
        }
    echo_rows(
        ["id", "name", "zone", "acres", "road miles", "register", "retired"],
        [
            [
                one.id,
                one.name,
                one.zone,
                f"{one.acres:g}",
                f"{one.road_miles:g}",
                str(counts[one.id]),
                one.retired_on.isoformat() if one.retired_on else "-",
            ]
            for one in found
        ],
    )


@block.command("show")
@click.argument("block_name")
@click.option("--on", "on_text", default=None, help="The day to read the register on.")
@pass_desk
def show(desk: Desk, block_name: str, on_text: str | None) -> None:
    """One block and everything on the register inside it."""
    on = day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        found = store.resolve(opened, block_name)
        inside = store.entries_in(opened, found.id, on)
    echo_pairs(
        [
            ("id", found.id),
            ("name", found.name),
            ("zone", found.zone),
            ("acres", f"{found.acres:g}"),
            ("road miles", f"{found.road_miles:g}"),
            ("listed", found.listed_on.isoformat()),
            ("retired", found.retired_on.isoformat() if found.retired_on else "-"),
            ("note", found.note or "-"),
        ],
    )
    if inside:
        click.echo("")
        echo_rows(
            ["entry", "kind", "name", "buffer ft", "notice"],
            [
                [
                    one.id,
                    one.kind,
                    one.name,
                    str(one.buffer),
                    "never" if one.absolute else f"{one.hours} h",
                ]
                for one in inside
            ],
        )


@block.command("retire")
@click.argument("block_name")
@click.option("--on", "on_text", default=None, help="The day it came off the run list.")
@click.option("--why", default="", help="Why it came off.")
@pass_desk
def retire(desk: Desk, block_name: str, on_text: str | None, why: str) -> None:
    """Take a block off the run list."""
    with desk.book() as opened:
        found = store.resolve(opened, block_name)
        gone = store.retire(opened, found.id, day_or_today(on_text, desk.zone_name), why)
    click.echo(f"{gone.id} retired {gone.retired_on}")


@block.command("link")
@click.argument("block_name")
@click.argument("exclusion_id")
@pass_desk
def link(desk: Desk, block_name: str, exclusion_id: str) -> None:
    """Record that a register entry falls inside a block."""
    with desk.book() as opened:
        found = store.resolve(opened, block_name)
        store.link(opened, found.id, exclusion_id)
        entry = exclusions.get(opened, exclusion_id)
    click.echo(f"{entry.name} is inside {found.name}")


@block.command("unlink")
@click.argument("block_name")
@click.argument("exclusion_id")
@pass_desk
def unlink(desk: Desk, block_name: str, exclusion_id: str) -> None:
    """Take a register entry out of a block."""
    with desk.book() as opened:
        found = store.resolve(opened, block_name)
        store.unlink(opened, found.id, exclusion_id)
    click.echo(f"{exclusion_id} taken out of {found.name}")


@click.group()
def register() -> None:
    """The places the district does not spray over."""


@register.command("add")
@click.argument("name")
@click.argument("zone_name")
@click.option("--kind", required=True, type=click.Choice(kinds()), help="What sort of place.")
@click.option("--contact", default="", help="Who to talk to.")
@click.option("--phone", default="", help="How to reach them.")
@click.option(
    "--buffer",
    "buffer_ft",
    default=0,
    type=int,
    help="Buffer in feet, if not the usual for the kind.",
)
@click.option(
    "--notice",
    "notice_hours",
    default=0,
    type=int,
    help="Notice wanted in hours, if not the usual for the kind.",
)
@click.option("--on", "on_text", default=None, help="The day it went on the register.")
@click.option("--note", default="", help="Anything worth knowing.")
@pass_desk
def add_entry(
    desk: Desk,
    name: str,
    zone_name: str,
    kind: str,
    contact: str,
    phone: str,
    buffer_ft: int,
    notice_hours: int,
    on_text: str | None,
    note: str,
) -> None:
    """Put a place on the register."""
    with desk.book() as opened:
        made = exclusions.add(
            opened,
            kind,
            name,
            zone_name,
            day_or_today(on_text, desk.zone_name),
            contact=contact,
            phone=phone,
            buffer_ft=buffer_ft,
            notice_hours=notice_hours,
            note=note,
        )
    click.echo(f"{made.id}  {made.line()}")


@register.command("list")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@click.option("--kind", default=None, type=click.Choice(kinds()), help="Only this sort of place.")
@click.option("--on", "on_text", default=None, help="Only entries current that day.")
@pass_desk
def list_entries(desk: Desk, zone_name: str | None, kind: str | None, on_text: str | None) -> None:
    """Everything on the register."""
    with desk.book() as opened:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        found = exclusions.all_entries(opened, zone_id=zone_id, kind=kind)
        if on_text is not None:
            on = day_or_today(on_text, desk.zone_name)
            found = [one for one in found if one.on_register(on)]
        blocks_for = {one.id: store.blocks_for(opened, one.id) for one in found}
    echo_rows(
        ["id", "kind", "name", "zone", "contact", "buffer ft", "notice", "blocks"],
        [
            [
                one.id,
                one.kind,
                one.name,
                one.zone,
                one.contact or "-",
                str(one.buffer),
                "never" if one.absolute else f"{one.hours} h",
                ", ".join(block.id for block in blocks_for[one.id]) or "-",
            ]
            for one in found
        ],
    )


@register.command("remove")
@click.argument("exclusion_id")
@click.option("--on", "on_text", default=None, help="The day it came off.")
@click.option("--why", default="", help="Why it came off.")
@pass_desk
def remove_entry(desk: Desk, exclusion_id: str, on_text: str | None, why: str) -> None:
    """Take a place off the register."""
    with desk.book() as opened:
        gone = exclusions.remove(
            opened,
            exclusion_id,
            day_or_today(on_text, desk.zone_name),
            why,
        )
    click.echo(f"{gone.id} came off {gone.removed_on}")
