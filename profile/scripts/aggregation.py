from collections import Counter, defaultdict
from datetime import date, timedelta


def classify_owner(owner, internal_orgs):
    return "internal" if owner.lower() in internal_orgs else "external"


def collect_contributions(
    client,
    members,
    start_date,
    end_date,
    internal_orgs,
    diagnostic_login="",
):
    daily = defaultdict(lambda: {"total": 0, "internal": 0, "external": 0})
    external_repositories = Counter()
    # GitHub contribution connections are capped, so month-sized windows keep
    # long-running dashboards usable without storing member-level data.
    windows = month_windows(start_date, end_date)
    normalized_diagnostic_login = diagnostic_login.casefold()
    diagnostic_member_found = False
    diagnostic_rows = []

    for index, login in enumerate(members, start=1):
        print(f"Fetching contributions for organization member {index} of {len(members)}")
        is_diagnostic_member = (
            bool(normalized_diagnostic_login)
            and login.casefold() == normalized_diagnostic_login
        )
        if is_diagnostic_member:
            diagnostic_member_found = True

        for window_start, window_end in windows:
            rows = client.fetch_contributions(login, window_start, window_end)
            if is_diagnostic_member:
                diagnostic_rows.extend(rows)

            for row in rows:
                if row["is_private"] or row["visibility"] != "PUBLIC":
                    continue
                kind = classify_owner(row["owner"], internal_orgs)
                count = int(row["count"])
                daily[row["date"]]["total"] += count
                daily[row["date"]][kind] += count
                if kind == "external":
                    external_repositories[row["repository"]] += count

    if normalized_diagnostic_login:
        diagnostic_source = "organization member aggregation"
        if not diagnostic_member_found:
            diagnostic_source = "direct diagnostic query; excluded from aggregation"
            for window_start, window_end in windows:
                diagnostic_rows.extend(
                    client.fetch_contributions(
                        diagnostic_login,
                        window_start,
                        window_end,
                    )
                )
        _print_diagnostic_report(
            diagnostic_member_found,
            diagnostic_source,
            diagnostic_rows,
        )

    return build_cumulative_series(daily, start_date, end_date), external_repositories


def _print_diagnostic_report(member_found, source, rows):
    type_counts = Counter()
    visibility_counts = Counter()
    month_counts = Counter()
    public_repositories = defaultdict(Counter)

    for row in rows:
        count = int(row["count"])
        contribution_type = row["type"]
        type_counts[contribution_type] += count
        month_counts[row["date"].strftime("%Y-%m")] += count

        visibility = row["visibility"]
        visibility_counts[visibility] += count
        if not row["is_private"]:
            public_repositories[row["repository"]][contribution_type] += count

    print("--- Targeted contribution diagnostics ---")
    print(
        "Diagnostic account present in organization discovery: "
        f"{'yes' if member_found else 'no'}"
    )
    print(f"Diagnostic query source: {source}")
    print(f"GitHub-attributed contributions returned: {sum(type_counts.values())}")
    for contribution_type in (
        "commit",
        "pull-request",
        "issue",
        "pull-request-review",
    ):
        print(
            f"  {contribution_type}: "
            f"{type_counts.get(contribution_type, 0)}"
        )

    print("Repository visibility returned by GitHub:")
    if visibility_counts:
        for visibility, count in sorted(visibility_counts.items()):
            print(f"  {visibility}: {count}")
    else:
        print("  none")

    print("Contributions by month:")
    if month_counts:
        for month, count in sorted(month_counts.items()):
            print(f"  {month}: {count}")
    else:
        print("  none")

    print("Public repositories returned for diagnostic account:")
    if not public_repositories:
        print("  none")
        return

    for repository, counts in sorted(
        public_repositories.items(),
        key=lambda item: (-sum(item[1].values()), item[0].casefold()),
    ):
        details = ", ".join(
            f"{contribution_type}={count}"
            for contribution_type, count in sorted(counts.items())
        )
        print(f"  {repository}: {sum(counts.values())} ({details})")


def month_windows(start_date, end_date):
    windows = []
    current = start_date

    while current <= end_date:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        window_end = min(next_month - timedelta(days=1), end_date)
        windows.append((current, window_end))
        current = window_end + timedelta(days=1)

    return windows


def build_cumulative_series(daily, start_date, end_date):
    cumulative = {"total": 0, "internal": 0, "external": 0}
    series = []
    current = start_date

    while current <= end_date:
        values = daily[current]
        cumulative["total"] += values["total"]
        cumulative["internal"] += values["internal"]
        cumulative["external"] += values["external"]
        series.append(
            {
                "date": current,
                "total": cumulative["total"],
                "internal": cumulative["internal"],
                "external": cumulative["external"],
            }
        )
        current += timedelta(days=1)

    return series
