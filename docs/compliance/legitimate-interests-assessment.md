# Legitimate Interests Assessment: Optomate lead signals (draft, updated 2026-11-14)

**Controller:** Optomate LTD, company number [COMPANY_NUMBER], registered office [REGISTERED_OFFICE].
**Contact for data requests:** admin@optomate.co.uk.
**Who handles the data:** Ahmed only. Only Ahmed sees the lists and makes the calls. No staff, VA or contractor.
**Method:** the ICO three-part test: purpose, necessity, balancing.

Every rule below is cited to the decision file that sets it (`docs/decisions/…`, `docs/templates/call_script.md`). Items marked **TO CONFIRM** are open and must not be filled from memory.

---

## 0. What the processing is

Optomate LTD builds a list of HVAC contractor businesses in the Dallas–Fort Worth area from the public Texas licence
register, and finds each business's own website, published business phone and contact form. It then measures how the
business handles contact: at most one call and one form message per month, each naming Optomate and its purpose.
A business that often misses calls or replies slowly is scored as a likely lead. Optomate then emails a small, verified
group to offer a call-answering service, and tests whether those leads reply more often than others
(`signal-rules.md`, "Month-1 composite score"; `calibration-plan.md`; `call_script.md`).

**Recipients are LLC and Inc businesses only. Sole traders are excluded.** In the code, only rows with
`entity_flag = likely_corporate` are drawn or eligible (`call-list-plan.md`, "Pool" and "Month-1 list v2";
`signal-rules.md`, "Eligible for the test"). Since 2026-10-29 the flag matches LLC, INC, CORP, LTD and LLP, but not
LP. **LLP and LP treatment: TO CONFIRM with adviser** (`data-sources.md`, change log). The flag is only a hint from the
name, so each business is confirmed by hand in the Texas Comptroller Taxable Entity Search before any email
(`data-sources.md`, "Entity-type flag"; `calibration-plan.md`, "Groups").

### Data categories

