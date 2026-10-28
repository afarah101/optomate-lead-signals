# Open places data for the queued businesses (written 2026-10-28, before the code)

A measurement, not a lookup step: how many of the 80 businesses in `data/logs/2026-11_manual_queue_v3.csv` an open
places dataset can recover, with identity confirmed only on the business's own website. The code is
`src/leads/open_places.py`; the output is `data/logs/2026-11_open_places_test.csv`.

## Sources

| Source | Used | How it is reached |
|---|---|---|
| **Overture Maps Places**, release `2026-10-21.0` (latest in `stac.overturemaps.org/catalog.json` on 2026-10-28) | Yes | The official GeoParquet release on `s3://overturemaps-us-west-2/release/2026-10-21.0/theme=places/type=place/`, read anonymously with DuckDB. Only rows inside the DFW box are read (ranged reads); the global files are not downloaded |
| **Foursquare OS Places** | **No, skipped** | Foursquare's access page says it is "now delivered through the Foursquare Places Portal, using an Iceberg-based data catalog", which replaces "the legacy public S3 bucket". Step 1 is "Create an account on the Places Portal", step 3 "Generate an access token". The Hugging Face copy is gated behind a login and accepting conditions. A sign-up is needed, so it is skipped (brief rule) |

Overture Places already includes some Foursquare data, transformed to the Overture schema. It is used here only as
part of Overture, under the terms below, and is not a test of Foursquare OS Places itself.

## Licences and attribution (quoted from the primary pages)

From `https://docs.overturemaps.org/attribution` (checked 2026-10-28). Places has no single licence; each source
has its own:

- Meta, Microsoft, BrightQuery, PinMeTo, Krick, RenderSEO, DAC, Birdeye, Uberall, OpenTravel Alliance: "Data from
  [source]. Available under CDLA Permissive 2.0."
- Foursquare: "Copyright 2024 Foursquare Labs, Inc. All rights reserved.", "Foursquare data was transformed to the
  Overture schema", available under Apache 2.0 with a NOTICE.txt file.
- AllThePlaces: "Data from AllThePlaces. Available under CC0 1.0."

Foursquare's own access page states: "Licensed under the Apache License, Version 2.0".

**What this means here.** The data is used internally, and nothing is shared. If any output built from it is ever
shared, it carries the attribution line of every source dataset listed in that row's `source_datasets` column, plus
the Apache 2.0 NOTICE for Foursquare rows.

## Area

The 9 DFW counties (Collin, Dallas, Denton, Ellis, Johnson, Kaufman, Parker, Rockwall, Tarrant) fit inside the box
longitude −98.1 to −96.0, latitude 32.0 to 33.5. The box is wider than the counties, so it is only a pre-filter.

## Match rule

1. **Normalised business name.** These are the existing `place_match` main words: capitals, dots removed, `&` read as
   AND, entity words dropped, singular = plural. A record matches when its `names.primary` contains **every** main
   word of the licence `business_name`. This is the same strict test the own-site name check uses.
2. **ZIP.** **Change from the brief, made before the code:** TDLR gives no ZIP for any business. All 20,462 rows of
   the 2026-10-27 extract have empty business and mailing address fields. So the licence's ZIP can't be compared.
   Instead, a record must have an address with region `TX` (or `Texas`) and a DFW ZIP, meaning a postcode starting `75`
   or `76`, with an optional ZIP+4. Records without a ZIP are not matched.
   *Superseded 2026-10-28 by the ZIP-to-county rule below (rule changes).*
3. **Identity is confirmed only on the business's own site.** A matched record is only a candidate. Its website goes
   to the existing reader (`website_contacts.read_own_site_contacts`, unchanged), and the site is confirmed only by:
   - the existing licence check: the TACL licence number is shown on the site; or
   - the existing site-name check: the site name contains every main word of the licence name.

   Record name, address and phone are never evidence of identity.
4. **Candidates per business.** Matched records with a website are tried in order of Overture `confidence`, highest
   first, at most **5 distinct websites** per business. Trying stops at the first confirmed site. A confirmed site
   with no `tel:`/schema.org phone (`no_tel_phone`) also stops trying, because that site is the business.
5. **The licence holder name is never used.** The input is the v3 queue, which has no holder column. The holder
   name isn't read, matched, stored or printed.

Reader rules unchanged: robots.txt, at most 2 pages per site, 1 request per second, 10-second timeout, no retries,
honest User-Agent, no emails, phones only from `tel:` links or schema.org markup.

## What is stored

`data/logs/2026-11_open_places_test.csv`, one row per queued business (80), never overwritten:

| Column | Value |
|---|---|
| `licence_number`, `business_name`, `county` | From the v3 queue |
| `outcome` | `confirmed`, or the reason nothing was confirmed: `no_match` (no record passed name + ZIP), `no_website` (matches, none with a website), or the reader's reason for the first site tried (`name_mismatch`, `robots_blocked`, `fetch_failed`, `redirect_off_site`), or `no_tel_phone` (site confirmed, no phone) |
| `match_by` | `licence` or `name`, for a confirmed site |
| `identity_label` | `verified` (`confirmed`, `no_tel_phone`), `unverified` (`robots_blocked`) or `unresolved` (every other outcome), per `src/leads/identity_label.py` and the rule logged 2026-10-28 in `lookup-automation.md`. Only `verified` rows go to outreach |
| `matched_records`, `records_with_website` | Counts for the measurement |
| `source_record_id` | The Overture `id` of the record whose website was confirmed |
| `source_datasets` | That record's upstream datasets (for attribution) |
| `website_url`, `business_phone`, `phone_source_url`, `form_url` | From the business's own site, only for a confirmed site |
| `lookup_date` | Run date |

