"""Reading and writing machines and the calibrations run on them."""

from __future__ import annotations

import datetime as dt

from dipcount import ids
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.equipment import Calibration, Machine
from dipcount.store.book import Book
from dipcount.units import Quantity

_MACHINE = "id, kind, maker, model, serial, nominal, swath_ft, added_on, retired_on, note"
_MACHINE_VALUES = (
    ":id, :kind, :maker, :model, :serial, :nominal, :swath_ft, :added_on, :retired_on, :note"
)
_CALIBRATION = "id, equipment, on_day, tested_by, flow, droplet, swath_ft, speed_mph, note"
_CALIBRATION_VALUES = (
    ":id, :equipment, :on_day, :tested_by, :flow, :droplet, :swath_ft, :speed_mph, :note"
)


def numbers(book: Book) -> list[str]:
    """Every machine id already issued."""
    return [str(row["id"]) for row in book.all("SELECT id FROM equipment")]


def add(
    book: Book,
    kind: str,
    maker: str,
    model: str,
    serial: str,
    added_on: dt.date,
    *,
    nominal: Quantity | None = None,
    swath_ft: float = 0.0,
    note: str = "",
) -> Machine:
    """Put a machine on the books."""
    if find_by_serial(book, serial) is not None:
        raise Duplicate("machine", serial)
    made = Machine(
        id=ids.next_serial("equipment", numbers(book)),
        kind=kind,
        maker=maker,
        model=model,
        serial=serial,
        added_on=added_on,
        nominal=nominal,
        swath_ft=swath_ft,
        note=note,
    )
    book.run(f"INSERT INTO equipment ({_MACHINE}) VALUES ({_MACHINE_VALUES})", made.to_row())
    return made


def get(book: Book, equipment_id: str) -> Machine:
    """One machine by id."""
    row = book.one(f"SELECT {_MACHINE} FROM equipment WHERE id = ?", (equipment_id,))
    if row is None:
        raise NotFound("machine", equipment_id)
    return Machine.from_row(row)


def find_by_serial(book: Book, serial: str) -> Machine | None:
    """One machine by serial number, or nothing."""
    row = book.one(f"SELECT {_MACHINE} FROM equipment WHERE serial = ?", (serial,))
    return None if row is None else Machine.from_row(row)


def resolve(book: Book, text: str) -> Machine:
    """A machine by id or by serial number."""
    if ids.looks_like("equipment", text):
        return get(book, text)
    found = find_by_serial(book, text)
    if found is None:
        raise NotFound("machine", text)
    return found


def all_machines(book: Book, *, kind: str | None = None) -> list[Machine]:
    """Every machine, optionally of one kind."""
    where = " WHERE kind = ?" if kind else ""
    params = (kind,) if kind else ()
    rows = book.all(f"SELECT {_MACHINE} FROM equipment{where} ORDER BY id", params)
    return [Machine.from_row(row) for row in rows]


def in_service(book: Book, on: dt.date, *, kind: str | None = None) -> list[Machine]:
    """Every machine in service on a day."""
    return [one for one in all_machines(book, kind=kind) if one.in_service(on)]


def retire(book: Book, equipment_id: str, on: dt.date, why: str = "") -> Machine:
    """Take a machine out of service."""
    machine = get(book, equipment_id)
    if machine.retired_on is not None:
        raise RuleViolation(
            "equipment.retired",
            f"{equipment_id} went out of service on {machine.retired_on}",
        )
    if on < machine.added_on:
        raise RuleViolation(
            "equipment.retired",
            "a machine cannot be retired before it arrived",
        )
    note = f"{machine.note}\nretired: {why}".strip() if why else machine.note
    book.run(
        "UPDATE equipment SET retired_on = ?, note = ? WHERE id = ?",
        (on.isoformat(), note, equipment_id),
    )
    return get(book, equipment_id)


def calibration_numbers(book: Book, on: dt.date) -> list[str]:
    """Every calibration id already issued for a day."""
    rows = book.all("SELECT id FROM calibration WHERE id LIKE ?", (f"CA-{on:%y%m%d}-%",))
    return [str(row["id"]) for row in rows]


def calibrate(
    book: Book,
    equipment_id: str,
    on: dt.date,
    tested_by: str,
    flow: Quantity,
    *,
    droplet: float | None = None,
    swath_ft: float | None = None,
    speed_mph: float = 0.0,
    note: str = "",
) -> Calibration:
    """Record one check of one machine."""
    machine = resolve(book, equipment_id)
    if not machine.in_service(on):
        raise RuleViolation(
            "equipment.retired",
            f"{machine.id} was not in service on {on.isoformat()}",
        )
    made = Calibration(
        id=ids.next_dated("calibration", on, calibration_numbers(book, on)),
        equipment=machine.id,
        on=on,
        tested_by=tested_by,
        flow=flow,
        droplet=droplet,
        swath_ft=machine.swath_ft if swath_ft is None else swath_ft,
        speed_mph=speed_mph,
        note=note,
    )
    book.run(
        f"INSERT INTO calibration ({_CALIBRATION}) VALUES ({_CALIBRATION_VALUES})",
        made.to_row(),
    )
    return get_calibration(book, made.id)


def get_calibration(book: Book, calibration_id: str) -> Calibration:
    """One calibration by id."""
    row = book.one(f"SELECT {_CALIBRATION} FROM calibration WHERE id = ?", (calibration_id,))
    if row is None:
        raise NotFound("calibration", calibration_id)
    return Calibration.from_row(row)


def calibrations_for(
    book: Book,
    equipment_id: str,
    *,
    since: dt.date | None = None,
) -> list[Calibration]:
    """Every calibration of one machine, oldest first."""
    clauses = ["equipment = ?"]
    params: list[object] = [equipment_id]
    if since is not None:
        clauses.append("on_day >= ?")
        params.append(since.isoformat())
    rows = book.all(
        f"SELECT {_CALIBRATION} FROM calibration WHERE {' AND '.join(clauses)} ORDER BY on_day, id",
        params,
    )
    return [Calibration.from_row(row) for row in rows]


def last_calibration(
    book: Book,
    equipment_id: str,
    *,
    on: dt.date | None = None,
) -> Calibration | None:
    """The most recent calibration of a machine, up to a day if given."""
    found = calibrations_for(book, equipment_id)
    if on is not None:
        found = [one for one in found if one.on <= on]
    return found[-1] if found else None
