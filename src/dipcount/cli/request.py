"""Commands for the calls the public makes."""

from __future__ import annotations

import click

from dipcount import clock
from dipcount.cli.options import (
    Desk,
    echo_pairs,
    echo_rows,
    moment_or_now,
    pass_desk,
    zone_id,
)
from dipcount.model.request import answer_hours, kinds, why
from dipcount.service import requests as service
from dipcount.store import requests as store


@click.group()
def call() -> None:
    """Take calls, answer them, and see what is running out of time."""


@call.command("kinds")
def list_kinds() -> None:
    """Every kind of call, how long it has, and why."""
    echo_rows(
        ["kind", "hours", "why"],
        [[one, str(answer_hours(one)), why(one)] for one in kinds()],
    )


@call.command("take")
@click.argument("address")
@click.option("--kind", required=True, type=click.Choice(kinds()), help="What the call is about.")
@click.option("--zone", "zone_name", required=True, help="Which zone it is in.")
@click.option("--at", "at_text", default=None, help="When the call came in.")
@click.option("--caller", default="", help="Who rang.")
@click.option("--phone", default="", help="How to reach them.")
@click.option("--detail", default="", help="What they said.")
@pass_desk
def take(
    desk: Desk,
    address: str,
    kind: str,
    zone_name: str,
    at_text: str | None,
    caller: str,
    phone: str,
    detail: str,
) -> None:
    """Write a call down as it comes in."""
    with desk.book() as opened:
        made = service.take(
            opened,
            desk.actor,
            kind,
            zone_name,
            moment_or_now(at_text, desk.zone_name),
            address,
            caller=caller,
            phone=phone,
            detail=detail,
        )
        where = service.standing(opened, made.id, made.taken_at)
    click.echo(f"{made.id}  {made.kind}  due {clock.stamp(where.due_at, desk.zone_name)}")
    if where.escalated:
        click.echo(f"  clock cut from {made.hours} hours: the level is {where.level}")


@call.command("assign")
@click.argument("request_id")
@click.argument("who")
@pass_desk
def assign(desk: Desk, request_id: str, who: str) -> None:
    """Put somebody's name against a call."""
    with desk.book() as opened:
        after = store.assign(opened, request_id, who)
    click.echo(f"{after.id} assigned to {after.assigned_to}")


@call.command("answer")
@click.argument("request_id")
@click.option("--at", "at_text", default=None, help="When somebody went out.")
@click.option("--site", "site_id", default=None, help="The site the visit found, if any.")
@pass_desk
def answer(desk: Desk, request_id: str, at_text: str | None, site_id: str | None) -> None:
    """Record a visit to a call."""
    with desk.book() as opened:
        where = service.answer(
            opened,
            desk.actor,
            request_id,
            moment_or_now(at_text, desk.zone_name),
            site_id=site_id,
        )
    took = where.request.answered_in()
    state = "late" if where.late else "in time"
    click.echo(f"{where.request.id}  answered in {took} hours, {state}")


@call.command("close")
@click.argument("request_id")
@click.argument("outcome")
@click.option("--at", "at_text", default=None, help="When it was closed.")
@pass_desk
def close(desk: Desk, request_id: str, outcome: str, at_text: str | None) -> None:
    """Close a call with what came of it."""
    with desk.book() as opened:
        after = service.finish(
            opened,
            desk.actor,
            request_id,
            moment_or_now(at_text, desk.zone_name),
            outcome,
        )
    click.echo(f"{after.id} closed: {after.outcome}")


@call.command("waiting")
@click.option("--at", "at_text", default=None, help="The moment to stand it on.")
@click.option("--zone", "zone_name", default=None, help="Only this zone.")
@click.option("--late", "only_late", is_flag=True, help="Only what has run out of time.")
@pass_desk
def waiting(desk: Desk, at_text: str | None, zone_name: str | None, only_late: bool) -> None:
    """Every call nobody has been out to, tightest clock first."""
    at = moment_or_now(at_text, desk.zone_name)
    with desk.book() as opened:
        zone = zone_id(opened, zone_name)
        found = (
            service.overdue(opened, at, zone_id=zone)
            if only_late
            else service.waiting(opened, at, zone_id=zone)
        )
    echo_rows(
        ["id", "kind", "zone", "address", "taken", "due", "hours left", "late"],
        [
            [
                one.request.id,
                one.request.kind,
                one.request.zone,
                one.request.address,
                clock.stamp(one.request.taken_at, desk.zone_name),
                clock.stamp(one.due_at, desk.zone_name),
                str(one.hours_left),
                "yes" if one.late else "",
            ]
            for one in found
        ],
    )


@call.command("show")
@click.argument("request_id")
@click.option("--at", "at_text", default=None, help="The moment to stand it on.")
@pass_desk
def show(desk: Desk, request_id: str, at_text: str | None) -> None:
    """One call in full."""
    at = moment_or_now(at_text, desk.zone_name)
    with desk.book() as opened:
        where = service.standing(opened, request_id, at)
    made = where.request
    echo_pairs(
        [
            ("id", made.id),
            ("kind", made.kind),
            ("zone", made.zone),
            ("address", made.address),
            ("caller", made.caller or "-"),
            ("phone", made.phone or "-"),
            ("detail", made.detail or "-"),
            ("taken", clock.stamp(made.taken_at, desk.zone_name)),
            ("hours allowed", str(where.hours)),
            ("response level", where.level),
            ("due", clock.stamp(where.due_at, desk.zone_name)),
            ("assigned to", made.assigned_to or "-"),
            (
                "visited",
                clock.stamp(made.visited_at, desk.zone_name) if made.visited_at else "-",
            ),
            ("site found", made.site or "-"),
            ("answered in", str(made.answered_in()) if made.answered_in() else "-"),
            ("late", "yes" if where.late else "no"),
            ("closed", clock.stamp(made.closed_at, desk.zone_name) if made.closed_at else "-"),
            ("outcome", made.outcome or "-"),
        ],
    )


@call.command("season")
@click.option("--from", "start_text", required=True, help="First day of the window.")
@click.option("--to", "end_text", required=True, help="Last day of the window.")
@pass_desk
def season(desk: Desk, start_text: str, end_text: str) -> None:
    """How the calls taken over a window were answered."""
    with desk.book() as opened:
        found = service.performance(opened, clock.day(start_text), clock.day(end_text))
        taken = store.between(opened, clock.day(start_text), clock.day(end_text))
        by_kind: dict[str, int] = {}
        for one in taken:
            by_kind[one.kind] = by_kind.get(one.kind, 0) + 1
    echo_pairs(
        [
            ("window", f"{found.start} to {found.end}"),
            ("calls taken", str(found.taken)),
            ("answered", str(found.answered)),
            ("answered in time", str(found.on_time)),
            ("share in time", f"{found.share_on_time:.0%}"),
            ("median hours", str(found.median_hours) if found.median_hours else "-"),
        ],
    )
    if by_kind:
        click.echo("")
        echo_rows(
            ["kind", "calls"],
            [[kind, str(count)] for kind, count in sorted(by_kind.items())],
        )
