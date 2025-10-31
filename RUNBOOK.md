# Blue/Green Deployment Operations Runbook

## Overview
This runbook provides guidance for responding to alerts from the Blue/Green deployment monitoring system.

## Quick Reference

| Alert Type | Color | Meaning | Immediate Action |
|------------|-------|---------|------------------|
| **Failover** | 🟠 Orange | Traffic switched from one pool to another due to health issues | Check health of failed pool, verify if expected |
| **High Error Rate** | 🔴 Red | 5xx errors exceed threshold over sliding window | Inspect upstream logs, consider pool toggle or rollback |
| **Recovery** | 🟢 Green | Previously failed pool has recovered and is healthy | Note recovery time, document resolution |

**When to act immediately:**
- Failover during business hours → Investigate within 15 minutes
- High error rate → Respond immediately, users are affected
- Recovery → Acknowledge and document

---

## Alert Types

### 1. Failover Alert 🔄

**What it means:**
The system has automatically switched from one pool to another (Blue→Green or Green→Blue) due to health issues with the primary pool.

**Alert contains:**
- Previous Pool
- Current Pool
- Release ID
- Timestamp

**Immediate Actions:**
1. **Verify the failover was expected:**
   ```bash
   # Check if you triggered a manual toggle
   cat .env | grep ACTIVE_POOL
   ```

2. **Check health of the failed pool:**
   ```bash
   # If Blue failed
   docker compose logs app_blue --tail=50
   curl http://localhost:8081/healthz

   # If Green failed
   docker compose logs app_green --tail=50
   curl http://localhost:8082/healthz
   ```

3. **Check current traffic routing:**
   ```bash
   for i in {1..10}; do
     curl -s http://localhost:8080/version | grep -E "X-App-Pool|X-Release-Id"
     sleep 1
   done
   ```

**Root Cause Investigation:**
- Review application logs for errors
- Check resource usage: `docker stats`
- Verify external dependencies (databases, APIs)
- Check if chaos mode was accidentally triggered

**Resolution:**
- If chaos mode was active: Stop it
  ```bash
  curl -X POST http://localhost:808X/chaos/stop
  ```
- If legitimate failure: Fix the underlying issue
- Monitor for stability before switching back
- Consider leaving backup pool as primary if stable

**Prevent Future Occurrences:**
- Address root cause identified in logs
- Review deployment procedures
- Consider increasing health check intervals

---

### 2. High Error Rate Alert ⚠️

**What it means:**
More than X% of requests returned 5xx errors over the last Y requests (configurable via ERROR_RATE_THRESHOLD and WINDOW_SIZE).

**Alert contains:**
- Current error rate (%)
- Configured threshold (%)
- Window size
- Number of 5xx errors
- Current active pool
- Timestamp

**Immediate Actions:**
1. **Verify current system state:**
   ```bash
   # Check which pool is serving traffic
   curl -i http://localhost:8080/version

   # Check both pools directly
   curl http://localhost:8081/version
   curl http://localhost:8082/version
   ```

2. **Check application logs:**
   ```bash
   docker compose logs app_blue app_green --tail=100
   ```

3. **Review Nginx logs:**
   ```bash
   docker compose logs nginx --tail=50
   ```

**Root Cause Investigation:**
- Database connection issues
- External API failures
- Resource exhaustion (CPU, memory)
- Configuration errors
- Deployment issues (bad release)

**Resolution Options:**

**Option A - Switch pools manually:**
```bash
# Edit .env
sed -i 's/ACTIVE_POOL=blue/ACTIVE_POOL=green/' .env
# Or vice versa

# Recreate nginx
docker compose up -d --force-recreate nginx

# Verify
curl -i http://localhost:8080/version
```

**Option B - Restart affected pool:**
```bash
docker compose restart app_blue  # or app_green
```

**Option C - Rollback to previous version:**
```bash
# Update .env with previous image tag
vim .env  # Change BLUE_IMAGE or GREEN_IMAGE

# Restart affected pool
docker compose up -d --force-recreate app_blue  # or app_green
```

**Prevention:**
- Implement circuit breakers in application
- Add pre-deployment smoke tests
- Monitor resource usage trends
- Set up proper application logging

---

### 3. Recovery Alert ✅

**What it means:**
The previously failed pool has recovered and is back in rotation (future enhancement).

**Actions:**
- Note the recovery time
- Review what resolved the issue
- Document for post-incident review

---

## Maintenance Mode

During planned maintenance or manual pool toggles, suppress alerts:

```bash
# Enable maintenance mode
echo "MAINTENANCE_MODE=true" >> .env
docker compose up -d --force-recreate alert_watcher

# Perform your maintenance
# ...

# Disable maintenance mode
sed -i 's/MAINTENANCE_MODE=true/MAINTENANCE_MODE=false/' .env
docker compose up -d --force-recreate alert_watcher
```

**Note:** Recovery alerts are NOT suppressed during maintenance mode.

---

## Configuration Reference

All settings are in `.env`:

```bash
# Slack webhook for alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Error rate threshold (percentage)
ERROR_RATE_THRESHOLD=2

# Number of requests to track for error rate
WINDOW_SIZE=200

# Minimum seconds between same alert type
ALERT_COOLDOWN_SEC=300

# Suppress non-critical alerts during maintenance
MAINTENANCE_MODE=false
```

---

## Troubleshooting

### Alert Watcher Not Sending Alerts

1. **Check webhook configuration:**
   ```bash
   docker compose exec alert_watcher env | grep SLACK_WEBHOOK_URL
   ```

2. **Check watcher logs:**
   ```bash
   docker compose logs alert_watcher
   ```

3. **Test webhook manually:**
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"Test alert"}' \
     $SLACK_WEBHOOK_URL
   ```

### Watcher Not Detecting Failovers

1. **Verify log format in Nginx:**
   ```bash
   docker compose exec nginx cat /var/log/nginx/access.log | tail -5
   ```
   Should show: `pool=blue release=...`

2. **Check volume mounting:**
   ```bash
   docker compose exec alert_watcher ls -la /var/log/nginx/
   ```

### Too Many Alerts

1. **Increase cooldown period:**
   ```bash
   # In .env
   ALERT_COOLDOWN_SEC=600  # 10 minutes
   ```

2. **Increase error threshold:**
   ```bash
   # In .env
   ERROR_RATE_THRESHOLD=5  # 5%
   ```

3. **Enable maintenance mode temporarily:**
   ```bash
   # In .env
   MAINTENANCE_MODE=true
   ```


---

## Post-Incident Review

After resolving any alert:

1. Document timeline of events
2. Identify root cause
3. List action items to prevent recurrence
4. Update runbook if needed
5. Share learnings with team

---

## Quick Reference Commands

```bash
# Check system status
docker compose ps

# View all logs
docker compose logs -f

# Check specific pool health
curl http://localhost:8081/healthz  # Blue
curl http://localhost:8082/healthz  # Green

# Manual pool toggle
sed -i 's/ACTIVE_POOL=blue/ACTIVE_POOL=green/' .env
docker compose up -d --force-recreate nginx

# Restart alert watcher
docker compose restart alert_watcher

# Stop all chaos
curl -X POST http://localhost:8081/chaos/stop
curl -X POST http://localhost:8082/chaos/stop
```
