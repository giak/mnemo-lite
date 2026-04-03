# OpenObserve UI Configuration Guide

> Manual steps for components that cannot be configured via API.
> Complete after running `make o2-setup` (which handles Functions, Streams, Dashboards via API).

## Prerequisites

1. Run `make o2-setup` first
2. Open http://localhost:5080
3. Login: `admin@mnemolite.local` / `Complexpass#123`
4. Ensure logs are flowing (API/MCP/Worker running)

---

## 1. Create Pipelines (Real-Time)

Pipelines associate VRL functions with streams. The functions are already created via API; now link them to streams.

### Pipeline: MnemoLite API Logs

1. Go to **Pipelines** > **Add Pipeline**
2. Name: `mnemolite-api-pipeline`
3. **Source**: Drag **Stream** node
   - Stream Type: `logs`
   - Stream Name: `mnemolite-api`
   - Click **Save**
4. **Transform**: Drag **Function** node (repeat 4 times for each function)
   - Associate Function: `normalize_log_level` > **Save**
   - Associate Function: `enrich_service_metadata` > **Save**
   - Associate Function: `extract_http_fields` > **Save**
   - Associate Function: `filter_noise_logs` > **Save**
5. **Destination**: Drag **Stream** node
   - Stream Name: `mnemolite-api` (same as source — catch-all)
   - Click **Save**
6. **Connect nodes**: Source → Functions (in order) → Destination
7. Click **Save** (pipeline activates automatically)

### Pipeline: MCP Logs

Repeat above with:
- Name: `mnemolite-mcp-pipeline`
- Source Stream: `mnemolite-mcp`
- Same 4 functions
- Destination: `mnemolite-mcp`

### Pipeline: Worker Logs

Repeat above with:
- Name: `conversation-worker-pipeline`
- Source Stream: `conversation-worker`
- Same 4 functions
- Destination: `conversation-worker`

---

## 2. Create Alert Templates

Go to **Management** > **Templates** > **Add Template**

### Template: MnemoLite Alert (Webhook/Slack)

- **Name**: `mnemolite_alert`
- **Type**: Webhook
- **Body**:
```json
{
  "text": "MnemoLite Alert: {alert_name}\nService: {service_name}\nSeverity: {severity}\nStream: {stream_name}\nCount: {alert_count}\nURL: {alert_url}\nDetails:\n{rows:5}"
}
```

### Template: MnemoLite Email Alert

- **Name**: `mnemolite_email`
- **Type**: Email
- **Title**: `Alert: {alert_name} - {severity}`
- **Body**:
```html
<h3>Alert: {alert_name}</h3>
<ul>
  <li>Severity: {severity}</li>
  <li>Service: {service_name}</li>
  <li>Stream: {stream_name}</li>
  <li>Count: {alert_count}</li>
  <li>URL: <a href="{alert_url}">View in OpenObserve</a></li>
</ul>
<h4>Details (first 5):</h4>
{rows:5}
```

---

## 3. Create Alert Destinations

Go to **Management** > **Alert Destinations** > **Add Destination**

### Destination: Local Webhook (for testing)

- **Name**: `mnemolite_webhook`
- **Type**: Webhook
- **URL**: `http://host.docker.internal:9090/webhook` (or your notification endpoint)
- **Method**: POST
- **Template**: `mnemolite_alert`
- **Headers**: `Content-Type: application/json`

### Destination: Email (if SMTP configured)

- **Name**: `mnemolite_email_dest`
- **Type**: Email
- **Email**: your-email@example.com
- **Template**: `mnemolite_email`

---

## 4. Create Alerts

Go to **Alerts** > **Add Alert**

### Alert 1: High API Error Rate

- **Name**: `High API Error Rate`
- **Stream Type**: `logs`
- **Stream Name**: `mnemolite-api`
- **Alert Type**: Scheduled
- **Frequency**: Every 5 minutes
- **Period**: Last 5 minutes
- **Silence**: 5 minutes
- **Threshold**: 10
- **Mode**: SQL
- **Query**:
```sql
SELECT http_status, count(*) as error_count
FROM "mnemolite-api"
WHERE http_status >= 500
GROUP BY http_status
HAVING error_count > 10
```
- **Destination**: `mnemolite_webhook`
- **Severity**: Critical

### Alert 2: High API Latency

- **Name**: `High API Latency`
- **Stream Type**: `logs`
- **Stream Name**: `mnemolite-api`
- **Alert Type**: Scheduled
- **Frequency**: Every 5 minutes
- **Period**: Last 5 minutes
- **Silence**: 5 minutes
- **Threshold**: 1
- **Mode**: SQL
- **Query**:
```sql
SELECT path, avg(latency_ms) as avg_latency
FROM "mnemolite-api"
WHERE latency_ms IS NOT NULL
GROUP BY path
HAVING avg_latency > 2000
```
- **Destination**: `mnemolite_webhook`
- **Severity**: Warning

### Alert 3: Low Cache Hit Rate

- **Name**: `Low Cache Hit Rate`
- **Stream Type**: `logs`
- **Stream Name**: `mnemolite-api`
- **Alert Type**: Scheduled
- **Frequency**: Every 15 minutes
- **Period**: Last 15 minutes
- **Silence**: 15 minutes
- **Threshold**: 1
- **Mode**: SQL
- **Query**:
```sql
SELECT avg(cache_hit) * 100 as hit_rate
FROM "mnemolite-api"
WHERE cache_hit IS NOT NULL
HAVING hit_rate < 80
```
- **Destination**: `mnemolite_webhook`
- **Severity**: Warning

### Alert 4: Worker Processing Failures

- **Name**: `Worker Processing Failures`
- **Stream Type**: `logs`
- **Stream Name**: `conversation-worker`
- **Alert Type**: Scheduled
- **Frequency**: Every 5 minutes
- **Period**: Last 5 minutes
- **Silence**: 5 minutes
- **Threshold**: 10
- **Mode**: SQL
- **Query**:
```sql
SELECT count(*) as failures
FROM "conversation-worker"
WHERE severity = 'error'
HAVING failures > 10
```
- **Destination**: `mnemolite_webhook`
- **Severity**: Critical

---

## 5. Verify Everything

### Check Pipelines
1. Go to **Pipelines**
2. Verify 3 pipelines are active (API, MCP, Worker)
3. Ingest test logs and verify they appear with normalized fields

### Check Dashboards
1. Go to **Dashboards**
2. Verify 3 dashboards exist (API Performance, MCP Operations, Worker Health)
3. Click each dashboard and verify panels show data

### Check Alerts
1. Go to **Alerts**
2. Verify 4 alerts exist and are enabled
3. Trigger a test alert by generating error logs:
```bash
for i in $(seq 1 15); do
  curl -u "admin@mnemolite.local:Complexpass#123" \
    "http://localhost:5080/api/default/mnemolite-api/_json" \
    -H "Content-Type: application/json" \
    -d "[{\"http_status\": 500, \"message\": \"test error $i\", \"severity\": \"error\"}]"
done
```

### Export Configs
```bash
python scripts/o2_export_configs.py
git add configs/openobserve/
git commit -m "chore: export OpenObserve configuration"
```
