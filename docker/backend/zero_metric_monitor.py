"""
Zero-Metric VM Monitoring
Detects VMs reporting all zeros and sends alerts
"""
import asyncio
import logging
from typing import List, Dict
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class ZeroMetricMonitor:
    """Monitors for VMs reporting zero metrics"""

    def __init__(self, db_pool, notification_service=None):
        self.db = db_pool
        self.notification_service = notification_service
        self.check_interval = int(os.getenv('ZERO_METRIC_CHECK_INTERVAL', '300'))  # 5 minutes
        self.alert_threshold = int(os.getenv('ZERO_METRIC_THRESHOLD', '3'))  # 3 consecutive checks
        self.zero_metric_counts = {}  # Track consecutive zero-metric occurrences
        self.alerted_vms = set()  # Track which VMs we've already alerted on

    async def find_zero_metric_vms(self) -> List[Dict]:
        """Find VMs with all zero metrics"""
        async with self.db.acquire() as conn:
            query = """
                SELECT
                    hostname,
                    cpu_usage,
                    memory_usage,
                    disk_usage,
                    timestamp,
                    status
                FROM vm_metrics
                WHERE cpu_usage = 0.0
                  AND memory_usage = 0.0
                  AND disk_usage = 0.0
                  AND status = 'online'
                ORDER BY hostname
            """
            rows = await conn.fetch(query)

            return [
                {
                    'hostname': row['hostname'],
                    'cpu': row['cpu_usage'],
                    'memory': row['memory_usage'],
                    'disk': row['disk_usage'],
                    'last_update': row['timestamp'],
                    'status': row['status']
                }
                for row in rows
            ]

    async def check_and_alert(self):
        """Check for zero-metric VMs and send alerts"""
        try:
            zero_vms = await self.find_zero_metric_vms()

            if not zero_vms:
                logger.info("✓ No VMs with zero metrics detected")
                # Reset all counters
                self.zero_metric_counts.clear()
                self.alerted_vms.clear()
                return

            logger.warning(f"⚠ Found {len(zero_vms)} VMs with zero metrics")

            # Update zero metric counts
            current_zero_hostnames = {vm['hostname'] for vm in zero_vms}

            # Reset counters for VMs that are no longer zero
            for hostname in list(self.zero_metric_counts.keys()):
                if hostname not in current_zero_hostnames:
                    self.zero_metric_counts.pop(hostname, None)
                    self.alerted_vms.discard(hostname)

            # Increment counters for zero-metric VMs
            for vm in zero_vms:
                hostname = vm['hostname']
                self.zero_metric_counts[hostname] = self.zero_metric_counts.get(hostname, 0) + 1

                # Alert if threshold reached and not already alerted
                if (self.zero_metric_counts[hostname] >= self.alert_threshold and
                    hostname not in self.alerted_vms):

                    await self._send_zero_metric_alert(vm, self.zero_metric_counts[hostname])
                    self.alerted_vms.add(hostname)

        except Exception as e:
            logger.error(f"✗ Error in zero-metric check: {e}")

    async def _send_zero_metric_alert(self, vm_data: Dict, occurrence_count: int):
        """Send alert for a VM with zero metrics"""
        if not self.notification_service:
            logger.warning(f"No notification service configured for zero-metric alert: {vm_data['hostname']}")
            return

        try:
            title = f"⚠️ Zero Metrics Detected - {vm_data['hostname']}"

            message = f"""
**VM Reporting Zero Metrics**

**Hostname:** {vm_data['hostname']}
**Status:** {vm_data['status']}
**Last Update:** {vm_data['last_update']}
**Consecutive Occurrences:** {occurrence_count} checks

**Current Metrics:**
- CPU Usage: 0.0%
- Memory Usage: 0.0%
- Disk Usage: 0.0%

**Possible Causes:**
1. Telegraf agent not running or crashed
2. Telegraf configuration missing input plugins
3. Permission issues reading /proc metrics
4. VM is powered off but still reporting heartbeat
5. Telegraf version compatibility issue

**Recommended Actions:**
1. SSH to the VM: `ssh {vm_data['hostname']}.ad.analog.com`
2. Check Telegraf status: `systemctl status telegraf`
3. Check Telegraf logs: `journalctl -u telegraf -n 50`
4. Test metric collection: `telegraf --test --config /etc/telegraf/telegraf.conf`
5. Restart Telegraf: `systemctl restart telegraf`

**Automatic Fix Script:**
Run: `bash fix_zero_metrics.sh` and select option 1 to diagnose this VM
            """

            # Send email notification
            if hasattr(self.notification_service, 'email_notifier') and \
               self.notification_service.email_notifier and \
               os.getenv('EMAIL_ENABLED', 'false').lower() == 'true':

                await self.notification_service.email_notifier.send_email(
                    subject=title,
                    body_html=message.replace('\n', '<br>').replace('**', '<strong>').replace('**', '</strong>'),
                    severity='warning'
                )
                logger.info(f"✓ Sent email alert for zero-metric VM: {vm_data['hostname']}")

            # Send Slack notification
            if hasattr(self.notification_service, 'slack_notifier') and \
               self.notification_service.slack_notifier and \
               os.getenv('SLACK_ENABLED', 'false').lower() == 'true':

                fields = [
                    {'title': 'Hostname', 'value': vm_data['hostname'], 'short': True},
                    {'title': 'Status', 'value': vm_data['status'], 'short': True},
                    {'title': 'Last Update', 'value': str(vm_data['last_update']), 'short': True},
                    {'title': 'Occurrences', 'value': str(occurrence_count), 'short': True},
                    {'title': 'CPU', 'value': '0.0%', 'short': True},
                    {'title': 'Memory', 'value': '0.0%', 'short': True}
                ]

                await self.notification_service.slack_notifier.send_slack(
                    title=title,
                    message=message,
                    severity='warning',
                    fields=fields
                )
                logger.info(f"✓ Sent Slack alert for zero-metric VM: {vm_data['hostname']}")

        except Exception as e:
            logger.error(f"✗ Failed to send zero-metric alert for {vm_data['hostname']}: {e}")

    async def start_monitoring(self):
        """Start continuous monitoring loop"""
        logger.info(f"🔍 Started zero-metric monitoring (interval: {self.check_interval}s, threshold: {self.alert_threshold})")

        while True:
            try:
                await self.check_and_alert()
            except Exception as e:
                logger.error(f"✗ Error in zero-metric monitoring loop: {e}")

            await asyncio.sleep(self.check_interval)

    async def get_zero_metric_report(self) -> Dict:
        """Get current status of zero-metric VMs"""
        zero_vms = await self.find_zero_metric_vms()

        return {
            'timestamp': datetime.now().isoformat(),
            'total_zero_metric_vms': len(zero_vms),
            'vms': zero_vms,
            'counters': {
                hostname: count
                for hostname, count in self.zero_metric_counts.items()
            },
            'alerted_vms': list(self.alerted_vms)
        }
