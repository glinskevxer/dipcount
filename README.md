# dipcount

Records for a mosquito abatement district.

The district runs a surveillance programme over its own territory, decides
where to treat from what the surveillance found, applies pesticide under a
label, and reports the whole of it to the state. This holds the records behind
that work: the sites, the traps, the counts, the pools, the products, the
treatments, the applicators who made them, and the reports drawn off them.

Everything lives in one sqlite file, called the book.

## Installing

```
python -m pip install -e ".[dev]" -c constraints.txt
```

Python 3.12 or 3.13. The only runtime dependency is click.

## A season, from the command line

Start the book and lay out the district.

```
dipcount --book district.sqlite3 book init
dipcount --book district.sqlite3 zone add north --supervisor "R. Vandeburg"
dipcount --book district.sqlite3 site add north "Weller Road basins" --habitat catch_basin --extent "14 each" --on 2025-03-01
dipcount --book district.sqlite3 site add north "Sawyer marsh" --habitat cattail_marsh --extent "6 acre" --on 2025-03-01
```

Put the crew and the shelf on the books.

```
dipcount --book district.sqlite3 crew add "K. Brennaman" PA-44192 --grade certified --category core --category "public health" --category aquatic --certified 2024-03-01 --expires 2027-03-01
dipcount --book district.sqlite3 product stock --on 2025-01-15
dipcount --book district.sqlite3 lot receive "Bactilore G" 24G-1187 "400 lb" --on 2025-03-03
```

Work the larval round. The verdict comes back with the clauses that produced
it.

```
dipcount --book district.sqlite3 dip due --on 2025-06-04
dipcount --book district.sqlite3 dip record SI-0002 --at "2025-06-04 09:00" --dips 10 --count CXPP 2 12
dipcount --book district.sqlite3 treat plan SI-0002 "Bactilore G" --on 2025-06-04
dipcount --book district.sqlite3 treat apply SI-0002 LT-0001 --by AP-001 --at "2025-06-04 10:40"
```

Run the traps, send the pools, and read the week.

```
dipcount --book district.sqlite3 trap add "Ambrose gravid 1" north --kind gravid --on 2025-03-01
dipcount --book district.sqlite3 trap collect TR-0001 --set "2025-06-03 16:30" --pulled "2025-06-04 08:15" --catch CXPP F 120
dipcount --book district.sqlite3 pool submit CO-250604-01 CXPP 50 --on 2025-06-05
dipcount --book district.sqlite3 pool result PL-250605-01 "West Nile" positive --on 2025-06-09
dipcount --book district.sqlite3 virus week 2025-W23
```

Fogging is held until the wind, the hour and the no spray register all agree.

```
dipcount --book district.sqlite3 block add "Ardmore east grid" north --acres 640 --on 2025-04-01
dipcount --book district.sqlite3 register add "Ferrand apiary" north --kind apiary --contact "M. Ferrand" --on 2025-04-01
dipcount --book district.sqlite3 block link "Ardmore east grid" EX-0001
dipcount --book district.sqlite3 spray waiting "Ardmore east grid" --at "2025-07-10 21:10"
dipcount --book district.sqlite3 spray window "Ardmore east grid" --at "2025-07-10 21:10" --wind 4.5 --temperature 74
```

The weather, the shop and the bottle assays sit behind all of it.

```
dipcount --book district.sqlite3 wx station "Ambrose airport" north --opened 2025-01-01
dipcount --book district.sqlite3 wx record ST-0001 --on 2025-06-04 --high 84 --low 62 --rain 0.7
dipcount --book district.sqlite3 wx flood --on 2025-06-06
dipcount --book district.sqlite3 shop add 40-11872 --kind "ulv fogger" --maker Larkspur --model XLR-40 --nominal "1.5 fl oz" --swath 300 --on 2024-05-01
dipcount --book district.sqlite3 shop calibrate EQ-001 --on 2025-06-12 --flow "1.5 fl oz" --droplet 17 --speed 10
dipcount --book district.sqlite3 assay run S-methoprene CXPP --dose 43 --minutes 30 --on 2025-08-12 --zone north --bottle 1 20 25
dipcount --book district.sqlite3 assay board --on 2025-08-20
```

Report it.

```
dipcount --book district.sqlite3 report week 2025-W23
dipcount --book district.sqlite3 report season 2025
dipcount --book district.sqlite3 report board
dipcount --book district.sqlite3 report use --year 2025
dipcount --book district.sqlite3 report export all --into out
```

## The layers

Imports only go one way, and `check_layers` says so.

| layer | what it holds |
| --- | --- |
| leaves | errors, dates and weeks, units, identifiers, species, habitats, the rule book |
| `model` | the records, frozen, with no idea where they are stored |
| `store` | every table and every query, and nothing else |
| `service` | what the district does: the rules, in one place each |
| `report` | the same records arranged for somebody to read or file |
| `cli` | a thin wrapper that holds no rules of its own |
| `tools` | the checks the package runs on itself |

## The checks

`./check.sh` runs everything ci runs. The checks are rules about all of the
code, which a test cannot express:

| check | what it asks |
| --- | --- |
| `check_docstrings` | does every public thing say what it is for |
| `check_layers` | does any import point at a layer above it |
| `check_wiring` | is there code with no caller |
| `check_tests` | did anybody write a test about this module |
| `check_cli` | can every command be typed, and does it have help |
| `check_sql` | is all the SQL in the store, and does anything select every column |
| `check_indexes` | does every foreign key have an index behind it |
| `check_migrations` | has a shipped migration been edited |
| `check_naming` | is every test name a sentence |
| `check_errors` | does every refusal name a clause that exists |
| `check_design` | are the records frozen and the functions short |
| `check_rules` | is every clause used |
| `check_package` | does the packaging say what the code says |
| `check_readme` | is every command in this file a command |

Three documents are generated rather than written: `docs/RULES.md`,
`docs/SCHEMA.md` and `docs/GLOSSARY.md`. Editing them is not how they change.

## The parts worth reading first

- `dipcount/rules.py` is the rule book. Every refusal names a clause in it.
- `dipcount/service/larvicide.py` is where the label, the season cap and the
  shelf meet, and the order they meet in is the interesting part.
- `dipcount/service/adulticide.py` holds the four things that have to line up
  before a truck goes out.
- `dipcount/estimate.py` is the pooled infection rate, which is an estimate
  and not a count.
