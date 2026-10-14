"""SQLite storage. Full SSNs/TINs are never stored — last 4 digits only."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import date
from decimal import Decimal

from .engine import Paycheck

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, ssn_last4 TEXT, pay_period TEXT NOT NULL,
  w4 TEXT NOT NULL DEFAULT '{}', deductions TEXT NOT NULL DEFAULT '[]', sui_rate TEXT NOT NULL DEFAULT '0'
);
CREATE TABLE IF NOT EXISTS paychecks (
  id INTEGER PRIMARY KEY, employee_id INTEGER NOT NULL REFERENCES employees(id),
  pay_date TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contractors (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, tin_last4 TEXT, address TEXT, w9_on_file INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS contractor_payments (
  id INTEGER PRIMARY KEY, contractor_id INTEGER NOT NULL REFERENCES contractors(id),
  pay_date TEXT NOT NULL, amount TEXT NOT NULL, note TEXT
);
"""


def connect(path: str = "payroll.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _dec_default(o):
    if isinstance(o, Decimal):
        return str(o)
    raise TypeError(type(o))


def save_paycheck(conn, employee_id: int, pay_date: date, pc: Paycheck) -> int:
    data = json.dumps(asdict(pc), default=_dec_default)
    cur = conn.execute("INSERT INTO paychecks(employee_id, pay_date, data) VALUES (?,?,?)",
                       (employee_id, pay_date.isoformat(), data))
    conn.commit()
    return cur.lastrowid


def paychecks_in_year(conn, year: int, employee_id: int | None = None) -> list[dict]:
    q = "SELECT employee_id, pay_date, data FROM paychecks WHERE pay_date BETWEEN ? AND ?"
    args: list = [f"{year}-01-01", f"{year}-12-31"]
    if employee_id is not None:
        q += " AND employee_id = ?"
        args.append(employee_id)
    rows = conn.execute(q + " ORDER BY pay_date", args).fetchall()
    out = []
    for r in rows:
        d = json.loads(r["data"])
        d["employee_id"], d["pay_date"] = r["employee_id"], r["pay_date"]
        out.append(d)
    return out
