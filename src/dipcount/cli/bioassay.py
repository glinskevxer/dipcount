"""Commands for bottle bioassays and what they say about the shelf."""

from __future__ import annotations

from decimal import Decimal

import click

from dipcount.cli.options import Desk, day_or_today, echo_pairs, echo_rows, pass_desk, zone_id
from dipcount.model.bioassay import CONTROL, CONTROL_CORRECT, CONTROL_VOID, SOURCES, Reading
from dipcount.service import resistance
from dipcount.store import bioassays as store
from dipcount.store import products, sites


def _share(value: Decimal | None) -> str:
    """A percentage for a report, or a dash when nothing was read."""
    return "-" if value is None else f"{value:.1f}%"


@click.group()
def assay() -> None:
    """Bottle assays, and whether what the district sprays still works."""


@assay.command("run")
@click.argument("active")
@click.argument("code")
@click.option("--source", default="field", type=click.Choice(SOURCES), help="Where they came from.")
@click.option("--on", "on_text", default=None, help="The day it was run.")
@click.option("--dose", required=True, type=float, help="Micrograms a bottle.")
@click.option("--minutes", required=True, type=int, help="The diagnostic time.")
@click.option("--zone", "zone_name", default=None, help="Which zone they came from.")
@click.option(
    "--bottle",
    "readings",
    nargs=3,
    multiple=True,
    metavar="LABEL KNOCKED TOTAL",
    help="One bottle at the diagnostic time. Use control for the untreated one.",
)
@click.option("--note", default="", help="Anything worth writing down.")
@pass_desk
def run(
    desk: Desk,
    active: str,
    code: str,
    source: str,
    on_text: str | None,
    dose: float,
    minutes: int,
    zone_name: str | None,
    readings: tuple[tuple[str, str, str], ...],
    note: str,
) -> None:
    """Record one assay and the bottles read at the diagnostic time."""
    bottles = [
        Reading(label, minutes, int(knocked), int(total)) for label, knocked, total in readings
    ]
    with desk.book() as opened:
        zone = zone_id(opened, zone_name)
        made = store.start(
            opened,
            active,
            code.upper(),
            source,
            day_or_today(on_text, desk.zone_name),
            desk.actor,
            dose,
            minutes,
            zone_id=zone,
            readings=bottles,
            note=note,
        )
    click.echo(made.line())
    if made.corrected():
        click.echo("  corrected for what died in the control bottle")


@assay.command("read")
@click.argument("assay_id")
@click.argument("label")
@click.argument("knocked", type=int)
@click.argument("total", type=int)
@click.option("--minute", required=True, type=int, help="The minute the count was taken.")
@pass_desk
def read(desk: Desk, assay_id: str, label: str, knocked: int, total: int, minute: int) -> None:
    """Write one more bottle reading onto an assay."""
    with desk.book() as opened:
        after = store.read(opened, assay_id, label, minute, knocked, total)
    click.echo(after.line())


@assay.command("show")
@click.argument("assay_id")
@pass_desk
def show(desk: Desk, assay_id: str) -> None:
    """One assay, its bottles and what it says."""
    with desk.book() as opened:
        made = store.get(opened, assay_id)
    found = made.mortality()
    echo_pairs(
        [
            ("assay", made.id),
            ("active", made.active),
            ("species", made.species),
            ("source", made.source),
            ("zone", made.zone or "-"),
            ("day", made.on.isoformat()),
            ("by", made.tested_by),
            ("dose", f"{made.dose_ug:g} ug a bottle"),
            ("diagnostic time", f"{made.diagnostic} minutes"),
            ("treated down", _share(made.treated_share(made.diagnostic))),
            ("control down", _share(made.control_share(made.diagnostic))),
            ("corrected", "yes" if made.corrected() else "no"),
            ("mortality", f"{found:.1f}%" if found is not None else "-"),
            ("verdict", made.verdict()),
            ("note", made.note or "-"),
        ],
    )
    if made.readings:
        click.echo("")
        echo_rows(
            ["bottle", "minute", "down", "of", "share"],
            [
                [
                    one.label,
                    str(one.minute),
                    str(one.knocked),
                    str(one.total),
                    f"{one.share:.1f}%",
                ]
                for one in made.readings
            ],
        )


@assay.command("board")
@click.option("--on", "on_text", default=None, help="The day to stand it on.")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@pass_desk
def board(desk: Desk, on_text: str | None, zone_name: str | None) -> None:
    """Every active and species pair, and where it stands."""
    on = day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        zone = zone_id(opened, zone_name)
        found = resistance.board(opened, on, zone_id=zone)
    echo_rows(
        ["active", "mode", "species", "verdict", "run", "age", "suspect"],
        [
            [
                one.active,
                one.mode or "-",
                one.species,
                one.verdict,
                one.assay.on.isoformat() if one.assay else "-",
                str(one.age_days) if one.age_days is not None else "-",
                "yes" if one.suspect else ("stale" if one.stale else ""),
            ]
            for one in found
        ],
    )


@assay.command("advice")
@click.argument("site_id")
@click.option("--on", "on_text", default=None, help="The day the work would be done.")
@pass_desk
def advice(desk: Desk, site_id: str, on_text: str | None) -> None:
    """What the assays and the rotation say about treating a site."""
    on = day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        site = sites.get(opened, site_id)
        rows = []
        for product in products.for_habitat(opened, site.habitat, on=on):
            warned = resistance.warn(opened, site.id, product.id, on)
            spun = resistance.rotation_warning(opened, site.id, product.id, on)
            rows.append(
                [
                    product.id,
                    product.name,
                    product.active,
                    "-" if warned is None else warned.rule,
                    "yes" if spun is not None else "",
                ],
            )
        modes = resistance.rotation(opened, site.id, on)
    click.echo(f"{site.id} {site.name}, {site.kind.name}")
    click.echo(f"last modes used: {', '.join(modes) or 'none'}\n")
    echo_rows(["product", "name", "active", "resistance", "rotation"], rows)


@assay.command("untested")
@click.argument("site_id")
@click.option("--on", "on_text", default=None, help="The day to stand it on.")
@pass_desk
def untested(desk: Desk, site_id: str, on_text: str | None) -> None:
    """Every product and species pair at a site nothing has been run on."""
    on = day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        found = resistance.untested_here(opened, site_id, on)
    echo_rows(["active", "species"], [[active, code] for active, code in found])


@assay.command("controls")
def controls() -> None:
    """What a control bottle does to a result."""
    echo_pairs(
        [
            ("control bottle", CONTROL),
            ("under", f"{CONTROL_CORRECT}% the raw figure stands"),
            ("between", f"{CONTROL_CORRECT}% and {CONTROL_VOID}% it is corrected"),
            ("over", f"{CONTROL_VOID}% the run says nothing"),
        ],
    )
