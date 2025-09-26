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

_V2 = """
CREATE TABLE inspection (
    id          TEXT PRIMARY KEY,
    site        TEXT NOT NULL REFERENCES site (id),
    at          TEXT NOT NULL,
    inspector   TEXT NOT NULL,
    water       INTEGER NOT NULL,
    dips        INTEGER NOT NULL DEFAULT 0,
    note        TEXT NOT NULL DEFAULT ''
);

CREATE INDEX inspection_by_site ON inspection (site);
CREATE INDEX inspection_by_at ON inspection (at);

CREATE TABLE larvae (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection  TEXT NOT NULL REFERENCES inspection (id),
    species     TEXT NOT NULL DEFAULT '',
    stage       TEXT NOT NULL,
    tally       INTEGER NOT NULL,
    UNIQUE (inspection, species, stage)
);

CREATE INDEX larvae_by_inspection ON larvae (inspection);
"""

_V3 = """
CREATE TABLE station (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    zone        TEXT NOT NULL REFERENCES zone (id),
    elevation   INTEGER NOT NULL DEFAULT 0,
    opened_on   TEXT NOT NULL,
    closed_on   TEXT,
    note        TEXT NOT NULL DEFAULT ''
);

CREATE INDEX station_by_zone ON station (zone);

CREATE TABLE observation (
    id          TEXT PRIMARY KEY,
    station     TEXT NOT NULL REFERENCES station (id),
    on_day      TEXT NOT NULL,
    high_f      REAL NOT NULL,
    low_f       REAL NOT NULL,
    rain_in     REAL NOT NULL DEFAULT 0,
    wind_mph    REAL NOT NULL DEFAULT 0,
    note        TEXT NOT NULL DEFAULT '',
    UNIQUE (station, on_day)
);

CREATE INDEX observation_by_day ON observation (on_day);
CREATE INDEX observation_by_station ON observation (station);
"""

_V4 = """
CREATE TABLE trap (
    id          TEXT PRIMARY KEY,
    zone        TEXT NOT NULL REFERENCES zone (id),
    name        TEXT NOT NULL UNIQUE,
    kind        TEXT NOT NULL,
    latitude    REAL,
    longitude   REAL,
    listed_on   TEXT NOT NULL,
    retired_on  TEXT,
    note        TEXT NOT NULL DEFAULT ''
);

CREATE INDEX trap_by_zone ON trap (zone);
CREATE INDEX trap_by_kind ON trap (kind);

CREATE TABLE collection (
    id          TEXT PRIMARY KEY,
    trap        TEXT NOT NULL REFERENCES trap (id),
    set_at      TEXT NOT NULL,
    pulled_at   TEXT NOT NULL,
    nights      REAL NOT NULL,
    worked      INTEGER NOT NULL DEFAULT 1,
    handler     TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT ''
);

CREATE INDEX collection_by_trap ON collection (trap);
CREATE INDEX collection_by_pulled ON collection (pulled_at);

CREATE TABLE catch (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    collection  TEXT NOT NULL REFERENCES collection (id),
    species     TEXT NOT NULL,
    sex         TEXT NOT NULL,
    tally       INTEGER NOT NULL,
    UNIQUE (collection, species, sex)
);

CREATE INDEX catch_by_collection ON catch (collection);
"""

_V5 = """
CREATE TABLE pool (
    id            TEXT PRIMARY KEY,
    collection    TEXT NOT NULL REFERENCES collection (id),
    species       TEXT NOT NULL,
    size          INTEGER NOT NULL,
    submitted_on  TEXT NOT NULL,
    lab           TEXT NOT NULL DEFAULT '',
    note          TEXT NOT NULL DEFAULT ''
);

CREATE INDEX pool_by_collection ON pool (collection);
CREATE INDEX pool_by_submitted ON pool (submitted_on);

CREATE TABLE assay (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    pool        TEXT NOT NULL REFERENCES pool (id),
    virus       TEXT NOT NULL,
    outcome     TEXT NOT NULL,
    tested_on   TEXT,
    ct          REAL,
    UNIQUE (pool, virus)
);

CREATE INDEX assay_by_pool ON assay (pool);
CREATE INDEX assay_by_virus ON assay (virus);
"""

