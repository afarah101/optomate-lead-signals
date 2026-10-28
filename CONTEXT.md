# CONTEXT: the project's language

A glossary for optomate-lead-signals: each term with its code name, meaning and where it lives. When a term in chat,
docs or prompts doesn't match the code, one of them is wrong. Terms marked **agreed, not in code** or **decided, not
in code** come from the decisions of 28 Oct 2026 and have no code yet (see `docs/audit/grill-audit-2026-10-28.md`).

## Segment and leads

| Term | Code name | Meaning | Lives in |
|---|---|---|---|
| Home-service trades | none (**decided, not in code**) | US plumbing and HVAC businesses treated as one group. **The first test is HVAC only (TDLR).** Plumbing (TSBPE) is added only after the HVAC test passes | `src/leads/tdlr_source.py:10-12`, `docs/decisions/data-sources.md:63-76` |
| Lead | a row of `LEAD_COLUMNS` | One active TDLR A/C Contractor licence in the 9 DFW counties, de-duplicated | `src/leads/dfw_filter.py:9`, `data/leads/tdlr_hvac_dfw.csv` |
| DFW | `DFW_COUNTIES` | Collin, Dallas, Denton, Ellis, Johnson, Kaufman, Parker, Rockwall, Tarrant | `src/leads/dfw_filter.py:5-7` |
| Licence holder | `licence_holder` (TDLR `owner_name`) | The licensed person. **Personal data**: never used in matching, never stored outside `data/` | `src/leads/dfw_filter.py:48` |
| Entity flag | `entity_flag` = `likely_corporate` / `unconfirmed` | A name-only hint about the entity type. **Accepted: LLC, Inc, Corp, LLP, LP, LTD** (`likely_corporate`, also matching L.L.C., INCORPORATED and CORPORATION). **Sole traders are excluded**: names with none of these suffixes are `unconfirmed` and never drawn for the call list. A hint, not proof | `src/leads/entity_type.py:6-14`, `src/signals/call_list.py:41` |

## Hot leads

| Term | Code name | Meaning | Lives in |
|---|---|---|---|
| **Hot lead** | `band == "hot"` | A business whose own-signal score is **2 or more** (out of 3). One point each for a missed call, no voicemail greeting, and no form reply or a reply after 24 h. Google reviews are **a hint only and are never stored** | `src/ranking/hot_lead_score.py:18-28`, `docs/decisions/signal-rules.md:9,69-79` |
| Middle / cold | `band` | 1 point = `middle` (left out of calibration); 0 points = `cold` | `src/ranking/hot_lead_score.py:28` |
| Eligible | `eligible` | Not do-not-contact, `likely_corporate`, a valid call this month, and a form sent this month at least 72 h before ranking | `src/ranking/hot_lead_score.py:65-70` |
| Do-not-contact | `do_not_contact_list()` | Businesses that asked to stop | `src/signals/contact_signals.py:171` |
| Call list | `draw_month_call_list()` | The month's 100 randomly drawn `likely_corporate` leads, balanced across time bands | `src/signals/call_list.py:33` |

## Contact discovery

