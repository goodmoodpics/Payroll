"""Transcription checks on the official tables: each bracket's base amount must
equal the previous base plus the previous rate times the bracket width."""
from decimal import Decimal as D

from nypayroll.tables import TaxTables

T = TaxTables(2026)


def _continuity(rows, tol, floor_rounding=D("0")):
    for (f0, b0, r0), (f1, b1, _) in zip(rows, rows[1:]):
        expected = D(b0) + (D(f1) - D(f0)) * D(r0)
        # floors printed rounded to whole dollars shift the base by up to rate * 0.50
        assert abs(expected - D(b1)) <= D(tol) + D(r0) * floor_rounding, (f1, expected, b1)


def test_federal_brackets_continuous():
    for variant, by_status in T.raw["federal"]["schedules"].items():
        for status, s in by_status.items():
            _continuity(s["brackets"], "0.01", D("0.5") if variant == "step2_checked" else D("0"))


PERIODS = {"weekly": 52, "biweekly": 26, "semimonthly": 24, "monthly": 12, "daily": 260}


def test_ny_annual_schedule_spot_values():
    # NY's column-5 amounts embed recapture adjustments, so they are not continuous;
    # check rows copied by hand from the printed annual schedules instead.
    m = T.raw["ny"]["method2"]
    assert m["single"]["tables"]["annual"][9] == ["265400", "0.0735", "19091.00"]
    assert m["single"]["tables"]["annual"][6] == ["107650", "0.0753", "5906.00"]
    assert m["married"]["tables"]["annual"][11] == ["1077550", "0.0765", "79369.00"]
    assert m["married"]["tables"]["annual"][9] == ["323200", "0.1349", "20854.00"]


def test_ny_period_tables_derive_from_annual():
    """Each per-period row is the annual row divided by pay periods (floors to whole dollars)."""
    for status, m in T.raw["ny"]["method2"].items():
        annual = m["tables"]["annual"]
        for period, n in PERIODS.items():
            rows = m["tables"][period]
            assert len(rows) == len(annual), (status, period)
            for (f, r, a), (fa, ra, aa) in zip(rows, annual):
                assert r == ra, (status, period, f)
                assert abs(D(f) - D(fa) / n) <= 1, (status, period, f)
                assert abs(D(a) - D(aa) / n) <= D("0.01"), (status, period, a)


def test_ny_table_a_matches_b_plus_c():
    m = T.raw["ny"]["method2"]
    # spot values printed in table A
    assert D(m["single"]["deduction"]["weekly"]) + 3 * D(m["single"]["exemption"]["weekly"]) == D("200.05")
    assert D(m["married"]["deduction"]["monthly"]) + 3 * D(m["married"]["exemption"]["monthly"]) == D("912.40")
    assert D(m["single"]["deduction"]["annual"]) + 10 * D(m["single"]["exemption"]["annual"]) == D("17400")
