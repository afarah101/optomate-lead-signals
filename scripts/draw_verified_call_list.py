"""Month-1 call list v2: verified, likely_corporate businesses only. Rules: docs/decisions/call-list-plan.md
("Month-1 list v2"). The draw and time bands are draw_month_call_list(); this script only builds its pool.

The licence holder column of the leads file is never read. No email column is read or written.
"""

import csv
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leads.dfw_filter import is_active_on  # noqa: E402
from signals.call_list import CALL_LIST_COLUMNS, _last_day_of, draw_month_call_list  # noqa: E402

DATA_DIR = ROOT / "data"
OVERLAP = DATA_DIR / "logs" / "2026-11_overlap_v1.csv"
LEADS = DATA_DIR / "leads" / "tdlr_hvac_dfw.csv"
OUT = DATA_DIR / "logs" / "2026-11_call_list_v2.csv"
SEED = 20261102
POOL_COLUMNS = ["licence_number", "business_name", "county", "business_phone", "entity_flag", "expiry_date"]
OUT_COLUMNS = CALL_LIST_COLUMNS + ["phone_unconfirmed"]


def _key(licence: str) -> str:
    return (licence or "").strip().lstrip("0")


def verified_pool(overlap_csv, leads_csv) -> tuple[list[dict], set[str], Counter]:
    """(pool rows for draw_month_call_list, licences whose phone is unconfirmed, how each verified row was judged)."""
    with open(leads_csv, newline="", encoding="utf-8") as f:
        leads = {_key(r["licence_number"]): {c: r[c] for c in POOL_COLUMNS if c in r} for r in csv.DictReader(f)}
    pool, unconfirmed, judged = [], set(), Counter()
    with open(overlap_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lead = leads.get(_key(row["licence_number"]))
            if lead is None:
                judged["not_in_leads"] += 1
                continue
            eligible = lead["entity_flag"] == "likely_corporate"
            judged[("eligible" if eligible else "not_eligible") + ("_was_unknown" if row["outreach_eligible"] == "unknown" else "")] += 1
            if not eligible:
                continue
            pool.append(lead | {"business_phone": row["reverse_phone"] or row["auto_phone"]})
            if row["reverse_phone_source"] == "Foursquare":
                unconfirmed.add(lead["licence_number"])
    return pool, unconfirmed, judged


def draw_verified_call_list(overlap_csv, leads_csv, seed=SEED, do_not_contact=frozenset(), call_month="2026-11"):
    pool, unconfirmed, judged = verified_pool(overlap_csv, leads_csv)
    month_end = _last_day_of(call_month)
    # The whole pool is drawn (it is under 100); size counts the rows draw_month_call_list will keep.
    size = sum(r["licence_number"] not in do_not_contact
               and is_active_on({"license_expiration_date_mmddccyy": r["expiry_date"]}, month_end) for r in pool)
    with tempfile.TemporaryDirectory() as tmp:
        pool_csv = Path(tmp) / "verified_pool.csv"
        with pool_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=POOL_COLUMNS)
            writer.writeheader()
            writer.writerows(pool)
        rows = draw_month_call_list(pool_csv, set(do_not_contact), seed, size=size, call_month=call_month)
    rows = [r | {"phone_unconfirmed": "yes" if r["licence_number"] in unconfirmed else ""} for r in rows]
    return rows, {"verified_rows": sum(judged.values()), "judged": dict(judged), "pool": len(pool), "drawn": len(rows)}


def write_verified_call_list(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as f:  # never overwritten: callers fill this sheet in
        writer = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    rows, summary = draw_verified_call_list(OVERLAP, LEADS)
    write_verified_call_list(rows, OUT)
    print(summary | {"bands": dict(Counter(r["time_band"] for r in rows)),
                     "phone_unconfirmed": sum(r["phone_unconfirmed"] == "yes" for r in rows),
                     "no_phone": sum(not r["business_phone"] for r in rows), "output": str(OUT)})
