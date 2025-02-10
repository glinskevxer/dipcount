"""The records themselves, with no idea where they are stored.

Everything here is a frozen dataclass that knows how to read itself off a row
and how to check that it makes sense. Nothing here opens a book, imports a
store or raises about anything it cannot see from its own fields.
"""

from dipcount.model.audit import Entry
from dipcount.model.site import Site
from dipcount.model.zone import Zone

__all__ = ["Entry", "Site", "Zone"]
