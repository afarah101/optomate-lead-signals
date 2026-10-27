# Calibration plan: do hot leads reply more often? (written 2026-10-27, before selection)

## Hypothesis

Hot leads reply to outreach more often than cold leads.

## Groups

- **15 hot** and **15 cold** businesses, chosen at random from **eligible** rows only.
  Bands and eligibility come from the Month-1 composite score in `signal-rules.md`. Eligible means: not on the
  do-not-contact list, `entity_flag = likely_corporate`, a valid call that month, and a form sent that month
  **at least 72 hours before the ranking runs**.
- **Middle leads (1 point) never enter a group.** If either band has fewer than 15 eligible rows, selection stops with
  an error that gives the counts. No group is ever filled up with other leads.
- **Fixed seed: `20261027`.** It is recorded here before selection and passed to
  `select_calibration_groups(ranked_rows, seed=20261027)`.
- The selector sorts candidates by licence number and draws with `random.Random(seed).random()`. Python promises that
  output stays the same across versions, so the same seed and the same eligible rows always give the same groups.
  Hot is drawn first, then cold.
- Record here after selection: the run date, the Python version, and the 30 selected licence numbers.
- Before any message is sent: confirm each selected business by hand in the Texas Comptroller Taxable Entity Search
  (`manual_entity_check = required`), and check the do-not-contact list again on the day of sending.

## Metric

**Reply rate within 14 days of sending** = businesses with a human reply within 14 days / businesses messaged, per group.
**Auto-replies do not count.**

## Pass rule (directional)

The test passes when **both** are true:
1. Hot reply rate ≥ 2 × cold reply rate.
2. At least **3 hot replies**.

If cold has 0 replies, rule 1 holds automatically, so rule 2 decides.

## What this test can and cannot show

**15 vs 15 gives a direction, not statistical proof.** With groups this small, chance alone can produce a 2× gap.
Proof needs a larger repeat test, sized in advance from the effect seen here.

## Changing the rules

**Rules cannot change after selection.** Any change must be logged below with the old rule, the new rule and the reason.

| Date | Old rule | New rule | Reason |
|---|---|---|---|
| 2026-10-27 (before selection) | Eligible needs no form | Eligible needs a form sent that month | Without it, `cold` could mean "no form data" instead of "replied fast" |
| 2026-10-27 (before selection) | Any form sent that month counts | The form must be sent at least 72 hours before the ranking runs | A form under 72 hours old with no reply reads as `no_reply` too early |
