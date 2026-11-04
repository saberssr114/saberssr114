"""Generates animated cyan SVG cards (stats, languages, contribution calendar)
from your real GitHub data. Runs inside GitHub Actions using GITHUB_TOKEN."""
import os, json, sys, html, urllib.request
from datetime import datetime

USER = os.environ.get("GH_USER", "saberssr114")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "dist")
MOCK = os.environ.get("MOCK") == "1"

BG, BORDER, CYAN, TXT, MUTED = "#0a0f18", "#00b8e0", "#00dcff", "#c9f4ff", "#5f8fa3"
FONT = "'Fira Code','DejaVu Sans Mono',Consolas,monospace"

QUERY = """
query($login:String!){ user(login:$login){
  followers{totalCount}
  repositories(ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC,first:100){
    totalCount
    nodes{ stargazerCount languages(first:5,orderBy:{field:SIZE,direction:DESC}){ edges{size node{name color}} } }
  }
  contributionsCollection{
    totalCommitContributions totalPullRequestContributions totalIssueContributions
    contributionCalendar{ totalContributions weeks{ contributionDays{ contributionCount date } } }
  }
}}"""

def fetch():
    if MOCK:
        import random; random.seed(3)
        weeks = [{"contributionDays": [{"contributionCount": random.choice([0]*8+[1,2,4]), "date": f"2026-01-{(d%28)+1:02d}"} for d in range(7)]} for _ in range(53)]
        return {"followers":{"totalCount":5},"repositories":{"totalCount":4,"nodes":[
            {"stargazerCount":3,"languages":{"edges":[{"size":900,"node":{"name":"JavaScript","color":"#f1e05a"}},{"size":400,"node":{"name":"HTML","color":"#e34c26"}},{"size":200,"node":{"name":"CSS","color":"#563d7c"}}]}}]},
            "contributionsCollection":{"totalCommitContributions":30,"totalPullRequestContributions":2,"totalIssueContributions":1,
            "contributionCalendar":{"totalContributions":43,"weeks":weeks}}}
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in data: sys.exit(str(data["errors"]))
    return data["data"]["user"]

CSS = f"""
text{{font-family:{FONT}}}
@keyframes up{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes glow{{0%,100%{{stroke-opacity:.45}}50%{{stroke-opacity:1}}}}
.card{{animation:glow 4s ease-in-out infinite}}
"""

def frame(w, h, title, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>{CSS}</style>
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="8" fill="{BG}" stroke="{BORDER}" stroke-width="2" class="card"/>
<text x="24" y="32" fill="{CYAN}" font-size="16" font-weight="bold">[ {html.escape(title)} ]</text>
{body}
</svg>'''

def stats_card(u):
    cc = u["contributionsCollection"]
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])
    items = [("CONTRIBUTIONS", cc["contributionCalendar"]["totalContributions"]),
             ("COMMITS", cc["totalCommitContributions"]),
             ("PULL REQUESTS", cc["totalPullRequestContributions"]),
             ("REPOS", u["repositories"]["totalCount"]),
             ("STARS", stars),
             ("FOLLOWERS", u["followers"]["totalCount"])]
    body = ""
    for i, (label, val) in enumerate(items):
        x = 24 + (i % 3) * 272; y = 80 + (i // 3) * 62
        body += f'<g style="opacity:0;animation:up .6s ease {i*0.12:.2f}s forwards">'
        body += f'<text x="{x}" y="{y}" fill="{CYAN}" font-size="28" font-weight="bold">{val}</text>'
        body += f'<text x="{x}" y="{y+20}" fill="{MUTED}" font-size="12">[ {label} ]</text></g>'
    return frame(843, 190, "GITHUB STATS", body)

def langs_card(u):
    tot = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]; t = tot.setdefault(n["name"], [0, n["color"] or CYAN]); t[0] += e["size"]
    top = sorted(tot.items(), key=lambda kv: -kv[1][0])[:6]
    s = sum(v[0] for _, v in top) or 1
    body = ""; x = 24; bw = 795
    body += f'<rect x="24" y="52" width="{bw}" height="12" rx="6" fill="#0f1722"/>'
    for i, (name, (size, color)) in enumerate(top):
        w = bw * size / s
        body += f'<rect x="{x:.1f}" y="52" width="{w:.1f}" height="12" fill="{color}" style="transform-origin:{x:.1f}px 58px;transform:scaleX(0);animation:grow .9s ease {i*0.15:.2f}s forwards"/>'
        x += w
    for i, (name, (size, color)) in enumerate(top):
        lx = 24 + (i % 3) * 272; ly = 98 + (i // 3) * 28
        body += f'<g style="opacity:0;animation:up .5s ease {0.4+i*0.1:.2f}s forwards"><circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{color}"/>'
        body += f'<text x="{lx+18}" y="{ly}" fill="{TXT}" font-size="13">{html.escape(name)} <tspan fill="{MUTED}">{100*size/s:.1f}%</tspan></text></g>'
    return frame(843, 160, "TOP LANGUAGES", body)

def calendar_card(u):
    cal = u["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]; mx = max([d["contributionCount"] for w in weeks for d in w["contributionDays"]] + [1])
    levels = ["#0f1722", "#0a4a5e", "#0a7f9c", "#00b8e0", "#00dcff"]
    def lvl(c): return 0 if c == 0 else 1 + min(3, int(3 * (c - 1) / max(mx, 1) + (0.0 if mx == 1 else 0.5)))
    cell, gap, x0, y0 = 12, 3, 24, 78
    body = ""; last_m = None
    for wi, w in enumerate(weeks):
        x = x0 + wi * (cell + gap)
        for di, d in enumerate(w["contributionDays"]):
            y = y0 + di * (cell + gap); l = lvl(d["contributionCount"])
            body += f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{levels[l]}" stroke="#1b2733" style="opacity:0;animation:fade .5s ease {wi*0.025:.3f}s forwards"><title>{d["date"]}: {d["contributionCount"]}</title></rect>'
        m = datetime.strptime(w["contributionDays"][0]["date"], "%Y-%m-%d").strftime("%b")
        if m != last_m and wi < len(weeks) - 2:
            body += f'<text x="{x}" y="64" fill="{MUTED}" font-size="11">{m}</text>'; last_m = m
    total = cal["totalContributions"]
    body += f'<text x="819" y="32" fill="{TXT}" font-size="13" text-anchor="end">{total} contributions in the last year</text>'
    h = y0 + 7 * (cell + gap) + 18
    return frame(x0 * 2 + len(weeks) * (cell + gap), h, "CONTRIBUTIONS", body)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    u = fetch()
    for name, fn in (("stats.svg", stats_card), ("langs.svg", langs_card), ("calendar.svg", calendar_card)):
        open(os.path.join(OUT, name), "w", encoding="utf-8").write(fn(u))
    print("generated", os.listdir(OUT))
