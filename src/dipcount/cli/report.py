"""Commands that print the reports."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import click

from dipcount import clock, species
from dipcount.cli.options import Desk, day_or_today, echo_sheet, pass_desk, zone_id
from dipcount.report import export, season, use_report, weekly
from dipcount.report.sheet import table


@click.group()
def report() -> None:
    """The week, the season, the board, the return and the files."""


@report.command("week")
@click.argument("label")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@click.option("--virus", "virus_name", default=species.WNV, help="Which virus to show.")
@pass_desk
def week(desk: Desk, label: str, zone_name: str | None, virus_name: str) -> None:
    """The week's surveillance and work on one sheet."""
    year, number = clock.read_week(label)
    with desk.book() as opened:
        zone = zone_id(opened, zone_name)
        found = weekly.weekly(opened, year, number, zone_id=zone, virus_name=virus_name)
    click.echo(found.render())


@report.command("season")
@click.argument("year", type=int)
@click.option("--on", "on_text", default=None, help="The day to take it to.")
@click.option("--first", default=season.FIRST_WEEK, type=int, help="First reporting week.")
@click.option("--last", default=season.LAST_WEEK, type=int, help="Last reporting week.")
@click.option("--virus", "virus_name", default=species.WNV, help="Which virus to show.")
@pass_desk
def season_report(
    desk: Desk,
    year: int,
    on_text: str | None,
    first: int,
    last: int,
    virus_name: str,
) -> None:
    """The season to date."""
    on = None if on_text is None else clock.day(on_text)
    with desk.book() as opened:
        found = season.season(
            opened,
            year,
            on=on,
            first=first,
            last=last,
            virus_name=virus_name,
        )
    click.echo(found.render())


@report.command("board")
@click.option("--on", "on_text", default=None, help="The day to stand it on.")
@click.option("--within", default=60, type=int, help="How far ahead to look.")
@pass_desk
def board(desk: Desk, on_text: str | None, within: int) -> None:
    """What is out of date, overdue or unanswered today."""
    on = day_or_today(on_text, desk.zone_name)
    with desk.book() as opened:
        found = season.board(opened, on, within=within)
    click.echo(found.render())


@report.command("use")
@click.option("--from", "start_text", default=None, help="First day of the window.")
@click.option("--to", "end_text", default=None, help="Last day of the window.")
@click.option("--year", type=int, default=None, help="A whole season instead of a window.")
@click.option("--csv", "as_csv", is_flag=True, help="Print comma separated values instead.")
@pass_desk
def use(
    desk: Desk,
    start_text: str | None,
    end_text: str | None,
    year: int | None,
    as_csv: bool,
) -> None:
    """The pesticide use return."""
    with desk.book() as opened:
        if year is not None:
            found = use_report.season(opened, year)
        else:
            if start_text is None or end_text is None:
                message = "give a year, or both ends of a window"
                raise click.UsageError(message)
            found = use_report.use_return(
                opened,
                clock.day(start_text),
                clock.day(end_text),
            )
    if as_csv:
        click.echo(found.csv(), nl=False)
        return
    click.echo(found.render())


@report.command("registers")
def registers() -> None:
    """Every register that can be exported."""
    echo_sheet(table(["register"], [[name] for name in export.names()]))


@report.command("export")
@click.argument("name")
@click.option("--into", required=True, type=click.Path(path_type=Path), help="Where to write.")
@click.option("--from", "start_text", default=None, help="First day, for the dated registers.")
@click.option("--to", "end_text", default=None, help="Last day, for the dated registers.")
@pass_desk
def export_them(
    desk: Desk,
    name: str,
    into: Path,
    start_text: str | None,
    end_text: str | None,
) -> None:
    """Write one register, or all of them, to a directory."""
    window = (
        dt.date(1900, 1, 1) if start_text is None else clock.day(start_text),
        dt.date(2999, 12, 31) if end_text is None else clock.day(end_text),
    )
    with desk.book() as opened:
        made = (
            export.write_all(opened, window, into)
            if name == "all"
            else [export.write(opened, name, window, into)]
        )
    for path in made:
        click.echo(str(path))
    click.echo(f"\n{len(made)} file{'' if len(made) == 1 else 's'}")
