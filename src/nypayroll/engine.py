"""Gross-to-net paycheck calculation (federal + NY)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .money import D, cents
from .tables import TaxTables, WithholdingSchedule

PERIODS_PER_YEAR = {"weekly": 52, "biweekly": 26, "semimonthly": 24, "monthly": 12, "quarterly": 4}
ZERO = Decimal("0")


@dataclass
class Deduction:
    name: str
    amount: Decimal
    reduces_income_tax: bool = False  # e.g. traditional 401(k), sec. 125 health premiums
    reduces_fica: bool = False  # e.g. sec. 125 premiums (not 401(k))


@dataclass
class W4:
    """Federal W-4 (2020+) and NY IT-2104 inputs."""
    fed_status: str = "single"  # single | married | head_of_household
    fed_step2_checked: bool = False
    fed_credits: Decimal = ZERO  # step 3
    fed_other_income: Decimal = ZERO  # step 4(a)
    fed_deductions: Decimal = ZERO  # step 4(b)
    fed_extra: Decimal = ZERO  # step 4(c), per period
    ny_status: str = "single"  # IT-2104: single | married
    ny_allowances: int = 0
    ny_extra: Decimal = ZERO  # per period
    nyc_resident: bool = False  # NYC resident income tax is withheld on top of NYS tax


@dataclass
class YTD:
    """Year-to-date amounts BEFORE this paycheck."""
    ss_wages: Decimal = ZERO
    medicare_wages: Decimal = ZERO
    pfl_withheld: Decimal = ZERO
    futa_wages: Decimal = ZERO
    sui_wages: Decimal = ZERO


@dataclass
class Paycheck:
    gross: Decimal
    ss_wages: Decimal
    medicare_wages: Decimal
    fit_wages: Decimal
    fed_withholding: Decimal
    ny_withholding: Decimal
    nyc_withholding: Decimal
    social_security: Decimal
    medicare: Decimal
    addl_medicare: Decimal
    ny_pfl: Decimal
    ny_sdi: Decimal
    deductions: dict[str, Decimal]
    net: Decimal
    employer: dict[str, Decimal] = field(default_factory=dict)

    @property
    def total_employee_taxes(self) -> Decimal:
        return (self.fed_withholding + self.ny_withholding + self.nyc_withholding + self.social_security
                + self.medicare + self.addl_medicare + self.ny_pfl + self.ny_sdi)


def annualized_withholding(taxable_wages: Decimal, periods: int, sched: WithholdingSchedule,
                           extra_annual_adjustment: Decimal = ZERO) -> Decimal:
    """Annual-percentage method: annualize, adjust, bracket lookup, de-annualize.

    Returns tax for ONE period, unrounded, floored at zero.
    """
    adjusted = taxable_wages * periods - sched.annual_adjustment - extra_annual_adjustment
    if adjusted <= 0:
        return ZERO
    chosen = sched.brackets[0]
    for b in sched.brackets:
        if adjusted >= b.floor:
            chosen = b
    annual_tax = chosen.base + (adjusted - chosen.floor) * chosen.rate
    return max(annual_tax, ZERO) / periods


class MethodIIIRequired(NotImplementedError):
    pass


def ny_method2_withholding(tables: TaxTables, wages: Decimal, period: str, status: str,
                           exemptions: int, table: str = "ny") -> Decimal:
    """NYS-50-T Method II exact calculation, per-period tables.

    Quarterly has no NY per-period table: wages are annualized against the annual
    schedule and divided by 4 (same approach NY uses for its annualized tax).
    """
    m = tables.ny_method2(status, table)
    key, factor = (period, 1) if period != "quarterly" else ("annual", 4)
    allowance = D(m["deduction"][key]) + exemptions * D(m["exemption"][key])
    net = wages * factor - allowance
    if net <= 0:
        return ZERO
    if net >= D(m["limits"][key]):
        raise MethodIIIRequired("net wages exceed Method II range; NY Method III (top rates) not implemented")
    floor, rate, add = next(r for r in reversed(m["tables"][key]) if net >= D(r[0]))
    return cents(((net - D(floor)) * D(rate) + D(add)) / factor)


def compute_paycheck(
    gross,
    period: str,
    w4: W4,
    tables: TaxTables,
    ytd: YTD | None = None,
    deductions: list[Deduction] | None = None,
    sui_rate=ZERO,
) -> Paycheck:
    gross = D(gross)
    ytd = ytd or YTD()
    deductions = deductions or []
    periods = PERIODS_PER_YEAR[period]

    ded_fit = sum((d.amount for d in deductions if d.reduces_income_tax), ZERO)
    ded_fica = sum((d.amount for d in deductions if d.reduces_fica), ZERO)
    fit_wages = gross - ded_fit
    fica_wages = gross - ded_fica

    # --- FICA -------------------------------------------------------------
    ss_base = tables.const("federal", "ss_wage_base")
    ss_room = max(ss_base - ytd.ss_wages, ZERO)
    ss_taxable = min(fica_wages, ss_room)
    social_security = cents(ss_taxable * tables.const("federal", "ss_rate"))
    medicare = cents(fica_wages * tables.const("federal", "medicare_rate"))
    thresh = tables.const("federal", "addl_medicare_threshold")
    over = max(ytd.medicare_wages + fica_wages - max(thresh, ytd.medicare_wages), ZERO)
    addl = cents(over * tables.const("federal", "addl_medicare_rate"))

    # --- income tax withholding ------------------------------------------
    fed_variant = "step2_checked" if w4.fed_step2_checked else "standard"
    fed_sched = tables.schedule("federal", w4.fed_status, fed_variant)
    fed_annual_adj = w4.fed_deductions - w4.fed_other_income  # 4(b) subtracts, 4(a) adds
    fed_tax = annualized_withholding(fit_wages, periods, fed_sched, fed_annual_adj)
    fed_tax = max(fed_tax - w4.fed_credits / periods, ZERO)
    fed_withholding = cents(fed_tax + w4.fed_extra)

    ny_withholding = ny_method2_withholding(tables, fit_wages, period, w4.ny_status, w4.ny_allowances) + w4.ny_extra
    nyc_withholding = cents(ZERO)
    if w4.nyc_resident:
        nyc_withholding = ny_method2_withholding(tables, fit_wages, period, w4.ny_status, w4.ny_allowances, "nyc")

    # --- NY PFL / SDI -----------------------------------------------------
    pfl_cap_left = max(tables.const("ny", "pfl_annual_cap") - ytd.pfl_withheld, ZERO)
    ny_pfl = min(cents(gross * tables.const("ny", "pfl_rate")), pfl_cap_left)
    sdi_cap = cents(tables.const("ny", "sdi_weekly_cap") * 52 / periods)
    ny_sdi = min(cents(gross * tables.const("ny", "sdi_rate")), sdi_cap)

    ded_amounts = {d.name: cents(d.amount) for d in deductions}
    net = (gross - sum(ded_amounts.values(), ZERO) - fed_withholding - ny_withholding
           - nyc_withholding - social_security - medicare - addl - ny_pfl - ny_sdi)

    # --- employer side ----------------------------------------------------
    futa_room = max(tables.const("federal", "futa_wage_base") - ytd.futa_wages, ZERO)
    sui_room = max(tables.const("ny", "sui_wage_base") - ytd.sui_wages, ZERO)
    employer = {
        "social_security": social_security,  # employer match equals employee share
        "medicare": medicare,
        "futa": cents(min(fica_wages, futa_room) * tables.const("federal", "futa_net_rate")),
        "sui": cents(min(gross, sui_room) * D(sui_rate)),
    }
    return Paycheck(
        gross=cents(gross), ss_wages=ss_taxable, medicare_wages=fica_wages, fit_wages=fit_wages,
        fed_withholding=fed_withholding, ny_withholding=ny_withholding, nyc_withholding=nyc_withholding,
        social_security=social_security, medicare=medicare, addl_medicare=addl,
        ny_pfl=ny_pfl, ny_sdi=ny_sdi, deductions=ded_amounts, net=cents(net), employer=employer,
    )
