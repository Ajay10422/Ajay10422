"""Render the job-search digest as email HTML, artifact HTML, and markdown."""
from __future__ import annotations

import html
import json

# --- palette (shared by both renderers) -------------------------------------
PINE = "#146B57"
RUST = "#A63D2F"
INK = "#12181A"
MUTED = "#5A6A66"
LINE = "#D9E0DB"
BG = "#F2F4F1"


def esc(text) -> str:
    return html.escape(str(text or ""))


def clip(text: str, limit: int) -> str:
    """Trim to a word boundary so a snippet never ends mid-word."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:.- ") + "\u2026"


def _score_band(score: int) -> tuple[str, str]:
    """Bands are calibrated against real runs.

    Only LinkedIn's top hits get their description fetched, so a posting scored
    on its title alone lands around 15-20 even when it is a good fit. Thresholds
    sit low enough that those still read as "good".
    """
    if score >= 30:
        return "strong", PINE
    if score >= 15:
        return "good", PINE
    return "fair", MUTED


# --- markdown ---------------------------------------------------------------
def render_markdown(d: dict) -> str:
    out = [f"# Job Radar - {d['run_label']} brief", "", f"_{d['generated']}_", ""]
    c = d["counts"]
    out.append(
        f"**{c.get('strong', 0)} strong matches** - {c.get('new', 0)} new postings "
        f"from {c.get('seen_total', 0)} scanned - "
        f"{len(d.get('outreach', []))} needing a reply"
    )
    out.append("")

    if d.get("outreach"):
        out += ["## Needs a reply", ""]
        for m in d["outreach"]:
            out.append(f"- **{m['subject']}** - {m['from']} ({m['date']})")
            if m.get("snippet"):
                out.append(f"  - {m['snippet']}")
            if m.get("url"):
                out.append(f"  - {m['url']}")
        out.append("")

    if d.get("status_updates"):
        out += ["## Application updates", ""]
        for m in d["status_updates"]:
            out.append(f"- {m['subject']} - {m['from']} ({m['date']})")
        out.append("")

    for key, heading in (("strong", "Top matches"), ("weak", "Also open")):
        if not d.get(key):
            continue
        out += [f"## {heading}", ""]
        for j in d[key]:
            meta = " · ".join(filter(None, [j.get("company"), j.get("location"), j.get("posted")]))
            out.append(f"- **[{j.get('title')}]({j.get('url')})** ({j.get('score', 0)}) - {meta}")
            if j.get("matched_skills"):
                out.append(f"  - matches: {', '.join(j['matched_skills'])}")
        out.append("")

    if d.get("errors"):
        out += ["## Run notes", ""] + [f"- {e}" for e in d["errors"]] + [""]
    return "\n".join(out)


# --- email HTML (inline styles only - Gmail strips most CSS) ----------------
def _email_job_row(j: dict) -> str:
    band, colour = _score_band(j.get("score", 0))
    meta = " &middot; ".join(
        esc(x) for x in filter(None, [j.get("company"), j.get("location"), j.get("posted")])
    )
    badges = [j.get("source", "")] + list(j.get("also_on", []))
    badge_html = "".join(
        f'<span style="display:inline-block;font:11px/1.6 ui-monospace,Menlo,monospace;'
        f'color:{MUTED};border:1px solid {LINE};border-radius:3px;padding:0 5px;'
        f'margin-right:4px;text-transform:uppercase;letter-spacing:.06em">{esc(b)}</span>'
        for b in badges if b
    )
    skills = ""
    if j.get("matched_skills"):
        skills = (
            f'<div style="font:12px/1.7 -apple-system,Segoe UI,Roboto,sans-serif;'
            f'color:{MUTED};margin-top:3px">matches: {esc(", ".join(j["matched_skills"]))}</div>'
        )
    salary = ""
    if j.get("salary"):
        salary = (
            f'<div style="font:12px/1.7 -apple-system,Segoe UI,Roboto,sans-serif;'
            f'color:{PINE};margin-top:2px">{esc(j["salary"])}</div>'
        )
    return f"""
    <tr>
      <td valign="top" style="padding:11px 10px 11px 0;border-bottom:1px solid {LINE};width:44px">
        <div style="font:600 15px/1.2 ui-monospace,Menlo,monospace;color:{colour};
                    font-variant-numeric:tabular-nums">{j.get('score', 0)}</div>
        <div style="font:10px/1.4 ui-monospace,Menlo,monospace;color:{MUTED};
                    text-transform:uppercase;letter-spacing:.07em">{band}</div>
      </td>
      <td valign="top" style="padding:11px 0;border-bottom:1px solid {LINE}">
        <a href="{esc(j.get('url'))}" style="font:600 15px/1.35 -apple-system,Segoe UI,Roboto,sans-serif;
           color:{INK};text-decoration:none">{esc(j.get('title'))}</a>
        <div style="font:13px/1.7 -apple-system,Segoe UI,Roboto,sans-serif;color:{MUTED};
                    margin-top:2px">{meta}</div>
        {salary}{skills}
        <div style="margin-top:6px">{badge_html}</div>
      </td>
    </tr>"""


def _email_mail_row(m: dict, colour: str) -> str:
    link_open = f'<a href="{esc(m.get("url"))}" style="color:{INK};text-decoration:none">' if m.get("url") else ""
    link_close = "</a>" if m.get("url") else ""
    snippet = ""
    if m.get("snippet"):
        snippet = (
            f'<div style="font:13px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:{MUTED};'
            f'margin-top:3px">{esc(clip(m["snippet"], 220))}</div>'
        )
    return f"""
    <tr><td style="padding:10px 0;border-bottom:1px solid {LINE};border-left:3px solid {colour};
                   padding-left:11px">
      {link_open}<span style="font:600 15px/1.35 -apple-system,Segoe UI,Roboto,sans-serif;
        color:{INK}">{esc(m.get('subject'))}</span>{link_close}
      <div style="font:13px/1.7 -apple-system,Segoe UI,Roboto,sans-serif;color:{MUTED};margin-top:2px">
        {esc(m.get('from'))} &middot; {esc(m.get('date'))}</div>
      {snippet}
    </td></tr>"""


EMAIL_MAX_JOBS = 15  # the email is a phone glance; the artifact holds the rest


def render_email_html(d: dict) -> str:
    c = d["counts"]
    shown = d.get("strong", [])[:EMAIL_MAX_JOBS]
    hidden = max(0, len(d.get("strong", [])) - EMAIL_MAX_JOBS) + d.get("strong_overflow", 0)
    stats = [
        ("strong matches", c.get("strong", 0), PINE),
        ("new postings", c.get("new", 0), INK),
        ("needs a reply", len(d.get("outreach", [])), RUST if d.get("outreach") else INK),
    ]
    stat_cells = "".join(
        f"""<td style="padding:0 22px 0 0">
              <div style="font:600 26px/1.1 ui-monospace,Menlo,monospace;color:{col};
                          font-variant-numeric:tabular-nums">{val}</div>
              <div style="font:11px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:{MUTED};
                          text-transform:uppercase;letter-spacing:.07em">{esc(label)}</div>
            </td>"""
        for label, val, col in stats
    )

    blocks = []
    if d.get("outreach"):
        blocks.append(("Needs a reply", "".join(_email_mail_row(m, RUST) for m in d["outreach"])))
    if d.get("status_updates"):
        blocks.append(("Application updates",
                       "".join(_email_mail_row(m, MUTED) for m in d["status_updates"])))
    if shown:
        label = "Top matches" if not hidden else f"Top {len(shown)} matches"
        blocks.append((label, "".join(_email_job_row(j) for j in shown)))
    if d.get("weak"):
        blocks.append(("Also open", "".join(_email_job_row(j) for j in d["weak"])))

    sections = "".join(
        f"""<tr><td style="padding:26px 0 4px">
              <div style="font:600 12px/1.6 ui-monospace,Menlo,monospace;color:{PINE};
                          text-transform:uppercase;letter-spacing:.1em">{esc(title)}</div>
            </td></tr>
            <tr><td><table width="100%" cellpadding="0" cellspacing="0"
                     style="border-collapse:collapse">{rows}</table></td></tr>"""
        for title, rows in blocks
    )

    if not blocks:
        sections = (
            f'<tr><td style="padding:26px 0;font:15px/1.7 -apple-system,Segoe UI,Roboto,sans-serif;'
            f'color:{MUTED}">Nothing new cleared the bar this run. '
            f'{c.get("repeat", 0)} postings were already in an earlier brief.</td></tr>'
        )

    footer_bits = []
    if hidden:
        footer_bits.append(f"{hidden} more matches on the full brief")
    footer_bits += [
        f"{c.get('seen_total', 0)} postings scanned",
        f"{c.get('repeat', 0)} already sent",
        f"{c.get('dropped', 0)} filtered out",
    ]
    if d.get("alerts_summary", {}).get("count"):
        footer_bits.append(f"{d['alerts_summary']['count']} alert emails folded in")
    notes = ""
    if d.get("errors"):
        notes = (
            f'<div style="margin-top:8px;color:{RUST}">'
            + "<br>".join(esc(e) for e in d["errors"]) + "</div>"
        )
    artifact_link = ""
    if d.get("artifact_url"):
        artifact_link = (
            f'<div style="margin-top:14px"><a href="{esc(d["artifact_url"])}" '
            f'style="font:13px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:{PINE}">'
            f'Open the full brief &rarr;</a></div>'
        )

    return f"""<div style="background:{BG};padding:24px 12px;margin:0">
