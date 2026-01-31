"""The checks this package runs on itself.

Every one of these is a rule about the code that a test cannot express,
because it is a rule about all of the code rather than about one behaviour. Is
every public thing documented. Does any service import a store it should not.
Is there a module the test suite has never named. Coverage cannot answer the
last one: a module can be executed to ninety per cent by tests of something
else entirely and still be a module nobody has written a test about.

Each check runs as a module, prints what it found, and exits non zero when it
found something. They run from ``check.sh`` and again as their own ci job, so
a check that starts failing is as loud as a test that starts failing.
"""
