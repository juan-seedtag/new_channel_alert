# New channel alert

Daily GitHub Actions job that detects `channel_id`s appearing for the first time in
`st_datalakehouse.analytics.etl_ssp_responses_daily_enriched` (present after a cutoff
date, default yesterday, but never on or before it) and posts an alert to the Slack
channel **#bi-demand**. Silent when there are none.

Runs every day at 07:00 UTC (~09:00 Madrid) on the `seedtag-gke-runners` self-hosted
pool, where `gcloud` has ambient credentials used to authenticate against Trino
(`trino-users.seedt.ag`). Stdlib-only Python 3.11 — no dependencies.

## Prerequisites

- **`SLACK_WEBHOOK_URL` repo secret** — an incoming-webhook URL pointing at #bi-demand.
- **Trino authorization** — the runner's gcloud service account must be authorized to
  query Trino at `trino-users.seedt.ag`.

## Testing locally

Dry run (prints the message instead of posting, since no webhook is set):

```bash
TRINO_USER=$(gcloud config get account) TRINO_ACCESS_TOKEN=$(gcloud auth print-access-token) python scripts/check_new_channels.py
```

Forced-positive test — set the cutoff a week back so recently-appeared channels count as "new":

```bash
CUTOFF_DATE=$(date -v-7d +%F) TRINO_USER=$(gcloud config get account) TRINO_ACCESS_TOKEN=$(gcloud auth print-access-token) python scripts/check_new_channels.py
```

(On Linux use `date -d '7 days ago' +%F`.)
