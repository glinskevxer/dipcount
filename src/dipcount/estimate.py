"""Estimating an infection rate out of pooled testing.

Pools are tested, not mosquitoes. A positive pool of fifty says at least one
of the fifty was carrying, and there is no way to tell whether it was one or
forty. So the rate has to be estimated from how many pools came back positive
and how big they were, and the two numbers a district can put in a report mean
different things.

The minimum infection rate is positives over mosquitoes, times a thousand. It
is easy to work out and it is a floor rather than an estimate: it assumes
exactly one infected mosquito in every positive pool, which is true only when
infection is rare. As the rate climbs it reads further and further low.

The maximum likelihood estimate asks which rate makes the pattern of positive
and negative pools most likely. It handles pools of different sizes, it does
not assume one carrier per pool, and it is what the state wants. The interval
around it comes from the likelihood ratio rather than a normal approximation,
because with two positives out of forty pools there is nothing normal about
the shape.

Nothing here touches the book. Give it sizes and outcomes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from dipcount.errors import UsageError

PER: Final = 1000
"""Rates are quoted per thousand mosquitoes."""

CHI2_95: Final = 3.8414588206941236
"""The one degree of freedom chi square point for a ninety five percent bound."""

_TINY: Final = 1e-15


@dataclass(frozen=True)
class Estimate:
    """An infection rate with the numbers it came from."""

    pools: int
    positives: int
    mosquitoes: int
    rate: Decimal
    lower: Decimal
    upper: Decimal
    method: str = "maximum likelihood"

    @property
    def usable(self) -> bool:
        """Whether there were any pools to estimate from."""
        return self.pools > 0

    def line(self) -> str:
        """One line for a report."""
        if not self.usable:
            return "no pools tested"
        return (
            f"{self.rate:.2f} per {PER}"
            f"  ({self.lower:.2f} to {self.upper:.2f})"
            f"  {self.positives} of {self.pools} pools, {self.mosquitoes} mosquitoes"
        )


def _check(sizes: list[int], positives: list[bool]) -> None:
    if len(sizes) != len(positives):
        raise UsageError("every pool needs a size and an outcome")
    for size in sizes:
        if size < 1:
            raise UsageError("a pool of nothing cannot be tested")


def minimum_infection_rate(sizes: list[int], positives: list[bool]) -> Decimal:
    """Positives over mosquitoes, per thousand. A floor, not an estimate."""
    _check(sizes, positives)
    total = sum(sizes)
    if total == 0:
        return Decimal(0)
    found = sum(1 for one in positives if one)
    return Decimal(found * PER) / Decimal(total)


def _loglik(p: float, sizes: list[int], positives: list[bool]) -> float:
    if p <= 0:
        return -math.inf if any(positives) else 0.0
    if p >= 1:
        return -math.inf if not all(positives) else 0.0
    total = 0.0
    for size, hit in zip(sizes, positives, strict=True):
        miss = math.exp(size * math.log1p(-p))
        if hit:
            if miss >= 1.0 - _TINY:
                return -math.inf
            total += math.log1p(-miss)
        else:
            total += size * math.log1p(-p)
    return total


def _slope(p: float, sizes: list[int], positives: list[bool]) -> float:
    total = 0.0
    for size, hit in zip(sizes, positives, strict=True):
        miss = math.exp(size * math.log1p(-p))
        if hit:
            total += size * miss / ((1 - p) * (1 - miss))
        else:
            total -= size / (1 - p)
    return total


def likelihood_rate(sizes: list[int], positives: list[bool]) -> float:
    """The rate that makes what the laboratory saw most likely, as a fraction."""
    _check(sizes, positives)
    if not sizes:
        return 0.0
    if not any(positives):
        return 0.0
    if all(positives):
        return 1.0
    low, high = _TINY, 1.0 - _TINY
    for _ in range(200):
        mid = (low + high) / 2
        if _slope(mid, sizes, positives) > 0:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def _bound(
    sizes: list[int],
    positives: list[bool],
    best: float,
    target: float,
    *,
    upward: bool,
) -> float:
    """Walk out from the estimate until the likelihood has dropped enough."""
    peak = _loglik(best, sizes, positives)
    low, high = (best, 1.0 - _TINY) if upward else (_TINY, best)
    edge = high if upward else low
    if peak - _loglik(edge, sizes, positives) < target:
        return edge
    for _ in range(200):
        mid = (low + high) / 2
        dropped = peak - _loglik(mid, sizes, positives)
        if (dropped > target) == upward:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def estimate(sizes: list[int], positives: list[bool]) -> Estimate:
    """The likelihood estimate with a ninety five percent interval."""
    _check(sizes, positives)
    found = sum(1 for one in positives if one)
    if not sizes:
        return Estimate(0, 0, 0, Decimal(0), Decimal(0), Decimal(0))
    best = likelihood_rate(sizes, positives)
    target = CHI2_95 / 2
    lower = 0.0 if found == 0 else _bound(sizes, positives, best, target, upward=False)
    upper = 1.0 if found == len(sizes) else _bound(sizes, positives, best, target, upward=True)
    return Estimate(
        pools=len(sizes),
        positives=found,
        mosquitoes=sum(sizes),
        rate=_per_thousand(best),
        lower=_per_thousand(lower),
        upper=_per_thousand(upper),
    )


def _per_thousand(fraction: float) -> Decimal:
    return Decimal(str(round(fraction * PER, 4)))


def vector_index(abundance: Decimal, rate: Decimal) -> Decimal:
    """Abundance times infection rate, which is what the risk ladder reads.

    Abundance is females per trap night and the rate is per thousand, so the
    product is the number of infected females a trap would take in a night.
    """
    if abundance < 0 or rate < 0:
        raise UsageError("neither abundance nor an infection rate can be negative")
    return abundance * rate / Decimal(PER)
