"""Versioned tax tables.

Every table lives in data/<year>/<name>.json and carries `source` and
`verified`. Withholding math never runs on a table that is unverified or
empty unless the caller explicitly opts in (tests, dry-runs).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from importlib import resources

from .money import D


class TablesNotReady(RuntimeError):
    pass


@dataclass(frozen=True)
class Bracket:
    floor: Decimal  # annual taxable wages at which this bracket starts
    base: Decimal  # tax on wages up to `floor`
    rate: Decimal  # marginal rate above `floor`


@dataclass(frozen=True)
class WithholdingSchedule:
    """Annualized-percentage-method schedule for one filing status."""
    annual_adjustment: Decimal  # standard deduction-equivalent subtracted first
    brackets: tuple[Bracket, ...]
    per_allowance: Decimal = Decimal("0")  # NY IT-2104 allowance value, if applicable


def _load_json(year: int, name: str) -> dict:
    path = resources.files("nypayroll") / "data" / str(year) / f"{name}.json"
    return json.loads(path.read_text())


class TaxTables:
    def __init__(self, year: int, allow_unverified: bool = False, overrides: dict | None = None):
        self.year = year
        self.allow_unverified = allow_unverified
        self.raw = {n: _load_json(year, n) for n in ("federal", "ny")}
        if overrides:
            for k, v in overrides.items():
                self.raw[k] = v

    # -- gating -----------------------------------------------------------
    def _require(self, table: str) -> dict:
        t = self.raw[table]
        if self.allow_unverified:
            return t
        if not t.get("verified"):
            raise TablesNotReady(
                f"{table} {self.year} tables are not verified against the official "
                f"source ({t.get('source')}). Fill in/verify data/{self.year}/{table}.json "
                "or pass allow_unverified for a dry run."
            )
        return t

    def unverified_items(self) -> list[str]:
        out = []
        for name, t in self.raw.items():
            if not t.get("verified"):
                out.append(f"{name}: {t.get('source')}")
            for key, val in t.get("constants", {}).items():
                if isinstance(val, dict) and not val.get("verified", True):
                    out.append(f"{name}.{key}: {val.get('note', '')}")
        return out

    # -- constants --------------------------------------------------------
    def const(self, table: str, key: str) -> Decimal:
        entry = self.raw[table]["constants"][key]
        if not self.allow_unverified and not entry.get("verified", False):
            raise TablesNotReady(f"{table}.{key} is not verified: {entry.get('note', '')}")
        return D(entry["value"])

    # -- withholding schedules -------------------------------------------
    def schedule(self, table: str, status: str, variant: str = "standard") -> WithholdingSchedule:
        t = self._require(table)
        try:
            s = t["schedules"][variant][status]
        except KeyError as e:
            raise TablesNotReady(f"{table} schedule {variant}/{status} missing") from e
        brackets = tuple(Bracket(D(f), D(b), D(r)) for f, b, r in s["brackets"])
        if not brackets:
            raise TablesNotReady(f"{table} schedule {variant}/{status} has no brackets yet")
        return WithholdingSchedule(D(s["annual_adjustment"]), brackets, D(s.get("per_allowance", "0")))
