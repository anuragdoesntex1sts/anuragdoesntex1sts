#!/usr/bin/env python3
"""Fetch public contribution activity and render self-contained profile SVG cards."""

from __future__ import annotations

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
STATIC = os.getenv("STATIC") == "1"
INK = "#e9eefb"
MUTED = "#a6b2cc"
PANEL = "#111a2d"
ACCENT = "#77e0c3"
BLUE = "#8ca8ff"
LEVELS = ["#1b2740", "#214c54", "#277968", "#40b897", "#8af0cc"]


class ContributionParser(HTMLParser):
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
            count, level = self.days[date]
            self.days[date] = (int(match.group(1)) if match else 0, level)
            self.active_tooltip = None
            self.tooltip_text = ""


def fetch_days() -> dict[str, tuple[int, int]]:
    url = f"https://github.com/users/{USERNAME}/contributions"
    request = urllib.request.Request(url, headers={"User-Agent": "profile-readme-renderer"})
    with urllib.request.urlopen(request, timeout=30) as response:
        parser = ContributionParser()
        parser.feed(response.read().decode("utf-8", errors="replace"))
    if not parser.days:
        raise RuntimeError("GitHub returned no contribution days; leaving existing cards untouched")
    return parser.days


def save_data(days: dict[str, tuple[int, int]]) -> None:
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "contributions.json").write_text(
        json.dumps({"username": USERNAME, "days": {k: list(v) for k, v in sorted(days.items())}}, indent=2) + "\n",
        encoding="utf-8",
    )


def read_data() -> dict[str, tuple[int, int]]:
    path = ROOT / "data" / "contributions.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: (int(v[0]), int(v[1])) for k, v in raw.get("days", {}).items()}


def metrics(days: dict[str, tuple[int, int]]) -> tuple[int, int, int, list[tuple[str, int]], list[tuple[dt.date, int]]]:
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    calendar = []
    for n in range(365):
        day = start + dt.timedelta(days=n)
        count, level = days.get(day.isoformat(), (0, 0))
        calendar.append((day, count))
    active = sum(count > 0 for _, count in calendar)
    best = max((count for _, count in calendar), default=0)
    streak = 0
    cursor = today
    if days.get(cursor.isoformat(), (0, 0))[0] == 0:
        cursor -= dt.timedelta(days=1)
    while days.get(cursor.isoformat(), (0, 0))[0] > 0:
        streak += 1
        cursor -= dt.timedelta(days=1)
    monthly: dict[str, int] = defaultdict(int)
    for day, count in calendar:
        monthly[day.strftime("%b")] += count
    bars = [(key, value) for key, value in monthly.items()]
    return sum(c for _, c in calendar), active, streak, bars, calendar


def animation_css() -> str:
    if STATIC:
        return ""
    return """<style>
      @keyframes rise { from { opacity:0; transform:translateY(12px) } to { opacity:1; transform:translateY(0) } }
      @keyframes sweep { 0%,72%,100% { transform:translateX(-120px); opacity:0 } 8%,60% { opacity:.7 } 35% { transform:translateX(680px); opacity:0 } }
      @keyframes pop { from { opacity:0; transform:scale(.55) } to { opacity:1; transform:scale(1) } }
      .intro { animation:rise .7s ease-out both }
      .shine { animation:sweep 7s ease-in-out infinite }
      .cell { transform-box:fill-box; transform-origin:center; animation:pop .38s ease-out both }
      @media (prefers-reduced-motion: reduce) { *,*::before,*::after { animation:none !important; transition:none !important } }
    </style>"""


