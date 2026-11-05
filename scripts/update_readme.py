#!/usr/bin/env python3
"""Refresh the dynamic sections of README.md from the public GitHub API.

Standard library only. Sections live between markers:
    <!--START_SECTION:name--> ... <!--END_SECTION:name-->
Set GITHUB_TOKEN for higher rate limits (optional).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

USER = os.environ.get("GH_PROFILE_USER", "0x0806")
README = Path(__file__).resolve().parent.parent / "README.md"
API = "https://api.github.com"
FEATURED_COUNT = 6
ACTIVITY_COUNT = 6


def api_get(path: str, retries: int = 3):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"{USER}-profile-readme"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{API}{path}", headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GitHub API request failed for {path}: {last}")


def esc(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def render_featured(repos: list[dict]) -> str:
    own = [r for r in repos if not r["fork"] and not r["archived"] and r["name"] != USER]
    own.sort(key=lambda r: (r["stargazers_count"], r["pushed_at"]), reverse=True)
    rows = ["| Project | Description | Language | ⭐ |", "|:--|:--|:--|--:|"]
    for r in own[:FEATURED_COUNT]:
        desc = esc(r.get("description")) or "—"
        if len(desc) > 110:
            desc = desc[:107].rstrip() + "..."
        lang = r.get("language") or "—"
        rows.append(f"| [**{r['name']}**]({r['html_url']}) | {desc} | {lang} | {r['stargazers_count']} |")
    return "\n".join(rows)


def render_stats(user: dict, repos: list[dict]) -> str:
    own = [r for r in repos if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in own)
    forks = sum(r["forks_count"] for r in own)
    langs = Counter(r["language"] for r in own if r.get("language"))
    def badge(label: str, value, color: str, style: str = "for-the-badge") -> str:
        q = lambda s: urllib.parse.quote(str(s).replace("-", "--"), safe="")  # noqa: E731
        return (f'<img src="https://img.shields.io/badge/{q(label)}-{q(value)}-{color}?style={style}" '
                f'alt="{label}: {value}" />')

    top = " ".join(badge(n, c, "2E86C1", "flat-square") for n, c in langs.most_common(6))
    return (
        f"<div align=\"center\">\n\n"
        f"{badge('Public Repos', user['public_repos'], '2E86C1')}\n"
        f"{badge('Stars Earned', stars, 'F1C40F')}\n"
        f"{badge('Forks', forks, '27AE60')}\n"
        f"{badge('Followers', user['followers'], '8E44AD')}\n\n"
        f"<sub>Languages by original repo count</sub><br/>\n{top}\n\n</div>"
    )


def describe_event(ev: dict) -> str | None:
    repo = ev["repo"]["name"]
    link = f"[{repo}](https://github.com/{repo})"
    kind, p = ev["type"], ev.get("payload", {})
    if kind == "PushEvent":
        n = p.get("size") or len(p.get("commits", [])) or 1
        return f"⬆️ Pushed {n} commit{'s' if n != 1 else ''} to {link}"
    if kind == "CreateEvent" and p.get("ref_type") == "repository":
        return f"🆕 Created {link}"
    if kind == "PullRequestEvent":
        return f"🔀 {p.get('action', 'updated').capitalize()} a pull request in {link}"
    if kind == "IssuesEvent":
        return f"🐛 {p.get('action', 'updated').capitalize()} an issue in {link}"
    if kind == "WatchEvent":
        return f"⭐ Starred {link}"
    if kind == "ForkEvent":
        return f"🍴 Forked {link}"
    return None


def render_activity(events: list[dict]) -> str:
    lines = []
    for ev in events:
        text = describe_event(ev)
        if text:
            lines.append(f"- {text} · <sub>{ev['created_at'][:10]}</sub>")
        if len(lines) >= ACTIVITY_COUNT:
            break
    return "\n".join(lines) or "_No recent public activity._"


def render_updated() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"<sub>🕒 Auto-updated: {now}</sub>"


def replace_section(text: str, name: str, body: str) -> str:
    pattern = re.compile(
        rf"(<!--START_SECTION:{re.escape(name)}-->)(.*?)(<!--END_SECTION:{re.escape(name)}-->)", re.S
    )
    if not pattern.search(text):
        raise KeyError(f"marker for section '{name}' not found in README")
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def main() -> int:
    user = api_get(f"/users/{USER}")
    repos = api_get(f"/users/{USER}/repos?per_page=100&type=owner&sort=pushed")
    events = api_get(f"/users/{USER}/events/public?per_page=50")
    text = README.read_text(encoding="utf-8")
    for name, body in {
        "featured": render_featured(repos),
        "stats": render_stats(user, repos),
        "activity": render_activity(events),
        "updated": render_updated(),
    }.items():
        text = replace_section(text, name, body)
    README.write_text(text, encoding="utf-8")
    print("README updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
