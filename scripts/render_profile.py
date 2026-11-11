#!/usr/bin/env python3
"""Render a paper-and-ink GitHub profile using self-contained animated SVG cards."""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import re
import urllib.request
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USERNAME = "anuragdoesntex1sts"
CARDS = ROOT / "cards"
DATA = ROOT / "data"
FONTS = ROOT / "fonts"
STATIC = os.getenv("STATIC") == "1"
OFFLINE = os.getenv("OFFLINE") == "1"

# Same paper, ink, and three-world palette as the reference: BUILD blue,
# BRAND red, LEARN yellow. The text and projects are Anurag's own.
PAPER = "#f3f3f1"
PAPER_DARK = "#e2e2de"
INK = "#111111"
INK_SOFT = "#3a3a3c"
MUTED = "#6e6e73"
RULE = "#dcdcd7"
BLUE = "#2f55ff"
RED = "#ef3b2d"
YELLOW = "#ffc81a"
HEAT = ["#e6e9f6", "#cbd4fb", "#a8b8ff", "#718dff", BLUE]
W = 880

FONT_FILES = {
    "serif": ("Instrument Serif", "normal", 400, "serif-400.woff.b64"),
    "serif-i": ("Instrument Serif", "italic", 400, "serif-italic.woff.b64"),
    "sans": ("Geist", "normal", 400, "geist-400.woff.b64"),
    "sans-b": ("Geist", "normal", 600, "geist-600.woff.b64"),
    "mono": ("Geist Mono", "normal", 400, "geistmono-400.woff.b64"),
}

BASE_CSS = """
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes pop{0%{opacity:0;transform:scale(.3)}70%{opacity:1;transform:scale(1.12)}100%{opacity:1;transform:none}}
@keyframes tilein{0%{opacity:0;transform:translateY(70px) scale(.72) rotate(-6deg)}60%{opacity:1;transform:translateY(-6px) scale(1.02) rotate(1deg)}100%{opacity:1;transform:none}}
@keyframes sheen{0%{transform:translateX(-180px) skewX(-20deg)}25%,100%{transform:translateX(350px) skewX(-20deg)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.28}}
.r{opacity:0;animation:rise .72s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box}
.f{opacity:0;animation:fade .8s ease-out both}
.g{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .75s cubic-bezier(.2,.7,.2,1) both}
.p{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .42s ease-out both}
.ti{opacity:0;transform-box:fill-box;transform-origin:50% 60%;animation:tilein 1s cubic-bezier(.2,.8,.2,1) both}
.sh{animation:sheen 5.5s ease-in-out infinite}
.live{animation:pulse 1.6s ease-in-out infinite}
.portrait{opacity:0;animation:fade .45s ease-out both}
@media(prefers-reduced-motion:reduce){.r,.f,.g,.p,.ti,.sh,.live,.portrait{animation:none!important;opacity:1!important;transform:none!important}.sh{display:none!important}}
"""

STATIC_CSS = ".r,.f,.g,.p,.ti,.live,.portrait{animation:none!important;opacity:1!important;transform:none!important}.sh{display:none!important}"


