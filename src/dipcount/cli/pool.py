"""Commands for sending pools to the laboratory and taking results back."""

from __future__ import annotations

import click

from dipcount import clock, species
from dipcount.cli.options import Desk, day_or_today, echo_pairs, echo_rows, pass_desk
from dipcount.model.pool import MAX_POOL, OUTCOMES, PENDING, POSITIVE
from dipcount.service import virus as service
from dipcount.store import pools as store
from dipcount.store import traps


@click.group()
def pool() -> None:
    """Send vials to the laboratory and record what comes back."""


@pool.command("submit")
@click.argument("collection_id")
@click.argument("code")
@click.argument("size", type=int)
@click.option("--on", "on_text", default=None, help="The day it went to the laboratory.")
@click.option("--lab", default="", help="Which laboratory it went to.")
@click.option("--note", default="", help="Anything worth writing down.")
@pass_desk
def submit(
    desk: Desk,
    collection_id: str,
    code: str,
    size: int,
    on_text: str | None,
    lab: str,
    note: str,
) -> None:
    """Send one vial of one species out of one jar."""
    with desk.book() as opened:
        made = store.submit(
            opened,
            collection_id,
            code.upper(),
            size,
            day_or_today(on_text, desk.zone_name),
            lab=lab,
            note=note,
        )
        left = traps.get_collection(opened, collection_id).females_of(code.upper())
        already = store.pooled(opened, collection_id, code.upper())
    click.echo(f"{made.id}  {made.size} {made.species}  {already} of {left} pooled")


@pool.command("result")
@click.argument("pool_id")
@click.argument("virus_name")
@click.argument("outcome", type=click.Choice(OUTCOMES))
@click.option("--on", "on_text", default=None, help="The day the laboratory ran it.")
@click.option("--ct", type=float, default=None, help="Cycle threshold, on a positive only.")
@pass_desk
def result(
    desk: Desk,
    pool_id: str,
    virus_name: str,
    outcome: str,
    on_text: str | None,
    ct: float | None,
) -> None:
    """Write one virus result against one pool."""
    tested = None if outcome == PENDING else day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        after = store.report(opened, pool_id, virus_name, outcome, tested, ct)
    click.echo(f"{after.id}  {virus_name}  {outcome}")


@pool.command("show")
@click.argument("pool_id")
@pass_desk
def show(desk: Desk, pool_id: str) -> None:
    """One pool and everything the laboratory has said about it."""
    with desk.book() as opened:
        found = store.get(opened, pool_id)
        collection = traps.get_collection(opened, found.collection)
        trap = traps.get(opened, collection.trap)
    echo_pairs(
        [
            ("pool", found.id),
            ("collection", found.collection),
            ("trap", f"{trap.id} {trap.name}"),
            ("pulled", collection.on.isoformat()),
            ("week", collection.week),
            ("species", f"{found.species} {found.sort.binomial}"),
            ("size", str(found.size)),
            ("submitted", found.submitted_on.isoformat()),
            ("lab", found.lab or "-"),
            ("note", found.note or "-"),
        ],
    )
    click.echo("")
    echo_rows(
        ["virus", "outcome", "tested", "ct", "carries"],
        [
            [
                one,
                found.outcome(one),
                (lambda got: got.tested_on.isoformat() if got and got.tested_on else "-")(
                    found.result(one),
                ),
                (lambda got: f"{got.ct:g}" if got and got.ct is not None else "-")(
                    found.result(one),
                ),
                "yes" if found.could_carry(one) else "no",
            ]
            for one in species.viruses()
        ],
    )


@pool.command("waiting")
@click.option("--virus", "virus_name", default=species.WNV, help="Which virus.")
@pass_desk
def waiting(desk: Desk, virus_name: str) -> None:
    """Every pool with nothing back yet for a virus."""
    with desk.book() as opened:
        found = store.outstanding(opened, virus_name)
    echo_rows(
        ["pool", "collection", "species", "size", "submitted", "lab"],
        [
            [
                one.id,
                one.collection,
                one.species,
                str(one.size),
                one.submitted_on.isoformat(),
                one.lab or "-",
            ]
            for one in found
        ],
    )


@pool.command("week")
@click.argument("label")
@click.option("--virus", "virus_name", default=species.WNV, help="Which virus to show.")
@pass_desk
def by_week(desk: Desk, label: str, virus_name: str) -> None:
    """Every pool made out of a jar pulled in one reporting week."""
    year, week = clock.read_week(label)
    with desk.book() as opened:
        found = service.pools_in_week(opened, year, week)
    echo_rows(
        ["pool", "collection", "species", "size", "outcome", "counts"],
        [
            [
                one.id,
                one.collection,
                one.species,
                str(one.size),
                one.outcome(virus_name),
                "yes" if one.could_carry(virus_name) and one.counts_for(virus_name) else "no",
            ]
            for one in found
        ],
    )


@pool.command("limits")
def limits() -> None:
    """What the laboratory will and will not take."""
    echo_pairs(
        [
            ("largest pool", str(MAX_POOL)),
            ("outcomes", ", ".join(OUTCOMES)),
            ("viruses", ", ".join(species.viruses())),
            ("counts in a rate", f"{POSITIVE} and negative only"),
        ],
    )
