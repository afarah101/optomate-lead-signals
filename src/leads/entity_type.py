"""Leads domain: a name-only hint that a licence holder trades as a registered entity."""

import re

# Whole word = not touching a letter or digit, so "INCREDIBLE" and "HELP" don't match.
_CORPORATE_SUFFIX = re.compile(
    r"(?<![A-Z0-9])(?:L\.L\.C\.?|LLC|LLP|INCORPORATED|INC|CORPORATION|CORP|LTD)(?![A-Z0-9])",
    re.IGNORECASE,
)


def flag_likely_corporate_entity(business_name: str | None) -> str:
    # A hint only: confirm in the Texas Comptroller Taxable Entity Search before any email.
    return "likely_corporate" if _CORPORATE_SUFFIX.search(business_name or "") else "unconfirmed"
