#!/usr/bin/env python3
"""
Nginx Log Watcher with Slack Alerting
Monitors nginx access logs for failovers and error rates
"""

import re
import time
import os
import json
import subprocess
from collections import deque
from datetime import datetime
import requests
from typing import Optional, Dict, Any

class LogWatcher:
    def __init__(self):
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL', '')
        self.error_threshold = float(os.getenv('ERROR_RATE_THRESHOLD', '2'))
        self.window_size = int(os.getenv('WINDOW_SIZE', '200'))
        self.cooldown_sec = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))
        self.maintenance_mode = os.getenv('MAINTENANCE_MODE', 'false').lower() == 'true'

        # State tracking
        self.current_pool: Optional[str] = None
        self.request_window = deque(maxlen=self.window_size)
        self.last_alert_times: Dict[str, float] = {}
        self.line_count = 0

        # Log pattern
        self.log_pattern = re.compile(
            r'pool=(?P<pool>[\w\-]+)\s+'
            r'release=(?P<release>[\w\-\.]+)\s+'
            r'upstream_status=(?P<upstream_status>[\d,\s]+)\s+'  # Can be "502" or "500, 502"
            r'upstream_addr=(?P<upstream_addr>[\w\.\:,\s]+)'      # Can be single or multiple
        )

        print(f"🔍 Log Watcher initialized")
        print(f"   Error threshold: {self.error_threshold}%")
        print(f"   Window size: {self.window_size} requests")
        print(f"   Alert cooldown: {self.cooldown_sec}s")
        print(f"   Maintenance mode: {self.maintenance_mode}")
        print(f"   Slack webhook configured: {bool(self.slack_webhook)}")
        if self.slack_webhook:
            print(f"   Webhook URL: {self.slack_webhook[:50]}...")

    def send_slack_alert(self, alert_type: str, message: str, details: Dict[str, Any]):
        """Send alert to Slack with cooldown enforcement"""
        print(f"\n🔔 Attempting to send {alert_type} alert...")

        if not self.slack_webhook:
            print(f"⚠️  Slack webhook not configured, skipping alert: {message}")
            return

        if self.maintenance_mode and alert_type != 'recovery':
            print(f"🔧 Maintenance mode: suppressing {alert_type} alert")
            return

        # Check cooldown
        now = time.time()
        last_alert = self.last_alert_times.get(alert_type, 0)
        if now - last_alert < self.cooldown_sec:
            print(f"⏱️  Alert cooldown active for {alert_type}, skipping")
            return

        # Color coding
        colors = {
            'failover': '#FFA500',  # Orange
            'error_rate': '#FF0000',  # Red
            'recovery': '#00FF00'     # Green
        }

        # Build Slack message with simpler format first
        payload = {
            "text": f"🚨 *{alert_type.upper().replace('_', ' ')}*\n{message}",
            "attachments": [{
                "color": colors.get(alert_type, '#808080'),
                "fields": [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in details.items()
                ],
                "footer": "Blue/Green Deployment Monitor | Created by @xodeeq",
                "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png",
                "ts": int(now)
            }],
            "username": "Deployment Bot",
            "icon_emoji": ":rotating_light:"
        }

        print(f"   Payload: {json.dumps(payload, indent=2)[:200]}...")

        try:
            print(f"   Posting to: {self.slack_webhook[:50]}...")
            response = requests.post(
                self.slack_webhook,
                json=payload,
                timeout=5
            )
            print(f"   Response status: {response.status_code}")
            print(f"   Response body: {response.text}")

            if response.status_code == 200:
                print(f"✅ Slack alert sent: {alert_type}")
                self.last_alert_times[alert_type] = now
            else:
                print(f"❌ Slack alert failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Error sending Slack alert: {e}")
            import traceback
            traceback.print_exc()

    def check_failover(self, pool: str, release: str):
        """Detect pool changes (failover events)"""
        if self.current_pool is None:
            self.current_pool = pool
            print(f"📍 Initial pool detected: {pool} ({release})")
            return

        if pool != self.current_pool:
            old_pool = self.current_pool
            self.current_pool = pool

            message = f"Failover detected: {old_pool} → {pool}"
            details = {
                "Previous Pool": old_pool,
                "Current Pool": pool,
                "Release ID": release,
                "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            print(f"\n🔄 {message}")
            print(f"   Details: {details}")
            self.send_slack_alert('failover', message, details)

    def check_error_rate(self):
        """Check if error rate exceeds threshold"""
        if len(self.request_window) < self.window_size:
            return  # Not enough data yet

        error_count = sum(1 for status in self.request_window if status >= 500)
        error_rate = (error_count / len(self.request_window)) * 100

        # Log error rate periodically
        if self.line_count % 50 == 0:
            print(f"   Current error rate: {error_rate:.2f}% ({error_count}/{len(self.request_window)})")

        if error_rate > self.error_threshold:
            message = f"High error rate detected: {error_rate:.2f}%"
            details = {
                "Error Rate": f"{error_rate:.2f}%",
                "Threshold": f"{self.error_threshold}%",
                "Window Size": self.window_size,
                "5xx Count": error_count,
                "Current Pool": self.current_pool or "unknown",
                "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            print(f"\n⚠️  {message}")
            print(f"   Details: {details}")
            self.send_slack_alert('error_rate', message, details)

    def process_log_line(self, line: str):
        """Parse and process a single log line"""
        self.line_count += 1

        match = self.log_pattern.search(line)
        if not match:
            if self.line_count % 100 == 0:
                print(f"   Processed {self.line_count} lines, no pattern match in recent line")
            return

        pool = match.group('pool')
        release = match.group('release')
        upstream_status_raw = match.group('upstream_status')
        upstream_addr = match.group('upstream_addr')

        # Parse status - could be "200" or "500, 500, 502"
        # Take the LAST status (final result)
        statuses = [int(s.strip()) for s in upstream_status_raw.split(',') if s.strip().isdigit()]
        if not statuses:
            return
        upstream_status = statuses[-1]  # Use the last/final status

        # Skip lines where pool/release are unavailable
        if pool == '-' or release == '-':
            # Still track errors for error rate calculation
            self.request_window.append(upstream_status)
            if self.line_count % 50 == 0:
                print(f"   [{self.line_count}] No backend available, status={upstream_status}")
            # Check error rate even without pool info
            self.check_error_rate()
            return

        # Log every request for debugging
        if self.line_count <= 10 or self.line_count % 50 == 0:
            print(f"   [{self.line_count}] pool={pool} status={upstream_status} addr={upstream_addr[:20]}")

        # Track request in window
        self.request_window.append(upstream_status)

        # Check for failover
        self.check_failover(pool, release)

        # Check error rate
        self.check_error_rate()

    def tail_log(self, log_path: str):
        """Tail nginx log file using tail -F command"""
        print(f"📂 Waiting for log file: {log_path}")

        # Wait for log file to exist
        while not os.path.exists(log_path):
            time.sleep(1)

        print(f"📖 Tailing log file: {log_path}")

        # Use tail -F to follow the log file (works with rotations and symlinks)
        process = subprocess.Popen(
            ['tail', '-F', '-n', '0', log_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        try:
            if process.stdout is None:
                raise RuntimeError("Failed to read from tail subprocess stdout")
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.process_log_line(line)
        except KeyboardInterrupt:
            process.terminate()
            raise

def main():
    log_path = '/var/log/nginx/access.log'
    watcher = LogWatcher()

    try:
        watcher.tail_log(log_path)
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == '__main__':
    main()
