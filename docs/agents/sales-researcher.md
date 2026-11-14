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
     Other capitalised words are allowed only from Script B's `OK_WORDS` list (DFW places, months, HVAC); if a place
     is not on that list, use the county or "your area". It is one sentence, true, and not pushy.
9. Email Ahmed only: the **own address of the Gmail account that the Gmail connector is signed in to** (the user's
   own email in your context). No other recipient, no cc, no bcc. If you cannot tell that address, do not send.
10. **Never read `data/outreach/.work/<date>_pages.json` or `data/outreach/<date>.csv`** (they hold names and raw page
    text). You read only `data/outreach/.work/<date>_model.json`, in which Script A has replaced names with `[name]`.

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

## Required task prompt (M6)

The scheduled task `agent-8-sales-researcher` must contain this exact line. Ahmed sets it by hand; you never edit
the task:

`Follow docs/agents/sales-researcher.md exactly. Never read data/outreach/.work/*_pages.json or data/outreach/*.csv; read only data/outreach/.work/<date>_model.json.`

## Step 1 · Select, fetch and extract (Script A)

Run Script A. It:

- deletes `data/outreach/*.csv`, `*_email.txt` and `.work/*` files older than 6 months (the date in the file name,
  else the file's change time).
  Rule: LIA line 142 (`docs/compliance/legitimate-interests-assessment.md`, Safeguards, "Retention" row);
- loads the newest call list (`data/logs/*_call_list*.csv`, not `*_emails.csv`), the newest reverse lookup
  (`data/leads/*_reverse_lookup_full_v*.csv`, not `*_domains*`), the newest auto lookup
  (`data/logs/*_lookup_auto*.csv`) and the ranking file `data/logs/<YYYY-MM>_ranked_leads.csv` for **this month**. If
  that file is missing, or only an older month's file exists, the rows are not ranked and the email says so;
- keeps a row only if: `may_go_to_outreach()` is true, the licence is not on the do-not-contact list (all call lists
  and call logs, `do_not_contact_list()`), `entity_flag == "likely_corporate"` (from `data/leads/tdlr_hvac_dfw.csv`),
  and, when this month's ranking file exists, `band == "hot"` **and** `eligible == "yes"`;
- skips a business that is in an outreach CSV from the last 28 days, so each week covers new businesses;
- fetches up to 2 pages per site until **15** sites are readable (at most 25 sites tried), with robots.txt checked
  before every request, redirect hops included;
- finds the named person and role in the full page text with code (hard rule 7);
- writes `data/outreach/.work/<date>_pages.json` (raw, for Script B only) and `data/outreach/.work/<date>_model.json`
  (redacted, for you), and prints each dropped row by licence number with its reason. It never prints a name.

```bash
.venv/bin/python - <<'EOF'
import csv, glob, html, json, re, sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit
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
ROLES = "co-owner|owner|founder|president|ceo|general manager"  # hard rule 7: exactly these 6
DOC = Path("docs/agents/sales-researcher.md").read_text(encoding="utf-8")
GROUPS = [l.split() for l in re.search(r"<!-- first-names -->\n```text\n(.*?)```", DOC, re.S)[1].lower().splitlines()]
FIRST = {w for g in GROUPS for w in g}
PROPER = Path("/usr/share/dict/propernames")  # macOS first names: more redaction in the model copy only
REDACT = FIRST | (set(PROPER.read_text().lower().split()) - {"the"} if PROPER.exists() else set())  # the list has "The"

# Retention: delete outreach CSVs older than 6 months (LIA line 142, Safeguards "Retention").
for p in [*OUT.glob("*.csv"), *OUT.glob("*_email.txt"), *WORK.glob("*")]:  # .work keeps raw text after dry runs
    made = (date.fromisoformat(p.stem) if re.fullmatch(r"\d{4}-\d\d-\d\d", p.stem)
            else date.fromtimestamp(p.stat().st_mtime))
    if made < TODAY - timedelta(days=183):
        p.unlink(); print(f"RETENTION deleted {p.name} (older than 6 months)")

def natural(p): return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p)]
def files(pattern, exclude=()): return sorted((p for p in glob.glob(pattern, recursive=True)
                                               if not any(x in p for x in exclude)), key=natural)
def rows(path): return list(csv.DictReader(open(path, newline="", encoding="utf-8")))
def key(licence): return (licence or "").strip().lstrip("0")

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
                    if older else f"RANKING MISSING: {RANK.name} not found in data/logs. Leads are not ranked.")

with open("data/leads/tdlr_hvac_dfw.csv", newline="", encoding="utf-8") as f:
    reader = csv.reader(f); header = next(reader)
    assert not {"licence_holder", "owner_name"} & set(header), "STOP: leads file has a licence holder column"
    li, ei, ti, ci = (header.index(c) for c in ("licence_number", "entity_flag", "licence_type", "county"))
    tdlr = {key(r[li]): {"entity": r[ei], "trade": r[ti], "county": r[ci]} for r in reader}

logged = [r for p in call_lists + files("data/logs/*call_log*.csv") for r in rows(p)]
blocked = {key(l) for l in do_not_contact_list(logged)}
recent = {r["business"] for p in files(str(OUT / "*.csv")) if re.fullmatch(r"\d{4}-\d\d-\d\d", Path(p).stem)
          and date.fromisoformat(Path(p).stem) >= TODAY - timedelta(days=28) and Path(p).stem != TODAY.isoformat()
          for r in rows(p)}

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
    town = f"{t['county'].title()} County" if t["county"].lower() in COUNTIES else "DFW"
    kept.append({"licence_key": k, "business": name, "website": src["website_url"], "identity_label": lab,
                 "phone_source": phone_source, "why_hot": why, "trade": t["trade"] or "HVAC", "town": town,
                 "score": int(rk["score"]) if ranked is not None else 0})
kept.sort(key=lambda r: -r["score"])  # stable: call-list order inside each score

# robots.txt on every request: http_get opens each redirect hop through wc._OPENER, so check the hop first.
robots_cache = {}
def robots_ok(url):
    origin = "{0.scheme}://{0.netloc}".format(urlsplit(url))
    if origin not in robots_cache:
        robots_cache[origin] = _robots_for(origin + "/", http_get)
    return robots_cache[origin].can_fetch(ROBOTS_TOKEN, url)
class RobotsOnEveryHop:
    def __init__(self, inner): self.inner = inner
    def open(self, request, timeout=None):
        if urlsplit(request.full_url).path != "/robots.txt" and not robots_ok(request.full_url):
            raise SiteUnreadable("robots_blocked")
        return self.inner.open(request, timeout=timeout)
wc._OPENER = RobotsOnEveryHop(wc._OPENER)

def text_of(markup):  # full text: names are searched in all of it; only the model copy is cut
    markup = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", markup)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()

NAME = r"[A-Z][a-z]+(?: [A-Z]\.)?(?: [A-Z][A-Za-z'-]+){1,2}"
PERSON = [re.compile(rf"(?P<name>{NAME})\s*[,|(–—-]\s*(?:[Tt]he\s+)?\b(?P<role>(?i:{ROLES}))\b"),  # separator required
          re.compile(rf"\b(?P<role>(?i:{ROLES}))\b\s*[:,–—-]?\s*(?P<name>{NAME})"),
          re.compile(rf"\b(?i:founded by)\s+(?P<name>{NAME})")]
NOT_NAME = {"llc", "inc", "co", "company", "heating", "air", "cooling", "plumbing", "services", "service", "hvac",
            "mechanical", "conditioning", "ac", "and", "the", "our", "owner", "founder", "president", "ceo",
            "general", "manager"}
def find_person(pages):
    # shortcut: text patterns only ("Jo Doe, Owner", "Owner: Jo Doe", "founded by Jo Doe"); JSON-LD Person is not read
    for page in pages:
        for pat in PERSON:
            for m in pat.finditer(page["text"]):
                words = m["name"].split()
                while words and words[0].lower() not in FIRST: words.pop(0)  # "Meet Jo Doe" -> "Jo Doe"
                while words and words[-1].lower().strip(".") in NOT_NAME: words.pop()
                if len(words) >= 2:
                    return " ".join(words), (m.groupdict().get("role") or "founder").lower(), page["url"]
    return "", "", ""

def tokens(name): return {t.strip(".,").lower() for t in [name, *name.split()] if len(t.strip(".,")) >= 2}
def name_regex(words, tail=""):
    alts = "|".join(sorted(map(re.escape, words), key=len, reverse=True))
    return re.compile(rf"\b(?i:{alts})\b(?!\s+(?i:county)\b){tail}")  # "Parker County" is a place, not a name
def redact(text, person):
    tail = r"(?:\s+[A-Z]\.)?(?:\s+[A-Z][A-Za-z'-]+){0,2}"  # also the surname after a first name
    # shortcut: a name on neither list (e.g. a rare customer name in a review) stays; Script B never reads this copy
    text = name_regex(REDACT | tokens(person), tail).sub("[name]", text)
    for t in (t for t in tokens(person) if len(t) >= 3):  # inside words too: "smithair.com" -> "[name]air.com"
        text = re.sub(re.escape(t), "[name]", text, flags=re.I)
    return text[:MAX_CHARS]

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
    person, role, person_url = find_person(pages)
    researched.append(r | {"lead_id": f"L{len(researched) + 1:02d}", "website": home.url, "pages": pages,
                           "named_person": person, "role": role, "person_source_url": person_url})

(WORK / f"{TODAY}_pages.json").write_text(json.dumps({"ranking_note": ranking_note, "leads": researched}, indent=1))
(WORK / f"{TODAY}_model.json").write_text(json.dumps([
    {"lead_id": r["lead_id"], "trade": r["trade"], "town": r["town"],
     "pages": [{"page": n, "text": redact(p["text"], r["named_person"])} for n, p in enumerate(r["pages"], 1)]}
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

Run Script B. It writes `data/outreach/<YYYY-MM-DD>.csv`, checks it and prints the email. If a check fails, fix
`_facts.json` and run it again. Do not send the email until Script B prints `CHECKS PASSED`.

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
# Capitalised words allowed in an opening line. Place names that are also first names (Allen, Justin, Keller,
# Murphy, Heath, Crowley, Lancaster, Celina, Prosper) are left out on purpose, so the check fails closed.
OK_WORDS = set("""collin dallas denton ellis johnson kaufman parker rockwall tarrant county texas tx dfw metroplex north
fort worth arlington plano garland irving grand prairie mckinney frisco mesquite carrollton richardson lewisville
flower mound mansfield euless bedford grapevine southlake coppell rowlett wylie desoto cedar hill duncanville
burleson weatherford waxahachie cleburne midlothian forney terrell argyle haltom city hurst colleyville sachse
little elm azle granbury royse benbrook saginaw watauga richland hills aledo roanoke corinth addison farmers branch
january february march april may june july august september october november december hvac""".split())
DOC = Path("docs/agents/sales-researcher.md").read_text(encoding="utf-8")
GROUPS = [l.split() for l in re.search(r"<!-- first-names -->\n```text\n(.*?)```", DOC, re.S)[1].lower().splitlines()]
FIRST = {w for g in GROUPS for w in g}

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
def unknown_capitals(line):
    words = re.findall(r"[A-Za-z]+", line)
    return [w for w in words[1:] if w[0].isupper() and w.lower() not in OK_WORDS]

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
            page = next(p["text"] for p in src["pages"] if p["url"] == r["person_source_url"])
            assert r["named_person"].lower() in page.lower(), f"{lid}: name not on its source page"
        line = r["opening_line"]
        assert bool(line) == bool(r["fact_source_url"]), f"{lid}: fact without a source"
        if line:
            assert re.match(r"Your?\b", line), f"{lid}: the line must start with You / Your"
            assert not re.search(r"[\"“”]", line), f"{lid}: no quotes in the line (review-quote ban)"
            assert r["business"].lower() not in line.lower(), f"{lid}: the business name is in the line"
            hits = name_hits(line, rows)  # F5: checked against ALL rows
            assert not hits, f"{lid}: name tokens {hits} in the opening line; rewrite it"
            odd = unknown_capitals(line)
            assert not odd, f"{lid}: capitalised words {odd} are not in OK_WORDS (a name?); rewrite the line"

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
    hits = name_hits(subject + "\n" + body, rows)  # on the whole email, before anything is changed
    assert not hits, f"name tokens {hits} are in the email"
    # written only after every check passes, so a failed run does not mark businesses as researched
    with open(f"data/outreach/{TODAY}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLUMNS); w.writeheader(); w.writerows(rows)
    print("CHECKS PASSED\n\nSUBJECT: " + subject + "\n\n" + body)
EOF
```

## Step 4 · Send

Send the printed subject and body as plain text with the Gmail connector (`send_message`), `to` = the user's own
address only (hard rule 9). If no Gmail tool is available, write the email to `data/outreach/<date>_email.txt` and
stop. Then delete `data/outreach/.work/<date>_pages.json`, `_model.json` and `_facts.json` (they hold page text) and
end the run. Do not commit; `data/` is not in Git.

A dry run (an audit) stops after Step 3: it sends nothing and keeps the `.work` files.

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
```
