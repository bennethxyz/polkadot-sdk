#!/usr/bin/env python3

import argparse
import json
import re
import sys
import time
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


GITHUB_SEARCH_URL = "https://api.github.com/search/issues"
DEFAULT_QUERY = 'label:bounty label:"good first issue" state:open'
CURRENCY_PATTERN = re.compile(r"(\$|USD|USDT|USDC|EUR|€|£)(\s?\d+[\d,\.]*)", re.IGNORECASE)


def build_request(url: str, token: Optional[str]) -> Request:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return Request(url, headers=headers)


def fetch_issues(query: str, pages: int, per_page: int, token: Optional[str]) -> List[Dict]:
    issues: List[Dict] = []
    for page in range(1, pages + 1):
        url = f"{GITHUB_SEARCH_URL}?q={quote(query)}&per_page={per_page}&page={page}"
        with urlopen(build_request(url, token)) as response:
            data = json.load(response)
        items = data.get("items", [])
        issues.extend(items)
        if len(items) < per_page:
            break
        if page < pages:
            time.sleep(1)
    return issues


def extract_repo_name(api_url: str) -> str:
    marker = "/repos/"
    return api_url.split(marker, 1)[1] if marker in api_url else api_url


def infer_reward(labels: List[str], body: str) -> Tuple[Optional[str], Optional[float]]:
    for label in labels:
        if label.lower().startswith("reward-"):
            digits = "".join(ch for ch in label if ch.isdigit() or ch == ".")
            if digits:
                try:
                    value = float(digits.replace(",", ""))
                except ValueError:
                    continue
                return f"${digits}", value

    match = CURRENCY_PATTERN.search(body)
    if match:
        symbol, amount = match.groups()
        try:
            numeric = float(amount.strip().replace(",", ""))
        except ValueError:
            return None, None
        return f"{symbol}{amount.strip()}", numeric

    return None, None


def collect_paid_issues(raw_issues: List[Dict], limit: int) -> List[Dict]:
    paid: List[Dict] = []
    for issue in raw_issues:
        if issue.get("assignee"):
            continue
        labels = [label.get("name", "") for label in issue.get("labels", [])]
        reward_text, reward_value = infer_reward(labels, issue.get("body") or "")
        if not reward_text:
            continue
        paid.append(
            {
                "title": issue.get("title", ""),
                "url": issue.get("html_url", ""),
                "repo": extract_repo_name(issue.get("repository_url", "")),
                "reward": reward_text,
                "reward_value": reward_value or 0.0,
                "labels": labels,
            }
        )

    paid.sort(key=lambda item: item["reward_value"], reverse=True)
    return paid[:limit] if limit else paid


def output_issues(issues: List[Dict], as_json: bool) -> None:
    if as_json:
        payload = [
            {
                "title": issue["title"],
                "url": issue["url"],
                "repo": issue["repo"],
                "reward": issue["reward"],
                "labels": issue["labels"],
            }
            for issue in issues
        ]
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    for issue in issues:
        print(f"{issue['reward']:>10} | {issue['repo']} | {issue['title']} | {issue['url']}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List paid good first issues from GitHub")
    parser.add_argument("--token", help="GitHub token for higher rate limits")
    parser.add_argument("--pages", type=int, default=1, help="Number of pages to fetch (30 results per page)")
    parser.add_argument("--per-page", type=int, default=100, help="Results per page (max 100)")
    parser.add_argument("--limit", type=int, default=10, help="Maximum issues to output (0 for all)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of table output")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Override the GitHub search query")
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    try:
        raw_issues = fetch_issues(args.query, args.pages, args.per_page, args.token)
    except HTTPError as error:
        sys.stderr.write(f"GitHub request failed: {error}\n")
        return 1

    issues = collect_paid_issues(raw_issues, args.limit)
    if not issues:
        sys.stderr.write("No paid good first issues found with the current filters.\n")
        return 1

    output_issues(issues, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
