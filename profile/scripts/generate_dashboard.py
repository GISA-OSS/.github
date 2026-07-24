import os
from pathlib import Path

from scripts.aggregation import collect_contributions
from scripts.config import (
    ASSETS_DIR,
    DIAGNOSTIC_LOGIN,
    DIAGNOSTICS_REQUESTED,
    INTERNAL_ORGS,
    ORG_NAMES,
    START_DATE,
    TODAY,
)
from scripts.github_client import GitHubClient
from scripts.visualizations import (
    ensure_assets,
    save_total_trend,
    save_total_trend_histogram,
)


def main():
    ensure_assets(ASSETS_DIR)

    if not ORG_NAMES:
        raise RuntimeError(
            "No organizations configured. Set ORG_NAMES to a comma-separated list."
        )

    if DIAGNOSTICS_REQUESTED and not DIAGNOSTIC_LOGIN:
        raise RuntimeError(
            "Targeted diagnostics were requested, but the "
            "DASHBOARD_DIAGNOSTIC_LOGIN secret is not configured."
        )
    if DIAGNOSTIC_LOGIN:
        print(
            "Targeted contribution diagnostics enabled. The configured login "
            "will not be printed."
        )

    client = GitHubClient()
    members, discovery_results, duplicate_memberships = _discover_members(
        client,
        ORG_NAMES,
    )
    if not members:
        raise RuntimeError(
            "No members discovered for the configured organizations "
            f"({', '.join(ORG_NAMES)}). Check token permissions."
        )

    print(f"Unique organization members to process: {len(members)}")
    print(f"Duplicate cross-organization memberships removed: {duplicate_memberships}")
    print(f"Contribution coverage: {START_DATE.isoformat()} through {TODAY.isoformat()}")

    series, _ = collect_contributions(
        client,
        members,
        START_DATE,
        TODAY,
        INTERNAL_ORGS,
        diagnostic_login=DIAGNOSTIC_LOGIN,
    )

    data_through = series[-1]["date"] if series else TODAY
    generated_assets = [
        "total_trend_chart.svg",
    ]

    save_total_trend(series, f"{ASSETS_DIR}/total_trend_chart.svg")

    # ========================================================================
    # MONTHLY HISTOGRAM GENERATION IS INTENTIONALLY DISABLED
    #
    # To re-enable it, uncomment the call below and add
    # "total_trend_histogram.svg" back to generated_assets above.
    # ========================================================================
    # save_total_trend_histogram(
    #     series,
    #     f"{ASSETS_DIR}/total_trend_histogram.svg",
    # )

    print(f"Generated assets: {', '.join(generated_assets)}")
    _write_actions_summary(
        discovery_results,
        len(members),
        duplicate_memberships,
        data_through,
        generated_assets,
    )


def _discover_members(client, organization_names):
    unique_members = {}
    discovery_results = []
    discovered_memberships = 0

    for organization_name in organization_names:
        organization_members = client.fetch_organization_members(organization_name)
        discovery_mode = client.member_discovery_mode
        member_count = len(organization_members)
        discovered_memberships += member_count
        discovery_results.append(
            {
                "organization": organization_name,
                "mode": discovery_mode,
                "member_count": member_count,
            }
        )
        print(
            f"Organization member discovery: organization={organization_name}, "
            f"mode={discovery_mode}, members={member_count}"
        )
        for login in organization_members:
            unique_members.setdefault(login.casefold(), login)

    members = sorted(unique_members.values(), key=str.casefold)
    duplicate_memberships = discovered_memberships - len(members)
    return members, discovery_results, duplicate_memberships


def _write_actions_summary(
    discovery_results,
    member_count,
    duplicate_memberships,
    data_through,
    assets,
):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = [
        "## Contribution dashboard generation",
        "",
        "### Organization discovery",
    ]
    lines.extend(
        f"- `{result['organization']}`: `{result['mode']}`, "
        f"**{result['member_count']}** members"
        for result in discovery_results
    )
    lines.extend(
        [
            "",
            f"- Unique members included: **{member_count}**",
            f"- Duplicate memberships removed: **{duplicate_memberships}**",
            f"- Contribution period: `{START_DATE.isoformat()}` through `{data_through.isoformat()}`",
            f"- Assets generated: {', '.join(f'`{asset}`' for asset in assets)}",
        ]
    )
    with Path(summary_path).open("a", encoding="utf-8") as summary:
        summary.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
