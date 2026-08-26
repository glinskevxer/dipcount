from __future__ import annotations

import ast
from pathlib import Path

from dipcount.tools import source


def test_the_package_root_holds_the_package() -> None:
    assert (source.package_root() / "__init__.py").exists()
    assert source.package_root().name == "dipcount"


def test_the_project_root_holds_the_pyproject() -> None:
    assert (source.project_root() / "pyproject.toml").exists()


def test_every_module_is_a_python_file_inside_the_package() -> None:
    found = source.modules()
    assert found
    for one in found:
        assert one.suffix == ".py"
        assert source.package_root() in one.parents


def test_the_modules_can_be_narrowed_to_a_subpackage() -> None:
    found = source.modules(under="store")
    assert found
    assert all("store" in one.parts for one in found)
    assert len(found) < len(source.modules())


def test_no_cache_files_are_walked() -> None:
    for one in [*source.modules(), *source.test_modules()]:
        assert "__pycache__" not in one.parts


def test_the_tests_are_found_too() -> None:
    found = source.test_modules()
    assert found
    assert any(one.name == "test_source.py" for one in found)


def test_a_path_becomes_an_import_name() -> None:
    assert source.dotted(source.package_root() / "clock.py") == "dipcount.clock"
    assert source.dotted(source.package_root() / "__init__.py") == "dipcount"
    assert source.dotted(source.package_root() / "store" / "book.py") == "dipcount.store.book"


def test_a_file_parses_and_reads(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n')
    assert isinstance(source.parse(path), ast.Module)
    assert source.source_of(path) == '"""A file."""\n'


def test_public_names_are_the_ones_without_an_underscore() -> None:
    assert source.is_public("week_start")
    assert not source.is_public("_helper")


def test_every_definition_is_walked(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\n\nclass A:\n    def b(self) -> None:\n        pass\n')
    found = source.walk_definitions(source.parse(path))
    assert [source.name_of(one) for one in found] == ["module", "A", "b"]


def test_a_definition_knows_its_line(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\n\ndef b() -> None:\n    pass\n')
    found = source.walk_definitions(source.parse(path))
    assert source.line_of(found[1]) == 4
    assert source.line_of(found[0]) == 1


def test_a_finding_prints_with_and_without_a_line() -> None:
    assert source.Finding("a.py", "no good", 4).line_text() == "  a.py:4  no good"
    assert source.Finding("a.py", "no good").line_text() == "  a.py  no good"


def test_a_clean_check_reports_ok(capsys: object) -> None:
    assert source.report("a check", []) == 0


def test_a_check_with_findings_reports_them(capsys: object) -> None:
    assert source.report("a check", [source.Finding("a.py", "no good")]) == 1


def test_a_path_prints_relative_to_the_checkout() -> None:
    printed = source.where(source.package_root() / "clock.py")
    assert printed == "src/dipcount/clock.py"


def test_a_path_outside_the_checkout_prints_whole(tmp_path: Path) -> None:
    assert source.where(tmp_path / "a.py") == str(tmp_path / "a.py")


def test_a_path_from_outside_the_package_comes_back_as_its_stem(tmp_path: Path) -> None:
    assert source.dotted(tmp_path / "one.py") == "one"
    assert source.dotted(tmp_path / "deep" / "two.py") == "two"
