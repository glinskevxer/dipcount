from __future__ import annotations

import json
from pathlib import Path

import pytest

from dipcount.tools import coverage_gate


def a_report(tmp_path: Path, files: dict[str, float], total: float) -> Path:
    path = tmp_path / "coverage.json"
    path.write_text(
        json.dumps(
            {
                "totals": {"percent_covered": total},
                "files": {
                    name: {"summary": {"percent_covered": percent, "missing_lines": 3}}
                    for name, percent in files.items()
                },
            },
        ),
    )
    return path


def test_a_report_is_read_back_as_a_total_and_files(tmp_path: Path) -> None:
    path = a_report(tmp_path, {"a.py": 99.0, "b.py": 80.0}, 95.5)
    total, files = coverage_gate.read(path)
    assert total == 95.5
    assert [one.name for one in files] == ["a.py", "b.py"]
    assert files[0].missing == 3


def test_the_files_under_a_floor_come_back_worst_first(tmp_path: Path) -> None:
    path = a_report(tmp_path, {"a.py": 99.0, "b.py": 70.0, "c.py": 60.0}, 90.0)
    _, files = coverage_gate.read(path)
    found = coverage_gate.below(files, 80.0)
    assert [one.name for one in found] == ["c.py", "b.py"]


def test_nothing_is_under_a_floor_of_nothing(tmp_path: Path) -> None:
    path = a_report(tmp_path, {"a.py": 99.0}, 99.0)
    _, files = coverage_gate.read(path)
    assert coverage_gate.below(files, 0.0) == []


def test_the_worst_files_are_cut_to_the_number_asked_for(tmp_path: Path) -> None:
    path = a_report(tmp_path, {"a.py": 99.0, "b.py": 70.0, "c.py": 60.0}, 90.0)
    _, files = coverage_gate.read(path)
    assert [one.name for one in coverage_gate.worst(files, 2)] == ["c.py", "b.py"]


def test_a_measured_file_prints_its_share(tmp_path: Path) -> None:
    path = a_report(tmp_path, {"a.py": 88.5}, 88.5)
    _, files = coverage_gate.read(path)
    assert "88.50%" in files[0].line()
    assert "3 lines missed" in files[0].line()


def test_the_file_floor_sits_under_the_total_floor() -> None:
    assert coverage_gate.FILE_FLOOR < coverage_gate.FLOOR


def test_the_floors_can_be_given_on_the_command_line() -> None:
    assert coverage_gate._argument(["--floor", "90"], "--floor", 95.0) == 90.0
    assert coverage_gate._argument([], "--floor", 95.0) == 95.0


def test_a_missing_report_stops_the_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(coverage_gate, "report_path", lambda: tmp_path / "nothing.json")
    with pytest.raises(SystemExit) as raised:
        coverage_gate.main([])
    assert raised.value.code == 1


def test_a_low_total_fails_the_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = a_report(tmp_path, {"a.py": 99.0}, 50.0)
    monkeypatch.setattr(coverage_gate, "report_path", lambda: path)
    with pytest.raises(SystemExit) as raised:
        coverage_gate.main([])
    assert raised.value.code == 1


def test_one_low_file_fails_the_gate_even_on_a_good_total(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = a_report(tmp_path, {"a.py": 99.9, "b.py": 40.0}, 98.0)
    monkeypatch.setattr(coverage_gate, "report_path", lambda: path)
    with pytest.raises(SystemExit) as raised:
        coverage_gate.main([])
    assert raised.value.code == 1


def test_a_good_report_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = a_report(tmp_path, {"a.py": 99.0, "b.py": 96.0}, 98.0)
    monkeypatch.setattr(coverage_gate, "report_path", lambda: path)
    with pytest.raises(SystemExit) as raised:
        coverage_gate.main([])
    assert raised.value.code == 0
