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

### The checks

Fourteen checks the package runs on itself, and three generated documents.
`check_wiring` found four helpers and two service entry points with no caller
and they were taken out. `check_indexes` found three foreign keys with no
index behind them, fixed as migration 16. `check_errors` found four clause
names in refusals that the rule book did not carry.
