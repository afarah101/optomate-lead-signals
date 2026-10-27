"""Ranking domain: the Month-1 composite score and which DFW leads are eligible for the calibration test.

Rules live in docs/decisions/signal-rules.md under "Month-1 composite score".
"""

import csv
import sys
from datetime import datetime, timedelta, timezone

from signals.contact_signals import (
    DALLAS, NO_REPLY, NO_REPLY_AFTER_HOURS, _parse_local, do_not_contact_list, load_call_log, load_form_log,
    summarise_contact_signals,
)

SLOW_FORM_REPLY_HOURS = 24  # a judgment recorded before any data; see signal-rules.md


def score_contact_signals(summary_row: dict) -> int:
    reply = summary_row.get("form_reply_hours")
    return (
        int(bool(summary_row.get("missed_rate")))  # one call a month, so any missed rate means the call was missed
        + int(summary_row.get("voicemail_greeting_present") == "no")
        + int(reply == NO_REPLY or (isinstance(reply, (int, float)) and reply > SLOW_FORM_REPLY_HOURS))
    )


def lead_band(score: int) -> str:
    return "hot" if score >= 2 else "cold" if score == 0 else "middle"


def _report_rejected(log_name: str, rejected: list[dict]) -> None:
    for r in rejected:
        print(f"{log_name} line {r['line']} rejected: {r['reason']}", file=sys.stderr)


def rank_dfw_leads(leads_csv, call_log, form_log, year_month: str, ranked_at: datetime | None = None) -> list[dict]:
    calls, rejected_calls = load_call_log(call_log)
    forms, rejected_forms = load_form_log(form_log)
    _report_rejected("call log", rejected_calls)
    _report_rejected("form log", rejected_forms)

    ranked_at = ranked_at or datetime.now(DALLAS)
    if ranked_at.tzinfo is None:
        ranked_at = ranked_at.replace(tzinfo=DALLAS)
    # A form counts only once its 72-hour reply window has closed, so no_reply is final, not "still waiting".
    window_closed_by = ranked_at.astimezone(timezone.utc) - timedelta(hours=NO_REPLY_AFTER_HOURS)
    settled_form = {
        f["licence_number"] for f in forms
        if f["sent_at_local"][:7] == year_month
        and _parse_local(f["sent_at_local"]).astimezone(timezone.utc) <= window_closed_by
    }

    # Stop requests on rejected rows still count, so build the list from every logged call.
    blocked = do_not_contact_list(calls + [r["row"] for r in rejected_calls])
    signals = {row["licence_number"]: row for row in summarise_contact_signals(calls, forms, year_month)}

    with open(leads_csv, newline="", encoding="utf-8") as f:
        leads = list(csv.DictReader(f))

    ranked = []
    for lead in leads:
        licence = lead["licence_number"]
        signal = signals.get(licence, {})
        score = score_contact_signals(signal)
        eligible = (
            licence not in blocked
            and lead.get("entity_flag") == "likely_corporate"
            and signal.get("missed_rate") is not None  # no rate means no valid call this month
            and licence in settled_form  # a form sent this month, at least 72 h ago
        )
        ranked.append({
            "licence_number": licence,
            "business_name": lead.get("business_name", ""),
            "county": lead.get("county", ""),
            "entity_flag": lead.get("entity_flag", ""),
            "score": score,
            "band": lead_band(score),
            "eligible": "yes" if eligible else "no",
            "manual_entity_check": "required" if eligible else "",
        })
    return sorted(ranked, key=lambda r: (-r["score"], r["licence_number"]))
