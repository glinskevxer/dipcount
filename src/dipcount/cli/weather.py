"""Commands for the weather record and what comes out of it."""

from __future__ import annotations

from decimal import Decimal

import click

from dipcount import clock, rules
from dipcount.cli.options import Desk, day_or_today, echo_pairs, echo_rows, pass_desk
from dipcount.model.weather import BASE_F, METHODS, MODIFIED
from dipcount.service import weather as service
from dipcount.store import weather as store
from dipcount.store import zones


@click.group()
def wx() -> None:
    """Stations, daily readings, heat units and flood watches."""


@wx.command("station")
@click.argument("name")
@click.argument("zone_name")
@click.option("--opened", "opened_text", default=None, help="The day it started reading.")
@click.option("--elevation", default=0, type=int, help="Feet above sea level.")
@click.option("--note", default="", help="Anything worth knowing about it.")
@pass_desk
def add_station(
    desk: Desk,
    name: str,
    zone_name: str,
    opened_text: str | None,
    elevation: int,
    note: str,
) -> None:
    """Put a weather station on the books."""
    opened = desk.open()
    try:
        made = store.add_station(
            opened,
            name,
            zone_name,
            day_or_today(opened_text, desk.zone_name),
            elevation=elevation,
            note=note,
        )
    finally:
        opened.close()
    click.echo(f"{made.id}  {made.name}")


@wx.command("stations")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@pass_desk
def list_stations(desk: Desk, zone_name: str | None) -> None:
    """Every station the district reads."""
    opened = desk.open()
    try:
        zone_id = None if zone_name is None else zones.resolve(opened, zone_name).id
        found = store.all_stations(opened, zone_id=zone_id)
    finally:
        opened.close()
    echo_rows(
        ["id", "name", "zone", "opened", "closed"],
        [
            [
                one.id,
                one.name,
                one.zone,
                one.opened_on.isoformat(),
                one.closed_on.isoformat() if one.closed_on else "-",
            ]
            for one in found
        ],
    )


@wx.command("close")
@click.argument("station_id")
@click.option("--on", "on_text", default=None, help="The last day it read.")
@pass_desk
def close_station(desk: Desk, station_id: str, on_text: str | None) -> None:
    """Stop reading a station."""
    opened = desk.open()
    try:
        closed = store.close_station(
            opened,
            station_id,
            day_or_today(on_text, desk.zone_name),
        )
    finally:
        opened.close()
    click.echo(f"{closed.id} closed {closed.closed_on}")


@wx.command("record")
@click.argument("station")
@click.option("--on", "on_text", default=None, help="The day being recorded.")
@click.option("--high", required=True, type=float, help="The day's high, Fahrenheit.")
@click.option("--low", required=True, type=float, help="The day's low, Fahrenheit.")
@click.option("--rain", default=0.0, type=float, help="Rainfall in inches.")
@click.option("--wind", default=0.0, type=float, help="Mean wind in miles an hour.")
@click.option("--note", default="", help="Anything worth writing down.")
@pass_desk
def record(
    desk: Desk,
    station: str,
    on_text: str | None,
    high: float,
    low: float,
    rain: float,
    wind: float,
    note: str,
) -> None:
    """Write one day's reading."""
    opened = desk.open()
    try:
        made = store.record(
            opened,
            station,
            day_or_today(on_text, desk.zone_name),
            high,
            low,
            rain_in=rain,
            wind_mph=wind,
            note=note,
        )
    finally:
        opened.close()
    click.echo(f"{made.id}  {made.on}  {made.high_f:g}/{made.low_f:g}  {made.degree_days()} units")


@wx.command("day")
@click.option("--on", "on_text", default=None, help="The day to show.")
@pass_desk
def day(desk: Desk, on_text: str | None) -> None:
    """Every station's reading for one day."""
    on = day_or_today(on_text, desk.zone_name)
    opened = desk.open()
    try:
        found = store.on_day(opened, on)
        names = {one.id: one.name for one in store.all_stations(opened)}
    finally:
        opened.close()
    echo_rows(
        ["station", "name", "high", "low", "rain", "wind", "units"],
        [
            [
                one.station,
                names.get(one.station, "-"),
                f"{one.high_f:g}",
                f"{one.low_f:g}",
                f"{one.rain_in:g}",
                f"{one.wind_mph:g}",
                str(one.degree_days()),
            ]
            for one in found
        ],
    )


