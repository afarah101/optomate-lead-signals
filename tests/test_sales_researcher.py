"""No network: Scripts A and B of docs/agents/sales-researcher.md, exec'd from the doc itself.

Fixed findings (audit of fe0f4b4) and the behaviours that must keep passing. HTTP is a fake opener in this file: no
site is ever requested.
"""

import contextlib
import email.message
import io
import json
import re
import sys
import urllib.error
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import leads.website_contacts as wc  # noqa: E402  (the same module object the scripts import)

SR = REPO / "docs" / "agents" / "sales-researcher.md"
DOC = SR.read_text(encoding="utf-8")
SCRIPT_A, SCRIPT_B = re.findall(r"<<'EOF'\n(.*?)\nEOF\n", DOC, re.S)
A_MARK = "# ---- The run starts here."
B_MARK = 'if __name__ == "__main__":'
TODAY = date.today()
NEEDS_DICT = pytest.mark.skipif(not Path("/usr/share/dict/words").exists(), reason="the scripts need a word list")


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "src").symlink_to(REPO / "src")
    (tmp_path / "docs").symlink_to(REPO / "docs")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def defs_a():
    ns = {"__name__": "sr_test"}
    exec(SCRIPT_A.split(A_MARK)[0], ns)
    return ns


def defs_b():
    ns = {"__name__": "sr_test"}
    exec(SCRIPT_B.split(B_MARK)[0], ns)
    return ns


def page(text):
    return [{"url": "https://example.com/about", "text": text}]


# ---------- Finding 1 (Major F1): a role word must start its phrase ----------

CUSTOMER_TITLES = [
    "We had the system checked and they fixed our AC the same day. Home Owner Mike Okafor",
    "Thanks again. Business Owner Mike Okafor",
    "Thanks again. Property Owner Mike Okafor",
    "Thanks again. Board President Mike Okafor",
    "Thanks again. Assistant to the President Mike Okafor",
    "Thanks again. Home Owner: Mike Okafor",
    "Thanks again. Meet our owner Mike Okafor",
]


@NEEDS_DICT
@pytest.mark.parametrize("text", CUSTOMER_TITLES)
def test_f1_customer_titles_are_refused(ws, text):
    assert defs_a()["find_person"](page(text)) == ("", "", "")


@NEEDS_DICT
def test_f1_audit_example_exactly(ws):
    assert defs_a()["find_person"](page("fixed our AC the same day. Home Owner Mike Jones")) == ("", "", "")


ACCEPTED = [
    ("Owner: Mike Okafor", "owner"),
    ("Owner Mike Okafor", "owner"),
    ("Our team. Owner Mike Okafor", "owner"),
    ("Mike Okafor, Owner", "owner"),
    ("Mike Okafor, the Owner", "owner"),
    ("Mike Okafor (President)", "president"),
    ("Mike Okafor – CEO", "ceo"),
    ("Mike Okafor | Founder", "founder"),
    ("Co-Owner: Mike Okafor", "co-owner"),
    ("General Manager: Mike Okafor", "general manager"),
    ("The company was founded by Mike Okafor in 1998.", "founder"),
]


@NEEDS_DICT
@pytest.mark.parametrize("text,role", ACCEPTED)
def test_f1_real_titles_still_accepted(ws, text, role):
    assert defs_a()["find_person"](page(text)) == ("Mike Okafor", role, "https://example.com/about")


PRIOR_F1_REFUSED = ["Co-Founder Mike Okafor", "Mike Okafor, Co-Founder", "Vice President Mike Okafor",
                    "Assistant General Manager Mike Okafor", "Former Owner Mike Okafor", "Co-founded by Mike Okafor",
                    "Mike Okafor, Sales Manager", "Mike Okafor, Technician"]


@NEEDS_DICT
@pytest.mark.parametrize("text", PRIOR_F1_REFUSED)
def test_f1_prior_refusals_kept(ws, text):
    assert defs_a()["find_person"](page(text)) == ("", "", "")


# ---------- Finding 3 (Minor F1): en dash and em dash act like a hyphen ----------

@NEEDS_DICT
@pytest.mark.parametrize("text", ["Co–Founder Mike Okafor", "Co—Founder Mike Okafor", "Mike Okafor, Co–Founder",
                                  "Mike Okafor, Co—Founder", "Co – Founder Mike Okafor", "Mike Okafor—Owner",
                                  "Co–founded by Mike Okafor"])
