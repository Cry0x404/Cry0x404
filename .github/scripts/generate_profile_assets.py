import json
import os
import urllib.request
from datetime import datetime, timezone
from html import escape

TOKEN = os.environ.get("GITHUB_TOKEN", "")
USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "Cry0x404")
OUT_DIR = "dist"
os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Cry0x404-profile-readme",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"
    HEADERS["X-GitHub-Api-Version"] = "2022-11-28"


def request_json(url, method="GET", payload=None, headers=None):
    body = None
    merged = dict(HEADERS)
    if headers:
        merged.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        merged["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=merged, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_profile():
    return request_json(f"https://api.github.com/users/{USERNAME}")


def fetch_repos():
    repos = []
    page = 1
    while True:
        batch = request_json(
            f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner&sort=updated"
        )
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def fetch_contributions():
    if not TOKEN:
        return None
    query = """
    query($login:String!) {
      user(login:$login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                weekday
              }
            }
          }
        }
      }
    }
    """
    try:
        data = request_json(
            "https://api.github.com/graphql",
            method="POST",
            payload={"query": query, "variables": {"login": USERNAME}},
        )
        return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    except Exception:
        return None


def svg_header(width, height):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">'
        '<style>'
        'text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}'
        '.title{font-size:22px;font-weight:700;fill:#f0f6fc}'
        '.label{font-size:13px;font-weight:600;fill:#8b949e}'
        '.value{font-size:26px;font-weight:750;fill:#4ade80}'
        '.small{font-size:12px;fill:#8b949e}'
        '</style>'
    )


def generate_stats(profile, repos, calendar):
    width, height = 860, 250
    public_repos = int(profile.get("public_repos", len(repos)) or 0)
    followers = int(profile.get("followers", 0) or 0)
    stars = sum(int(r.get("stargazers_count", 0) or 0) for r in repos)
    forks = sum(int(r.get("forks_count", 0) or 0) for r in repos)
    contributions = int(calendar.get("totalContributions", 0)) if calendar else 0
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    items = [
        ("PUBLIC REPOSITORIES", str(public_repos)),
        ("FOLLOWERS", str(followers)),
        ("STARS RECEIVED", str(stars)),
        ("CONTRIBUTIONS / YEAR", str(contributions)),
    ]

    parts = [svg_header(width, height)]
    parts.append('<rect x="1" y="1" width="858" height="248" rx="16" fill="#0d1117" stroke="#30363d"/>')
    parts.append('<rect x="1" y="1" width="858" height="5" rx="3" fill="#166534"/>')
    parts.append(f'<text x="28" y="44" class="title">GitHub Analytics — {escape(USERNAME)}</text>')
    parts.append('<text x="28" y="67" class="small">Generated from GitHub API data by this repository</text>')

    x_positions = [28, 235, 442, 649]
    for (label, value), x in zip(items, x_positions):
        parts.append(f'<rect x="{x}" y="92" width="183" height="96" rx="12" fill="#161b22" stroke="#30363d"/>')
        parts.append(f'<text x="{x+16}" y="122" class="label">{escape(label)}</text>')
        parts.append(f'<text x="{x+16}" y="161" class="value">{escape(value)}</text>')

    parts.append(f'<text x="28" y="221" class="small">Forks across public repositories: {forks}  •  Last generated: {updated} UTC</text>')
    parts.append('</svg>')
    with open(os.path.join(OUT_DIR, "profile-stats.svg"), "w", encoding="utf-8") as f:
        f.write("".join(parts))


def intensity(count, max_count):
    if count <= 0:
        return "#161b22"
    if max_count <= 1:
        return "#15803d"
    ratio = count / max_count
    if ratio <= 0.25:
        return "#052e16"
    if ratio <= 0.5:
        return "#14532d"
    if ratio <= 0.75:
        return "#166534"
    return "#4ade80"


def generate_activity(calendar):
    width, height = 860, 245
    parts = [svg_header(width, height)]
    parts.append('<rect x="1" y="1" width="858" height="243" rx="16" fill="#0d1117" stroke="#30363d"/>')
    parts.append('<rect x="1" y="1" width="858" height="5" rx="3" fill="#15803d"/>')
    parts.append('<text x="28" y="42" class="title">Contribution Activity</text>')

    if not calendar or not calendar.get("weeks"):
        parts.append('<text x="28" y="78" class="small">Contribution data was unavailable for this run. The card will refresh automatically.</text>')
        parts.append('</svg>')
    else:
        total = int(calendar.get("totalContributions", 0) or 0)
        weeks = calendar["weeks"][-53:]
        counts = [int(day.get("contributionCount", 0) or 0) for w in weeks for day in w.get("contributionDays", [])]
        max_count = max(counts) if counts else 0
        parts.append(f'<text x="28" y="67" class="small">{total} contributions in the last year • live GitHub contribution data</text>')

        start_x, start_y, cell, gap = 28, 91, 11, 3
        for wi, week in enumerate(weeks):
            days = week.get("contributionDays", [])
            for di, day in enumerate(days):
                count = int(day.get("contributionCount", 0) or 0)
                weekday = int(day.get("weekday", di) or 0)
                x = start_x + wi * (cell + gap)
                y = start_y + weekday * (cell + gap)
                color = intensity(count, max_count)
                date = escape(str(day.get("date", "")))
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color}">'
                    f'<title>{date}: {count} contributions</title></rect>'
                )

        legend_x = 690
        parts.append(f'<text x="{legend_x-42}" y="218" class="small">Less</text>')
        legend_colors = ["#161b22", "#052e16", "#14532d", "#166534", "#4ade80"]
        for i, color in enumerate(legend_colors):
            parts.append(f'<rect x="{legend_x + i*17}" y="207" width="11" height="11" rx="2" fill="{color}"/>')
        parts.append(f'<text x="{legend_x+92}" y="218" class="small">More</text>')
        parts.append('</svg>')

    with open(os.path.join(OUT_DIR, "contribution-activity.svg"), "w", encoding="utf-8") as f:
        f.write("".join(parts))


def main():
    try:
        profile = fetch_profile()
    except Exception:
        profile = {"public_repos": 0, "followers": 0}
    try:
        repos = fetch_repos()
    except Exception:
        repos = []
    calendar = fetch_contributions()
    generate_stats(profile, repos, calendar)
    generate_activity(calendar)


if __name__ == "__main__":
    main()
