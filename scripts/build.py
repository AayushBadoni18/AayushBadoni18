"""Builds the profile: every SVG tile in assets/ and README.md itself.

    python scripts/build.py

Live numbers come from Codeforces, LeetCode, CodeChef and GitHub. Each fetch falls back to the
last good value in assets/data.json, so one site being down never breaks the page. Fonts, icons,
screenshots and badge images are cached in vendor/. Edit copy and layout here, not in README.md.
"""
import base64
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request

# ───────────────────────────── profile ─────────────────────────────
GITHUB = "AayushBadoni18"
CODEFORCES = "AayushBadoni2005"
LEETCODE = "AayushBadoni2005"
CODECHEF = "aayushbadoni18"
HACKERRANK = "AayushBadoni2005"
HACKERRANK_STARS = 6  # HackerRank has no public API; edit by hand
EMAIL = "iamaayushbadoni1@gmail.com"
LINKEDIN = "https://www.linkedin.com/in/aayush-badoni-404612321/"
URLS = {"cf": f"https://codeforces.com/profile/{CODEFORCES}", "lc": f"https://leetcode.com/u/{LEETCODE}/",
        "cc": f"https://www.codechef.com/users/{CODECHEF}", "hr": f"https://www.hackerrank.com/profile/{HACKERRANK}"}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS, VENDOR = os.path.join(ROOT, "assets"), os.path.join(ROOT, "vendor")
UA = f"{GITHUB}-profile-readme"
ROW = 830  # widest row; GitHub's profile README column is 846px
M, MY, RX, BW = 6, 3, 20, 2  # transparent margins baked into every tile (rows of inline images already sit 6px apart), corner radius, border width

G_BLUE, G_RED, G_YELLOW, G_GREEN = "#4285F4", "#EA4335", "#FBBC04", "#34A853"
# Every tile is one SVG that carries both palettes and switches on prefers-color-scheme, so the README needs
# no <picture> tags (GitHub's renderer rewrites those when they sit inside links).
PALETTE = {  # name: (light, dark)
    "SURFACE": ("#F8F9FA", "#161B22"), "RAISED": ("#FFFFFF", "#1C2129"), "BORDER": ("#DADCE0", "#363D48"), "HAIR": ("#ECEEF1", "#232A33"),
    "INK": ("#202124", "#E8EAED"), "SUB": ("#5F6368", "#9AA0A6"), "FAINT": ("#9AA0A6", "#6E7681"), "CELL": ("#E6E9ED", "#1D232C"),
    "FOCAL": ("#202124", "#E8EAED"), "FOCAL_INK": ("#FFFFFF", "#202124"), "FOCAL_SUB": ("#BDC1C6", "#5F6368"), "FOCAL_HAIR": ("#3C4043", "#C4C7CB"),
    "BLUE": ("#2979FF", "#82B1FF"), "BLUE_INK": ("#1558D6", "#82B1FF"), "BLUE_TINT": ("#E8F0FE", "#162438"),
    "CYAN": ("#00B8D4", "#22D3EE"), "CYAN_INK": ("#00838F", "#67E8F9"), "CYAN_TINT": ("#E0F7FA", "#0E2A30"),
    "GREEN": ("#00BFA5", "#34D399"), "GREEN_INK": ("#00796B", "#6EE7B7"), "GREEN_TINT": ("#E0F5EF", "#11281F"),
    "YELLOW": ("#FFB300", "#FFD54F"), "YELLOW_INK": ("#A56300", "#FFD54F"), "YELLOW_TINT": ("#FFF6DD", "#2A2413"),
    "CORAL": ("#FF6F61", "#FF8A80"), "CORAL_INK": ("#D84315", "#FFAB91"), "CORAL_TINT": ("#FFECE8", "#321E1A"),
    "VIOLET": ("#7C4DFF", "#B39DFF"), "VIOLET_INK": ("#5E35B1", "#C9B8FF"), "VIOLET_TINT": ("#EFE9FF", "#211A3A"),
    "UP": ("#188038", "#81C995"), "DOWN": ("#D93025", "#F28B82"),
    "LC0": ("#00A896", "#2FD4C4"), "LC1": ("#E0A100", "#FFC94D"), "LC2": ("#E5345B", "#FF6B86"), "CC_STAR": ("#3366CC", "#6B9BFF"), "HR": ("#1BA94C", "#4ADE80"),
    "RANK0": ("#80868B", "#9AA0A6"), "RANK1": ("#1E8E3E", "#6BD968"), "RANK2": ("#00897B", "#2FD4C4"), "RANK3": ("#1967D2", "#8AB4F8"),
    "RANK4": ("#A142F4", "#E07BF0"), "RANK5": ("#E37400", "#FFBE6B"), "RANK6": ("#D93025", "#FF6B6B"),
}
globals().update({name: f"var(--{name.lower()})" for name in PALETTE})  # INK is "var(--ink)", and so on
LC, RANKS = (LC0, LC1, LC2), tuple(globals()[f"RANK{i}"] for i in range(7))
VARS = (":root{%s}@media (prefers-color-scheme:dark){:root{%s}.lt{display:none}.dk{display:inline}}"
        % ("".join(f"--{k.lower()}:{v[0]};" for k, v in PALETTE.items()), "".join(f"--{k.lower()}:{v[1]};" for k, v in PALETTE.items())))
LIFE_GREENS = ["#aceebb", "#4ac26b", "#2da44e", "#1a7f37"]  # literal: SMIL colour animations cannot read CSS variables

CF_RANKS = [(0, "Newbie"), (1200, "Pupil"), (1400, "Specialist"), (1600, "Expert"), (1900, "Candidate Master"), (2100, "Master"), (2400, "Grandmaster")]
CC_FLOORS = [0, 1400, 1600, 1800, 2000, 2200, 2500]  # 1 to 7 stars


def cf_rank(rating):
    i = max(i for i, (floor, _) in enumerate(CF_RANKS) if floor <= rating)
    return CF_RANKS[i][1], RANKS[i]


# ───────────────────────────── fetching ─────────────────────────────
def get(url, data=None, headers=None, binary=False):
    h = {"User-Agent": UA, **(headers or {})}
    if "api.github.com" in url and os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    for attempt in range(3):  # the icon and font hosts drop the odd connection
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=40) as r:
                body = r.read()
            return body if binary else body.decode("utf-8", "replace")
        except urllib.error.HTTPError:
            raise  # a real answer (404, rate limit); retrying will not change it
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2)


USED = set()  # vendor files this run touched; stale font subsets are pruned at the end


def vendored(name, fetch):
    """Bytes of vendor/<name>, fetched once and then reused."""
    path = os.path.join(VENDOR, name)
    USED.add(name)
    if not os.path.exists(path):
        raw = fetch()  # fetch before opening, so a failed download never leaves an empty file behind
        os.makedirs(VENDOR, exist_ok=True)
        with open(path, "wb") as f:
            f.write(raw)
    with open(path, "rb") as f:
        return f.read()


def fetch_codeforces():
    api = "https://codeforces.com/api/"
    info = json.loads(get(f"{api}user.info?handles={CODEFORCES}"))["result"][0]
    hist = json.loads(get(f"{api}user.rating?handle={CODEFORCES}"))["result"]
    subs = json.loads(get(f"{api}user.status?handle={CODEFORCES}"))["result"]
    solved = {(s["problem"].get("contestId"), s["problem"]["index"]) for s in subs if s.get("verdict") == "OK"}
    return {"rating": info["rating"], "max": info["maxRating"], "ratings": [c["newRating"] for c in hist],
            "best_rank": min(c["rank"] for c in hist), "solved": len(solved)}


def fetch_leetcode():
    q = ('{ matchedUser(username:"%s"){ submitStats{acSubmissionNum{difficulty count}} '
         'badges{displayName icon} userCalendar{streak totalActiveDays} } }' % LEETCODE)
    u = json.loads(get("https://leetcode.com/graphql", json.dumps({"query": q}).encode(),
                       {"Content-Type": "application/json"}))["data"]["matchedUser"]
    return {"solved": {x["difficulty"]: x["count"] for x in u["submitStats"]["acSubmissionNum"]},
            "streak": u["userCalendar"]["streak"], "active_days": u["userCalendar"]["totalActiveDays"],
            "badges": [{"name": b["displayName"], "icon": urllib.parse.urljoin("https://leetcode.com", b["icon"])} for b in u["badges"]]}


def fetch_codechef():
    page = get(f"https://www.codechef.com/users/{CODECHEF}")
    hist = json.loads(re.search(r"all_rating = (\[.*?\]);", page, re.S).group(1))  # the profile page embeds the real contest history
    contests = [{"code": c["code"], "date": c["end_date"][:10], "rating": int(c["rating"]), "rank": int(c["rank"])} for c in hist]
    solved = re.search(r"Total Problems Solved: (\d+)", page)
    return {"rating": contests[-1]["rating"], "max": max(c["rating"] for c in contests), "contests": contests,
            "solved": int(solved.group(1)) if solved else 0}


def fetch_github():
    page = get(f"https://github.com/users/{GITHUB}/contributions")
    counts = {m[0]: 0 if m[1].startswith("No") else int(m[1].split()[0].replace(",", ""))
              for m in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]+)', page)}
    days = []
    for td in re.findall(r"<td[^>]*data-date[^>]*>", page):
        attr = dict(re.findall(r'([\w-]+)="([^"]*)"', td))
        days.append([attr["data-date"], int(attr["data-level"]), counts.get(attr["id"], 0)])
    days.sort()
    repos = [r for r in json.loads(get(f"https://api.github.com/users/{GITHUB}/repos?per_page=100")) if not r["fork"]]
    langs = {}
    for r in repos:
        for name, size in json.loads(get(r["languages_url"])).items():
            langs[name] = langs.get(name, 0) + size
    return {"days": days, "repos": len(repos), "langs": langs}


