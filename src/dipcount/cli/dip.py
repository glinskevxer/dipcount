"""Commands for larval surveillance: the round, the dipper and the verdict."""

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
)
from dipcount.model.inspection import STAGES, Tally, stage_name
from dipcount.service import survey
from dipcount.store import inspections, sites, zones


@click.group()
def dip() -> None:
    """Work the larval round and record what came out of the water."""


@dip.command("record")
@click.argument("site_id")
@click.option("--at", "at_text", default=None, help="When the visit was, local time.")
@click.option("--dips", default=0, type=int, help="How many dips were taken.")
@click.option("--dry", is_flag=True, help="The site held no water.")
@click.option(
    "--count",
    "counts",
    nargs=3,
    multiple=True,
    metavar="SPECIES STAGE N",
    help="A tally: species code or a dash, stage R 1 2 3 4 or P, and a number.",
)
@click.option("--note", default="", help="Anything worth writing down.")
@pass_desk
def record(
    desk: Desk,
    site_id: str,
    at_text: str | None,
    dips: int,
    dry: bool,
    counts: tuple[tuple[str, str, str], ...],
    note: str,
) -> None:
    """Record one visit to a site."""
    tallies = tuple(
        Tally("" if code in ("-", "") else code.upper(), stage.upper(), int(number))
        for code, stage, number in counts
    )
    with desk.book() as opened:
        made, found = survey.inspect(
            opened,
            desk.actor,
            site_id,
            moment_or_now(at_text, desk.zone_name),
            water=not dry,
            dips=dips,
            tallies=tallies,
            note=note,
        )
    click.echo(f"{made.id}  {found.line()}")
    for sentence in found.why():
        click.echo(f"  {sentence}")


@dip.command("due")
@click.option("--on", "on_text", default=None, help="The day the round is being worked.")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@pass_desk
def due(desk: Desk, on_text: str | None, zone_name: str | None) -> None:
    """Every site that is due for a visit."""
    on = day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        waiting = survey.due(opened, on, zone_id=zone_id)
    echo_rows(
        ["site", "zone", "name", "habitat", "due", "days"],
        [
            [
                site.id,
                site.zone,
                site.name,
                site.habitat,
                when.isoformat(),
                str((on - when).days),
            ]
            for site, when in waiting
        ],
    )


@dip.command("show")
@click.argument("inspection_id")
@pass_desk
def show(desk: Desk, inspection_id: str) -> None:
    """One inspection, its tallies and the verdict it produced."""
    with desk.book() as opened:
        made = inspections.get(opened, inspection_id)
        site = sites.get(opened, made.site)
        found = survey.assess(site, made)
    echo_pairs(
        [
            ("inspection", made.id),
            ("site", f"{site.id} {site.name}"),
            ("habitat", site.kind.name),
            ("at", clock.stamp(made.at, desk.zone_name)),
            ("week", made.week),
            ("inspector", made.inspector),
            ("water", "yes" if made.water else "no"),
            ("dips", str(made.dips)),
            ("larvae", str(made.larvae)),
            ("pupae", str(made.pupae)),
            ("rafts", str(made.rafts)),
            ("per dip", f"{made.per_dip:.2f}"),
            ("threshold", f"{found.threshold:.2f}"),
            ("verdict", found.verdict),
            ("next visit", found.next_visit.isoformat()),
            ("note", made.note or "-"),
        ],
    )
    if made.tallies:
        click.echo("")
        echo_rows(
            ["species", "stage", "count"],
            [
                [one.species or "-", stage_name(one.stage), str(one.tally)]
                for one in sorted(made.tallies, key=lambda one: (one.species, one.stage))
            ],
        )


@dip.command("site")
@click.argument("site_id")
@click.option("--since", "since_text", default=None, help="Only from this day on.")
@pass_desk
def by_site(desk: Desk, site_id: str, since_text: str | None) -> None:
    """Every visit to one site, judged again."""
    since = None if since_text is None else clock.day(since_text)
    with desk.book() as opened:
        made = inspections.for_site(opened, site_id, since=since)
        found = survey.history(opened, site_id, since=since)
    echo_rows(
        ["inspection", "day", "dips", "larvae", "pupae", "per dip", "verdict"],
        [
            [
                one.id,
                one.on.isoformat(),
                str(one.dips),
                str(one.larvae),
                str(one.pupae),
                f"{one.per_dip:.2f}",
                verdict.verdict,
            ]
            for one, verdict in zip(made, found, strict=True)
        ],
    )


@dip.command("week")
@click.argument("label")
@pass_desk
def by_week(desk: Desk, label: str) -> None:
    """Every visit made in one reporting week."""
    year, week = clock.read_week(label)
    with desk.book() as opened:
        made = inspections.in_week(opened, year, week)
        rows = []
        for one in made:
            site = sites.get(opened, one.site)
            found = survey.assess(site, one)
            rows.append(
                [
                    one.on.isoformat(),
                    one.id,
                    site.name,
                    str(one.dips),
                    str(one.larvae),
                    f"{one.per_dip:.2f}",
                    found.verdict,
                ],
            )
    click.echo(f"{label}  {clock.week_start(year, week)} to {clock.week_end(year, week)}\n")
    echo_rows(["day", "inspection", "site", "dips", "larvae", "per dip", "verdict"], rows)


@dip.command("stages")
def stages() -> None:
    """What the stage codes on a tally mean."""
    echo_rows(["code", "stage"], [[one, stage_name(one)] for one in STAGES])
