"""No network: every page is local SAMPLE HTML served by a fake fetcher, and every Places call is a fake."""

import csv
import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leads import place_match
from leads.lookup_autofill import AUTO_COLUMNS, autofill_lookup
from leads.place_match import (
    PlacesUnavailable, fetch_website_live, find_place_candidates, load_api_key, name_matches_place, shares_main_words,
)
from leads import website_contacts
from leads.website_contacts import (
    Response, SiteUnreadable, Throttle, http_get, read_own_site_contacts, same_site, site_shows_licence_number, us_phone,
)
from signals.lookup_sheet import check_lookup_sheet

SITE = "https://www.sample-cooling.example/"
FAKE_KEY = "AIzaSAMPLE-not-a-real-key-0000000000000"


def page(body, title="SAMPLE Cooling LLC | Dallas HVAC", head=""):
    return f"<!doctype html><html><head><title>{title}</title>{head}</head><body>{body}</body></html>"


class FakeWeb:
    """Serves local SAMPLE pages and records every URL requested."""

    def __init__(self, pages, robots="", robots_status=200):
        self.pages, self.robots, self.robots_status, self.requested = pages, robots, robots_status, []

    def __call__(self, url):
        self.requested.append(url)
        if url.endswith("/robots.txt"):
            return Response(self.robots_status, url, "text/plain", self.robots)
        if url in self.pages:
            return Response(200, url, "text/html", self.pages[url])
        return Response(404, url, "text/html", "")

    def page_requests(self):
        return [u for u in self.requested if not u.endswith("/robots.txt")]


HOME = page("""
  <header><a href="tel:+1-214-555-0100">Call (214) 555-0100</a></header>
  <p>Or text 469-555-0199, or email <a href="mailto:office@sample-cooling.example">office@sample-cooling.example</a></p>
  <a href="/contact-us">Contact us</a>
  <footer><a href="tel:2145550100">214-555-0100</a> <a href="tel:9725550111">Sales</a></footer>
""")
CONTACT = page("""<form action="/send"><input name="name"><textarea name="message"></textarea></form>""")


def sample_site(**overrides):
    return FakeWeb({SITE: HOME, "https://www.sample-cooling.example/contact-us": CONTACT} | overrides)


# --- own-site reader -------------------------------------------------------------------------------------------

def test_tel_link_found_and_most_repeated_number_wins():
    contacts = read_own_site_contacts(SITE, get=sample_site())
    assert contacts["phone"] == "214-555-0100" and contacts["phone_source_url"] == SITE


def test_text_phone_is_ignored():
    web = sample_site(**{SITE: page("<p>Call 214-555-0100 today</p><span itemprop='x'>972 555 0111</span>")})
    assert read_own_site_contacts(SITE, get=web)["phone"] == ""


def test_email_is_never_collected():
    contacts = read_own_site_contacts(SITE, get=sample_site())
    assert "office@" not in json.dumps(contacts) and set(contacts) == {
        "website_url", "site_name", "phone", "phone_source_url", "form_url", "licence_shown"}


def test_schema_org_telephone_is_preferred_but_never_from_a_person():
    ld = json.dumps([{"@type": "Person", "name": "SAMPLE Jane", "telephone": "469-555-0199"},
                     {"@type": "HVACBusiness", "name": "SAMPLE Cooling LLC", "telephone": "+1 972-555-0123"}])
    web = sample_site(**{SITE: page('<a href="tel:2145550100">x</a>', head=f'<script type="application/ld+json">{ld}</script>')})
    assert read_own_site_contacts(SITE, get=web)["phone"] == "972-555-0123"


def test_contact_page_form_is_recorded():
    assert read_own_site_contacts(SITE, get=sample_site())["form_url"] == "https://www.sample-cooling.example/contact-us"


def test_search_box_is_not_a_contact_form():
    web = sample_site(**{"https://www.sample-cooling.example/contact-us": page("<form><input name='q'></form>")})
    assert read_own_site_contacts(SITE, get=web)["form_url"] == ""


def test_robots_block_is_respected():
    web = sample_site()
    web.robots = "User-agent: OptomateResearch\nDisallow: /\n"
    with pytest.raises(SiteUnreadable) as e:
        read_own_site_contacts(SITE, get=web)
    assert e.value.reason == "robots_blocked" and web.page_requests() == []


