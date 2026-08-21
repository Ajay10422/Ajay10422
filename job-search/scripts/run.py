"""Job Radar run: collect, score, dedupe, render.

LinkedIn is scraped here. Indeed, web/ATS and Gmail results are gathered by the
agent (they need connectors) and handed in with --extra as JSON arrays.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import digest as digest_mod  # noqa: E402
import linkedin as li  # noqa: E402
import store  # noqa: E402


def load_extra(paths: list[str], errors: list[str]) -> list[dict]:
    jobs: list[dict] = []
    for path in paths or []:
        if not os.path.exists(path):
            errors.append(f"missing input: {os.path.basename(path)}")
            continue
        try:
            with open(path) as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            errors.append(f"bad JSON in {os.path.basename(path)}: {exc}")
            continue
        for job in data:
            job.setdefault("source", "web")
            job.setdefault("description", "")
            if not job.get("id"):
                job["id"] = f"{job['source']}:{abs(hash(job.get('url', job.get('title', ''))))}"
            jobs.append(job)
    return jobs


def enrich(buckets: dict, config: dict, errors: list[str]) -> None:
    """Fetch descriptions for the best-looking LinkedIn hits, for real scoring."""
    limit = config["sources"]["linkedin"].get("fetch_descriptions_top_n", 12)
    ranked = [j for j in buckets["strong"] + buckets["weak"] if j.get("source") == "linkedin"]
    ranked.sort(key=lambda j: j.get("score", 0), reverse=True)
    fetched = 0
    for job in ranked[:limit]:
        if job.get("description"):
            continue
        try:
            job["description"] = li.fetch_description(job["id"])
            fetched += 1
        except Exception as exc:
            errors.append(f"description fetch failed for {job['id']}: {exc}")
            break
    if fetched:
        print(f"enriched {fetched} postings with descriptions")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--extra", action="append", default=[])
    ap.add_argument("--mail", help="JSON with outreach/status_updates/alerts_summary")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--run-label", default="Morning")
    ap.add_argument("--timezone", default="America/Toronto")
    ap.add_argument("--no-linkedin", action="store_true")
    ap.add_argument("--linkedin-cache", help="reuse this file if it exists, "
                    "otherwise scrape into it (lets the scrape run in parallel)")
    ap.add_argument("--dry-run", action="store_true", help="do not update the seen store")
    args = ap.parse_args()

    with open(args.config) as fh:
        config = json.load(fh)
    seen = store.load_seen(args.state)
    errors: list[str] = []
    sources_ran: list[str] = []

    jobs: list[dict] = []
    if not args.no_linkedin and config["sources"]["linkedin"]["enabled"]:
        cache = args.linkedin_cache
        try:
            if cache and os.path.exists(cache):
                with open(cache) as fh:
                    found = json.load(fh)
                print(f"reusing {len(found)} cached LinkedIn postings")
            else:
                found = li.collect(config, hours=args.hours)
                if cache:
                    with open(cache, "w") as fh:
                        json.dump(found, fh)
            jobs += found
            sources_ran.append("LinkedIn")
        except Exception as exc:
            errors.append(f"LinkedIn collection failed: {exc}")

    extra = load_extra(args.extra, errors)
    if extra:
        for label in sorted({j.get("source", "web") for j in extra}):
            sources_ran.append(label.title())
        jobs += extra

    print(f"collected {len(jobs)} raw postings from {len(sources_ran)} sources")

    buckets = store.process(jobs, config, seen)      # pass 1: titles only
    enrich(buckets, config, errors)                  # add descriptions to the best
    buckets = store.process(jobs, config, seen)      # pass 2: full scoring

    mail = {"outreach": [], "status_updates": [], "alerts_summary": {"count": 0}}
    if args.mail and os.path.exists(args.mail):
        try:
            with open(args.mail) as fh:
                mail.update(json.load(fh))
            sources_ran.append("Gmail")
        except json.JSONDecodeError as exc:
            errors.append(f"bad mail JSON: {exc}")

    now = dt.datetime.now(dt.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        now = now.astimezone(ZoneInfo(args.timezone))
        stamp = now.strftime("%a %d %b %Y, %-I:%M %p %Z")
    except Exception:
        stamp = now.strftime("%a %d %b %Y, %H:%M UTC")

    data = {
        "run_label": args.run_label,
        "generated": stamp,
        "counts": buckets["counts"],
        "strong": buckets["strong"][:30],
        "weak": buckets["weak"][:10],
        "strong_overflow": max(0, len(buckets["strong"]) - 30),
        "outreach": mail.get("outreach", []),
        "status_updates": mail.get("status_updates", []),
        "alerts_summary": mail.get("alerts_summary", {}),
        "sources_ran": sources_ran,
        "errors": errors,
    }

    os.makedirs(args.outdir, exist_ok=True)
    paths = {
        "digest.json": json.dumps(data, indent=2),
        "digest.email.html": digest_mod.render_email_html(data),
        "digest.artifact.html": digest_mod.render_artifact_html(data),
        "digest.md": digest_mod.render_markdown(data),
    }
    for name, content in paths.items():
        with open(os.path.join(args.outdir, name), "w") as fh:
            fh.write(content)

    if not args.dry_run:
        store.remember(seen, buckets["strong"] + buckets["weak"])
        store.save_seen(args.state, seen)

    counts = buckets["counts"]
    print(
        f"strong={counts['strong']} weak={counts['weak']} new={counts['new']} "
        f"repeat={counts['repeat']} dropped={counts['dropped']}"
    )
    if errors:
        print("run notes:")
        for err in errors:
            print(f"  - {err}")
    print(f"output -> {args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
