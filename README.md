# New channel alert

Daily GitHub Actions job that detects `channel_id`s appearing for the first time in
`st_datalakehouse.analytics.etl_ssp_responses_daily_enriched` (present after a cutoff
date, default yesterday, but never on or before it) and posts an alert to the Slack
channel **#bi-demand**. Silent when there are none.

Runs every day at 07:00 UTC (~09:00 Madrid) on the `seedtag-gke-runners` self-hosted
pool, where `gcloud` has ambient credentials used to authenticate against Trino
(`trino-users.seedt.ag`). Stdlib-only Python 3.11 — no dependencies.

## Prerequisites

- **`ALERTS_SLACK_TOKEN` repo secret** — a Slack bot token with `chat:write`; the bot
  must be a member of #bi-demand. Same Slack app setup as source_truth_v2's deal
  alerts (its token lives in `.env` locally / the Composer Connection
  `slack_sot_alerts`) — the same token can be reused here. The channel can be
  overridden with `ALERTS_CHANNEL` (defaults to `#bi-demand`).
- **Trino authorization** — the runner's gcloud service account must be authorized to
  query Trino at `trino-users.seedt.ag`.

## Testing locally

Dry run (prints the message instead of posting, since no Slack token is set):

```bash
TRINO_USER=$(gcloud config get account) TRINO_ACCESS_TOKEN=$(gcloud auth print-access-token) python scripts/check_new_channels.py
```

Forced-positive test — set the cutoff a week back so recently-appeared channels count as "new":

```bash
CUTOFF_DATE=$(date -v-7d +%F) TRINO_USER=$(gcloud config get account) TRINO_ACCESS_TOKEN=$(gcloud auth print-access-token) python scripts/check_new_channels.py
```

(On Linux use `date -d '7 days ago' +%F`.)
