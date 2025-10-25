"""Commands for the night's fogging: notice, the window, and the run."""

from __future__ import annotations

import click

from dipcount import clock, rules
from dipcount.cli.options import (
    Desk,
    echo_pairs,
    echo_rows,
    moment_or_now,
    pass_desk,
    read_quantity,
)
from dipcount.model.block import WAYS
from dipcount.service import adulticide
from dipcount.store import blocks, exclusions, products, runs, zones


@click.group()
def spray() -> None:
    """Tell people, check the night, and record the run."""


@spray.command("limits")
def limits() -> None:
    """What the district will and will not fog in."""
    echo_pairs(
        [
            ("wind", f"{rules.WIND_LOW} to {rules.WIND_HIGH} miles an hour"),
            ("temperature", f"{rules.TEMP_FLOOR} degrees and up"),
            ("hours", f"{rules.NIGHT_FROM}:00 to {rules.NIGHT_TO:02d}:00"),
            ("apiary notice", "48 hours"),
            ("organic farm notice", "24 hours"),
        ],
    )


@spray.command("tell")
@click.argument("exclusion_id")
@click.argument("block_name")
@click.option("--at", "given_text", default=None, help="When they were told.")
@click.option("--from", "from_text", required=True, help="When the window opens.")
@click.option("--to", "to_text", required=True, help="When the window closes.")
@click.option("--how", default="phone", type=click.Choice(WAYS), help="How they were told.")
@click.option("--note", default="", help="Anything worth writing down.")
@pass_desk
def tell(
    desk: Desk,
    exclusion_id: str,
    block_name: str,
    given_text: str | None,
    from_text: str,
    to_text: str,
    how: str,
    note: str,
) -> None:
    """Record that a place was told about a block and a window."""
    with desk.book() as opened:
        block = blocks.resolve(opened, block_name)
        made = blocks.give(
            opened,
            exclusion_id,
            block.id,
            moment_or_now(given_text, desk.zone_name),
            clock.moment(from_text, desk.zone_name),
            clock.moment(to_text, desk.zone_name),
            how,
            desk.actor,
            note=note,
        )
        entry = exclusions.get(opened, exclusion_id)
    click.echo(f"{made.id}  {entry.name}  {made.hours_given} hours notice")


@spray.command("waiting")
@click.argument("block_name")
@click.option("--at", "at_text", required=True, help="When the run would start.")
@pass_desk
def waiting(desk: Desk, block_name: str, at_text: str) -> None:
    """Everybody inside a block who has not been told about this run."""
    at = clock.moment(at_text, desk.zone_name)
    with desk.book() as opened:
        block = blocks.resolve(opened, block_name)
        untold = adulticide.who_to_tell(opened, block.id, at)
        by = adulticide.notice_deadline(opened, block.id, at)
    if by is not None:
        click.echo(f"notice for a run at {clock.stamp(at)} was due by {clock.stamp(by)}\n")
    echo_rows(
        ["entry", "kind", "name", "contact", "phone", "notice"],
        [
            [one.id, one.kind, one.name, one.contact or "-", one.phone or "-", f"{one.hours} h"]
            for one in untold
        ],
    )


@spray.command("window")
@click.argument("block_name")
@click.option("--at", "at_text", required=True, help="When the run would start.")
@click.option("--wind", type=float, default=None, help="Wind at the truck, miles an hour.")
@click.option("--temperature", type=float, default=None, help="Temperature, Fahrenheit.")
@click.option("--acres", type=float, default=None, help="How much of the block, if not all.")
@pass_desk
def window(
    desk: Desk,
    block_name: str,
    at_text: str,
    wind: float | None,
    temperature: float | None,
    acres: float | None,
) -> None:
    """Say whether a block may be run, and what stops it."""
    at = clock.moment(at_text, desk.zone_name)
    with desk.book() as opened:
        block = blocks.resolve(opened, block_name)
        found = adulticide.window(
            opened,
            block.id,
            at,
            wind_mph=wind,
            temperature=temperature,
            acres=acres,
            zone=desk.zone_name,
        )
    echo_pairs(
        [
            ("block", f"{block.id} {block.name}"),
            ("at", clock.stamp(at, desk.zone_name)),
            ("acres", f"{found.acres:g}"),
            ("wind", str(found.wind_mph) if found.wind_mph is not None else "-"),
            ("temperature", str(found.temperature) if found.temperature is not None else "-"),
            ("told", ", ".join(found.told) or "-"),
            ("not told", ", ".join(found.untold) or "-"),
            ("barred", ", ".join(found.barred) or "-"),
            ("allowed", "yes" if found.allowed else "no"),
        ],
    )
    for one in found.refusals:
        click.echo(f"  {one.line()}")


@spray.command("board")
@click.option("--at", "at_text", required=True, help="When the runs would start.")
@click.option("--wind", type=float, default=None, help="Wind at the truck, miles an hour.")
@click.option("--temperature", type=float, default=None, help="Temperature, Fahrenheit.")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@pass_desk
def board(
    desk: Desk,
    at_text: str,
    wind: float | None,
    temperature: float | None,
    zone_name: str | None,
) -> None:
    """Every block and whether the truck may go out on it."""
    at = clock.moment(at_text, desk.zone_name)
    with desk.book() as opened:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        found = adulticide.tonight_board(
            opened,
            at,
            wind_mph=wind,
            temperature=temperature,
            zone_id=zone_id,
        )
        names = {one.id: one.name for one in blocks.all_blocks(opened)}
    echo_rows(
        ["block", "name", "acres", "allowed", "held by"],
        [
            [
                one.block,
                names.get(one.block, one.block),
                f"{one.acres:g}",
                "yes" if one.allowed else "no",
                ", ".join(sorted({two.rule for two in one.refusals})) or "-",
            ]
            for one in found
        ],
    )