@wx.command("units")
@click.argument("station")
@click.option("--from", "start_text", required=True, help="First day of the window.")
@click.option("--to", "end_text", required=True, help="Last day of the window.")
@click.option("--base", default=float(BASE_F), type=float, help="The base to count above.")
@click.option("--method", default=MODIFIED, type=click.Choice(METHODS), help="How to count.")
@click.option("--strict", is_flag=True, help="Refuse a window with a missing day in it.")
@pass_desk
def units(
    desk: Desk,
    station: str,
    start_text: str,
    end_text: str,
    base: float,
    method: str,
    strict: bool,
) -> None:
    """Add up the heat units over a window."""
    opened = desk.open()
    try:
        found = service.accumulate(
            opened,
            station,
            clock.day(start_text),
            clock.day(end_text),
            base=base,
            method=method,
            strict=strict,
        )
    finally:
        opened.close()
    echo_pairs(
        [
            ("station", found.station),
            ("window", f"{found.start} to {found.end}"),
            ("days", f"{found.counted} of {found.days}"),
            ("base", f"{found.base:g}"),
            ("method", found.method),
            ("units", str(found.total)),
            ("missing", ", ".join(one.isoformat() for one in found.gaps) or "none"),
        ],
    )


@wx.command("forecast")
@click.argument("station")
@click.option("--laid", "laid_text", required=True, help="The day the brood was laid.")
@click.option("--method", default=MODIFIED, type=click.Choice(METHODS), help="How to count.")
@pass_desk
def forecast(desk: Desk, station: str, laid_text: str, method: str) -> None:
    """When a brood laid on a day should be flying."""
    laid = clock.day(laid_text)
    opened = desk.open()
    try:
        found = service.guild_forecast(opened, station, laid, method=method)
    finally:
        opened.close()
    echo_rows(
        ["guild", "units needed", "flying", "habitats"],
        [
            [
                guild,
                str(rules.development(guild)),
                when.isoformat() if when else "not yet",
                ", ".join(service.habitats_at_risk(guild)),
            ]
            for guild, when in sorted(found.items())
        ],
    )


@wx.command("flood")
@click.option("--on", "on_text", default=None, help="The day the round is being planned.")
@click.option(
    "--within",
    default=rules.FLOOD_INTERVAL,
    type=int,
    help="How many days back to look for the rain.",
)
@pass_desk
def flood(desk: Desk, on_text: str | None, within: int) -> None:
    """Floodwater sites whose zone has had enough rain to matter."""
    on = day_or_today(on_text, desk.zone_name)
    opened = desk.open()
    try:
        found = service.flooded(opened, on, within=within)
    finally:
        opened.close()
    click.echo(f"rain of {rules.FLOOD_INCHES} inch or more in the last {within} days\n")
    echo_rows(
        ["site", "zone", "name", "habitat", "extent"],
        [[one.id, one.zone, one.name, one.habitat, str(one.extent)] for one in found],
    )


@wx.command("rain")
@click.argument("station")
@click.option("--from", "start_text", required=True, help="First day of the window.")
@click.option("--to", "end_text", required=True, help="Last day of the window.")
@click.option("--at-least", default=float(rules.FLOOD_INCHES), type=float, help="Inches in a day.")
@pass_desk
def rain(desk: Desk, station: str, start_text: str, end_text: str, at_least: float) -> None:
    """The days that put enough rain down to matter, and the total."""
    start, end = clock.day(start_text), clock.day(end_text)
    opened = desk.open()
    try:
        wet = service.wet_days(opened, station, start, end, at_least=Decimal(str(at_least)))
        total = service.rainfall(opened, station, start, end)
    finally:
        opened.close()
    echo_rows(
        ["day", "rain", "high", "low"],
        [
            [one.on.isoformat(), f"{one.rain_in:g}", f"{one.high_f:g}", f"{one.low_f:g}"]
            for one in wet
        ],
    )
    click.echo(f"\n{total} inches over the window")
