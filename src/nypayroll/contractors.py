"""1099-NEC tracking."""
from __future__ import annotations

import csv
import io
from decimal import Decimal

from .money import D, cents


def year_totals(conn, year: int) -> list[dict]:
    rows = conn.execute(
        """SELECT c.id, c.name, c.tin_last4, c.address, c.w9_on_file, p.amount
           FROM contractors c JOIN contractor_payments p ON p.contractor_id = c.id
           WHERE p.pay_date BETWEEN ? AND ?""", (f"{year}-01-01", f"{year}-12-31")).fetchall()
    totals: dict[int, dict] = {}
    for r in rows:
        t = totals.setdefault(r["id"], {"id": r["id"], "name": r["name"], "tin_last4": r["tin_last4"],
                                        "address": r["address"], "w9_on_file": bool(r["w9_on_file"]),
                                        "total": Decimal("0")})
        t["total"] += D(r["amount"])
    for t in totals.values():
        t["total"] = cents(t["total"])
    return sorted(totals.values(), key=lambda t: t["name"])


def needs_1099(totals: list[dict], threshold) -> list[dict]:
    return [t for t in totals if t["total"] >= D(threshold)]


def export_csv(forms: list[dict]) -> str:
    """Generic recipient/amount CSV. Map columns to the IRS IRIS CSV template
    before uploading — the IRIS template layout is not reproduced here."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["recipient_name", "tin_last4", "address", "box_1_nonemployee_compensation", "w9_on_file"])
    for f in forms:
        w.writerow([f["name"], f["tin_last4"], f["address"], f["total"], "yes" if f["w9_on_file"] else "NO"])
    return out.getvalue()
