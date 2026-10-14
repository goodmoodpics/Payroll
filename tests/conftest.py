import copy

import pytest

from nypayroll.tables import TaxTables


def synthetic_tables() -> TaxTables:
    """SYNTHETIC brackets (10%/20% over 10,000 adj.) to test mechanics only.

    These are NOT official numbers. Official-number tests live in
    test_official_examples.py and are skipped until tables are verified.
    """
    t = TaxTables(2026, allow_unverified=True)
    raw = copy.deepcopy(t.raw)
    for name in ("federal", "ny"):
        for variant in raw[name]["schedules"].values():
            for status in variant.values():
                status["annual_adjustment"] = "10000"
                status["brackets"] = [["0", "0", "0.10"], ["50000", "5000", "0.20"]]
                if name == "ny":
                    status["per_allowance"] = "1000"
    return TaxTables(2026, allow_unverified=True, overrides=raw)


@pytest.fixture
def tables():
    return synthetic_tables()