def test_robots_block_on_contact_page_only():
    web = sample_site()
    web.robots = "User-agent: *\nDisallow: /contact-us\n"
    contacts = read_own_site_contacts(SITE, get=web)
    assert web.page_requests() == [SITE] and contacts["phone"] and contacts["form_url"] == ""


@pytest.mark.parametrize("status", [401, 403, 500, 503])
def test_forbidden_or_broken_robots_means_no(status):
    web = sample_site()
    web.robots_status = status
    with pytest.raises(SiteUnreadable, match="robots_blocked"):
        read_own_site_contacts(SITE, get=web)
    assert web.page_requests() == []


def test_missing_robots_means_allowed():
    web = sample_site()
    web.robots_status = 404
    assert read_own_site_contacts(SITE, get=web)["phone"] == "214-555-0100"


def test_at_most_two_pages():
    many_links = "".join(f'<a href="/contact-{i}">Contact {i}</a>' for i in range(5))
    pages = {SITE: page(many_links)} | {f"https://www.sample-cooling.example/contact-{i}": CONTACT for i in range(5)}
    web = FakeWeb(pages)
    read_own_site_contacts(SITE, get=web)
    assert web.page_requests() == [SITE, "https://www.sample-cooling.example/contact-0"]


def test_off_site_contact_link_is_not_followed():
    web = FakeWeb({SITE: page('<a href="https://forms.other.example/contact">Contact</a>')})
    read_own_site_contacts(SITE, get=web)
    assert web.page_requests() == [SITE]


def test_tracking_parameters_are_dropped():
    web = sample_site()
    contacts = read_own_site_contacts(SITE + "?utm_source=gmb&utm_medium=organic", get=web)
    assert contacts["website_url"] == SITE and web.page_requests()[0] == SITE


def test_user_agent_carries_the_research_contact(monkeypatch):
    from email.message import Message
    headers = Message()
    headers["Content-Type"] = "text/html; charset=utf-8"
    seen = {}

    class FakeResponse:
        status = 200

        def __init__(self):
            self.headers = headers
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, *a): return b"<html></html>"

    def fake_open(request, timeout):
        seen.update(user_agent=request.get_header("User-agent"), timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(website_contacts._OPENER, "open", fake_open)
    assert http_get("https://x.example/", throttle=Throttle(min_interval=0)).status == 200
    assert seen == {"user_agent": "OptomateResearch/0.1 (research contact: ops@optomate.co.uk)", "timeout": 10}


def test_one_request_per_second():
    now = [0.0]
    slept = []
    throttle = Throttle(clock=lambda: now[0], sleep=lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)))
    throttle.wait()
    now[0] += 0.25
    throttle.wait()
    now[0] += 3
    throttle.wait()
    assert slept == [0.75]


@pytest.mark.parametrize("raw, expected", [
    ("+1-214-555-0100", "214-555-0100"), ("%2B12145550100", "214-555-0100"), ("214.555.0100;ext=12", "214-555-0100"),
    ("555-0100", None), ("1-014-555-0100", None), ("214-155-0100", None),
])
def test_us_phone(raw, expected):
    assert us_phone(raw) == expected


def test_same_site():
    assert same_site("https://www.a.example/", "http://a.example/contact")
    assert not same_site("https://a.example/", "https://a.example.evil.example/")


# --- name match ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("licence, other, expected", [
    ("SAMPLE COOLING LLC", "Sample Cooling | Dallas HVAC", True),
    ("D.T.M. HEATING AND AIR CONDITIONING", "DTM Heating & Air Conditioning - Fort Worth", True),
    ("SAMPLE COOLING, INC.", "Sample Cooling Co", True),
    ("SAMPLE COOLING LLC", "Sample Plumbing", False),
    ("SAMPLE COOLING LLC", "", False),
    ("LLC", "LLC Heating", False),
])
def test_name_match_and_mismatch(licence, other, expected):
    assert shares_main_words(licence, other) is expected


@pytest.mark.parametrize("licence, other, expected", [
    ("SAMPLE AIR SPECIALIST LLC", "Sample Air Specialists", True),     # plural = singular
    ("SAMPLE AIR SERVICES INC", "Sample Air Service", True),
    ("SAMPLE GLASS LLC", "Sample Gla", False),                         # SS words keep their S
    ("SAMPLE NORTH AIR SERVICE LLC", "Sample Air Service", False),     # the site check still needs every word
])
def test_site_name_check_treats_plural_as_singular_but_stays_strict(licence, other, expected):
    assert shares_main_words(licence, other) is expected