| Term | Code name | Meaning | Lives in |
|---|---|---|---|
| Lookup | `2026-11_lookup*.csv` | Finding a business's website, phone and form for the call list | `src/signals/lookup_sheet.py`, `src/leads/lookup_autofill.py` |
| Own-site reader | `read_own_site_contacts()` | Reads at most 2 pages of the business's own site: robots.txt obeyed, 1 request per second, phone only from `tel:`/schema.org, never emails | `src/leads/website_contacts.py:220` |
| Identity judge | `match_by` = `licence` / `name` | A site is the business only if it shows the TDLR licence number with a **`TACLA` or `TACLB` prefix only** (a hyphen or space before the letter is allowed: `TACL[\s-]?[AB]`), or its site name has every main word of the licence name | `src/leads/website_contacts.py:203-213`, `src/leads/place_match.py:58` |
| Main words | `main_words()` | Name words in capitals, dots removed, & = AND, entity words dropped, singular = plural | `src/leads/place_match.py:45-55` |
| Auto-filled row | a row in `2026-11_lookup_auto_v*.csv` | A business whose site was confirmed and had a phone; `lookup_initials = auto` | `src/leads/lookup_autofill.py:99-105` |
| Manual queue (hand-check queue) | `2026-11_manual_queue_v*.csv` | Every other business, with one `reason` and its `identity_label`, to be looked up by hand | `src/leads/lookup_autofill.py:48-53` |
| `place_id` | `place_id` | Google's place identifier: the only Google data stored | `src/leads/lookup_autofill.py:19-20` |
| Open places fallback | `measure_open_places_recovery()` | Overture Places records matched by name + Texas DFW ZIP, then judged on the own site | `src/leads/open_places.py:105` |
| **Verified row** | `identity_label = "verified"` (`VERIFIED`) | The business's own website confirms its identity: it shows the TDLR licence number as `TACLA`/`TACLB` + digits, or passes the strict name match (every main word). This includes `no_tel_phone`: identity is confirmed, but no phone was found. **Only verified rows go to outreach**: the gate is `may_go_to_outreach()` | `src/leads/identity_label.py`, decided in chat 28 Oct 2026 |
| **Unverified row** | `identity_label = "unverified"` (`UNVERIFIED`) | A match from open data only (name + ZIP, never confirmed on the own site), or a business whose own site is blocked by robots.txt (`robots_blocked`). Never goes to outreach | `src/leads/identity_label.py`, decided in chat 28 Oct 2026 |
| **Unresolved row** | `identity_label = "unresolved"` (`UNRESOLVED`) | A person must check, because identity is unsettled. Either the own site was tried but couldn't settle it (`name_mismatch`, `fetch_failed`, `redirect_off_site`), or no candidate exists to check (`no_place_none`, `no_place_zip`, `no_place_texas`, `no_website`, `no_match`, `places_budget`). Goes to the **hand-check queue** (the manual queue), **never outreach** | `src/leads/identity_label.py`, decided in chat 28 Oct 2026 |
| **Phone source** | none (**decided, not in code**) | Recorded on every row, one of: `site` (a `tel:` link or schema.org `telephone` on the business's own site), `Google`, `Overture`, `Foursquare` | decided in chat, 28 Oct 2026 |

## Failure reasons (queue `reason` / `outcome`)

| Plain name | Code name | Meaning | Raised at |
|---|---|---|---|
| Wrong business | `name_mismatch` | A site was read, but it shows neither the licence number nor the full name | `src/leads/lookup_autofill.py:85` |
| No result | `no_place_none` | Google Text Search returned nothing | `src/leads/place_match.py:101` |
| No result (address) | `no_place_zip` / `no_place_texas` | Results came back, but none had a Texas address with a ZIP / any Texas address | `src/leads/place_match.py:105` |
| No result (open data) | `no_match` | No Overture record passed name + DFW ZIP | `src/leads/open_places.py:78` |
| No website | `no_website` | The place or record has no website | `src/leads/lookup_autofill.py:75` |
| robots.txt | `robots_blocked` | robots.txt disallows the page, or answers 401/403/5xx | `src/leads/website_contacts.py:91-92,228` |
| No tel: link | `no_tel_phone` | The site is confirmed as the business but has no `tel:`/schema.org phone | `src/leads/lookup_autofill.py:88` |
| Fetch failed | `fetch_failed` | Timeout, network error, non-HTML or non-200 homepage, or too many redirects | `src/leads/website_contacts.py:83-84,224,231` |
| Off-site redirect | `redirect_off_site` | The site redirects to a different domain; reading stops | `src/leads/website_contacts.py:80` |
| Budget held back | `places_budget` | A candidate was skipped to keep Places calls for businesses not yet searched | `src/leads/lookup_autofill.py:70` |
| Retired | `no_place`, `no_place_name` | Old reasons from v1/v2, no longer emitted | `docs/decisions/lookup-automation.md:114,154` |

## Open items

| Item | Owner | Note |
|---|---|---|
| Foursquare OS Places sign-up (Places Portal account and access token) | Ahmed | Needed before Foursquare can be a phone source or fallback (`docs/decisions/open-places.md:12`) |
| ZIP-to-county check via the HUD USPS ZIP-County crosswalk | Not assigned | Would let an open-data ZIP be checked against the TDLR county, since TDLR has no ZIPs (`docs/decisions/open-places.md:44-46`) |
