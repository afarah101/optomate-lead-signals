import csv
import random
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from signals.call_list import CALL_LIST_COLUMNS, CallListPoolTooSmall, draw_month_call_list, write_call_list

LEAD_COLUMNS = ["business_name", "licence_number", "expiry_date", "county", "entity_flag"]
SEED = 20261101


def lead(n, entity_flag="likely_corporate", expiry="06/03/2027"):
    return {"business_name": f"SAMPLE HVAC {n} LLC", "licence_number": f"S{n:04d}", "expiry_date": expiry,
            "county": "Dallas", "entity_flag": entity_flag}


def write_leads(tmp_path, rows, name="leads.csv"):
    path = tmp_path / name
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEAD_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def pool(n=150):
    return [lead(i) for i in range(n)]


def test_same_seed_gives_the_same_list(tmp_path):
    path = write_leads(tmp_path, pool())
    assert draw_month_call_list(path, set(), SEED) == draw_month_call_list(path, set(), SEED)


def test_row_order_does_not_matter(tmp_path):
    rows = pool()
    shuffled = rows[:]
    random.Random(7).shuffle(shuffled)
    first = draw_month_call_list(write_leads(tmp_path, rows, "a.csv"), set(), SEED)
    second = draw_month_call_list(write_leads(tmp_path, shuffled, "b.csv"), set(), SEED)
    assert first == second


def test_different_seed_gives_a_different_list(tmp_path):
    path = write_leads(tmp_path, pool())
    assert draw_month_call_list(path, set(), 1) != draw_month_call_list(path, set(), 2)


@pytest.mark.parametrize("size", [100, 99, 98, 7])
def test_band_counts_differ_by_at_most_one(tmp_path, size):
    rows = draw_month_call_list(write_leads(tmp_path, pool()), set(), SEED, size=size)
    counts = Counter(r["time_band"] for r in rows)
    assert len(rows) == size and set(counts) == {"morning", "afternoon", "evening"}
    assert max(counts.values()) - min(counts.values()) <= 1


def test_do_not_contact_is_excluded(tmp_path):
    blocked = {f"S{i:04d}" for i in range(0, 150, 2)}
    rows = draw_month_call_list(write_leads(tmp_path, pool()), blocked, SEED, size=75)
    assert len(rows) == 75 and not {r["licence_number"] for r in rows} & blocked


def test_unconfirmed_entities_are_excluded(tmp_path):
    rows = [lead(i, "unconfirmed") for i in range(100)] + [lead(i) for i in range(100, 110)]
    picked = draw_month_call_list(write_leads(tmp_path, rows), set(), SEED, size=10)
    assert {r["licence_number"] for r in picked} == {f"S{i:04d}" for i in range(100, 110)}


def test_licence_must_be_active_through_the_call_month(tmp_path):
    rows = [lead(0, expiry="11/29/2026"), lead(1, expiry="11/30/2026"), lead(2, expiry="12/01/2026"), lead(3, expiry="")]
    picked = draw_month_call_list(write_leads(tmp_path, rows), set(), SEED, size=2)
    assert {r["licence_number"] for r in picked} == {"S0001", "S0002"}


@pytest.mark.parametrize("blocked, expected", [(set(), 99), ({"S0000"}, 98)])
def test_short_pool_raises_with_the_count(tmp_path, blocked, expected):
    with pytest.raises(CallListPoolTooSmall, match=f"the pool has {expected}"):
        draw_month_call_list(write_leads(tmp_path, pool(99)), blocked, SEED)


def test_call_sheet_has_the_columns_and_empty_result_fields(tmp_path):
    rows = draw_month_call_list(write_leads(tmp_path, pool()), set(), SEED, size=3)
    out = tmp_path / "logs" / "call_list.csv"
    write_call_list(rows, out)
    with out.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        written = list(reader)
    assert reader.fieldnames == CALL_LIST_COLUMNS
    filled = {"licence_number", "business_name", "county", "time_band"}
    assert all(row[c] == "" for row in written for c in CALL_LIST_COLUMNS if c not in filled)


def test_call_sheet_is_never_overwritten(tmp_path):
    out = tmp_path / "call_list.csv"
    out.write_text("caller results\n")
    with pytest.raises(FileExistsError):
        write_call_list([], out)
    assert out.read_text() == "caller results\n"
