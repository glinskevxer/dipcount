"""Reading and writing service requests."""

from __future__ import annotations

import datetime as dt

from dipcount import clock, ids
from dipcount.errors import NotFound, RuleViolation
from dipcount.model.request import Request
from dipcount.store import applicators, sites, window, zones
from dipcount.store.book import Book

_COLUMNS = (
    "id, kind, zone, taken_at, caller, phone, address, detail, assigned_to,"
    " visited_at, site, closed_at, outcome, note"
)
_VALUES = (
    ":id, :kind, :zone, :taken_at, :caller, :phone, :address, :detail, :assigned_to,"
    " :visited_at, :site, :closed_at, :outcome, :note"
)


def numbers(book: Book) -> list[str]:
    """Every request id already issued."""
    return [str(row["id"]) for row in book.all("SELECT id FROM request")]


def take(
    book: Book,
    kind: str,
    zone_id: str,
    taken_at: dt.datetime,
    address: str,
    *,
    caller: str = "",
    phone: str = "",
    detail: str = "",
    note: str = "",
) -> Request:
    """Write down a call as it comes in."""
    zone = zones.resolve(book, zone_id)
    made = Request(
        id=ids.next_serial("request", numbers(book)),
        kind=kind,
        zone=zone.id,
        taken_at=taken_at,
        address=address,
        caller=caller,
        phone=phone,
        detail=detail,
        note=note,
    )
    book.run(f"INSERT INTO request ({_COLUMNS}) VALUES ({_VALUES})", made.to_row())
    return get(book, made.id)


def get(book: Book, request_id: str) -> Request:
    """One call by id."""
    row = book.one(f"SELECT {_COLUMNS} FROM request WHERE id = ?", (request_id,))
    if row is None:
        raise NotFound("request", request_id)
    return Request.from_row(row)


def assign(book: Book, request_id: str, applicator_id: str) -> Request:
    """Put somebody's name against a call."""
    call = get(book, request_id)
    holder = applicators.resolve(book, applicator_id)
    if call.closed_at is not None:
        raise RuleViolation("request.closed", f"{request_id} was closed on {call.closed_at}")
    book.run("UPDATE request SET assigned_to = ? WHERE id = ?", (holder.id, request_id))
    return get(book, request_id)


def visit(
    book: Book,
    request_id: str,
    visited_at: dt.datetime,
    *,
    site_id: str | None = None,
) -> Request:
    """Record that somebody went out to a call."""
    call = get(book, request_id)
    if call.closed_at is not None:
        raise RuleViolation("request.closed", f"{request_id} was closed on {call.closed_at}")
    if call.visited_at is not None:
        raise RuleViolation("request.visited", f"{request_id} was visited already")
    if visited_at < call.taken_at:
        raise RuleViolation("request.clock", "a call cannot be visited before it came in")
    if site_id is not None:
        sites.get(book, site_id)
    book.run(
        "UPDATE request SET visited_at = ?, site = ? WHERE id = ?",
        (clock.to_utc(visited_at).isoformat(), site_id, request_id),
    )
    return get(book, request_id)


def close(
    book: Book,
    request_id: str,
    closed_at: dt.datetime,
    outcome: str,
) -> Request:
    """Close a call with what came of it."""
    call = get(book, request_id)
    if call.closed_at is not None:
        raise RuleViolation("request.closed", f"{request_id} was closed on {call.closed_at}")
    if not outcome.strip():
        raise RuleViolation("request.closed", "a closed call needs an outcome")
    if closed_at < call.taken_at:
        raise RuleViolation("request.clock", "a call cannot be closed before it came in")
    book.run(
        "UPDATE request SET closed_at = ?, outcome = ? WHERE id = ?",
        (clock.to_utc(closed_at).isoformat(), outcome, request_id),
    )
    return get(book, request_id)


def all_requests(
    book: Book,
    *,
    zone_id: str | None = None,
    kind: str | None = None,
) -> list[Request]:
    """Every call, narrowed if asked."""
    clauses: list[str] = []
    params: list[object] = []
    if zone_id is not None:
        clauses.append("zone = ?")
        params.append(zone_id)
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = book.all(f"SELECT {_COLUMNS} FROM request{where} ORDER BY taken_at, id", params)
    return [Request.from_row(row) for row in rows]


def between(book: Book, start: dt.date, end: dt.date) -> list[Request]:
    """Every call taken over a run of local days."""
    first, after = window.bounds(start, end)
    rows = book.all(
        f"SELECT {_COLUMNS} FROM request WHERE taken_at >= ? AND taken_at < ?"
        " ORDER BY taken_at, id",
        (first, after),
    )
    return [Request.from_row(row) for row in rows]


def in_week(book: Book, year: int, week: int) -> list[Request]:
    """Every call taken in one reporting week."""
    return between(book, clock.week_start(year, week), clock.week_end(year, week))


def open_calls(book: Book, *, zone_id: str | None = None) -> list[Request]:
    """Every call nobody has closed."""
    return [one for one in all_requests(book, zone_id=zone_id) if one.open]


def unvisited(book: Book, *, zone_id: str | None = None) -> list[Request]:
    """Every call nobody has been out to."""
    return [one for one in open_calls(book, zone_id=zone_id) if not one.visited]


def for_site(book: Book, site_id: str) -> list[Request]:
    """Every call that produced a visit to one site."""
    rows = book.all(
        f"SELECT {_COLUMNS} FROM request WHERE site = ? ORDER BY taken_at, id",
        (site_id,),
    )
    return [Request.from_row(row) for row in rows]


def for_applicator(book: Book, applicator_id: str) -> list[Request]:
    """Every call somebody has their name against."""
    rows = book.all(
        f"SELECT {_COLUMNS} FROM request WHERE assigned_to = ? ORDER BY taken_at, id",
        (applicator_id,),
    )
    return [Request.from_row(row) for row in rows]
