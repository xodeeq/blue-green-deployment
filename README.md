## Stage 3: Monitoring and Alerting

### Setup

1. **Configure Slack Webhook:**
```bash
   # Edit .env and add your Slack webhook URL
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

2. **Start all services:**
```bash
   docker compose up -d --build
```

3. **Verify services are running:**
```bash
   docker compose ps
```

### Testing Alerts

**Automated tests:**
```bash
./test-monitoring.sh
```

**Manual alert generation (for screenshots):**
```bash
./trigger-alerts-for-screenshots.sh
```

### Viewing Logs

**Check Nginx structured logs:**
```bash
docker compose exec nginx tail -f /var/log/nginx/access.log
```

**Check alert watcher logs:**
```bash
docker compose logs -f alert_watcher
```

**Verify Slack messages in your Slack channel**

### Screenshots

See `/screenshots` directory for:
- `failover-alert.png` - Slack message when failover occurs
- `error-rate-alert.png` - Slack message when error rate exceeds threshold
- `nginx-logs.png` - Structured Nginx log format showing pool, release, status

### Configuration

All settings in `.env`:
- `SLACK_WEBHOOK_URL` - Slack incoming webhook
- `ERROR_RATE_THRESHOLD` - Error percentage before alert (default: 2%)
- `WINDOW_SIZE` - Number of requests to track (default: 200)
- `ALERT_COOLDOWN_SEC` - Seconds between same alert type (default: 300)
- `MAINTENANCE_MODE` - Suppress alerts during maintenance (default: false)

See `RUNBOOK.md` for operational procedures.
