"""Application layer: build every available DFW lead list and write the CSVs to data/leads/."""

import csv
from datetime import date

from leads import tdlr_source
from leads.dfw_filter import LEAD_COLUMNS, filter_active_dfw_contractors, is_in_dfw, remove_duplicate_licences, to_lead
from leads.entity_type import flag_likely_corporate_entity

# TSBPE plumbers are skipped: the official file is behind bot protection (see docs/decisions/data-sources.md).
SOURCES = [("tdlr_hvac_dfw.csv", tdlr_source)]


def build_dfw_lead_lists(retrieved_on: date | None = None) -> dict:
    retrieved_on = retrieved_on or date.today()
    report = {}
    for file_name, source in SOURCES:
        licences = source.read_licences(source.download_ac_contractor_licences(retrieved_on))
        active_dfw = filter_active_dfw_contractors(licences, retrieved_on)
        unique = remove_duplicate_licences(active_dfw)
        leads = [to_lead(l, source.DATASET_URL, retrieved_on) for l in unique]
        for lead in leads:
            lead["entity_flag"] = flag_likely_corporate_entity(lead["business_name"])

        out_path = source.DATA_DIR / "leads" / file_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LEAD_COLUMNS + ["entity_flag"])
            writer.writeheader()
            writer.writerows(leads)

        flagged = sum(lead["entity_flag"] == "likely_corporate" for lead in leads)
        report[file_name] = {
            "downloaded": len(licences),
            "in_dfw": sum(is_in_dfw(l) for l in licences),
            "active_dfw": len(active_dfw),
            "unique": len(unique),
            "likely_corporate": flagged,
            "unconfirmed": len(leads) - flagged,
        }
    return report


if __name__ == "__main__":
    print(build_dfw_lead_lists())
