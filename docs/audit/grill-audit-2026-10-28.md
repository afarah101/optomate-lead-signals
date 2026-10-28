# Grill audit: optomate-lead-signals vs agreed decisions (2026-10-28)

The 8 decisions are the ones agreed in chat on 28 Oct 2026. Evidence is `file:line` against the working tree at audit
time, or command output. Read-only audit: no code, config or dependency was changed, and no live API was called.

**State of the tree at audit time** (`git status --short`):

```
 M docs/decisions/lookup-automation.md
 M requirements.txt
?? docs/decisions/open-places.md
?? src/leads/open_places.py
?? tests/test_open_places.py
```

These five are uncommitted work from the two previous briefs (the v4 result note and the Overture measurement). This
audit adds only `docs/audit/grill-audit-2026-10-28.md` and `CONTEXT.md`.

## Top 5 holes, ranked by risk to first revenue

1. **The agreed hot-lead definition isn't built and contradicts the logged rules.** The code scores first-party
   call/form signals (`src/ranking/hot_lead_score.py:18-28`). There is no Google review signal anywhere in `src/`
   (`grep -i review src` returns nothing). And `docs/decisions/signal-rules.md:9` says "No Google review content is
   stored anywhere".
2. **No outreach gate: rows are never labelled "verified" or "unverified".** `grep -iw verified src tests` returns 0
   matches. The closest stand-ins are the auto/queue file split (`src/leads/lookup_autofill.py:19-20`) and
   `manual_entity_check` (`src/ranking/hot_lead_score.py:79`). Nothing stops an unconfirmed row from reaching outreach.
3. **The agreed contact channel can't be filled.** Decision 3 needs "public email or contact form". The reader never
   collects emails (`src/leads/website_contacts.py:4`, `docs/decisions/lookup-automation.md:50`), so only `form_url`
   can satisfy it. Coverage is also low:
   - 20 of 100 auto-filled (`data/logs/2026-11_lookup_auto_v3.csv`: 15 by licence, 5 by name);
   - Overture confirmed 6 more sites, 3 with a phone (`data/logs/2026-11_open_places_test.csv`, outcome counts below).
4. **Half the segment is missing: no plumbing source.** TSBPE is skipped (`docs/decisions/data-sources.md:63-76`,
   `src/leads/build_lead_list.py:10-11`), so "home-service trades" is HVAC only.
5. **A Places API outage mid-run leaves partial files, with no resume.**
   - Any HTTP error other than 404, including 429, raises `PlacesUnavailable` with no backoff (`src/leads/place_match.py:79-87`).
   - The run then re-raises after writing some rows (`src/leads/lookup_autofill.py:108-112`).
   - A re-run is refused because the files already exist (`src/leads/lookup_autofill.py:33-35`).
   - No test covers a 429 or a mid-run failure. The only failure test is on the first call (`tests/test_lookup_autofill.py:424`).

## Decision table

