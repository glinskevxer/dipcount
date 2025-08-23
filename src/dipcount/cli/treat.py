"""Commands for planning and recording treatments."""

from __future__ import annotations

import click

from dipcount import clock
from dipcount.cli.options import (
    Desk,
    day_or_today,
    echo_pairs,
    echo_rows,
    moment_or_now,
    pass_desk,
    read_quantity,
)
from dipcount.service import larvicide
from dipcount.store import products, sites, treatments
from dipcount.units import Rate


@click.group()
def treat() -> None:
    """Work out what may go on, and record what did."""


def _rate(text: str | None, per: str) -> Rate | None:
    return None if text is None else Rate(read_quantity(text), per)


@treat.command("plan")
@click.argument("site_id")
@click.argument("product_name")
@click.option("--on", "on_text", default=None, help="The day it would be made.")
@click.option("--extent", default=None, help="How much of the site, if not all of it.")
@click.option(
    "--strength",
    default=larvicide.MIDDLE,
    type=click.Choice(larvicide.STRENGTHS),
    help="Where in the label range to start.",
)
@click.option("--rate", "rate_text", default=None, help="A rate of your own, such as 6 lb.")
@pass_desk
def plan(
    desk: Desk,
    site_id: str,
    product_name: str,
    on_text: str | None,
    extent: str | None,
    strength: str,
    rate_text: str | None,
) -> None:
    """Say what may go on a site, and what stops it if anything does."""
    on = day_or_today(on_text, desk.zone_name)
    opened = desk.open()
    try:
        site = sites.get(opened, site_id)
        made = larvicide.plan(
            opened,
            site_id,
            product_name,
            on,
            extent=None if extent is None else read_quantity(extent),
            strength=strength,
            rate=_rate(rate_text, site.extent.unit),
        )
        product = products.resolve(opened, product_name)
    finally:
        opened.close()
    echo_pairs(
        [
            ("site", f"{site.id} {site.name}"),
            ("habitat", site.kind.name),
            ("product", f"{product.id} {product.name}"),
            ("day", on.isoformat()),
            ("extent", str(made.extent)),
            ("rate", str(made.rate) if made.rate else "-"),
            ("amount", str(made.amount) if made.amount else "-"),
            ("season used", str(made.season_used) if made.season_used is not None else "-"),
            ("season left", str(made.season_left) if made.season_left is not None else "-"),
            ("allowed", "yes" if made.allowed else "no"),
        ],
    )
    for one in made.refusals:
        click.echo(f"  [{one.rule}] {one.detail}")


@treat.command("choices")
@click.argument("site_id")
@click.option("--on", "on_text", default=None, help="The day the round is being worked.")
@pass_desk
def choices(desk: Desk, site_id: str, on_text: str | None) -> None:
    """Every product that could go on a site, allowed ones first."""
    on = day_or_today(on_text, desk.zone_name)
    opened = desk.open()
    try:
        found = larvicide.choices(opened, site_id, on)
        names = {one.id: one.name for one in products.all_products(opened)}
    finally:
        opened.close()
    echo_rows(
        ["product", "name", "rate", "amount", "allowed", "why not"],
        [
            [
                one.product,
                names.get(one.product, one.product),
                str(one.rate) if one.rate else "-",
                str(one.amount) if one.amount else "-",
                "yes" if one.allowed else "no",
                one.refusals[0].rule if one.refusals else "",
            ]
            for one in found
        ],
    )


