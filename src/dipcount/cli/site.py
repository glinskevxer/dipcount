"""Commands about sites."""

from __future__ import annotations

import click

from dipcount import habitat as hb
from dipcount.cli.options import (
    Desk,
    day_or_today,
    echo_pairs,
    echo_rows,
    pass_desk,
    read_quantity,
)
from dipcount.service import district
from dipcount.store import sites, zones


@click.group()
def site() -> None:
    """Put water on the list, take it off, and look at what is there."""


@site.command("add")
@click.argument("zone_name")
@click.argument("name")
@click.option("--habitat", required=True, type=click.Choice(hb.keys()), help="What kind of water.")
@click.option("--extent", required=True, help="How much of it, such as 6.5 acre or 14 each.")
@click.option("--on", "on_text", default=None, help="The day it went on the list.")
@click.option("--access", default="", help="How to get to it.")
@click.option("--lat", "latitude", type=float, default=None, help="Latitude, if it is known.")
@click.option("--lon", "longitude", type=float, default=None, help="Longitude, if it is known.")
@click.option("--note", default="", help="Anything worth knowing about it.")
@pass_desk
def add(
    desk: Desk,
    zone_name: str,
    name: str,
    habitat: str,
    extent: str,
    on_text: str | None,
    access: str,
    latitude: float | None,
    longitude: float | None,
    note: str,
) -> None:
    """Put a piece of water on the inspection list."""
    with desk.book() as opened:
        made = district.list_site(
            opened,
            desk.actor,
            zone_name,
            name,
            habitat,
            read_quantity(extent),
            day_or_today(on_text, desk.zone_name),
            access=access,
            latitude=latitude,
            longitude=longitude,
            note=note,
        )
    click.echo(f"{made.id}  {made.name}  {made.kind.name}  {made.extent}")


@site.command("list")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@click.option("--habitat", default=None, type=click.Choice(hb.keys()), help="Only this habitat.")
@click.option("--open-on", "open_text", default=None, help="Only sites listed on this day.")
@pass_desk
def list_them(
    desk: Desk,
    zone_name: str | None,
    habitat: str | None,
    open_text: str | None,
) -> None:
    """The site list."""
    with desk.book() as opened:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        found = sites.all_sites(opened, zone_id=zone_id, habitat=habitat)
        if open_text is not None:
            on = day_or_today(open_text, desk.zone_name)
            found = [one for one in found if one.is_open(on)]
    echo_rows(
        ["id", "zone", "name", "habitat", "extent"],
        [[one.id, one.zone, one.name, one.habitat, str(one.extent)] for one in found],
    )


@site.command("show")
@click.argument("site_id")
@pass_desk
def show(desk: Desk, site_id: str) -> None:
    """One site in full, with its trail."""
    with desk.book() as opened:
        found = sites.get(opened, site_id)
        history = district.site_history(opened, site_id)
    echo_pairs(
        [
            ("id", found.id),
            ("zone", found.zone),
            ("name", found.name),
            ("habitat", found.kind.name),
            ("extent", str(found.extent)),
            ("listed", found.listed_on.isoformat()),
            ("retired", found.retired_on.isoformat() if found.retired_on else "-"),
            ("access", found.access or "-"),
            ("note", found.note or "-"),
        ],
    )
    click.echo("")
    for entry in history:
        click.echo(entry.line())


@site.command("retire")
@click.argument("site_id")
@click.option("--on", "on_text", default=None, help="The day it came off the list.")
@click.option("--why", default="", help="Why it came off.")
@pass_desk
def retire(desk: Desk, site_id: str, on_text: str | None, why: str) -> None:
    """Take a site off the inspection list."""
    with desk.book() as opened:
        gone = district.retire_site(
            opened,
            desk.actor,
            site_id,
            day_or_today(on_text, desk.zone_name),
            why,
        )
    click.echo(f"{gone.id} retired {gone.retired_on}")


@site.command("remeasure")
@click.argument("site_id")
@click.argument("extent")
@pass_desk
def remeasure(desk: Desk, site_id: str, extent: str) -> None:
    """Write a new extent against a site."""
    with desk.book() as opened:
        changed = district.remeasure_site(opened, desk.actor, site_id, read_quantity(extent))
    click.echo(f"{changed.id} now {changed.extent}")


@site.command("move")
@click.argument("site_id")
@click.argument("zone_name")
@pass_desk
def move(desk: Desk, site_id: str, zone_name: str) -> None:
    """Move a site into another zone."""
    with desk.book() as opened:
        moved = district.move_site(opened, desk.actor, site_id, zone_name)
    click.echo(f"{moved.id} now in {moved.zone}")
