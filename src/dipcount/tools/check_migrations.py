"""The migrations are numbered, unedited, and produce the schema in use.

A shipped migration is not editable. The book in the district office has
already run it, and changing what it says does not change what that book
holds: it only makes the two disagree, and the disagreement surfaces months
later as a column that is there on one machine and not on another. So the lock
file carries a digest of every step, and this check refuses any difference
between it and the code.

The other half is that the steps actually run. A migration can be written
correctly, pass review, and fail on an empty book because it refers to a table
a later step creates. The check builds a book from nothing, one step at a
time, and stops at the first one that will not go on.
"""

from __future__ import annotations

from pathlib import Path

from dipcount.errors import BookError
from dipcount.store.book import Book
from dipcount.store.migrations import MIGRATIONS, latest, lock_text
from dipcount.tools import source

CHECK = "check_migrations"
LOCK = "migrations.lock"


def lock_path() -> Path:
    """Where the lock file lives."""
    return source.project_root() / LOCK


def lock_matches() -> list[source.Finding]:
    """Whether the lock file says what the migrations say."""
    path = lock_path()
    if not path.exists():
        return [source.Finding(LOCK, "is missing")]
    have = path.read_text()
    want = lock_text()
    if have == want:
        return []
    out: list[source.Finding] = []
    old = have.splitlines()
    new = want.splitlines()
    for number, (was, now) in enumerate(zip(old, new, strict=False), start=1):
        if was != now:
            out.append(source.Finding(LOCK, f"line {number} reads {was!r}, expected {now!r}"))
    if len(old) != len(new):
        out.append(source.Finding(LOCK, f"has {len(old)} lines and the code has {len(new)}"))
    return out


def numbering() -> list[source.Finding]:
    """Whether the steps run one to the last without a gap."""
    out: list[source.Finding] = []
    numbers = [step.number for step in MIGRATIONS]
    if numbers != list(range(1, len(numbers) + 1)):
        out.append(source.Finding("migrations", f"are numbered {numbers}"))
    names = [step.name for step in MIGRATIONS]
    for name in names:
        if names.count(name) > 1:
            out.append(source.Finding("migrations", f"two steps are both called {name!r}"))
            break
    if latest() != len(MIGRATIONS):
        out.append(source.Finding("migrations", "the latest version is not the last step"))
    return out


def steps_run() -> list[source.Finding]:
    """Whether every step applies to a book built from nothing."""
    out: list[source.Finding] = []
    book = Book.memory()
    try:
        for step in MIGRATIONS:
            try:
                with book.writing():
                    book.script(step.sql)
                    book.version = step.number
            except BookError as error:
                out.append(source.Finding("migrations", f"step {step.number} failed: {error}"))
                break
    finally:
        book.close()
    return out


def empty_steps() -> list[source.Finding]:
    """Every step that does nothing."""
    return [
        source.Finding("migrations", f"step {step.number} is empty")
        for step in MIGRATIONS
        if not step.sql.strip()
    ]


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return numbering() + empty_steps() + steps_run() + lock_matches()


def write_lock() -> Path:
    """Write the lock file from the migrations, and say where it went."""
    path = lock_path()
    path.write_text(lock_text())
    return path


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=len(MIGRATIONS))


if __name__ == "__main__":
    main()
