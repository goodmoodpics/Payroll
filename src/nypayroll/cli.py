from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from decimal import Decimal

from . import contractors as con
from . import db, deadlines, reports
from .engine import PERIODS_PER_YEAR, YTD, W4, Deduction, compute_paycheck
from .money import D, cents
from .tables import TablesNotReady, TaxTables


def _w4_from_json(s: str) -> W4:
    raw = json.loads(s)
    for k in ("fed_credits", "fed_other_income", "fed_deductions", "fed_extra", "ny_extra"):
        if k in raw:
            raw[k] = D(raw[k])
    return W4(**raw)


def _ytd(prior: list[dict]) -> YTD:
    s = lambda k: sum((D(p[k]) for p in prior), Decimal("0"))
    return YTD(
        ss_wages=s("ss_wages"), medicare_wages=s("medicare_wages"), pfl_withheld=s("ny_pfl"),
        futa_wages=s("medicare_wages"), sui_wages=s("gross"),
    )


def cmd_employee_add(a, conn):
    w4 = {"fed_status": a.fed_status, "ny_status": a.ny_status, "ny_allowances": a.ny_allowances,
          "fed_step2_checked": a.step2, "nyc_resident": a.nyc}
    cur = conn.execute("INSERT INTO employees(name, ssn_last4, pay_period, w4, sui_rate) VALUES (?,?,?,?,?)",
                       (a.name, a.ssn_last4, a.period, json.dumps(w4), a.sui_rate))
    conn.commit()
    print(f"employee {cur.lastrowid} added")


def cmd_run(a, conn):
    tables = TaxTables(a.year, allow_unverified=a.allow_unverified)
    e = conn.execute("SELECT * FROM employees WHERE id=?", (a.employee,)).fetchone()
    pay_date = date.fromisoformat(a.date)
    prior = [p for p in db.paychecks_in_year(conn, pay_date.year, a.employee) if p["pay_date"] < a.date]
    ded = [Deduction(name=n, amount=D(v), reduces_income_tax=True) for n, v in (x.split("=") for x in a.pretax_deduction)]
    pc = compute_paycheck(a.gross, e["pay_period"], _w4_from_json(e["w4"]), tables, _ytd(prior), ded, e["sui_rate"])
    if tables.allow_unverified:
        print("!! DRY RUN: unverified tables in use — results are not valid for real payroll:", file=sys.stderr)
        for item in tables.unverified_items():
            print("   -", item, file=sys.stderr)
    print(f"{e['name']}  pay date {a.date}  ({e['pay_period']})")
    for label, val in [("Gross", pc.gross), ("Federal W/H", pc.fed_withholding), ("NY W/H", pc.ny_withholding), ("NYC W/H", pc.nyc_withholding),
                       ("Social Security", pc.social_security), ("Medicare", pc.medicare),
                       ("Addl Medicare", pc.addl_medicare), ("NY PFL", pc.ny_pfl), ("NY SDI", pc.ny_sdi),
                       *pc.deductions.items(), ("NET PAY", pc.net)]:
        print(f"  {label:<16}{val:>12}")
    if not a.dry_run and not tables.allow_unverified:
        db.save_paycheck(conn, a.employee, pay_date, pc)
        print("saved.")
    elif not a.dry_run:
        print("not saved (unverified tables).")


def cmd_report(a, conn):
    checks = db.paychecks_in_year(conn, a.year)
    if a.form == "941":
        out = reports.form_941_summary(checks, a.quarter)
    elif a.form == "nys45":
        out = reports.nys45_summary(checks, a.quarter)
    else:
        out = reports.w2_summary(checks)
    for k, v in out.items():
        print(f"{k:<36}{v}")


def cmd_deadlines(a, conn):
    today = date.today()
    for d, what in deadlines.year_deadlines(a.year):
        flag = "  <-- upcoming" if today <= d and (d - today).days <= 30 else ""
        print(f"{d}  {what}{flag}")


