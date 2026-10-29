"""Tests against the official 2026 publications.

Federal: Pub 15-T has no printed percentage-method example, so expected values
are worked by hand through Worksheet 1A (steps shown).
NY: the worked examples printed in NYS-50-T-NYS (1/26), pages 16 and 18.
"""
from decimal import Decimal as D

import pytest

from nypayroll.engine import W4, compute_paycheck, ny_method2_withholding


# --- federal (Worksheet 1A) ------------------------------------------------
def test_fed_single_biweekly(tables):
    # 1c 2000*26=52,000; 1g 8,600; 1i 43,400. Row 19,900: 1,240 + 23,500*12% = 4,060; /26 = 156.15
    assert compute_paycheck("2000", "biweekly", W4(), tables).fed_withholding == D("156.15")


def test_fed_married_step2_credits_extra(tables):
    # 1c 6000*12=72,000; 1g 0 (Step 2 checked). Step-2 MFJ row 66,500: 5,800 + 5,500*22% = 7,010
    # 2h 7,010/12=584.17; 3b 2,000/12=166.67; 3c 417.50; 4a +10 -> 427.50
    w4 = W4(fed_status="married", fed_step2_checked=True, fed_credits=D("2000"), fed_extra=D("10"))
    assert compute_paycheck("6000", "monthly", w4, tables).fed_withholding == D("427.50")


def test_fed_step4ab_and_hoh(tables):
    # weekly 1500*52=78,000; +4a 5,200 = 83,200; -4b 3,000 -8,600 = 71,600
    # HoH row 33,250: 1,770 + 38,350*12% = 6,372; /52 = 122.54
    w4 = W4(fed_status="head_of_household", fed_other_income=D("5200"), fed_deductions=D("3000"))
    assert compute_paycheck("1500", "weekly", w4, tables).fed_withholding == D("122.54")


def test_fed_below_threshold_is_zero(tables):
    # 300*26 = 7,800 - 8,600 < 0
    assert compute_paycheck("300", "biweekly", W4(), tables).fed_withholding == D("0.00")


# --- New York State (NYS-50-T-NYS examples) ---------------------------------
@pytest.mark.parametrize("wages,period,status,ex,expected", [
    ("400", "weekly", "single", 3, "8.01"),         # p.16 example 1
    ("50000", "monthly", "single", 3, "3576.63"),   # p.16 example 3
    ("400", "weekly", "married", 4, "6.69"),        # p.18 example 1
    ("50000", "monthly", "married", 3, "3622.09"),  # p.18 example 3
])
def test_ny_published_examples(tables, wages, period, status, ex, expected):
    assert ny_method2_withholding(tables, D(wages), period, status, ex) == D(expected)


@pytest.mark.parametrize("wages,status,ex,published,exact", [
    # p.16 example 2: publication rounds 165.00*0.0753=12.4245 to 12.43 -> 258.51
    ("5000", "single", 1, "258.51", "258.50"),
    # p.18 example 2: publication writes 58.80*0.0707=4.157 as 4.15 -> 248.11
    ("5000", "married", 3, "248.11", "248.12"),
])
def test_ny_published_examples_with_intermediate_rounding(tables, wages, status, ex, published, exact):
    """The publication rounds an intermediate step inconsistently in these two
    examples; we round once at the end, which differs by one cent."""
    got = ny_method2_withholding(tables, D(wages), "semimonthly", status, ex)
    assert got == D(exact)
    assert abs(got - D(published)) == D("0.01")


def test_ny_quarterly_uses_annual_schedule(tables):
    # 15,000*4 = 60,000 - 8,400 (single, 1 ex) = 51,600 -> row 13,900: 586 + 37,700*5.4% = 2,621.80; /4
    assert ny_method2_withholding(tables, D("15000"), "quarterly", "single", 1) == D("655.45")
