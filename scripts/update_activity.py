"""Refresh the "Recent activity" section of README.md from public GitHub events.

Standard library only. Run by .github/workflows/update-activity.yml, or locally:
    python scripts/update_activity.py
"""

import json
import os
import re
import urllib.request
from pathlib import Path

USERNAME = "manjain15"
PROFILE_REPO = f"{USERNAME}/{USERNAME}"  # skip our own bot commits
README = Path(__file__).resolve().parent.parent / "README.md"
MAX_LINES = 6

START = "<!--START_SECTION:activity-->"
END = "<!--END_SECTION:activity-->"


def fetch_events() -> list[dict]:
    req = urllib.request.Request(
        f"https://api.github.com/users/{USERNAME}/events/public?per_page=100",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-readme"},
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def describe(event: dict) -> tuple[str, str] | None:
    """Return (dedupe_key, markdown_line) for an event, or None to skip it."""
    repo = event["repo"]["name"]
    if repo == PROFILE_REPO:
        return None
    link = f"[{repo}](https://github.com/{repo})"
    payload = event.get("payload", {})
    kind = event["type"]

    if kind == "PushEvent":
        n = payload.get("distinct_size") or payload.get("size") or 1
        word = "commit" if n == 1 else "commits"
        return f"push:{repo}", f"🔨 Pushed {n} {word} to {link}"
    if kind == "PullRequestEvent":
        pr = payload.get("pull_request", {})
        action = "Merged" if pr.get("merged") else payload.get("action", "updated").capitalize()
        return f"pr:{pr.get('html_url')}", f"🔀 {action} PR [#{pr.get('number')}]({pr.get('html_url')}) in {link}"
    if kind == "IssuesEvent" and payload.get("action") == "opened":
        issue = payload["issue"]
        return f"issue:{issue['html_url']}", f"❗ Opened issue [#{issue['number']}]({issue['html_url']}) in {link}"
    if kind == "CreateEvent" and payload.get("ref_type") == "repository":
        return f"create:{repo}", f"🆕 Created {link}"
    return None


def build_lines(events: list[dict]) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    for event in events:
        described = describe(event)
        if not described:
            continue
        key, line = described
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {line}")
        if len(lines) == MAX_LINES:
            break
    return lines


def main() -> None:
    lines = build_lines(fetch_events())
    if not lines:
        print("No recent public activity found; leaving README unchanged.")
        return

    text = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Markers {START} / {END} not found in README.md")

    block = f"{START}\n" + "\n".join(lines) + f"\n{END}"
    new_text = pattern.sub(lambda _: block, text)
    if new_text == text:
        print("README already up to date.")
        return
    README.write_text(new_text, encoding="utf-8")
    print(f"Updated README with {len(lines)} activity lines.")


if __name__ == "__main__":
    main()
