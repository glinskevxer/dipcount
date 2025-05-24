"""Commands for the arbovirus picture: rates, indices and the response level."""

from __future__ import annotations

import click

from dipcount import clock, rules, species
from dipcount.cli.options import Desk, echo_pairs, echo_rows, pass_desk
from dipcount.model.trap import KINDS
from dipcount.service import virus as service
from dipcount.store import zones


@click.group(name="virus")
def arbo() -> None:
    """What the pools and the traps say together."""


@arbo.command("ladder")
def ladder() -> None:
    """The response levels and the vector index each one starts at."""
    echo_rows(
        ["level", "vector index at or above"],
        [[name, str(floor)] for name, floor in rules.ladder()],
    )


@arbo.command("viruses")
def viruses() -> None:
    """Every virus the district tests for and what carries it."""
    echo_rows(
        ["virus", "vectors"],
        [
            [one, ", ".join(kind.code for kind in species.vectors_of(one))]
            for one in species.viruses()
        ],
    )


@arbo.command("week")
@click.argument("label")
@click.option("--virus", "virus_name", default=species.WNV, help="Which virus.")
@click.option("--kind", default="gravid", type=click.Choice(list(KINDS)), help="Which trap kind.")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@pass_desk
def week(
    desk: Desk,
    label: str,
    virus_name: str,
    kind: str,
    zone_name: str | None,
) -> None:
    """The whole picture for one reporting week."""
    year, number = clock.read_week(label)
    opened = desk.open()
    try:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        found = service.picture(opened, year, number, virus_name, kind=kind, zone_id=zone_id)
    finally:
        opened.close()
    echo_pairs(
        [
            ("week", found.label),
            ("virus", found.virus),
            ("trap kind", found.kind),
            ("collections", str(found.abundance.collections)),
            ("trap nights", str(found.abundance.nights)),
            ("vector females", str(found.abundance.females)),
            ("abundance", f"{found.abundance.value:.2f} per night"),
            ("pools in the rate", str(found.rate.pools)),
            ("pools held back", str(found.pools_held)),
            ("positive pools", str(found.rate.positives)),
            ("mosquitoes tested", str(found.rate.mosquitoes)),
            ("minimum rate", f"{found.minimum:.2f} per 1000"),
            ("estimated rate", f"{found.rate.rate:.2f} per 1000"),
            ("interval", f"{found.rate.lower:.2f} to {found.rate.upper:.2f}"),
            ("vector index", f"{found.vector_index:.3f}"),
            ("level", found.level),
        ],
    )
    click.echo("")
    for name in found.reasons:
        click.echo(f"  {rules.clause(name).text}")


@arbo.command("season")
@click.argument("year", type=int)
@click.option("--virus", "virus_name", default=species.WNV, help="Which virus.")
@click.option("--kind", default="gravid", type=click.Choice(list(KINDS)), help="Which trap kind.")
@click.option("--first", default=22, type=int, help="First reporting week.")
@click.option("--last", default=40, type=int, help="Last reporting week.")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@pass_desk
def season(
    desk: Desk,
    year: int,
    virus_name: str,
    kind: str,
    first: int,
    last: int,
    zone_name: str | None,
) -> None:
    """One line for every week of a season."""
    opened = desk.open()
    try:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        weeks = service.season(
            opened,
            year,
            virus_name,
            first=first,
            last=last,
            kind=kind,
            zone_id=zone_id,
        )
    finally:
        opened.close()
    echo_rows(
        ["week", "abundance", "pools", "positive", "rate", "index", "level"],
        [
            [
                one.label,
                f"{one.abundance.value:.2f}",
                str(one.rate.pools),
                str(one.rate.positives),
                f"{one.rate.rate:.2f}",
                f"{one.vector_index:.3f}",
                one.level,
            ]
            for one in weeks
        ],
    )


@arbo.command("first")
@click.argument("year", type=int)
@click.option("--virus", "virus_name", default=species.WNV, help="Which virus.")
@pass_desk
def first(desk: Desk, year: int, virus_name: str) -> None:
    """The earliest week of a season anything came back positive."""
    opened = desk.open()
    try:
        found = service.first_positive(opened, year, virus_name)
    finally:
        opened.close()
    if found is None:
        click.echo(f"nothing positive for {virus_name} in {year}")
        return
    click.echo(found.line())


@arbo.command("peak")
@click.argument("year", type=int)
@click.option("--virus", "virus_name", default=species.WNV, help="Which virus.")
@click.option("--first", "first_week", default=22, type=int, help="First reporting week.")
@click.option("--last", default=40, type=int, help="Last reporting week.")
@pass_desk
def peak(desk: Desk, year: int, virus_name: str, first_week: int, last: int) -> None:
    """The week of a season with the highest vector index."""
    opened = desk.open()
    try:
        found = service.peak(opened, year, virus_name, first=first_week, last=last)
    finally:
        opened.close()
    if found is None:
        click.echo(f"no vector index for {virus_name} in {year}")
        return
    click.echo(found.line())
