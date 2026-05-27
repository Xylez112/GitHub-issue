import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx
from git import Repo

from ..core.config import settings


@dataclass
class IssueData:
    owner: str
    repo: str
    number: int
    title: str
    body: str
    url: str


def parse_url(url: str) -> tuple[str, str, str]:
    """Parse a GitHub URL into (owner, repo, resource_type)."""
    pattern = r"github\.com/([^/]+)/([^/]+)"
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"Invalid GitHub URL: {url}")
    return match.group(1), match.group(2).removesuffix(".git"), match


def parse_issue_url(url: str) -> tuple[str, str, int]:
    """Parse issue URL into (owner, repo, issue_number)."""
    pattern = r"github\.com/([^/]+)/([^/]+)/issues/(\d+)"
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"Invalid GitHub Issue URL: {url}")
    return match.group(1), match.group(2), int(match.group(3))


def parse_repo_url(url: str) -> tuple[str, str]:
    """Parse repo URL into (owner, repo)."""
    pattern = r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$"
    match = re.search(pattern, url.rstrip("/"))
    if not match:
        raise ValueError(f"Invalid GitHub Repo URL: {url}")
    return match.group(1), match.group(2)


async def fetch_issue(issue_url: str) -> IssueData:
    """Fetch issue details from GitHub REST API."""
    owner, repo, issue_number = parse_issue_url(issue_url)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"

    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(api_url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return IssueData(
        owner=owner,
        repo=repo,
        number=issue_number,
        title=data["title"],
        body=data.get("body") or "",
        url=data["html_url"],
    )


def make_synthetic_issue(error_text: str, repo_url: str) -> IssueData:
    """Create an IssueData from raw error text instead of a GitHub Issue URL.

    Uses the first line of the error as the title, and the full text as the body.
    This lets the analyze-error endpoint share the same pipeline as the Issue endpoint.
    """
    owner, repo = parse_repo_url(repo_url)
    lines = error_text.strip().split("\n")
    title = lines[0][:200] if lines else "Error analysis"
    return IssueData(
        owner=owner,
        repo=repo,
        number=0,
        title=title,
        body=error_text,
        url="",
    )


def clone_repo(repo_url: str, target_dir: Path) -> Path:
    """Shallow clone a repo into target_dir. Returns the repo root path."""
    owner, repo_name = parse_repo_url(repo_url)

    clone_url = f"https://github.com/{owner}/{repo_name}.git"
    if settings.github_token:
        clone_url = f"https://{settings.github_token}@github.com/{owner}/{repo_name}.git"

    Repo.clone_from(clone_url, str(target_dir), depth=1)
    return target_dir
