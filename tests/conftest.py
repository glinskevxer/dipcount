from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from dipcount.store import Book


@pytest.fixture
def book() -> Iterator[Book]:
    """An empty in memory book, closed when the test is done."""
    opened = Book.memory()
    try:
        yield opened
    finally:
        opened.close()


@pytest.fixture
def book_path(tmp_path: Path) -> Path:
    """Where a book on disk goes for a test that needs a real file."""
    return tmp_path / "district.sqlite3"