def test_f3_dash_cofounder_refused(ws, text):
    assert defs_a()["find_person"](page(text)) == ("", "", "")


@NEEDS_DICT
@pytest.mark.parametrize("text", ["Co-Owner Mike Okafor", "Co–Owner Mike Okafor", "Co—Owner Mike Okafor",
                                  "Mike Okafor, Co–Owner", "Mike Okafor, Co—Owner"])
def test_f3_dash_coowner_is_co_owner(ws, text):
    a, b = defs_a(), defs_b()
    name, role, _ = a["find_person"](page(text))
    assert (name, role) == ("Mike Okafor", "co-owner") and role in b["ROLES"]


# ---------- Finding 4 (Minor M2): every quote mark ----------

@NEEDS_DICT
@pytest.mark.parametrize("ch", ["`", "‛", "‟", "″", "＂", '"', "“", "”", "‘", "„", "«", "»", "‹", "›", "′"])
def test_m2_quote_marks_rejected(ws, ch):
    assert defs_b()["has_quote"](f"Your team was called {ch}the best{ch} in Tarrant County.")


@NEEDS_DICT
@pytest.mark.parametrize("line", ["Your team was 'the best'.", "Your team was ’the best’ here.", "You said 'yes."])
def test_m2_stray_single_quotes_rejected(ws, line):
    assert defs_b()["has_quote"](line)


@NEEDS_DICT
@pytest.mark.parametrize("line", ["Your team’s work covers Tarrant County.", "You've served Denton County since 1998."])
def test_m2_apostrophe_inside_word_ok(ws, line):
    assert not defs_b()["has_quote"](line)


# ---------- Finding 2: review text and page text ----------

@NEEDS_DICT
def test_f2_drop_reviews_cuts_quotes_and_review_parts(ws):
    drop = defs_a()["drop_reviews"]
    text = ("Family owned since 1998. " + "We install systems. " * 20 + "Customer reviews: Sarah fixed it fast, "
            "5 stars! " + "We repair units. " * 30 + "“Best AC fix ever” said a neighbour. Serving Tarrant County.")
    out = drop(text)
    assert "Family owned since 1998." in out and "Serving Tarrant County." in out
    assert not re.search(r"reviews|Sarah|5 stars|Best AC fix", out)


def http_error(url, code, location=None):
    hdrs = email.message.Message()
    if location:
        hdrs["Location"] = location
    return urllib.error.HTTPError(url, code, "x", hdrs, None)


class FakeResponse(io.BytesIO):
    def __init__(self, body, ctype):
        super().__init__(body.encode())
        self.status = 200
        self.headers = email.message.Message()
        self.headers["Content-Type"] = f"{ctype}; charset=utf-8"


class FakeOpener:
    """url -> body (200), or ("redirect", location), or an int status. Records every URL asked for."""

    def __init__(self, routes):
        self.routes, self.asked = routes, []

    def open(self, request, timeout=None):
        url = request.full_url
        self.asked.append(url)
        hit = self.routes.get(url, 404)
        if isinstance(hit, int):
            raise http_error(url, hit)
        if isinstance(hit, tuple):
            raise http_error(url, 301, hit[1])
        return FakeResponse(hit, "text/plain" if url.endswith("/robots.txt") else "text/html")


FILLER = "We install and repair heating and cooling systems for homes. " * 100  # > 5,000 characters (M7)
SITE_A_HOME = '<html><body><a href="/about-us">About us</a><p>Family owned since 1998.</p></body></html>'
SITE_A_ABOUT = (f"<html><body><p>{FILLER}</p><p>Owner: Mike Okafor.</p><p>Serving Tarrant County since 1998.</p>"
                + "<p>We fix things. </p>" * 20 +
                "<p>Customer reviews</p><p>Sarah Quill fixed our AC, 5 stars!</p>" + "<p>Our crews. </p>" * 40 +
                "<p>“Best AC fix ever” — a neighbour</p></body></html>")