<table align="center" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;
       background:#FFFFFF;border:1px solid {LINE};border-radius:6px;border-collapse:separate">
  <tr><td style="padding:26px 28px">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td><div style="font:600 20px/1.25 Georgia,'Times New Roman',serif;color:{INK}">
            Job Radar</div>
          <div style="font:13px/1.7 -apple-system,Segoe UI,Roboto,sans-serif;color:{MUTED}">
            {esc(d['run_label'])} brief &middot; {esc(d['generated'])}</div></td>
    </tr></table>

    <table cellpadding="0" cellspacing="0" style="margin-top:20px;padding-top:18px;
           border-top:1px solid {LINE}"><tr>{stat_cells}</tr></table>

    <table width="100%" cellpadding="0" cellspacing="0">{sections}</table>

    <div style="margin-top:26px;padding-top:14px;border-top:1px solid {LINE};
                font:12px/1.7 -apple-system,Segoe UI,Roboto,sans-serif;color:{MUTED}">
      {esc(' · '.join(footer_bits))}<br>
      Sources: {esc(', '.join(d.get('sources_ran', [])))}
      {notes}{artifact_link}
    </div>
  </td></tr>
</table></div>"""


# --- artifact HTML ----------------------------------------------------------
ARTIFACT_CSS = """
:root{
  --bg:#F2F4F1; --surface:#FFFFFF; --ink:#12181A; --muted:#5A6A66;
  --line:#D9E0DB; --accent:#146B57; --hot:#A63D2F; --chip:#EDF1EE;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0E1412; --surface:#161E1B; --ink:#E8EDEA; --muted:#93A39D;
    --line:#26312D; --accent:#4FBF9F; --hot:#E08471; --chip:#1D2724;
  }
}
:root[data-theme="dark"]{
  --bg:#0E1412; --surface:#161E1B; --ink:#E8EDEA; --muted:#93A39D;
  --line:#26312D; --accent:#4FBF9F; --hot:#E08471; --chip:#1D2724;
}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);margin:0;
     font-family:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
     font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:760px;margin:0 auto;padding:48px 20px 72px}
