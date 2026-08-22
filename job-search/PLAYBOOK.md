# Job Radar - run playbook

A scheduled session follows this file top to bottom. It runs twice a day
(06:00 and 18:00 America/Toronto) and produces one brief: new job postings
matched against Ajay's resume, plus anything in the inbox that needs a human
reply.

## Hard rules

1. **Never commit anything derived from the inbox.** `Ajay10422/Ajay10422` is a
   public profile repo. Only `state/seen_jobs.json` (public job ids, titles,
   companies, URLs) is committed. Recruiter names, email subjects and snippets
   go in the email and the Artifact only.
2. **Never apply to anything, never send a reply to a recruiter, never mark
   mail read.** This job is read-only reconnaissance. It reports; Ajay decides.
3. **A failing source must not kill the run.** Catch it, add a line to
   `errors`, carry on with the other sources. A brief with three of four
   sources is worth sending; a crashed run is not.
4. **LinkedIn: public guest endpoints only.** No login, no cookies, no
   authenticated scraping. `scripts/linkedin.py` already throttles and backs
   off - do not raise its request rate.

## Step 0 - Check which tools this session actually has

Routines created through the API do not carry connector grants, so a scheduled
run may start without `Gmail:*` or `Indeed:*` tools. Check before you plan the
run, and degrade deliberately rather than crashing:

| Missing | What to do |
|---|---|
| `Indeed:*` | Skip Step 1. Note `"Indeed connector unavailable"` in errors. LinkedIn and the ATS boards still carry the run. |
| `Gmail:*` search | Skip Step 3 entirely. Note `"Gmail connector unavailable - inbox not scanned"`. Say so in your final report; it is the part Ajay most notices missing. |
| `Gmail:send_message` | You cannot email the brief. Instead **put the whole brief in your final report message** - the Routine's completion notification pushes that to Ajay's phone and inbox, so it is the fallback delivery channel. Lead with anything needing a reply, then the top matches as markdown links. |
| `Artifact` | Skip Step 5. Deliver by email and report only. |

Never silently drop a source. Every skipped step becomes a line in `errors`,
which the digest prints in its footer, and a sentence in your final report.

If the connectors are missing two runs in a row, say plainly in your report
that the Routine needs to be recreated from the claude.ai Routines UI with
Gmail and Indeed attached - that is the only way to grant them.

## Setup

```bash
cd /home/user/Ajay10422
git checkout claude/daily-job-search-automation-56x827
git pull origin claude/daily-job-search-automation-56x827
mkdir -p /tmp/jobradar
```

Read `job-search/config.json` - it holds the target roles, locations, filters
and scoring weights. Change behaviour by editing that file, not the scripts.

## Step 1 - Indeed (connector)

Call `Indeed:search_jobs` once per role x location. Roles are in
`config.roles.primary` + `config.roles.internship`; locations in
`config.locations` (use the `indeed` and `country` fields). Start with the six
primary roles across `Ontario`, `remote`, and `Toronto, Ontario`.

Optionally call `Indeed:get_resume` first if you want to confirm preferences
have not changed since the config was written.

Convert every result to this shape and write the array to
`/tmp/jobradar/indeed.json`:

```json
[{"source":"indeed","id":"in:<job id>","title":"...","company":"...",
  "location":"...","posted":"YYYY-MM-DD","url":"<the apply URL, unmodified>",
  "salary":"","description":""}]
```

Keep Indeed's URLs exactly as returned - they carry tracking parameters that
the apply flow needs. Convert "August 20, 2026" style dates to ISO.

## Step 2 - Web and ATS boards

Company career pages are where direct-apply links live. Run `WebSearch` for
each of these shapes (substitute roles from the config):

- `"GenAI Engineer" Toronto site:boards.greenhouse.io`
- `"AI Engineer" Canada remote site:jobs.lever.co`
- `"LLM Engineer" Ontario site:jobs.ashbyhq.com`
- `"Machine Learning Engineer" Toronto hiring 2026`
- `"AI Engineer intern" OR "AI co-op" Canada 2026`

Keep only results that are a specific job posting (a URL naming one role), not
a board index or a listicle. Where the posting date is not visible, leave
`posted` empty - the age filter skips blanks rather than guessing.

Write to `/tmp/jobradar/web.json` in the same shape, `"source":"web"`.

## Step 3 - Gmail, three buckets

The inbox takes roughly 15-20 automated job alerts a day, plus Facebook
Marketplace and newsletters. The alerts are noise; the signal is a person
writing to Ajay. Sorting them is the most valuable thing this run does.

**Bucket A - needs a reply.** Query (this exclusion list was tuned against the
real inbox - a looser query returns ~200 threads of which ~2 matter):

```
newer_than:1d -in:sent -in:draft
-from:facebookmail.com -from:jobs2web.com -from:joinhandshake.com
-from:jobalert.indeed.com -from:linkedin.com -from:indeedapply@indeed.com
-from:noreply -from:no-reply -from:donotreply -from:notifications
(recruiter OR staffing OR "reaching out" OR "your resume" OR "your profile"
 OR interview OR "your application" OR hiring OR "this position" OR "the role")
```

Then apply two rules that the query itself cannot express:

1. **Read the thread.** Call `Gmail:get_thread` with
   `messageFormat: PLAIN_TEXT`. Search previews only show a thread's *oldest*
   messages, so a thread Ajay already answered looks unanswered in the preview.
