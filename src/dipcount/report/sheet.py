"""Laying a table out so the columns line up and the numbers read right.

Two rules that sound fussy and are not. Numbers are right aligned, because a
column of left aligned figures cannot be scanned for the big one. And a column
is decided to be numeric by looking at every cell in it rather than the first,
since a column of counts with one dash in it is still a column of counts.

The same table renders as text for a terminal and as comma separated values
for whoever wants it in a spreadsheet, off one description. A report that
builds its own string is a report that will disagree with the file version of
itself by the end of the season.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

_NUMBER = re.compile(r"^-?[0-9][0-9,]*(\.[0-9]+)?%?$")
_BLANK = ("", "-", "none", "never")


def looks_numeric(cell: str) -> bool:
    """Whether one cell reads as a number."""
    return bool(_NUMBER.match(cell.strip()))


def numeric_column(cells: list[str]) -> bool:
    """Whether a whole column should be right aligned.

    A dash or a blank is neither, so a column of counts with a gap in it is
    still a column of counts. A column with nothing but gaps is not numeric,
    because there is nothing there to line up.
    """
    seen = [one.strip() for one in cells if one.strip().lower() not in _BLANK]
    return bool(seen) and all(looks_numeric(one) for one in seen)


@dataclass
class Sheet:
    """One table: headings, rows, and how it prints."""

    headings: list[str]
    rows: list[list[str]] = field(default_factory=list)
    title: str = ""
    footer: str = ""

    def add(self, *cells: str) -> None:
        """Put one row on the sheet."""
        if len(cells) != len(self.headings):
            raise ValueError(
                f"{len(cells)} cells for {len(self.headings)} headings",
            )
        self.rows.append(list(cells))

    def column(self, index: int) -> list[str]:
        """Every cell in one column."""
        return [row[index] for row in self.rows]

    def widths(self) -> list[int]:
        """How wide each column has to be."""
        out = [len(one) for one in self.headings]
        for row in self.rows:
            for index, cell in enumerate(row):
                out[index] = max(out[index], len(cell))
        return out

    def alignments(self) -> list[bool]:
        """Whether each column is right aligned."""
        return [numeric_column(self.column(index)) for index in range(len(self.headings))]

    def _line(self, cells: list[str], widths: list[int], right: list[bool]) -> str:
        pieces = [
            cell.rjust(widths[index]) if right[index] else cell.ljust(widths[index])
            for index, cell in enumerate(cells)
        ]
        return "  ".join(pieces).rstrip()

    def render(self) -> str:
        """The whole table as text."""
        widths = self.widths()
        right = self.alignments()
        lines: list[str] = []
        if self.title:
            lines.extend([self.title, ""])
        lines.append(self._line(self.headings, widths, right))
        lines.append("  ".join("-" * width for width in widths))
        lines.extend(self._line(row, widths, right) for row in self.rows)
        lines.append("")
        lines.append(f"{len(self.rows)} row{'' if len(self.rows) == 1 else 's'}")
        if self.footer:
            lines.append(self.footer)
        return "\n".join(lines)

    def csv(self) -> str:
        """The same table as comma separated values."""
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(self.headings)
        writer.writerows(self.rows)
        return out.getvalue()

    def __str__(self) -> str:
        return self.render()


def table(headings: list[str], rows: list[list[str]], *, title: str = "") -> Sheet:
    """A sheet made in one go from headings and rows."""
    made = Sheet(headings=list(headings), title=title)
    for row in rows:
        made.add(*row)
    return made


def pairs(entries: list[tuple[str, str]]) -> str:
    """A record printed as aligned label and value lines."""
    if not entries:
        return ""
    width = max(len(label) for label, _ in entries)
    return "\n".join(f"{label.rjust(width)}  {value}" for label, value in entries)
