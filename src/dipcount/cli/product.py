"""Commands for the product shelf and the labels on it."""

from __future__ import annotations

from decimal import Decimal

import click

from dipcount import formulary
from dipcount import habitat as hb
from dipcount.cli.options import Desk, day_or_today, echo_pairs, echo_rows, pass_desk, read_quantity
from dipcount.model.product import PURPOSES, SIGNALS
from dipcount.store import products as store
from dipcount.units import Rate


@click.group()
def product() -> None:
    """What is on the shelf, and what the labels allow."""


@product.command("stock")
@click.option("--on", "on_text", default=None, help="The day the shelf was set up.")
@pass_desk
def stock(desk: Desk, on_text: str | None) -> None:
    """Put the starting shelf in the book, leaving anything already there."""
    with desk.book() as opened:
        added = formulary.stock(opened, day_or_today(on_text, desk.zone_name))
    if not added:
        click.echo("the shelf was already stocked")
        return
    click.echo(f"{len(added)} products added: {', '.join(added)}")


@product.command("add")
@click.argument("name")
@click.argument("registration")
@click.option("--maker", required=True, help="Who makes it.")
@click.option("--active", required=True, help="The active ingredient.")
@click.option("--percent", required=True, type=float, help="How much of it, by share.")
@click.option("--form", required=True, type=click.Choice(hb.forms()), help="The formulation.")
@click.option("--purpose", required=True, type=click.Choice(PURPOSES), help="What it is for.")
@click.option("--on", "on_text", default=None, help="The day it came on the shelf.")
@click.option("--restricted", is_flag=True, help="A restricted use pesticide.")
@click.option("--signal", default="caution", type=click.Choice(SIGNALS), help="The signal word.")
@click.option("--reentry", default=0, type=int, help="Reentry interval in hours.")
@click.option("--note", default="", help="Anything worth knowing about it.")
@pass_desk
def add(
    desk: Desk,
    name: str,
    registration: str,
    maker: str,
    active: str,
    percent: float,
    form: str,
    purpose: str,
    on_text: str | None,
    restricted: bool,
    signal: str,
    reentry: int,
    note: str,
) -> None:
    """Put a product on the shelf."""
    with desk.book() as opened:
        made = store.add(
            opened,
            name,
            registration,
            maker,
            active,
            Decimal(str(percent)),
            form,
            purpose,
            day_or_today(on_text, desk.zone_name),
            restricted=restricted,
            signal=signal,
            reentry=reentry,
            note=note,
        )
    click.echo(f"{made.id}  {made.name}  {made.registration}")


@product.command("label")
@click.argument("product_name")
@click.argument("habitat", type=click.Choice(hb.keys()))
@click.option("--low", required=True, help="The bottom of the rate range, such as 2.5 lb.")
@click.option("--high", required=True, help="The top of the rate range.")
@click.option("--season-max", default=None, help="The most one place may take in a season.")
@click.option("--interval", default=0, type=int, help="Days between applications.")
@pass_desk
def label(
    desk: Desk,
    product_name: str,
    habitat: str,
    low: str,
    high: str,
    season_max: str | None,
    interval: int,
) -> None:
    """Write one habitat's rate range onto a product's label."""
    per = hb.habitat(habitat).extent_unit
    with desk.book() as opened:
        found = store.resolve(opened, product_name)
        after = store.label(
            opened,
            found.id,
            habitat,
            Rate(read_quantity(low), per),
            Rate(read_quantity(high), per),
            season_max=None if season_max is None else read_quantity(season_max),
            interval_days=interval,
        )
    entry = after.label_for(habitat)
    assert entry is not None
    click.echo(f"{after.id}  {entry.line()}")


@product.command("list")
@click.option("--purpose", default=None, type=click.Choice(PURPOSES), help="Only this purpose.")
@click.option("--form", default=None, type=click.Choice(hb.forms()), help="Only this formulation.")
@click.option("--on", "on_text", default=None, help="Only what was on the shelf that day.")
@pass_desk
def list_them(desk: Desk, purpose: str | None, form: str | None, on_text: str | None) -> None:
    """Every product on the shelf."""
    with desk.book() as opened:
        found = store.all_products(opened, purpose=purpose, form=form)
        if on_text is not None:
            on = day_or_today(on_text, desk.zone_name)
            found = [one for one in found if one.on_shelf(on)]
    echo_rows(
        ["id", "name", "registration", "active", "percent", "form", "purpose", "rup"],
        [
            [
                one.id,
                one.name,
                one.registration,
                one.active,
                f"{one.percent:g}",
                one.form,
                one.purpose,
                "yes" if one.restricted else "",
            ]
            for one in found
        ],
    )


@product.command("show")
@click.argument("product_name")
@pass_desk
def show(desk: Desk, product_name: str) -> None:
    """One product and everything its label says."""
    with desk.book() as opened:
        found = store.resolve(opened, product_name)
    echo_pairs(
        [
            ("id", found.id),
            ("name", found.name),
            ("registration", found.registration),
            ("maker", found.maker),
            ("active", found.active),
            ("percent", f"{found.percent:g}"),
            ("form", found.form),
            ("purpose", found.purpose),
            ("restricted", "yes" if found.restricted else "no"),
            ("signal word", found.signal),
            ("reentry", f"{found.reentry} hours"),
            ("added", found.added_on.isoformat()),
            ("withdrawn", found.withdrawn_on.isoformat() if found.withdrawn_on else "-"),
            ("note", found.note or "-"),
        ],
    )
    if found.labels:
        click.echo("")
        echo_rows(
            ["habitat", "low", "high", "per", "season max", "interval"],
            [
                [
                    one.habitat,
                    str(one.low.amount),
                    str(one.high.amount),
                    one.per,
                    str(one.season_max) if one.season_max else "-",
                    str(one.interval_days),
                ]
                for one in found.labels
            ],
        )


@product.command("for")
@click.argument("habitat", type=click.Choice(hb.keys()))
@click.option("--purpose", default=None, type=click.Choice(PURPOSES), help="Only this purpose.")
@click.option("--on", "on_text", default=None, help="Only what was on the shelf that day.")
@pass_desk
def for_habitat(desk: Desk, habitat: str, purpose: str | None, on_text: str | None) -> None:
    """Every product whose label covers one kind of water."""
    on = None if on_text is None else day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        found = store.for_habitat(opened, habitat, purpose=purpose, on=on)
        rows = []
        for one in found:
            entry = one.label_for(habitat)
            assert entry is not None
            rows.append(
                [
                    one.id,
                    one.name,
                    one.form,
                    one.purpose,
                    f"{entry.low.amount} to {entry.high.amount} per {entry.per}",
                    str(entry.interval_days),
                ],
            )
    click.echo(f"{hb.habitat(habitat).name}\n")
    echo_rows(["id", "name", "form", "purpose", "rate", "interval"], rows)


@product.command("withdraw")
@click.argument("product_name")
@click.option("--on", "on_text", default=None, help="The day it came off the shelf.")
@click.option("--why", default="", help="Why it came off.")
@pass_desk
def withdraw(desk: Desk, product_name: str, on_text: str | None, why: str) -> None:
    """Take a product off the shelf."""
    with desk.book() as opened:
        found = store.resolve(opened, product_name)
        gone = store.withdraw(opened, found.id, day_or_today(on_text, desk.zone_name), why)
    click.echo(f"{gone.id} withdrawn {gone.withdrawn_on}")
