import csv
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from calibration.select_test_groups import select_calibration_groups
from leads.dfw_filter import LEAD_COLUMNS
from ranking.hot_lead_score import rank_dfw_leads
from ranking.write_ranked_leads import (LOGS_DIR, RANKED_COLUMNS, main, rank_and_write, ranked_leads_path,
                                        write_ranked_leads)

DALLAS = ZoneInfo("America/Chicago")
RANKED_AT = datetime(2026, 11, 14, 12, 0, tzinfo=DALLAS)  # every fixture form is well past 72 h
READER_DOC = ROOT / "docs" / "agents" / "sales-researcher.md"


def template_columns(name):  # the real log headers, from docs/templates
    with (ROOT / "docs" / "templates" / name).open(newline="", encoding="utf-8") as f:
        return next(csv.reader(f))


CALL_COLUMNS = template_columns("call_log_template.csv")
FORM_COLUMNS = template_columns("form_log_template.csv")
TDLR_COLUMNS = LEAD_COLUMNS + ["entity_flag"]  # data/leads/tdlr_hvac_dfw.csv as build_lead_list writes it


def write_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path


def lead(licence, entity_flag="likely_corporate"):
    return {"business_name": f"SAMPLE COOLING {licence} LLC", "licence_number": licence, "licence_type": "A/C Contractor",
            "licence_status": "active", "expiry_date": "2027-06-30", "address": "", "city": "", "county": "DALLAS",
            "source": "TDLR", "retrieved_on": "2026-10-29", "entity_flag": entity_flag}


def call(licence, result="answered_by_person", band="morning", at="10:30", greeting="", stop="no"):
    return {"licence_number": licence, "business_name": f"SAMPLE COOLING {licence} LLC", "call_date": "2026-11-05",
            "call_time_local": at, "time_band": band, "result": result, "voicemail_greeting_present": greeting,
            "caller_initials": "XX", "stop_requested": stop, "notes": ""}


def form(licence, reply=""):
    return {"licence_number": licence, "business_name": f"SAMPLE COOLING {licence} LLC",
            "form_url": "https://example.invalid/contact", "sent_at_local": "2026-11-06 09:00",
            "first_reply_at_local": reply, "form_reply_hours": "", "notes": ""}


@pytest.fixture
def logs(tmp_path):
    leads = write_csv(tmp_path / "tdlr_hvac_dfw.csv", TDLR_COLUMNS, [
        lead("113684"), lead("0113690"), lead("113701"), lead("113702", "unconfirmed"), lead("113703"),
    ])
    calls = write_csv(tmp_path / "call_log.csv", CALL_COLUMNS, [
        call("113684", "voicemail", band="evening", at="18:30", greeting="no"),              # hot, eligible
        call("0113690", "no_answer", band="evening", at="18:45", greeting="no"),             # hot, eligible
        call("113701"),                                                                      # cold, eligible
        call("113702", "voicemail", band="evening", at="18:30", greeting="no"),              # hot, entity unconfirmed
        call("113703", "voicemail", band="evening", at="18:30", greeting="no", stop="yes"),  # hot, asked to stop
    ])
    forms = write_csv(tmp_path / "form_log.csv", FORM_COLUMNS, [
        form("113684"), form("0113690"), form("113701", reply="2026-11-06 10:00"), form("113702"), form("113703"),
    ])
    return leads, calls, forms


