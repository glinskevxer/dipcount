"""The row type the models read themselves off.

This is one line and it lives on its own for a reason. A model that imports it
from the store package is a model that depends on the store, which is the one
direction the layering does not allow: the store knows about models because it
builds them, and nothing goes back the other way.

``sqlite3.Row`` is a mapping by column name. Anything that behaves like one
will do, which is what makes a model testable with a plain dictionary.
"""

from __future__ import annotations

import sqlite3

Row = sqlite3.Row
"""A database row, addressed by column name."""

__all__ = ["Row"]