| # | Decision | Verdict | Evidence |
|---|---|---|---|
| 1 | Goal: hot leads; closing sales out of scope | **MATCH** | Ranking produces `band` hot/middle/cold (`src/ranking/hot_lead_score.py:27-28`). The call script says "I am not selling anything" (`docs/templates/call_script.md:13`) and "Do not sell anything" (`:8`) |
| 2 | Home-service trades: TDLR HVAC + TSBPE plumbing, DFW 9 counties, LLC/Inc only | **DRIFT** | TDLR HVAC is built (`src/leads/tdlr_source.py:10-12`). The 9 counties match (`src/leads/dfw_filter.py:5-7`). TSBPE is **missing** (`docs/decisions/data-sources.md:73`). The entity flag is wider than LLC/Inc: it also takes LLP, LP, CORP, CORPORATION, LTD (`src/leads/entity_type.py:6-8`). The call list draws `likely_corporate` only (`src/signals/call_list.py:41`). "Home-service trades" isn't a term anywhere in the code |
| 3 | Hot lead: 2+ of 5 newest Google reviews mention slow/missed contact, under 90 days; open and trading; owner-run; public email or form | **DRIFT** | The code's hot lead is a score of 2 or more from a missed call, no voicemail greeting, and a slow or missing form reply (`src/ranking/hot_lead_score.py:18-28`, `docs/decisions/signal-rules.md:69-79`). There's no review, 90-day, "open and trading" or "owner-run" logic anywhere in `src/` (grep). Emails are banned (`src/leads/website_contacts.py:4`) |
| 4 | Places API (New) first; own site is the identity judge (TACLA/TACLB or strict name); 20 of 100 | **MATCH** | Text Search + Details (`src/leads/place_match.py:15-18`). Site judge: licence (`src/leads/website_contacts.py:203-213`) or strict name (`src/leads/lookup_autofill.py:82-83` with `shares_main_words`, `src/leads/place_match.py:58-60`). The result is 20 rows, 15 licence + 5 name (command output below). The licence matcher accepts any `TACL` prefix, not only TACLA/TACLB (`src/leads/website_contacts.py:209`); a minor widening |
| 5 | Fallback: Overture + Foursquare OS Places, name + ZIP; no Splink/Zingg/pyJedAI/Brave/Common Crawl | **DRIFT** | Overture is built but **uncommitted** (`src/leads/open_places.py:35-50`). Foursquare is **skipped** because it needs a Places Portal account and token (`docs/decisions/open-places.md:12`). The ZIP rule is replaced by "TX + 75/76 ZIP", because TDLR has no ZIPs (`docs/decisions/open-places.md:44-46`, `src/leads/open_places.py:21-22,53-55`). The banned tools are absent (`grep -i 'splink\|zingg\|pyjedai\|brave\|common crawl' src docs requirements.txt` returns nothing) |
| 6 | Each row labelled "verified"/"unverified"; only verified to outreach | **MISSING** | `grep -iw 'verified\|unverified' src tests` returns 0 matches. No outreach module exists (module table) |
| 7 | Review data: Google Places API, 5 newest reviews; sort-by-newest unconfirmed | **MISSING** | The field masks request no reviews: `places.id,places.displayName,places.formattedAddress` and `websiteUri` only (`src/leads/place_match.py:17-18`). This conflicts with `docs/decisions/signal-rules.md:9` |
| 8 | Secrets in .env only; never in code, logs or git history | **MATCH** | `.env` is ignored (`.gitignore:2`, `git check-ignore -v .env` gives `.gitignore:2:.env`). The key is read from `.env` (`src/leads/place_match.py:33-42`) and sent only in a header (`src/leads/place_match.py:74`). The secrets scans are clean (below) |

## Module table

| Module | Job | Status | Evidence |
|---|---|---|---|
| `leads/tdlr_source.py` | Download and read TDLR A/C Contractor licences | Working, **untested** | `:16-29`; no test imports it (grep of `tests/` imports) |
| `leads/dfw_filter.py` | 9-county, active-on-date, de-duplicated lead rows | Working | `:5-59`, `tests/test_dfw_filter.py` |
| `leads/entity_type.py` | `likely_corporate` / `unconfirmed` name hint | Working | `:6-14`, `tests/test_entity_type.py` |
| `leads/build_lead_list.py` | Runner: writes `data/leads/tdlr_hvac_dfw.csv` | Working, **untested** | `:11-45`; no test imports it |
| `leads/place_match.py` | Places API (New) ACL: key, Text Search, Details, name rules | Working | `:28-111`, tested in `tests/test_lookup_autofill.py:15-17` |
| `leads/website_contacts.py` | Own-site reader: robots, throttle, tel/schema phone, form, licence | Working | `:19-250`, tested in `tests/test_lookup_autofill.py:19-21` |
| `leads/lookup_autofill.py` | Auto-fill the lookup or queue with a reason | Working | `:29-122` |
| `leads/open_places.py` | Overture fallback measurement | Working, **uncommitted** | `:30-136`, `tests/test_open_places.py` |
| `signals/contact_signals.py` | Call/form log loaders, missed rate, trend, do-not-contact | Working | `:23-199`, `tests/test_contact_signals.py` |
| `signals/call_list.py` | Monthly random call list (seed) | Working | `:33-83`, `tests/test_call_list.py` |
| `signals/lookup_sheet.py` | Manual lookup sheet + checker | Working | `:20-77`, `tests/test_lookup_sheet.py` |
| `ranking/hot_lead_score.py` | Month-1 score, band, eligibility | Working (first-party definition) | `:18-81`, `tests/test_ranking_and_calibration.py` |
| `calibration/select_test_groups.py` | Seeded hot/cold test groups | Working | `:16-33` |
| TSBPE plumber source | Plumbing leads | **Missing** | `docs/decisions/data-sources.md:74` |
| Google review signal | Decision 3/7 | **Missing** | grep `review` in `src/` returns nothing |
| Verified/unverified label + outreach gate | Decision 6 | **Missing** | grep returns 0 matches |
| Foursquare OS Places | Decision 5 | **Missing** (skipped, sign-up) | `docs/decisions/open-places.md:12` |

## Holes

### The 7 failure reasons: all handled

