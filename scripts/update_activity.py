#!/usr/bin/env python3
"""Rebuild the activity graphic (dark and light) from public GitHub contribution data.

Run every day by .github/workflows/activity.yml. Needs only the Python standard library.

    GH_TOKEN=... python scripts/update_activity.py     # fetch and rebuild
    python scripts/update_activity.py --empty           # write the empty placeholder
"""
import calendar
import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape

USER = os.environ.get("GH_USER", "AlsoAryan")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

W = 900
SANS = 'Inter, "SF Pro Text", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif'
MONO = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace'

THEMES = {
    "dark": dict(text="#E6ECF5", muted="#8D9BB2", line="#243350", cell0="#162238", accent="#F4C542"),
    "light": dict(text="#0E1726", muted="#56657C", line="#D3DAE6", cell0="#E7ECF3", accent="#C98B00"),
}
OPACITY = {1: 0.30, 2: 0.55, 3: 0.80, 4: 1.0}

# "Activity" set in Inter Display, drawn as outlines so it looks the same everywhere.
TITLE_D = "M20 0H208L358 418H980L1126 0H1318L774 1490H570ZM415 578 530 898C568 1003 608 1123 672 1321C736 1123 776 1003 813 898L925 578Z M1836.4 -24C2074.4 -24 2252.4 136 2281.4 344H2106.4C2073.4 215 1994.4 130 1836.4 130C1636.4 130 1518.4 286 1518.4 526C1518.4 768 1637.4 926 1836.4 926C1992.4 926 2084.4 836 2109.4 712H2281.4C2252.4 925 2076.4 1080 1836.4 1080C1543.4 1080 1346.4 850 1346.4 526C1346.4 204 1543.4 -24 1836.4 -24Z M2908.8 1056H2694.8V1344H2524.8V1056H2336.8V910H2524.8V238C2524.8 79 2613.8 0 2794.8 0H2908.8V146H2810.8C2723.8 146 2694.8 174 2694.8 256V910H2908.8Z M3061.1 0H3231.1V1056H3061.1ZM3146.1 1262C3210.1 1262 3262.1 1314 3262.1 1378C3262.1 1442 3210.1 1494 3146.1 1494C3082.1 1494 3030.1 1442 3030.1 1378C3030.1 1314 3082.1 1262 3146.1 1262Z M3771.5 0H3943.5L4351.5 1056H4170.5L3945.5 448C3915.5 367 3888.5 286 3860.5 205C3833.5 286 3805.5 367 3775.5 448L3547.5 1056H3363.5Z M4483.9 0H4653.9V1056H4483.9ZM4568.9 1262C4632.9 1262 4684.9 1314 4684.9 1378C4684.9 1442 4632.9 1494 4568.9 1494C4504.9 1494 4452.9 1442 4452.9 1378C4452.9 1314 4504.9 1262 4568.9 1262Z M5363.3 1056H5149.3V1344H4979.3V1056H4791.3V910H4979.3V238C4979.3 79 5068.3 0 5249.3 0H5363.3V146H5265.3C5178.3 146 5149.3 174 5149.3 256V910H5363.3Z M5583.6 -418H5687.6C5820.6 -418 5925.6 -338 5980.6 -196L6467.6 1056H6286.6L6062.6 448C6033.6 369 6004.6 290 5976.6 211C5949.6 290 5921.6 369 5891.6 448L5663.6 1056H5479.6L5888.6 9L5830.6 -141C5796.6 -229 5752.6 -268 5687.6 -268H5583.6Z"
TITLE_SCALE = 0.01270
TITLE_W = 82.49

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
QUERY = (
    "query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{"
    "totalContributions weeks{contributionDays{date contributionLevel}}}}}}"
)


def fetch(token):
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "profile-activity-graphic",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    user = (data.get("data") or {}).get("user")
    if not user:
        raise RuntimeError("GitHub returned no data: " + json.dumps(data.get("errors", data))[:400])
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["date"], LEVELS[d["contributionLevel"]]) for d in w["contributionDays"]] for w in cal["weeks"]]
    return weeks, cal["totalContributions"]


