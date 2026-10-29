# Research call script

**Rules before you dial**
- Check the do-not-contact list. If the business is on it, do not call.
- One call per business per calendar month. Call only inside a time band (Dallas time):
  morning 10:00–12:00, afternoon 14:00–16:30, evening 18:00–19:30.
- **Do not record the call.**
- **Never leave a voicemail.**
- Do not sell on the call. The opening says what Optomate may offer later; say nothing more about it unless asked.

## If a person answers

An answered call is the first contact, so it always gives the privacy notice URL (`signal-rules.md`, "Notice timing").

1. **Opening (say exactly):**
   "Hello, this is Ahmed from Optomate, a UK company. We study how HVAC firms handle calls, and we may later offer a
   call-answering service."
2. **The one question:**
   "Do you take emergency calls after 6pm?"
3. **Notice (say exactly):**
   "Our privacy notice is at [NOTICE_URL]."
4. **Close:**
   "Thank you, that's all I needed. Have a good day."
   Hang up.

**If they ask more about Optomate:** answer truthfully and briefly. Do not pitch.

**If they ask not to be called again:** say "Of course, I'll make sure you're not called again. Sorry to bother you."
End the call. Log `stop_requested = yes`. The business stays on the do-not-contact list forever.

## If no person answers

**Never leave a voicemail or any message.** Hang up and log the result. An unanswered call is not a contact.
- Voicemail or answering system: `voicemail`
- Rings out: `no_answer`
- Busy or dead line: `invalid`

On **evening** calls with `voicemail` or `no_answer`, log `voicemail_greeting_present` as `yes` or `no`.
Leave it blank on all other calls.

## Logging

Fill one row in a copy of `docs/templates/call_log_template.csv` saved under `data/`, never under `docs/`.
Use `call_date` as `YYYY-MM-DD` and `call_time_local` as `HH:MM`. Put your initials in `caller_initials`.
Keep `notes` short and factual. Do not write personal details about the person you spoke to.
