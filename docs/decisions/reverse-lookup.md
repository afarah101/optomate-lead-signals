# Reverse lookup: from HVAC websites to TDLR licences (written 2026-10-28, before the code)

Name search from the TDLR list has hit its limit (`open-places.md`, "Foursquare OS Places test"). The reverse lookup
starts from the other end: take every HVAC contractor website in the Foursquare cache, read the TDLR licence number
off the site, and join it to the DFW leads. The code is `src/leads/reverse_lookup.py`.

## Source

- `data/raw/fsq/places_os_tx_dfw_categories_2026-10-28.parquet`: open Texas places in the DFW box, with
  Foursquare categories (see `data/raw/fsq/SUBSET.md`). The catalog is not queried again.
- **Category:** only `63be6904847c3692a84b9b56`, "Business and Professional Services > Home Improvement Service >
  Heating, Ventilating and Air Conditioning Contractor". 1,903 listings, 1,403 with a website. "Refrigeration and Ice
  Supplier" (41 listings) is excluded: a supplier, not a contractor.
- **Leads:** `data/leads/tdlr_hvac_dfw.csv` (4,619 DFW leads), read for `licence_number`, `business_name`, `county`
  and `entity_flag` only. The licence holder column is never read.
- **Statewide numbers:** `data/raw/tdlr_ac_contractors_2026-10-27.csv`, used only to tell a TDLR number outside DFW
  (`licence_not_in_leads`) from a number TDLR doesn't have (`licence_unknown`).

## One crawl per domain

A domain is the website's host, lower case, `www.` dropped. The 1,403 listings have 1,185 domains. Each domain is
crawled once, from the first of its listing websites in sorted order. A domain is **skipped** (never fetched) when:

