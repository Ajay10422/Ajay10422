"""Relevance scoring, filtering, and the committed seen-jobs store.

PRIVACY: the seen store is committed to a PUBLIC repo. It may only ever hold
public job-posting facts (id, title, company, url, date). Nothing derived from
the inbox goes in here.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

SEEN_VERSION = 1
RETENTION_DAYS = 45


def _today() -> str:
    return dt.date.today().isoformat()


def load_seen(path: str) -> dict:
    if not os.path.exists(path):
        return {"version": SEEN_VERSION, "jobs": {}}
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {"version": SEEN_VERSION, "jobs": {}}
    data.setdefault("jobs", {})
    return data


def save_seen(path: str, seen: dict) -> None:
    cutoff = (dt.date.today() - dt.timedelta(days=RETENTION_DAYS)).isoformat()
    seen["jobs"] = {
        key: val
        for key, val in seen["jobs"].items()
        if val.get("first_seen", "9999") >= cutoff
    }
    seen["version"] = SEEN_VERSION
    seen["updated"] = _today()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(seen, fh, indent=1, sort_keys=True)


def remember(seen: dict, jobs: list[dict]) -> None:
    """Record public facts only - this file lands in a public repo."""
    for job in jobs:
        seen["jobs"].setdefault(
            job["id"],
            {
                "first_seen": _today(),
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "url": job.get("url", ""),
            },
        )


def is_new(seen: dict, job: dict) -> bool:
    return job["id"] not in seen["jobs"]


def _age_days(posted: str) -> float | None:
    if not posted:
        return None
    try:
        return (dt.date.today() - dt.date.fromisoformat(posted[:10])).days
    except ValueError:
        return None


_SKILL_CACHE: dict[str, re.Pattern] = {}


def _skill_re(skill: str) -> re.Pattern:
    """Match on a word boundary so 'rag' does not fire inside 'leverage'.

    Anchored at the start only, so 'agent' still matches 'agents' and 'agentic'.
    """
    if skill not in _SKILL_CACHE:
        _SKILL_CACHE[skill] = re.compile(r"\b" + re.escape(skill), re.I)
    return _SKILL_CACHE[skill]


def score(job: dict, config: dict) -> tuple[int, list[str]]:
    """Score a posting against the resume. Returns (score, reasons)."""
    rules = config["scoring"]
    title = (job.get("title") or "").lower()
    body = (job.get("description") or "").lower()
    blob = f"{title} {body}"
    total = 0
    hits: list[str] = []

    for skill, weight in rules["skill_weights"].items():
        pattern = _skill_re(skill)
        in_title = bool(pattern.search(title))
        in_body = bool(pattern.search(body))
        if not (in_title or in_body):
            continue
        gain = weight * (rules["title_multiplier"] if in_title else 1)
        total += gain
        hits.append(skill)

    for term, penalty in rules["seniority_penalties"].items():
        if term in title:
            total += penalty

    for term, bonus in rules["bonuses"].items():
        if term in blob:
            total += bonus

    age = _age_days(job.get("posted", ""))
    if age is not None and age <= 1:
        total += 3
    return total, hits[:8]


def excluded(job: dict, config: dict) -> str | None:
    """Return a reason string if the job should be dropped, else None."""
    filters = config["filters"]
    title = (job.get("title") or "").lower()
    body = (job.get("description") or "").lower()

    for term in filters["exclude_title_keywords"]:
        if term.strip() and term.strip() in title:
            return f"title contains '{term.strip()}'"
    for term in filters["exclude_description_keywords"]:
        if body and term in body:
            return f"description contains '{term}'"

    age = _age_days(job.get("posted", ""))
    if age is not None and age > filters["max_age_days"]:
        return f"posted {age}d ago"
    return None


_NORM = re.compile(r"[^a-z0-9]+")


def _fingerprint(job: dict) -> str:
    """Same role at the same company across two boards is one job."""
    title = _NORM.sub("", (job.get("title") or "").lower())
    company = _NORM.sub("", (job.get("company") or "").lower())
    return f"{company}|{title}"


def dedupe_across_sources(jobs: list[dict]) -> list[dict]:
    """Collapse cross-board duplicates, keeping the first and noting the rest."""
    kept: dict[str, dict] = {}
    for job in jobs:
        key = _fingerprint(job)
        if not key.strip("|"):
            kept[job["id"]] = job
            continue
        if key in kept:
            existing = kept[key]
            others = existing.setdefault("also_on", [])
            label = job.get("source", "?")
            if label not in others and label != existing.get("source"):
                others.append(label)
                existing.setdefault("alt_urls", []).append(job.get("url", ""))
            continue
        kept[key] = job
    return list(kept.values())


def process(jobs: list[dict], config: dict, seen: dict) -> dict:
    """Filter, score, dedupe. Returns buckets for the digest."""
    fresh, repeats, dropped = [], [], []

    for job in jobs:
        reason = excluded(job, config)
        if reason:
            dropped.append({**job, "drop_reason": reason})
            continue
        if not is_new(seen, job):
            repeats.append(job)
            continue
        fresh.append(job)

    fresh = dedupe_across_sources(fresh)
    for job in fresh:
        job["score"], job["matched_skills"] = score(job, config)

    min_score = config["filters"]["min_score"]
    strong = [j for j in fresh if j["score"] >= min_score]
    weak = [j for j in fresh if j["score"] < min_score]
    strong.sort(key=lambda j: j["score"], reverse=True)
    weak.sort(key=lambda j: j["score"], reverse=True)

    return {
        "strong": strong,
        "weak": weak,
        "repeats": repeats,
        "dropped": dropped,
        "counts": {
            "seen_total": len(jobs),
            "new": len(fresh),
            "strong": len(strong),
            "weak": len(weak),
            "repeat": len(repeats),
            "dropped": len(dropped),
        },
    }
