"""Leads domain: which TDLR A/C contractor licences count as Dallas–Fort Worth leads."""

from datetime import date, datetime

DFW_COUNTIES = frozenset(
    {"DALLAS", "TARRANT", "COLLIN", "DENTON", "ROCKWALL", "KAUFMAN", "ELLIS", "JOHNSON", "PARKER"}
)

LEAD_COLUMNS = [
    # No licence_holder: the holder name is personal data and is never kept (data-sources.md, 2026-10-29).
    "business_name", "licence_number", "licence_type", "licence_status",
    "expiry_date", "address", "city", "county", "source", "retrieved_on",
]


def is_in_dfw(licence: dict) -> bool:
    return (licence.get("business_county") or "").strip().upper() in DFW_COUNTIES


def is_active_on(licence: dict, on: date) -> bool:
    # The dataset has no status field; an unexpired licence is the only "active" signal.
    try:
        expiry = datetime.strptime(licence.get("license_expiration_date_mmddccyy") or "", "%m/%d/%Y").date()
    except ValueError:
        return False
    return expiry >= on


def remove_duplicate_licences(licences: list[dict]) -> list[dict]:
    seen, unique = set(), []
    for licence in licences:
        number = (licence.get("license_number") or "").strip()
        if number not in seen:
            seen.add(number)
            unique.append(licence)
    return unique


def filter_active_dfw_contractors(licences: list[dict], on: date) -> list[dict]:
    return [l for l in licences if is_in_dfw(l) and is_active_on(l, on)]


def to_lead(licence: dict, source: str, retrieved_on: date) -> dict:
    address = " ".join(
        part.strip() for part in (licence.get("business_address_line1"), licence.get("business_address_line2")) if part and part.strip()
    )
    return {
        "business_name": licence.get("business_name", ""),
        "licence_number": licence.get("license_number", ""),
        "licence_type": licence.get("license_type", ""),
        "licence_status": "",  # not in the dataset; see docs/decisions/data-sources.md
        "expiry_date": licence.get("license_expiration_date_mmddccyy", ""),
        "address": address,
        # shortcut: city left empty because business_city_state_zip is blank for every A/C contractor; parse it if TDLR starts filling it
        "city": "",
        "county": (licence.get("business_county") or "").strip().title(),
        "source": source,
        "retrieved_on": retrieved_on.isoformat(),
    }
