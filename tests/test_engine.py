from decimal import Decimal as D

import pytest

from nypayroll.engine import YTD, W4, Deduction, compute_paycheck
from nypayroll.tables import TablesNotReady, TaxTables


def test_unverified_tables_are_refused():
    with pytest.raises(TablesNotReady):
        compute_paycheck("2000", "biweekly", W4(), TaxTables(2026))


def test_fica_basic(tables):
    pc = compute_paycheck("2000.00", "biweekly", W4(), tables)
    assert pc.social_security == D("124.00")
    assert pc.medicare == D("29.00")
    assert pc.addl_medicare == D("0.00")


def test_social_security_wage_base_cap(tables):
    # 184,500 base (flagged unverified, allowed in this test): only $1,000 of room left
    pc = compute_paycheck("5000", "biweekly", W4(), tables, ytd=YTD(ss_wages=D("183500")))
    assert pc.ss_wages == D("1000")
    assert pc.social_security == D("62.00")


def test_additional_medicare_over_threshold(tables):
    pc = compute_paycheck("10000", "monthly", W4(), tables, ytd=YTD(medicare_wages=D("195000")))
    assert pc.addl_medicare == D("45.00")  # (195000+10000-200000) * 0.9%


def test_pfl_cap(tables):
    pc = compute_paycheck("5000", "biweekly", W4(), tables, ytd=YTD(pfl_withheld=D("410")))
    assert pc.ny_pfl == D("1.91")


def test_sdi_capped_per_period(tables):
    assert compute_paycheck("5000", "weekly", W4(), tables).ny_sdi == D("0.60")
    assert compute_paycheck("5000", "biweekly", W4(), tables).ny_sdi == D("1.20")
    assert compute_paycheck("5000", "monthly", W4(), tables).ny_sdi == D("2.60")


def test_annualized_withholding_mechanics(tables):
    # 2000 biweekly -> 52,000 annual - 10,000 adj = 42,000 -> 10% = 4,200 -> /26
    pc = compute_paycheck("2000", "biweekly", W4(), tables)
    assert pc.fed_withholding == D("161.54")


def test_pretax_deduction_reduces_income_tax_not_fica(tables):
    ded = [Deduction("401k", D("200"), reduces_income_tax=True)]
    pc = compute_paycheck("2000", "biweekly", W4(), tables, deductions=ded)
    assert pc.social_security == D("124.00")  # FICA unaffected
    assert pc.fit_wages == D("1800")
    assert pc.fed_withholding < compute_paycheck("2000", "biweekly", W4(), tables).fed_withholding


def test_net_is_gross_minus_everything(tables):
    pc = compute_paycheck("2000", "biweekly", W4(ny_allowances=2), tables)
    assert pc.net == pc.gross - pc.total_employee_taxes


def test_employer_futa_and_sui_wage_bases(tables):
    pc = compute_paycheck("3000", "biweekly", W4(), tables,
                          ytd=YTD(futa_wages=D("6000"), sui_wages=D("12500")), sui_rate="0.041")
    assert pc.employer["futa"] == D("6.00")  # only $1,000 of FUTA room * 0.6%
    assert pc.employer["sui"] == D("20.50")  # only $500 of SUI room * 4.1%


def test_floats_rejected(tables):
    with pytest.raises(TypeError):
        compute_paycheck(2000.5, "biweekly", W4(), tables)
