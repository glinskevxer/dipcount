"""The error types every layer raises.

Nothing in this package raises a bare ``Exception`` or a builtin. A caller
that wants to tell a bad request from a broken district needs the difference
in the type, and the command line needs it to pick an exit status. The rule
the tools enforce is that everything raised here descends from
:class:`DipcountError` and carries a sentence a field supervisor could read.
"""

from __future__ import annotations


class DipcountError(Exception):
    """Base for everything this package raises on purpose."""

    exit_status = 1


class UsageError(DipcountError):
    """The request was malformed before anything was looked up."""

    exit_status = 2


class NotFound(UsageError):
    """A record was named that the book does not hold."""

    exit_status = 3

    def __init__(self, kind: str, key: str) -> None:
        super().__init__(f"no {kind} named {key}")
        self.kind = kind
        self.key = key


class Duplicate(UsageError):
    """A record was offered under a key the book already holds."""

    exit_status = 4

    def __init__(self, kind: str, key: str) -> None:
        super().__init__(f"{kind} {key} is already on the books")
        self.kind = kind
        self.key = key


class RuleViolation(DipcountError):
    """The request was well formed and the rule book refuses it.

    The ``rule`` is the short name the rule table uses, so a refusal can be
    traced back to the clause that produced it without reading the message.
    """

    exit_status = 5

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule


class LabelViolation(RuleViolation):
    """The application would break the pesticide label.

    A label is federal law, so this is deliberately a type of its own rather
    than a rule violation with a label shaped message: nothing may catch it by
    accident and carry on.
    """

    exit_status = 6


class BookError(DipcountError):
    """The book itself is wrong: missing, unmigrated or corrupt."""

    exit_status = 7


class MigrationError(BookError):
    """A migration refused to run, or ran and left the book inconsistent."""

    exit_status = 8


def describe(error: BaseException) -> str:
    """One line naming the failure and its class, for the command line."""
    if isinstance(error, RuleViolation):
        return f"{type(error).__name__} [{error.rule}]: {error}"
    return f"{type(error).__name__}: {error}"


def status_for(error: BaseException) -> int:
    """The exit status a command should leave behind for ``error``."""
    if isinstance(error, DipcountError):
        return error.exit_status
    return 1
