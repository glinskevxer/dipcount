"""The command line, which is a thin wrapper over the services.

Nothing here decides anything. A command reads what it was given, turns it
into the types the service layer wants, calls one service function, and prints
what came back. Any rule found in this package is a rule in the wrong place,
and the layer check says so.
"""
