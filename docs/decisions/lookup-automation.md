# Lookup automation rules (written 2026-10-27, before the code)

Replaces "Never scrape" for the November lookup (see the rule change in `call-list-plan.md`).
The code is `src/leads/place_match.py`, `src/leads/website_contacts.py` and `src/leads/lookup_autofill.py`.

## Google Places (finding the website)

- **Places API (New)**, key `GOOGLE_MAPS_API_KEY`, read from `.env` (Git-ignored). The key is sent only in the
  `X-Goog-Api-Key` header. It is never printed, logged or written to any file.
- **Text Search**, field mask `places.id,places.displayName,places.formattedAddress`, query
  `"<business_name> <county> County TX"`. The result is accepted only if its display name has every main word of the
  licence name (rule below) and its address is in Texas (`, TX 7xxxx`). Only the **place_id** is kept.
- **Place Details**, field mask `websiteUri` only. The website address is used live, in memory, to start the own-site
  reader.
- **Google data is used live only and never stored, except `place_id`.** Display names, addresses and the raw
  `websiteUri` are not written anywhere. What is stored as `website_url` is the site's own address after it has been
  read and confirmed (below), not Google's value.
- **Accepted risk:** the website address is found through Google live, then confirmed on the site itself. Google's terms
  restrict storing Places content. This design keeps only place_id, which Google allows, but the website address
  still comes from Google first.

## Own-site reader (reading the business's website)

- **At most 2 pages per business:** the homepage, plus one contact page linked from it on the same site.
  `robots.txt` is fetched once per site and does not count as a page.
- **Obey robots.txt** for the token `OptomateResearch`. If it disallows a page, that page is not fetched.
  If robots.txt answers 401/403, or can't be reached (server error, timeout), nothing on the site is fetched.
  A 404 means no rules, so everything is allowed.
- **User-Agent:** `OptomateResearch/0.1 (research contact: ops@optomate.co.uk)`. No other identity, no browser disguise, no
  fingerprinting, no proxies.
- **At most 1 request per second**, counted across every request (robots.txt, pages and redirects).
- **10-second timeout** per request. **No retries.** A failure goes to the manual queue.
- **Redirects:** followed only within the same site (`www.` and `http`→`https` variants), at most 3 hops. A redirect to
  another site stops the read.
- Only HTML responses are read, up to 2 MB each.
- Query strings and fragments are removed from the website address before it is read or stored. Google's
  `websiteUri` often carries tracking parameters.

## What is stored

| Value | Only from | Stored with |
|---|---|---|
| `business_phone` | `tel:` links, or schema.org `telephone` in JSON-LD, never from a `Person` node | `phone_source_url` = the page it was on |
| `form_url` | The contact page, if that page has a `<form>` containing a `<textarea>` (a message box) | The URL is its own source |
| `website_url` | The site's own homepage address after redirects | `lookup_date` |

- **Phone choice:** schema.org `telephone` first, because the business declares it as its number. Otherwise the `tel:`
  number that appears most often on the page (the main number usually repeats in the header and footer); on a tie,
  the first one. The number must be a valid 10-digit US number and is stored as `214-555-0100`.
- **Never collect emails.** `contact_email` stays empty, and `mailto:` links are ignored.
- **Never parse phones from free text.** A number that isn't in a `tel:` link or schema.org markup is ignored.

## Accepting a site

The site is accepted only if its name (`og:site_name`, else the schema.org organisation name, else `<title>`) contains
**every main word** of the licence `business_name`. Main words are the name's words in capitals, with dots removed
(`D.T.M.` → `DTM`), `&` read as `AND`, and these words dropped: LLC, INC, CO, plus CORP, CORPORATION, INCORPORATED,
LTD, LP, LLP, THE, AND, OF. Singular and plural count as the same word (see "Rule changes" below).
The Places result is picked with a looser test, 70% of the main words (see "Rule changes").

## Outputs

- `data/logs/2026-11_lookup_auto.csv`: the lookup sheet columns plus `place_id`, one row per accepted business,
  `lookup_date` = run date, `lookup_initials = auto`.
- `data/logs/2026-11_manual_queue.csv`: every other business, with its `reason`: `no_place_none`, `no_place_name`, `no_place_zip`, `no_place_texas`, `no_website`,
  `robots_blocked`, `fetch_failed`, `redirect_off_site`, `name_mismatch`, `no_tel_phone`. A queue row keeps
  `website_url` and `form_url` only when the site passed the name check. Queue rows are looked up by hand under the
  Lookup step rules.
