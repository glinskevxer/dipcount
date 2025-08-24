"""Commands for the shed: deliveries, stock and recalls."""

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
from dipcount.model.lot import REASONS
from dipcount.store import inventory as store
from dipcount.store import products


@click.group()
def lot() -> None:
    """What came in, what is left, and what came off which code."""


@lot.command("receive")
@click.argument("product_name")
@click.argument("code")
@click.argument("quantity")
@click.option("--on", "on_text", default=None, help="The day it arrived.")
@click.option("--expires", "expires_text", default=None, help="The date on the container.")
@click.option("--held-at", default="", help="Where in the shed it is.")
@click.option("--note", default="", help="Anything worth knowing about it.")
@pass_desk
def receive(
    desk: Desk,
    product_name: str,
    code: str,
    quantity: str,
    on_text: str | None,
    expires_text: str | None,
    held_at: str,
    note: str,
) -> None:
    """Book a delivery in."""
    with desk.book() as opened:
        made = store.receive(
            opened,
            product_name,
            code,
            read_quantity(quantity),
            day_or_today(on_text, desk.zone_name),
            expires_on=None if expires_text is None else clock.day(expires_text),
            held_at=held_at,
            note=note,
        )
    click.echo(f"{made.id}  {made.code}  {made.quantity}")


@lot.command("list")
@click.option("--product", "product_name", default=None, help="Only lots of this product.")
@pass_desk
def list_them(desk: Desk, product_name: str | None) -> None:
    """Every lot the shed has had, with what is left of it."""
    with desk.book() as opened:
        product_id = None if product_name is None else products.resolve(opened, product_name).id
        holdings = store.holdings(opened, product_id=product_id)
        names = {one.id: one.name for one in products.all_products(opened)}
    echo_rows(
        ["lot", "product", "code", "received", "expires", "in", "left"],
        [
            [
                one.lot.id,
                names.get(one.lot.product, one.lot.product),
                one.lot.code,
                one.lot.received_on.isoformat(),
                one.lot.expires_on.isoformat() if one.lot.expires_on else "-",
                str(one.lot.quantity),
                str(one.left),
            ]
            for one in holdings
        ],
    )


@lot.command("show")
@click.argument("lot_id")
@pass_desk
def show(desk: Desk, lot_id: str) -> None:
    """One lot, what is left of it, and every draw off it."""
    with desk.book() as opened:
        holding = store.stock(opened, lot_id)
        made = store.draws(opened, lot_id)
        product = products.get(opened, holding.lot.product)
    echo_pairs(
        [
            ("lot", holding.lot.id),
            ("product", f"{product.id} {product.name}"),
            ("code", holding.lot.code),
            ("received", holding.lot.received_on.isoformat()),
            ("expires", holding.lot.expires_on.isoformat() if holding.lot.expires_on else "-"),
            ("held at", holding.lot.held_at or "-"),
            ("came in", str(holding.lot.quantity)),
            ("drawn", str(holding.drawn)),
            ("left", str(holding.left)),
            ("note", holding.lot.note or "-"),
        ],
    )
    if made:
        click.echo("")
        echo_rows(
            ["day", "amount", "reason", "for", "by"],
            [
                [
                    one.on.isoformat(),
                    str(one.amount),
                    one.reason,
                    one.reference or "-",
                    one.actor,
                ]
                for one in made
            ],
        )


@lot.command("draw")
@click.argument("lot_id")
@click.argument("amount")
@click.option("--reason", default="disposed", type=click.Choice(REASONS), help="What it was for.")
@click.option("--at", "at_text", default=None, help="When it came off the shelf.")
@click.option("--for", "reference", default="", help="The record it belongs to.")
@pass_desk
def draw(
    desk: Desk,
    lot_id: str,
    amount: str,
    reason: str,
    at_text: str | None,
    reference: str,
) -> None:
    """Take an amount off a lot without making a treatment."""
    with desk.book() as opened:
        made = store.draw(
            opened,
            lot_id,
            read_quantity(amount),
            moment_or_now(at_text, desk.zone_name),
            desk.actor,
            reason=reason,
            reference=reference,
        )
        left = store.stock(opened, lot_id).left
    click.echo(f"{made.amount} {made.reason} off {made.lot}, {left} left")


@lot.command("expiring")
@click.option("--on", "on_text", default=None, help="The day to look from.")
@click.option("--days", default=60, type=int, help="How far ahead to look.")
@pass_desk
def expiring(desk: Desk, on_text: str | None, days: int) -> None:
    """Every lot with something left that goes out of date soon."""
    on = day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        found = store.expiring(opened, on, days)
        names = {one.id: one.name for one in products.all_products(opened)}
    echo_rows(
        ["lot", "product", "code", "expires", "left", "days"],
        [
            [
                one.lot.id,
                names.get(one.lot.product, one.lot.product),
                one.lot.code,
                one.lot.expires_on.isoformat() if one.lot.expires_on else "-",
                str(one.left),
                str((one.lot.expires_on - on).days) if one.lot.expires_on else "-",
            ]
            for one in found
        ],
    )


@lot.command("recall")
@click.argument("product_name")
@click.argument("code")
@pass_desk
def recall(desk: Desk, product_name: str, code: str) -> None:
    """Every draw ever made off one manufacturer code."""
    with desk.book() as opened:
        product = products.resolve(opened, product_name)
        found = store.recall(opened, product.id, code)
    click.echo(f"{product.name} lot {code}\n")
    echo_rows(
        ["day", "amount", "reason", "for", "by"],
        [
            [one.on.isoformat(), str(one.amount), one.reason, one.reference or "-", one.actor]
            for one in found
        ],
    )
