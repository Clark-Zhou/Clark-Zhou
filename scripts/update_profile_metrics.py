#!/usr/bin/env python3
"""Update the generated GitHub profile metrics block in README.md."""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional


README = Path("README.md")
START = "<!-- PROFILE-METRICS:START -->"
END = "<!-- PROFILE-METRICS:END -->"


def api_get(url: str, token: Optional[str]) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Clark-Zhou-profile-metrics",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_repos(username: str, token: Optional[str]) -> List[Dict[str, object]]:
    repos: List[Dict[str, object]] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/users/{username}/repos"
            f"?type=owner&sort=updated&per_page=100&page={page}"
        )
        data = api_get(url, token)
        if not isinstance(data, list) or not data:
            break
        repos.extend(item for item in data if isinstance(item, dict))
        if len(data) < 100:
            break
        page += 1
    return repos


def fmt_date(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "n/a"
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value[:10]
    return parsed.date().isoformat()


def bar(percent: int) -> str:
    filled = max(0, min(10, round(percent / 10)))
    return "#" * filled + "-" * (10 - filled)


def generate_block(username: str, repos: List[Dict[str, object]]) -> str:
    own_repos = [repo for repo in repos if not repo.get("fork")]
    active_repos = [repo for repo in own_repos if not repo.get("archived")]
    stars = sum(int(repo.get("stargazers_count") or 0) for repo in own_repos)
    forks = sum(int(repo.get("forks_count") or 0) for repo in own_repos)
    language_counts = Counter(
        str(repo.get("language"))
        for repo in own_repos
        if repo.get("language")
    )
    top_language = language_counts.most_common(1)[0][0] if language_counts else "n/a"
    language_total = sum(language_counts.values()) or 1
    top_languages = language_counts.most_common(4)
    latest_repo = max(
        active_repos or own_repos or repos,
        key=lambda repo: str(repo.get("pushed_at") or repo.get("updated_at") or ""),
        default={},
    )
    latest_name = str(latest_repo.get("name") or "n/a")
    latest_push = fmt_date(latest_repo.get("pushed_at") or latest_repo.get("updated_at"))
    sync_time = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if top_languages:
        language_lines = "\n".join(
            f"{language:<14} [{bar(round(count / language_total * 100))}] {round(count / language_total * 100):>3}%"
            for language, count in top_languages
        )
    else:
        language_lines = "No public repository language data yet."

    public_count = len(own_repos)
    active_count = len(active_repos)

    return f"""{START}
<table>
  <tr>
    <td align="center" width="25%">
      <strong>{public_count}</strong><br>
      <sub>public repositories</sub>
    </td>
    <td align="center" width="25%">
      <strong>{stars}</strong><br>
      <sub>stars earned</sub>
    </td>
    <td align="center" width="25%">
      <strong>{html.escape(top_language)}</strong><br>
      <sub>primary language</sub>
    </td>
    <td align="center" width="25%">
      <strong>{html.escape(latest_name)}</strong><br>
      <sub>latest pushed repo</sub>
    </td>
  </tr>
</table>

### Dashboard

| KPI | Live value | Signal |
| --- | --- | --- |
| Public repositories | `{public_count}` | Synced from GitHub API |
| Active repositories | `{active_count}` | Non-archived, non-fork repos |
| Total stars | `{stars}` | Across public owner repos |
| Total forks | `{forks}` | Across public owner repos |
| Primary language | `{html.escape(top_language)}` | Most frequent repo language |
| Latest push | `{html.escape(latest_name)} / {latest_push}` | Most recently pushed repo |

### Focus Metrics

<table>
  <tr>
    <td width="50%">
      <pre>
{html.escape(language_lines)}</pre>
    </td>
    <td width="50%">
      <pre>
live github sync

user   {html.escape(username)}
repos  {public_count}
stars  {stars}
sync   {sync_time}</pre>
    </td>
  </tr>
</table>

### Current Loop

```txt
idea -> prototype -> test -> learn -> ship
```
{END}"""


def replace_block(readme: str, generated: str) -> str:
    pattern = re.compile(
        rf"{re.escape(START)}.*?{re.escape(END)}",
        flags=re.DOTALL,
    )
    if pattern.search(readme):
        return pattern.sub(generated, readme)
    marker = "---\n\n"
    if marker in readme:
        return readme.replace(marker, f"{generated}\n\n{marker}", 1)
    return f"{readme.rstrip()}\n\n{generated}\n"


def main() -> int:
    username = os.environ.get("GITHUB_USERNAME")
    if not username and os.environ.get("GITHUB_REPOSITORY"):
        username = os.environ["GITHUB_REPOSITORY"].split("/", 1)[0]
    username = username or "Clark-Zhou"
    token = os.environ.get("GITHUB_TOKEN")

    try:
        repos = fetch_repos(username, token)
    except urllib.error.URLError as exc:
        print(f"Failed to fetch GitHub data: {exc}", file=sys.stderr)
        return 1

    readme = README.read_text(encoding="utf-8")
    generated = generate_block(username, repos)
    README.write_text(replace_block(readme, generated), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
