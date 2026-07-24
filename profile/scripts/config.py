import os
from datetime import date


_org_names_value = os.environ.get("ORG_NAMES")
if _org_names_value is None:
    _org_names_value = os.environ.get("ORG_NAME", "gisa-oss")
ORG_NAMES = [
    org.strip()
    for org in _org_names_value.split(",")
    if org.strip()
]
INTERNAL_ORGS = [
    org.strip().lower()
    for org in os.environ.get("INTERNAL_ORGS", "gisa-oss").split(",")
    if org.strip()
]

DIAGNOSTIC_LOGIN = os.environ.get("DIAGNOSTIC_LOGIN", "").strip()
DIAGNOSTICS_REQUESTED = (
    os.environ.get("DIAGNOSTICS_REQUESTED", "false").lower()
    in {"1", "true", "yes", "on"}
)

START_DATE = date(2026, 1, 1)
TODAY = date.today()

ASSETS_DIR = "assets"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