@spray.command("go")
@click.argument("block_name")
@click.argument("lot_id")
@click.option("--by", "applicator", required=True, help="Which licence holder made the run.")
@click.option("--start", "start_text", required=True, help="When the truck started.")
@click.option("--finish", "finish_text", required=True, help="When it finished.")
@click.option("--amount", required=True, help="How much went out, such as 1.4 gal.")
@click.option("--acres", type=float, default=None, help="How much of the block, if not all.")
@click.option("--wind", type=float, default=None, help="Wind at the truck, miles an hour.")
@click.option("--temperature", type=float, default=None, help="Temperature, Fahrenheit.")
@click.option("--wind-from", default="", help="Which way the wind was coming from.")
@click.option("--equipment", default="", help="Which machine it went through.")
@click.option("--note", default="", help="Anything worth writing down.")
@pass_desk
def go(
    desk: Desk,
    block_name: str,
    lot_id: str,
    applicator: str,
    start_text: str,
    finish_text: str,
    amount: str,
    acres: float | None,
    wind: float | None,
    temperature: float | None,
    wind_from: str,
    equipment: str,
    note: str,
) -> None:
    """Record one night's run over a block."""
    with desk.book() as opened:
        block = blocks.resolve(opened, block_name)
        made = adulticide.spray(
            opened,
            applicator,
            block.id,
            lot_id,
            clock.moment(start_text, desk.zone_name),
            clock.moment(finish_text, desk.zone_name),
            read_quantity(amount),
            acres=acres,
            wind_mph=wind,
            temperature=temperature,
            wind_from=wind_from,
            equipment=equipment,
            note=note,
        )
    click.echo(f"{made.id}  {made.line()}")


@spray.command("runs")
@click.option("--from", "start_text", required=True, help="First day of the window.")
@click.option("--to", "end_text", required=True, help="Last day of the window.")
@click.option("--block", "block_name", default=None, help="Only this block.")
@pass_desk
def list_runs(desk: Desk, start_text: str, end_text: str, block_name: str | None) -> None:
    """Every run over a window."""
    with desk.book() as opened:
        block_id = None if block_name is None else blocks.resolve(opened, block_name).id
        found = runs.between(
            opened,
            clock.day(start_text),
            clock.day(end_text),
            block_id=block_id,
        )
        names = {one.id: one.name for one in products.all_products(opened)}
    echo_rows(
        ["night", "run", "block", "product", "acres", "amount", "rate", "by"],
        [
            [
                one.on.isoformat(),
                one.id,
                one.block,
                names.get(one.product, one.product),
                f"{one.acres:g}",
                str(one.amount),
                str(one.rate),
                one.applicator,
            ]
            for one in found
        ],
    )


@spray.command("show")
@click.argument("run_id")
@pass_desk
def show(desk: Desk, run_id: str) -> None:
    """One run in full."""
    with desk.book() as opened:
        made = runs.get(opened, run_id)
        block = blocks.get(opened, made.block)
        product = products.get(opened, made.product)
        told = blocks.notices_for(opened, made.block)
    echo_pairs(
        [
            ("run", made.id),
            ("block", f"{block.id} {block.name}"),
            ("product", f"{product.id} {product.name}"),
            ("registration", product.registration),
            ("lot", made.lot),
            ("applicator", made.applicator),
            ("licence", made.licence or "-"),
            ("started", clock.stamp(made.started_at, desk.zone_name)),
            ("finished", clock.stamp(made.finished_at, desk.zone_name)),
            ("minutes", str(made.minutes)),
            ("acres", f"{made.acres:g}"),
            ("amount", str(made.amount)),
            ("rate", str(made.rate)),
            ("wind", f"{made.wind_mph:g} from {made.wind_from}" if made.wind_mph else "-"),
            ("temperature", f"{made.temperature:g}" if made.temperature else "-"),
            ("equipment", made.equipment or "-"),
            ("note", made.note or "-"),
        ],
    )
    if told:
        click.echo("")
        echo_rows(
            ["notice", "entry", "given", "how", "hours"],
            [
                [
                    one.id,
                    one.exclusion,
                    clock.stamp(one.given_at, desk.zone_name),
                    one.how,
                    str(one.hours_given),
                ]
                for one in told
            ],
        )


@spray.command("nights")
@click.option("--from", "start_text", required=True, help="First day of the window.")
@click.option("--to", "end_text", required=True, help="Last day of the window.")
@pass_desk
def nights(desk: Desk, start_text: str, end_text: str) -> None:
    """Every night the truck went out over a window."""
    with desk.book() as opened:
        found = runs.nights(opened, clock.day(start_text), clock.day(end_text))
        rows = [
            [
                one.isoformat(),
                str(len(runs.on_day(opened, one))),
                f"{sum(two.acres for two in runs.on_day(opened, one)):g}",
            ]
            for one in found
        ]
    echo_rows(["night", "runs", "acres"], rows)


@spray.command("season")
@click.argument("block_name")
@click.argument("year", type=int)
@pass_desk
def season(desk: Desk, block_name: str, year: int) -> None:
    """How much of a block was fogged in a season, counting every pass."""
    with desk.book() as opened:
        block = blocks.resolve(opened, block_name)
        acres = runs.season_acres(opened, block.id, year)
        made = runs.between(
            opened,
            clock.day(f"{year}-01-01"),
            clock.day(f"{year}-12-31"),
            block_id=block.id,
        )
    echo_pairs(
        [
            ("block", f"{block.id} {block.name}"),
            ("acres", f"{block.acres:g}"),
            ("runs", str(len(made))),
            ("acres fogged", f"{acres:g}"),
            ("passes", f"{acres / block.acres:.2f}"),
        ],
    )
