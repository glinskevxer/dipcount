from __future__ import annotations

import pytest

from dipcount.report import sheet


def test_a_sheet_lines_the_columns_up() -> None:
    made = sheet.table(["id", "name"], [["SI-0001", "Weller Road"], ["SI-0002", "Sawyer"]])
    lines = made.render().splitlines()
    assert lines[0].startswith("id")
    assert set(lines[1]) <= {"-", " "}
    assert "2 rows" in made.render()


def test_one_row_reads_as_one_row() -> None:
    made = sheet.table(["id"], [["SI-0001"]])
    assert "1 row" in made.render()
    assert "1 rows" not in made.render()


def test_an_empty_sheet_still_prints_its_headings() -> None:
    made = sheet.table(["id", "name"], [])
    assert "id" in made.render()
    assert "0 rows" in made.render()


def test_a_row_of_the_wrong_width_is_refused() -> None:
    made = sheet.Sheet(headings=["id", "name"])
    with pytest.raises(ValueError, match="cells for"):
        made.add("SI-0001")


def test_numbers_are_right_aligned_and_words_are_not() -> None:
    made = sheet.table(["name", "count"], [["a", "1"], ["bbbb", "1000"]])
    lines = made.render().splitlines()
    assert lines[2].endswith("   1")
    assert lines[3].endswith("1000")


def test_a_column_with_a_gap_in_it_is_still_numeric() -> None:
    assert sheet.numeric_column(["1", "-", "1000"])
    assert sheet.numeric_column(["1", "", "2"])


def test_a_column_of_nothing_but_gaps_is_not_numeric() -> None:
    assert not sheet.numeric_column(["-", "-", ""])


def test_words_beside_numbers_make_a_word_column() -> None:
    assert not sheet.numeric_column(["1", "two", "3"])


def test_percentages_and_thousands_read_as_numbers() -> None:
    assert sheet.looks_numeric("42%")
    assert sheet.looks_numeric("1,240")
    assert sheet.looks_numeric("-3.5")
    assert not sheet.looks_numeric("6 acre")


def test_a_title_goes_above_the_headings() -> None:
    made = sheet.table(["id"], [["SI-0001"]], title="the site list")
    assert made.render().splitlines()[0] == "the site list"


def test_a_footer_goes_under_the_count() -> None:
    made = sheet.Sheet(headings=["id"], footer="taken 2025-06-04")
    made.add("SI-0001")
    assert made.render().splitlines()[-1] == "taken 2025-06-04"


def test_the_same_sheet_comes_out_as_a_file() -> None:
    made = sheet.table(["id", "name"], [["SI-0001", "Weller Road, north"]])
    assert made.csv() == 'id,name\nSI-0001,"Weller Road, north"\n'


def test_a_column_can_be_read_back(  # which is how the alignment is worked out
) -> None:
    made = sheet.table(["id", "count"], [["a", "1"], ["b", "2"]])
    assert made.column(1) == ["1", "2"]


def test_printing_a_sheet_renders_it() -> None:
    made = sheet.table(["id"], [["SI-0001"]])
    assert str(made) == made.render()


def test_pairs_line_the_labels_up() -> None:
    text = sheet.pairs([("id", "SI-0001"), ("habitat", "catch basin")])
    lines = text.splitlines()
    assert lines[0].startswith("     id")
    assert lines[1].startswith("habitat")


def test_pairs_of_nothing_is_nothing() -> None:
    assert sheet.pairs([]) == ""
