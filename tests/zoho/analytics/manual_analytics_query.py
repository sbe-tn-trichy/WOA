"""Run a live dynamic SQL query through the Zoho Analytics SDK.

The access token is retrieved at runtime through ``HttpTokenProvider``. All
settings have safe development defaults and can be overridden with environment
variables.
"""

import os
import sys
from pathlib import Path
from typing import Any

from zoho import HttpTokenProvider, ZohoAnalyticsAPI
from workflows.runtime.config import _load_config_dict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_config() -> dict[str, Any]:
    return _load_config_dict(PROJECT_ROOT)


def run_query() -> list[dict[str, Any]]:
    config = _load_config()
    token_url = os.environ.get(
        "TOKEN_URL", "http://localhost:3000/server/new/tokens"
    )
    access_token = HttpTokenProvider(token_url).get_token("analytics")
    organization_id = os.environ.get(
        "ZOHO_ANALYTICS_ORGANIZATION_ID", "60018545708"
    )
    workspace_id = os.environ.get(
        "ZOHO_ANALYTICS_WORKSPACE_ID", "264324000000002043"
    )
    sql_query = os.environ.get(
        "ZOHO_ANALYTICS_SQL_QUERY",
        'SELECT * FROM "Payment Customer Finder" LIMIT 5',
    )
    domain = os.environ.get("ZOHO_ANALYTICS_DOMAIN") or config.get("domain", "com")
    poll_interval = float(os.environ.get("ZOHO_ANALYTICS_POLL_INTERVAL", "2"))
    max_attempts = int(os.environ.get("ZOHO_ANALYTICS_MAX_ATTEMPTS", "30"))

    client = ZohoAnalyticsAPI(
        access_token=access_token,
        organization_id=organization_id,
        domain=domain,
    )
    return client.queries.execute(
        workspace_id=workspace_id,
        sql_query=sql_query,
        poll_interval=poll_interval,
        max_attempts=max_attempts,
    )


if __name__ == "__main__":
    try:
        result = run_query()
    except Exception as exc:
        print(f"LIVE QUERY FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(f"LIVE QUERY SUCCEEDED: {len(result)} row(s)")
    print(json.dumps(result[:5], indent=2, default=str))
