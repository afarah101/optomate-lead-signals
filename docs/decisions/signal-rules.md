# Contact-signal rules (written 2026-10-27, before the code)

These rules define the first-party contact signals in `src/signals/contact_signals.py`.
The code follows this file. If they disagree, the code is wrong.

## Data origin

- Every signal here is **first-party data**: Optomate staff collect it by making one call or sending one form to a business.
- **No Google review content is stored anywhere**: not in the logs, templates, code or outputs.
- Logs that hold real businesses live in `data/`, which Git ignores. The templates in `docs/templates/` hold headers only.

## Calls

**Result values** (column `result`):

| Value | Meaning | Counts in rates? |
|---|---|---|
| `answered_by_person` | A person picked up | Yes, valid |
| `voicemail` | A voicemail or answering system took the call | Yes, valid and missed |
| `no_answer` | It rang out with no pickup and no voicemail | Yes, valid and missed |
| `invalid` | Busy signal or dead line | **No, excluded from rates** |

Any other value is rejected.

**Time bands** (Dallas local time, America/Chicago; both ends included):

| Band | Window |
|---|---|
| `morning` | 10:00–12:00 |
| `afternoon` | 14:00–16:30 |
| `evening` | 18:00–19:30 |

A row is rejected if `time_band` is not one of these, or if `call_time_local` falls outside its stated band.

**Frequency:** at most **one call per business (licence_number) per calendar month**. Every call counts, including
`invalid` ones. If a log has two calls for one business in the same month, the earlier one is kept and the later one is rejected.

**Do-not-contact:** a business that asks not to be called gets `stop_requested = yes`. It then goes on the do-not-contact list
**forever**. Any later call to that business is rejected. `stop_requested` must be `yes` or `no`.
A stop request is honoured **even on a rejected row**, because the person still asked. The rejection reason says so, and
`do_not_contact_list` accepts rejected rows as well as accepted ones.

**Voicemail greeting** (`voicemail_greeting_present`, `yes` or `no`): recorded on **evening calls only**.
- Non-evening calls: the column must be blank. Otherwise the row is rejected.
- Evening calls with `voicemail` or `no_answer`: `yes` or `no` is required.
- Evening calls with `answered_by_person` or `invalid`: may be blank, because no greeting was heard.

**Monthly missed rate** = (`voicemail` + `no_answer`) / valid calls, per business and month.
If a business has no valid calls that month, there is no rate (empty).
Because of the one-call rule, a single business's monthly rate is always 0, 1 or empty.

**Trend** compares this month's missed rate with the previous calendar month's:
`rising` (higher), `falling` (lower), `flat` (equal), `new` (no rate for the previous month).
If there is no rate this month, the trend is empty.

## Forms

- **One research message per business per calendar month.** A second form in the same month is rejected.
- **The form message names Optomate, asks the same real question as the call ("Do you take emergency calls after
  6pm?"), and includes the privacy notice URL.** No pretend customer inquiries (rule change 2026-10-29).
- `form_reply_hours` = hours from `sent_at_local` to `first_reply_at_local` (first human reply), to one decimal place. The code
  computes it in Dallas time and handles daylight-saving changes.
- **No reply within 72 hours** (no `first_reply_at_local`, or a reply after more than 72.0 hours) means `no_reply`.
- A row is rejected if the reply is before the send time, if a timestamp is not `YYYY-MM-DD HH:MM`, or if a filled-in
  `form_reply_hours` disagrees with the computed value.

## Notice timing (added 2026-10-29)

- **An answered call or a form message is the first contact**, and it gives the privacy notice URL
  (`docs/templates/call_script.md`; the form rule above).
- **An unanswered call is not a contact.** No voicemail or other message is ever left.
- **The first email carries the notice** and is sent **within 1 month of collecting the data**.

## Rejected rows

The loaders never drop rows silently. Every rejected row comes back with its CSV line number, the row and the reason.

## Month-1 composite score (appended 2026-10-27, before any data or code)

A score from 0 to 3 per business per month, built from one `summarise_contact_signals()` row:

| Signal | Point |
|---|---|
| Missed call: the month's call was `voicemail` or `no_answer`, in any band | +1 |
| `voicemail_greeting_present = no` | +1 |
| Form: `form_reply_hours` is `no_reply` or greater than 24 | +1 |

**Bands:** `hot` = 2 or 3 points. `cold` = 0 points. `middle` = 1 point, **excluded from the calibration test**.

**The 24-hour cut-off is a judgment**, recorded here before any data was collected. It is not fitted to results.

**From month 3:** add the rolling 3-month missed rate. This is not built yet.

A missing signal gives no point: no form sent that month, no greeting heard, or no valid call.
**Eligible for the test:** the business is not on the do-not-contact list, its `entity_flag` is `likely_corporate`, it
has at least one valid (non-`invalid`) call that month, **and a form was sent to it that month at least 72 hours before
the ranking runs** (Dallas time, real elapsed hours).
Every eligible row is marked `manual_entity_check = required`.

*Amended 2026-10-27, before any selection:*
1. A form must have been sent that month, so that `cold` (0 points) means "signals measured and none missed", not
   "no form data".
2. That form must be at least 72 hours old when the ranking runs, so that `no_reply` is final and not "still waiting".

## Rule changes

| Date | Old rule | New rule | Reason |
|---|---|---|---|
| 2026-10-29 | Call opening "this is a short research call. I am not selling anything", question about opening hours, caller names the company only if asked | The opening names Ahmed and Optomate, a UK company, states the purpose (studying how HVAC firms handle calls) and that a call-answering service may be offered later. One real question: "Do you take emergency calls after 6pm?" The caller gives the notice URL. Never leave a voicemail (`docs/templates/call_script.md`) | The call must state its real purpose (`docs/compliance/legitimate-interests-assessment.md`) |
| 2026-10-29 | "One honest research inquiry" per month, wording not set | The form message names Optomate, asks the same real question and includes the notice URL. No pretend customer inquiries | The same transparency reason |
| 2026-10-29 | No rule on when the privacy notice is given | An answered call or a form message is the first contact and gives the notice URL. An unanswered call is not a contact. The first email carries the notice and goes within 1 month of collecting the data | UK GDPR Article 14(3): notice by the first contact, and within one month |