header{border-bottom:1px solid var(--line);padding-bottom:22px}
h1{font-family:Newsreader,Georgia,serif;font-weight:600;font-size:clamp(30px,5vw,42px);
   line-height:1.1;margin:0;letter-spacing:-.01em;text-wrap:balance}
.sub{color:var(--muted);font-size:14px;margin-top:6px}
.stats{display:flex;flex-wrap:wrap;gap:32px;margin:24px 0 0}
.stat .n{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:34px;font-weight:600;
         line-height:1;font-variant-numeric:tabular-nums}
.stat .l{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;color:var(--muted);
         text-transform:uppercase;letter-spacing:.1em;margin-top:6px}
.n.accent{color:var(--accent)} .n.hot{color:var(--hot)}
h2{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12px;font-weight:600;
   color:var(--accent);text-transform:uppercase;letter-spacing:.12em;
   margin:44px 0 4px;padding-bottom:8px;border-bottom:1px solid var(--line)}
.job{display:grid;grid-template-columns:56px 1fr;gap:16px;padding:16px 0;
     border-bottom:1px solid var(--line)}
.score{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:19px;font-weight:600;
       font-variant-numeric:tabular-nums;color:var(--accent);line-height:1.2}
.band{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:10px;color:var(--muted);
      text-transform:uppercase;letter-spacing:.08em}
.job a.t{font-size:17px;font-weight:600;color:var(--ink);text-decoration:none;
         line-height:1.35;display:inline-block}
.job a.t:hover{color:var(--accent);text-decoration:underline}
.meta{color:var(--muted);font-size:14px;margin-top:2px}
.pay{color:var(--accent);font-size:13px;margin-top:2px}
.chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.chip{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;color:var(--muted);
      background:var(--chip);border:1px solid var(--line);border-radius:3px;padding:1px 6px}
.chip.src{text-transform:uppercase;letter-spacing:.06em}
.mail{border-left:3px solid var(--hot);padding:12px 0 12px 14px;margin-top:14px;
      background:var(--surface);border-radius:0 4px 4px 0}
.mail.quiet{border-left-color:var(--muted)}
.mail .s{font-size:16px;font-weight:600;color:var(--ink);text-decoration:none}
.mail .s:hover{color:var(--accent)}
.empty{color:var(--muted);padding:24px 0}
footer{margin-top:48px;padding-top:16px;border-top:1px solid var(--line);
       color:var(--muted);font-size:13px}
