"""Commands for the licence register and the credits behind it."""

from __future__ import annotations

from decimal import Decimal

import click

from dipcount import clock
from dipcount.cli.options import Desk, day_or_today, echo_pairs, echo_rows, pass_desk
from dipcount.model.applicator import CATEGORIES, GRADES
from dipcount.service import licensing
from dipcount.store import applicators as store
from dipcount.store import products, sites


@click.group()
def crew() -> None:
    """Who is licensed, for what, and until when."""


@crew.command("add")
@click.argument("name")
@click.argument("licence")
@click.option("--grade", required=True, type=click.Choice(GRADES), help="Grade of licence.")
@click.option(
    "--category",
    "categories",
    multiple=True,
    required=True,
    type=click.Choice(CATEGORIES),
    help="A category the licence covers. Repeat for more than one.",
)
@click.option("--certified", "certified_text", required=True, help="The day it was issued.")
@click.option("--expires", "expires_text", required=True, help="The day it runs out.")
@click.option("--under", "supervisor", default=None, help="Who supervises, for a technician.")
@click.option("--note", default="", help="Anything worth knowing.")
@pass_desk
def add(
    desk: Desk,
    name: str,
    licence: str,
    grade: str,
    categories: tuple[str, ...],
    certified_text: str,
    expires_text: str,
    supervisor: str | None,
    note: str,
) -> None:
    """Put a licence holder on the books."""
    opened = desk.open()
    try:
        made = store.add(
            opened,
            name,
            licence,
            grade,
            tuple(categories),
            clock.day(certified_text),
            clock.day(expires_text),
            supervisor=supervisor,
            note=note,
        )
    finally:
        opened.close()
    click.echo(f"{made.id}  {made.name}  {made.licence}  {made.grade}")


@crew.command("list")
@click.option("--grade", default=None, type=click.Choice(GRADES), help="Only this grade.")
@click.option("--on", "on_text", default=None, help="Only licences in date that day.")
@pass_desk
def list_them(desk: Desk, grade: str | None, on_text: str | None) -> None:
    """Everybody on the licence register."""
    opened = desk.open()
    try:
        found = store.all_applicators(opened, grade=grade)
        if on_text is not None:
            on = day_or_today(on_text, desk.zone_name)
            found = [one for one in found if one.licensed(on)]
    finally:
        opened.close()
    echo_rows(
        ["id", "name", "licence", "grade", "categories", "expires", "under"],
        [
            [
                one.id,
                one.name,
                one.licence,
                one.grade,
                ", ".join(one.categories),
                one.expires_on.isoformat(),
                one.supervisor or "-",
            ]
            for one in found
        ],
    )


@crew.command("show")
@click.argument("who")
@click.option("--on", "on_text", default=None, help="The day to stand it on.")
@pass_desk
def show(desk: Desk, who: str, on_text: str | None) -> None:
    """One licence holder, their standing and their courses."""
    on = day_or_today(on_text, desk.zone_name)
    opened = desk.open()
    try:
        found = store.resolve(opened, who)
        where = licensing.standing(opened, found.id, on)
        courses = store.credits_for(
            opened,
            found.id,
            since=found.cycle_start(),
            until=found.expires_on,
        )
    finally:
        opened.close()
    echo_pairs(
        [
            ("id", found.id),
            ("name", found.name),
            ("licence", found.licence),
            ("grade", found.grade),
            ("categories", ", ".join(found.categories)),
            ("certified", found.certified_on.isoformat()),
            ("expires", found.expires_on.isoformat()),
            ("in date", "yes" if where.licensed else "no"),
            ("days left", str(where.days_left)),
            ("supervisor", found.supervisor or "-"),
            ("hours held", str(where.hours_held)),
            ("hours needed", str(where.hours_needed)),
            ("renewable", "yes" if where.renewable else "no"),
            ("left", found.left_on.isoformat() if found.left_on else "-"),
        ],
    )
    if courses:
        click.echo("")
        echo_rows(
            ["day", "category", "hours", "course"],
            [[one.on.isoformat(), one.category, str(one.hours), one.course] for one in courses],
        )


