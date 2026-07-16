"""The package writes into the book and nowhere else.

A package that writes into its own checkout works perfectly until somebody
installs it where the process cannot write, which is every container that runs
as a user other than root and every deployment that mounts the code read only.
The failure then is not a permission error in the place that wrote: it is
whatever happened next, three calls away, when the file was not there.

So this snapshots every file in the source tree, works a season through, and
asks whether anything moved. And it makes the tree read only for the duration,
which is the only version of the question that cannot be answered by accident.
"""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from dipcount.tools import smoke, source


def digest(path: Path) -> str:
    """A digest of one file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    """A digest of every python file under a directory."""
    return {
        str(one.relative_to(root)): digest(one)
        for one in sorted(root.rglob("*.py"))
        if "__pycache__" not in one.parts
    }


@pytest.fixture
def locked() -> Iterator[Path]:
    """The package source, read only for the length of one test."""
    root = source.package_root()
    modes: dict[Path, int] = {}
    for one in sorted(root.rglob("*.py")):
        if "__pycache__" in one.parts:
            continue
        modes[one] = one.stat().st_mode
        one.chmod(modes[one] & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    try:
        yield root
    finally:
        for one, mode in modes.items():
            one.chmod(mode)


def test_a_season_leaves_the_source_tree_alone() -> None:
    root = source.package_root()
    before = snapshot(root)
    smoke.run(quiet=True)
    assert snapshot(root) == before


def test_a_season_runs_with_the_source_tree_read_only(locked: Path) -> None:
    made = smoke.run(quiet=True)
    assert made.exists()
    assert not os.access(next(locked.rglob("clock.py")), os.W_OK)


def test_the_book_is_the_only_thing_written(tmp_path: Path) -> None:
    before = set(tmp_path.rglob("*"))
    made = smoke.run(quiet=True)
    assert made.parent != tmp_path
    assert set(tmp_path.rglob("*")) == before


def test_the_tests_do_not_write_into_the_checkout() -> None:
    root = source.project_root() / "tests"
    before = snapshot(root)
    smoke.run(quiet=True)
    assert snapshot(root) == before


def test_the_generated_documents_are_not_rewritten_by_a_season() -> None:
    docs = source.project_root() / "docs"
    before = {one.name: digest(one) for one in sorted(docs.glob("*.md"))}
    smoke.run(quiet=True)
    assert {one.name: digest(one) for one in sorted(docs.glob("*.md"))} == before