Nothing else from Overture is stored: no names, addresses, Overture phones, emails or socials. The `emails` column is
never even selected. The v1–v4 lookup and queue files are inputs or untouched; this run writes only its own file.

## Dependency

`duckdb==1.5.6` (MIT), vetted in `/tmp/sandbox` on 2026-10-28:
- pip-audit, osv-scanner and gitleaks found nothing;
- the three GitHub advisories for `duckdb/duckdb` were all fixed by 1.4.2 or earlier.

2.0.0 (released 2026-10-21) was passed over as a one-week-old major release.

Reading S3 needs DuckDB's `httpfs` extension. DuckDB downloads the signed extension once from its own extension
repository into `~/.duckdb/extensions/`, and unsigned extensions stay disabled (`allow_unsigned_extensions=false`).
To remove it: delete `~/.duckdb/`.

## Rule changes

### 2026-10-28: Identity label column (before the code)

`identity_label` is added to the output, with the same rule as the lookup (`lookup-automation.md`, 2026-10-28):
`confirmed` and `no_tel_phone` are `verified`; `robots_blocked` is `unverified`; `no_match`, `no_website`,
`name_mismatch`, `fetch_failed` and `redirect_off_site` are `unresolved`. The existing
`2026-11_open_places_test.csv` isn't relabelled.

### 2026-10-28: ZIP-to-county with the Census ZCTA-to-County file (before the code)

| | Old rule | New rule |
|---|---|---|
| Address | Region `TX`/`Texas` and a postcode starting `75` or `76` (anywhere in DFW) | The record's postcode, trimmed to 5 digits (ZIP+4 allowed), must lie in **the business's own TDLR county** |
| Test | Pattern only | A row in the Census file links that 5-digit ZCTA to the county's FIPS code with `AREALAND_PART > 0` |

**Source.** U.S. Census Bureau, 2020 ZCTA to County Relationship File:
`https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt`, retrieved
2026-10-28. It's public, with no account needed. It's saved as `data/raw/zcta_county_2020.txt` (Git-ignored).

**The file as read** (2026-10-28):
- Pipe-delimited, with a UTF-8 byte-order mark and 47,863 data rows.
- Columns used, exactly as in its header: `GEOID_ZCTA5_20` (5-digit ZCTA), `GEOID_COUNTY_20` (5-digit county FIPS)
  and `AREALAND_PART` (land area of the ZCTA–county overlap, square metres).
- 903 rows have an empty `GEOID_ZCTA5_20` (county area outside any ZCTA). These are skipped.
- 7 linked rows have `AREALAND_PART = 0` (a water-only overlap). These don't link.
- There is no business-share ratio, so any land overlap counts.

**County FIPS**, confirmed against the file's own `NAMELSAD_COUNTY_20`: Collin 48085, Dallas 48113, Denton 48121,
Ellis 48139, Johnson 48251, Kaufman 48257, Parker 48367, Rockwall 48397, Tarrant 48439.

**Limits.**
- A ZCTA is the Census's area version of a ZIP, not the USPS ZIP itself. PO-box-only and some business ZIPs have no
  ZCTA, so a record with one of those ZIPs doesn't match.
- A ZIP that crosses a county line matches each county it touches. The own-site check still decides identity.
- The region (`TX`) test is dropped, because a ZCTA linked to a Texas county FIPS (`48…`) is in Texas.

**Result of the strict county rule (2026-10-28).** It was re-run to `data/leads/2026-11_open_places_test_v2.csv`, with
the same 80 businesses and the same Overture release:
- verified fell from **6 to 4** (licence 4 → 3, name 2 → 1), and phones from 3 to 1;
- `no_match` rose from 59 to 65;
- no business gained a confirmation.

Two businesses that their own sites had already confirmed were lost:

| Licence | TDLR county | County of the Overture ZIP (Census file) | Confirmed before by |
|---|---|---|---|
| 168761 | Collin | Tarrant | site name |
| 116548 | Rockwall | Hunt (48231), outside the 9 DFW counties | TACL licence number |

The TDLR `business_county` doesn't always match where the business trades. The own-site check was already rejecting
the wrong businesses; the county rule rejected right ones.

### 2026-10-28: ZIP in any Texas county; county match recorded, not filtered (before the code)

| | Old rule | New rule |
|---|---|---|
| Candidate filter | The record's ZIP is in the business's TDLR county | The record's ZIP (5 digits, ZIP+4 trimmed) is in **any Texas county**: the Census file links its ZCTA to a county FIPS starting `48`, with `AREALAND_PART > 0` |
| County match | Was the filter | **Recorded only**, as the new column `zip_county_match` = `yes` / `no`: is the confirmed record's ZIP in the TDLR county? Empty when no site was confirmed. Never filters |
| Identity | Own site only (licence number or strict site name) | **Unchanged.** The own site is the only judge |

The DFW bounding box is still a pre-filter on the Overture read, so "any Texas county" in practice means Texas ZIPs
inside the box.