def cmd_contractor_add(a, conn):
    cur = conn.execute("INSERT INTO contractors(name, tin_last4, address, w9_on_file) VALUES (?,?,?,?)",
                       (a.name, a.tin_last4, a.address, int(a.w9)))
    conn.commit()
    print(f"contractor {cur.lastrowid} added")


def cmd_contractor_pay(a, conn):
    conn.execute("INSERT INTO contractor_payments(contractor_id, pay_date, amount, note) VALUES (?,?,?,?)",
                 (a.contractor, a.date, str(cents(a.amount)), a.note))
    conn.commit()
    print("payment recorded")


def cmd_1099(a, conn):
    tables = TaxTables(a.year, allow_unverified=True)
    threshold = tables.const("federal", "form_1099_nec_threshold")
    forms = con.needs_1099(con.year_totals(conn, a.year), threshold)
    verified = tables.raw["federal"]["constants"]["form_1099_nec_threshold"]["verified"]
    if not verified:
        print(f"!! 1099-NEC threshold ${threshold} is UNVERIFIED — confirm before filing.", file=sys.stderr)
    missing = [f["name"] for f in forms if not f["w9_on_file"]]
    if missing:
        print("!! no W-9 on file for:", ", ".join(missing), file=sys.stderr)
    sys.stdout.write(con.export_csv(forms))


def cmd_tables(a, conn):
    t = TaxTables(a.year, allow_unverified=True)
    items = t.unverified_items()
    print("All tables verified." if not items else "UNVERIFIED items (payroll will refuse to run):")
    for i in items:
        print(" -", i)


def main(argv=None):
    p = argparse.ArgumentParser(prog="nypayroll")
    p.add_argument("--db", default="payroll.db")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("employee-add")
    s.add_argument("name"); s.add_argument("--period", choices=PERIODS_PER_YEAR, required=True)
    s.add_argument("--ssn-last4"); s.add_argument("--fed-status", choices=["single", "married"], default="single")
    s.add_argument("--ny-status", choices=["single", "married"], default="single")
    s.add_argument("--ny-allowances", type=int, default=0); s.add_argument("--step2", action="store_true")
    s.add_argument("--nyc", action="store_true", help="employee lives in NYC (NYC resident tax withheld)")
    s.add_argument("--sui-rate", default="0"); s.set_defaults(fn=cmd_employee_add)

    s = sub.add_parser("run", help="calculate (and save) one paycheck")
    s.add_argument("--employee", type=int, required=True); s.add_argument("--gross", required=True)
    s.add_argument("--date", required=True); s.add_argument("--year", type=int, default=2026)
    s.add_argument("--pretax-deduction", action="append", default=[], metavar="NAME=AMOUNT")
    s.add_argument("--dry-run", action="store_true"); s.add_argument("--allow-unverified", action="store_true")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("report", help="filing-prep numbers")
    s.add_argument("form", choices=["941", "nys45", "w2"]); s.add_argument("--year", type=int, required=True)
    s.add_argument("--quarter", type=int, choices=[1, 2, 3, 4]); s.set_defaults(fn=cmd_report)

    s = sub.add_parser("deadlines"); s.add_argument("--year", type=int, default=date.today().year)
    s.set_defaults(fn=cmd_deadlines)

    s = sub.add_parser("contractor-add"); s.add_argument("name"); s.add_argument("--tin-last4")
    s.add_argument("--address", default=""); s.add_argument("--w9", action="store_true")
    s.set_defaults(fn=cmd_contractor_add)

    s = sub.add_parser("contractor-pay"); s.add_argument("--contractor", type=int, required=True)
    s.add_argument("--amount", required=True); s.add_argument("--date", required=True)
    s.add_argument("--note", default=""); s.set_defaults(fn=cmd_contractor_pay)

    s = sub.add_parser("1099", help="1099-NEC CSV for the year"); s.add_argument("--year", type=int, required=True)
    s.set_defaults(fn=cmd_1099)

    s = sub.add_parser("tables-status"); s.add_argument("--year", type=int, default=2026)
    s.set_defaults(fn=cmd_tables)

    a = p.parse_args(argv)
    conn = db.connect(a.db)
    try:
        a.fn(a, conn)
    except TablesNotReady as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
