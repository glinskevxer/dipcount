# The rule book

Generated from `dipcount.rules` by `python -m dipcount.tools.build_rules`.
Edit the clause table, not this file.

62 clauses in 17 areas.

## adult

### adult.threshold

*a trap kind has its own figure*

Each kind of trap has an action figure in females per trap night. A light trap catches everything that flies and a gravid trap catches the few that have already fed, so the two figures are not comparable and neither is a total taken across both.

### adult.broken

*a trap that did not run is not a night of nothing*

A collection off a trap that was knocked over, or whose battery was flat, is left out of both halves of the index. Counting it as a night of zero drags the figure down for the whole week.

### adult.baseline

*twice the usual is the thing worth reporting*

A week is elevated when its index is at least twice the mean of the same week in the seasons before it. A district with three seasons behind it has a baseline; one without has a figure and no baseline, and the difference is reported rather than hidden.

## equipment

### equipment.calibration

*a machine works to its last calibration*

A calibration stands for thirty days. Past that the machine has not been shown to do anything, and what went on the ground is a guess written down as a figure.

### equipment.flow

*the flow has to be near what the machine is rated at*

Ten percent either way. Outside that the nozzle is worn or blocked, and the rate the paperwork claims is not the rate applied.

### equipment.droplet

*an ultra low volume machine has to make small droplets*

Over the ceiling the cloud falls out of the air. The mosquitoes never meet it and what has happened is a pesticide application to somebody's lawn.

### equipment.retired

*a machine out of service applies nothing*

A retired machine takes no calibration and makes no run, whatever the last one said about it and however busy the week is.

## label

### label.site

*a product goes where its label says and nowhere else*

The label names the kinds of water the product may be put into. A site whose habitat is not on the label cannot be treated with it at any rate.

### label.rate

*the rate is inside the range, both ends*

Under the bottom of the range is a treatment that will not work and over the top is an offence. Neither is a judgement call.

### label.season

*a season cap is a cap on the place, not on the visit*

The label limits what one acre or one structure may receive in a season. What is left of that cap after earlier treatments limits this one, and a cap that leaves less than the bottom of the rate range leaves no legal treatment at all rather than a smaller one.

### label.interval

*applications are spaced the way the label spaces them*

The days between two applications of one product at one place are the label's to set. A site treated inside the interval waits, whatever the dipper found.

### label.shelf

*a product off the shelf cannot be applied*

A product withdrawn before the day of the application is not available for it, whatever is still in the shed.

### label.form

*a formulation goes into water that takes it*

A rate cannot be written, and an application cannot be made, for a formulation the habitat does not take.

## larval

### larval.threshold

*when a site is worth treating*

A site is worth treating when the larvae per dip reach the figure for its habitat. Below that figure the visit is recorded and nothing is applied.

### larval.vector

*a vector in the sample halves the figure*

If any species in the sample carries a virus the district watches for, the habitat figure is halved before the count is compared to it.

### larval.pupal

*a brood that is mostly pupae is past treating*

When pupae are half or more of the immatures, a larvicide will not reach the brood. The site is not treated with one, and the next visit is set for the emergence rather than for the interval.

### larval.late

*third and fourth instars close the window*

When three quarters of the larvae are third or fourth instar the treatment has to go on within a day to be worth making at all.

### larval.raft

*egg rafts are a reason to come back, not to treat*

Egg rafts on their own do not meet any threshold. They shorten the interval to the next visit to four days.

### larval.dry

*a dry site is a result*

A site with no water is recorded as inspected. It is not treated, and it goes to the back of the round rather than off the list.

## licence

### licence.date

*an expired licence makes no applications*

The licence has a date and after it the holder applies nothing, of any kind, at any rate.

### licence.category

*the category has to cover the work*

Permanent water needs an aquatic category and everything else in this programme needs public health. A licence in another category is a licence for other work.

### licence.grade

*a restricted use product needs a certified applicator*

A technician may apply anything not restricted, working under a certified applicator. A trainee applies nothing alone.

### licence.credits

*credits are for renewal, not for working today*

Somebody short of credit hours in October is still licensed and still working. They will not be renewed. Reporting them as unlicensed is wrong and reporting them as fine is worse.

### licence.supervision

*only a certified applicator supervises*

A technician cannot be somebody else's supervisor, whatever the staffing that week looks like.

### licence.renewal

*a renewal runs forward*

A new certification period ends after the one it replaces. A renewal that shortens a licence is a typing mistake, and one that repeats the same dates is not a renewal.

### licence.left

*somebody leaves once*

A leaving date is written once and not written again. Somebody who comes back is added again, because the licence they come back with is not the one they left with.

## pool

### pool.jar

*a pool comes out of a jar and cannot be bigger than one*

Pools of a species out of one collection cannot add up to more females than were counted in it, because there is nowhere else they could have come from.

## product

### product.withdrawn

*a product comes off the shelf once*

A withdrawn product is not withdrawn again, and it cannot come off before the day it went on.

## report

### report.retention

*records are kept for two years after the season they belong to*

Two years is the floor, not the target. A record destroyed at two years and one day is a record that was not there when it was wanted.

### report.completeness

*an application with a gap in it is not reportable*

The state wants the day, the place, the product, the registration number, the amount, the area and who made it. A row missing any of those is a row the district cannot file.

## request

### request.clock

*the clock starts when the phone is put down*

The answer time runs from when the call was taken, not from when somebody got round to reading it, and a call answered late stays late however long afterwards it is closed.

### request.escalation

*a busy virus week shortens two of the clocks*

When the response level is high or above, dead bird and spray concern calls are answered in half the usual time. The other kinds do not move, because finding water does not get faster.

### request.visited

*a call is visited once*

