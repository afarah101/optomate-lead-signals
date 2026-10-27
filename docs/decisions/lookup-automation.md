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
- **User-Agent:** `OptomateResearch/0.1 (research contact: see README)`. No other identity, no browser disguise, no
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
- `data/logs/2026-11_manual_queue.csv`: every other business, with its `reason`: `no_place`, `no_website`,
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
