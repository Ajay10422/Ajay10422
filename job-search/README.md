# Job Radar

A twice-daily job hunt that runs itself. At **06:00** and **18:00**
America/Toronto a scheduled Claude session sweeps four sources, scores what it
finds against Ajay's resume, drops anything it has already shown, and sends one
brief by email plus a live Artifact page.

## What it searches

| Source | How | Notes |
|---|---|---|
| **LinkedIn** | `scripts/linkedin.py` | Public logged-out job endpoints only - no account, no cookies. Throttled with backoff. |
| **Indeed** | Indeed connector | Uses the resume and preferences already on the Indeed profile. |
| **Web / ATS** | WebSearch | Greenhouse, Lever, Ashby, Workable - where direct-apply links live. |
| **Gmail** | Gmail connector | Splits real human outreach from the ~15-20 daily alert blasts. |

## Why the mail scan is split three ways

The inbox receives far more automated job alerts than actual messages. A naive
"check my mail for job invites" returns about 200 threads a fortnight, of which
a couple are a person writing to Ajay. So the run sorts into:

- **Needs a reply** - a human wrote it *and* Ajay has not already answered
  (if the newest message in the thread is his, it is not waiting on him).
- **Application updates** - receipts, assessments, interview requests, rejections.
- **Alert blasts** - counted, never quoted. If one names a strong role, that
  role is added to the job list instead.

## Scoring

`scripts/store.py` scores each posting against the resume skills in
`config.json`. Title matches count triple. Seniority above Ajay's band
(principal, staff, manager) is penalised; intern, co-op, junior and remote get
a small bonus; a posting from the last 24 hours gets a freshness bump.
Anything under `filters.min_score` drops to a secondary "Also open" section.

Matching is word-boundary anchored, so `rag` does not fire inside
*leverage* - but `agent` still matches *agents* and *agentic*.

## Dedupe

`state/seen_jobs.json` remembers every posting already sent, for 45 days, so
the 18:00 brief never repeats the 06:00 one. It is the only file a run commits.

> **Privacy.** This repository is public. The seen store holds public job
> facts only - id, title, company, URL. Nothing from the inbox is ever
> committed; recruiter names and email subjects exist only in the email and
> the private Artifact.

## Changing what it looks for

Edit `config.json` - roles, locations, filters and scoring weights all live
there. The scripts read it; they do not hardcode anything.

```jsonc
"roles":    { "primary": [...], "internship": [...] },
"locations":[ { "label": "Ontario", "linkedin": "...", "indeed": "..." } ],
"filters":  { "max_age_days": 30, "min_score": 10, "exclude_title_keywords": [...] }
```

To pause the automation, disable the two Routines in Claude; to change the
times, edit their cron expressions. Both are named `Job Radar - morning/evening`.

## Running it by hand

```bash
cd job-search
python3 scripts/linkedin.py --config config.json --out /tmp/jobradar/linkedin.json
python3 scripts/run.py --config config.json --state state/seen_jobs.json \
  --outdir /tmp/jobradar --linkedin-cache /tmp/jobradar/linkedin.json \
  --run-label Morning --dry-run
```

`--dry-run` skips updating the seen store, so you can re-run without burning
the postings. Outputs land in `/tmp/jobradar/`: `digest.json`,
`digest.email.html`, `digest.artifact.html`, `digest.md`.

`PLAYBOOK.md` is the full step-by-step the scheduled session follows.

## Files

```
job-search/
├── PLAYBOOK.md            what each scheduled run does, step by step
├── config.json            roles, locations, filters, scoring weights
├── scripts/
│   ├── linkedin.py        public guest-endpoint search + description fetch
│   ├── store.py           scoring, filtering, cross-source dedupe, seen store
│   ├── digest.py          email HTML, artifact HTML, markdown renderers
│   └── run.py             orchestrates a run end to end
└── state/
    └── seen_jobs.json     public job ids already sent (committed)
```
