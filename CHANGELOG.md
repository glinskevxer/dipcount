# Changelog

## 0.1.0

The first season the district ran on this rather than on paper.

### The records

- Zones and sites, measured in acres or in structures depending on habitat.
- Larval inspections with tallies by species and stage, and a verdict off the
  rule book.
- Weather stations, daily observations, and heat units by three methods.
- Traps, collections, and females per trap night with the males left out.
- Pools sent to the laboratory, and one result for each virus.
- The product shelf with the label rate ranges, season caps and intervals.
- Lots in the shed, with stock worked out from the draws rather than stored.
- Treatments, carrying the certification number that was in force that day.
- Applicators, their licence categories and their recertification credits.
- The no spray register, spray blocks, notices and runs.
- Machines and calibrations, and the driving speed that hits a labelled rate.
- Service requests with an answer clock the season can shorten.
- Bottle bioassays, corrected for the control and voided when it is too high.

### The reports

- The reporting week, gathered onto one sheet.
- The season to date, and the board of what is out of date or overdue.
- The pesticide use return, holding back any row with a gap in it.
- Every register as a comma separated file.

### Keeping the book

- A backup taken through sqlite rather than the filesystem, so it can be taken
  while the round is coming in, and opened again before it is called a backup.
- A rota that keeps the newest few and prunes the rest.

### The checks

Fourteen checks the package runs on itself, and three generated documents.

What they found, in the order they found it:

- `check_wiring` named four command line helpers and two service entry points
  with no caller anywhere. They were taken out.
- `check_indexes` named three foreign keys with no index behind the child
  side. Fixed as migration 16, because a shipped migration is not edited.
- `check_errors` named four clause names used in refusals that the rule book
  did not carry. The clauses were written down.
- `check_rules` named four clauses nothing in the code referred to. They are
  named now by the index, the trend and the resistance finding.
- `check_design` named four functions long enough to be two. They are eight
  now, and each of them says one thing.

And two defects the tests found that no check could:

- Opening a book in a directory the process cannot write let sqlite's own
  error out, which says nothing to a caller trying to tell a bad request from
  a broken book.
- A backup taken from inside a grouped write does not fail. Python retries a
  busy source for ever, so the call hangs, which in a nightly job is a
  process nobody notices until the morning. It is refused with a sentence.