def load_data():
    path = os.path.join(ASSETS, "data.json")
    data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for key, fn in [("cf", fetch_codeforces), ("lc", fetch_leetcode), ("cc", fetch_codechef), ("gh", fetch_github)]:
        try:
            data[key] = fn()
        except Exception as e:  # a site being down must not break the build
            if key not in data or (key == "cc" and "contests" not in data[key]):
                raise
            print(f"warning: {key} fetch failed ({e!r}); using cached data")
    os.makedirs(ASSETS, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return data


def week_change(d):
    """Solved-count changes against the newest snapshot that is at least a week old.
    Returns ({key: change}, 'since 4 Nov'), or ({}, '') until such a snapshot exists: no baseline, no arrow."""
    path = os.path.join(ASSETS, "history.json")
    hist = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    today = dt.date.today()
    now = {"cf": d["cf"]["solved"], "lc": d["lc"]["solved"]["All"], "cc": d["cc"]["solved"]}
    hist[today.isoformat()] = now
    hist = dict(sorted(hist.items())[-400:])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=1)
    old = [k for k in hist if k <= (today - dt.timedelta(days=7)).isoformat()]
    if not old:
        return {}, ""
    base, when = hist[old[-1]], dt.date.fromisoformat(old[-1])
    return {k: now[k] - base[k] for k in now}, f"since {when.day} {when:%b}"


# ───────────────────────────── svg core ─────────────────────────────
def b64(raw):
    return base64.b64encode(raw).decode()


FACES = {"d": ("Google Sans Flex", 700), "b": ("Google Sans Flex", 500), "m": ("Google Sans Code", 500), "j": ("Shippori Mincho", 600)}


def font_css(body):
    """@font-face rules for the classes this SVG uses, subset to the characters it contains and embedded
    as data URIs (an SVG shown through <img> cannot load anything external)."""
    chars = "".join(sorted(set(html.unescape("".join(re.findall(r">([^<]+)<", body)))) | set("0123456789 ")))
    out = ""
    for cls, (family, weight) in FACES.items():
        if f'class="{cls}"' not in body:
            continue
        def fetch(family=family, weight=weight):
            css = get("https://fonts.googleapis.com/css2?family=%s:wght@%d&text=%s" % (family.replace(" ", "+"), weight, urllib.parse.quote(chars)))
            return get(re.search(r"url\((https://[^)]+)\)", css).group(1), binary=True)
        key = hashlib.md5(chars.encode()).hexdigest()[:8]
        out += ("@font-face{font-family:'%s';font-weight:%d;src:url(data:font/ttf;base64,%s) format('truetype')}"
                % (family, weight, b64(vendored(f"font-{cls}-{key}.ttf", fetch))))
    return out


