# Data sources

## TDLR licence holders: HVAC lead source (verified 2026-10-27)

| Item | Value |
|---|---|
| Dataset name | TDLR - All Licenses |
| Dataset ID | `7358-krk7` |
| URL | https://data.texas.gov/dataset/TDLR-All-Licenses/7358-krk7 |
| API used | `https://data.texas.gov/resource/7358-krk7.csv` (Socrata SODA, no key) |
| Publisher | Texas Department of Licensing and Regulation (the dataset metadata `attribution` and `Agency` fields both give this name) |
| Provenance flag | `official` |
| Portal | Texas Open Data Portal (data.texas.gov), run by Texas DIR on Tyler Technologies (Socrata) |
| Created | 2014-08-01 |
| Last data update (`rowsUpdatedAt`) | 2026-10-19 18:51 UTC |
| Rows (whole dataset) | 966,778 on 2026-10-27 |

### Licence / terms of use: exact quotes

1. Dataset metadata (`/api/views/7358-krk7.json`): `"license": null`, `"licenseId": null`. **The dataset publishes no licence.**
2. Portal footer "Terms of Service" link goes to Tyler's *Data & Insights Software-As-A-Service License Agreement*
   (https://www.tylertech.com/client-terms/data-insights-software-as-a-service-license-agreement).
   That agreement covers the government client, not the public. It says that the
   "Client is solely responsible for determining the online terms of use and licenses"
   for public users. In other words, the State of Texas or TDLR sets data terms. Tyler does not.
3. Texas DIR's portal page (https://dir.texas.gov/office-chief-data-officer/texas-open-data-portal) describes the portal as
   "the official State of Texas repository for publicly accessible open data sets".

**Finding:** I found no term that forbids downloading or reusing this data. I also found no explicit open licence.
The publisher's own page is the dataset's `attributionLink` (https://www.tdlr.texas.gov/LicenseSearch/licfile.asp).
I did **not** open it, because it sits on the TDLR licence search site, which is out of bounds.
**Open action:** a person should read that page by hand for any TDLR use conditions before outreach starts.

### Field mapping to `data/leads/tdlr_hvac_dfw.csv`

| Output column | Source field | Note |
|---|---|---|
| business_name | `business_name` | |
| licence_holder | `owner_name` | **To be removed** (decision 2026-10-29, pending code change; see "Change log") |
| licence_number | `license_number` | |
| licence_type | `license_type` | Kept value: `A/C Contractor` (the Air Conditioning and Refrigeration Contractor licence). `A/C Technician` and `A/C CE Provider` are excluded. |
| licence_status | *none* | **No status column in the dataset. Left empty.** |
| expiry_date | `license_expiration_date_mmddccyy` | MM/DD/YYYY, as published |
| address | `business_address_line1`, `business_address_line2` | **Both fields are empty for all 20,462 A/C Contractor rows (checked 2026-10-27), so this column is empty.** |
| city | `business_city_state_zip` | **Empty for all A/C Contractor rows, so this column is empty.** |
| county | `business_county` | Empty on 777 A/C Contractor rows. Those rows cannot match DFW and are dropped. |
| source | literal | The dataset URL above |
| retrieved_on | literal | Download date |

Not used: `mailing_address_*`, `owner_telephone` and `business_telephone`. The mailing address is the only address
the dataset fills in, but it can be the holder's home address, and the brief did not ask for it.
**Decision (2026-10-27, Ahmed Farah):** keep `address` and `city` empty. Do not use mailing addresses.

### Rules applied

- **Active** = `expiry_date` is on or after the retrieval date. The dataset has no status field, and it does
  contain expired licences (for example 11/07/2025), so the expiry date is the only signal.
- **DFW** = `business_county` in Dallas, Tarrant, Collin, Denton, Rockwall, Kaufman, Ellis, Johnson, Parker.
- **De-duplication** = first row per `license_number`. The source had 0 duplicates on 2026-10-27
  (20,462 rows, 20,462 distinct numbers). The rule stays as a guard.
- Personal data stays local: `data/` is in `.gitignore`.

## TSBPE plumber licences: not available for automated use (checked 2026-10-27)

| Item | Value |
|---|---|
| data.texas.gov | **No TSBPE dataset.** Catalog API searches for `plumbing`, `Plumbing Examiners` and `plumber license`, and the attribution `Texas State Board of Plumbing Examiners`, all returned 0 results for the data.texas.gov domain. |
| Publisher's own file | Texas State Board of Plumbing Examiners, "Free Licensee List": https://tsbpe.texas.gov/free-licensee-list/ (found by web search; the search summary described daily-updated CSV lists that include Master Plumber and Responsible Master Plumber) |
| Access result | One plain HTTPS GET of that page returned **HTTP 403 with a Cloudflare "Sorry, you have been blocked" page**. |
| Last update | Unknown: page not readable. |
| Terms of use | **Not quoted: page not readable.** The web search summary mentioned a terms-of-use disclaimer on the page, but I could not read its wording. |

**Decision:** TSBPE is skipped. I did not retry with other clients, headers or tools, because that would mean getting around the publisher's bot protection. I did not touch the TSBPE licence search.
`src/leads/tsbpe_source.py` was not created, because the file's columns are unknown and the brief says not to invent fields.

**To unblock:** a person downloads the Master Plumber and Responsible Master Plumber CSVs by hand from the page above, reads and records the terms here, and saves the files to `data/raw/`. The source can then be built from the real columns. The other option is to ask TSBPE for a bulk data file.

## Entity-type flag (`entity_flag` column)

`flag_likely_corporate_entity(business_name)` in `src/leads/entity_type.py` returns `likely_corporate` when the business name
contains LLC, L.L.C., INC, INCORPORATED, CORP, CORPORATION, LTD or LLP as a whole word (any case). Otherwise it returns `unconfirmed`. LP alone no longer counts (2026-10-29). **LLP and LP treatment: TO CONFIRM with adviser.**

**This flag is a hint from the name only. It does not confirm legal entity status.** A name can carry "LLC" after
the entity has ended, and a real company can trade under a name with no suffix.
**Before any email, confirm each entity by hand in the Texas Comptroller Taxable Entity Search**
(https://comptroller.texas.gov/taxes/franchise/account-status/search).

## Change log

| Date | Old rule | New rule | Reason |
|---|---|---|---|
| 2026-10-29 | `licence_holder` (TDLR `owner_name`) kept in `data/leads/tdlr_hvac_dfw.csv` | **Remove the `licence_holder` column from the leads file. Pending code change**: the leads builder still writes it until that change is made | It is personal data with no current use (`docs/compliance/legitimate-interests-assessment.md`, data minimisation) |
| 2026-10-29 | `likely_corporate` on LLC, L.L.C., INC, INCORPORATED, CORP, CORPORATION, LTD, LP or LLP | **LP removed.** LLC, L.L.C., INC, INCORPORATED, CORP, CORPORATION, LTD and LLP still count (`src/leads/entity_type.py`). **LLP and LP treatment: TO CONFIRM with adviser** | Compliance decision, 2026-10-29: outreach is to LLC and Inc businesses only |
