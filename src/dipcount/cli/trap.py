"""Commands for the adult trapping round."""

from __future__ import annotations

import click

from dipcount import clock, rules
from dipcount.cli.options import (
    Desk,
    day_or_today,
    echo_pairs,
    echo_rows,
    moment_or_now,
    pass_desk,
)
from dipcount.model.trap import KINDS, Catch
from dipcount.service import trapping
from dipcount.store import traps as store
from dipcount.store import zones


@click.group()
def trap() -> None:
    """Run the trap round and work out what is flying."""


@trap.command("kinds")
def kinds() -> None:
    """The kinds of trap the district runs and what each one is for."""
    echo_rows(
        ["key", "name", "lure", "figure", "note"],
        [
            [
                one.key,
                one.name,
                one.lure,
                str(rules.adult_threshold(one.key)),
                one.note or "-",
            ]
            for one in KINDS.values()
        ],
    )


@trap.command("add")
@click.argument("name")
@click.argument("zone_name")
@click.option("--kind", required=True, type=click.Choice(list(KINDS)), help="What kind of trap.")
@click.option("--on", "on_text", default=None, help="The day it went up.")
@click.option("--lat", "latitude", type=float, default=None, help="Latitude, if it is known.")
@click.option("--lon", "longitude", type=float, default=None, help="Longitude, if it is known.")
@click.option("--note", default="", help="Anything worth knowing about it.")
@pass_desk
def add(
    desk: Desk,
    name: str,
    zone_name: str,
    kind: str,
    on_text: str | None,
    latitude: float | None,
    longitude: float | None,
    note: str,
) -> None:
    """Put a trap station on the books."""
    opened = desk.open()
    try:
        made = store.add(
            opened,
            zone_name,
            name,
            kind,
            day_or_today(on_text, desk.zone_name),
            latitude=latitude,
            longitude=longitude,
            note=note,
        )
    finally:
        opened.close()
    click.echo(f"{made.id}  {made.name}  {made.sort.name}")


@trap.command("list")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@click.option("--kind", default=None, type=click.Choice(list(KINDS)), help="Only this kind.")
@pass_desk
def list_them(desk: Desk, zone_name: str | None, kind: str | None) -> None:
    """Every trap station."""
    opened = desk.open()
    try:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        found = store.all_traps(opened, zone_id=zone_id, kind=kind)
    finally:
        opened.close()
    echo_rows(
        ["id", "name", "zone", "kind", "listed", "retired"],
        [
            [
                one.id,
                one.name,
                one.zone,
                one.kind,
                one.listed_on.isoformat(),
                one.retired_on.isoformat() if one.retired_on else "-",
            ]
            for one in found
        ],
    )


@trap.command("retire")
@click.argument("trap_id")
@click.option("--on", "on_text", default=None, help="The day it came down.")
@click.option("--why", default="", help="Why it came down.")
@pass_desk
def retire(desk: Desk, trap_id: str, on_text: str | None, why: str) -> None:
    """Take a trap off the round."""
    opened = desk.open()
    try:
        gone = store.retire(opened, trap_id, day_or_today(on_text, desk.zone_name), why)
    finally:
        opened.close()
    click.echo(f"{gone.id} retired {gone.retired_on}")


@trap.command("collect")
@click.argument("trap_name")
@click.option("--set", "set_text", default=None, help="When the trap went out.")
@click.option("--pulled", "pulled_text", default=None, help="When it came in.")
@click.option("--broken", is_flag=True, help="The trap did not run.")
@click.option(
    "--catch",
    "catches",
    nargs=3,
    multiple=True,
    metavar="SPECIES SEX N",
    help="What was in the jar: species code, F or M, and a number.",
)
@click.option("--note", default="", help="Anything worth writing down.")
@pass_desk
def collect(
    desk: Desk,
    trap_name: str,
    set_text: str | None,
    pulled_text: str | None,
    broken: bool,
    catches: tuple[tuple[str, str, str], ...],
    note: str,
) -> None:
    """Record one collection off a trap."""
    jar = tuple(Catch(code.upper(), sex.upper(), int(number)) for code, sex, number in catches)
    opened = desk.open()
    try:
        made = trapping.collect(
            opened,
            desk.actor,
            trap_name,
            moment_or_now(set_text, desk.zone_name),
            moment_or_now(pulled_text, desk.zone_name),
            worked=not broken,
            catches=jar,
            note=note,
        )
    finally:
        opened.close()
    if made.worked:
        click.echo(
            f"{made.id}  {made.females} females and {made.males} males"
            f"  {made.nights} nights  {made.index:.2f}/night",
        )
    else:
        click.echo(f"{made.id}  did not run")


