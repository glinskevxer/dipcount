"""Reading and writing traps and the collections that come off them."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from dipcount import clock, ids
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.trap import Catch, Collection, Trap
from dipcount.store import window, zones
from dipcount.store.book import Book, Row

_TRAP = "id, zone, name, kind, latitude, longitude, listed_on, retired_on, note"
_COLLECTION = "id, trap, set_at, pulled_at, nights, worked, handler, note"


def trap_numbers(book: Book) -> list[str]:
    """Every trap id already issued."""
    return [str(row["id"]) for row in book.all("SELECT id FROM trap")]


def add(
    book: Book,
    zone_id: str,
    name: str,
    kind: str,
    listed_on: dt.date,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    note: str = "",
) -> Trap:
    """Put a trap station on the books."""
    zone = zones.resolve(book, zone_id)
    if find_by_name(book, name) is not None:
        raise Duplicate("trap", name)
    trap = Trap(
        id=ids.next_serial("trap", trap_numbers(book)),
        zone=zone.id,
        name=name,
        kind=kind,
        listed_on=listed_on,
        latitude=latitude,
        longitude=longitude,
        note=note,
    )
    book.run(
        f"INSERT INTO trap ({_TRAP}) VALUES"
        " (:id, :zone, :name, :kind, :latitude, :longitude, :listed_on, :retired_on, :note)",
        trap.to_row(),
    )
    return trap


def get(book: Book, trap_id: str) -> Trap:
    """One trap by id."""
    row = book.one(f"SELECT {_TRAP} FROM trap WHERE id = ?", (trap_id,))
    if row is None:
        raise NotFound("trap", trap_id)
    return Trap.from_row(row)


def find_by_name(book: Book, name: str) -> Trap | None:
    """One trap by name, or nothing."""
    row = book.one(f"SELECT {_TRAP} FROM trap WHERE name = ?", (name,))
    return None if row is None else Trap.from_row(row)


def resolve(book: Book, text: str) -> Trap:
    """A trap by id or by name."""
    if ids.looks_like("trap", text):
        return get(book, text)
    found = find_by_name(book, text)
    if found is None:
        raise NotFound("trap", text)
    return found


def all_traps(book: Book, *, zone_id: str | None = None, kind: str | None = None) -> list[Trap]:
    """Every trap, narrowed by zone or kind if asked."""
    clauses: list[str] = []
    params: list[object] = []
    if zone_id is not None:
        clauses.append("zone = ?")
        params.append(zone_id)
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = book.all(f"SELECT {_TRAP} FROM trap{where} ORDER BY id", params)
    return [Trap.from_row(row) for row in rows]


def open_on(book: Book, on: dt.date, *, zone_id: str | None = None) -> list[Trap]:
    """Every trap that was running on a given day."""
    return [one for one in all_traps(book, zone_id=zone_id) if one.is_open(on)]


def retire(book: Book, trap_id: str, on: dt.date, why: str = "") -> Trap:
    """Take a trap off the round."""
    trap = get(book, trap_id)
    if trap.retired_on is not None:
        raise RuleViolation("trap.retired", f"{trap_id} was retired on {trap.retired_on}")
    if on < trap.listed_on:
        raise RuleViolation("trap.retired", "a trap cannot be retired before it was listed")
    note = f"{trap.note}\nretired: {why}".strip() if why else trap.note
    book.run(
        "UPDATE trap SET retired_on = ?, note = ? WHERE id = ?", (on.isoformat(), note, trap_id)
    )
    return get(book, trap_id)


def collection_numbers(book: Book, on: dt.date) -> list[str]:
    """Every collection id already issued for a day."""
    stem = f"CO-{on:%y%m%d}-"
    rows = book.all("SELECT id FROM collection WHERE id LIKE ?", (f"{stem}%",))
    return [str(row["id"]) for row in rows]


def _catches(book: Book, collection_id: str) -> tuple[Catch, ...]:
    rows = book.all(
        "SELECT species, sex, tally FROM catch WHERE collection = ? ORDER BY species, sex",
        (collection_id,),
    )
    return tuple(Catch.from_row(row) for row in rows)


def _load(book: Book, row: Row) -> Collection:
    return Collection.from_row(row, _catches(book, str(row["id"])))


def record(
    book: Book,
    trap_id: str,
    set_at: dt.datetime,
    pulled_at: dt.datetime,
    handler: str,
    *,
    worked: bool = True,
    catches: Iterable[Catch] = (),
    note: str = "",
) -> Collection:
    """Write one collection and everything counted out of the jar."""
    trap = resolve(book, trap_id)
    on = clock.in_zone(pulled_at).date()
    if not trap.is_open(on):
        raise RuleViolation("trap.retired", f"{trap.name} was not running on {on.isoformat()}")
    lines = tuple(catches)
    if len({(one.species, one.sex) for one in lines}) != len(lines):
        raise Duplicate("catch", "one species and sex counted twice")
    made = Collection(
        id=ids.next_dated("collection", on, collection_numbers(book, on)),
        trap=trap.id,
        set_at=set_at,
        pulled_at=pulled_at,
        handler=handler,
        worked=worked,
        note=note,
        catches=lines,
    )
    with book.writing():
        book.run(
            f"INSERT INTO collection ({_COLLECTION})"
            " VALUES (:id, :trap, :set_at, :pulled_at, :nights, :worked, :handler, :note)",
            made.to_row(),
        )
        book.run_many(
            "INSERT INTO catch (collection, species, sex, tally) VALUES (?, ?, ?, ?)",
            [(made.id, one.species, one.sex, one.tally) for one in lines],
        )
    return get_collection(book, made.id)


def get_collection(book: Book, collection_id: str) -> Collection:
    """One collection by id, with its catches."""
    row = book.one(f"SELECT {_COLLECTION} FROM collection WHERE id = ?", (collection_id,))
    if row is None:
        raise NotFound("collection", collection_id)
    return _load(book, row)


def between(
    book: Book, start: dt.date, end: dt.date, *, trap_id: str | None = None
) -> list[Collection]:
    """Every collection pulled over a run of local days."""
    first, after = window.bounds(start, end)
    clauses = ["pulled_at >= ?", "pulled_at < ?"]
    params: list[object] = [first, after]
    if trap_id is not None:
        clauses.append("trap = ?")
        params.append(trap_id)
    rows = book.all(
        f"SELECT {_COLLECTION} FROM collection WHERE {' AND '.join(clauses)} ORDER BY pulled_at",
        params,
    )
    return [_load(book, row) for row in rows]


def for_trap(book: Book, trap_id: str) -> list[Collection]:
    """Every collection off one trap, oldest first."""
    rows = book.all(
        f"SELECT {_COLLECTION} FROM collection WHERE trap = ? ORDER BY pulled_at",
        (trap_id,),
    )
    return [_load(book, row) for row in rows]


def on_day(book: Book, on: dt.date) -> list[Collection]:
    """Every collection pulled on one local day."""
    return between(book, on, on)


def in_week(book: Book, year: int, week: int) -> list[Collection]:
    """Every collection pulled in one reporting week."""
    return between(book, clock.week_start(year, week), clock.week_end(year, week))


def last_for_trap(book: Book, trap_id: str) -> Collection | None:
    """The most recent collection off one trap."""
    found = for_trap(book, trap_id)
    return found[-1] if found else None