@crew.command("credit")
@click.argument("who")
@click.argument("course")
@click.option("--on", "on_text", required=True, help="The day the course was sat.")
@click.option("--category", required=True, type=click.Choice(CATEGORIES), help="What it counts in.")
@click.option("--hours", required=True, type=float, help="Credit hours earned.")
@pass_desk
def credit(desk: Desk, who: str, course: str, on_text: str, category: str, hours: float) -> None:
    """Record a course somebody sat."""
    opened = desk.open()
    try:
        found = store.resolve(opened, who)
        made = store.credit(
            opened,
            found.id,
            clock.day(on_text),
            category,
            Decimal(str(hours)),
            course,
        )
    finally:
        opened.close()
    click.echo(f"{found.name}  {made.hours} hours in {made.category}  {made.course}")


@crew.command("renew")
@click.argument("who")
@click.option("--certified", "certified_text", required=True, help="The day it was reissued.")
@click.option("--expires", "expires_text", required=True, help="The day it now runs out.")
@pass_desk
def renew(desk: Desk, who: str, certified_text: str, expires_text: str) -> None:
    """Write a new certification period against a licence."""
    opened = desk.open()
    try:
        found = store.resolve(opened, who)
        after = store.renew(
            opened,
            found.id,
            clock.day(certified_text),
            clock.day(expires_text),
        )
    finally:
        opened.close()
    click.echo(f"{after.name} licensed to {after.expires_on}")


@crew.command("leave")
@click.argument("who")
@click.option("--on", "on_text", default=None, help="The last day worked.")
@pass_desk
def leave(desk: Desk, who: str, on_text: str | None) -> None:
    """Record that somebody has left the district."""
    opened = desk.open()
    try:
        found = store.resolve(opened, who)
        after = store.leave(opened, found.id, day_or_today(on_text, desk.zone_name))
    finally:
        opened.close()
    click.echo(f"{after.name} left {after.left_on}")


@crew.command("expiring")
@click.option("--on", "on_text", default=None, help="The day to look from.")
@click.option("--days", default=90, type=int, help="How far ahead to look.")
@pass_desk
def expiring(desk: Desk, on_text: str | None, days: int) -> None:
    """Every licence that runs out soon, and whether the credits are there."""
    on = day_or_today(on_text, desk.zone_name)
    opened = desk.open()
    try:
        found = licensing.expiring(opened, on, days)
    finally:
        opened.close()
    echo_rows(
        ["id", "name", "grade", "expires", "days", "hours held", "hours needed", "renewable"],
        [
            [
                one.applicator.id,
                one.applicator.name,
                one.applicator.grade,
                one.applicator.expires_on.isoformat(),
                str(one.days_left),
                str(one.hours_held),
                str(one.hours_needed),
                "yes" if one.renewable else "no",
            ]
            for one in found
        ],
    )


@crew.command("for")
@click.argument("site_id")
@click.argument("product_name")
@click.option("--on", "on_text", default=None, help="The day the work would be done.")
@pass_desk
def for_job(desk: Desk, site_id: str, product_name: str, on_text: str | None) -> None:
    """Everybody who could legally make one application."""
    on = day_or_today(on_text, desk.zone_name)
    opened = desk.open()
    try:
        site = sites.get(opened, site_id)
        product = products.resolve(opened, product_name)
        wanted = licensing.category_for(site, product)
        found = licensing.crew(opened, site_id, product.id, on)
    finally:
        opened.close()
    click.echo(f"{site.name}, {product.name}, needs the {wanted} category\n")
    echo_rows(
        ["id", "name", "grade", "categories"],
        [[one.id, one.name, one.grade, ", ".join(one.categories)] for one in found],
    )
