# Month-1 call list plan (written 2026-10-27, before the draw)

## What and when

- **Month:** 2026-11.
- **Size:** 100 businesses. The hot/cold split is unknown, and calibration needs at least 15 eligible leads in each band,
  so the list is large enough to have a fair chance of that.

## Pool

Rows in `data/leads/tdlr_hvac_dfw.csv` where **all** of these hold:
- `entity_flag = likely_corporate`
- The licence is **active on every possible call date**: `expiry_date` on or after **2026-11-30**, the last day of the month.
  The call date is not known at draw time, so the strictest date is used.
- `licence_number` is not on the do-not-contact list. On 2026-10-27 no call log exists yet, so the list is empty.

## Draw

- **Fixed seed: `20261101`**, recorded here before the draw.
- Sort the pool by `licence_number`, then give each row one key from `random.Random(20261101).random()` in that order.
  The 100 rows with the lowest keys are selected.
- **Time bands:** the same random generator then gives each selected row a second key, taken in licence-number order.
  Rows are sorted by that key and assigned `morning`, `afternoon`, `evening` in turn, so band counts differ by at most 1
  (34 / 33 / 33 for 100 rows).
- If the pool has fewer than 100 rows, the draw stops with an error that gives the count.

## Second batch

If month 1 gives fewer than 15 eligible leads in either band (hot or cold), draw a second batch:
- Use a **new seed**, logged in this file **before** that draw.
- **Never reuse a business already called.** Exclude every licence number on an earlier call list, as well as the
  do-not-contact list.

## Business phone: not in the data

The TDLR dataset has a `business_telephone` field (and an `owner_telephone` field), but **both are empty for all 20,462
A/C Contractor rows** in the 2026-10-27 download. So `business_phone` on the call list is **empty** and callers must
find each number by hand before calling (see "Lookup step" below). `owner_telephone` would not be used even if it were
filled, because it can be a personal number.

## Call sheet

`data/logs/2026-11_call_list.csv`, columns: `licence_number, business_name, county, business_phone, time_band, call_date,
result, voicemail_greeting_present, caller_initials, stop_requested, notes, form_url, form_sent_at_local,
form_first_reply_at_local`. Every result column is left empty for the caller.
The sheet is never overwritten once written, so a filled-in sheet cannot be lost by re-running the draw.

## Recorded after the draw

| Item | Value |
|---|---|
| Run date | 2026-10-27 |
| Python version | 3.12.15 |
| Pool size | 2,031 (of 2,135 `likely_corporate`; 104 expire before 2026-11-30; do-not-contact list empty) |
| Selected | 100, seed `20261101` |
| Morning / afternoon / evening | 34 / 33 / 33 |
| Output | `data/logs/2026-11_call_list.csv` (Git-ignored) |

## Lookup step (written 2026-10-27, before the code)

Done by a person, one business at a time, **before 2026-11-01**, in `data/logs/2026-11_lookup.csv`.
Looking something up is not contact: nobody is called, emailed or messaged during the lookup.
The call list `data/logs/2026-11_call_list.csv` is not edited. Callers read the phone from the lookup sheet.

**Source: the business's own website only.** For every value, record the exact page URL it came from and the lookup date.

| Column | What goes in it |
|---|---|
| `website_url` | The business's own website home page, or `no_website` |
| `business_phone` | The main customer number published on the site, as `214-555-0100` |
| `phone_source_url` | The exact page on the site that shows that number |
| `form_url` | The site's contact form page. The URL is its own source |
| `contact_email` | The contact address the business publishes on its site (for example `info@` or `office@`) |
| `email_source_url` | The exact page on the site that shows that address |
| `lookup_date` | `YYYY-MM-DD`, the day of the lookup |
| `lookup_initials` | The person who did the lookup |
| `notes` | Short and factual |

**Match before you trust it.** Use the site only if the business name on it matches `business_name` (small differences
like "LLC" or "&" are fine) and it places the business in or near the listed `county`. If unsure, treat it as no website.

**No website found:** write `no_website` in `website_url` and leave every other lookup value empty. At call time, the
caller may read the number live on Google Maps to dial it, but **must never write that number into any sheet**.

**Never collect** personal mobile numbers or personal email addresses, and never take anything from directories,
data brokers, people-search sites, paid lists or social media. Not a person's direct line, and not a staff page.

~~**Never scrape.** Every lookup is done by hand in a browser. No scrapers, extensions, bulk lookup services or scripts.~~
**Superseded 2026-10-27**, see "Rule changes" below and `lookup-automation.md`.

**Checking the sheet:** `check_lookup_sheet()` reports every row where:
- a phone or email is present but its source URL is missing, or a source URL is not on the row's `website_url` site;
- any value is present but `lookup_date` is missing;
- `website_url` is `no_website` but a phone, form URL or email is filled in.

Fix every reported row before calls start.

## Rule changes

| Date | Old rule | New rule | Reason |
|---|---|---|---|
| 2026-10-27 (before any automated lookup) | "Never scrape. Every lookup is done by hand." | Automated lookup under the rules in `lookup-automation.md`: Google Places (New), used live, finds each business's website, then a strict own-site reader reads at most 2 pages (homepage + one contact page), obeys robots.txt, sends an honest User-Agent and makes at most 1 request per second. It stores only a phone from `tel:` links or schema.org `telephone`, the contact-form page URL and the website URL, each with its source page. Emails are never collected. Anything it can't confirm goes to a manual queue, worked by hand under the Lookup step rules above. | The open-source extractor (vdrmota) was rejected after a sandbox security test: 104 dependency advisories, fingerprint spoofing, and it mixed personal contacts in with business ones. A narrow reader with explicit limits replaces it. |