a:focus-visible,.job a:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
@media (max-width:520px){.job{grid-template-columns:44px 1fr;gap:12px}.stats{gap:22px}}
"""


def _artifact_job(j: dict) -> str:
    band, _ = _score_band(j.get("score", 0))
    meta = " &middot; ".join(
        esc(x) for x in filter(None, [j.get("company"), j.get("location"), j.get("posted")])
    )
    chips = "".join(
        f'<span class="chip src">{esc(b)}</span>'
        for b in [j.get("source", "")] + list(j.get("also_on", [])) if b
    )
    chips += "".join(f'<span class="chip">{esc(s)}</span>' for s in j.get("matched_skills", []))
    pay = f'<div class="pay">{esc(j["salary"])}</div>' if j.get("salary") else ""
    return f"""<article class="job">
  <div><div class="score">{j.get('score', 0)}</div><div class="band">{band}</div></div>
  <div>
    <a class="t" href="{esc(j.get('url'))}" target="_blank" rel="noopener">{esc(j.get('title'))}</a>
    <div class="meta">{meta}</div>{pay}
    <div class="chips">{chips}</div>
  </div>
</article>"""


def _artifact_mail(m: dict, quiet: bool = False) -> str:
    cls = "mail quiet" if quiet else "mail"
    subject = esc(m.get("subject"))
    if m.get("url"):
        subject = f'<a class="s" href="{esc(m["url"])}" target="_blank" rel="noopener">{subject}</a>'
    else:
        subject = f'<span class="s">{subject}</span>'
    snippet = f'<div class="meta">{esc(clip(m["snippet"], 260))}</div>' if m.get("snippet") else ""
    return f"""<div class="{cls}">{subject}
  <div class="meta">{esc(m.get('from'))} &middot; {esc(m.get('date'))}</div>{snippet}</div>"""


def render_artifact_html(d: dict) -> str:
    c = d["counts"]
    body = []
    if d.get("outreach"):
        body.append("<h2>Needs a reply</h2>")
        body += [_artifact_mail(m) for m in d["outreach"]]
    if d.get("status_updates"):
        body.append("<h2>Application updates</h2>")
        body += [_artifact_mail(m, quiet=True) for m in d["status_updates"]]
    if d.get("strong"):
        body.append("<h2>Top matches</h2>")
        body += [_artifact_job(j) for j in d["strong"]]
    if d.get("weak"):
        body.append("<h2>Also open</h2>")
        body += [_artifact_job(j) for j in d["weak"]]
    if not body:
        body.append(
            f'<p class="empty">Nothing new cleared the bar this run. '
            f'{c.get("repeat", 0)} postings were already in an earlier brief.</p>'
        )

    notes = ""
    if d.get("errors"):
        notes = "<br>".join(esc(e) for e in d["errors"])
        notes = f'<div style="color:var(--hot);margin-top:8px">{notes}</div>'

    return f"""<title>Job Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{ARTIFACT_CSS}</style>
<div class="wrap">
  <header>
    <h1>Job Radar</h1>
    <div class="sub">{esc(d['run_label'])} brief &middot; {esc(d['generated'])}</div>
    <div class="stats">
      <div class="stat"><div class="n accent">{c.get('strong', 0)}</div>
        <div class="l">strong matches</div></div>
      <div class="stat"><div class="n">{c.get('new', 0)}</div>
        <div class="l">new postings</div></div>
      <div class="stat"><div class="n {'hot' if d.get('outreach') else ''}">{len(d.get('outreach', []))}</div>
        <div class="l">needs a reply</div></div>
      <div class="stat"><div class="n">{c.get('seen_total', 0)}</div>
        <div class="l">scanned</div></div>
    </div>
  </header>
  {''.join(body)}
  <footer>
    {f"{d['strong_overflow']} more matches not shown &middot; " if d.get('strong_overflow') else ""}
    {c.get('repeat', 0)} already sent in an earlier brief &middot;
    {c.get('dropped', 0)} filtered out &middot;
    sources: {esc(', '.join(d.get('sources_ran', [])))}
    {notes}
  </footer>
</div>"""


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--digest", required=True)
    ap.add_argument("--email-out")
    ap.add_argument("--artifact-out")
    ap.add_argument("--markdown-out")
    args = ap.parse_args()

    with open(args.digest) as fh:
        data = json.load(fh)
    if args.email_out:
        open(args.email_out, "w").write(render_email_html(data))
    if args.artifact_out:
        open(args.artifact_out, "w").write(render_artifact_html(data))
    if args.markdown_out:
        open(args.markdown_out, "w").write(render_markdown(data))
    print("rendered")