@trap.command("due")
@click.option("--on", "on_text", default=None, help="The day the round is being worked.")
@click.option("--every", default=7, type=int, help="How often a trap should be run.")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@pass_desk
def due(desk: Desk, on_text: str | None, every: int, zone_name: str | None) -> None:
    """Every trap that has not been run lately."""
    on = day_or_today(on_text, desk.zone_name)
    opened = desk.open()
    try:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        waiting = trapping.due(opened, on, every=every, zone_id=zone_id)
        rows = []
        for one in waiting:
            last = store.last_for_trap(opened, one.id)
            rows.append(
                [
                    one.id,
                    one.name,
                    one.kind,
                    last.on.isoformat() if last else "never",
                    str((on - last.on).days) if last else "-",
                ],
            )
    finally:
        opened.close()
    echo_rows(["id", "name", "kind", "last run", "days"], rows)


@trap.command("show")
@click.argument("collection_id")
@pass_desk
def show(desk: Desk, collection_id: str) -> None:
    """One collection and what was in the jar."""
    opened = desk.open()
    try:
        made = store.get_collection(opened, collection_id)
        which = store.get(opened, made.trap)
    finally:
        opened.close()
    echo_pairs(
        [
            ("collection", made.id),
            ("trap", f"{which.id} {which.name}"),
            ("kind", which.sort.name),
            ("set", clock.stamp(made.set_at, desk.zone_name)),
            ("pulled", clock.stamp(made.pulled_at, desk.zone_name)),
            ("nights", str(made.nights)),
            ("worked", "yes" if made.worked else "no"),
            ("females", str(made.females)),
            ("males", str(made.males)),
            ("index", f"{made.index:.2f}"),
            ("week", made.week),
            ("note", made.note or "-"),
        ],
    )
    if made.catches:
        click.echo("")
        echo_rows(
            ["species", "sex", "count", "per night"],
            [
                [
                    one.species,
                    one.sex,
                    str(one.tally),
                    f"{made.index_of(one.species):.2f}" if one.sex == "F" else "-",
                ]
                for one in made.catches
            ],
        )


@trap.command("index")
@click.argument("label")
@click.option("--kind", default="gravid", type=click.Choice(list(KINDS)), help="Which trap kind.")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@click.option("--species", "code", default="", help="Only this species code.")
@click.option("--seasons", default=rules.BASELINE_SEASONS, type=int, help="Baseline seasons.")
@pass_desk
def index(
    desk: Desk,
    label: str,
    kind: str,
    zone_name: str | None,
    code: str,
    seasons: int,
) -> None:
    """The index for one reporting week, against the seasons before it."""
    year, week = clock.read_week(label)
    opened = desk.open()
    try:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        found = trapping.trend(
            opened,
            year,
            week,
            kind,
            zone_id=zone_id,
            code=code.upper(),
            seasons=seasons,
        )
    finally:
        opened.close()
    ratio = found.ratio
    echo_pairs(
        [
            ("week", found.index.label),
            ("kind", kind),
            ("species", code.upper() or "all"),
            ("collections", str(found.index.collections)),
            ("dropped", str(found.index.dropped)),
            ("females", str(found.index.females)),
            ("trap nights", str(found.index.nights)),
            ("index", f"{found.index.value:.2f}"),
            ("figure", str(found.index.threshold)),
            ("over figure", "yes" if found.index.over else "no"),
            ("baseline", f"{found.baseline:.2f}" if found.has_baseline else "none"),
            ("seasons", ", ".join(str(one) for one in found.years) or "-"),
            ("ratio", f"{ratio:.2f}" if ratio is not None else "-"),
            ("elevated", "yes" if found.elevated else "no"),
        ],
    )


@trap.command("season")
@click.argument("year", type=int)
@click.option("--kind", default="gravid", type=click.Choice(list(KINDS)), help="Which trap kind.")
@click.option("--first", default=18, type=int, help="First reporting week.")
@click.option("--last", default=40, type=int, help="Last reporting week.")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@pass_desk
def season(
    desk: Desk,
    year: int,
    kind: str,
    first: int,
    last: int,
    zone_name: str | None,
) -> None:
    """One index for every week of a season."""
    opened = desk.open()
    try:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        weeks = trapping.season(opened, year, kind, first=first, last=last, zone_id=zone_id)
    finally:
        opened.close()
    echo_rows(
        ["week", "collections", "females", "nights", "index", "over"],
        [
            [
                one.label,
                str(one.collections),
                str(one.females),
                str(one.nights),
                f"{one.value:.2f}",
                "yes" if one.over else "",
            ]
            for one in weeks
        ],
    )
