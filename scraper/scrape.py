#!/usr/bin/env python3
"""AP Government Jobs crawler.

Run:  python scraper/scrape.py
Out:  data/jobs.json   (consumed directly by docs/index.html)

Design notes
------------
* District sites all run NIC's S3WaaS WordPress platform, so one parser
  (`parse_s3waas`) covers all 26 districts, including pagination.
* State/central sites vary; `parse_generic` is a tolerant recruitment-link
  extractor with keyword scoring, so a redesign degrades coverage instead
  of crashing the run.
* Every run records per-source health (ok / empty / error) into the JSON,
  so the frontend can show exactly which sources were covered — no silent
  gaps, which is the only honest way to approach "get all the jobs".
* Dedup key: normalized (source_id, url, title). History is merged so a
  notice keeps its first_seen date; items unseen for HISTORY_DAYS are
  dropped only after their deadline (if known) has passed.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from sources import build_sources  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "jobs.json"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 APJobsBot/1.0 (+public-service aggregator)")
TIMEOUT = 25
RETRIES = 2
MAX_PAGES = 3          # S3WaaS pagination depth per district
HISTORY_DAYS = 45      # keep dead links this long after last sighting
IST = timezone(timedelta(hours=5, minutes=30))

RECRUIT_WORDS = re.compile(
    r"recruit|notification|vacan|posts?\b|walk[- ]?in|apply|engagement|"
    r"outsourc|appointment|hiring|selection|dsc|group[- ][iv1-4]|constable|"
    r"staff nurse|teacher|anm\b|mpha|paramedic", re.I)
NOISE_WORDS = re.compile(
    r"result|answer key|hall ?ticket|admit card|merit list|seniority|"
    r"transfer|tender|quotation|auction|corrigendum to tender", re.I)

DATE_PATTERNS = [
    (re.compile(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})"), "dmy"),
    (re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})"), "ymd"),
]
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
TEXT_DATE = re.compile(r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})")


@dataclass
class Job:
    id: str
    title: str
    org: str
    level: str
    district: str | None
    url: str
    source_id: str
    source_name: str
    published: str | None = None
    deadline: str | None = None
    first_seen: str = ""
    last_seen: str = ""
    tags: list = field(default_factory=list)


# ----------------------------------------------------------------- utils

def now_iso() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def get(url: str, session: requests.Session) -> requests.Response | None:
    for attempt in range(RETRIES + 1):
        try:
            r = session.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
            if r.status_code == 200 and len(r.text) > 500:
                return r
        except requests.RequestException:
            pass
        time.sleep(1.5 * (attempt + 1))
    return None


def parse_date(text: str) -> str | None:
    """Extract the first plausible date from text -> ISO YYYY-MM-DD."""
    m = TEXT_DATE.search(text)
    if m:
        mon = MONTHS.get(m.group(2)[:3].lower())
        if mon:
            try:
                return datetime(int(m.group(3)), mon, int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    for pat, order in DATE_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                if order == "dmy":
                    d = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                else:
                    d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if 2000 < d.year < 2100:
                    return d.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def find_deadline(text: str) -> str | None:
    """A date preceded by last-date phrasing, else None (never guess)."""
    m = re.search(r"(?:last date|closing date|on or before|upto|up to|till|before)\D{0,25}"
                  r"(\d{1,2}(?:st|nd|rd|th)?[-/.\s][A-Za-z\d]{1,9}[-/.\s,]*\d{2,4})", text, re.I)
    return parse_date(m.group(1)) if m else None


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def job_key(source_id: str, url: str, title: str) -> str:
    return f"{source_id}|{url.split('#')[0].rstrip('/')}|{clean(title).lower()[:120]}"


# ----------------------------------------------------------------- parsers

def parse_s3waas(src: dict, session: requests.Session) -> list[Job]:
    """NIC S3WaaS notice-category pages: table/list of notices, paginated."""
    jobs, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        url = src["url"] if page == 1 else src["url"].rstrip("/") + f"/page/{page}/"
        r = get(url, session)
        if r is None:
            if page == 1:
                raise ConnectionError("unreachable")
            break
        soup = BeautifulSoup(r.text, "html.parser")
        main = soup.find("main") or soup.find(id="content") or soup
        rows = main.find_all("tr")
        blocks = rows if rows else main.find_all(["li", "article", "div"], recursive=True)
        found_on_page = 0
        for block in blocks:
            a = block.find("a", href=True)
            if not a:
                continue
            title = clean(a.get_text() or a.get("title", ""))
            href = urljoin(url, a["href"])
            if len(title) < 8 or NOISE_WORDS.search(title):
                continue
            if not (RECRUIT_WORDS.search(title) or href.lower().endswith(".pdf")):
                continue
            k = job_key(src["id"], href, title)
            if k in seen:
                continue
            seen.add(k)
            block_text = clean(block.get_text(" "))
            jobs.append(Job(
                id=k, title=title, org=src["name"], level=src["level"],
                district=src["district"], url=href, source_id=src["id"],
                source_name=src["name"],
                published=parse_date(block_text),
                deadline=find_deadline(block_text),
            ))
            found_on_page += 1
        if found_on_page == 0:
            break
    return jobs


def parse_generic(src: dict, session: requests.Session) -> list[Job]:
    """Tolerant extractor: every link whose text/context scores as recruitment."""
    r = get(src["url"], session)
    if r is None:
        raise ConnectionError("unreachable")
    soup = BeautifulSoup(r.text, "html.parser")
    jobs, seen = [], set()
    for a in soup.find_all("a", href=True):
        title = clean(a.get_text())
        href = urljoin(src["url"], a["href"])
        if len(title) < 12 or len(title) > 220:
            continue
        if href.startswith(("mailto:", "javascript:", "tel:")):
            continue
        if NOISE_WORDS.search(title) or not RECRUIT_WORDS.search(title):
            continue
        k = job_key(src["id"], href, title)
        if k in seen:
            continue
        seen.add(k)
        ctx = clean((a.find_parent(["tr", "li", "p", "div"]) or a).get_text(" "))[:400]
        jobs.append(Job(
            id=k, title=title, org=src["name"], level=src["level"],
            district=src["district"], url=href, source_id=src["id"],
            source_name=src["name"],
            published=parse_date(ctx), deadline=find_deadline(ctx),
        ))
    return jobs[:40]


# ----------------------------------------------------------------- pipeline

def load_previous() -> dict:
    if OUT.exists():
        try:
            return json.loads(OUT.read_text())
        except json.JSONDecodeError:
            pass
    return {"jobs": [], "sources": [], "updated": None}


def run() -> int:
    session = requests.Session()
    sources = build_sources()
    prev = load_previous()
    prev_jobs = {j["id"]: j for j in prev.get("jobs", [])}
    now = now_iso()
    today = datetime.now(IST).date()

    all_jobs: dict[str, Job] = {}
    health = []

    for src in sources:
        if src["kind"] == "portal":
            health.append({**{k: src[k] for k in ("id", "name", "level", "url")},
                           "status": "portal", "count": 0, "note": "JS portal — link surfaced in UI"})
            continue
        try:
            parser = parse_s3waas if src["kind"] == "s3waas" else parse_generic
            found = parser(src, session)
            for j in found:
                old = prev_jobs.get(j.id)
                j.first_seen = old["first_seen"] if old else now
                j.last_seen = now
                if old and old.get("deadline") and not j.deadline:
                    j.deadline = old["deadline"]
                all_jobs[j.id] = j
            health.append({**{k: src[k] for k in ("id", "name", "level", "url")},
                           "status": "ok" if found else "empty", "count": len(found), "note": ""})
            print(f"[ok]    {src['id']:24s} {len(found):3d} notices")
        except Exception as e:
            health.append({**{k: src[k] for k in ("id", "name", "level", "url")},
                           "status": "error", "count": 0, "note": str(e)[:120]})
            print(f"[fail]  {src['id']:24s} {e}")
        time.sleep(0.8)  # be polite to NIC servers

    # carry forward recent history for sources that errored or dropped items
    cutoff = today - timedelta(days=HISTORY_DAYS)
    for jid, old in prev_jobs.items():
        if jid in all_jobs:
            continue
        try:
            last = datetime.fromisoformat(old["last_seen"]).date()
        except (ValueError, KeyError):
            continue
        dl = old.get("deadline")
        deadline_passed = bool(dl) and datetime.strptime(dl, "%Y-%m-%d").date() < today
        if last >= cutoff and not deadline_passed:
            all_jobs[jid] = Job(**{k: old.get(k) for k in Job.__dataclass_fields__})

    jobs_out = sorted((asdict(j) for j in all_jobs.values()),
                      key=lambda j: (j["deadline"] or "9999", j["first_seen"]),)
    payload = {
        "updated": now,
        "job_count": len(jobs_out),
        "sources": health,
        "jobs": jobs_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    ok = sum(1 for h in health if h["status"] == "ok")
    print(f"\nWrote {len(jobs_out)} jobs from {ok}/{len(health)} healthy sources -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