2. **Drop anything he has already answered.** If the newest message in the
   thread was sent by `ajaykrishna10422@gmail.com`, the ball is not in his
   court - leave it out. This is the rule that keeps the section honest.

Keep a thread only if a person wrote it. Record:

```json
{"from":"Name - Company <addr>","subject":"...","date":"YYYY-MM-DD",
 "snippet":"what they want, and your read on whether it fits",
 "url":"https://mail.google.com/mail/u/0/#inbox/<threadId>"}
```

In the snippet, say plainly if the role is off-band (a contract asking for 8+
years, a sales role, a different stack). Ajay still decides, but he should not
have to open the mail to find that out.

**Bucket B - application updates.** Automated, but about *his own*
applications: "we received your application", assessments, interview
scheduling, rejections. Typical senders are `indeedapply@indeed.com`,
`*@talent.icims.com`, `*@myworkday.com`, `*.hr@adp.com`, `rise@risepeople.com`,
`hire@peoplepilot.io`. Query:

```
newer_than:1d -in:sent (from:indeedapply@indeed.com OR from:talent.icims.com
 OR from:myworkday.com OR from:adp.com OR from:risepeople.com
 OR from:peoplepilot.io OR subject:("your application" OR "application received"
 OR interview OR assessment OR offer))
```

Title, sender and date is enough - these go in `status_updates`. Where the body
reads as a rejection or an interview request rather than a receipt, say so in
the subject line you record.

**Bucket C - alert blasts.** Do not list these. Count them into
`alerts_summary.count`. If an alert names a role that looks like a strong
match, add it to `web.json` as a job rather than quoting the email.

Write `/tmp/jobradar/mail.json`:

```json
{"outreach":[...],"status_updates":[...],"alerts_summary":{"count":0}}
```

## Step 4 - Collect, score and render

LinkedIn is paced deliberately and takes 4-6 minutes, so start it in the
background as the *first* action of the run, before Step 1, and let it scrape
while the connector work happens:

```bash
cd /home/user/Ajay10422/job-search
nohup python3 scripts/linkedin.py --config config.json \
  --out /tmp/jobradar/linkedin.json --hours 24 > /tmp/jobradar/linkedin.log 2>&1 &
```

Then by the time Steps 1-3 are done it is finished, and `--linkedin-cache`
picks the results up instead of scraping again. This step merges every source,
drops anything already sent in an earlier brief, scores what is left against
the resume, and renders the outputs.

```bash
cd /home/user/Ajay10422/job-search
python3 scripts/run.py \
  --config config.json \
  --state state/seen_jobs.json \
  --outdir /tmp/jobradar \
  --linkedin-cache /tmp/jobradar/linkedin.json \
  --extra /tmp/jobradar/indeed.json \
  --extra /tmp/jobradar/web.json \
  --mail /tmp/jobradar/mail.json \
  --hours 24 \
  --run-label "Morning"
```

Use `--run-label "Evening"` on the 18:00 run. LinkedIn collection takes a few
minutes - it deliberately paces its requests.

Outputs land in `/tmp/jobradar/`: `digest.json`, `digest.email.html`,
`digest.artifact.html`, `digest.md`.

## Step 5 - Publish the Artifact

There is one long-lived "Job Radar" artifact that each run updates in place, so
the link Ajay keeps stays current.

Publish `/tmp/jobradar/digest.artifact.html` with the `url` from
`config.delivery.artifact_url` so it redeploys to the same address, with
`favicon: "📡"`. Keep the title as **Job Radar** - do not rename it.

If that publish fails because the artifact was deleted, publish without `url`,
then write the new address back into `config.delivery.artifact_url` and commit
that change alongside the seen store.

Then write the artifact URL into the digest so the email can link to it:

```bash
python3 - <<'PY'
import json
p = "/tmp/jobradar/digest.json"
d = json.load(open(p))
d["artifact_url"] = "<the artifact URL>"
json.dump(d, open(p, "w"), indent=2)
import sys; sys.path.insert(0, "/home/user/Ajay10422/job-search/scripts")
import digest
open("/tmp/jobradar/digest.email.html", "w").write(digest.render_email_html(d))
PY
```

## Step 6 - Email the brief

Send with `Gmail:send_message`:

- `to`: `ajaykrishna10422@gmail.com`
- `subject`: `Job Radar - <N> strong matches, <M> needing a reply` (use the
  real counts from `digest.json`; if both are zero, say `quiet run`)
- `htmlBody`: the contents of `/tmp/jobradar/digest.email.html`
- `body`: the contents of `/tmp/jobradar/digest.md` as the plain-text fallback

## Step 7 - Save the dedupe state

`run.py` has already updated `state/seen_jobs.json`. Commit only that file:

```bash
cd /home/user/Ajay10422
git add job-search/state/seen_jobs.json
git commit -m "Job Radar: <YYYY-MM-DD> <morning|evening> run"
git push -u origin claude/daily-job-search-automation-56x827
```

If the push fails on a network error, retry up to 4 times with 2s/4s/8s/16s
backoff. If it still fails, say so in the final message - the brief has already
been delivered, only the dedupe memory is behind.

## Step 8 - Report

Finish with a short summary: counts per source, the top three matches by score,
anything in "needs a reply", and any entry in `errors`. If a source failed two
runs in a row, say so plainly - that is a broken pipe, not a blip.
