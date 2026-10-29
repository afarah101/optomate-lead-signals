"""Full reverse lookup over every crawlable domain, recording why each unreadable site failed.

Rules: docs/decisions/reverse-lookup.md. The fetch code is unchanged: the cause is read from the original exception,
which `raise ... from None` keeps as `__context__`. Outputs are never overwritten. The errors file holds the domain,
outcome and cause only, never names.
"""

import json
import socket
import ssl
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leads import reverse_lookup as rl  # noqa: E402
from leads.website_contacts import SiteUnreadable, http_get, read_own_site_contacts  # noqa: E402

LEADS_DIR = rl.DATA_DIR / "leads"
OUT = LEADS_DIR / "2026-11_reverse_lookup_full_v1.csv"
DOMAINS_LOG = LEADS_DIR / "2026-11_reverse_lookup_full_domains_v1.csv"
ERRORS = LEADS_DIR / "2026-11_reverse_lookup_full_errors_v1.jsonl"


def cause_type(error: SiteUnreadable) -> str:
    """dns / tls / 403 / timeout / other for fetch_failed; the outcome itself for robots_blocked and redirect_off_site."""
    if error.reason != "fetch_failed":
        return error.reason
    inner = getattr(error.__context__, "reason", error.__context__)  # URLError wraps the socket or TLS error
    if isinstance(inner, socket.gaierror):
        return "dns"
    if isinstance(inner, ssl.SSLError):
        return "tls"
    if isinstance(inner, TimeoutError):
        return "timeout"
    return "403" if str(error).endswith("HTTP 403") else "other"


def run(out_csv, domains_csv, errors_jsonl, listings, leads, statewide, get=http_get) -> dict:
    for path in map(Path, (out_csv, domains_csv, errors_jsonl)):
        if path.exists():
            raise FileExistsError(f"{path} already exists; it is never overwritten")
    kept, _ = rl.crawlable_domains(listings)
    causes = Counter()
    with Path(errors_jsonl).open("x", encoding="utf-8") as errors:

        def read_site(url):
            requested = []

            def counted_get(u):
                requested.append(u)
                return get(u)

            try:
                return read_own_site_contacts(url, get=counted_get)
            except SiteUnreadable as e:
                ctx, kind = e.__context__, cause_type(e)
                causes[kind] += e.reason == "fetch_failed"
                errors.write(json.dumps({
                    "domain": rl.domain_of(url), "outcome": e.reason, "cause_type": kind, "message": str(e),
                    "stage": "robots" if requested and requested[-1].endswith("/robots.txt") else "page",
                    "requests": len(requested), "error": type(ctx).__name__ if ctx else "",
                    "cause": repr(getattr(ctx, "reason", ctx))[:300] if ctx else ""}) + "\n")
                errors.flush()
                raise

        summary = rl.run_reverse_lookup_sample(out_csv, domains_csv, listings, leads, statewide,
                                               read_site=read_site, size=len(kept))
    return summary | {"fetch_failed_by_cause": dict(+causes), "errors": str(errors_jsonl)}


if __name__ == "__main__":
    print(json.dumps(run(OUT, DOMAINS_LOG, ERRORS, rl.fetch_hvac_listings(), rl.load_leads(),
                         rl.load_statewide_numbers()), indent=1))