| Category | What exactly | Source | Cited in |
|---|---|---|---|
| Business name | TDLR `business_name` | TDLR open data | `data-sources.md`, field mapping |
| Licence number | TDLR `license_number`, plus `expiry_date` and `county` | TDLR open data | `data-sources.md`, field mapping |
| Entity flag | `likely_corporate` / `unconfirmed`, from the name | Derived | `data-sources.md`, "Entity-type flag" |
| Business phone | Only from `tel:` links or schema.org `telephone` on the business's own site, never from a `Person` node, with the source page. Fallback for a verified business with no phone on its site: an open map dataset's listing phone, marked `phone_unconfirmed` | Own website; open map dataset | `lookup-automation.md`, "What is stored"; `reverse-lookup.md`, "Output"; `call-list-plan.md`, "Month-1 list v2" |
| Website | The site's own homepage address after redirects | Own website (found through Google Places or open map datasets) | `lookup-automation.md`, "What is stored"; `open-places.md`; `reverse-lookup.md` |
| Contact-form URL | The contact page, if it has a message form | Own website | `lookup-automation.md`, "What is stored" |
| **Named business email** | A named or generic address (for example `jane@` or `office@`), **only as published on the business's own website**, with the page it was on. *Rule only: no code collects it yet* | Own website | `lookup-automation.md`, 2026-10-29 "Outreach email address" |
| **Opening-line facts** | Facts used in a personal opening line of an email, **each with its source URL**; only from the own website or TDLR data. *Rule only: no code yet* | Own website; TDLR open data | `lookup-automation.md`, 2026-10-29 "Facts for a personal opening line" |
| **Named owner/manager name and role** | The name and role of one person, **only as shown on the business's own website**, with the page it was on. Role is one of owner, co-owner, founder, president, CEO, general manager. Found by code; never put in an email; never the TDLR licence holder | Own website | `docs/agents/sales-researcher.md`, hard rules 4, 6 and 7 |
| Raw page text (short-lived) | The text of at most 2 pages of the business's own website. It can show reviews and customer names. Held only in memory while the code finds the named owner/manager; `_pages.json` keeps page URLs only. The model reads a temporary copy (at most 5,000 characters per page) with quoted passages, 300 characters each side of a review word, and names removed. The removal is a heuristic, so review text with no such mark can stay in that copy. Never in the CSV or the email. The copy is deleted in the same run, or after a run that stops early at the start of the next weekly run; with no later run it stays until deleted by hand | Own website | `docs/agents/sales-researcher.md`, Step 1, Step 3 and Script B |
| Place identifiers | Google `place_id`; open map dataset record IDs (`source_record_id`, `source_datasets`, `fsq_place_id`) | Google; open map datasets | `lookup-automation.md`, "Google Places"; `open-places.md`, "What is stored"; `reverse-lookup.md`, "Output" |
| Identity label | `verified` / `unverified` / `unresolved` | Derived | `lookup-automation.md`, 2026-10-28 "Identity label" |
| Call outcome | `result` (`answered_by_person`, `voicemail`, `no_answer`, `invalid`), call date and time, time band, `voicemail_greeting_present` (evening only), `stop_requested`, short factual notes | First-party (Ahmed's call) | `signal-rules.md`, "Calls"; `call_script.md`; `call-list-plan.md`, "Call sheet" |
| Form reply time | Form sent time, first human reply time, `form_reply_hours`, `no_reply` after 72 hours | First-party (Ahmed's form message) | `signal-rules.md`, "Forms" |
| Lead score | 0–3 points per month and band `hot` / `middle` / `cold` | Derived | `signal-rules.md`, "Month-1 composite score" |
| Licence holder name | TDLR `owner_name`, held as `licence_holder` in the downloaded licence list. **Decision 2026-10-29: remove the column; pending code change** | TDLR open data | `data-sources.md`, field mapping and change log |

**The licence holder name is personal data** (a named individual). It is not read by the reverse lookup
(`reverse-lookup.md`, "Source") or the open-places test (`open-places.md`, rule 5). It was used once, as a live Google
Text Search query in the closed v4 experiment, never stored, printed or logged there, and that code was reverted
(`lookup-automation.md`, 2026-10-28 "Wider searches"). It is never used for contact. Its removal from the leads file is
decided and waiting on a code change (`data-sources.md`, change log).

### Data not collected

| Not collected | Cited in |
|---|---|
| Guessed, pattern-built or purchased email addresses. Gmail-type addresses shown as a business contact: **TO CONFIRM with adviser** | `lookup-automation.md`, 2026-10-29 "Outreach email address" |
| Any email, by the current own-site reader: `contact_email` stays empty, `mailto:` is ignored, and Overture `emails` are never selected | `lookup-automation.md`, "What is stored"; `open-places.md`, "What is stored" |
| Review text in our records (the CSV, the lead files) and emails: "No Google review content is stored anywhere"; never used in an opening line. Exception: the temporary model copy of own-site page text (row "Raw page text" above) can hold review text the code did not recognise | `signal-rules.md`, "Data origin"; `lookup-automation.md`, 2026-10-29 "Facts for a personal opening line"; `docs/agents/sales-researcher.md`, Step 1 |
| Anything collected automatically from social media (it is read by hand only) | `lookup-automation.md`, 2026-10-29 "Facts for a personal opening line" |
| Call recordings: "Do not record the call" | `call_script.md` |
| Personal mobile numbers and direct lines; anything from directories, data brokers, people-search sites, paid lists or social media | `call-list-plan.md`, "Lookup step"; `lookup-automation.md`, "Known limits" |
| Mailing addresses (they can be the holder's home) and `owner_telephone` | `data-sources.md`, field mapping and decision; `call-list-plan.md`, "Business phone" |
| Google display names, addresses and raw `websiteUri` (only `place_id` is kept) | `lookup-automation.md`, "Google Places" |
| Open map dataset names, addresses, phones, emails and socials (except the `phone_unconfirmed` fallback above) | `open-places.md`, "What is stored"; `reverse-lookup.md`, "Output" |
| Personal details about the person who answers | `call_script.md`, "Logging" |
| Phones parsed from page text | `lookup-automation.md`, "What is stored" |

---

## 1. Purpose test: is there a legitimate interest?

| Question | Answer |
|---|---|
| What is the interest? | **Optomate LTD's commercial interest in finding US HVAC businesses that miss customer calls or reply slowly, and offering them a call-answering service by B2B email.** Recital 47 UK GDPR says direct marketing may be a legitimate interest. |
| Who benefits? | Optomate (better-targeted outreach and fewer untargeted messages). The businesses may benefit by hearing about a service that answers the calls they miss. |
| Why is it important? | Without the signals, outreach would go to every licensee. That means more messages to businesses that have no need. |
| Other laws and rules | TDLR data publishes no licence, and no reuse ban was found. **Open action:** the TDLR attribution page must be read by hand for use conditions before outreach starts (`data-sources.md`, "Finding"). Google Places terms: only `place_id` is kept (`lookup-automation.md`, "Accepted risk"). Open map dataset licences and attribution are recorded (`open-places.md`, "Licences"). Website reads obey robots.txt (`lookup-automation.md`). US rules for calls and email (for example CAN-SPAM) are outside this assessment. |
| Ethical issues | The call and the form message state the real purpose (`call_script.md`; `signal-rules.md`, "Forms"). No pretend customer inquiries. |

**Result:** passes.

---

## 2. Necessity test: is the processing needed for it?

| Question | Answer |
|---|---|
| Does each item help the purpose? | Licence number and name: they identify the business and prove identity on its own site (`lookup-automation.md`, "Accept a site by licence number"; `reverse-lookup.md`, "Join"). Phone and form URL: needed to take the call and form measurements. Call outcome and reply time: these *are* the signals (`signal-rules.md`). Website: the only accepted source of contact details. Business email: needed to send the outreach email. Named owner/manager name and role: the first email goes to a person who can decide, not to a general inbox. Opening-line facts: they make the email relevant to that business, and each one carries its source. |
| Is there a less intrusive way? | Several steps already take the least intrusive option: only the business's own site counts, at most 2 pages are read (`lookup-automation.md`), there is one call and one form per month (`signal-rules.md`), voicemail is never left (`call_script.md`), Google data is not stored (`lookup-automation.md`), and email addresses are never guessed or bought (`lookup-automation.md`, 2026-10-29). |
| Is anything held that isn't needed? | The licence holder name. Its removal is decided (`data-sources.md`, change log); the code change is pending. |
| Is the call frequency proportionate? | Yes. **One call per business per calendar month at most**, every call counted, including `invalid` ones (`signal-rules.md`, "Frequency"; `call_script.md`). One form message per month at most (`signal-rules.md`, "Forms"). |

**Result:** passes, on condition that the licence holder column is removed before the first call or email.

---

## 3. Balancing test: do the businesses' interests override?

### Nature of the data
Mostly business data published by the business itself (its own site) or by the State of Texas (the licence
register). The only personal data are the licence holder name (being removed), a named business email and the name
and role of a named owner or manager, both as published on the business's own site, and possibly a phone that turns
out to be a person's own line. No special-category or criminal-offence data is held.

### Reasonable expectations of a licensed business
- Texas requires A/C contractors to show their licence number in their advertising: 16 TAC §75.71(h)
  (`lookup-automation.md`, "Legal source"). The register is published as open data (`data-sources.md`).
- A business that publishes a phone number, an email address and a contact form on its own website expects customers
  and suppliers to call it and send messages.
- An LLC or Inc. can reasonably expect occasional B2B contact.
- The call and the form message say who is calling, why, and that a call-answering service may be offered later, and
  they give the privacy notice URL (`call_script.md`; `signal-rules.md`, "Forms" and "Notice timing"). So the
  measurement is not hidden from the business at first contact.

### Likely impact
Low: at most one short call and one form message a month, no voicemail or messages left, and no recordings. The score
affects only whether a business receives a B2B email. It has no legal or similarly significant effect.

### Safeguards

| Safeguard | Cited in |
|---|---|
| **The real purpose is stated**: the call opening names Ahmed, Optomate (a UK company), the study and the possible call-answering service; the form message names Optomate and asks the same real question | `call_script.md`; `signal-rules.md`, "Forms" |
| **Notice at first contact**: an answered call or a form message gives the notice URL. An unanswered call is not a contact. The first email carries the notice and goes within 1 month of collecting the data | `signal-rules.md`, "Notice timing"; `call_script.md` |
| **Opt-out on calls:** "If they ask not to be called again", the caller agrees, ends the call and logs `stop_requested = yes` | `call_script.md` |
| **Do-not-contact list kept permanently**, and honoured even on a rejected log row; any later call is rejected | `signal-rules.md`, "Do-not-contact"; `call_script.md` |
| Do-not-contact checked before every call and on the day of every send | `call_script.md`; `calibration-plan.md`, "Groups" |
| Do-not-contact businesses are left out of every call list | `call-list-plan.md`, "Pool" |
| **One call per business per calendar month at most**; one form message per month | `signal-rules.md`, "Frequency" and "Forms" |
| Calls only in three day-time and early-evening bands (Dallas time) | `signal-rules.md`, "Time bands" |
| **Never leave a voicemail**, no recordings, no selling on the call | `call_script.md` |
| Email only to addresses published on the business's own website; never guessed, pattern-built or purchased | `lookup-automation.md`, 2026-10-29 "Outreach email address" |
| Opening-line facts only from the own website and TDLR, each with its source URL; no fact without a source; no review text; social media by hand only | `lookup-automation.md`, 2026-10-29 "Facts for a personal opening line" |
| Only `verified` businesses (identity confirmed on the own site) go to outreach | `lookup-automation.md`, "Identity label" |
| LLC and Inc only, each confirmed by hand in the Comptroller search before any email | `data-sources.md`; `calibration-plan.md` |
| A phone that reaches a named person's personal line is treated as a wrong number | `lookup-automation.md`, "Known limits" |
| Open map dataset phones are marked `phone_unconfirmed` and checked on the site before dialling | `call-list-plan.md`, "Month-1 list v2" |
| The website reader obeys robots.txt and sends an honest User-Agent with the contact address admin@optomate.co.uk | `lookup-automation.md`, "Own-site reader" and 2026-10-29 "User-Agent contact address" |
| Data stays on Ahmed's Mac; `data/` is Git-ignored, so GitHub holds code only | `data-sources.md`, "Rules applied"; `signal-rules.md`, "Data origin" |
| Retention: 6 months after last contact; the do-not-contact list is kept permanently with minimum data, only to honour objections | Fixed fact (not yet in a decision file) |
| Named owner/manager: found by code on the own site only, kept in `data/` only, never in an email; the research model reads page text only after the names are removed; outreach CSVs older than 6 months are deleted at the start of each weekly run | `docs/agents/sales-researcher.md`, hard rules 6, 7 and 10, Step 1 |

### Risks and how they are handled

| Risk | Handling |
|---|---|
| The licence holder name is kept without a current use | Removal decided 2026-10-29 (`data-sources.md`); **code change pending** |
| Gmail-type addresses shown as a business contact may be a person's own address | **TO CONFIRM with adviser** before any is used (`lookup-automation.md`, 2026-10-29) |
| An LLP or LP may be a small partnership of individuals | LP removed from the flag; **LLP and LP treatment: TO CONFIRM with adviser** (`data-sources.md`, change log) |

**Result:** the balance favours the processing. The data is low-risk business contact data, the real purpose and the
notice are given at first contact, contact is rare and easy to stop, and there is no significant effect.

---

## Open items

1. **TO CONFIRM:** the SuperSend transfer safeguard, from SuperSend's DPA (UK Data Bridge, IDTA or UK Addendum).
2. **TO CONFIRM:** whether Optomate LTD must pay the ICO data protection fee (ICO self-assessment).
3. **TO CONFIRM:** the public URL where the full notice will be hosted (`[NOTICE_URL]` in the call script and notice).
4. **TO CONFIRM:** the transfer safeguards for Google (Places API queries) and Stripe, if their processing takes place
   outside the UK.
5. **TO CONFIRM with adviser:** Gmail-type addresses shown as a business contact.
6. **TO CONFIRM with adviser:** LLP and LP treatment.

**Resolved on 2026-10-29:** how the notice reaches a business at first contact (decisions 1–3); where outreach email
addresses come from (decision 4); whether to name Foursquare as a source (decision 8: it is not named); the wording of
Optomate's service (decision 1); the form message wording (decision 3); the research-call purpose risk (decision 1).

---

## Decision

**Legitimate interests is the appropriate lawful basis.** Conditions before the first call: the notice URL is live
(open item 3) and the licence holder column is removed (pending code change). Before the first email: the SuperSend
safeguard is confirmed (open item 1).

- Assessed by: Ahmed, for Optomate LTD, 2026-10-29 (draft).
- **Review date: 2027-04-29**, or sooner if the data, sources, recipients or contact method change.
