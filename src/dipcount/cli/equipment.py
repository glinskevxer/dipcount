"""Commands for the shop: machines, calibrations and driving speeds."""

from __future__ import annotations

import click

from dipcount.cli.options import (
    Desk,
    day_or_today,
    echo_pairs,
    echo_rows,
    pass_desk,
    read_quantity,
)
from dipcount.model.equipment import KINDS
from dipcount.service import calibration
from dipcount.store import equipment as store
from dipcount.units import Rate


@click.group()
def shop() -> None:
    """The machines, and whether they may be used."""


@shop.command("add")
@click.argument("serial")
@click.option("--kind", required=True, type=click.Choice(KINDS), help="What sort of machine.")
@click.option("--maker", required=True, help="Who made it.")
@click.option("--model", required=True, help="Which model.")
@click.option("--nominal", default=None, help="Rated flow, such as 1.5 fl oz a minute.")
@click.option("--swath", "swath_ft", default=0.0, type=float, help="Swath width in feet.")
@click.option("--on", "on_text", default=None, help="The day it arrived.")
@click.option("--note", default="", help="Anything worth knowing.")
@pass_desk
def add(
    desk: Desk,
    serial: str,
    kind: str,
    maker: str,
    model: str,
    nominal: str | None,
    swath_ft: float,
    on_text: str | None,
    note: str,
) -> None:
    """Put a machine on the books."""
    with desk.book() as opened:
        made = store.add(
            opened,
            kind,
            maker,
            model,
            serial,
            day_or_today(on_text, desk.zone_name),
            nominal=None if nominal is None else read_quantity(nominal),
            swath_ft=swath_ft,
            note=note,
        )
    click.echo(f"{made.id}  {made.maker} {made.model}  {made.serial}")


@shop.command("list")
@click.option("--kind", default=None, type=click.Choice(KINDS), help="Only this kind.")
@click.option("--on", "on_text", default=None, help="The day to stand it on.")
@pass_desk
def list_them(desk: Desk, kind: str | None, on_text: str | None) -> None:
    """Every machine and where it stands."""
    on = day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        found = [
            calibration.standing(opened, one.id, on)
            for one in store.all_machines(opened, kind=kind)
        ]
    echo_rows(
        ["id", "kind", "model", "serial", "nominal", "swath", "due", "usable"],
        [
            [
                one.machine.id,
                one.machine.kind,
                one.machine.model,
                one.machine.serial,
                str(one.machine.nominal) if one.machine.nominal else "-",
                f"{one.machine.swath_ft:g}",
                one.due_on.isoformat() if one.due_on else "never",
                "yes" if one.usable else "no",
            ]
            for one in found
        ],
    )


@shop.command("calibrate")
@click.argument("machine")
@click.option("--on", "on_text", default=None, help="The day it was checked.")
@click.option("--flow", required=True, help="What came out in a minute, such as 1.5 fl oz.")
@click.option("--droplet", type=float, default=None, help="Volume median diameter in microns.")
@click.option("--swath", "swath_ft", type=float, default=None, help="Swath measured, in feet.")
@click.option("--speed", "speed_mph", type=float, default=0.0, help="Speed driven, miles an hour.")
@click.option("--note", default="", help="Anything worth writing down.")
@pass_desk
def calibrate(
    desk: Desk,
    machine: str,
    on_text: str | None,
    flow: str,
    droplet: float | None,
    swath_ft: float | None,
    speed_mph: float,
    note: str,
) -> None:
    """Record one check of one machine."""
    with desk.book() as opened:
        made = store.calibrate(
            opened,
            machine,
            day_or_today(on_text, desk.zone_name),
            desk.actor,
            read_quantity(flow),
            droplet=droplet,
            swath_ft=swath_ft,
            speed_mph=speed_mph,
            note=note,
        )
        found = calibration.standing(opened, made.equipment, made.on)
    applied = made.rate()
    click.echo(
        f"{made.id}  {made.flow} a minute"
        f"  {'rate ' + str(applied) if applied else 'no rate, speed not given'}"
        f"  due {made.due()}",
    )
    for one in found.refusals():
        click.echo(f"  {one.line()}")