class ContributionParser(HTMLParser):
    """Read public day counts from GitHub's contribution-calendar HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.days: dict[str, tuple[int, int]] = {}
        self.id_dates: dict[str, str] = {}
        self.active_tooltip: str | None = None
        self.tooltip_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        date = data.get("data-date")
        if date:
            try:
                day = dt.date.fromisoformat(date)
            except ValueError:
                return
            count_match = re.search(r"(\d+) contributions?", data.get("aria-label", ""))
            count = int(data.get("data-count") or (count_match.group(1) if count_match else 0))
            level = int(data.get("data-level") or 0)
            self.days[day.isoformat()] = (count, level)
            if data.get("id"):
                self.id_dates[data["id"]] = day.isoformat()
        if tag == "tool-tip" and data.get("for") in self.id_dates:
            self.active_tooltip = self.id_dates[data["for"]]
            self.tooltip_text = ""

    def handle_data(self, data: str) -> None:
        if self.active_tooltip:
            self.tooltip_text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "tool-tip" and self.active_tooltip:
            match = re.search(r"(\d+) contributions?", self.tooltip_text)
            date = self.active_tooltip
            _, level = self.days[date]
            self.days[date] = (int(match.group(1)) if match else 0, level)
            self.active_tooltip = None
            self.tooltip_text = ""


def font_faces(keys: tuple[str, ...]) -> str:
    faces = []
    for key in keys:
        family, style, weight, filename = FONT_FILES[key]
        encoded = (FONTS / filename).read_text(encoding="ascii").strip()
        faces.append(
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};"
            f"src:url(data:font/woff;base64,{encoded}) format('woff')}}"
        )
    return "".join(faces)


def svg_doc(width: int, height: int, label: str, body: str,
            fonts: tuple[str, ...], extra_css: str = "") -> str:
    css = font_faces(fonts) + BASE_CSS + extra_css
    if STATIC:
        css += STATIC_CSS
    title = html.escape(label)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{title}">'
        f"<title>{title}</title><style>{css}</style>{body}</svg>"
    )


def fetch_days() -> dict[str, tuple[int, int]]:
    url = f"https://github.com/users/{USERNAME}/contributions"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "anurag-profile-card-renderer", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        parser = ContributionParser()
        parser.feed(response.read().decode("utf-8", errors="replace"))
    if not parser.days:
        raise RuntimeError("GitHub returned no contribution days; existing cards were left untouched")
    return parser.days


def save_days(days: dict[str, tuple[int, int]]) -> None:
    DATA.mkdir(exist_ok=True)
    payload = {"username": USERNAME, "days": {k: list(v) for k, v in sorted(days.items())}}
    (DATA / "contributions.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_days() -> dict[str, tuple[int, int]]:
    path = DATA / "contributions.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: (int(v[0]), int(v[1])) for k, v in raw.get("days", {}).items()}


def calendar_data(days: dict[str, tuple[int, int]]):
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    calendar = []
    for index in range(365):
        day = start + dt.timedelta(days=index)
        count, level = days.get(day.isoformat(), (0, 0))
        calendar.append((day, count, level))

    total = sum(count for _, count, _ in calendar)
    active = sum(count > 0 for _, count, _ in calendar)
    streak = 0
    cursor = today
    if days.get(cursor.isoformat(), (0, 0))[0] == 0:
        cursor -= dt.timedelta(days=1)
    while days.get(cursor.isoformat(), (0, 0))[0] > 0:
        streak += 1
        cursor -= dt.timedelta(days=1)

    weekdays = defaultdict(int)
    months = defaultdict(int)
    for day, count, _ in calendar:
        weekdays[day.strftime("%A")] += count
        months[(day.year, day.month)] += count
    busiest = max(weekdays, key=weekdays.get) if weekdays and max(weekdays.values()) else "—"
    period_keys = sorted(months)[-12:]
    bars = [(dt.date(year, month, 1).strftime("%b"), months[(year, month)]) for year, month in period_keys]
    return calendar, total, active, streak, busiest, bars


def render_hero() -> str:
    portrait_rows = (DATA / "avatar-ascii.txt").read_text(encoding="utf-8").splitlines()
    portrait = "".join(
        f'<text class="portrait" style="animation-delay:{0.5 + i * 0.018:.3f}s" '
        f'x="588" y="{38 + i * 5.3:.1f}" xml:space="preserve" '
        f'font-family="Geist Mono,monospace" font-size="5.2" fill="{INK}">{html.escape(row)}</text>'
        for i, row in enumerate(portrait_rows)
    )
    body = f'''<rect width="880" height="360" fill="{PAPER}"/>
      <circle class="p" cx="60" cy="48" r="3" fill="{BLUE}"/>
      <text class="r" x="74" y="52" font-family="Geist Mono,monospace" font-size="10" letter-spacing="1.4" fill="{MUTED}">STUDENT DEVELOPER · GOOGLE CLOUD STUDY JAM</text>
      <text class="r" style="animation-delay:.12s" x="53" y="157" font-family="Instrument Serif,Georgia,serif" font-size="96" fill="{INK}">Anurag</text>
      <defs><linearGradient id="nameblue" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{INK}"/><stop offset=".42" stop-color="{BLUE}"/><stop offset=".68" stop-color="{BLUE}"/><stop offset="1" stop-color="{INK}"/><animateTransform attributeName="gradientTransform" type="translate" values="-1 0;1 0;-1 0" dur="7s" repeatCount="indefinite"/></linearGradient></defs>
      <text class="r" style="animation-delay:.24s" x="53" y="247" font-family="Instrument Serif,Georgia,serif" font-size="96" fill="url(#nameblue)">Naskar</text>
      <text class="r" style="animation-delay:.38s" x="58" y="283" font-family="Geist,Arial,sans-serif" font-size="15" fill="{INK_SOFT}">I build web apps, explore machine learning, and keep learning in public.</text>
      <text class="f" style="animation-delay:.52s" x="58" y="316" font-family="Geist Mono,monospace" font-size="10" letter-spacing="1" fill="{MUTED}">19 GOOGLE CLOUD STUDY JAM BADGES</text>
      {portrait}'''
    return svg_doc(880, 360, "Anurag Naskar — student developer building web apps and exploring machine learning", body,
                   ("serif", "sans", "mono"))


def render_heatmap(calendar) -> str:
    first_day = calendar[0][0]
    first_sunday = first_day - dt.timedelta(days=(first_day.weekday() + 1) % 7)
    cells = []
    month_labels = []
    seen_months = set()
    for day, _, level in calendar:
        week = (day - first_sunday).days // 7
        weekday = (day.weekday() + 1) % 7
        color = HEAT[min(max(level, 0), len(HEAT) - 1)]
        delay = (week * 7 + weekday) * 0.0055
        cells.append(
            f'<rect class="p" style="animation-delay:{delay:.3f}s" '
            f'x="{50 + week * 15}" y="{61 + weekday * 14}" width="11" height="11" rx="2" fill="{color}"/>'
        )
        key = (day.year, day.month)
        if day.day <= 7 and key not in seen_months:
            seen_months.add(key)
            month_labels.append(
                f'<text class="f" style="animation-delay:{delay:.3f}s" x="{50 + week * 15}" y="176" '
                f'font-family="Geist,Arial,sans-serif" font-size="10" fill="{MUTED}">{day.strftime("%b")}</text>'
            )
    body = f'''<rect width="880" height="198" fill="{PAPER}"/>
      <text class="r" x="50" y="36" font-family="Instrument Serif,Georgia,serif" font-size="30" fill="{INK}">Every day, <tspan fill="{BLUE}" font-style="italic">in blue</tspan></text>
      <text class="f" x="690" y="34" text-anchor="end" font-family="Geist Mono,monospace" font-size="9" letter-spacing="1" fill="{MUTED}">PUBLIC CONTRIBUTIONS · LAST YEAR</text>
      {''.join(cells)}{''.join(month_labels)}
      <text x="50" y="194" font-family="Geist,Arial,sans-serif" font-size="9" fill="{MUTED}">Less</text>
      {''.join(f'<rect x="{83 + i * 14}" y="185" width="9" height="9" rx="2" fill="{color}"/>' for i, color in enumerate(HEAT))}
      <text x="160" y="194" font-family="Geist,Arial,sans-serif" font-size="9" fill="{MUTED}">More</text>'''
    return svg_doc(880, 202, "Public GitHub contributions, shown as a blue daily heatmap", body,
                   ("serif", "sans", "mono"))


def render_activity(total: int, active: int, streak: int, busiest: str, bars) -> str:
    max_value = max((value for _, value in bars), default=0) or 1
    bar_svg = []
    start_x, gap, bar_width, baseline, max_height = 414, 37, 23, 153, 79
    for i, (month, value) in enumerate(bars):
        height = max(3, max_height * value / max_value)
        x = start_x + i * gap
        y = baseline - height
        color = BLUE if value == max_value and value > 0 else INK
        delay = .22 + i * .075
        bar_svg.append(
            f'<rect class="g" style="animation-delay:{delay:.2f}s" x="{x}" y="{y:.1f}" '
            f'width="{bar_width}" height="{height:.1f}" rx="5" fill="{color}"/>'
        )
        if value == max_value and value > 0:
            bar_svg.append(
                f'<text class="f" style="animation-delay:{delay + .5:.2f}s" x="{x + bar_width / 2}" '
                f'y="{y - 7:.1f}" text-anchor="middle" font-family="Geist,Arial,sans-serif" '
                f'font-size="10" fill="{BLUE}">{value:,}</text>'
            )
        bar_svg.append(
            f'<text class="f" style="animation-delay:{delay:.2f}s" x="{x + bar_width / 2}" y="174" '
            f'text-anchor="middle" font-family="Geist,Arial,sans-serif" font-size="9" fill="{MUTED}">{month}</text>'
        )
    body = f'''<rect width="880" height="207" rx="16" fill="{PAPER}"/>
      <text class="f" x="50" y="33" font-family="Geist Mono,monospace" font-size="9" letter-spacing="1.2" fill="{MUTED}">THE LAST 12 MONTHS ON GITHUB</text>
      <text class="r" style="animation-delay:.08s" x="48" y="88" font-family="Instrument Serif,Georgia,serif" font-size="48" fill="{INK}">{total:,}<tspan font-style="italic"> contributions</tspan></text>
      <text class="f" style="animation-delay:.18s" x="51" y="120" font-family="Geist,Arial,sans-serif" font-size="11" fill="{INK_SOFT}">{active} active days  ·  {streak}-day streak</text>
      <text class="f" style="animation-delay:.25s" x="51" y="140" font-family="Geist,Arial,sans-serif" font-size="11" fill="{MUTED}">Busiest day: {html.escape(busiest)}</text>
      <path d="M405 153 H854" stroke="{RULE}" stroke-width="1"/>{''.join(bar_svg)}'''
    return svg_doc(880, 207, f"{total:,} public GitHub contributions, with monthly bars, active days, streak, and busiest weekday", body,
                   ("serif", "serif-i", "sans", "mono"))


def render_world_tile(name: str, title: str, lines: tuple[str, str], accent: str, pale: str, index: int) -> str:
    body = f'''<rect width="293" height="194" fill="{PAPER}"/>
      <defs><clipPath id="clip"><rect x="5" y="4" width="281" height="178" rx="13"/></clipPath></defs>
      <g clip-path="url(#clip)"><rect x="5" y="4" width="281" height="178" fill="{pale}"/><rect x="5" y="79" width="281" height="103" fill="{accent}"/>
      <text class="r" style="animation-delay:{index * .15:.2f}s" x="23" y="30" font-family="Geist Mono,monospace" font-size="9" letter-spacing="1.3" fill="{accent}">{html.escape(name)}</text>
      <text class="r" style="animation-delay:{index * .15 + .08:.2f}s" x="21" y="69" font-family="Instrument Serif,Georgia,serif" font-size="35" fill="{INK}">{html.escape(title)}</text>
      <text class="f" style="animation-delay:{index * .15 + .28:.2f}s" x="23" y="110" font-family="Geist,Arial,sans-serif" font-size="11" fill="{INK if accent == YELLOW else '#ffffff'}">{html.escape(lines[0])}</text>
      <text class="f" style="animation-delay:{index * .15 + .36:.2f}s" x="23" y="130" font-family="Geist,Arial,sans-serif" font-size="11" fill="{INK if accent == YELLOW else '#ffffff'}">{html.escape(lines[1])}</text>
      <path class="f" style="animation-delay:{index * .15 + .44:.2f}s" d="M248 155h21m-7-7 7 7-7 7" fill="none" stroke="{INK if accent == YELLOW else '#ffffff'}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      <rect class="sh" x="-80" y="4" width="48" height="178" fill="#ffffff" opacity=".23"/></g>'''
    return svg_doc(293, 194, f"{name}: {title} — {lines[0]} {lines[1]}", body,
                   ("serif", "sans", "mono"))


def render_coding_title() -> str:
    body = f'''<rect width="880" height="74" fill="{PAPER}"/>
      <text class="r" x="50" y="48" font-family="Instrument Serif,Georgia,serif" font-size="34" fill="{INK}">What I’m coding</text>
      <rect class="f" style="animation-delay:.2s" x="50" y="60" width="66" height="4" rx="2" fill="{YELLOW}"/>'''
    return svg_doc(880, 74, "What Anurag is coding", body, ("serif",))


def render_repo_card(name: str, category: str, description: tuple[str, str], url: str, index: int) -> str:
    body = f'''<rect width="293" height="175" fill="{PAPER}"/>
      <rect x="6" y="3" width="280" height="164" rx="12" fill="{PAPER}" stroke="{RULE}"/>
      <text class="f" x="22" y="29" font-family="Geist Mono,monospace" font-size="9" letter-spacing="1" fill="{MUTED}">{html.escape(category.upper())}</text>
      <text class="r" style="animation-delay:{index * .12:.2f}s" x="20" y="68" font-family="Instrument Serif,Georgia,serif" font-size="27" fill="{INK}">{html.escape(name)}</text>
      <text class="f" style="animation-delay:{index * .12 + .12:.2f}s" x="22" y="99" font-family="Geist,Arial,sans-serif" font-size="10.5" fill="{INK_SOFT}">{html.escape(description[0])}</text>
      <text class="f" style="animation-delay:{index * .12 + .2:.2f}s" x="22" y="117" font-family="Geist,Arial,sans-serif" font-size="10.5" fill="{INK_SOFT}">{html.escape(description[1])}</text>
      <text class="f" style="animation-delay:{index * .12 + .28:.2f}s" x="22" y="147" font-family="Geist Mono,monospace" font-size="8.5" letter-spacing=".5" fill="{BLUE}">VIEW PROJECT  ↗</text>'''
    return svg_doc(293, 175, f"{name}: {description[0]} {description[1]}", body,
                   ("serif", "sans", "mono"))


def write_card(name: str, contents: str) -> None:
    CARDS.mkdir(exist_ok=True)
    (CARDS / name).write_text(contents + "\n", encoding="utf-8")


def main() -> None:
    if OFFLINE:
        days = read_days()
    elif STATIC:
        days = read_days()
    else:
        days = fetch_days()
        save_days(days)
    calendar, total, active, streak, busiest, bars = calendar_data(days)

    write_card("hero-portrait.svg", render_hero())
    write_card("heatmap.svg", render_heatmap(calendar))
    write_card("activity.svg", render_activity(total, active, streak, busiest, bars))
    write_card("build.svg", render_world_tile("BUILD", "CineLock", ("Cinema booking, seat holds", "and reconciled checkout."), BLUE, "#e5e9ff", 0))
    write_card("brand.svg", render_world_tile("BRAND", "RedVeg", ("A storefront and admin", "prototype for commerce."), RED, "#f8e2df", 1))
    write_card("learn.svg", render_world_tile("LEARN", "19× badges", ("Google Cloud Study Jam", "and applied ML in Python."), YELLOW, "#fff1bb", 2))
    write_card("title-coding.svg", render_coding_title())
    write_card("repo-cinelock.svg", render_repo_card("CineLock", "TypeScript · FastAPI", ("A full-stack cinema booking", "experience with temporary seats."), "https://github.com/anuragdoesntex1sts/CineLock", 0))
    write_card("repo-redveg.svg", render_repo_card("RedVeg Commerce", "TypeScript · React", ("A mobile-first storefront and", "responsive admin prototype."), "https://github.com/anuragdoesntex1sts/redveg-commerce-ui", 1))
    write_card("repo-disease.svg", render_repo_card("Disease Prediction", "Python · Machine Learning", ("Model comparisons with recall", "and F1 on medical data."), "https://github.com/anuragdoesntex1sts/CodeAlpha_Disease-Prediction-from-Medical-Data", 2))
    print(f"Rendered 10 Three Worlds cards from {total} public contributions")


if __name__ == "__main__":
    main()