@pytest.mark.parametrize("licence, google, expected", [
    ("SAMPLE NORTH AIR LLC", "Sample Air", False),                                   # 2 of 3 = 67%
    ("SAMPLE NORTH AIR SERVICE LLC", "Sample Air Services", True),                   # 3 of 4 = 75%
    ("A1 B2 C3 D4 E5 F6 G7 H8 I9 J10", "A1 B2 C3 D4 E5 F6 G7", True),                # 7 of 10 = exactly 70%
    ("A1 B2 C3 D4 E5 F6 G7 H8 I9 J10", "A1 B2 C3 D4 E5 F6", False),                  # 6 of 10
    ("SAMPLE AIR SPECIALIST LLC", "Sample Air Specialists", True),
    ("LLC", "LLC", False),
])
def test_places_name_70_percent_edges(licence, google, expected):
    assert name_matches_place(licence, google) is expected


def places_reply(*places):
    return lambda url, key, mask, body=None: {"places": [
        {"id": pid, "displayName": {"text": name}, "formattedAddress": address} for pid, name, address in places]}


@pytest.mark.parametrize("places, expected", [
    ([], ([], "no_place_none")),
    ([("p1", "Sample Cooling", "Dallas, TX, USA")], ([], "no_place_zip")),
    ([("p1", "Sample Cooling", "Dallas, Texas, USA")], ([], "no_place_zip")),
    ([("p1", "Sample Cooling", "1 Main St, Tulsa, OK 74103, USA")], ([], "no_place_texas")),
    ([("p1", "Other Plumbing", "1 Elm St, Dallas, TX 75201, USA")], (["p1"], "")),   # the site judges the name now
])
def test_place_candidate_reason_codes(places, expected):
    assert find_place_candidates("SAMPLE COOLING LLC", "Dallas", api_key=FAKE_KEY, request=places_reply(*places)) == expected


def test_up_to_three_texas_candidates_with_name_matches_first():
    zip_ok = "1 Elm St, Dallas, TX 75201, USA"
    reply = places_reply(("p1", "Other Air", zip_ok), ("p2", "Sample Cooling", "Dallas, TX, USA"), ("p3", "Another Air", zip_ok),
                         ("p4", "Sample Cooling", zip_ok), ("p5", "Fourth Air", zip_ok), ("p6", "Fifth Air", zip_ok))
    assert find_place_candidates("SAMPLE COOLING LLC", "Dallas", api_key=FAKE_KEY, request=reply) == (["p4", "p1", "p3"], "")


def test_texas_without_zip_is_named_but_not_a_candidate():
    # The ZIP rule stays until evidence shows it costs matches (see lookup-automation.md "Rule changes").
    assert find_place_candidates("SAMPLE COOLING LLC", "Dallas", api_key=FAKE_KEY,
                                 request=places_reply(("p1", "Sample Cooling", "Dallas, TX, USA"))) == ([], "no_place_zip")


# --- licence number on the site --------------------------------------------------------------------------------

@pytest.mark.parametrize("markup, licence, expected", [
    ("<footer>TDLR TACLB00012345E</footer>", "12345", True),                       # TACL prefix, leading zeros
    ("<p>TACLA12345C</p>", "0012345", True),                                       # zeros on our side ignored too
    ("<p>TACL-A #00012345 E</p>", "12345", True),
    ("<p>TACLA<span>00012345</span>E</p>", "12345", True),                         # split by markup
    ("<p>License #12345</p>", "12345", False),                                     # digits without the prefix
    ("<p>TACT 12345E</p>", "12345", False),
    ("<p>TACLA123456E</p>", "12345", False),                                       # a longer number is not ours
    ("<p>TACLA 99999C and 12345</p>", "12345", True),                              # within 20 characters
    ("<p>TACLA see our office for details 12345</p>", "12345", False),             # beyond 20 characters
    ("<script>var l='TACLA12345C'</script><p>no licence</p>", "12345", False),     # visible text only
    ("<p>TACLA12345C</p>", "", False),
])
def test_site_shows_licence_number(markup, licence, expected):
    assert site_shows_licence_number(markup, licence) is expected


