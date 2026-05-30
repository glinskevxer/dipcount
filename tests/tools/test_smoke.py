from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest

from dipcount.report import use_report
from dipcount.store import Book, applicators, blocks, inventory, requests, sites, treatments
from dipcount.tools import smoke


@pytest.fixture(scope="module")
def worked() -> Iterator[Book]:
    path = smoke.run(quiet=True)
    book = Book(path)
    try:
        yield book
    finally:
        book.close()


def test_a_whole_season_runs_through(worked: Book) -> None:
    assert worked.version > 0
    assert worked.count("site") == 2
    assert worked.count("block") == 1


def test_the_district_is_laid_out(worked: Book) -> None:
    assert len(sites.all_sites(worked)) == 2
    assert len(blocks.all_blocks(worked)) == 1
    assert len(applicators.all_applicators(worked)) == 1


def test_the_larval_round_left_a_treatment(worked: Book) -> None:
    made = treatments.between(worked, dt.date(2025, 1, 1), dt.date(2025, 12, 31))
    assert len(made) == 1
    assert made[0].licence == "PA-44192"


def test_the_traps_and_the_pools_came_in(worked: Book) -> None:
    assert worked.count("collection") == 1
    assert worked.count("pool") == 2
    assert worked.count("assay") == 2


def test_the_block_was_fogged_after_the_apiary_was_told(worked: Book) -> None:
    assert worked.count("notice") == 1
    assert worked.count("run") == 1


def test_the_bottle_assay_was_run(worked: Book) -> None:
    assert worked.count("bioassay") == 1
    assert worked.count("bottle") == 5


def test_the_call_was_taken(worked: Book) -> None:
    assert len(requests.all_requests(worked)) == 1


def test_the_return_carries_both_applications(worked: Book) -> None:
    filed = use_report.season(worked, 2025)
    assert len(filed.filed) == 2
    assert len(filed.held) == 0


def test_the_stock_came_off_the_shelf(worked: Book) -> None:
    assert inventory.stock(worked, "LT-0001").left < inventory.get(worked, "LT-0001").quantity


def test_the_run_prints_when_it_is_not_quiet(capsys: pytest.CaptureFixture[str]) -> None:
    smoke.run(quiet=False)
    printed = capsys.readouterr().out
    assert "larval surveillance" in printed
    assert "pesticide use" in printed


def test_the_smoke_module_runs_from_the_command_line(capsys: pytest.CaptureFixture[str]) -> None:
    smoke.main(["--quiet"])
    assert "a season worked through" in capsys.readouterr().out
