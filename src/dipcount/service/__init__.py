"""What the district actually does, expressed once.

A service takes a book, the name of whoever is asking, and the facts of the
job. It checks the rules, calls the stores in the right order, and leaves a
line on the audit trail. The command line is a thin wrapper over this layer
and holds no rules of its own, which is what makes the rules testable without
a terminal.
"""

from dipcount.service.district import (
    list_site,
    list_zone,
    move_site,
    remeasure_site,
    retire_site,
    site_history,
)

__all__ = [
    "list_site",
    "list_zone",
    "move_site",
    "remeasure_site",
    "retire_site",
    "site_history",
]