def test_reader_reports_licence_from_either_page():
    web = sample_site(**{"https://www.sample-cooling.example/contact-us": page("<p>TACLB00012345E</p>" + CONTACT)})
    assert read_own_site_contacts(SITE, get=web, licence_number="12345")["licence_shown"] is True
    assert read_own_site_contacts(SITE, get=sample_site(), licence_number="12345")["licence_shown"] is False


# --- Places adapter --------------------------------------------------------------------------------------------

def test_candidates_must_be_in_texas():
    response = {"places": [
        {"id": "p-ok", "displayName": {"text": "Sample Cooling"}, "formattedAddress": "1 Main St, Tulsa, OK 74103, USA"},
        {"id": "p-tx", "displayName": {"text": "SAMPLE Cooling LLC"}, "formattedAddress": "1 Elm St, Dallas, TX 75201, USA"},
    ]}
    calls = []
    found = find_place_candidates("SAMPLE COOLING LLC", "Dallas", api_key=FAKE_KEY,
                                  request=lambda url, key, mask, body=None: calls.append((mask, body)) or response)
    assert found == (["p-tx"], "")
    assert calls == [("places.id,places.displayName,places.formattedAddress",
                      {"textQuery": "SAMPLE COOLING LLC Dallas County TX", "regionCode": "US"})]


def test_website_detail_asks_for_website_only():
    masks = []
    site = fetch_website_live("p-tx", api_key=FAKE_KEY,
                              request=lambda url, key, mask, body=None: masks.append(mask) or {"websiteUri": SITE})
    assert site == SITE and masks == ["websiteUri"]