ROUTES = {
    "https://a.example/robots.txt": "User-agent: *\nAllow: /\n",
    "https://a.example/": SITE_A_HOME,
    "https://a.example/about-us": SITE_A_ABOUT,
    "https://b.example/robots.txt": "User-agent: *\nDisallow: /\n",
    "https://b.example/": SITE_A_HOME,
    "https://c.example/robots.txt": "User-agent: *\nDisallow: /private/\n",
    "https://c.example/": ("redirect", "/private/home"),
    "https://c.example/private/home": SITE_A_HOME,
    "https://d.example/robots.txt": ("redirect", "/"),  # the old robots.txt -> "/" loop
    "https://d.example/": "<html><body><p>Serving Denton County.</p></body></html>",
}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def run_a(ws, monkeypatch):
    month = f"{TODAY:%Y-%m}"
    write(ws / f"data/logs/{month}_call_list_v1.csv", "licence_number,business_name,stop_requested\n"
          "TACLA1,Okafor Cooling LLC,\nTACLA2,Bee Air LLC,\nTACLA3,Cee Air LLC,\nTACLA4,Dee Air LLC,\n")
    write(ws / f"data/leads/{month}_reverse_lookup_full_v1.csv", "licence_number,identity_label,website_url,phone_source\n"
          "TACLA1,verified,https://a.example/,site\nTACLA2,verified,https://b.example/,site\n"
          "TACLA3,verified,https://c.example/,site\nTACLA4,verified,https://d.example/,site\n")
    write(ws / f"data/logs/{month}_lookup_auto_v1.csv", "licence_number,website_url\n")
    write(ws / "data/leads/tdlr_hvac_dfw.csv", "licence_number,entity_flag,licence_type,county,city\n"
          + "".join(f"TACLA{i},likely_corporate,HVAC,TARRANT,\n" for i in range(1, 5)))
    out, work = ws / "data/outreach", ws / "data/outreach/.work"
    write(work / "2026-02-30_pages.json", "{}")  # M8: an impossible date
    write(out / "2026-02-30.csv", "business\nX LLC\n")
    write(out / f"{TODAY - timedelta(days=200)}.csv", "business\nOld LLC\n")
    write(work / f"{TODAY - timedelta(days=1)}_model.json", "[]")
    fake = FakeOpener(ROUTES)
    monkeypatch.setattr(wc, "_OPENER", fake)
    monkeypatch.setattr(wc._THROTTLE, "min_interval", 0)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(SCRIPT_A, {"__name__": "__main__"})
    return ws, buf.getvalue(), fake


@NEEDS_DICT
def test_f6_bad_file_dates_skipped_and_reported(run_a):
    ws, printed, _ = run_a
    assert "RETENTION skipped 2026-02-30_pages.json" in printed and "RECENT skipped 2026-02-30.csv" in printed
    assert (ws / "data/outreach/.work/2026-02-30_pages.json").exists()
    assert not (ws / f"data/outreach/{TODAY - timedelta(days=200)}.csv").exists()  # 6-month retention kept
    assert not (ws / f"data/outreach/.work/{TODAY - timedelta(days=1)}_model.json").exists()  # earlier run's text


@NEEDS_DICT
def test_f2_pages_json_has_no_page_text_and_model_has_no_review(run_a):
    ws, printed, _ = run_a
    pages_json = (ws / f"data/outreach/.work/{TODAY}_pages.json").read_text()
    model_json = (ws / f"data/outreach/.work/{TODAY}_model.json").read_text()
    leads = json.loads(pages_json)["leads"]
    assert all(set(p) == {"url"} for lead in leads for p in lead["pages"])
    assert not re.search(r"Sarah|Quill|5 stars|Best AC fix|install and repair", pages_json)
    assert not re.search(r"Sarah|Quill|5 stars|reviews|Best AC fix|Okafor|Mike", model_json)
    a = next(l for l in leads if l["licence_key"] == "TACLA1")
    assert (a["named_person"], a["role"], a["person_on_page"]) == ("Mike Okafor", "owner", True)  # M7: past 5,000


