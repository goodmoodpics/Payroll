from datetime import date
from decimal import Decimal as D

from nypayroll import contractors as con
from nypayroll import db, deadlines, reports
from nypayroll.cli import main
from nypayroll.engine import W4, compute_paycheck


def _checks(tables, n=6):
    out = []
    for i in range(n):
        pc = compute_paycheck("2000", "biweekly", W4(), tables, sui_rate="0.04")
        d = db.json.loads(db.json.dumps(db.asdict(pc), default=db._dec_default))
        d["pay_date"] = f"2026-0{1 + i // 2}-{10 + 14 * (i % 2):02d}"
        out.append(d)
    return out


def test_quarter_deadlines_roll_off_weekends():
    assert deadlines.quarter_end_due(2026, 1) == date(2026, 4, 30)  # Thursday
    assert deadlines.quarter_end_due(2026, 4) == date(2027, 2, 1)  # Jan 31 2027 is a Sunday
    assert deadlines.quarter_end_due(2026, 2) == date(2026, 7, 31)  # Friday


def test_year_deadlines_complete():
    items = deadlines.year_deadlines(2026)
    assert sum("Form 941" in w for _, w in items) == 4
    assert sum("NYS-45" in w for _, w in items) == 4
    assert sum("deposit" in w for _, w in items) == 12


def test_941_summary_totals(tables):
    checks = _checks(tables)
    q1 = [c for c in checks if reports.quarter_of(c["pay_date"]) == 1]
    s = reports.form_941_summary(checks, 1)
    assert s["line_5a_ss_wages"] == D("2000") * len(q1)
    assert s["total_ss_tax_both_shares"] == D("124.00") * 2 * len(q1)


def test_nys45_and_w2(tables):
    checks = _checks(tables)
    assert reports.nys45_summary(checks, 1)["total_gross_wages"] == D("12000.00")
    assert reports.w2_summary(checks)["box_4_ss_tax"] == D("124.00") * 6


def test_1099_threshold_and_missing_w9(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    conn.execute("INSERT INTO contractors(name, tin_last4, address, w9_on_file) VALUES ('A',  '1111','x',1)")
    conn.execute("INSERT INTO contractors(name, tin_last4, address, w9_on_file) VALUES ('B',  '2222','y',0)")
    for cid, amt in [(1, "1500.00"), (1, "700.50"), (2, "300.00")]:
        conn.execute("INSERT INTO contractor_payments(contractor_id, pay_date, amount) VALUES (?, '2026-05-01', ?)", (cid, amt))
    totals = con.year_totals(conn, 2026)
    assert [t["total"] for t in totals] == [D("2200.50"), D("300.00")]
    assert [t["name"] for t in con.needs_1099(totals, "2000")] == ["A"]
    assert "A,1111,x,2200.50,yes" in con.export_csv(con.needs_1099(totals, "2000"))


def test_cli_refuses_real_run_with_unverified_tables(tmp_path, capsys):
    dbp = str(tmp_path / "p.db")
    assert main(["--db", dbp, "employee-add", "Pat", "--period", "biweekly"]) == 0
    code = main(["--db", dbp, "run", "--employee", "1", "--gross", "2000", "--date", "2026-01-16"])
    assert code == 2
    assert "not verified" in capsys.readouterr().err
