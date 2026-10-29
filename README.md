# ny-payroll

Internal NY-state payroll calculator and **filing-prep** tool (single employer, plus 1099 freelancers).
It calculates paychecks and produces the numbers/files you enter into IRS, SSA and NY portals.
**It does not file or pay anything.**

## Status

| Piece | State |
|---|---|
| Paycheck engine (FICA, addl. Medicare, fed + NY withholding, NY PFL/SDI, FUTA/SUI employer side) | built |
| Federal withholding (Pub 15-T 2026, automated percentage method) | **loaded**, hand-worked Worksheet 1A tests |
| NYS withholding (NYS-50-T-NYS 1/26, Method II) | **loaded**, passes the publication's worked examples |
| NYC resident withholding | **not loaded** — needs NYS-50-T-NYC |
| SQLite storage, CLI, pay runs with YTD caps | built |
| Filing-prep summaries (941, NYS-45, W-2) | built; figures only, not forms |
| Deadline calendar | built (monthly federal depositor; weekends roll, holidays don't) |
| 1099-NEC tracking + CSV | built; CSV must be mapped to the IRIS template |

### Payroll refuses to run until everything is verified
`nypayroll tables-status` lists outstanding items. Remaining for 2026:

- SS wage base, FUTA credit-reduction status, 1099-NEC threshold (`federal.json` constants)
- NY UI taxable wage base (`ny.json` constant)
- NYC resident tables (NYS-50-T-NYC) — only needed if the employee lives in NYC

Tables are extracted with `tools/extract_tables.py` from `pdftotext -layout` output and checked by
`tests/test_table_integrity.py` (bracket continuity, per-period vs. annual consistency, spot values).

Notes: NY quarterly pay has no per-period table, so it annualizes against NY's annual schedule.
Two NY published examples (p.16 ex. 2, p.18 ex. 2) round an intermediate step inconsistently; we round
once at the end and differ by $0.01 — documented in `tests/test_official_examples.py`.
NY Method III (net wages above ~$1M/yr annualized) is not implemented and raises an error.

## Usage
```
python -m venv .venv && .venv/bin/pip install -e . pytest
nypayroll employee-add "Pat Example" --period biweekly --ssn-last4 1234 --ny-allowances 1
nypayroll run --employee 1 --gross 2000 --date 2026-01-16 --dry-run --allow-unverified   # dry run only
nypayroll report 941 --year 2026 --quarter 1
nypayroll deadlines --year 2026
nypayroll contractor-add "Freelancer" --tin-last4 9999 --w9
nypayroll contractor-pay --contractor 1 --amount 1500 --date 2026-03-01
nypayroll 1099 --year 2026 > 1099.csv
```
Only the last 4 digits of SSNs/TINs are stored. Keep the database file out of git (already ignored).

## Not modeled yet
Semiweekly federal deposit rules, NYS-1 deposit schedules, Yonkers withholding, MCTMT, supplemental-wage
withholding, garnishments, minimum-wage/overtime checks, corrections/amended returns.
