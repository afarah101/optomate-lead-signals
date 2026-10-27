"""Signals domain: first-party contact signals from Optomate's own research calls and forms.

Rules live in docs/decisions/signal-rules.md. Loaders return (accepted_rows, rejected_rows); a rejected row is
{"line": csv_line_number, "row": raw_row, "reason": text} and is never dropped silently.
"""

import csv
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

DALLAS = ZoneInfo("America/Chicago")
CALL_RESULTS = {"answered_by_person", "voicemail", "no_answer", "invalid"}
MISSED_RESULTS = {"voicemail", "no_answer"}
TIME_BANDS = {
    "morning": (time(10, 0), time(12, 0)),
    "afternoon": (time(14, 0), time(16, 30)),
    "evening": (time(18, 0), time(19, 30)),
}
NO_REPLY = "no_reply"
NO_REPLY_AFTER_HOURS = 72.0


def _read_log(path) -> list[tuple[int, dict]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [(reader.line_num, row) for row in reader]


def _clean(raw: dict) -> tuple[dict, str | None]:
    if None in raw:
        return raw, "more values than columns"
    row = {k: (v or "").strip() for k, v in raw.items()}
    return row, None if row.get("licence_number") else "missing licence_number"


def _reject(rejected: list, line: int, raw: dict, reason: str) -> None:
    if (raw.get("stop_requested") or "").strip().lower() == "yes":
        reason += "; STOP REQUESTED on this row: still honour it"
    rejected.append({"line": line, "row": raw, "reason": reason})


def _call_problem(row: dict) -> str | None:
    try:
        call_at = datetime.strptime(f"{row.get('call_date', '')} {row.get('call_time_local', '')}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "call_date must be YYYY-MM-DD and call_time_local HH:MM"
    # Rewrite in canonical form so month keys and sorting work even if the log had "2026-1-5" or "9:05".
    row["call_date"], row["call_time_local"] = call_at.strftime("%Y-%m-%d"), call_at.strftime("%H:%M")
    call_time = call_at.time()
    result, band_name, greeting = row.get("result", ""), row.get("time_band", ""), row.get("voicemail_greeting_present", "")
    if result not in CALL_RESULTS:
        return f"unknown result {result!r}"
    if band_name not in TIME_BANDS:
        return f"unknown time_band {band_name!r}"
    start, end = TIME_BANDS[band_name]
    if not start <= call_time <= end:
        return f"call_time_local {row['call_time_local']} is outside the {band_name} band"
    if band_name != "evening":
        if greeting:
            return "voicemail_greeting_present is recorded on evening calls only"
    elif greeting not in ("", "yes", "no") or (result in MISSED_RESULTS and not greeting):
        return "evening voicemail/no_answer calls need voicemail_greeting_present yes or no"
    if row.get("stop_requested") not in ("yes", "no"):
        return "stop_requested must be yes or no"
    return None


def load_call_log(path) -> tuple[list[dict], list[dict]]:
    checked, rejected = [], []
    for line, raw in _read_log(path):
        row, problem = _clean(raw)
        problem = problem or _call_problem(row)
        if problem:
            _reject(rejected, line, raw, problem)
        else:
            checked.append((line, raw, row))

    calls, called_months, stopped_on = [], set(), {}
    for line, raw, row in sorted(checked, key=lambda c: (c[2]["call_date"], c[2]["call_time_local"], c[0])):
        licence, month = row["licence_number"], row["call_date"][:7]
        if licence in stopped_on:
            _reject(rejected, line, raw, f"business asked not to be called on {stopped_on[licence]}: do-not-contact")
        elif (licence, month) in called_months:
            _reject(rejected, line, raw, f"second call to this business in {month}: one call per month")
        else:
            called_months.add((licence, month))
            calls.append(row)
            if row["stop_requested"] == "yes":
                stopped_on[licence] = row["call_date"]
    return calls, sorted(rejected, key=lambda r: r["line"])


def _parse_local(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=DALLAS)


def _form_problem(row: dict) -> tuple[float | str | None, str | None]:
    try:
        sent = _parse_local(row.get("sent_at_local", ""))
        replied = _parse_local(row["first_reply_at_local"]) if row.get("first_reply_at_local") else None
    except ValueError:
        return None, "sent_at_local and first_reply_at_local must be YYYY-MM-DD HH:MM"
    row["sent_at_local"] = sent.strftime("%Y-%m-%d %H:%M")
    if replied is None:
        # shortcut: a form sent under 72 h ago with no reply yet also reads as no_reply; load logs after the window closes
        hours = NO_REPLY
    else:
        # Subtract in UTC so a daylight-saving change between send and reply is counted correctly.
        seconds = (replied.astimezone(timezone.utc) - sent.astimezone(timezone.utc)).total_seconds()
        if seconds < 0:
            return None, "first_reply_at_local is before sent_at_local"
        hours = round(seconds / 3600, 1)
        hours = NO_REPLY if hours > NO_REPLY_AFTER_HOURS else hours
    given = row.get("form_reply_hours", "")
    if given:
        try:
            matches = given == NO_REPLY if hours == NO_REPLY else round(float(given), 1) == hours
        except ValueError:
            matches = False
        if not matches:
            return None, f"form_reply_hours {given!r} disagrees with the computed {hours!r}"
    return hours, None


def load_form_log(path) -> tuple[list[dict], list[dict]]:
    checked, rejected = [], []
    for line, raw in _read_log(path):
        row, problem = _clean(raw)
        hours = None
        if not problem:
            hours, problem = _form_problem(row)
        if problem:
            _reject(rejected, line, raw, problem)
        else:
            checked.append((line, raw, {**row, "form_reply_hours": hours}))

    forms, sent_months = [], set()
    for line, raw, row in sorted(checked, key=lambda f: (f[2]["sent_at_local"], f[0])):
        key = (row["licence_number"], row["sent_at_local"][:7])
        if key in sent_months:
            _reject(rejected, line, raw, f"second form to this business in {key[1]}: one inquiry per month")
        else:
            sent_months.add(key)
            forms.append(row)
    return forms, sorted(rejected, key=lambda r: r["line"])


def _previous_month(year_month: str) -> str:
    year, month = map(int, year_month.split("-"))
    return f"{year - (month == 1)}-{(month - 2) % 12 + 1:02d}"


def monthly_missed_rate(calls: list[dict], licence_number: str, year_month: str) -> float | None:
    valid = [c for c in calls if c["licence_number"] == licence_number and c["call_date"][:7] == year_month
             and c["result"] != "invalid"]
    if not valid:
        return None
    return sum(c["result"] in MISSED_RESULTS for c in valid) / len(valid)


def missed_call_trend(calls: list[dict], licence_number: str, year_month: str) -> str | None:
    now = monthly_missed_rate(calls, licence_number, year_month)
    if now is None:
        return None
    before = monthly_missed_rate(calls, licence_number, _previous_month(year_month))
    if before is None:
        return "new"
    return "rising" if now > before else "falling" if now < before else "flat"


def do_not_contact_list(calls: list[dict]) -> set[str]:
    # Works on raw rejected rows too, so a stop request on a bad row is never lost.
    return {
        (c.get("licence_number") or "").strip() for c in calls
        if (c.get("stop_requested") or "").strip().lower() == "yes" and (c.get("licence_number") or "").strip()
    }


def summarise_contact_signals(calls: list[dict], forms: list[dict], year_month: str) -> list[dict]:
    blocked = do_not_contact_list(calls)
    businesses = {}
    for row in [*calls, *forms]:
        businesses.setdefault(row["licence_number"], row.get("business_name", ""))

    summary = []
    for licence, name in sorted(businesses.items()):
        call = next((c for c in calls if c["licence_number"] == licence and c["call_date"][:7] == year_month), None)
        form = next((f for f in forms if f["licence_number"] == licence and f["sent_at_local"][:7] == year_month), None)
        summary.append({
            "licence_number": licence,
            "business_name": name,
            "year_month": year_month,
            "missed_rate": monthly_missed_rate(calls, licence, year_month),
            "trend": missed_call_trend(calls, licence, year_month),
            "voicemail_greeting_present": call["voicemail_greeting_present"] if call else "",
            "form_reply_hours": form["form_reply_hours"] if form else "",
            "do_not_contact": "yes" if licence in blocked else "no",
        })
    return summary