| Failure | Reason code | Raised at | Test references (`grep -c` in `tests/test_lookup_autofill.py`) |
|---|---|---|---|
| Wrong business | `name_mismatch` | `src/leads/lookup_autofill.py:85` | 5 |
| No result | `no_place_none` (also `no_place_zip`, `no_place_texas`) | `src/leads/place_match.py:101,105` | 5 / 3 / 1 |
| No website | `no_website` | `src/leads/lookup_autofill.py:75` | 2 |
| robots.txt | `robots_blocked` (401/403/5xx robots means disallow, `src/leads/website_contacts.py:91-92`) | `src/leads/website_contacts.py:228` | 6 |
| No tel: link | `no_tel_phone` | `src/leads/lookup_autofill.py:88` | 5 |
| Fetch failed | `fetch_failed` | `src/leads/website_contacts.py:83,84,224,231` | **1** (thin) |
| Off-site redirect | `redirect_off_site` | `src/leads/website_contacts.py:80` | **1** (thin) |

An extra reason, `places_budget` (`src/leads/lookup_autofill.py:70`), isn't in the agreed list of 7.

### Rate limits and retries
- Websites: one 1-request-per-second throttle for the whole process (`src/leads/website_contacts.py:36-46`). No
  retries by design (`docs/decisions/lookup-automation.md:32`). Tested (`tests/test_lookup_autofill.py:174-179`).
- Places: a hard call budget (`src/leads/lookup_autofill.py:22,58-59,69`), but **no handling for 429 or a transient
  5xx**, which stop the run (`src/leads/place_match.py:79-87`). See hole 5.

### Undefined or inconsistent terms
- "hot lead" means two different things: a score band (`src/ranking/hot_lead_score.py:28`) vs decision 3.
- "verified" is used in the decisions and absent from the code.
- `no_place_name` is still listed as an output reason (`docs/decisions/lookup-automation.md:65`) but was retired
  (`docs/decisions/lookup-automation.md:154`), and the code no longer emits it (reason grep above).
- `docs/decisions/lookup-automation.md:11-12` still says a Places result needs "every main word". That was superseded
  by the 70% share (`src/leads/place_match.py:25`), and later by candidates judged on the site.
- "LLC/Inc only" (decision 2) vs the `likely_corporate` flag, which also covers LLP, LP and LTD (`src/leads/entity_type.py:7`).
- The project glossary is missing: `GLOSSARY.md`, `VISION.md` and `CONTEXT_MAP.md` aren't in `git ls-files`.
  `CONTEXT.md` is added by this audit.

### Hardcoded values
- Counties: `src/leads/dfw_filter.py:5-7`. Overture box: `src/leads/open_places.py:20`.
- Limits: `PLACES_BUDGET = 300` (`src/leads/lookup_autofill.py:22`), `MAX_SITES_PER_BUSINESS = 5`
  (`src/leads/open_places.py:23`), reader limits (`src/leads/website_contacts.py:21-24`), `SLOW_FORM_REPLY_HOURS = 24`
  (`src/ranking/hot_lead_score.py:15`), `NO_REPLY_AFTER_HOURS = 72.0` (`src/signals/contact_signals.py:20`).
- Month and seed in runners: `call_month="2026-11"` (`src/signals/call_list.py:34`), `seed=20261101` (`src/signals/call_list.py:80`),
  and `2026-11_*` file names in every `__main__` (`src/leads/lookup_autofill.py:126-127`, `src/signals/lookup_sheet.py:72`,
  `src/signals/call_list.py:81`, `src/leads/open_places.py:135-136`). December needs code edits.
- Overture release: `src/leads/open_places.py:18`. User-Agent contact: `src/leads/website_contacts.py:19`.
- Keys: **none hardcoded.** The key is read from `.env` (`src/leads/place_match.py:33-42`).

### Missing tests
- `tdlr_source.py` and `build_lead_list.py` have no tests (no import in `tests/`).
- No test for a Places 429 or a mid-run Places failure.
- `fetch_failed` and `redirect_off_site` have one test reference each.

### Secrets (scan run)
```
$ git log --all -p | grep -cE "AIza[0-9A-Za-z_-]{35}"
0
$ git log --all -p | grep -nE "GOOGLE_MAPS_API_KEY\s*="
(no output)
$ gitleaks git . --no-banner
6 commits scanned. ... no leaks found
$ gitleaks dir . --no-banner --redact=100   (working tree, incl. ignored files)
leaks found: 1  ->  .env 1 gcp-api-key   (the key's intended home; .env is Git-ignored, mode -rw-------)
```

