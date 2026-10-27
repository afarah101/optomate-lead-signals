# Research call script

**Rules before you dial**
- Check the do-not-contact list. If the business is on it, do not call.
- One call per business per calendar month. Call only inside a time band (Dallas time):
  morning 10:00–12:00, afternoon 14:00–16:30, evening 18:00–19:30.
- **Do not record the call.**
- Do not name or describe Optomate's services. Do not sell anything.

## If a person answers

1. **Opening (say exactly):**
   "Hello, this is a short research call. I am not selling anything."
2. **The one question:**
   "Could you tell me your opening hours, please?"
3. **Close:**
   "Thank you, that's all I needed. Have a good day."
   Hang up.

**If they ask who is calling:** give your first name and the company name truthfully, and say it is a short research
call. Do not describe services.

**If they ask not to be called again:** say "Of course, I'll make sure you're not called again. Sorry to bother you."
End the call. Log `stop_requested = yes`. The business stays on the do-not-contact list forever.

## If no person answers

Do not leave a message. Hang up and log the result.
- Voicemail or answering system: `voicemail`
- Rings out: `no_answer`
- Busy or dead line: `invalid`

On **evening** calls with `voicemail` or `no_answer`, log `voicemail_greeting_present` as `yes` or `no`.
Leave it blank on all other calls.

## Logging

Fill one row in a copy of `docs/templates/call_log_template.csv` saved under `data/`, never under `docs/`.
Use `call_date` as `YYYY-MM-DD` and `call_time_local` as `HH:MM`. Put your initials in `caller_initials`.
Keep `notes` short and factual. Do not write personal details about the person you spoke to.
