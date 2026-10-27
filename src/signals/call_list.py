"""Signals domain: the monthly research call list, drawn with a seed fixed in docs/decisions/call-list-plan.md."""

import calendar
import csv
import random
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from calibration.select_test_groups import _draw
from leads.dfw_filter import is_active_on
from signals.contact_signals import do_not_contact_list, load_call_log

TIME_BANDS = ["morning", "afternoon", "evening"]
CALL_LIST_COLUMNS = [
    "licence_number", "business_name", "county", "business_phone", "time_band", "call_date", "result",
    "voicemail_greeting_present", "caller_initials", "stop_requested", "notes", "form_url", "form_sent_at_local",
    "form_first_reply_at_local",
]
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class CallListPoolTooSmall(ValueError):
    pass


def _last_day_of(call_month: str) -> date:
    year, month = map(int, call_month.split("-"))
    return date(year, month, calendar.monthrange(year, month)[1])


def draw_month_call_list(leads_csv, do_not_contact: set[str], seed: int, size: int = 100,
                         call_month: str = "2026-11") -> list[dict]:
    month_end = _last_day_of(call_month)
    with open(leads_csv, newline="", encoding="utf-8") as f:
        leads = {row["licence_number"]: row for row in csv.DictReader(f)}

    pool = sorted(
        licence for licence, lead in leads.items()
        if lead.get("entity_flag") == "likely_corporate"
        and licence not in do_not_contact
        # The call date isn't known at draw time, so the licence must still be active on the month's last day.
        and is_active_on({"license_expiration_date_mmddccyy": lead.get("expiry_date")}, month_end)
    )
    if len(pool) < size:
        raise CallListPoolTooSmall(f"need {size} businesses for {call_month}; the pool has {len(pool)}")

    rng = random.Random(seed)
    selected = _draw(rng, pool, size)
    band_order = {licence: rng.random() for licence in selected}
    rows = []
    for i, licence in enumerate(sorted(selected, key=band_order.__getitem__)):
        lead = leads[licence]
        rows.append({column: "" for column in CALL_LIST_COLUMNS} | {
            "licence_number": licence,
            "business_name": lead.get("business_name", ""),
            "county": lead.get("county", ""),
            "business_phone": lead.get("business_phone", ""),  # empty: TDLR leaves business_telephone blank
            "time_band": TIME_BANDS[i % len(TIME_BANDS)],
        })
    return sorted(rows, key=lambda r: r["licence_number"])


def write_call_list(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # "x" refuses to overwrite: callers fill this sheet in, and a re-run must never wipe their results.
    with path.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CALL_LIST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    # Optional argument: a call log whose stop requests (accepted or rejected rows) must be excluded.
    blocked = set()
    if len(sys.argv) > 1:
        calls, rejected = load_call_log(sys.argv[1])
        blocked = do_not_contact_list(calls + [r["row"] for r in rejected])
    rows = draw_month_call_list(DATA_DIR / "leads" / "tdlr_hvac_dfw.csv", blocked, seed=20261101)
    out = DATA_DIR / "logs" / "2026-11_call_list.csv"
    write_call_list(rows, out)
    print({"selected": len(rows), "bands": dict(Counter(r["time_band"] for r in rows)), "output": str(out)})
