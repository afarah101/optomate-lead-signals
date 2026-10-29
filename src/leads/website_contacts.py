"""Leads: a strict reader for a business's own website. Rules: docs/decisions/lookup-automation.md.

At most 2 pages (homepage + one contact page), robots.txt obeyed, honest User-Agent, 1 request per second, 10 s timeout,
no retries. Reads a phone only from tel: links or schema.org JSON-LD telephone, never from text. Never reads emails.
"""

import html
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter, namedtuple
from html.parser import HTMLParser
from http.client import HTTPException
from urllib.parse import unquote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

USER_AGENT = "OptomateResearch/0.1 (research contact: admin@optomate.co.uk)"
ROBOTS_TOKEN = "OptomateResearch"
TIMEOUT_SECS = 10
MIN_SECS_BETWEEN_REQUESTS = 1.0
MAX_REDIRECTS = 3
MAX_BYTES = 2_000_000
ORG_TYPES = {"Organization", "Corporation", "LocalBusiness", "WebSite", "HVACBusiness", "HomeAndConstructionBusiness"}

Response = namedtuple("Response", "status url content_type text")


class SiteUnreadable(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


class Throttle:
    def __init__(self, min_interval=MIN_SECS_BETWEEN_REQUESTS, clock=time.monotonic, sleep=time.sleep):
        self.min_interval, self.clock, self.sleep, self.last = min_interval, clock, sleep, None

    def wait(self) -> None:
        if self.last is not None and (gap := self.clock() - self.last) < self.min_interval:
            self.sleep(self.min_interval - gap)
        self.last = self.clock()


_THROTTLE = Throttle()  # one throttle for every request this process makes


class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # redirects are followed by hand so each hop is throttled and checked for same-site


_OPENER = urllib.request.build_opener(_NoAutoRedirect)


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def same_site(a: str, b: str) -> bool:
    return bool(_host(a)) and _host(a) == _host(b) and urlsplit(b).scheme in ("http", "https")


def http_get(url: str, throttle: Throttle = _THROTTLE) -> Response:
    for _ in range(MAX_REDIRECTS + 1):
        throttle.wait()
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"})
        try:
            with _OPENER.open(request, timeout=TIMEOUT_SECS) as r:
                body = r.read(MAX_BYTES)
                return Response(r.status, url, r.headers.get_content_type(),
                                body.decode(r.headers.get_content_charset() or "utf-8", "replace"))
        except urllib.error.HTTPError as e:
            location = e.headers.get("Location") if e.code in (301, 302, 303, 307, 308) else None
            if not location:
                return Response(e.code, url, "", "")
            next_url = urljoin(url, location)
            if not same_site(url, next_url):
                raise SiteUnreadable("redirect_off_site") from None
            url = next_url
        except (urllib.error.URLError, HTTPException, TimeoutError, OSError, ValueError) as e:
            raise SiteUnreadable("fetch_failed", type(e).__name__) from None
    raise SiteUnreadable("fetch_failed", "too many redirects")


def _robots_for(url: str, get) -> RobotFileParser:
    parts = urlsplit(url)
    response = get(f"{parts.scheme}://{parts.netloc}/robots.txt")
    robots = RobotFileParser()
    if response.status in (401, 403) or response.status >= 500:
        robots.disallow_all = True  # unreachable or forbidden robots.txt: assume the site says no
    elif response.status >= 400:
        robots.allow_all = True  # no robots.txt: no rules
    else:
        robots.parse(response.text.splitlines())
    return robots


def us_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", re.split(r"[;,]", unquote(raw or ""))[0])
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] in "01" or digits[3] in "01":
        return None
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


