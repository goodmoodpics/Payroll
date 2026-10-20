# ny-payroll

Internal NY-state payroll calculator and **filing-prep** tool (single employer, plus 1099 freelancers).
It calculates paychecks and produces the numbers/files you enter into IRS, SSA and NY portals.
**It does not file or pay anything.**

## Status

| Piece | State |
|---|---|
| Paycheck engine (FICA, addl. Medicare, fed + NY withholding, NY PFL/SDI, FUTA/SUI employer side) | built, mechanics tested with synthetic tables |
| Official tax tables (IRS Pub 15-T, NYS-50-T-NYS) | **NOT LOADED** — see below |
| SQLite storage, CLI, pay runs with YTD caps | built |
| Filing-prep summaries (941, NYS-45, W-2) | built; figures only, not forms |
| Deadline calendar | built (monthly federal depositor; weekends roll, holidays don't) |
| 1099-NEC tracking + CSV | built; CSV must be mapped to the IRIS template |

### Payroll refuses to run until tables are verified
Each `src/nypayroll/data/<year>/*.json` file has `verified` flags. Real runs raise `TablesNotReady`
for anything unverified. `nypayroll tables-status` lists what's outstanding. Items to load/verify for 2026 (NYC resident schedule is the `nyc` variant in `ny.json`):

1. `federal.json`: Pub 15-T percentage-method schedules (standard + Step 2 checkbox, single/married), plus SS wage base, FUTA credit-reduction status, 1099-NEC threshold.
2. `ny.json`: NYS-50-T-NYS Method II schedules and per-allowance amount, plus the NY UI wage base.
3. Then add worked-example tests from the publications (`tests/test_official_examples.py`).

PFL (0.432%, $411.91 cap) was confirmed from NY DFS. Statutory FICA rates are marked verified.

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
