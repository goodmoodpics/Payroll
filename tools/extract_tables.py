"""Extract withholding tables from `pdftotext -layout` output of IRS Pub 15-T and NYS-50-T-NYS.

Usage: python -I tools/extract_tables.py p15t.txt nys50_t_nys.txt > tables.json
Layout-dependent: re-check against the PDFs each year.
"""
import json
import re
import sys

NUM = r"\$?([\d,]+(?:\.\d+)?)%?"


def nums(line):
    return [x.replace(",", "") for x in re.findall(r"\$?([\d][\d,]*(?:\.\d+)?)", line)]


def federal(text):
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if "2026 Percentage Method Tables for Automated Payroll" in l and "Systems and" in l)
    out, section = {}, None
    names = {"Married Filing Jointly": "married", "Single or Married Filing Separately": "single", "Head of Household": "head_of_household"}
    for l in lines[start:start + 60]:
        for k, v in names.items():
            if k in l:
                section = v
                out[section] = {"standard": [], "step2_checked": []}
        n = nums(l)
        if section and len(n) in (8, 10):
            half = len(n) // 2
            for variant, row in (("standard", n[:half]), ("step2_checked", n[half:])):
                a, c, d = row[0], row[-3], row[-2]  # A, C, D (E repeats A)
                out[section][variant].append([a, c, str(round(float(d) / 100, 4))])
    return out


def ny(text):
    lines = text.splitlines()
    out = {}
    for status, marker in (("single", "Single                   NYS-50-T-NYS (1/26) Page 17"),
                           ("married", "Married                   NYS-50-T-NYS (1/26) Page 19")):
        i = next(i for i, l in enumerate(lines) if marker in l)
        block = lines[i:i + 90]
        tables, order = {}, [("weekly", "monthly"), ("biweekly", "daily"), ("semimonthly", "annual")]
        limits = {}
        k = -1
        for l in block:
            if "Table II - A" in l or "Table II - B" in l or "Table II - C" in l:
                k += 1
                left, right = order[k]
                tables[left], tables[right] = [], []
                continue
            m = re.match(r"^\s*(\d+)\s", l)
            n = nums(l)
            if k >= 0 and m and len(n) == 12:
                for name, row in ((order[k][0], n[1:6]), (order[k][1], n[7:12])):
                    tables[name].append([row[0], row[3], row[4]])  # floor, rate, add
                    limits[name] = row[1]  # upper bound of the last row
        out[status] = {"tables": tables, "limits": limits}
    return out


if __name__ == "__main__":
    fed = federal(open(sys.argv[1]).read())
    nyt = ny(open(sys.argv[2]).read())
    json.dump({"federal": fed, "ny": nyt}, sys.stdout, indent=1)