def read_back(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- path and schema ---------------------------------------------------------------------------------------------

def test_path_is_the_exact_name_the_reader_opens():
    assert ranked_leads_path("2026-11") == ROOT / "data" / "logs" / "2026-11_ranked_leads.csv"
    assert LOGS_DIR == ROOT / "data" / "logs"
    assert 'RANK = Path(f"data/logs/{TODAY:%Y-%m}_ranked_leads.csv")' in READER_DOC.read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", ["2026-13", "2026-1", "202611", "2026-11-14", ""])
def test_bad_month_is_refused(bad):
    with pytest.raises(ValueError):
        ranked_leads_path(bad)


def test_columns_match_rank_dfw_leads_field_for_field(logs, tmp_path):
    rows = rank_dfw_leads(*logs, "2026-11", ranked_at=RANKED_AT)
    path = write_ranked_leads(rows, "2026-11", tmp_path / "out")
    with path.open(newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert header == RANKED_COLUMNS == list(rows[0])
    assert {"licence_number", "score", "band", "eligible"} <= set(header)  # the reader's required columns
    assert read_back(path) == [{k: str(v) for k, v in r.items()} for r in rows]


def test_rows_with_other_columns_are_refused(tmp_path):
    with pytest.raises(ValueError, match="expected"):
        write_ranked_leads([{"licence_number": "113684", "band": "hot"}], "2026-11", tmp_path)
    assert not (tmp_path / "2026-11_ranked_leads.csv").exists()


def test_rerun_replaces_the_file_and_leaves_no_temp_files(logs, tmp_path):
    out = tmp_path / "out"
    rank_and_write(*logs, "2026-11", ranked_at=RANKED_AT, logs_dir=out)
    path = rank_and_write(*logs, "2026-11", ranked_at=RANKED_AT, logs_dir=out)
    assert [p.name for p in out.iterdir()] == ["2026-11_ranked_leads.csv"]
    assert len(read_back(path)) == 5


def test_month_defaults_to_the_dallas_month_of_ranked_at(logs, tmp_path):
    late_night = datetime(2026, 11, 30, 23, 30, tzinfo=DALLAS)  # already 1 Dec in UTC
    assert rank_and_write(*logs, ranked_at=late_night, logs_dir=tmp_path).name == "2026-11_ranked_leads.csv"


def test_command_line_writes_the_file(logs, tmp_path, capsys):
    leads, calls, forms = logs
    main([str(calls), str(forms), "--month", "2026-11", "--leads", str(leads), "--logs-dir", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert "2026-11_ranked_leads.csv" in out and "'rows': 5" in out
    assert (tmp_path / "out" / "2026-11_ranked_leads.csv").exists()


# --- writer -> existing reader -> hot/eligible gate --------------------------------------------------------------

def reader_code():
    """The ranking reader and gate exactly as Script A in docs/agents/sales-researcher.md has them."""
    doc = READER_DOC.read_text(encoding="utf-8")
    helpers = "\n".join(re.search(rf"^def {name}\(.*$", doc, re.M)[0] for name in ("natural", "rows", "key"))
    block = re.search(r'^RANK = Path\(.*?\n(?=\nwith open\("data/leads/tdlr_hvac_dfw\.csv")', doc, re.M | re.S)[0]
    gate = re.search(r'if (ranked is not None and \(rk\.get\("band"\), rk\.get\("eligible"\)\) != \("hot", "yes"\))',
                     doc)[1]
    return helpers, block, gate


def run_reader(workdir, today, licences):
    helpers, block, gate = reader_code()
    scope = {"csv": csv, "re": re, "Path": Path, "TODAY": today}
    cwd = Path.cwd()
    try:
        os.chdir(workdir)  # the reader opens data/logs/... relative to the repo root
        exec(helpers + "\n" + block, scope)
        passed = []
        for licence in licences:
            k = scope["key"](licence)
            rk = (scope["ranked"] or {}).get(k, {})
            if not eval(gate, {}, {"ranked": scope["ranked"], "rk": rk}):
                passed.append(licence)
    finally:
        os.chdir(cwd)
    return scope["ranking_note"], scope["ranked"], passed


def test_reader_gate_keeps_only_hot_and_eligible_leads_from_the_written_file(logs, tmp_path):
    workdir = tmp_path / "repo"
    rank_and_write(*logs, "2026-11", ranked_at=RANKED_AT, logs_dir=workdir / "data" / "logs")
    call_list = ["113684", "113690", "113701", "113702", "113703", "999999"]  # call list keys may drop leading zeros
    note, ranked, passed = run_reader(workdir, date(2026, 11, 14), call_list)
    assert note == "Ranking: 2026-11_ranked_leads.csv (band hot and eligible yes only)."
    assert ranked is not None and len(ranked) == 5
    assert passed == ["113684", "113690"]  # hot + eligible; cold, unconfirmed, do-not-contact and unranked drop
    assert int(ranked["113684"]["score"]) == 3  # Script A casts score with int()


def test_reader_reports_missing_without_this_month_file(logs, tmp_path):
    workdir = tmp_path / "repo"
    rank_and_write(*logs, "2026-10", ranked_at=RANKED_AT, logs_dir=workdir / "data" / "logs")
    note, ranked, passed = run_reader(workdir, date(2026, 11, 14), ["113684", "113701"])
    assert ranked is None and note.startswith("RANKING OUT OF DATE") and passed == ["113684", "113701"]


def test_written_file_feeds_calibration_selection(logs, tmp_path):
    path = rank_and_write(*logs, "2026-11", ranked_at=RANKED_AT, logs_dir=tmp_path)
    groups = select_calibration_groups(read_back(path), seed=20261027, group_size=1)
    assert groups["hot"][0] in {"113684", "0113690"} and groups["cold"] == ["113701"]
