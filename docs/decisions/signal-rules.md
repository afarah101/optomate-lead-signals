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

- **One honest research inquiry per business per calendar month.** A second form in the same month is rejected.
- `form_reply_hours` = hours from `sent_at_local` to `first_reply_at_local` (first human reply), to one decimal place. The code
  computes it in Dallas time and handles daylight-saving changes.
- **No reply within 72 hours** (no `first_reply_at_local`, or a reply after more than 72.0 hours) means `no_reply`.
- A row is rejected if the reply is before the send time, if a timestamp is not `YYYY-MM-DD HH:MM`, or if a filled-in
  `form_reply_hours` disagrees with the computed value.

## Rejected rows

The loaders never drop rows silently. Every rejected row comes back with its CSV line number, the row and the reason.