- Neither file is ever overwritten. Every business on the call list ends up in exactly one of them.
- The original `2026-11_lookup.csv` and the call list are not touched.

## Known limits

- A `tel:` link can still be a person's own mobile, for example on a one-person business's site. The reader can't tell.
  Callers treat any number that reaches a named person's personal line as a wrong number and put it on the manual queue.
- Forms built in JavaScript or embedded in an iframe aren't seen, so `form_url` stays empty for those sites.

## Rule changes

### 2026-10-27: Places name match (after the v1 run, before v2)

**Evidence.** The v1 run sent 71 of 100 businesses to `no_place`. A live re-search of the first 10 of them (by
licence number in call-list order; 10 Text Search calls; results held in memory only, nothing stored) found:

| Which test failed | Count |
|---|---|
| Google returned no results at all | 6 |
| Results came back, but no result shared the name | 2 |
| A near name (plural, or one word off) in Texas | 2 |
| Name matched, Texas address without ZIP | **0** |
| Name matched, address not in Texas | 0 |

| | Old rule | New rule |
|---|---|---|
| Places name | Every main word of the licence name must appear in Google's name | **At least 70%** of the licence name's main words appear in Google's name, compared as whole numbers (3 of 4 passes, 2 of 3 does not) |
| Singular / plural | Different words | **The same word**: a trailing `S` is dropped from words longer than 3 letters that don't end in `SS` (SERVICES = SERVICE), in both the Places test and the site test |
| Site name (confirmation on the business's own site) | Every main word | **Unchanged**: every main word, now with singular = plural. The 70% share applies to Google's name only, so the site itself still has to carry the full name |
| Texas address | `, TX 7xxxx` | **Unchanged.** The ZIP failure was not seen in the evidence (0 of 10), so it isn't changed without proof |

**Why only the name rule.** 4 of 10 failed on name words, and 2 of those were near names that the new rule is meant
to catch. The ZIP requirement explained none of the 10. The biggest cause, 6 of 10 with no results at all, isn't
fixed by either change.

**Queue reasons now record the failed test**, so the next diagnosis needs no extra Places calls:
`no_place_none` (no results), `no_place_name` (no result shares the name), `no_place_zip` (name matches, Texas
address without ZIP), `no_place_texas` (name matches, not in Texas). The v2 run measures `no_place_zip` across all
businesses, which is the evidence needed before changing the address rule.

### 2026-10-27: User-Agent contact and queue reasons (after the v2 run)

| | Old rule | New rule | Reason |
|---|---|---|---|
| User-Agent | `OptomateResearch/0.1 (research contact: see README)` | `OptomateResearch/0.1 (research contact: ops@optomate.co.uk)` | The README is in a private repo, so a site owner reading their server logs couldn't reach it. The address now travels with every request. |
| Queue reason for a Places miss | `no_place`, written by `lookup_autofill.py` | The failed test: `no_place_none`, `no_place_name`, `no_place_zip`, `no_place_texas` | The v2 run needed a separate runner to record these. They are now written by the module itself, so every future run records them. |

### 2026-10-27: Accept a site by licence number (before v3, before the code)

| | Old rule | New rule |
|---|---|---|
| Accepting a site | The site name carries every main word of the licence `business_name` | **Either** that name rule passes, **or** the site shows the business's own TDLR licence number |
| Places | One result, picked by the 70% name share | **Up to 3 candidates** whose address passes the Texas + ZIP rule (unchanged), tried in order on the business's own site. Candidates that pass the 70% name share go first |

**Legal source.** 16 TAC §75.71 ("Responsibilities of the Contracting Company"), subsection (h): all advertising by
air conditioning and refrigeration contracting companies "designed to solicit air conditioning or refrigeration
business must include the affiliated licensee's license number." Checked on 2026-10-27 in the Cornell LII copy of the
Texas Administrative Code.

**Limits.**
- Not every site shows the number. §75.71(h) says "all advertising" and lists exemptions, but doesn't name websites,
  and compliance is uneven.
- The rule requires the *affiliated licensee's* number. A company can show a different licensee's number from the one
  in our TDLR row. That's a non-match, and the name rule still applies.
- The rule sets no format. How sites write the number is **unverified until it is checked on real sites** (next
  entry), and the matcher is set from that evidence.
- The reader still reads only the homepage and one contact page, so a number shown only on another page isn't seen.

### 2026-10-27: Licence format on real sites (evidence for the matcher)

The homepages of the first 10 v2 auto-filled sites, by licence number, were read once each (robots.txt obeyed,
same User-Agent and throttle, no Places calls; page text held in memory only, nothing stored):

| What the homepage shows | Sites |
|---|---|
| Its own licence: `TACLA` or `TACLB` + 0 to 3 leading zeros + the licence digits + `C` or `E` (for example `TACLB00012345E`) | 6 (one of them also shows a second licensee's TACL number) |
| A `TACT` token with a different number | 1 |
| No licence number on the homepage | 3 |
| The licence digits without the `TACL` prefix | 0 |

**Matcher (set from this evidence, unchanged from the brief):** `site_shows_licence_number()` is true only when a run
of digits starting within 20 characters after `TACL`, read in the page's visible text with leading zeros ignored, is
exactly the licence number. Digits without the `TACL` prefix never count, and a longer or shorter number containing the
licence digits doesn't count either.

**Queue reasons in v3:** `no_place_name` is retired. Candidates are no longer filtered by Google's name; the name is
judged on the business's own site (`name_mismatch`). A business keeps the reason of its first candidate, unless a
later candidate's site was confirmed but had no phone (`no_tel_phone`), which is kept instead because that site is the
business. `places_budget` is new: a candidate wasn't tried because the run's Places budget (300 calls) had to stay
free for the businesses still to be searched.

### 2026-10-28: Wider searches for the v3 queue (before v4, before the code)

Applies to a re-run of the 80 businesses in `2026-11_manual_queue_v3.csv` only.

| | Old rule | New rule |
|---|---|---|
| Candidates per query | 3 | **5** (Texas + ZIP rule unchanged) |
| Queries | 1: `<business_name> <county> County TX` | Tried in this order, each **only if the earlier ones found no confirmed site**: **1** the original query; **2** the name without trade words (AIR, HEATING, COOLING, CONDITIONING, HVAC, MECHANICAL, SERVICES, singular or plural, plus the entity words LLC, INC, CO, CORP, CORPORATION, INCORPORATED, LTD, LP, LLP and THE, AND, OF) + `<county> County TX`; **3** `<business_name> <county> TX`; **4** `<licence holder name> air conditioning <county> TX` |
| Identity | Licence number or site name on the business's own site | **Unchanged.** A site is confirmed only on the business's own site, by the TACL licence number or the existing site-name rule. A wider search only finds more candidates; it never confirms one |

**Details:**
- Query 2 is skipped when removing the trade words leaves nothing, or leaves the name unchanged. A query identical
  to an earlier one is skipped.
- Query 1 was already run in v3 with 3 candidates, so here it only adds candidates 4 and 5. Its first 3, and the
  place_id recorded in the v3 queue, count as already tried. **A place_id already tried for a business is never
  fetched again** for that business.
- **The licence holder name is personal data.** It is read from `data/leads/tdlr_hvac_dfw.csv` (`licence_holder`, as
  "LAST, FIRST M", sent as "FIRST M LAST") and used only as a live Text Search query. It is never stored, printed or
  logged. Notes record only the query number (`query_used=4`), never the query text.
- **Budgets, counted separately:** at most 600 Text Search calls and 300 Place Details calls. If either cap would be
  passed, the run stops calling Google, and every business not finished keeps its v3 queue row unchanged.
- **Merge:** `2026-11_lookup_auto_v4.csv` = every v3 auto row unchanged + the newly confirmed rows.
  `2026-11_manual_queue_v4.csv` = the rest, each with the reason from this re-run (a confirmed site without a phone
  is kept first, otherwise the first candidate's reason, otherwise the last query's `no_place_*` reason).

**Result (2026-10-28).** Wider searches were tried on 43 of the 80 queued businesses, and 0 new businesses were
confirmed. The run stopped when the Place Details cap was reached at 300 calls (Text Search: 175 of 600). The other 37
kept their v3 queue rows. The outputs are `2026-11_lookup_auto_v4.csv` and `2026-11_manual_queue_v4.csv`. **Experiment
closed:** the v4 code was reverted, so the queries, candidate count and budgets above are not in the code. The 80
businesses go to the manual lookup.
