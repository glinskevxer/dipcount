"""Reading and writing spray blocks and the notices given over them."""

from __future__ import annotations

import datetime as dt

from dipcount import clock, ids
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.block import Block, Notice
from dipcount.model.exclusion import Exclusion
from dipcount.store import exclusions, zones
from dipcount.store.book import Book

_BLOCK = "id, zone, name, acres, road_miles, listed_on, retired_on, note"
_BLOCK_VALUES = ":id, :zone, :name, :acres, :road_miles, :listed_on, :retired_on, :note"
_NOTICE = "id, exclusion, block, given_at, spray_from, spray_to, how, given_by, note"
_NOTICE_VALUES = (
    ":id, :exclusion, :block, :given_at, :spray_from, :spray_to, :how, :given_by, :note"
)


def numbers(book: Book) -> list[str]:
    """Every block id already issued."""
    return [str(row["id"]) for row in book.all("SELECT id FROM block")]


def add(
    book: Book,
    zone_id: str,
    name: str,
    acres: float,
    listed_on: dt.date,
    *,
    road_miles: float = 0.0,
    note: str = "",
) -> Block:
    """Put a block on the run list."""
    zone = zones.resolve(book, zone_id)
    if find_by_name(book, name) is not None:
        raise Duplicate("block", name)
    made = Block(
        id=ids.next_serial("block", numbers(book)),
        zone=zone.id,
        name=name,
        acres=acres,
        listed_on=listed_on,
        road_miles=road_miles,
        note=note,
    )
    book.run(f"INSERT INTO block ({_BLOCK}) VALUES ({_BLOCK_VALUES})", made.to_row())
    return made


def get(book: Book, block_id: str) -> Block:
    """One block by id."""
    row = book.one(f"SELECT {_BLOCK} FROM block WHERE id = ?", (block_id,))
    if row is None:
        raise NotFound("block", block_id)
    return Block.from_row(row)


def find_by_name(book: Book, name: str) -> Block | None:
    """One block by name, or nothing."""
    row = book.one(f"SELECT {_BLOCK} FROM block WHERE name = ?", (name,))
    return None if row is None else Block.from_row(row)


def resolve(book: Book, text: str) -> Block:
    """A block by id or by name."""
    if ids.looks_like("block", text):
        return get(book, text)
    found = find_by_name(book, text)
    if found is None:
        raise NotFound("block", text)
    return found


def all_blocks(book: Book, *, zone_id: str | None = None) -> list[Block]:
    """Every block, optionally in one zone."""
    where = " WHERE zone = ?" if zone_id else ""
    params = (zone_id,) if zone_id else ()
    rows = book.all(f"SELECT {_BLOCK} FROM block{where} ORDER BY id", params)
    return [Block.from_row(row) for row in rows]


def open_on(book: Book, on: dt.date, *, zone_id: str | None = None) -> list[Block]:
    """Every block on the run list on a day."""
    return [one for one in all_blocks(book, zone_id=zone_id) if one.is_open(on)]


def retire(book: Book, block_id: str, on: dt.date, why: str = "") -> Block:
    """Take a block off the run list."""
    block = get(book, block_id)
    if block.retired_on is not None:
        raise RuleViolation("spray.block", f"{block_id} was retired on {block.retired_on}")
    if on < block.listed_on:
        raise RuleViolation("spray.block", "a block cannot be retired before it was listed")
    note = f"{block.note}\nretired: {why}".strip() if why else block.note
    book.run(
        "UPDATE block SET retired_on = ?, note = ? WHERE id = ?",
        (on.isoformat(), note, block_id),
    )
    return get(book, block_id)


def link(book: Book, block_id: str, exclusion_id: str) -> None:
    """Record that a register entry falls inside a block."""
    block = get(book, block_id)
    entry = exclusions.get(book, exclusion_id)
    if book.count(
        "block_exclusion",
        "block = ? AND exclusion = ?",
        (block.id, entry.id),
    ):
        raise Duplicate("register entry in block", f"{entry.id} in {block.id}")
    book.run(
        "INSERT INTO block_exclusion (block, exclusion) VALUES (?, ?)",
        (block.id, entry.id),
    )


def unlink(book: Book, block_id: str, exclusion_id: str) -> None:
    """Take a register entry out of a block."""
    cursor = book.run(
        "DELETE FROM block_exclusion WHERE block = ? AND exclusion = ?",
        (block_id, exclusion_id),
    )
    if not cursor.rowcount:
        raise NotFound("register entry in block", f"{exclusion_id} in {block_id}")


def entries_in(book: Book, block_id: str, on: dt.date) -> list[Exclusion]:
    """Every register entry inside a block that is current on a day."""
    rows = book.all(
        "SELECT exclusion FROM block_exclusion WHERE block = ? ORDER BY exclusion",
        (block_id,),
    )
    found = [exclusions.get(book, str(row["exclusion"])) for row in rows]
    return [one for one in found if one.on_register(on)]


def blocks_for(book: Book, exclusion_id: str) -> list[Block]:
    """Every block one register entry falls inside."""
    rows = book.all(
        "SELECT block FROM block_exclusion WHERE exclusion = ? ORDER BY block",
        (exclusion_id,),
    )
    return [get(book, str(row["block"])) for row in rows]


def notice_numbers(book: Book) -> list[str]:
    """Every notice id already issued."""
    return [str(row["id"]) for row in book.all("SELECT id FROM notice")]


def give(
    book: Book,
    exclusion_id: str,
    block_id: str,
    given_at: dt.datetime,
    spray_from: dt.datetime,
    spray_to: dt.datetime,
    how: str,
    given_by: str,
    *,
    note: str = "",
) -> Notice:
    """Record that somebody was told about a block and a window."""
    block = resolve(book, block_id)
    entry = exclusions.get(book, exclusion_id)
    if not book.count(
        "block_exclusion",
        "block = ? AND exclusion = ?",
        (block.id, entry.id),
    ):
        raise RuleViolation(
            "spray.notice",
            f"{entry.name} is not recorded as falling inside {block.name}",
        )
    made = Notice(
        id=ids.next_serial("notice", notice_numbers(book)),
        exclusion=entry.id,
        block=block.id,
        given_at=given_at,
        spray_from=spray_from,
        spray_to=spray_to,
        how=how,
        given_by=given_by,
        note=note,
    )
    book.run(f"INSERT INTO notice ({_NOTICE}) VALUES ({_NOTICE_VALUES})", made.to_row())
    return get_notice(book, made.id)


def get_notice(book: Book, notice_id: str) -> Notice:
    """One notice by id."""
    row = book.one(f"SELECT {_NOTICE} FROM notice WHERE id = ?", (notice_id,))
    if row is None:
        raise NotFound("notice", notice_id)
    return Notice.from_row(row)


def notices_for(
    book: Book,
    block_id: str,
    *,
    exclusion_id: str | None = None,
) -> list[Notice]:
    """Every notice given over one block, oldest first."""
    clauses = ["block = ?"]
    params: list[object] = [block_id]
    if exclusion_id is not None:
        clauses.append("exclusion = ?")
        params.append(exclusion_id)
    rows = book.all(
        f"SELECT {_NOTICE} FROM notice WHERE {' AND '.join(clauses)} ORDER BY given_at, id",
        params,
    )
    return [Notice.from_row(row) for row in rows]


def covering(
    book: Book,
    block_id: str,
    exclusion_id: str,
    at: dt.datetime,
) -> Notice | None:
    """The notice that covers a run at a moment, if there is one."""
    for one in notices_for(book, block_id, exclusion_id=exclusion_id):
        if one.covers(clock.to_utc(at)):
            return one
    return None
