import os
from datetime import date, datetime, time, timezone

import requests

from scripts.config import GITHUB_GRAPHQL_URL


class GitHubClientError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token=None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.member_discovery_mode = "not-run"
        if not self.token:
            raise GitHubClientError(
                "GITHUB_TOKEN is missing. Provide a GitHub token with access "
                "to read organization members and contribution data."
            )

    def query(self, query, variables):
        try:
            response = requests.post(
                GITHUB_GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=60,
            )
        except requests.RequestException as exc:
            raise GitHubClientError(f"GitHub API request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise GitHubClientError(
                "GitHub API authentication failed. Check that GITHUB_TOKEN is "
                "valid and can read organization members and user contributions."
            )

        if not response.ok:
            raise GitHubClientError(
                f"GitHub API returned HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        payload = response.json()
        if payload.get("errors"):
            messages = "; ".join(error.get("message", str(error)) for error in payload["errors"])
            raise GitHubClientError(
                "GitHub GraphQL returned errors. The token may lack organization "
                f"or contribution permissions: {messages}"
            )

        return payload["data"]

    def fetch_organization_members(self, org_name):
        query = """
        query($org: String!, $cursor: String) {
          organization(login: $org) {
            membersWithRole(first: 100, after: $cursor) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                login
              }
            }
          }
        }
        """
        members = []
        cursor = None

        while True:
            data = self.query(query, {"org": org_name, "cursor": cursor})
            organization = data.get("organization")
            if organization is None:
                raise GitHubClientError(
                    f"Organization '{org_name}' was not found or is not visible "
                    "to the configured token."
                )

            page = organization["membersWithRole"]
            members.extend(node["login"] for node in page["nodes"])
            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]
        self.member_discovery_mode = "full-organization"

        return sorted(set(members), key=str.lower)

    def fetch_contributions(self, login, start_date, end_date):
        query = """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              commitContributionsByRepository(maxRepositories: 100) {
                repository {
                  nameWithOwner
                  isPrivate
                  visibility
                  owner {
                    login
                  }
                }
                contributions(first: 100) {
                  pageInfo {
                    hasNextPage
                  }
                  nodes {
                    occurredAt
                    commitCount
                  }
                }
              }
              pullRequestContributionsByRepository(maxRepositories: 100) {
                repository {
                  nameWithOwner
                  isPrivate
                  visibility
                  owner {
                    login
                  }
                }
                contributions(first: 100) {
                  pageInfo {
                    hasNextPage
                  }
                  nodes {
                    occurredAt
                  }
                }
              }
              issueContributionsByRepository(maxRepositories: 100) {
                repository {
                  nameWithOwner
                  isPrivate
                  visibility
                  owner {
                    login
                  }
                }
                contributions(first: 100) {
                  pageInfo {
                    hasNextPage
                  }
                  nodes {
                    occurredAt
                  }
                }
              }
              pullRequestReviewContributionsByRepository(maxRepositories: 100) {
                repository {
                  nameWithOwner
                  isPrivate
                  visibility
                  owner {
                    login
                  }
                }
                contributions(first: 100) {
                  pageInfo {
                    hasNextPage
                  }
                  nodes {
                    occurredAt
                  }
                }
              }
            }
          }
        }
        """
        data = self.query(
            query,
            {
                "login": login,
                "from": _to_datetime(start_date),
                "to": _to_datetime(end_date, end_of_day=True),
            },
        )
        user = data.get("user")
        if user is None:
            return []

        collection = user["contributionsCollection"]
        rows = []
        rows.extend(
            _extract_contributions(
                collection["commitContributionsByRepository"],
                "commit",
                is_commit_group=True,
            )
        )
        rows.extend(
            _extract_contributions(
                collection["pullRequestContributionsByRepository"],
                "pull-request",
            )
        )
        rows.extend(
            _extract_contributions(
                collection["issueContributionsByRepository"],
                "issue",
            )
        )
        rows.extend(
            _extract_contributions(
                collection["pullRequestReviewContributionsByRepository"],
                "pull-request-review",
            )
        )
        return rows


def _to_datetime(value, end_of_day=False):
    clock = time.max if end_of_day else time.min
    return datetime.combine(value, clock, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_contributions(repo_groups, contribution_type, is_commit_group=False):
    rows = []
    for group in repo_groups:
        repository = group["repository"]
        owner = repository["owner"]["login"]
        name_with_owner = repository["nameWithOwner"]

        # GitHub returns contribution nodes grouped by repository, but nested
        # pagination is intentionally not persisted. The workflow only keeps
        # anonymized aggregate counts in memory for chart generation.
        if group["contributions"]["pageInfo"]["hasNextPage"]:
            raise GitHubClientError(
                f"Contribution pagination limit reached for {name_with_owner}. "
                "Narrow the date range or extend the client pagination before "
                "publishing updated charts."
            )

        for node in group["contributions"]["nodes"]:
            count = node.get("commitCount", 1) if is_commit_group else 1
            rows.append(
                {
                    "date": date.fromisoformat(node["occurredAt"][:10]),
                    "repository": name_with_owner,
                    "owner": owner,
                    "count": count,
                    "type": contribution_type,
                    "is_private": repository["isPrivate"],
                    "visibility": repository["visibility"],
                }
            )
    return rows
