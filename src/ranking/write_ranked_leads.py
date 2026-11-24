"""Ranking domain: save the month's ranked leads where the Sales Researcher reads them.

The reader is Script A in docs/agents/sales-researcher.md. It opens exactly data/logs/<YYYY-MM>_ranked_leads.csv for
the current month, needs the columns licence_number, score, band and eligible, and keeps a row only with
band == "hot" and eligible == "yes". This module writes that file from rank_dfw_leads() and nothing else.

Usage (from the repo root):
    python src/ranking/write_ranked_leads.py CALL_LOG FORM_LOG [--month YYYY-MM] [--leads CSV]
"""

import argparse
import csv
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

if __name__ == "__main__":  # run as a script: make the src/ packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ranking.hot_lead_score import rank_dfw_leads  # noqa: E402
from signals.contact_signals import DALLAS  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
LOGS_DIR = DATA_DIR / "logs"
LEADS_CSV = DATA_DIR / "leads" / "tdlr_hvac_dfw.csv"
# The row keys of rank_dfw_leads(), in order. The reader needs licence_number, score, band and eligible.
RANKED_COLUMNS = ["licence_number", "business_name", "county", "entity_flag", "score", "band", "eligible",
                  "manual_entity_check"]


def ranked_leads_path(year_month: str, logs_dir=LOGS_DIR) -> Path:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", year_month):
        raise ValueError(f"year_month must be YYYY-MM, got {year_month!r}")
    return Path(logs_dir) / f"{year_month}_ranked_leads.csv"


def write_ranked_leads(rows: list[dict], year_month: str, logs_dir=LOGS_DIR) -> Path:
    """Write rows to <logs_dir>/<year_month>_ranked_leads.csv and return the path.

    The file is derived, so a re-run replaces it (a later run may see more forms past their 72 h window). The new file
    is written beside the old one and swapped in, so the reader never sees half a file.
    """
    path = ranked_leads_path(year_month, logs_dir)
    for row in rows:
        if set(row) != set(RANKED_COLUMNS):
            raise ValueError(f"ranked row {row.get('licence_number')!r} has columns {sorted(row)}, "
                             f"expected {RANKED_COLUMNS}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RANKED_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        os.chmod(tmp, 0o644)  # mkstemp makes 0o600; the reader may run as another account or a sync tool
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def rank_and_write(leads_csv, call_log, form_log, year_month: str | None = None, ranked_at: datetime | None = None,
                   logs_dir=LOGS_DIR) -> Path:
    ranked_at = ranked_at or datetime.now(DALLAS)
    if ranked_at.tzinfo is None:
        ranked_at = ranked_at.replace(tzinfo=DALLAS)
    year_month = year_month or ranked_at.astimezone(DALLAS).strftime("%Y-%m")
    ranked_leads_path(year_month, logs_dir)  # refuse a bad month before ranking
    rows = rank_dfw_leads(leads_csv, call_log, form_log, year_month, ranked_at=ranked_at)
    return write_ranked_leads(rows, year_month, logs_dir)


def _month_arg(value: str) -> str:
    try:
        ranked_leads_path(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None
    return value


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Write data/logs/<YYYY-MM>_ranked_leads.csv")
    parser.add_argument("call_log")
    parser.add_argument("form_log")
    parser.add_argument("--month", type=_month_arg, help="YYYY-MM to rank; default: this month in Dallas time")
    parser.add_argument("--leads", default=str(LEADS_CSV))
    parser.add_argument("--logs-dir", default=str(LOGS_DIR))
    args = parser.parse_args(argv)
    path = rank_and_write(args.leads, args.call_log, args.form_log, args.month, logs_dir=args.logs_dir)
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    hot_eligible = sum(r["band"] == "hot" and r["eligible"] == "yes" for r in rows)
    print({"output": str(path), "rows": len(rows), "hot_and_eligible": hot_eligible})


if __name__ == "__main__":
    main()