The visit is the answer, and it is recorded once. Somebody going back a second time is answering a second call, and it is written down as one.

### request.closed

*a closed call takes no more work*

Nothing is assigned to it, visited on it, or closed again. Reopening work on a closed call means taking a new one, which is what keeps the answer times honest.

## resistance

### resistance.species

*a finding is about the species it was run on*

Resistance in a catch basin Culex says nothing about a floodplain producing Aedes. A finding only bears on a site whose habitat produces the species the bottles held.

### resistance.stale

*a finding has a shelf life*

Two seasons on, a bottle assay is history rather than evidence. It is still reported, and it is reported as old.

### resistance.rotation

*modes of action are rotated, not products*

Two products with different names and the same mode of action are one product as far as resistance is concerned. Three applications running in one mode at one site is a rotation that is not happening.

## site

### site.extent

*a site is measured in the unit its habitat uses*

Structures are counted one at a time and ground is measured in acres. A rate written for one cannot be applied over the other.

### site.retired

*a site comes off the list once*

A retired site is not retired again, and it cannot be retired before the day it was listed.

### site.zone

*a site belongs to one zone*

Moving a site to the zone it is already in is not a move, and a name already used in the receiving zone blocks one.

## spray

### spray.wind

*the wind has to be inside a band, not under a ceiling*

Over the top of the band the fog drifts off the block. Under the bottom of it there is nothing to carry the droplets and an inversion holds them where they were released. Still air is a refusal, not a perfect night.

### spray.temperature

*cold air does not carry a fog*

Below the floor the droplets fall out of the air and the mosquitoes are not flying to meet them anyway.

### spray.hours

*the truck runs at night*

Ground ultra low volume goes out when the target species are flying and the pollinators are not, which is after dusk and before the early hours.

### spray.notice

*everybody on the register inside the block is told first*

Notice is given for a place and a block together, covering a window the run falls inside, far enough ahead for the kind of entry. A notice for the neighbouring block is not notice.

### spray.absolute

*some entries take the block off the run*

An entry that no amount of notice gets round is not a delay. The block does not run, tonight or any night, until the entry comes off the register.

### spray.block

*a block comes off the run list once*

A retired block is not retired again, and it cannot be retired before the day it was listed.

### spray.register

*a register entry comes off once*

An entry is removed from the register once, and not before the day it went on.

### spray.acres

*a run covers no more than the block holds*

Part of a block may be run. More than the block is a measuring mistake and the rate that comes out of it is wrong in the comfortable direction.

## stock

### stock.short

*the shelf is the limit*

A draw larger than what is left of a lot is a counting mistake, and letting it through turns one mistake into a stock figure nobody can reconcile.

### stock.expired

*an out of date lot is not stock*

A lot past its date may be disposed of and may not be applied.

### stock.unit

*a lot is drawn in the unit it was received in*

A draw in another dimension is not a smaller draw, it is a different substance.

### stock.product

*a lot belongs to one product*

A treatment names a lot, and the product is read off the lot rather than typed in beside it.

## trap

### trap.retired

*a trap comes off the round once*

A retired trap takes no more collections, and it cannot be retired before the day it went up.

## treat

### treat.extent

*nothing is treated over more ground than it has*

The extent treated is measured in the habitat's unit and cannot exceed what the site was measured at.

## virus

### virus.vector

*only what carries the virus is in the rate for it*

A pool is tested whatever species it holds, and the result is kept. The infection rate for a virus is estimated over the pools of species that carry it, because a negative pool of something that could never have been positive says nothing about the rate.

### virus.pools

*an unreadable pool is neither positive nor negative*

A pool the laboratory reported as unsatisfactory is left out of both halves of the rate, and one still out at the laboratory has not happened yet.

### virus.week

*a pool belongs to the week it was caught in*

Results are reported against the reporting week the jar was pulled in, not the week the vial reached the laboratory. Two districts with different courier days have to be addable.

### virus.ladder

*the vector index is what the response level reads*

Abundance on its own and infection rate on its own each say half of it. The product is how many infected females a trap takes in a night, and the response level is read off that.

## weather

### weather.method

*a season is accumulated one way from end to end*

Degree days are counted by one method for the whole season. A total built one way cannot be compared with a total built another, and changing method part way through produces neither.

### weather.gap

*a missing day is not a day with no heat in it*

An accumulation over a window with missing readings is reported with the gaps named. Treating a gap as zero runs the total low for the rest of the season.

### weather.flood

*half an inch is a brood*

Rain of half an inch or more over a day puts every floodwater site in the zone on the round, ahead of its ordinary interval.

### weather.station

*a station reads between the day it opened and the day it closed*

A reading outside that is a reading from somewhere else, and a station is closed once.

## the figures the clauses use

| figure | value |
| --- | --- |
| adult thresholds | bg 5, gravid 10, light 50, resting 5 |
| elevated ratio | 2 |
| flood rain | 0.5 inch |
| larval thresholds | catch_basin 0.5, cattail_marsh 0.5, container 0.2, floodplain 1.0, lagoon 1.0, livestock_trough 0.2, ornamental_pond 0.2, retention_pond 0.5, roadside_ditch 1.0, snowmelt_pool 1.0, sump 0.5, tailwater 1.0, tyre_pile 0.2, woodland_pool 1.0 |
| late instar share | 0.75 |
| night hours | 20:00 to 02:00 |
| pupal stop | 0.5 |
| raft interval | 4 days |
| resistance shelf life | 730 days |
| response ladder | none 0, low 0.05, moderate 0.25, high 0.75, emergency 1.5 |
| retention | 2 years |
| rotation run | 3 |
| temperature floor | 50 |
| wind band | 1 to 10 mph |