### Licence-holder names (personal data) in the repo
All 20,345 distinct holder names from `data/leads/tdlr_hvac_dfw.csv` and the raw TDLR extract were checked against
every tracked file plus the 3 untracked files, and against the full `git log --all -p`:
```
holder names known: 20345
hits 0
history hits 0
```
`data/` is ignored (`.gitignore:1`).

### Stored Google Places content
- `place_id` is stored (`src/leads/lookup_autofill.py:19-20`). Google allows caching it.
- `website_url` is stored after own-site confirmation, as the address the site itself answered on
  (`src/leads/website_contacts.py:233`). It is still found through Google's `websiteUri` first. This is an **accepted
  risk**, documented at `docs/decisions/lookup-automation.md:18-20`, and has had no legal review.
- No display names, addresses or raw `websiteUri` are written: the field masks are at `src/leads/place_match.py:17-18`,
  and the output columns at `src/leads/lookup_autofill.py:99-105`.

### Other findings (reported, not touched)
- The Overture measurement output exists: 80 rows, outcomes `no_match 59, name_mismatch 6, fetch_failed 5,
  confirmed 3, no_tel_phone 3, robots_blocked 2, no_website 1, redirect_off_site 1`, with `match_by` licence 4 and
  name 2. A separate session is reporting it in full.
- `requirements.txt` gained `duckdb==1.5.6`, uncommitted (`git status`).

## Open questions (with recommended answers)

1. Which hot-lead definition wins: Google reviews (decision 3) or first-party call/form signals (`signal-rules.md`)?
   **Recommend:** first-party signals stay the score; reviews become an optional pre-filter only after question 2 is settled.
2. May review text be stored, given `signal-rules.md:9`? **Recommend:** store no text. Store only a per-business count
   of matching reviews and the newest review date, computed live.
3. Does Places API (New) return the 5 *newest* reviews? **Recommend:** check Google's Place Details (New) docs before
   building. If there is no newest sort, reword the rule to "the reviews Places returns".
4. Public email: the decision needs it, the code bans it. **Recommend:** allow only a role address on the business's
   own domain (for example `info@`), from a `mailto:` on its own site, and log the rule first.
5. How is "owner-run" measured for LLC/Inc businesses? **Recommend:** a call-time question recorded in the call log;
   don't infer it from names.
6. How is "open and trading" measured? **Recommend:** Overture `operating_status` (free, already in the release) before
   paying for Places `businessStatus`.
7. What makes a row "verified"? **Recommend:** the own site is confirmed (`match_by` licence or name) **and** a phone or
   `form_url` was found on it. Everything else is "unverified".
8. LLC/Inc only, or every `likely_corporate` suffix? **Recommend:** keep CORP/CORPORATION (= Inc), and decide on
   LP/LLP/LTD explicitly.
9. TSBPE: who downloads the CSVs by hand? **Recommend:** a person downloads them and records the terms, as
   `data-sources.md:76` already says.
10. Foursquare needs a portal account: worth it? **Recommend:** no for now. Overture already includes
    some Foursquare data (`docs/decisions/open-places.md:14`).
11. Commit the uncommitted Overture work? **Recommend:** yes, after its report is reviewed.

## Test result

Run offline: sockets blocked in-process, no files changed.
```
$ .venv/bin/python -c "import socket, sys
def blocked(*a, **k): raise RuntimeError('network blocked during tests')
socket.socket.connect = blocked; socket.create_connection = blocked; socket.getaddrinfo = blocked
import pytest; sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', 'tests']))"
........................................................................ [ 62%]
........................................................................ [ 93%]
..............                                                           [100%]
230 passed in 0.24s
```
**230 passed, 0 failed.** 22 of them are in the uncommitted `tests/test_open_places.py`, so the committed suite is 208.

Row counts quoted above (read-only):
```
2026-11_call_list.csv 100
2026-11_lookup_auto_v3.csv 20 {'licence': 15, 'name': 5}
2026-11_lookup_auto_v4.csv 20 {'licence': 15, 'name': 5}
2026-11_manual_queue_v3.csv 80 {'name_mismatch': 36, 'no_place_none': 23, 'redirect_off_site': 2, 'robots_blocked': 6, 'fetch_failed': 2, 'no_website': 7, 'no_place_texas': 1, 'no_tel_phone': 3}
2026-11_open_places_test.csv 80 {'no_match': 59, 'no_tel_phone': 3, 'confirmed': 3, 'name_mismatch': 6, 'no_website': 1, 'fetch_failed': 5, 'robots_blocked': 2, 'redirect_off_site': 1}
```
