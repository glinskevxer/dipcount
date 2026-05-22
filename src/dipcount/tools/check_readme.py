"""Every command in the readme is a command.

A readme goes stale in one direction: the program changes and the transcript
does not. Somebody renames an option, the tests all pass because they were
updated with it, and the first thing a new reader types is the one thing that
no longer works.

So the commands in the readme are replayed against the click tree rather than
trusted. Not run, because that would want a book and a season of data, but
resolved: does the group exist, does the command exist inside it, and is every
option one the command takes. That catches every way a transcript goes stale
except a changed default, and it costs nothing.

The check also asks the other way round: is every group in the program
mentioned somewhere in the readme, so a whole area of the work cannot be added
without a line about it.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Final

import click

from dipcount.cli.main import cli
from dipcount.tools import source

CHECK = "check_readme"
DOCUMENT = "README.md"

_LINE: Final = re.compile(r"^dipcount\s+(.*)$")


def path() -> Path:
    """Where the readme lives."""
    return source.project_root() / DOCUMENT


def commands() -> list[tuple[list[str], int]]:
    """Every command the readme shows, with the line it is on."""
    out: list[tuple[list[str], int]] = []
    for number, line in enumerate(path().read_text().splitlines(), start=1):
        found = _LINE.match(line.strip())
        if found:
            out.append((shlex.split(found.group(1)), number))
    return out


def _strip_globals(words: list[str]) -> list[str]:
    out = list(words)
    for name in ("--book", "--actor", "--zone"):
        while name in out:
            at = out.index(name)
            del out[at : at + 2]
    return out


def _option_names(command: click.Command) -> set[str]:
    out: set[str] = set()
    for parameter in command.params:
        out.update(parameter.opts)
        out.update(parameter.secondary_opts)
    return out


def _resolve(words: list[str]) -> tuple[click.Command | None, str]:
    current: click.Command = cli
    for word in words:
        if word.startswith("-") or not isinstance(current, click.Group):
            break
        found = current.commands.get(word)
        if found is None:
            return None, f"{word} is not a command of {current.name}"
        current = found
    if isinstance(current, click.Group):
        return None, "stops at a group rather than a command"
    return current, ""


def bad_commands() -> list[source.Finding]:
    """Every readme command that will not resolve."""
    out: list[source.Finding] = []
    for words, number in commands():
        stripped = _strip_globals(words)
        command, why = _resolve(stripped)
        if command is None:
            out.append(source.Finding(DOCUMENT, f"{' '.join(stripped)}: {why}", number))
            continue
        allowed = _option_names(command) | {"--help"}
        for word in stripped:
            if word.startswith("--") and word not in allowed:
                out.append(
                    source.Finding(DOCUMENT, f"{command.name} has no option {word}", number),
                )
    return out


def unmentioned_groups() -> list[source.Finding]:
    """Every group the readme never mentions."""
    text = path().read_text()
    out: list[source.Finding] = []
    for name, command in sorted(cli.commands.items()):
        if not isinstance(command, click.Group):
            continue
        if name not in text:
            out.append(source.Finding(DOCUMENT, f"never mentions the {name} group"))
    return out


def sections() -> list[source.Finding]:
    """Every heading the readme is expected to carry."""
    text = path().read_text()
    return [
        source.Finding(DOCUMENT, f"has no {heading} section")
        for heading in ("## Installing", "## The layers", "## The checks")
        if heading not in text
    ]


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return sections() + bad_commands() + unmentioned_groups()


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=len(commands()))


if __name__ == "__main__":
    main()