@shop.command("show")
@click.argument("machine")
@click.option("--on", "on_text", default=None, help="The day to stand it on.")
@pass_desk
def show(desk: Desk, machine: str, on_text: str | None) -> None:
    """One machine, where it stands, and its calibration history."""
    on = day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        found = store.resolve(opened, machine)
        where = calibration.standing(opened, found.id, on)
        history = store.calibrations_for(opened, found.id)
    echo_pairs(
        [
            ("id", found.id),
            ("kind", found.kind),
            ("maker", found.maker),
            ("model", found.model),
            ("serial", found.serial),
            ("nominal flow", str(found.nominal) if found.nominal else "-"),
            ("swath", f"{found.swath_ft:g} ft"),
            ("arrived", found.added_on.isoformat()),
            ("retired", found.retired_on.isoformat() if found.retired_on else "-"),
            ("last checked", where.last.on.isoformat() if where.last else "never"),
            ("due", where.due_on.isoformat() if where.due_on else "-"),
            ("usable", "yes" if where.usable else "no"),
            ("note", found.note or "-"),
        ],
    )
    for one in where.refusals():
        click.echo(f"  {one.line()}")
    if history:
        click.echo("")
        echo_rows(
            ["id", "day", "flow", "droplet", "swath", "speed", "rate", "by"],
            [
                [
                    one.id,
                    one.on.isoformat(),
                    str(one.flow),
                    f"{one.droplet:g}" if one.droplet else "-",
                    f"{one.swath_ft:g}",
                    f"{one.speed_mph:g}",
                    str(one.rate()) if one.rate() else "-",
                    one.tested_by,
                ]
                for one in history
            ],
        )


@shop.command("due")
@click.option("--on", "on_text", default=None, help="The day to look from.")
@click.option("--within", default=0, type=int, help="How many days ahead to look.")
@pass_desk
def due(desk: Desk, on_text: str | None, within: int) -> None:
    """Every machine due for calibration."""
    on = day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        found = calibration.due(opened, on, within=within)
    echo_rows(
        ["id", "model", "serial", "last", "due", "days over"],
        [
            [
                one.machine.id,
                one.machine.model,
                one.machine.serial,
                one.last.on.isoformat() if one.last else "never",
                one.due_on.isoformat() if one.due_on else "-",
                str(one.days_over),
            ]
            for one in found
        ],
    )


@shop.command("speed")
@click.argument("machine")
@click.argument("rate_text")
@click.option("--on", "on_text", default=None, help="The day to use the calibration from.")
@pass_desk
def speed(desk: Desk, machine: str, rate_text: str, on_text: str | None) -> None:
    """How fast to drive to hit a rate on the last measured flow."""
    on = day_or_today(on_text, desk.zone_name)
    wanted = Rate(read_quantity(rate_text), "acre")
    with desk.book() as opened:
        found = store.resolve(opened, machine)
        where = calibration.standing(opened, found.id, on)
        driving = calibration.target_speed(opened, found.id, wanted, on)
    if driving is None:
        click.echo(f"{found.id} has no calibration to work from")
        return
    echo_pairs(
        [
            ("machine", f"{found.id} {found.model}"),
            ("calibrated", where.last.on.isoformat() if where.last else "-"),
            ("flow", str(where.last.flow) if where.last else "-"),
            ("swath", f"{found.swath_ft:g} ft"),
            ("wanted", str(wanted)),
            ("drive at", f"{driving:.2f} mph"),
        ],
    )


@shop.command("retire")
@click.argument("machine")
@click.option("--on", "on_text", default=None, help="The day it went out of service.")
@click.option("--why", default="", help="Why it went out.")
@pass_desk
def retire(desk: Desk, machine: str, on_text: str | None, why: str) -> None:
    """Take a machine out of service."""
    with desk.book() as opened:
        found = store.resolve(opened, machine)
        gone = store.retire(opened, found.id, day_or_today(on_text, desk.zone_name), why)
    click.echo(f"{gone.id} out of service {gone.retired_on}")