_V6 = """
CREATE TABLE product (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    registration  TEXT NOT NULL UNIQUE,
    maker         TEXT NOT NULL,
    active        TEXT NOT NULL,
    percent       REAL NOT NULL,
    form          TEXT NOT NULL,
    purpose       TEXT NOT NULL,
    restricted    INTEGER NOT NULL DEFAULT 0,
    signal        TEXT NOT NULL DEFAULT 'caution',
    reentry       INTEGER NOT NULL DEFAULT 0,
    added_on      TEXT NOT NULL,
    withdrawn_on  TEXT,
    note          TEXT NOT NULL DEFAULT ''
);

CREATE INDEX product_by_active ON product (active);
CREATE INDEX product_by_form ON product (form);

CREATE TABLE label_rate (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    product       TEXT NOT NULL REFERENCES product (id),
    habitat       TEXT NOT NULL,
    low_rate      TEXT NOT NULL,
    high_rate     TEXT NOT NULL,
    per           TEXT NOT NULL,
    season_max    TEXT,
    interval_days INTEGER NOT NULL DEFAULT 0,
    UNIQUE (product, habitat)
);

CREATE INDEX label_rate_by_product ON label_rate (product);
CREATE INDEX label_rate_by_habitat ON label_rate (habitat);
"""

_V7 = """
CREATE TABLE lot (
    id           TEXT PRIMARY KEY,
    product      TEXT NOT NULL REFERENCES product (id),
    code         TEXT NOT NULL,
    received_on  TEXT NOT NULL,
    quantity     TEXT NOT NULL,
    expires_on   TEXT,
    held_at      TEXT NOT NULL DEFAULT '',
    note         TEXT NOT NULL DEFAULT '',
    UNIQUE (product, code)
);

CREATE INDEX lot_by_product ON lot (product);
CREATE INDEX lot_by_expiry ON lot (expires_on);

CREATE TABLE draw (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    lot         TEXT NOT NULL REFERENCES lot (id),
    at          TEXT NOT NULL,
    amount      TEXT NOT NULL,
    reason      TEXT NOT NULL,
    reference   TEXT NOT NULL DEFAULT '',
    actor       TEXT NOT NULL
);

CREATE INDEX draw_by_lot ON draw (lot);
CREATE INDEX draw_by_reference ON draw (reference);
"""

_V8 = """
CREATE TABLE treatment (
    id          TEXT PRIMARY KEY,
    site        TEXT NOT NULL REFERENCES site (id),
    product     TEXT NOT NULL REFERENCES product (id),
    lot         TEXT NOT NULL REFERENCES lot (id),
    at          TEXT NOT NULL,
    applicator  TEXT NOT NULL,
    extent      TEXT NOT NULL,
    amount      TEXT NOT NULL,
    equipment   TEXT NOT NULL DEFAULT '',
    inspection  TEXT REFERENCES inspection (id),
    note        TEXT NOT NULL DEFAULT ''
);

CREATE INDEX treatment_by_site ON treatment (site);
CREATE INDEX treatment_by_product ON treatment (product);
CREATE INDEX treatment_by_lot ON treatment (lot);
CREATE INDEX treatment_by_at ON treatment (at);
"""

_V9 = """
CREATE TABLE applicator (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    licence       TEXT NOT NULL UNIQUE,
    grade         TEXT NOT NULL,
    categories    TEXT NOT NULL,
    certified_on  TEXT NOT NULL,
    expires_on    TEXT NOT NULL,
    supervisor    TEXT REFERENCES applicator (id),
    left_on       TEXT,
    note          TEXT NOT NULL DEFAULT ''
);

CREATE INDEX applicator_by_grade ON applicator (grade);
CREATE INDEX applicator_by_expiry ON applicator (expires_on);

CREATE TABLE credit (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    applicator  TEXT NOT NULL REFERENCES applicator (id),
    on_day      TEXT NOT NULL,
    category    TEXT NOT NULL,
    hours       REAL NOT NULL,
    course      TEXT NOT NULL,
    UNIQUE (applicator, on_day, course)
);

CREATE INDEX credit_by_applicator ON credit (applicator);
"""

_V10 = """
-- The use report has to carry the certification number that was in force on
-- the day, not the one the applicator holds now. A renewal changes the number
-- and must not change what last season's report says, so the number is copied
-- onto the treatment rather than looked up through the licence register.
ALTER TABLE treatment ADD COLUMN licence TEXT NOT NULL DEFAULT '';

CREATE INDEX treatment_by_applicator ON treatment (applicator);
"""