def svg_open(width: int, height: int, title: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">'


def render_hero() -> str:
    return f'''{svg_open(1000, 250, "Anurag Naskar — student developer")}
    <defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#101a31"/><stop offset="1" stop-color="#1a2943"/></linearGradient><linearGradient id="shine"><stop stop-color="{ACCENT}" stop-opacity="0"/><stop offset=".5" stop-color="{ACCENT}" stop-opacity=".55"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient></defs>
    {animation_css()}<rect width="1000" height="250" rx="24" fill="url(#bg)"/><circle cx="890" cy="30" r="180" fill="#6d83ff" opacity=".08"/><circle cx="960" cy="210" r="130" fill="{ACCENT}" opacity=".07"/>
    <g class="intro"><text x="62" y="68" fill="{ACCENT}" font-family="ui-monospace,monospace" font-size="16" letter-spacing="3">ANURAG NASKAR  /  DEVELOPER</text><text x="58" y="148" fill="{INK}" font-family="Arial,sans-serif" font-size="62" font-weight="700">Building ideas into</text><text x="58" y="215" fill="{INK}" font-family="Arial,sans-serif" font-size="62" font-weight="700">useful software.</text><rect class="shine" x="60" y="86" width="90" height="150" fill="url(#shine)" opacity=".35"/></g>
    <text x="760" y="94" fill="{MUTED}" font-family="ui-monospace,monospace" font-size="15">FOCUS</text><text x="760" y="128" fill="{INK}" font-family="Arial,sans-serif" font-size="19">Web apps</text><text x="760" y="158" fill="{INK}" font-family="Arial,sans-serif" font-size="19">Applied ML</text><text x="760" y="188" fill="{INK}" font-family="Arial,sans-serif" font-size="19">Cloud learning</text>
    </svg>'''


def project_card(title: str, category: str, description: str, accent: str, index: int) -> str:
    return f'''{svg_open(320, 180, title + " — " + description)}{animation_css()}<rect width="320" height="180" rx="20" fill="{PANEL}" stroke="#2a3854"/><circle cx="277" cy="39" r="22" fill="{accent}" opacity=".16"/><text x="277" y="45" text-anchor="middle" fill="{accent}" font-family="Arial,sans-serif" font-size="17" font-weight="700">0{index}</text><text x="24" y="41" fill="{accent}" font-family="ui-monospace,monospace" font-size="11" letter-spacing="1.5">{html.escape(category.upper())}</text><text x="24" y="82" fill="{INK}" font-family="Arial,sans-serif" font-size="25" font-weight="700">{html.escape(title)}</text><text x="24" y="113" fill="{MUTED}" font-family="Arial,sans-serif" font-size="13">{html.escape(description)}</text><path d="M24 147h48" stroke="{accent}" stroke-width="3" stroke-linecap="round"/><path d="M66 141l7 6-7 6" fill="none" stroke="{accent}" stroke-width="2"/></svg>'''


def render_activity(days: dict[str, tuple[int, int]]) -> str:
    total, active, streak, bars, calendar = metrics(days)
    width, height = 1000, 245
    cells = []
    # Align the displayed 53-week grid to Sunday rows, as GitHub does.
    first = calendar[0][0] - dt.timedelta(days=(calendar[0][0].weekday() + 1) % 7)
    for day, count in calendar:
        week = (day - first).days // 7
        weekday = (day.weekday() + 1) % 7
        level = days.get(day.isoformat(), (0, 0))[1]
        color = LEVELS[min(max(level, 0), 4)]
        delay = (week * 7 + weekday) * 0.006
        cells.append(f'<rect class="cell" style="animation-delay:{delay:.3f}s" x="{34+week*13}" y="{127+weekday*13}" width="9" height="9" rx="3" fill="{color}"/>')
    max_month = max((n for _, n in bars), default=1) or 1
    bar_svg = []
    for i, (month, value) in enumerate(bars):
        h = max(2, int(44 * value / max_month))
        x = 754 + i * 17
        bar_svg.append(f'<rect x="{x}" y="{177-h}" width="10" height="{h}" rx="4" fill="{BLUE if value == max_month else ACCENT}" opacity="{.95 if value == max_month else .55}"/>')
    return f'''{svg_open(width,height,"Public GitHub contributions: last 365 days")}{animation_css()}<rect width="1000" height="245" rx="22" fill="{PANEL}" stroke="#2a3854"/><text x="32" y="42" fill="{INK}" font-family="Arial,sans-serif" font-size="21" font-weight="700">A year of showing up</text><text x="32" y="71" fill="{MUTED}" font-family="Arial,sans-serif" font-size="13">Public GitHub contributions · trailing 12 months</text><text x="32" y="111" fill="{ACCENT}" font-family="Arial,sans-serif" font-size="26" font-weight="700">{total:,}</text><text x="32" y="132" fill="{MUTED}" font-family="Arial,sans-serif" font-size="11">CONTRIBUTIONS</text><text x="202" y="111" fill="{BLUE}" font-family="Arial,sans-serif" font-size="26" font-weight="700">{active}</text><text x="202" y="132" fill="{MUTED}" font-family="Arial,sans-serif" font-size="11">ACTIVE DAYS</text><text x="344" y="111" fill="{INK}" font-family="Arial,sans-serif" font-size="26" font-weight="700">{streak}</text><text x="344" y="132" fill="{MUTED}" font-family="Arial,sans-serif" font-size="11">DAY STREAK</text>{''.join(bar_svg)}<text x="754" y="202" fill="{MUTED}" font-family="Arial,sans-serif" font-size="10">MONTHLY TOTALS</text>{''.join(cells)}<text x="34" y="231" fill="{MUTED}" font-family="Arial,sans-serif" font-size="10">Less</text>{''.join(f'<rect x="{72+i*14}" y="221" width="9" height="9" rx="3" fill="{c}"/>' for i,c in enumerate(LEVELS))}<text x="133" y="231" fill="{MUTED}" font-family="Arial,sans-serif" font-size="10">More</text></svg>'''


def write_card(name: str, content: str) -> None:
    (CARDS / name).write_text(content + "\n", encoding="utf-8")


def main() -> None:
    CARDS.mkdir(exist_ok=True)
    days = read_data()
    if not STATIC and os.getenv("OFFLINE") != "1":
        days = fetch_days()
        save_data(days)
    write_card("hero.svg", render_hero())
    write_card("cinelock.svg", project_card("CineLock", "Full-stack · TypeScript", "Cinema booking, seat holds, payments", ACCENT, 1))
    write_card("redveg.svg", project_card("RedVeg Commerce", "Frontend · TypeScript", "Storefront and admin prototype", BLUE, 2))
    write_card("ml.svg", project_card("Disease Prediction", "Machine learning · Python", "Model comparison with recall and F1", "#f2bc75", 3))
    write_card("activity.svg", render_activity(days))
    print(f"Rendered profile cards in {CARDS}")


if __name__ == "__main__":
    main()