| Skip | Rule | Why |
|---|---|---|
| Manufacturer | The host is, or is a subdomain of, a domain in the list below | Not a contractor; crawling wastes requests |
| Platform | The host is, or is a subdomain of, `homeadvisor.com` or `servicemagic.com` | A lead marketplace, not the business's own site |
| Dealer network | 2+ listings share the domain and their names have **no main word in common** | One site for many unrelated businesses (e.g. a brand's dealer locator) |

Multi-location businesses (2+ listings whose names share a main word, e.g. `accurateairtx.com`) are kept and crawled
once. Rules are checked in the order above; a domain is counted under the first that fits.

**Manufacturer skip list.** From Ahmed (2026-10-28): `carrier.com`, `trane.com`, `lennox.com`, `rheem.com`,
`goodmanmfg.com`, `daikin.com`, `mitsubishicomfort.com`. Added from the cache, because they appear there as
manufacturer or manufacturer-supply domains: `americanstandardair.com`, `bryant.com`, `ruudac.com`,
`maytaghvac.com`, `frigidaire.net`, `lennoxpros.com`, `tranesupply.com`.
Not skipped: dealer subdomains on brand platforms whose host names a contractor (e.g. `<dealer>.rheemteam.net`,
`<dealer>.ruudpropartner.com`); they are the dealer's own page and may show its licence.

## Crawl

The existing own-site reader (`read_own_site_contacts`), unchanged rules: robots.txt, at most 2 pages (home + one
contact page), 1 request per second across all sites, 10 s timeout, no retries, honest User-Agent, no emails, phone
only from `tel:` or schema.org. The reader now also returns every licence number it read
(`licence_numbers_shown`): after each `TACL[\s-]?[AB]` prefix, **the first** run of digits, if it starts within 20
characters, leading zeros dropped (first-number rule from 2026-10-28, see `lookup-automation.md`). This is the same rule the lookup already uses; `site_shows_licence_number` is now built on it.

## Join (the name check is required)

| Case | Outcome | Label |
|---|---|---|
| One DFW lead's licence is on the site **and** the site name has every main word of that lead's TDLR name (`shares_main_words`) | `confirmed` (site phone found) or `no_tel_phone` | verified |
| One DFW lead's licence is on the site, but the site name fails the name check | `licence_name_mismatch` | unresolved |
| Licences of 2+ DFW leads with different names (main words) are on the site | `many_licences`, one row per lead | unresolved |
| The same lead's licence is on 2+ domains | `licence_on_many_sites`, one row | unresolved |
| Only numbers TDLR has outside DFW | `licence_not_in_leads`, domain log only | no business row |
| Only numbers TDLR doesn't have | `licence_unknown`, domain log only | no business row |
| No `TACLA`/`TACLB` number on the site | `licence_not_shown`, domain log only | no business row |
| The site can't be read | `robots_blocked` / `fetch_failed` / `redirect_off_site`, domain log only | no business row |

- **The own site's name is the only name judged.** The Foursquare listing name is never used to verify.
- This is stricter than the lookup (licence **or** name): the reverse lookup needs licence **and** name.
- If 2+ DFW leads with the same main words are on one site, each is judged on its own.

## Output

- `data/leads/2026-11_reverse_lookup_sample_v1.csv`: one row per TDLR business found. `match_by` is always
  `licence`; `name_also_matches` = `yes`/`no`; `outreach_eligible` = `yes` only if the row is verified **and**
  `entity_flag` is `likely_corporate`. `phone_source` = `site`, else `Foursquare` (the listing's `tel`, for a
  verified row with no phone on its site; not checked on the site). No holder names, no site names.
- `data/leads/2026-11_reverse_lookup_sample_domains_v1.csv`: one row per sampled domain: domain, listings, outcome,
  licence numbers read, DFW leads matched. No names.
- Neither file is ever overwritten.

## Test: the sample first, then stop

200 of the crawlable domains, drawn with `random.Random(20261028).sample()` over the sorted domain list.
**PASS:** at least 16 verified businesses (8 per 100 domains, against 7.5 per 100 from name search). The run stops
after the sample. No full run without Ahmed's approval.

## Sample result (2026-10-28): PASS, 17 verified from 200 domains

1,403 listings, 1,185 domains; 26 skipped (manufacturer 11, dealer network 13, platform 2); 1,159 crawlable; 200 drawn.

| Domains (200) | Count |
|---|---|
| `licence_not_shown` | 80 |
| `fetch_failed` / `robots_blocked` / `redirect_off_site` | 60 / 17 / 9 |
| `confirmed` / `no_tel_phone` | 10 / 6 |
| `licence_name_mismatch` | 11 |
| `licence_not_in_leads` | 5 |
| `many_licences` | 2 |

32 businesses found: **17 verified** (11 `confirmed`, 6 `no_tel_phone`), 15 unresolved (11 `licence_name_mismatch`,
4 `many_licences`), 0 `licence_on_many_sites`. Phones: 11 from the site, 6 from Foursquare. **6** are
outreach-eligible (verified and `likely_corporate`). 1 of the 32 is among the 80 queued businesses (unresolved).

Seen in the data: years and area codes within 20 characters of the prefix are read as numbers (`2026`, `2022`,
`972`). In this sample it changed no verified result, but on one site `2022` is also a DFW lead's licence and made
the domain `many_licences`. No full run until Ahmed approves.

## Re-run v2 with the first-number rule (2026-10-28): the same 200 domains

Same seed, same 200 domains (checked against the v1 domain log before crawling). Outputs:
`2026-11_reverse_lookup_sample_v2.csv` and `2026-11_reverse_lookup_sample_domains_v2.csv`; v1 is kept.

| | v1 | v2 |
|---|---|---|
| Verified (outreach-eligible) | 17 (6) | **17 (6)**, the same 17 businesses |
| Unresolved | 15 | 14: the `2022` row is gone (a year read as a licence), and `30880` moves from `many_licences` to `licence_name_mismatch` |
| Domains with 2+ numbers read | 13 | 1 (two prefixes on one site) |
| Domain outcomes changed | | 3: the `2022` site; one site from `licence_not_in_leads` to `licence_unknown` (a dropped second number had been a TDLR number outside DFW); one site from `robots_blocked` to a homepage 403 (the live site changed) |

**Why sites fail to load (v2, 61 `fetch_failed`; the 60 from v1 are all among them).** Cause read from the original
exception, without changing the fetch code:

| Cause | Sites |
|---|---|
| DNS: the host doesn't resolve (47 of 48 don't resolve with or without `www.` either) | 48 |
| TLS: certificate for another host name (2), self-signed (1), access denied (1) | 4 |
| 403 (homepage) | 2 |
| Timeout | 1 |
| Other: homepage 404 (3), homepage 409 (2), too many redirects (1) | 6 |

Most failures are dead domains in the Foursquare listings, so fetch changes can recover at most about 13 of 200.
