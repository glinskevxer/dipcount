"""Whether a machine may be used, and how fast to drive it.

A calibration is not a certificate that gets filed. It is three measurements
that between them say what the machine puts on the ground, and each of them
can fail on its own: the flow can drift as a nozzle wears, the droplet
spectrum can coarsen as a pump loses pressure, and the whole thing goes out of
date thirty days after it was measured whatever the numbers said.

The useful direction is the other way round. Given a labelled rate and a
measured flow, there is exactly one driving speed that puts the labelled rate
on the ground at the machine's swath. That figure is what goes on the work
card, and it changes every time the machine is recalibrated.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from dipcount.model.equipment import Calibration, Machine, speed_for
from dipcount.model.product import Label
from dipcount.rules import Refusal
from dipcount.store import equipment, products, sites
from dipcount.store.book import Book
from dipcount.units import Rate


@dataclass(frozen=True)
class Standing:
    """Where one machine stands on a given day."""

    machine: Machine
    on: dt.date
    last: Calibration | None = None

    @property
    def calibrated(self) -> bool:
        """Whether a calibration is in date today."""
        return self.last is not None and self.on <= self.last.due()

    @property
    def due_on(self) -> dt.date | None:
        """When the next calibration falls due."""
        return None if self.last is None else self.last.due()

    @property
    def days_over(self) -> int:
        """How many days past due the machine is, or nothing if it is not."""
        if self.due_on is None or self.on <= self.due_on:
            return 0
        return (self.on - self.due_on).days

    @property
    def flow_ok(self) -> bool:
        """Whether the last measured flow was near the machine's rating."""
        if self.last is None:
            return False
        if self.machine.nominal is None:
            return True
        return self.last.within(self.machine.nominal)

    @property
    def droplet_ok(self) -> bool:
        """Whether the last droplet reading cleared the ceiling."""
        return self.last is not None and self.last.droplet_ok(self.machine.is_ulv)

    @property
    def usable(self) -> bool:
        """Whether the machine may be used today."""
        return (
            self.machine.in_service(self.on)
            and self.calibrated
            and self.flow_ok
            and self.droplet_ok
        )

    def refusals(self) -> list[Refusal]:
        """Every reason this machine may not be used, named."""
        out: list[Refusal] = []
        if not self.machine.in_service(self.on):
            out.append(Refusal("equipment.retired", f"{self.machine.id} is out of service"))
        if self.last is None:
            out.append(
                Refusal("equipment.calibration", f"{self.machine.id} has never been calibrated"),
            )
            return out
        if not self.calibrated:
            out.append(
                Refusal(
                    "equipment.calibration",
                    f"{self.machine.id} was due on {self.due_on} and is {self.days_over} days over",
                ),
            )
        if not self.flow_ok:
            out.append(
                Refusal(
                    "equipment.flow",
                    f"{self.last.flow} is outside ten percent of {self.machine.nominal}",
                ),
            )
        if not self.droplet_ok:
            out.append(
                Refusal(
                    "equipment.droplet",
                    f"{self.machine.id} last read"
                    f" {self.last.droplet if self.last.droplet else 'nothing'}"
                    " for droplet size",
                ),
            )
        return out

    def line(self) -> str:
        """One line for a shop sheet."""
        state = "usable" if self.usable else "held"
        due = self.due_on.isoformat() if self.due_on else "never calibrated"
        return f"{self.machine.id}  {self.machine.model}  {state}  due {due}"


def standing(book: Book, equipment_id: str, on: dt.date) -> Standing:
    """Where one machine stands on a day."""
    machine = equipment.resolve(book, equipment_id)
    return Standing(
        machine=machine,
        on=on,
        last=equipment.last_calibration(book, machine.id, on=on),
    )


def check(book: Book, equipment_id: str, on: dt.date) -> Refusal | None:
    """The first reason a machine may not be used, if there is one."""
    found = standing(book, equipment_id, on).refusals()
    return found[0] if found else None


def usable(book: Book, on: dt.date, *, kind: str | None = None) -> list[Machine]:
    """Every machine that may be used today."""
    return [
        one
        for one in equipment.in_service(book, on, kind=kind)
        if standing(book, one.id, on).usable
    ]


def due(book: Book, on: dt.date, *, within: int = 0) -> list[Standing]:
    """Every machine due for calibration, most overdue first."""
    out: list[Standing] = []
    for one in equipment.in_service(book, on):
        where = standing(book, one.id, on)
        if where.due_on is None or where.due_on <= on + dt.timedelta(days=within):
            out.append(where)
    return sorted(out, key=lambda one: (one.due_on or dt.date.min, one.machine.id))


def board(book: Book, on: dt.date) -> list[Standing]:
    """Where every machine stands, by id."""
    return [standing(book, one.id, on) for one in equipment.all_machines(book)]


def target_speed(
    book: Book,
    equipment_id: str,
    wanted: Rate,
    on: dt.date,
) -> Decimal | None:
    """How fast to drive to hit a rate, on the last measured flow."""
    where = standing(book, equipment_id, on)
    if where.last is None:
        return None
    swath = where.last.swath_ft or where.machine.swath_ft
    if swath <= 0:
        return None
    return speed_for(where.last.flow, wanted, swath)


def speed_for_label(
    book: Book,
    equipment_id: str,
    site_id: str,
    product_id: str,
    on: dt.date,
) -> tuple[Rate, Decimal] | None:
    """The label's middle rate for a site, and the speed that hits it."""
    site = sites.get(book, site_id)
    product = products.resolve(book, product_id)
    label: Label | None = product.label_for(site.habitat)
    if label is None:
        return None
    wanted = label.middle()
    speed = target_speed(book, equipment_id, wanted, on)
    return None if speed is None else (wanted, speed)