CSS = """
.dk{display:none}
.d{font-family:'Google Sans Flex','Google Sans',Inter,Roboto,'Segoe UI',system-ui,sans-serif;font-weight:700}
.b{font-family:'Google Sans Flex','Google Sans',Inter,Roboto,'Segoe UI',system-ui,sans-serif;font-weight:500}
.m{font-family:'Google Sans Code','Roboto Mono',ui-monospace,Consolas,monospace;font-weight:500}
.j{font-family:'Shippori Mincho','Yu Mincho','Hiragino Mincho ProN','Noto Serif JP',serif;font-weight:600}
.in{animation:in .9s cubic-bezier(.2,.7,.2,1) both}
.up{animation:up 1s cubic-bezier(.2,.7,.2,1) both}
.draw{animation:draw 2.4s cubic-bezier(.4,0,.2,1) both}
.grow{transform-box:fill-box;transform-origin:bottom;animation:grow .9s cubic-bezier(.2,.7,.2,1) both}
.wide{transform-box:fill-box;transform-origin:left;animation:wide 1.2s cubic-bezier(.2,.7,.2,1) both}
.flip{transform-box:fill-box;transform-origin:center;animation:flip 7s infinite}
.pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2.8s ease-out infinite}
@keyframes in{from{opacity:0;transform:translateY(10px)}}
@keyframes up{from{transform:translateY(110%)}}
@keyframes draw{from{stroke-dashoffset:1}}
@keyframes grow{from{transform:scaleY(0)}}
@keyframes wide{from{transform:scaleX(0)}}
@keyframes flip{0%,78%{transform:scaleX(1);animation-timing-function:ease-in}86%{transform:scaleX(0);animation-timing-function:ease-out}94%,100%{transform:scaleX(1)}}
@keyframes pulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(3);opacity:0}}
@keyframes drift{to{transform:translate(var(--dx),var(--dy))}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


def write(name, w, h, body, defs=""):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img">'
           f"<style>{font_css(body)}{CSS}{VARS}</style><defs>{defs}</defs>{body}</svg>")  # VARS last: its dark-mode rules must win over the defaults in CSS
    os.makedirs(ASSETS, exist_ok=True)
    with open(os.path.join(ASSETS, name + ".svg"), "w", encoding="utf-8") as f:
        f.write(svg)


def tile(name, w, h, inner, bg=None, edge=None, defs=""):
    """A bento tile. `inner` is drawn in a (w-2M) x (h-2MY) box and clipped to the rounded corners."""
    iw, ih = w - 2 * M, h - 2 * MY
    write(name, w, h,
          f'<g transform="translate({M} {MY})"><clipPath id="clip"><rect width="{iw}" height="{ih}" rx="{RX}"/></clipPath>'
          f'<rect width="{iw}" height="{ih}" rx="{RX}" fill="{bg or SURFACE}"/><g clip-path="url(#clip)">{inner}</g>'
          f'<rect x="{BW / 2}" y="{BW / 2}" width="{iw - BW}" height="{ih - BW}" rx="{RX - BW / 2}" fill="none" stroke="{edge or BORDER}" stroke-width="{BW}"/></g>', defs)


def tx(x, y, s, cls="b", size=14, fill=None, anchor=None, extra=""):
    a = f' text-anchor="{anchor}"' if anchor else ""
    return f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill or INK}"{a} {extra}>{html.escape(str(s), quote=False)}</text>'


def title(x, y, s, size=23, fill=None, anchor=None):
    """Tile heading: bold and large enough to scan."""
    return tx(x, y, s, "d", size, fill, anchor, 'letter-spacing="-.5"')


def big(x, y, s, size, fill=None, anchor=None):
    return tx(x, y, s, "d", size, fill, anchor, f'letter-spacing="{-size * .035:.1f}"')


def lab(x, y, s, fill=None, size=11, anchor=None):
    """Small metadata only. Never a heading."""
    return tx(x, y, s.upper(), "m", size, fill or SUB, anchor, 'letter-spacing="1.2"')


def para(x, y, s, width, size=14, fill=None, lh=1.45, cls="b"):
    """Wrapped text. Returns (svg, y of the line after the last one)."""
    lines = textwrap.wrap(s, max(8, int(width / (size * .52))))
    return "".join(tx(x, y + i * size * lh, ln, cls, size, fill or SUB) for i, ln in enumerate(lines)), y + len(lines) * size * lh


def chips(x, y, items, ink, tint, maxw=10 ** 6, size=12.5):
    """Chips set in Google Sans Code (0.6em advance, so widths are exact). Returns (svg, bottom y)."""
    out, cx = "", x
    for it in items:
        w = len(it) * size * .6 + 22
        if cx + w > x + maxw:
            cx, y = x, y + 34
        out += f'<rect x="{cx:.0f}" y="{y}" width="{w:.0f}" height="28" rx="14" fill="{tint}"/>' + tx(f"{cx + 11:.0f}", y + 18.6, it, "m", size, ink)
        cx += w + 8
    return out, y + 28


def arrow(x, y, color, s=7):
    return f'<path d="M{x},{y + s} L{x + s},{y} M{x + 1.5},{y} H{x + s} V{y + s - 1.5}" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'


def link(x, y, url, color=None):
    return tx(x, y, url, "m", 11, color or SUB) + arrow(x + len(url) * 6.6 + 6, y - 8, color or SUB)


def delta(x, y, change, period, size=14):
    """Stock-ticker movement: green up, red down, grey flat. Pass change=None when there is no baseline; nothing is drawn."""
    if change is None:
        return ""
    if change > 0:
        color, mark, txt = UP, f'<path d="M{x},{y - 1} l6,-10 l6,10 z" fill="{UP}"/>', f"+{change:,}"
    elif change < 0:
        color, mark, txt = DOWN, f'<path d="M{x},{y - 11} l6,10 l6,-10 z" fill="{DOWN}"/>', f"-{abs(change):,}"
    else:
        color, mark, txt = SUB, f'<rect x="{x}" y="{y - 7}" width="12" height="3" rx="1.5" fill="{SUB}"/>', "0"
    return mark + tx(x + 17, y, txt, "d", size, color) + tx(x + 17 + len(txt) * size * .6 + 6, y, period, "b", size - 1.5, SUB)


def smooth(pts):
    """Catmull-Rom spline through pts as a cubic Bézier path."""
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        d += (f" C{p1[0] + (p2[0] - p0[0]) / 6:.1f},{p1[1] + (p2[1] - p0[1]) / 6:.1f}"
              f" {p2[0] - (p3[0] - p1[0]) / 6:.1f},{p2[1] - (p3[1] - p1[1]) / 6:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return d


def star(cx, cy, r, fill):
    pts = " ".join(f"{cx + (r if i % 2 == 0 else r * .42) * math.sin(i * math.pi / 5):.1f},"
                   f"{cy - (r if i % 2 == 0 else r * .42) * math.cos(i * math.pi / 5):.1f}" for i in range(10))
    return f'<polygon points="{pts}" fill="{fill}"/>'


def delay(s):
    return f'style="animation-delay:{s:.2f}s"'


# ───────────────────────────── hero, headings, buttons ─────────────────────────────
def hero():
    w, h = ROW, 420
    iw, ih = w - 2 * M, h - 2 * MY
    cx, cy = 668, 200
    def drift(shape, dx, dy, t, d):
        return f'<g class="in" {delay(d)}><g style="--dx:{dx}px;--dy:{dy}px;animation:drift {t}s ease-in-out infinite alternate">{shape}</g></g>'
    glow = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" opacity=".22" filter="url(#soft)"/>'
                   for x, y, r, c in [(cx - 40, cy - 10, 110, G_BLUE), (cx - 46, cy + 104, 60, "#FF6F61"), (cx + 90, cy + 90, 80, G_GREEN)])
    motif = (glow
             + f'<line x1="{cx + 28}" x2="{cx + 28}" y1="14" y2="{ih - 14}" stroke="{BLUE}" stroke-opacity=".28"/>'
               f'<line x1="{cx - 176}" x2="{iw}" y1="{cy}" y2="{cy}" stroke="{BLUE}" stroke-opacity=".28"/>'
               f'<circle cx="{cx}" cy="{cy}" r="146" fill="none" stroke="{BLUE}" stroke-opacity=".55" stroke-width="1.2" pathLength="1" stroke-dasharray="1" class="draw"/>'
               f'<g><animateTransform attributeName="transform" type="rotate" from="-50 {cx} {cy}" to="310 {cx} {cy}" dur="40s" repeatCount="indefinite"/>'
               f'<circle cx="{cx + 146}" cy="{cy}" r="5.5" fill="{G_BLUE}"/></g>'
             + drift(f'<circle cx="{cx - 30}" cy="{cy - 10}" r="96" fill="{G_BLUE}" opacity=".9"/>', 6, 8, 9, .2)
             + drift(f'<path d="M{cx + 36},{cy - 112} A104,104 0 0 1 {cx + 130},{cy - 16} A104,104 0 0 1 {cx + 36},{cy - 112} Z" fill="{G_YELLOW}" opacity=".95"/>', -8, 6, 11, .35)
             + drift(f'<rect x="{cx + 16}" y="{cy + 20}" width="116" height="110" rx="12" fill="{G_GREEN}" opacity=".86"/>', 8, -6, 13, .5)
             + drift(f'<path d="M{cx - 92},{cy + 136} h92 l-46,-76 z" fill="#FF6F61" stroke="#FF6F61" stroke-width="10" stroke-linejoin="round" opacity=".95"/>', -5, -8, 10, .65))
    def reveal(y, s, d, fill):  # editorial line reveal: the word rises out of a clipping mask
        return (f'<clipPath id="r{y}"><rect x="0" y="{y - 92}" width="470" height="116"/></clipPath><g clip-path="url(#r{y})">'
                f'<g class="up" {delay(d)}>{big(34, y, s, 108, fill)}</g></g>')
    roles = (f'<text x="40" y="318" class="b" font-size="18" fill="{SUB}">Competitive Programmer<tspan fill="{G_BLUE}" dx="12">•</tspan>'
             f'<tspan dx="12">Software Engineer</tspan><tspan fill="{G_GREEN}" dx="12">•</tspan><tspan dx="12">Designer</tspan></text>')
    inner = (motif + lab(40, 58, "B.E. Information Technology   ·   AIT Pune   ·   Class of 2028", SUB, 11.5)
             + reveal(160, "Aayush", .05, None) + reveal(262, "Badoni", .2, "url(#name)")
             + f'<g class="in" {delay(.6)}>' + roles + tx(40, 350, "I like solving difficult problems and building useful things.", "b", 18) + "</g>"
             + f'<g class="in" {delay(.8)}><rect x="40" y="370" width="352" height="34" rx="17" fill="{GREEN_TINT}" stroke="{GREEN}" stroke-opacity=".5"/>'
               f'<circle cx="60" cy="387" r="5" fill="{G_GREEN}" class="pulse"/><circle cx="60" cy="387" r="5" fill="{G_GREEN}"/>'
             + tx(76, 392, "Open to SDE internships  ·  Summer 2027", "b", 14.5, GREEN_INK)
             + f'<path d="M354,387 h18 m-6,-5 l6,5 l-6,5" fill="none" stroke="{GREEN_INK}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></g>')
    defs = (f'<linearGradient id="name" gradientUnits="userSpaceOnUse" x1="34" x2="380"><stop offset="0" stop-color="{G_BLUE}"/><stop offset="1" stop-color="{G_GREEN}"/></linearGradient>'
            '<filter id="soft" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="34"/></filter>')
    tile("hero", w, h, inner, defs=defs)


def heading(slug, num, text, note):
    body = (tx(M + 2, 56, num, "m", 13, FAINT) + big(M + 36, 60, text, 36)
            + tx(ROW - M - 2, 56, note, "b", 13, FAINT, "end")
            + f'<rect x="{M + 2}" y="78" width="{ROW - 2 * M - 4}" height="2" fill="{BORDER}"/>'
              f'<rect x="{M + 2}" y="77" width="64" height="4" rx="2" fill="{INK}" class="wide"/>')
    write("h-" + slug, ROW, 96, body)


# The current Gmail mark (five flat colours), drawn from its native 88 x 66 box
GMAIL = ('<g transform="translate(-15.6 -12.6) scale(.3)"><path fill="#4285f4" d="M58 108h14V74L52 59v43c0 3.32 2.69 6 6 6"/>'
         '<path fill="#34a853" d="M120 108h14c3.32 0 6-2.69 6-6V59l-20 15"/><path fill="#fbbc04" d="M120 48v26l20-15v-8c0-7.42-8.47-11.65-14.4-7.2"/>'
         '<path fill="#ea4335" d="M72 74V48l24 18 24-18v26L96 92"/><path fill="#c5221f" d="M52 51v8l20 15V48l-5.6-4.2c-5.94-4.45-14.4-.22-14.4 7.2"/></g>')
LINKEDIN_LOGO = ('<rect width="22" height="22" rx="4" fill="#0A66C2"/><circle cx="6.4" cy="6.4" r="1.95" fill="#fff"/><rect x="4.7" y="9.5" width="3.4" height="8.3" fill="#fff"/>'
                 '<path d="M10.1 9.5h3.2v1.3c.5-.9 1.6-1.5 3-1.5 2.4 0 3.1 1.5 3.1 3.9v4.6H16v-4c0-1-.3-1.7-1.3-1.7s-1.3.7-1.3 1.7v4h-3.3z" fill="#fff"/>')


def button(name, txt, logo, logo_w, logo_h=22):
    tw = len(txt) * 8.8
    w = round(20 + logo_w + 10 + tw + 32) + 2 * M
    x = M + 20
    body = (f'<rect x="{M + 1}" y="{M + 1}" width="{w - 2 * M - 2}" height="44" rx="22" fill="{RAISED}" stroke="{BORDER}" stroke-width="{BW}"/>'
            f'<g transform="translate({x} {M + 23 - logo_h / 2})">{logo}</g>'
            + tx(x + logo_w + 10, M + 28, txt, "b", 14.5) + arrow(x + logo_w + 10 + tw + 6, M + 19, FAINT))
    write(name, w, 46 + 2 * M, body)
    return w


# ───────────────────────────── highlights ─────────────────────────────
def highlights(d):
    # Barclays: the focal tile. 300 dots, one per ten teams; five lit dots are the 48 finalists.
    iw, ih = 490 - 2 * M, 280 - 2 * MY
    lit, dots = {37, 112, 158, 203, 266}, ""
    for i in range(300):
        x, y = iw - 30 - 19 * 8.6 + (i % 20) * 8.6, 88 + (i // 20) * 8.6
        if i in lit:
            dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{G_YELLOW}" class="pulse" {delay(i % 5 * .5)}/><circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{G_YELLOW}"/>'
        else:
            dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="{FOCAL_HAIR}"/>'
    inner = (title(28, 52, "Barclays Hack-O-Hire", 23, FOCAL_INK) + tx(iw - 30, 50, "National finals", "b", 13, FOCAL_SUB, "end")
             + big(24, 152, "Top 48", 76, FOCAL_INK) + tx(28, 192, "of 3,000+ teams.", "b", 18, FOCAL_INK)
             + tx(28, 216, "Finalist, as team captain.", "b", 18, FOCAL_SUB)
             + tx(28, 250, "Shortlisted from 15,000+ participants.", "b", 13, FOCAL_SUB) + dots
             + tx(iw - 30, 250, "1 dot = 10 teams", "b", 12, FOCAL_SUB, "end"))
    tile("hl-barclays", 490, 280, inner, FOCAL, FOCAL)

    iw = 340 - 2 * M
    start, end = dt.date(2024, 7, 15), dt.date(2028, 6, 30)
    frac = min(1, max(0, (dt.date.today() - start).days / (end - start).days))
    seg = (iw - 56 - 3 * 6) / 4
    bar = "".join(f'<rect x="{28 + i * (seg + 6):.1f}" y="216" width="{seg:.1f}" height="7" rx="3.5" fill="{BLUE}" fill-opacity=".22"/>'
                  f'<rect x="{28 + i * (seg + 6):.1f}" y="216" width="{seg * min(1, max(0, frac * 4 - i)):.1f}" height="7" rx="3.5" fill="{BLUE}" class="wide" {delay(.3 + i * .2)}/>'
                  for i in range(4))
    inner = (title(28, 52, "Academics", 23, BLUE_INK) + big(26, 118, "Third year", 52) + tx(28, 148, "First semester", "d", 20, SUB)
             + tx(28, 180, "B.E. Information Technology", "b", 16) + tx(28, 201, "Army Institute of Technology, Pune", "b", 14, SUB)
             + bar + tx(28, 248, "2024", "b", 12.5, SUB) + tx(iw - 28, 248, "Class of 2028", "b", 12.5, SUB, "end"))
    tile("hl-academics", 340, 280, inner, BLUE_TINT, BLUE)

    inner = (title(28, 52, "ICPC 2026", 23, YELLOW_INK) + big(26, 126, "Shortlisted", 50)
             + tx(28, 158, "Kanpur Regional", "b", 18) + tx(28, 192, "The regional round of the world's", "b", 14, SUB)
             + tx(28, 211, "oldest programming contest.", "b", 14, SUB))
    tile("hl-icpc", 340, 244, inner, YELLOW_TINT, YELLOW)

    iw = 490 - 2 * M
    four = "".join(f'<circle cx="{iw - 114 + i * 26}" cy="45" r="7" fill="{c}" class="in" {delay(.2 + i * .12)}/>' for i, c in enumerate([G_BLUE, G_RED, G_YELLOW, G_GREEN]))
    inner = (title(28, 52, "Google · The Big Code") + four + big(24, 134, "Top 1,500", 66)
             + tx(28, 168, "Qualified for Round 2.", "b", 18)
             + tx(28, 202, "A national contest open to engineering students across India.", "b", 14, SUB))
    tile("hl-bigcode", 490, 244, inner)


# ───────────────────────────── competitive programming ─────────────────────────────
def cp_codeforces(d):
    cf, w, h = d["cf"], ROW, 476
    iw, ih = w - 2 * M, h - 2 * MY
    rank, color = cf_rank(cf["rating"])
    r = cf["ratings"]
    gx, gy, gw, gh = 62, 210, iw - 62 - 124, 190
    lo, hi = max(0, min(r) // 100 * 100 - 100), max(r) // 100 * 100 + 200
    X = lambda i: gx + gw * i / max(len(r) - 1, 1)
    Y = lambda v: gy + gh - gh * (v - lo) / (hi - lo)
    pts = [(X(i), Y(v)) for i, v in enumerate(r)]
    line, (lx, ly) = smooth(pts), pts[-1]
    grid = "".join(tx(gx - 12, Y(v) + 4, v, "b", 11.5, SUB, "end") + f'<line x1="{gx}" x2="{gx + gw}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{HAIR}"/>'
                   for v in range(lo, hi + 1, 200))
    for i, (floor, name) in enumerate(CF_RANKS):
        if lo < floor < hi:
            grid += (f'<line x1="{gx}" x2="{gx + gw}" y1="{Y(floor):.1f}" y2="{Y(floor):.1f}" stroke="{RANKS[i]}" stroke-width="1.4" stroke-dasharray="2 5"/>'
                     + tx(gx + gw + 12, Y(floor) + 4, f"{name} {floor}", "b", 12, RANKS[i]))
    dots = "".join(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.6" fill="{SURFACE}" stroke="{cf_rank(v)[1]}" stroke-width="2" class="in" {delay(.5 + 1.6 * i / len(r))}/>'
                   for i, ((px, py), v) in enumerate(zip(pts, r)))
    stats = [("Contests", len(r)), ("Solved", cf["solved"]), ("Best rank", f"{cf['best_rank']:,}")]
    inner = (title(32, 54, "Codeforces", 26) + big(28, 146, cf["rating"], 84, color)
             + tx(232, 112, rank, "d", 30, color, None, 'letter-spacing="-.6"') + tx(233, 136, f"current rating · peak {cf['max']}", "b", 13.5, SUB)
             + (delta(233, 164, r[-1] - r[-2], "last contest") if len(r) > 1 else "")
             + "".join(tx(iw - 344 + i * 112, 102, k, "b", 13.5, SUB) + big(iw - 345 + i * 112, 140, v, 32) for i, (k, v) in enumerate(stats))
             + grid
             + f'<path d="{line} L{lx:.1f},{gy + gh} L{gx},{gy + gh} Z" fill="{color}" fill-opacity=".1" class="in" {delay(1.2)}/>'
               f'<path d="{line}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" pathLength="1" stroke-dasharray="1" class="draw"/>'
             + dots
             + f'<g class="in" {delay(2.2)}><circle cx="{lx:.1f}" cy="{ly:.1f}" r="5.5" fill="{color}" class="pulse"/><circle cx="{lx:.1f}" cy="{ly:.1f}" r="5.5" fill="{color}"/>'
               f'<rect x="{lx - 27:.1f}" y="{ly - 40:.1f}" width="54" height="26" rx="13" fill="{color}"/>'
             + tx(f"{lx:.1f}", f"{ly - 22:.1f}", cf["rating"], "d", 13.5, SURFACE, "middle") + "</g>"
             + tx(gx, gy + gh + 24, "first rated contest", "b", 12, SUB) + tx(gx + gw, gy + gh + 24, f"contest {len(r)}", "b", 12, SUB, "end")
             + link(32, ih - 20, f"codeforces.com/profile/{CODEFORCES}"))
    tile("cp-codeforces", w, h, inner, edge=color)


def badge_png(url):
    """LeetCode serves 1080px badges of 1 MB+; fetch a 168px copy through the wsrv.nl image proxy."""
    small = "https://wsrv.nl/?w=168&h=168&output=png&url=" + urllib.parse.quote(url, safe="")
    return vendored("badge-" + hashlib.md5(url.encode()).hexdigest()[:10] + ".png", lambda: get(small, binary=True))


def cp_leetcode(d, change, since):
    lc, w, h = d["lc"], 490, 356
    iw, ih = w - 2 * M, h - 2 * MY
    top = max(lc["solved"][k] for k in ("Easy", "Medium", "Hard"))
    bars = ""
    for i, (name, c) in enumerate(zip(("Easy", "Medium", "Hard"), LC)):
        y = 216 + i * 30
        bars += (tx(28, y + 5, name, "b", 14.5, SUB) + tx(244, y + 5, lc["solved"][name], "d", 16, None, "end")
                 + f'<rect x="98" y="{y - 4}" width="104" height="8" rx="4" fill="{c}" fill-opacity=".18"/>'
                   f'<rect x="98" y="{y - 4}" width="{104 * lc["solved"][name] / top:.1f}" height="8" rx="4" fill="{c}" class="wide" {delay(.3 + i * .15)}/>')
    badges = "".join(f'<image class="flip" x="{284 + i * 62}" y="100" width="58" height="58" href="data:image/png;base64,{b64(badge_png(b["icon"]))}"/>'
                     for i, b in enumerate(lc["badges"][:3]))
    names = "".join(tx(288, 196 + i * 21, b["name"], "b", 12.5, SUB) for i, b in enumerate(lc["badges"][:4]))
    inner = (title(28, 54, "LeetCode", 26) + big(24, 140, lc["solved"]["All"], 74) + tx(28, 166, "problems solved", "b", 15, SUB)
             + delta(28, 190, change.get("lc"), since) + bars
             + f'<line x1="264" x2="264" y1="76" y2="{ih - 52}" stroke="{BORDER}" stroke-width="2"/>' + tx(288, 84, f"{len(lc['badges'])} badges", "d", 16) + badges + names
             + tx(288, 196 + min(len(lc["badges"]), 4) * 21 + 12, f"{lc['streak']}-day streak", "d", 15, LC[0])
             + tx(288, 196 + min(len(lc["badges"]), 4) * 21 + 32, f"{lc['active_days']} active days", "b", 13, SUB)
             + link(28, ih - 20, f"leetcode.com/u/{LEETCODE}"))
    tile("cp-leetcode", w, h, inner, edge=LC[1])


def cp_hackerrank():
    w, h = 340, 356
    iw, ih = w - 2 * M, h - 2 * MY
    stars = "".join(f'<g class="in" {delay(.2 + i * .1)}>{star(42 + i * 34, 196, 13, HR)}</g>' for i in range(HACKERRANK_STARS))
    inner = (title(28, 54, "HackerRank", 26) + big(25, 150, f"{HACKERRANK_STARS}-star", 74) + stars
             + tx(28, 246, "Problem Solving", "d", 19) + tx(28, 270, "Gold badge, the highest tier.", "b", 14, SUB)
             + link(28, ih - 20, f"hackerrank.com/profile/{HACKERRANK}"))
    tile("cp-hackerrank", w, h, inner, edge=HR)


def cp_codechef(d):
    cc, w, h = d["cc"], 490, 404
    iw, ih = w - 2 * M, h - 2 * MY
    cs = cc["contests"]
    r = [c["rating"] for c in cs]
    stars = sum(1 for f in CC_FLOORS if f <= cc["rating"])
    boxes = "".join(f'<g class="in" {delay(.2 + i * .12)}><rect x="{202 + i * 32}" y="88" width="27" height="27" rx="6" fill="{CC_STAR}"/>{star(215.5 + i * 32, 102, 8.5, "#fff")}</g>' for i in range(stars))
    # chart: one point per rated contest, straight segments (nothing is interpolated), star thresholds as reference lines
    gx, gy, gw, gh = 64, 196, iw - 64 - 44, 120
    lo, hi = min(r) // 100 * 100 - 100, max(r) // 100 * 100 + 100
    X = lambda i: gx + 22 + (gw - 44) * i / max(len(r) - 1, 1)
    Y = lambda v: gy + gh - gh * (v - lo) / (hi - lo)
    pts = [(X(i), Y(v)) for i, v in enumerate(r)]
    grid = "".join(tx(gx - 10, Y(v) + 4, v, "b", 11.5, SUB, "end") + f'<line x1="{gx}" x2="{gx + gw}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{HAIR}" stroke-width="1.2"/>'
                   for v in range(lo, hi + 1, 100))
    for n, floor in enumerate(CC_FLOORS, 1):
        if lo < floor <= hi:
            grid += (f'<line x1="{gx}" x2="{gx + gw}" y1="{Y(floor):.1f}" y2="{Y(floor):.1f}" stroke="{CC_STAR}" stroke-width="1.4" stroke-dasharray="2 5"/>'
                     + tx(gx + gw + 8, Y(floor) + 4, f"{n}-star", "b", 11.5, CC_STAR))
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    marks = ""
    for i, ((x, y), c) in enumerate(zip(pts, cs)):
        last = i == len(cs) - 1
        when = dt.date.fromisoformat(c["date"])
        marks += (f'<g class="in" {delay(.5 + i * .25)}>'
                  + (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{CC_STAR}" class="pulse"/>' if last else "")
                  + f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{6 if last else 4.5}" fill="{CC_STAR if last else SURFACE}" stroke="{CC_STAR}" stroke-width="2.4"/>'
                  + tx(f"{x:.1f}", f"{y - 13:.1f}", c["rating"], "d", 13.5 if last else 12.5, CC_STAR if last else INK, "middle")
                  + tx(f"{x:.1f}", gy + gh + 20, re.sub(r"^START(\d+).*", r"Starters \1", c["code"]), "b", 11.5, SUB, "middle")
                  + tx(f"{x:.1f}", gy + gh + 36, f"{when.day} {when:%b}", "b", 11, FAINT, "middle") + "</g>")
    stats = [("Peak", cc["max"]), ("Contests", len(cs)), ("Best rank", f"{min(c['rank'] for c in cs):,}")]
    inner = (title(28, 54, "CodeChef", 26) + big(24, 124, cc["rating"], 62) + boxes
             + tx(202 + stars * 32 + 6, 109, f"{stars}-star", "d", 20, CC_STAR)
             + (delta(28, 154, r[-1] - r[-2], "last contest") if len(r) > 1 else "")
             + "".join(tx(iw - 30 - (2 - i) * 84, 142, k, "b", 12.5, SUB, "end") + tx(iw - 30 - (2 - i) * 84, 166, v, "d", 19, None, "end") for i, (k, v) in enumerate(stats))
             + grid
             + f'<path d="{path} L{pts[-1][0]:.1f},{gy + gh} L{pts[0][0]:.1f},{gy + gh} Z" fill="{CC_STAR}" fill-opacity=".12" class="in" {delay(1)}/>'
               f'<path d="{path}" fill="none" stroke="{CC_STAR}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" class="draw"/>'
             + marks + link(28, ih - 20, f"codechef.com/users/{CODECHEF}"))
    tile("cp-codechef", w, h, inner, edge=CC_STAR)


def cp_total(d, change, since):
    w, h = 340, 404
    iw, ih = w - 2 * M, h - 2 * MY
    parts = [("Codeforces", d["cf"]["solved"], cf_rank(d["cf"]["rating"])[1]), ("LeetCode", d["lc"]["solved"]["All"], LC[1]), ("CodeChef", d["cc"]["solved"], CC_STAR)]
    total, contests = sum(p[1] for p in parts), len(d["cf"]["ratings"]) + len(d["cc"]["contests"])
    top = max(p[1] for p in parts)
    rows_ = ""
    for i, (name, n, c) in enumerate(parts):  # bars share one scale, so their lengths compare directly
        y = 232 + i * 38
        rows_ += (tx(28, y, name, "b", 14.5) + tx(iw - 28, y, n, "d", 16, None, "end")
                  + f'<rect x="28" y="{y + 9}" width="{iw - 56}" height="7" rx="3.5" fill="{c}" fill-opacity=".16"/>'
                    f'<rect x="28" y="{y + 9}" width="{(iw - 56) * n / top:.1f}" height="7" rx="3.5" fill="{c}" class="wide" {delay(.3 + i * .2)}/>')
    inner = (title(28, 54, "Across platforms", 24, GREEN_INK) + big(24, 148, total, 84) + tx(28, 176, "problems solved", "b", 16, SUB)
             + delta(28, 202, sum(change.values()) if change else None, since) + rows_
             + big(28, ih - 24, contests, 26) + tx(28 + len(str(contests)) * 16 + 8, ih - 24, "rated contests", "b", 15, SUB))
    tile("cp-total", w, h, inner, GREEN_TINT, GREEN)


# ───────────────────────────── projects ─────────────────────────────
def shot(name, x, y, w, h, crop):
    """A real screenshot from the project's repo, cropped with a viewBox."""
    raw = open(os.path.join(VENDOR, name), "rb").read()
    sw, sh = {"shot-forex.jpg": (1200, 675), "shot-access.jpg": (1000, 559)}[name]
    return (f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{crop}" preserveAspectRatio="xMidYMid slice">'
            f'<image width="{sw}" height="{sh}" href="data:image/jpeg;base64,{b64(raw)}"/></svg>')


