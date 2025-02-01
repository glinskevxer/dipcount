"""The schema, one numbered step at a time.

A migration is never edited after it ships. The book in the district office
has already run it, and changing what it says does not change what that book
holds, it only makes the two disagree. ``migrations.lock`` records a digest of
every step so that an edit to a shipped one is caught by a check rather than
by a corrupted book two seasons later.

New work goes on the end as another step, including work that undoes an
earlier one.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Migration:
    """One numbered step from one schema version to the next."""

    number: int
    name: str
    sql: str

    def digest(self) -> str:
        """A short digest of the step, for the lock file."""
        body = f"{self.number}\n{self.name}\n{self.sql.strip()}\n"
        return hashlib.sha256(body.encode()).hexdigest()[:16]


_V1 = """
CREATE TABLE zone (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    supervisor  TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE site (
    id          TEXT PRIMARY KEY,
    zone        TEXT NOT NULL REFERENCES zone (id),
    name        TEXT NOT NULL,
    habitat     TEXT NOT NULL,
    access      TEXT NOT NULL DEFAULT '',
    latitude    REAL,
    longitude   REAL,
    extent      TEXT NOT NULL DEFAULT '0 acre',
    listed_on   TEXT NOT NULL,
    retired_on  TEXT,
    note        TEXT NOT NULL DEFAULT '',
    UNIQUE (zone, name)
);

CREATE INDEX site_by_zone ON site (zone);
CREATE INDEX site_by_habitat ON site (habitat);

CREATE TABLE audit (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    subject     TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT ''
);

CREATE INDEX audit_by_subject ON audit (subject);
CREATE INDEX audit_by_at ON audit (at);
"""

MIGRATIONS: Final[tuple[Migration, ...]] = (Migration(1, "zones sites and the audit trail", _V1),)


def latest() -> int:
    """The schema version this code expects."""
    return MIGRATIONS[-1].number if MIGRATIONS else 0


def lock_text() -> str:
    """The contents ``migrations.lock`` should have."""
    lines = ["# One line per migration: number, digest, name. Never edit a shipped line."]
    lines += [f"{step.number:03d} {step.digest()} {step.name}" for step in MIGRATIONS]
    return "\n".join(lines) + "\n"
