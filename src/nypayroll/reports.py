"""Filing-prep summaries. These produce NUMBERS TO ENTER into the agency
portals/forms — nothing here files or pays anything."""
from __future__ import annotations

from decimal import Decimal

from .money import D, cents

ZERO = Decimal("0")


def _sum(rows, key):
    return cents(sum((D(r[key]) for r in rows), ZERO))


def quarter_of(pay_date: str) -> int:
    return (int(pay_date[5:7]) - 1) // 3 + 1


def form_941_summary(checks: list[dict], quarter: int) -> dict:
    rows = [c for c in checks if quarter_of(c["pay_date"]) == quarter]
    ss_tax = _sum(rows, "social_security")
    med_tax = _sum(rows, "medicare") + _sum(rows, "addl_medicare")
    emp_ss = cents(sum((D(r["employer"]["social_security"]) for r in rows), ZERO))
    emp_med = cents(sum((D(r["employer"]["medicare"]) for r in rows), ZERO))
    fed_wh = _sum(rows, "fed_withholding")
    return {
        "line_2_wages_tips": _sum(rows, "fit_wages"),
        "line_3_fed_income_tax_withheld": fed_wh,
        "line_5a_ss_wages": _sum(rows, "ss_wages"),
        "line_5c_medicare_wages": _sum(rows, "medicare_wages"),
        "total_ss_tax_both_shares": ss_tax + emp_ss,
        "total_medicare_tax_both_shares": med_tax + emp_med,
        "total_tax_before_adjustments": fed_wh + ss_tax + emp_ss + med_tax + emp_med,
        "note": "Compare to your actual deposits; fractions-of-cents adjustments (line 7) are not computed.",
    }


def nys45_summary(checks: list[dict], quarter: int) -> dict:
    rows = [c for c in checks if quarter_of(c["pay_date"]) == quarter]
    return {
        "total_gross_wages": _sum(rows, "gross"),
        "ny_income_tax_withheld": _sum(rows, "ny_withholding"),
        "nyc_income_tax_withheld": _sum(rows, "nyc_withholding"),
        "pfl_withheld": _sum(rows, "ny_pfl"),
        "sdi_withheld": _sum(rows, "ny_sdi"),
        "employer_sui_due": cents(sum((D(r["employer"]["sui"]) for r in rows), ZERO)),
        "note": "UI wages per employee and the NYS-45 attachments must be entered per the form instructions.",
    }


def w2_summary(checks: list[dict]) -> dict:
    return {
        "box_1_wages": _sum(checks, "fit_wages"),
        "box_2_fed_withheld": _sum(checks, "fed_withholding"),
        "box_3_ss_wages": _sum(checks, "ss_wages"),
        "box_4_ss_tax": _sum(checks, "social_security"),
        "box_5_medicare_wages": _sum(checks, "medicare_wages"),
        "box_6_medicare_tax": _sum(checks, "medicare") + _sum(checks, "addl_medicare"),
        "box_16_ny_wages": _sum(checks, "fit_wages"),
        "box_17_ny_withheld": _sum(checks, "ny_withholding"),
        "box_18_19_nyc_local_wages_withheld": (_sum(checks, "fit_wages"), _sum(checks, "nyc_withholding")),
        "box_14_ny_pfl": _sum(checks, "ny_pfl"),
        "box_14_ny_sdi": _sum(checks, "ny_sdi"),
        "note": "NY box 16 may differ from federal box 1 for items NY treats differently (e.g. 414(h)); review.",
    }
