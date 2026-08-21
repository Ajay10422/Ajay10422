"""LinkedIn public (guest) job search.

Uses only the logged-out endpoints LinkedIn serves to anonymous job seekers -
no account, no cookies, no authenticated scraping. Requests are throttled and
back off on rate limiting.
"""
from __future__ import annotations

import html
import json
import random
import re
import time
import urllib.parse
import urllib.request

GUEST_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
GUEST_POSTING = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Politeness: LinkedIn throttles aggressively. Keep the pace human-ish.
MIN_DELAY = 2.0
MAX_DELAY = 4.0


class RateLimited(Exception):
    pass


def _get(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-CA,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 999, 403):
            raise RateLimited(f"HTTP {exc.code}") from exc
        raise


def _get_with_backoff(url: str, attempts: int = 4) -> str:
    delay = 5.0
    for attempt in range(attempts):
        try:
            return _get(url)
        except RateLimited:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
    return ""


def _nap() -> None:
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def _clean(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


_CARD_SPLIT = re.compile(r"<li>")
_RE_URN = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
_RE_LINK = re.compile(r'href="(https://[a-z]{0,3}\.?linkedin\.com/jobs/view/[^"?]+)')
_RE_TITLE = re.compile(r'base-search-card__title">\s*(.*?)\s*</h3>', re.S)
_RE_COMPANY = re.compile(r'hidden-nested-link"[^>]*>\s*(.*?)\s*</a>', re.S)
_RE_COMPANY_URL = re.compile(r'href="(https://[a-z.]*linkedin\.com/company/[^"?]+)')
_RE_LOCATION = re.compile(r'job-search-card__location">\s*(.*?)\s*</span>', re.S)
_RE_DATE = re.compile(r'datetime="([\d-]+)"')
_RE_SALARY = re.compile(r'job-search-card__salary-info">\s*(.*?)\s*</span>', re.S)


def parse_cards(markup: str) -> list[dict]:
    """Extract job records from a guest-search HTML fragment."""
    jobs: list[dict] = []
    for chunk in _CARD_SPLIT.split(markup):
        link = _RE_LINK.search(chunk)
        if not link:
            continue
        urn = _RE_URN.search(chunk)
        job_id = urn.group(1) if urn else link.group(1).rsplit("-", 1)[-1]
        jobs.append(
            {
                "source": "linkedin",
                "id": f"li:{job_id}",
                "title": _clean(_RE_TITLE.search(chunk).group(1)) if _RE_TITLE.search(chunk) else "",
                "company": _clean(_RE_COMPANY.search(chunk).group(1)) if _RE_COMPANY.search(chunk) else "",
                "company_url": _RE_COMPANY_URL.search(chunk).group(1) if _RE_COMPANY_URL.search(chunk) else "",
                "location": _clean(_RE_LOCATION.search(chunk).group(1)) if _RE_LOCATION.search(chunk) else "",
                "posted": _RE_DATE.search(chunk).group(1) if _RE_DATE.search(chunk) else "",
                "salary": _clean(_RE_SALARY.search(chunk).group(1)) if _RE_SALARY.search(chunk) else "",
                "url": link.group(1),
                "description": "",
            }
        )
    return jobs


def search(keywords: str, location: str, hours: int = 24, pages: int = 2,
           remote_only: bool = False, verbose: bool = True) -> list[dict]:
    """Run one guest search, walking `pages` pages of 10 results."""
    found: list[dict] = []
    for page in range(pages):
        params = {
            "keywords": keywords,
            "location": location,
            "f_TPR": f"r{hours * 3600}",
            "start": page * 10,
            "sortBy": "DD",
        }
        if remote_only:
            params["f_WT"] = "2"
        url = f"{GUEST_SEARCH}?{urllib.parse.urlencode(params)}"
        try:
            markup = _get_with_backoff(url)
        except Exception as exc:  # a dead query must not kill the whole run
            if verbose:
                print(f"  ! {keywords} @ {location} p{page}: {exc}")
            break
        batch = parse_cards(markup)
        if verbose:
            print(f"  . {keywords} @ {location} p{page}: {len(batch)} cards")
        found.extend(batch)
        if len(batch) < 10:  # short page means no more results
            break
        _nap()
    for job in found:
        job["query"] = keywords
        job["search_location"] = location
        job["remote_search"] = remote_only
    return found


def fetch_description(job_id: str, max_chars: int = 4000) -> str:
    """Pull the public job description for relevance scoring."""
    numeric = job_id.split(":", 1)[-1]
    try:
        markup = _get_with_backoff(GUEST_POSTING.format(job_id=numeric), attempts=2)
    except Exception:
        return ""
    match = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', markup, re.S)
    if not match:
        match = re.search(r'description__text[^>]*>(.*?)</section>', markup, re.S)
    body = match.group(1) if match else ""
    return _clean(body)[:max_chars]


def collect(config: dict, hours: int = 24, verbose: bool = True,
            out_path: str | None = None) -> list[dict]:
    """Run every role x location combination in the config.

    Writes partial results after each location when out_path is given, so an
    interrupted sweep still leaves usable output behind.
    """
    settings = config["sources"]["linkedin"]
    queries = list(config["roles"]["primary"]) + list(config["roles"].get("internship", []))
    seen_ids: set[str] = set()
    results: list[dict] = []

    for location in config["locations"]:
        for keywords in queries:
            batch = search(
                keywords,
                location["linkedin"],
                hours=hours,
                pages=settings.get("pages_per_query", 2),
                remote_only=location.get("remote_only", False),
                verbose=verbose,
            )
            for job in batch:
                if job["id"] in seen_ids:
                    continue
                seen_ids.add(job["id"])
                job["location_label"] = location["label"]
                results.append(job)
            _nap()
        if out_path:  # checkpoint after each location
            with open(out_path, "w") as fh:
                json.dump(results, fh)
            if verbose:
                print(f"  checkpoint: {len(results)} postings after {location['label']}")
    if verbose:
        print(f"LinkedIn: {len(results)} unique postings")
    return results


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hours", type=int, default=24)
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = json.load(fh)
    jobs = collect(cfg, hours=args.hours, out_path=args.out)
    with open(args.out, "w") as fh:
        json.dump(jobs, fh, indent=2)
    print(f"wrote {len(jobs)} jobs -> {args.out}")