_V11 = """
CREATE TABLE exclusion (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    name          TEXT NOT NULL,
    zone          TEXT NOT NULL REFERENCES zone (id),
    contact       TEXT NOT NULL DEFAULT '',
    phone         TEXT NOT NULL DEFAULT '',
    buffer_ft     INTEGER NOT NULL DEFAULT 0,
    notice_hours  INTEGER NOT NULL DEFAULT 0,
    listed_on     TEXT NOT NULL,
    removed_on    TEXT,
    note          TEXT NOT NULL DEFAULT '',
    UNIQUE (kind, name)
);

CREATE INDEX exclusion_by_zone ON exclusion (zone);
CREATE INDEX exclusion_by_kind ON exclusion (kind);
"""

_V12 = """
CREATE TABLE block (
    id          TEXT PRIMARY KEY,
    zone        TEXT NOT NULL REFERENCES zone (id),
    name        TEXT NOT NULL UNIQUE,
    acres       REAL NOT NULL,
    road_miles  REAL NOT NULL DEFAULT 0,
    listed_on   TEXT NOT NULL,
    retired_on  TEXT,
    note        TEXT NOT NULL DEFAULT ''
);

CREATE INDEX block_by_zone ON block (zone);

CREATE TABLE block_exclusion (
    block       TEXT NOT NULL REFERENCES block (id),
    exclusion   TEXT NOT NULL REFERENCES exclusion (id),
    PRIMARY KEY (block, exclusion)
);

CREATE INDEX block_exclusion_by_exclusion ON block_exclusion (exclusion);

CREATE TABLE notice (
    id          TEXT PRIMARY KEY,
    exclusion   TEXT NOT NULL REFERENCES exclusion (id),
    block       TEXT NOT NULL REFERENCES block (id),
    given_at    TEXT NOT NULL,
    spray_from  TEXT NOT NULL,
    spray_to    TEXT NOT NULL,
    how         TEXT NOT NULL,
    given_by    TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT ''
);

CREATE INDEX notice_by_exclusion ON notice (exclusion);
CREATE INDEX notice_by_block ON notice (block);

CREATE TABLE run (
    id           TEXT PRIMARY KEY,
    block        TEXT NOT NULL REFERENCES block (id),
    product      TEXT NOT NULL REFERENCES product (id),
    lot          TEXT NOT NULL REFERENCES lot (id),
    applicator   TEXT NOT NULL,
    licence      TEXT NOT NULL DEFAULT '',
    started_at   TEXT NOT NULL,
    finished_at  TEXT NOT NULL,
    amount       TEXT NOT NULL,
    acres        REAL NOT NULL,
    equipment    TEXT NOT NULL DEFAULT '',
    temperature  REAL,
    wind_mph     REAL,
    wind_from    TEXT NOT NULL DEFAULT '',
    note         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX run_by_block ON run (block);
CREATE INDEX run_by_started ON run (started_at);
CREATE INDEX run_by_lot ON run (lot);
"""

MIGRATIONS: Final[tuple[Migration, ...]] = (
    Migration(1, "zones sites and the audit trail", _V1),
    Migration(2, "inspections and what the dipper found", _V2),
    Migration(3, "weather stations and their daily observations", _V3),
    Migration(4, "traps, the collections off them and what was in the jar", _V4),
    Migration(5, "pools sent to the lab and what came back", _V5),
    Migration(6, "the product shelf and the rates on the labels", _V6),
    Migration(7, "lots on the shelf and every draw off them", _V7),
    Migration(8, "treatments, and what went on what", _V8),
    Migration(9, "applicators, their licences and their credits", _V9),
    Migration(10, "the licence number in force when a treatment was made", _V10),
    Migration(11, "the register of places that are not sprayed", _V11),
    Migration(12, "spray blocks, the notices given and the runs made", _V12),
)


def latest() -> int:
    """The schema version this code expects."""
    return MIGRATIONS[-1].number if MIGRATIONS else 0


def lock_text() -> str:
    """The contents ``migrations.lock`` should have."""
    lines = ["# One line per migration: number, digest, name. Never edit a shipped line."]
    lines += [f"{step.number:03d} {step.digest()} {step.name}" for step in MIGRATIONS]
    return "\n".join(lines) + "\n"
