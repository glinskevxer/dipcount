"""The command line is complete and says what everything is for.

Three things go wrong with a command line and none of them is caught by a
test, because a test drives the commands somebody remembered to write about.

A group can be defined and never added to the main command, so it exists,
imports cleanly, has tests of its own functions, and cannot be typed. An
option can be added without help text, so ``--help`` prints a name and leaves
the reader to guess. And a command can be given a name that already belongs to
another command in the same group, which click resolves by keeping the last
one.

This walks the actual click objects rather than the source, because what
matters is what got registered, not what looks as though it was.
"""

from __future__ import annotations

import importlib

import click

from dipcount.cli.main import cli
from dipcount.tools import source

CHECK = "check_cli"


def groups() -> dict[str, click.Group]:
    """Every group registered on the main command."""
    out: dict[str, click.Group] = {}
    for name, command in cli.commands.items():
        if isinstance(command, click.Group):
            out[name] = command
    return out


def defined_groups() -> dict[str, str]:
    """Every click group defined anywhere under the command line package."""
    out: dict[str, str] = {}
    for path in source.modules(under="cli"):
        module = source.dotted(path)
        if module.endswith((".main", ".options")) or path.name == "__init__.py":
            continue
        loaded = importlib.import_module(module)
        for name in dir(loaded):
            found = getattr(loaded, name)
            if isinstance(found, click.Group):
                out[found.name or name] = module
    return out


def unregistered() -> list[source.Finding]:
    """Every group that exists and cannot be typed."""
    registered = set(groups())
    return [
        source.Finding(module, f"defines the group {name}, which main does not add")
        for name, module in sorted(defined_groups().items())
        if name not in registered
    ]


def _commands(group: click.Group) -> list[tuple[str, click.Command]]:
    return sorted(group.commands.items())


def options_without_help() -> list[source.Finding]:
    """Every option that prints its name and nothing else."""
    out: list[source.Finding] = []
    for group_name, group in sorted(groups().items()):
        for name, command in _commands(group):
            for parameter in command.params:
                if isinstance(parameter, click.Option) and not parameter.help:
                    out.append(
                        source.Finding(
                            f"{group_name} {name}",
                            f"option {parameter.name} has no help",
                        ),
                    )
    return out


def commands_without_help() -> list[source.Finding]:
    """Every command with no summary line."""
    out: list[source.Finding] = []
    for group_name, group in sorted(groups().items()):
        for name, command in _commands(group):
            if not (command.help or command.short_help):
                out.append(source.Finding(f"{group_name} {name}", "has no help"))
    return out


def counted() -> tuple[int, int]:
    """How many groups and commands the program offers."""
    found = groups()
    return len(found), sum(len(one.commands) for one in found.values())


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return unregistered() + commands_without_help() + options_without_help()


def main() -> None:
    """Run the check."""
    found_groups, found_commands = counted()
    print(f"{CHECK}: {found_groups} groups, {found_commands} commands")
    source.run(CHECK, findings(), counted=found_commands)


if __name__ == "__main__":
    main()
