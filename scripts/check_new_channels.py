#!/usr/bin/env python3
"""Daily alert: detect channel_ids appearing for the first time in
st_datalakehouse.analytics.etl_ssp_responses_daily_enriched after a cutoff date,
and post to Slack (#bi-demand, chat.postMessage with a bot token — same Slack app
setup as source_truth_v2's deal alerts) when any are found. Stdlib only."""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone

QUERY_TEMPLATE = """\
SELECT DISTINCT channel_id
FROM st_datalakehouse.analytics.etl_ssp_responses_daily_enriched
WHERE date > DATE '{cutoff}'
  AND channel_id NOT IN (
    SELECT DISTINCT channel_id
    FROM st_datalakehouse.analytics.etl_ssp_responses_daily_enriched
    WHERE date <= DATE '{cutoff}' AND channel_id IS NOT NULL
  )
"""


def get_cutoff() -> str:
    cutoff = os.environ.get("CUTOFF_DATE")
    if cutoff:
        # Validate format to avoid injecting garbage into the SQL literal.
        datetime.strptime(cutoff, "%Y-%m-%d")
        return cutoff
    return (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()


def http_json(req: urllib.request.Request) -> dict:
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_trino_query(host: str, user: str, token: str, sql: str) -> list:
    headers = {
        "X-Trino-User": user,
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain",
    }
    req = urllib.request.Request(
        f"https://{host}:443/v1/statement",
        data=sql.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    result = http_json(req)

    rows = []
    while True:
        if result.get("error"):
            raise RuntimeError(f"Trino query failed: {result['error']}")
        rows.extend(result.get("data") or [])
        next_uri = result.get("nextUri")
        if not next_uri:
            break
        time.sleep(0.2)
        result = http_json(urllib.request.Request(next_uri, headers=headers))

    state = result.get("stats", {}).get("state")
    if state and state != "FINISHED":
        raise RuntimeError(f"Trino query ended in state {state}")
    return rows


def post_slack(token: str, channel: str, text: str) -> None:
    """chat.postMessage via the Slack Web API — same setup as source_truth_v2:
    bot token with chat:write, bot must be a member of the channel."""
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(
            {"channel": channel, "text": text,
             "unfurl_links": False, "unfurl_media": False}
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(f"Slack chat.postMessage: {body.get('error') or 'unknown_error'}")


def main() -> int:
    host = os.environ.get("TRINO_HOST", "trino-users.seedt.ag")
    user = os.environ.get("TRINO_USER")
    token = os.environ.get("TRINO_ACCESS_TOKEN")
    if not user or not token:
        print("ERROR: TRINO_USER and TRINO_ACCESS_TOKEN must be set", file=sys.stderr)
        return 1

    cutoff = get_cutoff()
    sql = QUERY_TEMPLATE.format(cutoff=cutoff)
    print(f"Checking for channels new after {cutoff} on {host}...")

    try:
        rows = run_trino_query(host, user, token, sql)
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"ERROR: query failed: {exc}", file=sys.stderr)
        return 1

    channel_ids = sorted(str(r[0]) for r in rows if r and r[0] is not None)
    if not channel_ids:
        print("No new channels found. Nothing to report.")
        return 0

    today = date.today().isoformat()
    message = (
        f"⚠️ New channel(s) in etl_ssp_responses_daily_enriched on {today}: "
        + ", ".join(channel_ids)
    )

    slack_token = os.environ.get("ALERTS_SLACK_TOKEN")
    slack_channel = os.environ.get("ALERTS_CHANNEL", "#bi-demand").strip()
    if not slack_token:
        print("ALERTS_SLACK_TOKEN not set — dry run. Message would be:")
        print(message)
        return 0

    try:
        post_slack(slack_token, slack_channel, message)
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"ERROR: Slack post failed: {exc}", file=sys.stderr)
        return 1

    print(f"Alert sent to {slack_channel} ({len(channel_ids)} new channel(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