def facts(x, y, rows, width):
    out = ""
    for k, v in rows:
        p, y2 = para(x, y + 21, v, width, 13.5)
        out += tx(x, y, k, "d", 13.5) + p
        y = y2 + 12
    return out, y


def art_agni(w, h):
    grid = "".join(f'<line x1="{x}" x2="{x}" y1="0" y2="{h}" stroke="{BORDER}"/>' for x in range(0, w, 29)) + "".join(f'<line x1="0" x2="{w}" y1="{y}" y2="{y}" stroke="{BORDER}"/>' for y in range(0, h, 29))
    river = f'<path d="M-10,{h * .78:.0f} C{w * .3:.0f},{h * .6:.0f} {w * .45:.0f},{h * .95:.0f} {w + 10},{h * .55:.0f}" fill="none" stroke="{CYAN}" stroke-opacity=".5" stroke-width="7" stroke-linecap="round"/>'
    def spot(x, y, c, name, live):
        pulse = f'<circle cx="{x}" cy="{y}" r="7" fill="{c}" class="pulse"/>' if live else f'<circle cx="{x}" cy="{y}" r="15" fill="none" stroke="{c}" stroke-width="1.5" stroke-dasharray="3 4"/>'
        tw = len(name) * 6.4 + 18
        return (pulse + f'<circle cx="{x}" cy="{y}" r="7" fill="{c}"/><rect x="{x + 16}" y="{y - 12}" width="{tw:.0f}" height="24" rx="12" fill="{RAISED}" stroke="{BORDER}" stroke-width="1.5"/>'
                + tx(x + 25, y + 4, name, "b", 11.5, INK))
    return grid + river + spot(60, 52, YELLOW, "steel plant · recurring", False) + spot(110, 128, CORAL, "anomaly · possible wildfire", True) + spot(238, 88, YELLOW, "refinery", False)