class _PageReader(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url, self.title, self.og_site_name = base_url, "", ""
        self.tel_numbers, self.json_ld, self.links = [], [], []
        self.has_message_form = False
        self._in_title = self._in_json_ld = False
        self._json_ld_parts, self._form_depth, self._anchor = [], 0, None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and a.get("property", "").lower() == "og:site_name":
            self.og_site_name = a.get("content", "").strip()
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_json_ld, self._json_ld_parts = True, []
        elif tag == "form":
            self._form_depth += 1
        elif tag == "textarea" and self._form_depth:
            self.has_message_form = True
        elif tag == "a":
            href = a.get("href", "").strip()
            if href.lower().startswith("tel:"):
                self.tel_numbers.append(href[4:])
            elif href and not href.lower().startswith(("mailto:", "javascript:", "#")):
                self._anchor = [urljoin(self.base_url, href), []]

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            self.json_ld.append("".join(self._json_ld_parts))
        elif tag == "form" and self._form_depth:
            self._form_depth -= 1
        elif tag == "a" and self._anchor:
            self.links.append((self._anchor[0], " ".join(self._anchor[1])))
            self._anchor = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_json_ld:
            self._json_ld_parts.append(data)
        if self._anchor:
            self._anchor[1].append(data.strip())


def _walk_json_ld(node, phones: list, names: list) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_json_ld(item, phones, names)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = [t for t in (types if isinstance(types, list) else [types]) if isinstance(t, str)]
        if "Person" not in types:  # a Person's telephone can be a personal number
            phone = node.get("telephone")
            phones += [p for p in (phone if isinstance(phone, list) else [phone]) if isinstance(p, str)]
            if isinstance(node.get("name"), str) and any(t in ORG_TYPES or t.endswith("Business") for t in types):
                names.append(node["name"])
        for value in node.values():
            if isinstance(value, (dict, list)):
                _walk_json_ld(value, phones, names)


def _read_page(response: Response) -> dict:
    reader = _PageReader(response.url)
    reader.feed(response.text)
    schema_phones, schema_names = [], []
    for block in reader.json_ld:
        try:
            _walk_json_ld(json.loads(block), schema_phones, schema_names)
        except ValueError:
            pass
    schema_phone = next((p for p in map(us_phone, schema_phones) if p), None)
    tel_counts = Counter(p for p in map(us_phone, reader.tel_numbers) if p)
    contact_link = next((url for url, text in reader.links
                         if same_site(response.url, url) and urlsplit(url).path.rstrip("/") != urlsplit(response.url).path.rstrip("/")
                         and ("contact" in urlsplit(url).path.lower() or "contact" in text.lower())), None)
    return {
        "site_name": reader.og_site_name or (schema_names[0] if schema_names else "") or reader.title.strip(),
        # Equal counts keep first-seen order, so a tie goes to the first number on the page.
        "phone": schema_phone or (tel_counts.most_common(1)[0][0] if tel_counts else ""),
        "has_message_form": reader.has_message_form,
        "contact_link": contact_link,
    }


def _visible_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", markup)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).upper()


def licence_numbers_shown(page_html: str) -> set[str]:
    # Real sites write e.g. TACLB00012345E (see lookup-automation.md); only the TACLA/TACLB prefix counts, and only
    # the first number after it, so a year or phone number nearby isn't read as a licence.
    text, numbers = _visible_text(page_html), set()
    for prefix in re.finditer(r"TACL[\s-]?[AB]", text):
        run = re.search(r"\d+", text[prefix.end():prefix.end() + 40])
        if run and run.start() <= 20:
            numbers.add(run.group().lstrip("0"))
    return numbers - {""}


def site_shows_licence_number(page_html: str, licence_number: str | None) -> bool:
    wanted = (licence_number or "").strip().lstrip("0")
    return wanted.isdigit() and wanted in licence_numbers_shown(page_html)


def _is_html_ok(response: Response) -> bool:
    return response.status == 200 and response.content_type in ("text/html", "application/xhtml+xml")


def read_own_site_contacts(url: str, get=None, licence_number: str | None = None) -> dict:
    get = get or http_get
    url = urlsplit(url)._replace(query="", fragment="").geturl()  # drop tracking parameters from Google's link
    if urlsplit(url).scheme not in ("http", "https"):
        raise SiteUnreadable("fetch_failed", "not a web address")

    robots = _robots_for(url, get)
    if not robots.can_fetch(ROBOTS_TOKEN, url):
        raise SiteUnreadable("robots_blocked")
    home = get(url)  # page 1 of 2
    if not _is_html_ok(home):
        raise SiteUnreadable("fetch_failed", f"homepage HTTP {home.status}")
    page = _read_page(home)
    numbers = licence_numbers_shown(home.text)
    contacts = {"website_url": home.url, "site_name": page["site_name"], "phone": page["phone"],
                "phone_source_url": home.url if page["phone"] else "", "form_url": ""}

    link = page["contact_link"]
    if link and robots.can_fetch(ROBOTS_TOKEN, link):
        try:
            contact = get(link)  # page 2 of 2; nothing else is ever fetched
        except SiteUnreadable:
            contact = None
        if contact and _is_html_ok(contact):
            contact_page = _read_page(contact)
            if contact_page["has_message_form"]:
                contacts["form_url"] = contact.url
            if not contacts["phone"] and contact_page["phone"]:
                contacts.update(phone=contact_page["phone"], phone_source_url=contact.url)
            numbers |= licence_numbers_shown(contact.text)
    wanted = (licence_number or "").strip().lstrip("0")
    return contacts | {"licence_shown": wanted.isdigit() and wanted in numbers, "licence_numbers": sorted(numbers)}