def empty_weeks(today=None):
    """Fifty-three blank weeks ending today, used before the first sync."""
    today = today or dt.date.today()
    sunday = today - dt.timedelta(days=(today.weekday() + 1) % 7)
    start = sunday - dt.timedelta(weeks=52)
    weeks = []
    for w in range(53):
        days = []
        for r in range(7):
            d = start + dt.timedelta(weeks=w, days=r)
            if d <= today:
                days.append((d.isoformat(), 0))
        weeks.append(days)
    return weeks


def render(theme, weeks, total):
    c = THEMES[theme]
    n = len(weeks)
    pitch = (W - 2) / n
    cell = pitch - 4
    dy = 0 if total is not None else -36  # tighter layout while there is no headline figure
    top = 180 + dy
    parts = []

    # section heading: node, title, hairline
    parts.append(f'<circle cx="5" cy="30" r="4.5" fill="{c["accent"]}"/>')
    parts.append(
        f'<path transform="translate(24 39) scale({TITLE_SCALE} {-TITLE_SCALE})" d="{TITLE_D}" fill="{c["text"]}"/>'
    )
    parts.append(f'<path d="M{24 + TITLE_W + 22:.1f} 30.5H{W}" stroke="{c["line"]}" stroke-width="1"/>')

    # headline figure (only once real data has been fetched)
    if total is not None:
        parts.append(
            f'<text x="2" y="112" font-family="{escape(SANS)}" font-size="54" font-weight="300" '
            f'letter-spacing="-1.5" fill="{c["text"]}">{total:,}</text>'
        )
        caption = "contributions in the last year"
    else:
        caption = "Contribution activity, updated daily from GitHub"
    parts.append(
        f'<text x="1" y="{140 + dy}" font-family="{escape(SANS)}" font-size="15" fill="{c["muted"]}">'
        f"{caption}</text>"
    )

    # legend
    lx = W - 30 - 8 - 71
    parts.append(
        f'<text x="{lx - 8}" y="{140 + dy}" text-anchor="end" font-family="{escape(SANS)}" font-size="13" '
        f'fill="{c["muted"]}">Less</text>'
    )
    for i in range(5):
        fill = c["cell0"] if i == 0 else c["accent"]
        op = "" if i == 0 else f' fill-opacity="{OPACITY[i]}"'
        parts.append(f'<rect x="{lx + i * 15}" y="{130 + dy}" width="11" height="11" rx="3" fill="{fill}"{op}/>')
    parts.append(
        f'<text x="{W}" y="{140 + dy}" text-anchor="end" font-family="{escape(SANS)}" font-size="13" '
        f'fill="{c["muted"]}">More</text>'
    )

    # month labels
    last_month, last_col = None, -10
    for i, days in enumerate(weeks):
        if not days:
            continue
        d0 = dt.date.fromisoformat(days[0][0])
        if d0.month != last_month:
            if i - last_col >= 3 and 1 + i * pitch < W - 40:
                parts.append(
                    f'<text x="{1 + i * pitch:.1f}" y="{168 + dy}" font-family="{escape(MONO)}" font-size="12" '
                    f'fill="{c["muted"]}">{calendar.month_abbr[d0.month]}</text>'
                )
                last_col = i
            last_month = d0.month

    # the grid, Sunday at the top
    for i, days in enumerate(weeks):
        for date, level in days:
            row = (dt.date.fromisoformat(date).weekday() + 1) % 7
            x, y = 1 + i * pitch, top + row * pitch
            if level == 0:
                parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="3" fill="{c["cell0"]}"/>')
            else:
                parts.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="3" '
                    f'fill="{c["accent"]}" fill-opacity="{OPACITY[level]}"/>'
                )

    h = int(top + 7 * pitch + 14)
    label = "Contribution activity over the last year" + (f": {total:,} contributions" if total is not None else "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
        f'role="img" aria-labelledby="t"><title id="t">{escape(label)}</title>' + "".join(parts) + "</svg>\n"
    )


def write(weeks, total):
    os.makedirs(OUT, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(OUT, f"activity-{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render(theme, weeks, total))


def main():
    if "--empty" in sys.argv:
        write(empty_weeks(), None)
        return 0
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Set GH_TOKEN to a GitHub token first.", file=sys.stderr)
        return 1
    try:
        weeks, total = fetch(token)
    except Exception as err:  # keep the existing graphic and show the reason in the log
        print("Could not fetch contributions:", err, file=sys.stderr)
        return 1
    write(weeks, total)
    print(f"Wrote activity graphics: {total} contributions in {len(weeks)} weeks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
