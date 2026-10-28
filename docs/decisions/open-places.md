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