@NEEDS_DICT
def test_robots_every_request_and_hop(run_a):
    ws, printed, fake = run_a
    assert "DROP licence TACLA2: site unreadable: robots_blocked" in printed
    assert "DROP licence TACLA3: site unreadable: robots_blocked" in printed  # redirect hop checked
    assert "https://b.example/" not in fake.asked and "https://c.example/private/home" not in fake.asked
    for site in "abcd":
        asked = [u for u in fake.asked if u.startswith(f"https://{site}.example")]
        assert asked[0] == f"https://{site}.example/robots.txt"  # robots.txt before any page
    leads = json.loads((ws / f"data/outreach/.work/{TODAY}_pages.json").read_text())["leads"]
    assert {l["licence_key"] for l in leads} == {"TACLA1", "TACLA4"}  # robots.txt -> "/" does not loop


@NEEDS_DICT
def test_script_b_end_to_end_f4_m9_and_page_text_deleted(run_a):
    ws, _, _ = run_a
    work = ws / "data/outreach/.work"
    write(work / f"{TODAY}_facts.json", json.dumps({
        "L01": {"opening_line": "Your team has served Tarrant County since 1998.", "fact_page": 2}}))
    pages = json.loads((work / f"{TODAY}_pages.json").read_text())
    pages["leads"] = pages["leads"][:1]  # L01 has a person and a fact: no A-line (M9)
    write(work / f"{TODAY}_pages.json", json.dumps(pages))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(SCRIPT_B, {"__name__": "__main__"})
    printed = buf.getvalue()
    assert "CHECKS PASSED" in printed
    assert "L01 · HVAC · Tarrant County · " in printed  # F4: lead ID + trade + town
    assert not re.search(r"Okafor|Mike|Cooling", printed)
    assert "No actions this week" in printed  # M9
    assert not (work / f"{TODAY}_pages.json").exists() and not (work / f"{TODAY}_model.json").exists()
    assert (ws / f"data/outreach/{TODAY}.csv").exists()


@NEEDS_DICT
def test_script_b_refuses_a_new_quote_mark(run_a):
    ws, _, _ = run_a
    work = ws / "data/outreach/.work"
    write(work / f"{TODAY}_facts.json", json.dumps(
        {"L01": {"opening_line": "Your team is ″the best″ in Tarrant County.", "fact_page": 2}}))
    with pytest.raises(AssertionError, match="no quotes"), contextlib.redirect_stdout(io.StringIO()):
        exec(SCRIPT_B, {"__name__": "__main__"})
    assert (work / f"{TODAY}_pages.json").exists()  # nothing deleted on a failed check


# ---------- F5: names of every row, with nicknames ----------

@NEEDS_DICT
def test_f5_name_hits_every_row_and_nicknames(ws):
    hits = defs_b()["name_hits"]
    rows = [{"named_person": "Robert Okafor"}, {"named_person": ""}]
    assert hits("Your team with Bob", rows) == ["bob"]
    assert hits("Your okafor crew", rows) == ["<a name from the CSV>"]
    assert hits("Your team serves Tarrant County.", rows) == []


# ---------- Finding 5: no "at most 7 days" promise; Finding 2: honest notice and LIA ----------

NOTICE = REPO / "docs/compliance/article-14-notice.md"
LIA = REPO / "docs/compliance/legitimate-interests-assessment.md"


def test_f5_no_seven_day_promise():
    for path in (SR, NOTICE, LIA):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r'(?i)(?:at most|within) 7 days(?!"? (?:was|claim))', text.replace("\n", " ")), path.name


def test_f2_notice_and_lia_wording():
    notice = NOTICE.read_text(encoding="utf-8").replace("\n", " ")
    assert "never stores or uses review text" not in notice
    assert "keeps only the page addresses, not the page text" in notice and "can stay in the copy" in notice
    lia = LIA.read_text(encoding="utf-8").splitlines()
    assert lia[40].startswith("| Raw page text (short-lived)") and "can stay in that copy" in lia[40]
    assert lia[60].startswith("| Review text in our records") and "Exception" in lia[60]


# ---------- no regression: M6 line, LIA line 143 ----------

M6 = ("`Follow docs/agents/sales-researcher.md exactly. Never read data/outreach/.work/*_pages.json or "
      "data/outreach/*.csv; read only data/outreach/.work/<date>_model.json.`")


def test_m6_line_exact():
    assert M6 in DOC.splitlines()


def test_retention_cites_lia_line_143():
    assert "Rule: LIA line 143" in DOC and "(LIA line 143" in SCRIPT_A
    assert LIA.read_text(encoding="utf-8").splitlines()[142].startswith("| Retention: 6 months after last contact")
