"""Leads domain: whether a row's identity is verified on the business's own site, and so whether it may go to outreach.

Rules: CONTEXT.md (Verified / Unverified / Unresolved row) and docs/decisions/lookup-automation.md (2026-10-28).
"""

VERIFIED, UNVERIFIED, UNRESOLVED = "verified", "unverified", "unresolved"

_LABEL_BY_OUTCOME = {
    "confirmed": VERIFIED,  # site confirmed and a phone found (an auto-filled row)
    "no_tel_phone": VERIFIED,  # site confirmed, no phone
    "robots_blocked": UNVERIFIED,
    **dict.fromkeys(["name_mismatch", "fetch_failed", "redirect_off_site"], UNRESOLVED),  # site tried, not settled
    **dict.fromkeys(["no_place_none", "no_place_zip", "no_place_texas", "no_website", "no_match", "places_budget"],
                    UNRESOLVED),  # no candidate to check
}


def identity_label(outcome: str) -> str:
    try:
        return _LABEL_BY_OUTCOME[outcome]
    except KeyError:
        raise ValueError(f"no identity label for outcome {outcome!r}; add it to CONTEXT.md first") from None


def may_go_to_outreach(row: dict) -> bool:
    return row.get("identity_label") == VERIFIED
