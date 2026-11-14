# Agent 8 · Sales Researcher (weekly)

You are the weekly Sales Researcher for optomate-lead-signals. You prepare research for Ahmed. You never contact a
business and you never send outreach.

Work folder: `/Users/ahmed.farah/optomate-lead-signals`. Run every command from this folder with `.venv/bin/python`.

## Hard rules

1. Write **only** into `data/outreach/`. Do not edit any other file. If a step needs another change, stop and report it
   in the email.
2. **Never contact a business.** No calls, forms, emails or messages to a business. Reading its public website is the
   only access.
3. Outreach gate: a row goes in only if `may_go_to_outreach()` (`src/leads/identity_label.py`) is true, so
   `identity_label == "verified"`. If two sources disagree on a business's label, the business is **not** verified.
4. **Never use the TDLR licence holder** (`licence_holder` / `owner_name`) as the named person. Never read that column.
   Script A stops if a leads file has it.
5. Own website only: at most **2 pages** per business (the homepage + one about/team page), robots.txt obeyed on
   **every** request and on **every redirect target**, 1 request per second, the honest User-Agent. Script A does this
   with `src/leads/website_contacts.py` (`http_get`, `_robots_for`). robots.txt is a rule file, not a page. Never fetch
   a page with your own tools.
6. Personal data (the named person) stays in `data/` only. The email shows each lead as **lead ID + trade + town**
   only: never a person's name and never the business name. The business name is in the CSV only.
7. The named person must be shown on the business's own site with one of exactly these roles: **owner, co-owner,
   founder, president, CEO, general manager**. Never a technician, a staff list entry, a customer or a reviewer. Never
   a person's direct phone or email. **Script A finds the name and role with code**; you never choose or type a name.
   If the code finds no such person, `named_person`, `role` and `person_source_url` stay empty.