def art_sahayog(w, h):
    cx, cy = w * .52, h * .5
    roads = (f'<path d="M0,{h * .3:.0f} L{w},{h * .62:.0f} M{w * .28:.0f},0 L{w * .4:.0f},{h} M{w * .8:.0f},0 L{w * .66:.0f},{h}" stroke="{BORDER}" stroke-width="9" fill="none"/>'
             f'<path d="M0,{h * .3:.0f} L{w},{h * .62:.0f} M{w * .28:.0f},0 L{w * .4:.0f},{h} M{w * .8:.0f},0 L{w * .66:.0f},{h}" stroke="{RAISED}" stroke-width="1.5" stroke-dasharray="6 8" fill="none"/>')
    sos = "".join(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="12" fill="{CORAL}" class="pulse" {delay(i * .9)}/>' for i in range(3)) + f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="12" fill="{CORAL}"/>' + tx(f"{cx:.0f}", f"{cy + 3.5:.0f}", "SOS", "d", 8.5, "#fff", "middle")
    pins = "".join(f'<g class="in" {delay(.3 + i * .2)}><rect x="{x - 11}" y="{y - 11}" width="22" height="22" rx="6" fill="{GREEN_TINT}" stroke="{GREEN}" stroke-width="1.6"/>'
                   f'<path d="M{x},{y - 5} v10 M{x - 5},{y} h10" stroke="{GREEN}" stroke-width="2.2" stroke-linecap="round"/></g>'
                   for i, (x, y) in enumerate([(46, 44), (w - 54, 50), (72, h - 40), (w - 78, h - 46)]))
    return roads + pins + sos


def project_forex():
    w, h = ROW, 492
    iw, ih = w - 2 * M, h - 2 * MY
    sx = 404
    one, y = para(34, 132, "Hover a price on any site and read it in your own currencies, without opening a converter tab.", 326, 15, INK)
    f, _ = facts(34, y + 14, [("What I built", "A Manifest V3 extension with a hover tooltip, a selection mode and a converter that floats over the page."),
                              ("Decisions", "TreeWalker scan plus MutationObserver for live pages. Locale-aware price parsing. A bare $ is resolved from the site and language. Rates cached for 30 minutes.")], 326)
    c, _ = chips(34, ih - 78, ["TypeScript", "Manifest V3", "REST"], BLUE_INK, BLUE_TINT)
    inner = (lab(34, 48, "01 · Browser extension · v3.1", BLUE_INK) + big(32, 98, "Forex Hover Pro", 38)
             + one + f + c + link(34, ih - 22, "github.com/AayushBadoni18/Forex-Hover")
             + shot("shot-forex.jpg", sx, 0, iw - sx, ih, "560 70 536 630") + f'<line x1="{sx}" x2="{sx}" y1="0" y2="{ih}" stroke="{BLUE}" stroke-width="{BW}"/>')
    tile("project-forex", w, h, inner, RAISED, BLUE)


def project_card(name, w, num, kind, heading_, line, rows, tags, url, art, accent, tint, edge):
    h = 560
    iw, ih = w - 2 * M, h - 2 * MY
    one, y = para(28, 290, line, iw - 56, 14.5, INK)
    f, _ = facts(28, y + 14, rows, iw - 56)
    c, _ = chips(28, ih - 78, tags, accent, tint)
    inner = (art + f'<line x1="0" x2="{iw}" y1="190" y2="190" stroke="{edge}" stroke-width="{BW}"/>' + lab(28, 224, f"{num} · {kind}", accent)
             + big(27, 262, heading_, 30) + one + f + c + link(28, ih - 22, url))
    tile(name, w, h, inner, RAISED, edge)


def projects():
    project_forex()
    project_card("project-accessbridge", 470, "02", "Browser extension", "AccessBridge AI",
                 "Right-click to simplify dense text, decode tone or describe an image.",
                 [("What I built", "An MV3 service worker with context-menu actions and a Shadow DOM interface that page styles cannot break."),
                  ("Decisions", "Three reading levels. Common jargon is answered from a local list, with no API call.")],
                 ["JavaScript", "Manifest V3", "OpenRouter"], "github.com/AayushBadoni18/AccessBridge-AI",
                 shot("shot-access.jpg", 0, 0, 458, 190, "0 48 1000 415"), GREEN_INK, GREEN_TINT, GREEN)
    project_card("project-agniview", 360, "03", "Geospatial", "AgniView",
                 "Tells a wildfire from a steel plant in satellite heat data.",
                 [("What I built", "A Flask and PostGIS service that ingests NASA FIRMS hourly, with a Next.js map."),
                  ("Decisions", "Rules classify; AI only explains stored evidence.")],
                 ["Python", "PostGIS", "Docker"], "github.com/AayushBadoni18/AgniView",
                 f'<rect width="348" height="190" fill="{SURFACE}"/>' + art_agni(348, 190), CORAL_INK, CORAL_TINT, CORAL)
    w, h = ROW, 250
    iw, ih = w - 2 * M, h - 2 * MY
    ax = iw - 300
    c, _ = chips(34, ih - 78, ["React", "TypeScript", "Leaflet", "Express", "MongoDB"], YELLOW_INK, YELLOW_TINT)
    inner = (lab(34, 46, "04 · Disaster response · team project", YELLOW_INK) + big(32, 90, "Sahayog", 34)
             + para(34, 118, "Alerts, citizen incident reports, a live hazard map and one-tap SOS, in several languages.", ax - 60, 14.5, INK)[0]
             + c + link(34, ih - 22, "github.com/AayushBadoni18/sahayog")
             + f'<svg x="{ax}" y="0" width="300" height="{ih}"><rect width="300" height="{ih}" fill="{SURFACE}"/>{art_sahayog(300, ih)}</svg>'
               f'<line x1="{ax}" x2="{ax}" y1="0" y2="{ih}" stroke="{YELLOW}" stroke-width="{BW}"/>')
    tile("project-sahayog", w, h, inner, RAISED, YELLOW)


# ───────────────────────────── stack ─────────────────────────────
S = "skill"  # skillicons.dev tile; "brand" = simpleicons.org glyph on a matching tile; "mono" = lettered tile where no logo is published
STACK = [  # (file, width, height, heading, accent, per row, items)
    ("stack-languages", 490, 200, "Programming Languages", "BLUE", 6,
     [(S, "cpp", "C++"), (S, "c", "C"), (S, "python", "Python"), (S, "java", "Java"), (S, "js", "JavaScript"), (S, "ts", "TypeScript")]),
    ("stack-frontend", 340, 200, "Frontend Development", "CYAN", 5,
     [(S, "react", "React"), (S, "nextjs", "Next.js"), (S, "tailwind", "Tailwind"), (S, "html", "HTML"), (S, "css", "CSS")]),
    ("stack-backend", 290, 200, "Backend Development", "GREEN", 3, [(S, "nodejs", "Node.js"), (S, "express", "Express"), (S, "flask", "Flask")]),
    ("stack-data", 210, 200, "Databases", "YELLOW", 2, [(S, "mongodb", "MongoDB"), (S, "postgres", "PostgreSQL")]),
    ("stack-dev", 490, 292, "Development & Infrastructure", "CORAL", 3,
     [(S, "docker", "Docker"), (S, "git", "Git"), (S, "github", "GitHub"), (S, "vscode", "VS Code"), (S, "idea", "IntelliJ IDEA"), (S, "pycharm", "PyCharm")]),
    ("stack-aitools", 830, 192, "AI-Assisted Development & Tools", "VIOLET", 8,
     [("brand", "claude", "Claude Code"), ("brand", "cline", "Cline"), ("mono", "AG", "Antigravity"), ("brand", "githubcopilot", "GitHub Copilot"),
      ("mono", "OR", "OmniRoute"), (S, "vscode", "VS Code"), (S, "git", "Git"), (S, "github", "GitHub")]),
]
AI_ML = ["Large Language Models", "Multimodal AI", "Applied AI", "AI integrations", "OpenRouter"]
CORE = ["Data Structures & Algorithms", "Algorithm Analysis", "OOP", "Operating Systems", "DBMS", "Computer Networks", "AI / ML", "Theory of Computation"]
BRAND_COLORS = {"claude": ("D97757", "D97757")}  # others are drawn in ink


def glyph(kind, slug, x, y, size):
    if kind == S:
        out = ""
        for theme, cls in [("light", "lt"), ("dark", "dk")]:
            raw = vendored(f"icon-{slug}-{theme}.svg", lambda: get(f"https://skillicons.dev/icons?i={slug}&theme={theme}", binary=True))
            out += f'<image class="{cls}" x="{x:.1f}" y="{y}" width="{size}" height="{size}" href="data:image/svg+xml;base64,{b64(raw)}"/>'
        return out
    box = f'<rect x="{x:.1f}" y="{y}" width="{size}" height="{size}" rx="{size * .23:.1f}" fill="{RAISED}" stroke="{BORDER}" stroke-width="1.5"/>'
    if kind == "mono":
        return box + tx(f"{x + size / 2:.1f}", y + size / 2 + 5.5, slug, "d", 15, VIOLET_INK, "middle")
    out, g = box, size * .56
    for hexc, cls in zip(BRAND_COLORS.get(slug, ("202124", "E8EAED")), ("lt", "dk")):
        raw = vendored(f"icon-si-{slug}-{hexc}.svg", lambda: get(f"https://cdn.simpleicons.org/{slug}/{hexc}", binary=True))
        out += f'<image class="{cls}" x="{x + (size - g) / 2:.1f}" y="{y + (size - g) / 2:.1f}" width="{g:.1f}" height="{g:.1f}" href="data:image/svg+xml;base64,{b64(raw)}"/>'
    return out


def stack():
    for name, w, h, heading_, accent, per_row, items in STACK:
        iw = w - 2 * M
        pitch = (iw - 36) / per_row
        ink = globals()[accent + "_INK"]
        inner = title(26, 52, heading_, 22 if w > 300 else 20, ink)
        for i, (kind, slug, label_) in enumerate(items):
            r, c = divmod(i, per_row)
            cx, y = 18 + c * pitch + pitch / 2, 84 + r * 96
            inner += f'<g class="in" {delay(.1 + i * .06)}>{glyph(kind, slug, cx - 22, y, 44)}' + tx(f"{cx:.1f}", y + 66, label_, "b", 13.5, INK, "middle") + "</g>"
        tile(name, w, h, inner, globals()[accent + "_TINT"] if name == "stack-aitools" else None, globals()[accent])
    c, _ = chips(26, 84, AI_ML, VIOLET_INK, VIOLET_TINT, 330 - 2 * M - 52, 13)
    tile("stack-aiml", 330, 200, title(26, 52, "AI / ML", 22, VIOLET_INK) + c, edge=VIOLET)
    c, _ = chips(26, 84, CORE, BLUE_INK, BLUE_TINT, 340 - 2 * M - 52, 13)
    tile("stack-core", 340, 292, title(26, 52, "CS Fundamentals", 22, BLUE_INK) + c, edge=BLUE)


def focus():
    """Current technical interests. Descriptions say what I am studying, not what I claim to have mastered."""
    s = 'fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"'
    items = [
        ("Large Language Models", "How they behave inside real products: prompting, context and where they fail.", VIOLET, VIOLET_TINT,
         f'<path d="M6,10 h28 M6,20 h20 M6,30 h24" {s} stroke="{VIOLET}"/><circle cx="33" cy="20" r="3" fill="{VIOLET}" class="pulse"/><circle cx="33" cy="20" r="3" fill="{VIOLET}"/>'),
        ("Multi-Agent Orchestration", "Splitting one job across several agents and models, and keeping them coordinated.", CYAN, CYAN_TINT,
         f'<path d="M20,9 L8,31 M20,9 L32,31 M8,31 H32" {s} stroke="{CYAN}"/>' + "".join(f'<circle cx="{x}" cy="{y}" r="5" fill="{CYAN}"/>' for x, y in [(20, 9), (8, 31), (32, 31)])),
        ("Backend systems", "APIs, caching and data stores.", GREEN, GREEN_TINT,
         "".join(f'<rect x="6" y="{6 + i * 10.5}" width="28" height="7.5" rx="2.5" {s} stroke="{GREEN}"/>' for i in range(3))),
        ("Developer tools", "Small tools that remove a daily annoyance.", YELLOW, YELLOW_TINT,
         f'<path d="M14,11 L5,20 L14,29 M26,11 L35,20 L26,29 M23,8 L17,32" {s} stroke="{YELLOW_INK}"/>'),
        ("Interface design", "Layout, type and motion.", CORAL, CORAL_TINT,
         f'<path d="M6,32 C6,10 34,30 34,8" {s} stroke="{CORAL}"/><rect x="3" y="29" width="6" height="6" fill="{CORAL}"/><rect x="31" y="5" width="6" height="6" fill="{CORAL}"/>'),
    ]
    w, h = ROW, 300
    iw = w - 2 * M
    inner = title(28, 54, "Current focus", 24)
    for i, (name, desc, c, tint, art) in enumerate(items):
        big_ = i < 2
        cw = (iw - 56) / (2 if big_ else 3)
        x, y = 28 + (i if big_ else i - 2) * cw, 84 if big_ else 192
        p, _ = para(x + 64, y + 42, desc, cw - 84, 13.5)
        inner += (f'<g class="in" {delay(.1 + i * .1)}><rect x="{x:.0f}" y="{y}" width="50" height="50" rx="13" fill="{tint}" stroke="{c}" stroke-width="1.6"/>'
                  f'<g transform="translate({x + 5:.0f} {y + 5})">{art}</g>' + tx(f"{x + 64:.0f}", y + 20, name, "d", 17) + p + "</g>")
    tile("focus", w, h, inner)


# ───────────────────────────── beyond the coder ─────────────────────────────
def beyond():
    w, h = 490, 268
    iw, ih = w - 2 * M, h - 2 * MY
    def poster(x, shapes, d):
        return f'<g class="in" {delay(d)}><rect x="{x}" y="66" width="78" height="112" rx="5" fill="{RAISED}" stroke="{BORDER}" stroke-width="1.5"/><svg x="{x}" y="66" width="78" height="112">{shapes}</svg></g>'
    posters = (poster(iw - 276, f'<circle cx="39" cy="44" r="24" fill="{G_RED}"/><rect x="14" y="78" width="50" height="6" fill="{INK}"/><rect x="14" y="90" width="30" height="6" fill="{INK}"/>', .2)
               + poster(iw - 190, f'<path d="M0,112 L78,112 L78,30 Z" fill="{G_BLUE}"/><circle cx="24" cy="30" r="12" fill="{G_YELLOW}"/>', .35)
               + poster(iw - 104, f'<rect x="12" y="14" width="26" height="84" fill="{G_GREEN}"/><rect x="42" y="14" width="24" height="40" fill="{G_YELLOW}"/><circle cx="54" cy="80" r="12" fill="{INK}"/>', .5))
    inner = (title(28, 54, "Designer", 26, YELLOW_INK) + big(26, 126, "3×", 60) + tx(28, 156, "state-level winner,", "b", 16.5)
             + tx(28, 178, "poster making.", "b", 16.5) + posters
             + tx(28, 222, "Design came before code, and it still decides", "b", 14, SUB) + tx(28, 241, "how I build interfaces.", "b", 14, SUB))
    tile("beyond-designer", w, h, inner, edge=YELLOW)

    w = 340
    iw = w - 2 * M
    lanes = "".join(f'<path d="M28,{166 + i * 18} H{iw - 28}" stroke="{CORAL}" stroke-opacity=".35" stroke-width="2"/>'
                    f'<circle cy="{166 + i * 18}" r="5" fill="{CORAL}"><animate attributeName="cx" values="28;{iw - 28}" dur="{3.4 + i * .9}s" repeatCount="indefinite"/></circle>' for i in range(3))
    inner = (title(28, 54, "Athlete", 26, CORAL_INK) + tx(28, 98, "Track and field", "d", 20)
             + tx(28, 124, "On the college athletics team.", "b", 14.5, SUB) + lanes
             + tx(28, 241, "Discipline carries over to everything else.", "b", 13.5, SUB))
    tile("beyond-athlete", w, h, inner, CORAL_TINT, CORAL)

    w, h = ROW, 200
    iw = w - 2 * M
    spines = "".join(f'<rect x="{iw - 190 + x}" y="{150 - hh}" width="{bw}" height="{hh}" rx="3" fill="{c}" class="grow" {delay(.2 + i * .1)}/>'
                     for i, (x, bw, hh, c) in enumerate([(0, 18, 76, CYAN), (23, 24, 96, VIOLET), (52, 16, 64, YELLOW), (73, 22, 88, GREEN), (100, 20, 104, CORAL), (125, 17, 72, BLUE)]))
    inner = (title(28, 54, "Reader", 26, CYAN_INK) + tx(28, 98, "Off the screen", "d", 20) + spines
             + f'<rect x="{iw - 202}" y="150" width="168" height="3" rx="1.5" fill="{INK}"/>'
             + tx(28, 126, "Books are where I slow down and think.", "b", 14.5, SUB))
    tile("beyond-reader", w, h, inner, edge=CYAN)


# ───────────────────────────── github ─────────────────────────────
def github(d):
    gh, w, h = d["gh"], ROW, 372
    iw, ih = w - 2 * M, h - 2 * MY
    days = gh["days"]
    counts = [c for _, _, c in days]
    total, active = sum(counts), sum(1 for c in counts if c)
    weeks = [sum(counts[i:i + 7]) for i in range(0, len(days), 7)]
    gx, gy, gw, gh_ = 300, 92, iw - 300 - 32, 160
    top, pitch = max(max(weeks), 1), (iw - 300 - 32) / len(weeks)
    scale = max(10, math.ceil(top / 10) * 10)
    axis = "".join(f'<line x1="{gx}" x2="{gx + gw}" y1="{gy + gh_ - gh_ * v / scale:.1f}" y2="{gy + gh_ - gh_ * v / scale:.1f}" stroke="{HAIR}" stroke-width="1.2"/>'
                   + tx(gx - 8, gy + gh_ - gh_ * v / scale + 4, v, "b", 11.5, SUB, "end") for v in (0, scale // 2, scale))
    bars = "".join(f'<rect x="{gx + i * pitch:.1f}" y="{gy + gh_ - max(gh_ * v / scale, 2):.1f}" width="{pitch - 3:.1f}" height="{max(gh_ * v / scale, 2):.1f}" rx="2" '
                   f'fill="{BLUE if v else BORDER}" class="grow" {delay(.2 + i * .018)}/>' for i, v in enumerate(weeks))
    months, seen = "", None
    for i in range(0, len(days), 7):
        m = dt.date.fromisoformat(days[i][0]).strftime("%b")
        if m != seen and i // 7 < len(weeks) - 2:
            months += tx(f"{gx + (i // 7) * pitch:.1f}", gy + gh_ + 20, m, "b", 11.5, SUB)
            seen = m
    stats = (tx(32, 100, "Contributions, last 12 months", "b", 13.5, SUB) + big(30, 150, f"{total:,}", 50)
             + delta(32, 176, sum(counts[-30:]) - sum(counts[-60:-30]), "last 30 days vs the 30 before")
             + tx(32, 214, "Active days", "b", 13.5, SUB) + big(31, 246, active, 28)
             + tx(150, 214, "Own repositories", "b", 13.5, SUB) + big(149, 246, gh["repos"], 28))
    langs = sorted(gh["langs"].items(), key=lambda kv: -kv[1])[:6]
    whole, x, bar, legend = sum(v for _, v in langs), 32.0, "", ""
    shades = [BLUE, GREEN, YELLOW, CORAL, VIOLET, CYAN]
    lx = 32.0
    for i, (name, v) in enumerate(langs):
        bw = (iw - 64) * v / whole
        bar += f'<rect x="{x:.1f}" y="{ih - 62}" width="{max(bw - 3, 2):.1f}" height="10" rx="5" fill="{shades[i]}" class="wide" {delay(.4 + i * .1)}/>'
        txt = f"{name} {100 * v / whole:.0f}%"
        legend += f'<circle cx="{lx + 5:.0f}" cy="{ih - 30}" r="5" fill="{shades[i]}"/>' + tx(f"{lx + 16:.0f}", ih - 25.5, txt, "b", 13, INK)
        lx += len(txt) * 7 + 34
        x += bw
    inner = title(32, 54, "GitHub", 26) + tx(iw - 32, 52, "Contributions per week", "b", 13.5, SUB, "end") + stats + axis + bars + months + bar + legend
    tile("github", w, h, inner, edge=BLUE)


def life_step(g):
    """One generation of Conway's Game of Life on a torus. Cell values are ages (0 = dead), used for colour."""
    rows, cols = len(g), len(g[0])
    nxt = [[0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            n = sum(bool(g[(r + dr) % rows][(c + dc) % cols]) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)
            if g[r][c] and n in (2, 3):
                nxt[r][c] = min(g[r][c] + 1, 4)
            elif not g[r][c] and n == 3:
                nxt[r][c] = 1
    return nxt


def distinct_generations(grid, limit):
    """How many generations pass before the board dies or revisits a state (capped at limit)."""
    alive = lambda g: tuple(tuple(bool(v) for v in row) for row in g)
    seen, n = {alive(grid)}, 0
    while n < limit:
        grid = life_step(grid)
        if alive(grid) in seen or not any(map(any, grid)):
            break
        seen.add(alive(grid))
        n += 1
    return n


LIFE_GENERATIONS = 100
SEEDS = [  # tried in order; the first whose evolution stays new for 100 generations wins
    ("every day with a contribution", lambda level, count: count > 0),
    ("days with two or more contributions", lambda level, count: count >= 2),
    ("days with an odd number of contributions", lambda level, count: count % 2 == 1),
    ("days with three or more contributions", lambda level, count: count >= 3),
    ("days with an even number of contributions", lambda level, count: count > 0 and count % 2 == 0),
]


def life(d):
    days = d["gh"]["days"]
    first = (dt.date.fromisoformat(days[0][0]).weekday() + 1) % 7  # GitHub columns start on Sunday
    cols = math.ceil((first + len(days)) / 7)
    def board(rule):
        g = [[0] * cols for _ in range(7)]
        for i, (_, level, count) in enumerate(days):
            if rule(level, count):
                g[(first + i) % 7][(first + i) // 7] = max(level, 1)
        return g
    scored = [(distinct_generations(board(rule), LIFE_GENERATIONS), name, rule) for name, rule in SEEDS]
    n, seed_name, rule = next((s for s in scored if s[0] >= LIFE_GENERATIONS), max(scored, key=lambda s: s[0]))
    seed = board(rule)
    gens = [[[1 if v else 0 for v in row] for row in seed]]
    for _ in range(n):  # n is 100 whenever a seed sustains it; otherwise the honest, shorter count
        gens.append(life_step(gens[-1]))
    hold, step, fade = 2.6, .2, .9
    total = hold + step * n + fade
    w = ROW
    iw = w - 2 * M
    pitch = (iw - 64) / cols
    y0 = 112
    h = round(y0 + 7 * pitch + 46) + 2 * MY
    ih = h - 2 * MY
    cells, off = "", "#0000"
    for r in range(7):
        for c in range(cols):
            vals, times = [LIFE_GREENS[seed[r][c] - 1] if seed[r][c] else off], [0.0]
            for g, grid in enumerate(gens[1:], 1):
                col = LIFE_GREENS[min(grid[r][c], 3)] if grid[r][c] else off  # newborn cells are lighter, survivors deepen
                if col != vals[-1]:
                    vals.append(col)
                    times.append((hold + step * (g - 1)) / total)
            box = f'x="{32 + c * pitch:.1f}" y="{y0 + r * pitch:.1f}" width="{pitch - 3:.1f}" height="{pitch - 3:.1f}" rx="2.5"'
            cells += f'<rect {box} fill="{CELL}"/>'
            if len(vals) > 1:
                cells += (f'<rect {box} fill="{vals[0]}"><animate attributeName="fill" calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite" '
                          f'values="{";".join(vals)}" keyTimes="{";".join(f"{t:.4f}" for t in times)}"/></rect>')
            elif vals[0] != off:
                cells += f'<rect {box} fill="{vals[0]}"/>'
    # the board fades out on generation n and back in on the seed, so the loop has no visible jump
    veil = (f'<rect x="28" y="{y0 - 4}" width="{iw - 56}" height="{7 * pitch + 6:.0f}" fill="{SURFACE}" opacity="0">'
            f'<animate attributeName="opacity" values="1;0;0;1" keyTimes="0;{.6 / total:.4f};{(total - fade) / total:.4f};1" dur="{total:.2f}s" repeatCount="indefinite"/></rect>')
    inner = (title(32, 54, "Conway's Game of Life", 26) + tx(iw - 32, 52, f"{n} generations per loop", "d", 15, GREEN_INK, "end")
             + tx(32, 82, f"Run on my contribution graph. Seed: {seed_name}.", "b", 14, SUB) + cells + veil
             + f'<rect x="32" y="{ih - 24}" width="{iw - 64}" height="3" rx="1.5" fill="{BORDER}"/>'
               f'<rect x="32" y="{ih - 24}" height="3" rx="1.5" fill="{GREEN}" width="0"><animate attributeName="width" values="0;0;{iw - 64};{iw - 64}" '
               f'keyTimes="0;{hold / total:.4f};{(total - fade) / total:.4f};1" dur="{total:.2f}s" repeatCount="indefinite"/></rect>')
    tile("life", w, h, inner, edge=GREEN)
    return n


# ───────────────────────────── contact and signature ─────────────────────────────
def contact():
    body = (big(M + 2, 84, "Have an interesting problem to solve?", 44) + big(M + 2, 142, "Let's build something.", 44, BLUE_INK)
            + f'<path d="M{M + 4},158 H{M + 424}" stroke="{BLUE}" stroke-width="4" stroke-linecap="round" pathLength="1" stroke-dasharray="1" class="draw"/>'
            + tx(M + 2, 204, "Software engineering internships for summer 2027, and collaborations on developer tools.", "b", 16, SUB))
    write("contact", ROW, 232, body)
    body = (f'<rect x="{ROW / 2 - 20}" y="34" width="40" height="2" rx="1" fill="{BORDER}"/>'
            f'<g class="in" {delay(.2)}>' + tx(ROW / 2 + 7, 104, "心を燃やせ", "j", 40, None, "middle", 'letter-spacing="14"')
            + tx(ROW / 2, 142, "Set your heart ablaze.", "b", 14, SUB, "middle", 'letter-spacing=".4"') + "</g>")
    write("signature", ROW, 176, body)


# ───────────────────────────── README ─────────────────────────────
def img(name, width, alt, href=None):
    tag = f'<img src="assets/{name}.svg" width="{width}" alt="{html.escape(alt)}">'
    return f'<a href="{href}">{tag}</a>' if href else tag


def rows(*lines):
    """Bento rows: tiles in a row touch (their gutters are baked in), rows are separated by <br>."""
    return '<p align="center">\n' + "<br>\n".join("".join(r) for r in lines) + "\n</p>\n"


def readme(d, bw, life_n):
    cf, lc, cc = d["cf"], d["lc"], d["cc"]
    rank = cf_rank(cf["rating"])[0]
    gh = "https://github.com/AayushBadoni18/"
    parts = [
        "<!-- Generated by scripts/build.py. Edit the copy and layout there, then run it; changes made here are overwritten. -->\n",
        rows([img("hero", ROW, "Aayush Badoni. Competitive programmer, software engineer, designer. B.E. Information Technology, Army Institute of Technology Pune, class of 2028. Open to SDE internships for summer 2027.")],
             [img("btn-email", bw["btn-email"], "Email " + EMAIL, "mailto:" + EMAIL), img("btn-linkedin", bw["btn-linkedin"], "LinkedIn", LINKEDIN)],
             [img("btn-cf", bw["btn-cf"], "Codeforces profile", URLS["cf"]), img("btn-lc", bw["btn-lc"], "LeetCode profile", URLS["lc"]),
              img("btn-cc", bw["btn-cc"], "CodeChef profile", URLS["cc"]), img("btn-hr", bw["btn-hr"], "HackerRank profile", URLS["hr"])]),
        '<p align="center">I compete in programming contests, build browser extensions and full-stack products, '
        "and care how the result looks: I was a poster artist before I was a programmer.</p>\n",
        rows([img("h-highlights", ROW, "Highlights")],
             [img("hl-barclays", 490, "Barclays Hack-O-Hire national finals: top 48 of 3,000+ teams, finalist as team captain."),
              img("hl-academics", 340, "Academics: third year, first semester. B.E. Information Technology, Army Institute of Technology Pune, class of 2028.")],
             [img("hl-icpc", 340, "ICPC 2026: shortlisted, Kanpur Regional."),
              img("hl-bigcode", 490, "Google's The Big Code: top 1,500, qualified for Round 2.")]),
        rows([img("h-cp", ROW, "Competitive Programming")],
             [img("cp-codeforces", ROW, f"Codeforces: {rank}, current rating {cf['rating']}, peak {cf['max']}, {len(cf['ratings'])} rated contests, {cf['solved']} problems solved, with a rating graph.", URLS["cf"])],
             [img("cp-leetcode", 490, f"LeetCode: {lc['solved']['All']} problems solved ({lc['solved']['Easy']} easy, {lc['solved']['Medium']} medium, {lc['solved']['Hard']} hard), {len(lc['badges'])} badges.", URLS["lc"]),
              img("cp-hackerrank", 340, f"HackerRank: {HACKERRANK_STARS}-star in Problem Solving.", URLS["hr"])],
             [img("cp-codechef", 490, f"CodeChef: rating {cc['rating']}, {sum(1 for f in CC_FLOORS if f <= cc['rating'])}-star, with a rating graph over {len(cc['contests'])} rated contests.", URLS["cc"]),
              img("cp-total", 340, f"Across platforms: {cf['solved'] + lc['solved']['All'] + cc['solved']} problems solved, {len(cf['ratings']) + len(cc['contests'])} rated contests.")]),
        rows([img("h-projects", ROW, "Projects")],
             [img("project-forex", ROW, "Forex Hover Pro: a Manifest V3 browser extension. Hover a price on any site and read it in your own currencies. TypeScript.", gh + "Forex-Hover")],
             [img("project-accessbridge", 470, "AccessBridge AI: a browser extension that simplifies dense text, decodes tone and describes images. JavaScript, Manifest V3, OpenRouter.", gh + "AccessBridge-AI"),
              img("project-agniview", 360, "AgniView: tells a wildfire from a steel plant in NASA FIRMS satellite heat data. Python, Flask, PostGIS, Next.js, Docker.", gh + "AgniView")],
             [img("project-sahayog", ROW, "Sahayog: a team-built disaster response platform with alerts, incident reports, a hazard map and SOS. React, TypeScript, Leaflet, Express, MongoDB.", gh + "sahayog")]),
        rows([img("h-stack", ROW, "Tech Stack")],
             [img("stack-languages", 490, "Programming Languages: C++, C, Python, Java, JavaScript, TypeScript."), img("stack-frontend", 340, "Frontend Development: React, Next.js, Tailwind CSS, HTML, CSS.")],
             [img("stack-backend", 290, "Backend Development: Node.js, Express, Flask."), img("stack-data", 210, "Databases: MongoDB, PostgreSQL."), img("stack-aiml", 330, "AI / ML: " + ", ".join(AI_ML) + ".")],
             [img("stack-aitools", ROW, "AI-Assisted Development and Tools: Claude Code, Cline, Google Antigravity, GitHub Copilot, OmniRoute, VS Code, Git, GitHub.")],
             [img("stack-dev", 490, "Development and Infrastructure: Docker, Git, GitHub, VS Code, IntelliJ IDEA, PyCharm."), img("stack-core", 340, "CS Fundamentals: " + ", ".join(CORE) + ".")],
             [img("focus", ROW, "Current focus: large language models, multi-agent orchestration, backend systems, developer tools, interface design.")]),
        rows([img("h-beyond", ROW, "Beyond the Coder")],
             [img("beyond-designer", 490, "Designer: three-time state-level winner in poster making."), img("beyond-athlete", 340, "Athlete: track and field, college athletics team.")],
             [img("beyond-reader", ROW, "Reader: books are where I slow down and think.")]),
        rows([img("h-activity", ROW, "Activity")],
             [img("github", ROW, "GitHub activity: contributions over the last 12 months by week, active days, and languages across my repositories.", "https://github.com/" + GITHUB)],
             [img("life", ROW, f"Conway's Game of Life, seeded by my GitHub contribution graph, {life_n} generations per loop.")]),
        rows([img("contact", ROW, "Have an interesting problem to solve? Let's build something.")],
             [img("signature", ROW, "心を燃やせ. Set your heart ablaze.")]),
    ]
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts))


def main():
    d = load_data()
    change, since = week_change(d)
    hero()
    for slug, num, text, note in [("highlights", "01", "Highlights", "the short version"), ("cp", "02", "Competitive Programming", "live numbers, rebuilt daily"),
                                  ("projects", "03", "Projects", "four things I built"), ("stack", "04", "Tech Stack", "what I reach for"),
                                  ("beyond", "05", "Beyond the Coder", "the other half"), ("activity", "06", "Activity", "last twelve months")]:
        heading(slug, num, text, note)
    bw = {"btn-email": button("btn-email", EMAIL, GMAIL, 27, 20), "btn-linkedin": button("btn-linkedin", "LinkedIn", LINKEDIN_LOGO, 22)}
    for slug, name, color in [("cf", "Codeforces", cf_rank(d["cf"]["rating"])[1]), ("lc", "LeetCode", LC[1]), ("cc", "CodeChef", CC_STAR), ("hr", "HackerRank", HR)]:
        bw["btn-" + slug] = button("btn-" + slug, name, f'<circle cx="6" cy="11" r="6" fill="{color}"/>', 12)
    highlights(d)
    cp_codeforces(d)
    cp_leetcode(d, change, since)
    cp_hackerrank()
    cp_codechef(d)
    cp_total(d, change, since)
    projects()
    stack()
    focus()
    beyond()
    github(d)
    gens = life(d)
    contact()
    readme(d, bw, gens)
    for name in os.listdir(VENDOR):  # font subsets are keyed by the characters on a tile, so old ones pile up as numbers change
        if name.startswith("font-") and name not in USED:
            os.remove(os.path.join(VENDOR, name))
    text = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    for name in os.listdir(ASSETS):  # tiles the README no longer uses
        if name.endswith(".svg") and f"assets/{name}" not in text:
            os.remove(os.path.join(ASSETS, name))

    # self-checks: Life rules hold, every SVG is well-formed, and the README references only files that exist
    import xml.etree.ElementTree as ET
    blinker = life_step([[0, 0, 0, 0, 0], [0, 0, 1, 0, 0], [0, 0, 1, 0, 0], [0, 0, 1, 0, 0], [0, 0, 0, 0, 0]])
    assert [bool(v) for v in blinker[2]] == [False, True, True, True, False], "Game of Life rule broken"
    svgs = [n for n in os.listdir(ASSETS) if n.endswith(".svg")]
    for name in svgs:
        ET.parse(os.path.join(ASSETS, name))  # our own output, not untrusted input
    missing = [p for p in re.findall(r'src="(assets/[^"]+)"', text) if not os.path.exists(os.path.join(ROOT, p))]
    assert not missing, f"README references missing files: {missing}"
    size = sum(os.path.getsize(os.path.join(ASSETS, n)) for n in svgs)
    print(f"built {len(svgs)} tiles, {size // 1024} KB; CF {d['cf']['rating']}, LC {d['lc']['solved']['All']}, CC {d['cc']['rating']}, life {gens} generations")


if __name__ == "__main__":
    main()
