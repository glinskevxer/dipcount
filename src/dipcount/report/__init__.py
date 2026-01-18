"""Reports: the same records, arranged for somebody to read or to file.

Nothing here decides anything or writes anything. A report takes a book and a
window, asks the services what they already know, and arranges the answer.
That separation is what lets the same weekly figures go out as a table for the
board, as a comma separated file for the state, and as a line in a summary,
without three copies of the arithmetic.
"""

from dipcount.report.sheet import Sheet, pairs, table

__all__ = ["Sheet", "pairs", "table"]