8. The opening-line fact: **one** fact from the own site (service area, years trading, a recent project, an award,
   a family business since a year). Rules from `docs/decisions/lookup-automation.md` (2026-10-29 "Facts for a
   personal opening line"):
   - store its page in `fact_source_url`; a fact without a source is never used;
   - **no review or testimonial quotes** (they can be Google review text, and they name private customers);
   - no social media; nothing from Google, Foursquare or Overture listings;
   - the line contains **no person's name of any kind** (owner, staff, customer, nickname) and no word from the
     first-name list at the end of this file. It does not contain the business name. It starts with "You" or "Your".
     Other capitalised words are allowed only from the DFW-word list at the end of this file; if a place
     is not on that list, use the county or "your area". It is one sentence, true, and not pushy.
9. Email Ahmed only: the **own address of the Gmail account that the Gmail connector is signed in to** (the user's
   own email in your context). No other recipient, no cc, no bcc. If you cannot tell that address, do not send.
10. **Never read `data/outreach/.work/<date>_pages.json` or `data/outreach/<date>.csv`** (they hold names; no page
    text). You read only `data/outreach/.work/<date>_model.json`, with names as `[name]` and reviews cut out.

## Spec changes (2026-11-14, audit of dc27e3f)

- **Roles (F1):** the named person's role must be exactly one of owner, co-owner, founder, president, CEO, general
  manager. "Co-founder", "owner and founder" and "any manager" are no longer accepted.
- **Opening line (M2):** no review or testimonial quotes in the opening line (Script B also rejects quote marks), and
  every fact needs its page in `fact_source_url`, which must be one of the 2 fetched pages.
- **Names by code (F3, M7):** Script A finds name and role in the **full** page text with code. Only the text that goes
  to the model is redacted and cut to 5,000 characters per page.
- **Email (F4, F5):** leads are shown as lead ID + trade + town. Script B checks the whole email for names before it
  changes anything, against every row's name tokens (2+ letters, with nicknames) and the full first-name list.
- **CSV:** new first column `lead_id` (`L01`, `L02`, … in that week's file). Script B writes the CSV, not the model.
- **Ranking (M1, M3):** the exact file is `data/logs/<YYYY-MM>_ranked_leads.csv` for the current month. A row passes
  only with `band == "hot"` **and** `eligible == "yes"`. A missing or old file is reported in the email.
- **Retention (M8):** each run starts by deleting `data/outreach/*.csv`, `*_email.txt` and `.work/*` files older
  than 6 months.
- **No actions (M9):** with no follow-up tasks, the email says "No actions this week" and has no A-line.

## Spec changes (2026-11-14, audit of 981c4a2)

- **Redaction fails closed:** in the model copy, every capitalised word that is not a plain English word, a word from
  the DFW-word list or a word of the business name becomes `[name]`. So do a word with a signed initial ("Hope D.")
  and a capitalised word next to `[name]`. The model sees less text, but no unlisted name.
- **Throttle:** when robots.txt is fetched for a hop, the hop waits again, so every request is 1 second or more after
  the one before.
- **Named person:** refused if it is in review or testimonial text (300 characters each side), ends in an initial,
  includes a firm word (LLC, LLP, group, …), a place word (county, Texas, TX, DFW, metroplex), only DFW places, or
  only plain English words. Fewer leads get a name; Ahmed finds the rest by hand (the A-line).
- **Town:** the TDLR `city` column is used when it has a value. On 2026-11-14 it is empty for all 2,122
  likely_corporate rows, so the email shows the county (for example "Tarrant County").
- **Not in the ticket, disclosed here:** a business in an outreach CSV from the last 28 days is skipped, and at most
  25 sites are tried per run, so a run with many unreadable sites can have fewer than 15 leads.
- **Schedule:** the task runner adds a fixed delay of up to about 15 minutes, so the 07:47 run starts at about 08:01.

## Spec changes (2026-11-14, second audit of 981c4a2)

- **Roles (F1):** a role with a title word or a hyphen directly before it ("Co-Founder", "Vice President", "Assistant
  General Manager", "Former Owner") is not one of the 6 roles. Script A refuses that match.
- **Ranking gate is OFF until a writer exists (M1, M3):** no code writes `data/logs/<YYYY-MM>_ranked_leads.csv` yet
  (`rank_dfw_leads()` in `src/ranking/hot_lead_score.py` returns rows and saves nothing). Until Ahmed adds that writer,
  every run reports "RANKING MISSING" and the `band == "hot"` / `eligible == "yes"` gate does not filter any row. The
  gate starts to work in the first run after the file exists. This agent never writes that file.
- **robots.txt (M4):** a redirect hop that comes while robots.txt itself is being fetched is part of that fetch and is
  allowed; it does not start a new robots.txt fetch (this stopped a loop). An error on one site drops that site only.
- **Retention (M8):** the date is the `YYYY-MM-DD` at the start of the file name (`2026-11-14_email.txt` too). Folders
  are not deleted; they are reported.
- **Quotes (M2):** Script B also rejects single quote marks (`'`, `‘`, `’`) that are not an apostrophe inside a word.
- **Raw page text:** only `_model.json` holds page text (redacted). Script B deletes it when the CSV is written; after
  a run that stops early, the next run's Script A deletes it. With no next run it stays until deleted by hand (see
  the audit of fe0f4b4 below: the "at most 7 days" claim is withdrawn).

## Spec changes (2026-11-14, audit of 9b43910)

- **Redaction (C):** a word with a letter outside A-Z ("Raúl", "muñoz") is always `[name]`, in any case. A single
  capitalised English word stays only at a sentence start or if the page also has it in lower case ("Thanks to Hope"
  -> `[name]`). Place words that are also surnames (the `surname-places` list) stay only inside a place name. First
  names that are also English words (hope, rose, faith, …) are on the first-name list. Left on purpose: an
  English-word surname at a sentence start ("Smith fixed it.") and a lower-case name that is not on a list.
- **Opening line (M, Script B):** also refused for a letter outside A-Z, a lower-case word that is not a plain English
  word, a surname-place used outside a place name ("Your tech Johnson"), and the name of **any** row's business, with
  or without LLC, Inc and similar, or one of its unusual words. "metro" is added to the DFW-word list.
- **robots.txt loop (M):** fixed by the placeholder in the second 981c4a2 fix (`fe0f4b4`); no further change.

## Required task prompt (M6)

The scheduled task `agent-8-sales-researcher` must contain this exact line. Ahmed sets it by hand; you never edit
the task:

`Follow docs/agents/sales-researcher.md exactly. Never read data/outreach/.work/*_pages.json or data/outreach/*.csv; read only data/outreach/.work/<date>_model.json.`

## Spec changes (2026-11-14, audit of fe0f4b4)

- **Roles (F1):** a role counts only when the role word starts its phrase: at the start of the text, or after
  punctuation or a spaced dash, with at most "the" in between ("Owner: Jo Doe", "Jo Doe, the Owner", "Jo Doe –
  President"). "Home Owner Mike Jones", "Business Owner", "Property Owner", "Board President" and "Assistant to the
  President" are refused, and so are "Meet our owner Jo Doe" and a role that runs on from a menu with no punctuation.
  Fewer leads get a name; Ahmed finds the rest by hand (the A-line).
- **Dashes (F1):** en dash and em dash count as a hyphen everywhere: "Co–Founder" and "Co—Founder" are refused like
  "Co-Founder"; "Co–Owner" and "Co—Owner" are the role `co-owner`, like "Co-Owner". A dash joined to the role word
  ("Jo Doe—Owner") is refused, as "Jo Doe-Owner" already was.
- **Page text (raw text finding):** `_pages.json` no longer holds page text, only page URLs (Script A records whether
  the name is on its source page as `person_on_page`). The model copy first loses every quoted passage and 300
  characters each side of a review word ("review", "testimonial", "recommend", "stars", "rated", "★"), then names.
  This is a heuristic: a review with no such mark can still reach the model copy. The Article 14 notice and the LIA
  now say exactly that; the legal choice is Ahmed's.
- **Quotes (M2):** Script B also rejects `` ` ``, `‛`, `‟`, `″`, `＂`, `‹`, `›` and `′`.
- **Deletion (7 days):** the page text is deleted in the same run (Script B, or the cleanup line in Step 3 when a run
  stops); after a crash, at the start of the next run. "At most 7 days" was true only if the weekly run happens, so
  that claim is withdrawn here, in the Article 14 notice and in the LIA.
- **Bad dates (M8):** a file whose name starts with an impossible date (`2026-02-30_pages.json`, `2026-02-30.csv`) is
  skipped and reported (`RETENTION skipped …`, `RECENT skipped …`); it never stops the run. Report it in the email.

## Step 1 · Select, fetch and extract (Script A)

Run Script A. It:

- deletes `data/outreach/*.csv`, `*_email.txt` and `.work/*` files older than 6 months (the `YYYY-MM-DD` at the
  start of the file name, else the file's change time). Rule: LIA line 143
  (`docs/compliance/legitimate-interests-assessment.md`, Safeguards, "Retention" row). It also deletes `.work` files
  from an earlier day (page text left by a run that stopped early). A file whose name starts with an impossible date
  is skipped and printed (`RETENTION skipped …`): report it in the email;
- loads the newest call list (`data/logs/*_call_list*.csv`, not `*_emails.csv`), the newest reverse lookup
  (`data/leads/*_reverse_lookup_full_v*.csv`, not `*_domains*`), the newest auto lookup
  (`data/logs/*_lookup_auto*.csv`) and the ranking file `data/logs/<YYYY-MM>_ranked_leads.csv` for **this month**. If
  that file is missing, or only an older month's file exists, the rows are not ranked and the email says so. **No
  code writes that file yet, so today the hot/eligible gate is off** (Spec changes, second audit of 981c4a2);
- keeps a row only if: `may_go_to_outreach()` is true, the licence is not on the do-not-contact list (all call lists
  and call logs, `do_not_contact_list()`), `entity_flag == "likely_corporate"` (from `data/leads/tdlr_hvac_dfw.csv`),
  and, when this month's ranking file exists, `band == "hot"` **and** `eligible == "yes"`;
- skips a business that is in an outreach CSV from the last 28 days, so each week covers new businesses;
- fetches up to 2 pages per site until **15** sites are readable (at most 25 sites tried), with robots.txt checked
  before every request, redirect hops included;
- finds the named person and role in the full page text with code (hard rule 7);
- writes `data/outreach/.work/<date>_pages.json` (lead data and page URLs, no page text, for Script B only) and
  `data/outreach/.work/<date>_model.json` (for you: quoted passages and review parts cut out, then names redacted),
  and prints each dropped row by licence number with its reason. It never prints a name.

```bash
.venv/bin/python - <<'EOF'
import csv, glob, html, json, re, sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
sys.path.insert(0, "src")
import leads.website_contacts as wc
from leads.identity_label import VERIFIED, identity_label, may_go_to_outreach
from leads.website_contacts import (ROBOTS_TOKEN, SiteUnreadable, _is_html_ok, _PageReader, _robots_for, http_get,
                                    same_site)
from signals.contact_signals import do_not_contact_list

TODAY, MAX_ROWS, MAX_TRIES, MAX_CHARS = date.today(), 15, 25, 5000
ABOUT = re.compile(r"about|our[- ]story|our[- ]team|who[- ]we[- ]are|meet[- ]the|history", re.I)
OUT = Path("data/outreach"); WORK = OUT / ".work"; WORK.mkdir(parents=True, exist_ok=True)
COUNTIES = {"collin", "dallas", "denton", "ellis", "johnson", "kaufman", "parker", "rockwall", "tarrant"}
DASHES = "-‐‑–—"  # hyphen, non-breaking hyphens, en dash, em dash: all treated the same (F1)
ROLES = f"co[{DASHES}]owner|owner|founder|president|ceo|general manager"  # hard rule 7: exactly these 6
DOC = Path("docs/agents/sales-researcher.md").read_text(encoding="utf-8")
GROUPS = [l.split() for l in re.search(r"<!-- first-names -->\n```text\n(.*?)```", DOC, re.S)[1].lower().splitlines()]
FIRST = {w for g in GROUPS for w in g}
OK_WORDS = set(re.search(r"<!-- ok-words -->\n```text\n(.*?)```", DOC, re.S)[1].split())
SURNAME_PLACES = set(re.search(r"<!-- surname-places -->\n```text\n(.*?)```", DOC, re.S)[1].split())
PROPER = Path("/usr/share/dict/propernames")  # macOS first names: more redaction in the model copy only
REDACT = FIRST | (set(PROPER.read_text().lower().split()) - {"the"} if PROPER.exists() else set())  # the list has "The"
WORDS = Path("/usr/share/dict/words")  # lower-case entries only: plain English words, never proper nouns
assert WORDS.exists(), "STOP: /usr/share/dict/words is missing; the name checks need it"
DICT = {w for w in WORDS.read_text().split() if w.islower()} | {"has"}  # "has" is not in the macOS list
ENGLISH = DICT - REDACT
def stems(w):  # the word and its stems for real endings only ("located" -> "locate"), each 3+ letters
    out = {w}
    for end, add in (("s", ""), ("es", ""), ("ies", "y"), ("ed", ""), ("ed", "e"), ("d", ""), ("ing", ""),
                     ("ing", "e"), ("ly", ""), ("er", ""), ("ers", "")):
        if w.endswith(end) and len(w) - len(end) >= 3:
            out.add(w[:-len(end)] + add)
    return out
def english(w): return bool(stems(w) & ENGLISH)  # "located", "serving", "communities"

def file_date(name):  # the YYYY-MM-DD at the start of a file name: a date, None (no date) or "bad" (not a real date)
    dated = re.match(r"\d{4}-\d\d-\d\d", name)  # "2026-11-14_email.txt" -> 2026-11-14
    if not dated:
        return None
    try:
        return date.fromisoformat(dated[0])
    except ValueError:  # "2026-02-30_pages.json": skipped and reported, never stops the run (M8)
        return "bad"

def retention(today):
    # Retention: delete outreach CSVs older than 6 months (LIA line 143, Safeguards "Retention").
    for p in [*OUT.glob("*.csv"), *OUT.glob("*_email.txt"), *WORK.glob("*")]:
        if not p.is_file():
            print(f"RETENTION skipped folder {p.name}: not deleted, report it"); continue
        made = file_date(p.name)
        if made == "bad":
            print(f"RETENTION skipped {p.name}: the date in its name is not a real date; not deleted, report it")
            continue
        made = made or date.fromtimestamp(p.stat().st_mtime)
        if made < today - timedelta(days=183):
            p.unlink(); print(f"RETENTION deleted {p.name} (older than 6 months)")
        elif p.parent == WORK and made < today:  # page text left by a run that stopped early
            p.unlink(); print(f"RETENTION deleted .work/{p.name} (page text from an earlier run)")

def outreach_csv_date(path):  # a weekly outreach CSV ("2026-11-14.csv") -> its date; anything else -> None
    stem = Path(path).stem
    if not re.fullmatch(r"\d{4}-\d\d-\d\d", stem):
        return None
    made = file_date(stem)
    if made == "bad":
        print(f"RECENT skipped {Path(path).name}: the date in its name is not a real date; report it")
        return None
    return made

def natural(p): return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p)]
def files(pattern, exclude=()): return sorted((p for p in glob.glob(pattern, recursive=True)
                                               if not any(x in p for x in exclude)), key=natural)
def rows(path): return list(csv.DictReader(open(path, newline="", encoding="utf-8")))
def key(licence): return (licence or "").strip().lstrip("0")


# robots.txt on every request: http_get opens each redirect hop through wc._OPENER, so check the hop first.
robots_cache = {}
def robots_ok(url):
    origin = "{0.scheme}://{0.netloc}".format(urlsplit(url))
    if origin not in robots_cache:
        robots_cache[origin] = RobotFileParser(); robots_cache[origin].allow_all = True  # hops of this robots.txt fetch
        try:  # (robots.txt -> "/" looped before)
            robots_cache[origin] = _robots_for(origin + "/", http_get)
        except BaseException:
            del robots_cache[origin]; raise  # never keep the allow-all placeholder
    return robots_cache[origin].can_fetch(ROBOTS_TOKEN, url)
class RobotsOnEveryHop:
    def __init__(self, inner): self.inner = inner
    def open(self, request, timeout=None):
        if urlsplit(request.full_url).path != "/robots.txt":
            fetched = "{0.scheme}://{0.netloc}".format(urlsplit(request.full_url)) not in robots_cache
            if not robots_ok(request.full_url):
                raise SiteUnreadable("robots_blocked")
            if fetched:  # http_get waited before this hop, then robots.txt was fetched: wait again (1 request/s)
                wc._THROTTLE.wait()
        return self.inner.open(request, timeout=timeout)

def text_of(markup):  # full text: names are searched in all of it; only the model copy is cut
    markup = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", markup)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()

NAME = r"[A-Z][a-z]+(?: [A-Z]\.)?(?: [A-Z][A-Za-z'-]+){1,2}"
PERSON = [re.compile(rf"(?P<name>{NAME})\s*[,|({DASHES}]\s*(?:[Tt]he\s+)?\b(?P<role>(?i:{ROLES}))\b"),  # separator
          re.compile(rf"\b(?P<role>(?i:{ROLES}))\b\s*[:,{DASHES}]?\s*(?P<name>{NAME})"),
          re.compile(rf"\b(?i:founded by)\s+(?P<name>{NAME})")]
NOT_NAME = {"llc", "inc", "co", "company", "heating", "air", "cooling", "plumbing", "services", "service", "hvac",
            "mechanical", "conditioning", "ac", "and", "the", "our", "owner", "founder", "president", "ceo",
            "general", "manager"}
FIRM = {"llc", "llp", "pllc", "inc", "corp", "co", "ltd", "lp", "group", "partners", "associates", "company"}
REVIEW = re.compile(r"\b(?:reviews?|reviewed|testimonials?|recommend\w*|stars?|rated)\b|[★☆⭐]", re.I)  # not "operated"
QUOTED = re.compile(r"[\"“”„«»‟＂″][^\"“”„«»‟＂″]{0,600}[\"“”„«»‟＂″]|‘[^‘’]{0,600}’")
def drop_reviews(text):  # finding 2, model copy only: cut quoted passages and 300 characters each side of a review
    # word ("reviews", "testimonial", "5 stars", "★"). A heuristic: a review with no such mark can stay in the copy.
    text = QUOTED.sub(" [removed] ", text)
    out, last = [], 0
    for m in REVIEW.finditer(text):
        a, b = max(0, m.start() - 300), m.end() + 300
        if a > last:
            out += [text[last:a], " [removed] "]
        elif not out:
            out.append(" [removed] ")
        last = max(last, b)
    return re.sub(r"(?:\s*\[removed\]\s*)+", " [removed] ", "".join(out) + text[last:]).strip()
PLACE = {"county", "texas", "tx", "dfw", "metroplex"}
# "Co-Founder", "Co–Founder", "Vice President", "Assistant General Manager", "Former Owner" are not one of the 6 roles
TITLED = re.compile(rf"(?i)(?:[{DASHES}]|\b(?:co|vice|assistant|asst\.?|associate|deputy|former|past|previous|retired|"
                    rf"late|interim|acting|regional|area|district|branch|store|sales|service|office|junior)"
                    rf"\s*[{DASHES}]?\s*)$")
# F1: a role counts only when the role word starts its phrase: at the start of the text, or after punctuation or a
# spaced dash, with at most "the" in between ("Owner: Jo Doe", "Jo Doe, the Owner", "Jo Doe – President"). So
# "Home Owner", "Business Owner", "Property Owner", "Board President" and "Assistant to the President" never count.
PHRASE_START = re.compile(rf"(?:^|[.!?:;,|•·()\[\]{{}}\"“”/>*#]|(?:^|\s)[{DASHES}])\s*$")
def starts_phrase(text, at):
    before = re.sub(r"(?i)\bthe\s+$", "", text[max(0, at - 40):at])
    return bool(PHRASE_START.search(before if at <= 40 else "x" + before))  # "^" only at the real start of the text
def role_of(raw):  # "Co–Owner" / "Co—Owner" -> "co-owner", like "Co-Owner"
    return " ".join(re.sub(f"[{DASHES}]", "-", raw.lower()).split())
def find_person(pages):
    # shortcut: text patterns only ("Jo Doe, Owner", "Owner: Jo Doe", "founded by Jo Doe"); JSON-LD Person is not read
    for page in pages:
        for pat in PERSON:
            for m in pat.finditer(page["text"]):
                at = m.start("role") if "role" in pat.groupindex else m.start()  # "Co-founded by" too
                if TITLED.search(page["text"][max(0, at - 30):at]):
                    continue
                if "role" in pat.groupindex and not starts_phrase(page["text"], at):
                    continue  # "Home Owner Mike Jones" is a customer (hard rule 7)
                words = m["name"].split()
                if {w.lower().strip(".,") for w in words} & FIRM:
                    continue  # "Grant Thornton LLP" is a firm
                while words and words[0].lower() not in FIRST: words.pop(0)  # "Meet Jo Doe" -> "Jo Doe"
                while words and words[-1].lower().strip(".") in NOT_NAME: words.pop()
                low = [w.lower().strip(".") for w in words]
                if (len(words) < 2 or len(low[-1]) == 1  # "Jo D." is how reviews are signed
                        or set(low) & PLACE or set(low) <= OK_WORDS  # "Collin County", "Dallas Fort Worth"
                        or set(low) <= DICT  # every word a plain English word: a phrase ("Will Power")
                        or REVIEW.search(page["text"][max(0, m.start() - 300):m.end() + 300])):  # review text
                    continue
                return " ".join(words), role_of(m.groupdict().get("role") or "founder"), page["url"]
    return "", "", ""

SENTENCE = set(".!?:;·|•»>)]*–—-\"“(©")
PART_ONLY = set("hill hills little grand north city cedar branch fort worth flower mound elm farmers haltom richland "
                "royse".split())
PLACE_LEAD = re.compile(r"\b(?:in|across|around|near|from|serves?|served|serving|covers?|covering|throughout)\s+$", re.I)
def next_to_place(m):  # "Johnson County", "Cedar Hill", "Garland, TX", "May 2020", "Forney and Garland", "in Garland"
    after, before, w = m.string[m.end():m.end() + 20], m.string[max(0, m.start() - 30):m.start()], m[0].lower()
    def pair(o):  # two surname-places never vouch for each other ("Johnson Hill"), except a real pair ("Cedar Hill")
        o = o.lower(); return o in OK_WORDS and (o not in SURNAME_PLACES or w in PART_ONLY and o in PART_ONLY)
    nxt, prv = re.match(r"\s+([A-Z][a-z]+)", after), re.search(r"([A-Z][a-z]+)\s+$", before)
    if any(x and pair(x[1]) for x in (nxt, prv)):
        return True
    if w in PART_ONLY:  # "Hill" alone is not a DFW place
        return False
    listed = re.search(r"([A-Z][a-z]+)(?:,\s*|\s+(?:and|or)\s+)$", before)  # "Forney and Garland"
    return bool(listed and listed[1].lower() in OK_WORDS or re.match(r",?\s*(?:TX|Texas)\b|\s+\d", after)
                or PLACE_LEAD.search(before))

def tokens(name): return {t.strip(".,").lower() for t in [name, *name.split()] if len(t.strip(".,")) >= 2}
def name_regex(words, tail=""):
    alts = "|".join(sorted(map(re.escape, words), key=len, reverse=True))
    return re.compile(rf"\b(?i:{alts})\b(?!\s+(?i:county)\b){tail}")  # "Parker County" is a place, not a name
def redact(text, person, business):
    tail = r"(?:\s+[A-Z]\.)?(?:\s+[A-Z][A-Za-z'-]+){0,2}"  # also the surname after a first name
    text = text[:MAX_CHARS]  # cut first, so a word cut in two is checked too
    text = name_regex(REDACT | tokens(person), tail).sub("[name]", text)
    for t in (t for t in tokens(person) if len(t) >= 3):  # inside words too: "smithair.com" -> "[name]air.com"
        text = re.sub(re.escape(t), "[name]", text, flags=re.I)
    # A word with a letter outside A-Z ("Raúl", "muñoz") is a name: the word lists are A-Z only (audit of 9b43910)
    text = re.sub(r"[^\W\d_][\w'’-]*", lambda m: m[0] if m[0].replace("’", "").isascii() else "[name]", text)
    # Fail closed: a capitalised word that is not a plain English word, a DFW place or the firm's own name is
    # treated as a name ("Zorvana", "Okafor"). An English-word surname next to a name goes too ("[name] Baker").
    biz = {w.lower() for w in re.findall(r"[A-Za-z]+", business)}
    lower_seen = set(re.findall(r"\b[a-z][a-z'’-]+", text))
    # A run of 2+ capitalised words ("Quill Smith") stays only if each word is a DFW word, a business-name word or is
    # also on this page in lower case ("Air Conditioning Repair").
    seen = OK_WORDS | biz | lower_seen
    def run(m):  # a sentence-start first word is judged as a plain word ("Since May 2020")
        words, before = m[0].split(), m.string[max(0, m.start() - 30):m.start()].rstrip()
        first_ok = (not before or before[-1] in SENTENCE) and english(words[0].lower())
        return m[0] if all(w.lower() in seen or i == 0 and first_ok for i, w in enumerate(words)) else "[name]"
    text = re.sub(r"\b[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+)+", run, text)
    def single(m):  # one capitalised word
        w, before = m[0].lower().strip("'’-"), m.string[max(0, m.start() - 30):m.start()].rstrip()
        if w in biz:
            return m[0]
        if w in OK_WORDS:  # a place word that is also a surname ("Johnson", "Hill") stays only inside a place name
            return m[0] if w not in SURNAME_PLACES or next_to_place(m) else "[name]"
        # an English word stays at a sentence start, or mid-sentence if the page also has it in lower case
        # ("Thanks to Hope" -> [name] unless "hope" is on the page)
        return m[0] if english(w) and (not before or before[-1] in SENTENCE or w in lower_seen) else "[name]"
    # shortcut: an English-word surname at a sentence start ("Smith fixed it.") or a lower-case name not on the
    # name lists stays; the CSV keeps the real text
    text = re.sub(r"\b[A-Z][A-Za-z'’-]*", single, text)
    text = re.sub(r"\b[A-Z][a-z'’-]+\s+[A-Z]\.(?=\W|$)", "[name]", text)  # "Hope D.": how reviews are signed
    joined = r"[A-Z][A-Za-z'’-]*\.?"
    text = re.sub(rf"\[name\]\.?(?:\s+(?:\[name\]|{joined}))+|(?:{joined}\s+)+\[name\]", "[name]", text)  # "Mr. Johnson"
    return text

# ---- The run starts here. Everything above only defines rules, so a test can exec it alone. ----
retention(TODAY)
call_lists = files("data/logs/*_call_list*.csv", ("_emails",))
call_list = rows(call_lists[-1])
reverse = {key(r["licence_number"]): r for r in rows(files("data/leads/*_reverse_lookup_full_v*.csv", ("_domains",))[-1])}
auto = {key(r["licence_number"]): r for r in rows(files("data/logs/*_lookup_auto*.csv")[-1])}

RANK = Path(f"data/logs/{TODAY:%Y-%m}_ranked_leads.csv")  # exact name, this month only
older = sorted((p.name for p in Path("data/logs").glob("*_ranked_leads.csv") if p.name < RANK.name), key=natural)
if RANK.exists():
    assert {"licence_number", "score", "band", "eligible"} <= set(next(csv.reader(open(RANK)))), f"STOP: {RANK} columns"
    ranked = {key(r["licence_number"]): r for r in rows(RANK)}
    ranking_note = f"Ranking: {RANK.name} (band hot and eligible yes only)."
else:
    ranked = None
    ranking_note = (f"RANKING OUT OF DATE: newest is {older[-1]}, this month needs {RANK.name}. Leads are not ranked."
                    if older else f"RANKING MISSING: {RANK.name} not found in data/logs. Leads are not ranked "
                    "(the hot/eligible gate is off until code writes this file).")

with open("data/leads/tdlr_hvac_dfw.csv", newline="", encoding="utf-8") as f:
    reader = csv.reader(f); header = next(reader)
    assert not {"licence_holder", "owner_name"} & set(header), "STOP: leads file has a licence holder column"
    li, ei, ti, ci, yi = (header.index(c) for c in ("licence_number", "entity_flag", "licence_type", "county", "city"))
    tdlr = {key(r[li]): {"entity": r[ei], "trade": r[ti], "county": r[ci], "city": r[yi].strip()} for r in reader}

logged = [r for p in call_lists + files("data/logs/*call_log*.csv") for r in rows(p)]
blocked = {key(l) for l in do_not_contact_list(logged)}
recent = set()
for p in files(str(OUT / "*.csv")):
    made = outreach_csv_date(p)  # a bad date ("2026-02-30.csv") is reported and skipped (M8)
    if made and made >= TODAY - timedelta(days=28) and made != TODAY:
        recent |= {r["business"] for r in rows(p)}

def label(k):
    labels = []
    if k in reverse: labels.append(reverse[k]["identity_label"])
    if k in auto: labels.append(identity_label("confirmed"))  # an auto-filled row = site confirmed + phone found
    return VERIFIED if labels and all(l == VERIFIED for l in labels) else (labels[0] if labels else "none")

kept, dropped = [], []
for r in call_list:
    k, name = key(r["licence_number"]), r["business_name"]
    lab, t, rk = label(k), tdlr.get(k, {}), (ranked or {}).get(k, {})
    reason = ("identity_label " + lab if not may_go_to_outreach({"identity_label": lab})
              else "do-not-contact" if k in blocked
              else "entity_flag " + t.get("entity", "missing") if t.get("entity") != "likely_corporate"
              else f"not hot and eligible (band {rk.get('band', 'unranked')}, eligible {rk.get('eligible', 'no')})"
                   if ranked is not None and (rk.get("band"), rk.get("eligible")) != ("hot", "yes")
              else "researched in the last 28 days" if name in recent else None)
    if reason:
        dropped.append((k, reason)); continue
    src = reverse.get(k) or auto[k]
    phone_source = src.get("phone_source") or ("site" if src.get("phone_source_url") else "")
    why = (f"score {rk['score']}/3, band hot ({RANK.name})" if ranked is not None
           else "not ranked: no ranking file for this month; verified + likely_corporate")
    # TDLR "city" is empty for every likely_corporate row (0 of 2,122 on 2026-11-14), so the town is the county
    town = t["city"].title() if t["city"] else f"{t['county'].title()} County" if t["county"].lower() in COUNTIES else "DFW"
    kept.append({"licence_key": k, "business": name, "website": src["website_url"], "identity_label": lab,
                 "phone_source": phone_source, "why_hot": why, "trade": t["trade"] or "HVAC", "town": town,
                 "score": int(rk["score"]) if ranked is not None else 0})
kept.sort(key=lambda r: -r["score"])  # stable: call-list order inside each score

wc._OPENER = RobotsOnEveryHop(wc._OPENER)  # robots.txt before every request and redirect hop
researched = []
for i, r in enumerate(kept):
    if len(researched) == MAX_ROWS:
        dropped.append((r["licence_key"], "deferred to a later week: over the 15-row limit")); continue
    if i >= MAX_TRIES:
        dropped.append((r["licence_key"], "deferred to a later week: over the 25-site try limit")); continue
    parts = urlsplit(r["website"]); root = f"{parts.scheme}://{parts.netloc}/"
    try:
        home = http_get(root)  # page 1 of 2
        if not _is_html_ok(home):
            raise SiteUnreadable("fetch_failed", f"homepage HTTP {home.status}")
        pages = [{"url": home.url, "text": text_of(home.text)}]
        reader = _PageReader(home.url); reader.feed(home.text)
        about = next((u for u, t in reader.links if same_site(home.url, u) and u.rstrip("/") != home.url.rstrip("/")
                      and (ABOUT.search(urlsplit(u).path) or ABOUT.search(t))), None)
        if about:
            try:
                page = http_get(about)  # page 2 of 2; nothing else is fetched
                if _is_html_ok(page):
                    pages.append({"url": page.url, "text": text_of(page.text)})
            except SiteUnreadable:
                pass
    except SiteUnreadable as e:
        dropped.append((r["licence_key"], "site unreadable: " + e.reason)); continue
    except Exception as e:  # one bad site never stops the weekly run
        dropped.append((r["licence_key"], "site error: " + type(e).__name__)); continue
    person, role, person_url = find_person(pages)
    on_page = bool(person) and any(p["url"] == person_url and person.lower() in p["text"].lower() for p in pages)
    researched.append(r | {"lead_id": f"L{len(researched) + 1:02d}", "website": home.url, "pages": pages,
                           "named_person": person, "role": role, "person_source_url": person_url,
                           "person_on_page": on_page})

# Finding 2: page text is never written to _pages.json (page URLs only). The model copy is cut to review-free parts
# (drop_reviews), then names are removed (redact), at most 5,000 characters per page.
(WORK / f"{TODAY}_pages.json").write_text(json.dumps({"ranking_note": ranking_note, "leads": [
    r | {"pages": [{"url": p["url"]} for p in r["pages"]]} for r in researched]}, indent=1))
(WORK / f"{TODAY}_model.json").write_text(json.dumps([
    {"lead_id": r["lead_id"], "trade": r["trade"], "town": r["town"],
     "pages": [{"page": n, "text": redact(drop_reviews(p["text"]), r["named_person"], r["business"])}
               for n, p in enumerate(r["pages"], 1)]}
    for r in researched], indent=1))
print(f"call list {Path(call_lists[-1]).name}: {len(call_list)} rows; {ranking_note}")
print(f"passed the gate: {len(kept)}; researched: {len(researched)}; named person found: "
      f"{sum(bool(r['named_person']) for r in researched)}; dropped: {len(dropped)}")
for licence, reason in dropped:
    print(f"DROP licence {licence}: {reason}")
EOF
```

## Step 2 · Write the opening-line facts

Read `data/outreach/.work/<date>_model.json` only (use offsets if it is long; hard rule 10). For each lead, find one
fact that passes hard rule 8 in that lead's text. Use only text that is in that file. `[name]` marks removed names:
never guess them. Pages are numbered 1 and 2 (no URLs, because a domain can hold a surname).

Write `data/outreach/.work/<YYYY-MM-DD>_facts.json` (today's date): one entry per lead that has a fact, with the
number of the page the fact is on, for example
`{"L01": {"opening_line": "Your team has served Tarrant County since 1998.", "fact_page": 2}}`.
Script B turns `fact_page` into `fact_source_url`. Leave out a lead that has no fact that passes rule 8.

## Step 3 · Build the CSV, check it and build the email (Script B)

Run Script B. It checks the rows and the email, then writes `data/outreach/<YYYY-MM-DD>.csv`, deletes the page text
(`_pages.json`, `_model.json`) and prints the email. If a check fails, fix
`_facts.json` and run it again. Do not send the email until Script B prints `CHECKS PASSED`.

If you stop the run without `CHECKS PASSED` (for any reason), first delete the page text, then report it in the email:
`rm -f data/outreach/.work/$(date +%F)_pages.json data/outreach/.work/$(date +%F)_model.json`.

```bash
.venv/bin/python - <<'EOF'
import csv, json, re, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, "src")
from leads.identity_label import may_go_to_outreach

TODAY = date.today()
COLUMNS = ["lead_id", "business", "website", "named_person", "role", "person_source_url", "opening_line", "why_hot",
           "phone_source", "fact_source_url"]
ROLES = {"owner", "co-owner", "founder", "president", "ceo", "general manager"}  # hard rule 7: exactly these 6
DOC = Path("docs/agents/sales-researcher.md").read_text(encoding="utf-8")
GROUPS = [l.split() for l in re.search(r"<!-- first-names -->\n```text\n(.*?)```", DOC, re.S)[1].lower().splitlines()]
FIRST = {w for g in GROUPS for w in g}
OK_WORDS = set(re.search(r"<!-- ok-words -->\n```text\n(.*?)```", DOC, re.S)[1].split())

def tokens(name): return {t.strip(".,").lower() for t in [name, *name.split()] if len(t.strip(".,")) >= 2}
def row_tokens(r):  # the row's name tokens plus their nicknames ("Robert" -> "bob", "rob", ...)
    own = tokens(r["named_person"])
    return own | {w for g in GROUPS if own & set(g) for w in g}
def name_regex(words):
    alts = "|".join(sorted(map(re.escape, words), key=len, reverse=True))
    return re.compile(rf"\b(?i:{alts})\b(?!\s+(?i:county)\b)")  # "Parker County" is a place, not a name
def name_hits(text, rows):
    # every row's tokens + the whole first-name list, 2+ letters; a CSV name is never printed
    found = {m[0].lower() for m in name_regex(FIRST.union(*map(row_tokens, rows))).finditer(text)}
    return sorted(w if w in FIRST else "<a name from the CSV>" for w in found)
WORDS = {w for w in Path("/usr/share/dict/words").read_text().split() if w.islower()} | {"has"}  # as Script A
SURNAME_PLACES = set(re.search(r"<!-- surname-places -->\n```text\n(.*?)```", DOC, re.S)[1].split())
SUFFIX = r"\b(?:llc|l\.l\.c|inc|corp|co|ltd|lp|llp|pllc|company|the)\b\.?"
PART_ONLY = set("hill hills little grand north city cedar branch fort worth flower mound elm farmers haltom richland "
                "royse".split())
PLACE_LEAD = re.compile(r"\b(?:in|across|around|near|from|serves?|served|serving|covers?|covering|throughout)\s+$", re.I)
def next_to_place(m):  # the same rule as Script A
    after, before, w = m.string[m.end():m.end() + 20], m.string[max(0, m.start() - 30):m.start()], m[0].lower()
    def pair(o):  # two surname-places never vouch for each other ("Johnson Hill"), except a real pair ("Cedar Hill")
        o = o.lower(); return o in OK_WORDS and (o not in SURNAME_PLACES or w in PART_ONLY and o in PART_ONLY)
    nxt, prv = re.match(r"\s+([A-Z][a-z]+)", after), re.search(r"([A-Z][a-z]+)\s+$", before)
    if any(x and pair(x[1]) for x in (nxt, prv)):
        return True
    if w in PART_ONLY:  # "Hill" alone is not a DFW place
        return False
    listed = re.search(r"([A-Z][a-z]+)(?:,\s*|\s+(?:and|or)\s+)$", before)  # "Forney and Garland"
    return bool(listed and listed[1].lower() in OK_WORDS or re.match(r",?\s*(?:TX|Texas)\b|\s+\d", after)
                or PLACE_LEAD.search(before))
def stems(w):  # the word and its stems for real endings only ("located" -> "locate"), each 3+ letters
    out = {w}
    for end, add in (("s", ""), ("es", ""), ("ies", "y"), ("ed", ""), ("ed", "e"), ("d", ""), ("ing", ""),
                     ("ing", "e"), ("ly", ""), ("er", ""), ("ers", "")):
        if w.endswith(end) and len(w) - len(end) >= 3:
            out.add(w[:-len(end)] + add)
    return out
def known(w):  # a plain word ("communities", "served") or a two-word compound ("firefighter")
    return bool(stems(w) & WORDS) or any(w[:i] in WORDS and w[i:] in WORDS for i in range(3, len(w) - 2))
QUOTES = "\"“”‘„«»`‛‟″＂‹›′"  # M2: every double or single quote mark, backtick and prime
def has_quote(line):  # an apostrophe inside a word ("Your team’s", "You've") is fine
    return bool(re.search(f"[{re.escape(QUOTES)}]|(?<![A-Za-z])['’]|['’](?![A-Za-z])", line))
def line_problems(line, rows):
    words = re.findall(r"[A-Za-z]+", line)
    bad = [] if re.sub(r"[—–’·]", "", line).isascii() else ["letters outside A-Z (a name?)"]
    bad += [w for w in words[1:] if w[0].isupper() and w.lower() not in OK_WORDS]
    bad += [m[0] for m in re.finditer(r"\b[A-Z][a-z]+", line) if m[0].lower() in SURNAME_PLACES
            and not next_to_place(m)]  # "Our tech Johnson" is a person
    bad += [w for w in words if w[0].islower() and w not in OK_WORDS and not known(w)]  # "our tech zorvana"
    low = {w.lower() for w in words}
    for r in rows:  # every row's business name, without LLC, and each of its unusual words
        core = re.sub(r"\s+", " ", re.sub(SUFFIX, " ", r["business"].lower())).strip(" ,.&")
        odd = {w for w in re.findall(r"[a-z]+", core) if len(w) >= 3 and w not in OK_WORDS and not known(w)}
        if core and re.search(rf"\b{re.escape(core)}\b", line.lower()) or odd & low:
            bad.append("<a business name>")
    return bad

if __name__ == "__main__":  # a test can exec the lines above alone
    work = json.loads(Path(f"data/outreach/.work/{TODAY}_pages.json").read_text())
    facts_path = Path(f"data/outreach/.work/{TODAY}_facts.json")
    facts = json.loads(facts_path.read_text()) if facts_path.exists() else {}
    leads = work["leads"]
    assert set(facts) <= {l["lead_id"] for l in leads}, f"unknown lead IDs in facts: {set(facts) - {l['lead_id'] for l in leads}}"
    def fact(l):
        f = facts.get(l["lead_id"])
        if not f:
            return {"opening_line": "", "fact_source_url": ""}
        assert isinstance(f.get("opening_line"), str), f"{l['lead_id']}: opening_line is missing"
        assert f.get("fact_page") in range(1, len(l["pages"]) + 1), f"{l['lead_id']}: fact_page must be 1 or 2"
        return {"opening_line": f["opening_line"].strip(), "fact_source_url": l["pages"][f["fact_page"] - 1]["url"]}
    rows = [{c: (fact(l)[c] if c in ("opening_line", "fact_source_url") else l[c]) for c in COLUMNS} for l in leads]
    assert len(rows) <= 15, f"{len(rows)} rows: max 15"

    for r, src in zip(rows, leads):
        lid = r["lead_id"]  # messages use the lead ID, never a name
        assert may_go_to_outreach(src), f"{lid}: fails may_go_to_outreach()"
        urls = {p["url"] for p in src["pages"]}
        assert len(urls) <= 2, f"{lid}: more than 2 pages"
        for col in ("person_source_url", "fact_source_url"):
            assert not r[col] or r[col] in urls, f"{lid}: {col} is not a fetched page"
        assert bool(r["named_person"]) == bool(r["role"]) == bool(r["person_source_url"]), f"{lid}: person fields"
        if r["named_person"]:
            assert r["role"] in ROLES, f"{lid}: role {r['role']!r} is not allowed (hard rule 7)"
            assert src.get("person_on_page") is True, f"{lid}: name not on its source page"  # Script A checked it
        line = r["opening_line"]
        assert bool(line) == bool(r["fact_source_url"]), f"{lid}: fact without a source"
        if line:
            assert re.match(r"Your?\b", line), f"{lid}: the line must start with You / Your"
            assert not has_quote(line), \
                f"{lid}: no quotes in the line (review-quote ban); an apostrophe inside a word is fine"
            assert r["business"].lower() not in line.lower(), f"{lid}: the business name is in the line"
            hits = name_hits(line, rows)  # F5: checked against ALL rows
            assert not hits, f"{lid}: name tokens {hits} in the opening line; rewrite it"
            odd = line_problems(line, rows)
            assert not odd, f"{lid}: {odd} in the opening line (a name or a business name?); rewrite the line"

    subject = f"[Agent] Sales Researcher · wk {TODAY.day} {TODAY:%b} · {len(rows)} leads"
    lines = [f"{r['lead_id']} · {l['trade']} · {l['town']} · {r['why_hot']} · "
             f"{r['opening_line'] or '(no own-site fact found)'}" for r, l in zip(rows, leads)]
    no_person = [r["lead_id"] for r in rows if not r["named_person"]]
    no_fact = [r["lead_id"] for r in rows if not r["opening_line"]]
    tasks = ([f"find an owner, co-owner, founder, president, CEO or general manager by hand on the own sites of leads "
              f"{', '.join(no_person)}"] if no_person else [])
    tasks += [f"find one own-site fact by hand for leads {', '.join(no_fact)}"] if no_fact else []
    body = "\n".join([f"Sales Researcher · {TODAY} · {len(rows)} leads. Business names and contacts: "
                      f"data/outreach/{TODAY}.csv only.", work["ranking_note"], "", *lines, "",
                      *(["ACTIONS — reply YES + number:", *[f"A{n} | none | {t} | S" for n, t in enumerate(tasks, 1)]]
                        if tasks else ["No actions this week"])])
    for l in leads:  # the town is a TDLR register place ("Allen", "Dallas"), never a person: only its shape is checked
        assert re.fullmatch(r"[A-Z][A-Za-z .'-]{1,39}", l["town"]), f"{l['lead_id']}: odd town value"
    masked = "\n".join(line.replace(f" · {l['town']} · ", " · <town> · ", 1) for line, l in zip(lines, leads))
    hits = name_hits(subject + "\n" + body.replace("\n".join(lines), masked), rows)  # whole email, nothing changed
    assert not hits, f"name tokens {hits} are in the email"
    # written only after every check passes, so a failed run does not mark businesses as researched
    with open(f"data/outreach/{TODAY}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLUMNS); w.writeheader(); w.writerows(rows)
    for raw in (f"{TODAY}_pages.json", f"{TODAY}_model.json"):  # page text is not kept once the CSV exists
        Path(f"data/outreach/.work/{raw}").unlink(missing_ok=True)
    print("CHECKS PASSED\n\nSUBJECT: " + subject + "\n\n" + body)
EOF
```

## Step 4 · Send

Send the printed subject and body as plain text with the Gmail connector (`send_message`), `to` = the user's own
address only (hard rule 9). If no Gmail tool is available, write the email to `data/outreach/<date>_email.txt` and
stop. Script B has already deleted `.work/<date>_pages.json` and `_model.json`; delete `.work/<date>_facts.json` and
end the run. Do not commit; `data/` is not in Git.

A dry run (an audit) stops after Step 3: it sends nothing. Script B (or the Step 3 cleanup line) has deleted the page
text; `_facts.json` stays until the next run.

## First-name list (Scripts A and B read this block)

Each line is one name with its nicknames. Every word is a name token. Matching ignores case, so a word such as
"will", "mark" or "grant" also fails an opening line: write the line without it.

<!-- first-names -->
```text
robert bob bobby rob robbie bert
william bill billy will willie liam
richard rick ricky rich dick
james jim jimmy jamie
john johnny jack jon
joseph joe joey
michael mike mikey mick
thomas tom tommy
charles charlie chuck chas
christopher chris kris
daniel dan danny
david dave davey
edward ed eddie ted ned
anthony tony
andrew andy drew
matthew matt
nicholas nick nicky
steven stephen steve stevie
kenneth ken kenny
ronald ron ronnie
donald don donnie
timothy tim timmy
gregory greg
jeffrey jeff
lawrence larry
gerald gerry jerry
raymond ray
benjamin ben benny
samuel sam sammy
alexander alex al
albert al bert
alan allen al
arthur art
patrick pat
peter pete
douglas doug
frederick fred freddie
francis frank frankie
leonard leo len lenny
phillip philip phil
zachary zach zack
jonathan jon
nathaniel nathan nate
joshua josh
jacob jake
gabriel gabe
abraham abe
theodore theo teddy
walter walt wally
harold hal harry
henry hank
eugene gene
vincent vince
russell russ
terrence terry
calvin cal
clifford cliff
randall randy
bradley brad
jeremy jerry
elizabeth liz beth betty eliza
margaret maggie meg peggy
katherine catherine kathy kate katie cathy
susan sue susie
patricia patty tricia trish
jennifer jen jenny
jessica jess jessie
deborah debra deb debbie
rebecca becky becca
barbara barb
christina christine tina
cynthia cindy
victoria vicky tori
kimberly kim
pamela pam
samantha sammie
alexandra lexi
amanda mandy
judith judy
dorothy dot dottie
abigail abby
melissa missy mel
stephanie steph
jacqueline jackie
nancy nan
mary linda karen sarah lisa sandra ashley emily donna michelle carol nicole helen anna laura shirley angela
brenda emma ruth amy kathleen virginia sharon kelly evelyn joyce janet carolyn rachel heather maria diane julie
joan olivia marie gloria teresa sara janice julia grace kayla denise frances martha amber doris brittany diana
natalie beverly danielle sophia madison alice jean lauren megan hannah andrea jane cheryl kathryn ann tiffany
crystal holly erin lori tammy dawn sherry wendy rhonda tracy tara valerie monica leslie kristen kristin rosa ana
carmen lucy
mark paul kevin brian george eric jason ryan gary justin scott brandon dennis tyler aaron jose adam noah ethan
christian keith roger austin sean carl dylan jordan jesse bryan bruce logan juan wayne elijah roy ralph louis
shawn travis troy marcus luis carlos miguel jorge javier manuel ricardo eduardo antonio francisco pedro alejandro
fernando roberto hector oscar raul jesus mario sergio ramon rafael ruben marco victor angel cody chad derek dustin
wesley curtis clint clayton colton cole dale darrell glenn glen gordon grant heath hunter chase ivan jared jay
joel lance lee leroy lloyd luke mason max mitchell neil norman owen preston rex rodney ross shane spencer stanley
todd trent trevor tristan ty tyrone wade warren earl ernest floyd herbert howard marvin melvin dwayne darren
duane irving dallas parker ellis collin bo jo cy
hope rose faith joy ruby pearl iris ivy daisy lily violet autumn summer
```

## DFW-word list (Scripts A and B read this block)

Capitalised words that an opening line may use, and that the model copy keeps. Place names that are also first names
(Allen, Justin, Keller, Murphy, Heath, Crowley, Lancaster, Celina, Prosper) are left out on purpose, so the checks
fail closed.

<!-- ok-words -->
```text
collin dallas denton ellis johnson kaufman parker rockwall tarrant county texas tx dfw metroplex metro north
fort worth arlington plano garland irving grand prairie mckinney frisco mesquite carrollton richardson lewisville
flower mound mansfield euless bedford grapevine southlake coppell rowlett wylie desoto cedar hill duncanville
burleson weatherford waxahachie cleburne midlothian forney terrell argyle haltom city hurst colleyville sachse
little elm azle granbury royse benbrook saginaw watauga richland hills aledo roanoke corinth addison farmers branch
january february march april may june july august september october november december hvac
```

Place words from the list above that are also surnames or months. Script A keeps them in the model copy, and
Script B allows them in an opening line, only next to another place word, before ", TX" or "Texas", before a
number, or after "in", "serves", "across" and similar words ("Johnson County", "Cedar Hill", "Garland, TX",
"May 2020", "Forney and Garland", "serves Wylie").

<!-- surname-places -->
```text
johnson hill hills little grand north city cedar branch fort worth flower mound elm farmers mansfield bedford
richardson garland terrell forney wylie hurst addison burleson rowlett coppell benbrook cleburne granbury royse
colleyville saginaw watauga euless argyle aledo roanoke corinth haltom richland may june april august
```