def test_key_is_read_from_env_and_never_printed(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text(f'# local\nexport GOOGLE_MAPS_API_KEY="{FAKE_KEY}"\n')
    assert load_api_key(env) == FAKE_KEY

    def failing_request(url, key, mask, body=None):
        raise PlacesUnavailable("Places API HTTP 403: API key not valid")

    with pytest.raises(PlacesUnavailable) as e:
        find_place_candidates("SAMPLE COOLING LLC", "Dallas", api_key=FAKE_KEY, request=failing_request)
    out = capsys.readouterr()
    assert FAKE_KEY not in out.out + out.err + str(e.value)


def test_missing_key_stops(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OTHER=1\n")
    with pytest.raises(PlacesUnavailable, match="missing"):
        load_api_key(env)


def test_real_request_puts_key_only_in_a_header(monkeypatch):
    seen = {}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, *a): return b'{"websiteUri": "https://x.example"}'

    def fake_urlopen(request, timeout):
        seen.update(url=request.full_url, headers=dict(request.header_items()), timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(place_match.urllib.request, "urlopen", fake_urlopen)
    assert fetch_website_live("p1", api_key=FAKE_KEY) == "https://x.example"
    assert FAKE_KEY not in seen["url"] and seen["headers"]["X-goog-api-key"] == FAKE_KEY and seen["timeout"] == 10


# --- autofill --------------------------------------------------------------------------------------------------

def write_call_list(tmp_path, names):
    path = tmp_path / "call_list.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["licence_number", "business_name", "county", "time_band"])
        writer.writeheader()
        writer.writerows({"licence_number": f"S{i}", "business_name": n, "county": "Dallas", "time_band": "morning"}
                         for i, n in enumerate(names))
    return path


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def site_result(i, site_name, phone="", form=False, licence_shown=False):
    url = f"https://site{i}.example/"
    return {"website_url": url, "site_name": site_name, "phone": phone, "phone_source_url": url if phone else "",
            "form_url": f"{url}contact" if form else "", "licence_shown": licence_shown}


def run_autofill(tmp_path, capsys=None):
    names = ["SAMPLE COOLING LLC", "SAMPLE NOWHERE LLC", "SAMPLE NOSITE LLC", "SAMPLE BLOCKED LLC",
             "SAMPLE MISMATCH LLC", "SAMPLE NOPHONE LLC"]
    places = {n: f"place-{i}" for i, n in enumerate(names) if n != "SAMPLE NOWHERE LLC"}
    websites = {f"place-{i}": f"https://site{i}.example/" for i in range(len(names)) if i != 2}
    sites = {
        "https://site0.example/": site_result(0, "Sample Cooling", phone="214-555-0100", form=True),
        "https://site4.example/": site_result(4, "Other Business", phone="214-555-0104"),
        "https://site5.example/": site_result(5, "Sample Nophone", form=True),
    }

    def read_site(url, licence_number=None):
        if url == "https://site3.example/":
            raise SiteUnreadable("robots_blocked")
        return sites[url]

    out, queue = tmp_path / "auto.csv", tmp_path / "queue.csv"
    report = autofill_lookup(write_call_list(tmp_path, names), out, queue, find_candidates=lambda n, c: ([places[n]], "") if n in places else ([], "no_place_none"),
                             website_of=websites.get, read_site=read_site, today=date(2026, 10, 28))
    return report, out, queue


def test_autofill_routes_every_business_once(tmp_path):
    report, out, queue = run_autofill(tmp_path)
    auto, queued = read_rows(out), read_rows(queue)
    assert [r["licence_number"] for r in auto] == ["S0"]
    assert {r["licence_number"]: r["reason"] for r in queued} == {
        "S1": "no_place_none", "S2": "no_website", "S3": "robots_blocked", "S4": "name_mismatch", "S5": "no_tel_phone"}
    assert report["auto_filled"] == 1 and report["places_calls"] == 11  # 6 searches + 5 details


def test_autofill_row_is_complete_and_passes_the_checker(tmp_path):
    _, out, _ = run_autofill(tmp_path)
    row = read_rows(out)[0]
    assert list(row) == AUTO_COLUMNS
    assert (row["business_phone"], row["lookup_date"], row["lookup_initials"], row["contact_email"], row["place_id"]) == (
        "214-555-0100", "2026-10-28", "auto", "", "place-0")
    assert check_lookup_sheet(out) == []


def test_queue_keeps_website_only_after_the_name_check(tmp_path):
    _, _, queue = run_autofill(tmp_path)
    rows = {r["reason"]: r for r in read_rows(queue)}
    assert rows["name_mismatch"]["website_url"] == "" and rows["robots_blocked"]["website_url"] == ""
    assert rows["no_tel_phone"]["website_url"] == "https://site5.example/"


@pytest.mark.parametrize("existing", ["auto.csv", "queue.csv"])
def test_no_overwrite(tmp_path, existing):
    (tmp_path / existing).write_text("kept\n")
    with pytest.raises(FileExistsError):
        run_autofill(tmp_path)
    assert (tmp_path / existing).read_text() == "kept\n"


def test_places_failure_on_first_call_keeps_no_files_and_no_key(tmp_path, capsys):
    def broken(name, county):
        raise PlacesUnavailable("Places API HTTP 403: Places API (New) has not been used in project")

    out, queue = tmp_path / "auto.csv", tmp_path / "queue.csv"
    with pytest.raises(PlacesUnavailable, match="403"):
        autofill_lookup(write_call_list(tmp_path, ["SAMPLE COOLING LLC"]), out, queue, find_candidates=broken)
    assert not out.exists() and not queue.exists()
    printed = capsys.readouterr()
    assert FAKE_KEY not in printed.out + printed.err


def candidate_run(tmp_path, candidates, websites, sites, names=("SAMPLE COOLING LLC",), budget=300):
    seen = []

    def read_site(url, licence_number=None):
        seen.append((url, licence_number))
        if isinstance(sites[url], SiteUnreadable):
            raise sites[url]
        return sites[url]

    out, queue = tmp_path / "auto.csv", tmp_path / "queue.csv"
    report = autofill_lookup(write_call_list(tmp_path, list(names)), out, queue,
                             find_candidates=lambda n, c: (candidates.get(n, []), "" if n in candidates else "no_place_none"),
                             website_of=websites.get, read_site=read_site, today=date(2026, 10, 28), places_budget=budget)
    return report, read_rows(out), read_rows(queue), seen


def test_licence_match_beats_name_mismatch(tmp_path):
    report, auto, queue, seen = candidate_run(
        tmp_path, {"SAMPLE COOLING LLC": ["p1"]}, {"p1": "https://site1.example/"},
        {"https://site1.example/": site_result(1, "Totally Different Brand", phone="214-555-0101", licence_shown=True)})
    assert [r["notes"] for r in auto] == ["auto: site found via Google Places live; match_by=licence"]
    assert seen == [("https://site1.example/", "S0")] and report["match_by"] == {"licence": 1}


def test_name_match_is_recorded(tmp_path):
    _, auto, _, _ = candidate_run(tmp_path, {"SAMPLE COOLING LLC": ["p1"]}, {"p1": "https://site1.example/"},
                                  {"https://site1.example/": site_result(1, "Sample Cooling", phone="214-555-0101")})
    assert auto[0]["notes"].endswith("match_by=name")


def test_three_candidates_are_tried_in_order(tmp_path):
    report, auto, queue, seen = candidate_run(
        tmp_path, {"SAMPLE COOLING LLC": ["p1", "p2", "p3"]},
        {"p2": "https://site2.example/", "p3": "https://site3.example/"},
        {"https://site2.example/": site_result(2, "Other Air", phone="214-555-0102"),
         "https://site3.example/": site_result(3, "Sample Cooling", phone="214-555-0103")})
    assert [u for u, _ in seen] == ["https://site2.example/", "https://site3.example/"]   # p1 had no website
    assert auto[0]["place_id"] == "p3" and queue == [] and report["places_calls"] == 4    # 1 search + 3 details


def test_first_accepted_candidate_stops_the_search(tmp_path):
    report, auto, _, seen = candidate_run(
        tmp_path, {"SAMPLE COOLING LLC": ["p1", "p2"]}, {"p1": "https://site1.example/", "p2": "https://site2.example/"},
        {"https://site1.example/": site_result(1, "Sample Cooling", phone="214-555-0101"),
         "https://site2.example/": site_result(2, "Sample Cooling", phone="214-555-0102")})
    assert len(seen) == 1 and auto[0]["place_id"] == "p1" and report["places_calls"] == 2


def test_confirmed_site_without_phone_is_kept_over_the_first_reason(tmp_path):
    _, auto, queue, seen = candidate_run(
        tmp_path, {"SAMPLE COOLING LLC": ["p1", "p2", "p3"]},
        {"p1": "https://site1.example/", "p2": "https://site2.example/", "p3": "https://site3.example/"},
        {"https://site1.example/": site_result(1, "Other Air", phone="214-555-0101"),
         "https://site2.example/": site_result(2, "Sample Cooling", form=True),
         "https://site3.example/": site_result(3, "Sample Cooling", phone="214-555-0103")})
    assert auto == [] and len(seen) == 2   # p3 not tried: p2 is the business
    assert (queue[0]["reason"], queue[0]["place_id"], queue[0]["website_url"]) == ("no_tel_phone", "p2", "https://site2.example/")


@pytest.mark.parametrize("site, reason", [
    (None, "no_website"),
    (SiteUnreadable("robots_blocked"), "robots_blocked"),
    (SiteUnreadable("redirect_off_site"), "redirect_off_site"),
    (SiteUnreadable("fetch_failed"), "fetch_failed"),
    (site_result(1, "Other Air", phone="214-555-0101"), "name_mismatch"),
    (site_result(1, "Sample Cooling"), "no_tel_phone"),
])
def test_every_site_reason_code(tmp_path, site, reason):
    websites = {} if site is None else {"p1": "https://site1.example/"}
    _, auto, queue, _ = candidate_run(tmp_path, {"SAMPLE COOLING LLC": ["p1"]}, websites, {"https://site1.example/": site})
    assert auto == [] and queue[0]["reason"] == reason
    assert queue[0]["website_url"] == ("https://site1.example/" if reason == "no_tel_phone" else "")


def test_places_budget_is_never_exceeded_and_every_business_is_searched(tmp_path):
    names = ("SAMPLE COOLING LLC", "SAMPLE HEATING LLC")
    websites = {f"p{i}": f"https://site{i}.example/" for i in range(1, 4)}
    sites = {u: site_result(9, "Other Air", phone="214-555-0109") for u in websites.values()}
    report, auto, queue, seen = candidate_run(tmp_path, {names[0]: ["p1", "p2", "p3"]}, websites, sites, names, budget=4)
    assert report["places_calls"] == 4 and len(seen) == 2
    assert {r["licence_number"]: r["reason"] for r in queue} == {"S0": "name_mismatch", "S1": "no_place_none"}


def test_budget_reached_on_a_search_stops_the_run(tmp_path):
    with pytest.raises(PlacesUnavailable, match="budget of 1"):
        candidate_run(tmp_path, {}, {}, {}, ("SAMPLE A LLC", "SAMPLE B LLC"), budget=1)
