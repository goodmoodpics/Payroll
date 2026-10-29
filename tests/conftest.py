import copy

import pytest

from nypayroll.tables import TaxTables


def dev_tables() -> TaxTables:
    """Official 2026 federal/NYS tables, with unverified constants allowed and a
    SYNTHETIC NYC table (a copy of the NYS tables) so NYC mechanics can be tested
    before NYS-50-T-NYC is loaded. NYC numbers from this fixture are not real."""
    t = TaxTables(2026, allow_unverified=True)
    raw = copy.deepcopy(t.raw)
    raw["ny"]["nyc"] = {"verified": True, "source": "SYNTHETIC test copy", "method2": raw["ny"]["method2"]}
    return TaxTables(2026, allow_unverified=True, overrides=raw)


@pytest.fixture
def tables():
    return dev_tables()