@treat.command("apply")
@click.argument("site_id")
@click.argument("lot_id")
@click.option("--by", "applicator", required=True, help="Which licence holder made it.")
@click.option("--at", "at_text", default=None, help="When it went on.")
@click.option("--extent", default=None, help="How much of the site, if not all of it.")
@click.option(
    "--strength",
    default=larvicide.MIDDLE,
    type=click.Choice(larvicide.STRENGTHS),
    help="Where in the label range to work.",
)
@click.option("--rate", "rate_text", default=None, help="A rate of your own, such as 6 lb.")
@click.option("--product", "product_name", default=None, help="Confirm the lot is this product.")
@click.option("--equipment", default="", help="What it went on with.")
@click.option("--inspection", default=None, help="The inspection that prompted it.")
@click.option("--note", default="", help="Anything worth writing down.")
@pass_desk
def apply(
    desk: Desk,
    site_id: str,
    lot_id: str,
    applicator: str,
    at_text: str | None,
    extent: str | None,
    strength: str,
    rate_text: str | None,
    product_name: str | None,
    equipment: str,
    inspection: str | None,
    note: str,
) -> None:
    """Make one application and draw the product off a lot."""
    opened = desk.open()
    try:
        site = sites.get(opened, site_id)
        made = larvicide.treat(
            opened,
            applicator,
            site_id,
            lot_id,
            moment_or_now(at_text, desk.zone_name),
            product_id=product_name,
            extent=None if extent is None else read_quantity(extent),
            strength=strength,
            rate=_rate(rate_text, site.extent.unit),
            equipment=equipment,
            inspection=inspection,
            note=note,
        )
    finally:
        opened.close()
    click.echo(f"{made.id}  {made.line()}")


@treat.command("list")
@click.option("--from", "start_text", required=True, help="First day of the window.")
@click.option("--to", "end_text", required=True, help="Last day of the window.")
@click.option("--site", "site_id", default=None, help="Only this site.")
@click.option("--product", "product_name", default=None, help="Only this product.")
@pass_desk
def list_them(
    desk: Desk,
    start_text: str,
    end_text: str,
    site_id: str | None,
    product_name: str | None,
) -> None:
    """Every treatment over a window."""
    opened = desk.open()
    try:
        product_id = None if product_name is None else products.resolve(opened, product_name).id
        found = treatments.between(
            opened,
            clock.day(start_text),
            clock.day(end_text),
            site_id=site_id,
            product_id=product_id,
        )
        names = {one.id: one.name for one in products.all_products(opened)}
    finally:
        opened.close()
    echo_rows(
        ["day", "treatment", "site", "product", "extent", "amount", "rate", "by"],
        [
            [
                one.on.isoformat(),
                one.id,
                one.site,
                names.get(one.product, one.product),
                str(one.extent),
                str(one.amount),
                str(one.rate),
                one.applicator,
            ]
            for one in found
        ],
    )


@treat.command("show")
@click.argument("treatment_id")
@pass_desk
def show(desk: Desk, treatment_id: str) -> None:
    """One treatment in full."""
    opened = desk.open()
    try:
        made = treatments.get(opened, treatment_id)
        site = sites.get(opened, made.site)
        product = products.get(opened, made.product)
    finally:
        opened.close()
    echo_pairs(
        [
            ("treatment", made.id),
            ("site", f"{site.id} {site.name}"),
            ("habitat", site.kind.name),
            ("product", f"{product.id} {product.name}"),
            ("registration", product.registration),
            ("active", f"{product.active} at {product.percent:g} percent"),
            ("lot", made.lot),
            ("at", clock.stamp(made.at, desk.zone_name)),
            ("week", made.week),
            ("applicator", made.applicator),
            ("licence", made.licence or "-"),
            ("extent", str(made.extent)),
            ("amount", str(made.amount)),
            ("rate", str(made.rate)),
            ("active applied", str(made.active(product.percent))),
            ("equipment", made.equipment or "-"),
            ("inspection", made.inspection or "-"),
            ("note", made.note or "-"),
        ],
    )


@treat.command("season")
@click.argument("site_id")
@click.argument("year", type=int)
@pass_desk
def season(desk: Desk, site_id: str, year: int) -> None:
    """How much active ingredient a site took in a season."""
    opened = desk.open()
    try:
        found = larvicide.active_applied(opened, site_id, year)
        site = sites.get(opened, site_id)
    finally:
        opened.close()
    click.echo(f"{site.id} {site.name}, {site.extent}, {year}\n")
    echo_rows(
        ["active ingredient", "applied"],
        [[name, str(amount)] for name, amount in sorted(found.items())],
    )
