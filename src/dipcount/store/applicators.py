"""Reading and writing applicators and their credits."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from dipcount import ids
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.applicator import CERTIFIED, Applicator, Credit
from dipcount.store import numbering
from dipcount.store.book import Book

_APPLICATOR = (
    "id, name, licence, grade, categories, certified_on, expires_on, supervisor, left_on, note"
)
_VALUES = (
    ":id, :name, :licence, :grade, :categories, :certified_on, :expires_on,"
    " :supervisor, :left_on, :note"
)
_CREDIT = "seq, applicator, on_day, category, hours, course"


def add(
    book: Book,
    name: str,
    licence: str,
    grade: str,
    categories: tuple[str, ...],
    certified_on: dt.date,
    expires_on: dt.date,
    *,
    supervisor: str | None = None,
    note: str = "",
) -> Applicator:
    """Put a licence holder on the books."""
    if find_by_name(book, name) is not None:
        raise Duplicate("applicator", name)
    if find_by_licence(book, licence) is not None:
        raise Duplicate("licence", licence)
    if supervisor is not None:
        boss = get(book, supervisor)
        if boss.grade != CERTIFIED:
            raise RuleViolation(
                "licence.supervision",
                f"{boss.name} is a {boss.grade} and cannot supervise anybody",
            )
    holder = Applicator(
        id=numbering.next_serial(book, "applicator", "applicator"),
        name=name,
        licence=licence,
        grade=grade,
        categories=categories,
        certified_on=certified_on,
        expires_on=expires_on,
        supervisor=supervisor,
        note=note,
    )
    book.run(f"INSERT INTO applicator ({_APPLICATOR}) VALUES ({_VALUES})", holder.to_row())
    return holder


def get(book: Book, applicator_id: str) -> Applicator:
    """One applicator by id."""
    row = book.one(f"SELECT {_APPLICATOR} FROM applicator WHERE id = ?", (applicator_id,))
    if row is None:
        raise NotFound("applicator", applicator_id)
    return Applicator.from_row(row)


def find_by_name(book: Book, name: str) -> Applicator | None:
    """One applicator by name, or nothing."""
    row = book.one(f"SELECT {_APPLICATOR} FROM applicator WHERE name = ?", (name,))
    return None if row is None else Applicator.from_row(row)


def find_by_licence(book: Book, licence: str) -> Applicator | None:
    """One applicator by licence number, or nothing."""
    row = book.one(f"SELECT {_APPLICATOR} FROM applicator WHERE licence = ?", (licence,))
    return None if row is None else Applicator.from_row(row)


def resolve(book: Book, text: str) -> Applicator:
    """An applicator by id, by name or by licence number."""
    if ids.looks_like("applicator", text):
        return get(book, text)
    found = find_by_name(book, text) or find_by_licence(book, text)
    if found is None:
        raise NotFound("applicator", text)
    return found


def all_applicators(book: Book, *, grade: str | None = None) -> list[Applicator]:
    """Every licence holder, optionally of one grade."""
    where = " WHERE grade = ?" if grade else ""
    params = (grade,) if grade else ()
    rows = book.all(f"SELECT {_APPLICATOR} FROM applicator{where} ORDER BY id", params)
    return [Applicator.from_row(row) for row in rows]


def working(book: Book, on: dt.date) -> list[Applicator]:
    """Everybody with a licence in date on a day."""
    return [one for one in all_applicators(book) if one.licensed(on)]


def under(book: Book, supervisor_id: str) -> list[Applicator]:
    """Everybody working under one certified applicator."""
    rows = book.all(
        f"SELECT {_APPLICATOR} FROM applicator WHERE supervisor = ? ORDER BY id",
        (supervisor_id,),
    )
    return [Applicator.from_row(row) for row in rows]


def renew(book: Book, applicator_id: str, certified_on: dt.date, expires_on: dt.date) -> Applicator:
    """Write a new certification period against a licence."""
    holder = get(book, applicator_id)
    if expires_on <= holder.expires_on:
        raise RuleViolation(
            "licence.renewal",
            f"{holder.name} is already licensed to {holder.expires_on}",
        )
    book.run(
        "UPDATE applicator SET certified_on = ?, expires_on = ? WHERE id = ?",
        (certified_on.isoformat(), expires_on.isoformat(), applicator_id),
    )
    return get(book, applicator_id)


def leave(book: Book, applicator_id: str, on: dt.date) -> Applicator:
    """Record that somebody has left the district."""
    holder = get(book, applicator_id)
    if holder.left_on is not None:
        raise RuleViolation("licence.left", f"{holder.name} left on {holder.left_on}")
    book.run("UPDATE applicator SET left_on = ? WHERE id = ?", (on.isoformat(), applicator_id))
    return get(book, applicator_id)


def credit(
    book: Book,
    applicator_id: str,
    on: dt.date,
    category: str,
    hours: Decimal,
    course: str,
) -> Credit:
    """Record a course somebody sat."""
    holder = get(book, applicator_id)
    if book.count(
        "credit",
        "applicator = ? AND on_day = ? AND course = ?",
        (holder.id, on.isoformat(), course),
    ):
        raise Duplicate("credit", f"{holder.name} {course} on {on.isoformat()}")
    entry = Credit(0, holder.id, on, category, hours, course)
    cursor = book.run(
        "INSERT INTO credit (applicator, on_day, category, hours, course) VALUES (?, ?, ?, ?, ?)",
        (entry.applicator, on.isoformat(), entry.category, float(entry.hours), entry.course),
    )
    return get_credit(book, int(cursor.lastrowid or 0))


def get_credit(book: Book, seq: int) -> Credit:
    """One credit by its sequence number."""
    row = book.one(f"SELECT {_CREDIT} FROM credit WHERE seq = ?", (seq,))
    if row is None:
        raise NotFound("credit", str(seq))
    return Credit.from_row(row)


def credits_for(
    book: Book,
    applicator_id: str,
    *,
    since: dt.date | None = None,
    until: dt.date | None = None,
) -> list[Credit]:
    """Every course one person sat, oldest first."""
    clauses = ["applicator = ?"]
    params: list[object] = [applicator_id]
    if since is not None:
        clauses.append("on_day >= ?")
        params.append(since.isoformat())
    if until is not None:
        clauses.append("on_day <= ?")
        params.append(until.isoformat())
    rows = book.all(
        f"SELECT {_CREDIT} FROM credit WHERE {' AND '.join(clauses)} ORDER BY on_day, seq",
        params,
    )
    return [Credit.from_row(row) for row in rows]
