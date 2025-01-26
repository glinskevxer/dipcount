"""Everything that touches the district's book.

The book is one sqlite file. Every table, every migration and every query in
this package lives under this package, and nothing above it writes SQL. The
layer check enforces that: a service that wants a row asks a store for it.
"""

from dipcount.store.book import Book, Row

__all__ = ["Book", "Row"]
