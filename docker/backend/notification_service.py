"""
Notification Service for VM Monitor
Sends alerts via Email and Slack for critical events
"""
import os
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio

logger = logging.getLogger(__name__)


class AlertRule:
    """Define alert rules and thresholds"""

    # CPU/Memory/Disk thresholds
    CPU_WARNING = float(os.getenv('ALERT_CPU_WARNING', '80'))
    CPU_CRITICAL = float(os.getenv('ALERT_CPU_CRITICAL', '95'))

    MEMORY_WARNING = float(os.getenv('ALERT_MEMORY_WARNING', '80'))
    MEMORY_CRITICAL = float(os.getenv('ALERT_MEMORY_CRITICAL', '95'))

    DISK_WARNING = float(os.getenv('ALERT_DISK_WARNING', '85'))
    DISK_CRITICAL = float(os.getenv('ALERT_DISK_CRITICAL', '95'))

    # CVE thresholds
    CVE_CRITICAL_COUNT = int(os.getenv('ALERT_CVE_CRITICAL_COUNT', '1'))  # Alert if >= 1 critical CVE
    CVE_HIGH_COUNT = int(os.getenv('ALERT_CVE_HIGH_COUNT', '5'))  # Alert if >= 5 high CVEs

    # VM offline threshold
    VM_OFFLINE_MINUTES = int(os.getenv('ALERT_VM_OFFLINE_MINUTES', '10'))

    # Alert cooldown (don't spam)
    ALERT_COOLDOWN_MINUTES = int(os.getenv('ALERT_COOLDOWN_MINUTES', '60'))


class EmailNotifier:
    """Send email notifications"""

    def __init__(self):
        self.enabled = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.from_email = os.getenv('SMTP_FROM_EMAIL', self.smtp_username)
        self.to_emails = os.getenv('ALERT_EMAIL_TO', '').split(',')

        if self.enabled and not all([self.smtp_username, self.smtp_password]):
            logger.warning("Email notifications enabled but SMTP credentials not configured")
            self.enabled = False

    def send_email(self, subject: str, body_html: str, severity: str = 'warning') -> bool:
        """Send email notification"""
        if not self.enabled:
            logger.debug("Email notifications disabled")
            return False

        if not self.to_emails or not self.to_emails[0]:
            logger.warning("No recipient email addresses configured")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[VM Monitor] {subject}"
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)

            # HTML email body
            html_part = MIMEText(body_html, 'html')
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"✓ Email sent: {subject} to {len(self.to_emails)} recipients")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to send email: {e}")
            return False


class SlackNotifier:
    """Send Slack notifications via webhook"""

    def __init__(self):
        self.enabled = os.getenv('SLACK_ENABLED', 'false').lower() == 'true'
        self.webhook_url = os.getenv('SLACK_WEBHOOK_URL')

        if self.enabled and not self.webhook_url:
            logger.warning("Slack notifications enabled but webhook URL not configured")
            self.enabled = False

    def send_slack(self, title: str, message: str, severity: str = 'warning', fields: List[Dict] = None) -> bool:
        """Send Slack notification"""
        if not self.enabled:
            logger.debug("Slack notifications disabled")
            return False

        # Color based on severity
        color_map = {
            'info': '#36a64f',      # Green
            'warning': '#ff9800',   # Orange
            'critical': '#f44336'   # Red
        }
        color = color_map.get(severity, '#ff9800')

        # Build Slack message payload
        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": title,
                    "text": message,
                    "footer": "VM Monitor Alert System",
                    "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }

        # Add fields if provided
        if fields:
            payload["attachments"][0]["fields"] = fields

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            logger.info(f"✓ Slack notification sent: {title}")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to send Slack notification: {e}")
            return False


class NotificationService:
    """Main notification service coordinating all alert channels"""

    def __init__(self):
        self.email = EmailNotifier()
        self.slack = SlackNotifier()

        # Track sent alerts to avoid spam (hostname -> last_alert_time)
        self.alert_history = {}

    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if enough time has passed since last alert (cooldown)"""
        if alert_key not in self.alert_history:
            return True

        last_alert = self.alert_history[alert_key]
        cooldown = timedelta(minutes=AlertRule.ALERT_COOLDOWN_MINUTES)

        if datetime.now() - last_alert > cooldown:
            return True

        logger.debug(f"Alert suppressed (cooldown): {alert_key}")
        return False

    def _record_alert(self, alert_key: str):
        """Record that an alert was sent"""
        self.alert_history[alert_key] = datetime.now()

    async def send_vm_critical_alert(self, vm_data: Dict):
        """Send alert for VM in critical state"""
        hostname = vm_data.get('hostname', 'Unknown')
        cpu = vm_data.get('cpu_usage', 0)
        memory = vm_data.get('memory_usage', 0)
        disk = vm_data.get('disk_usage', 0)

        alert_key = f"vm_critical_{hostname}"
        if not self._should_send_alert(alert_key):
            return

        # Email
        email_subject = f"🚨 CRITICAL: {hostname} - High Resource Usage"
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #f44336;">⚠️ Critical Alert: VM {hostname}</h2>
            <p>The following VM has exceeded critical thresholds:</p>

            <table style="border-collapse: collapse; width: 100%; max-width: 500px;">
                <tr style="background: #f5f5f5;">
                    <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Metric</th>
                    <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Value</th>
                    <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Status</th>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;">CPU Usage</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{cpu:.1f}%</td>
                    <td style="padding: 10px; border: 1px solid #ddd; color: {'#f44336' if cpu > AlertRule.CPU_CRITICAL else '#ff9800'};">
                        {'CRITICAL' if cpu > AlertRule.CPU_CRITICAL else 'WARNING'}
                    </td>
                </tr>
                <tr style="background: #f5f5f5;">
                    <td style="padding: 10px; border: 1px solid #ddd;">Memory Usage</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{memory:.1f}%</td>
                    <td style="padding: 10px; border: 1px solid #ddd; color: {'#f44336' if memory > AlertRule.MEMORY_CRITICAL else '#ff9800'};">
                        {'CRITICAL' if memory > AlertRule.MEMORY_CRITICAL else 'WARNING'}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;">Disk Usage</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{disk:.1f}%</td>
                    <td style="padding: 10px; border: 1px solid #ddd; color: {'#f44336' if disk > AlertRule.DISK_CRITICAL else '#ff9800'};">
                        {'CRITICAL' if disk > AlertRule.DISK_CRITICAL else 'WARNING'}
                    </td>
                </tr>
            </table>

            <p style="margin-top: 20px;">
                <strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                <strong>Action Required:</strong> Investigate immediately
            </p>

            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This is an automated alert from VM Monitor.<br>
                Dashboard: <a href="https://your-server.example.com">https://your-server.example.com</a>
            </p>
        </body>
        </html>
        """

        self.email.send_email(email_subject, email_body, severity='critical')

        # Slack
        slack_title = f"🚨 CRITICAL: {hostname}"
        slack_message = f"VM has exceeded critical resource thresholds"
        slack_fields = [
            {"title": "CPU", "value": f"{cpu:.1f}%", "short": True},
            {"title": "Memory", "value": f"{memory:.1f}%", "short": True},
            {"title": "Disk", "value": f"{disk:.1f}%", "short": True},
            {"title": "Time", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "short": True}
        ]

        self.slack.send_slack(slack_title, slack_message, severity='critical', fields=slack_fields)

        self._record_alert(alert_key)
        logger.info(f"✓ Critical alert sent for {hostname}")

    async def send_vm_offline_alert(self, hostname: str, last_seen: datetime):
        """Send alert when VM goes offline"""
        alert_key = f"vm_offline_{hostname}"
        if not self._should_send_alert(alert_key):
            return

        offline_duration = datetime.now() - last_seen

        # Email
        email_subject = f"⚠️ VM Offline: {hostname}"
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #ff9800;">⚠️ VM Offline Alert</h2>
            <p><strong>{hostname}</strong> has not reported metrics recently.</p>

            <table style="margin: 20px 0;">
                <tr><td><strong>Last Seen:</strong></td><td>{last_seen.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                <tr><td><strong>Offline Duration:</strong></td><td>{int(offline_duration.total_seconds() / 60)} minutes</td></tr>
                <tr><td><strong>Alert Time:</strong></td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            </table>

            <p><strong>Possible Causes:</strong></p>
            <ul>
                <li>VM shutdown or rebooted</li>
                <li>Telegraf agent stopped</li>
                <li>Network connectivity issue</li>
                <li>System crash</li>
            </ul>
        </body>
        </html>
        """

        self.email.send_email(email_subject, email_body, severity='warning')

        # Slack
        slack_title = f"⚠️ VM Offline: {hostname}"
        slack_message = f"No metrics received for {int(offline_duration.total_seconds() / 60)} minutes"
        slack_fields = [
            {"title": "Last Seen", "value": last_seen.strftime('%Y-%m-%d %H:%M:%S'), "short": False}
        ]

        self.slack.send_slack(slack_title, slack_message, severity='warning', fields=slack_fields)

        self._record_alert(alert_key)
        logger.info(f"✓ Offline alert sent for {hostname}")

    async def send_cve_alert(self, hostname: str, cve_data: Dict):
        """Send alert for critical CVE vulnerabilities"""
        critical_count = cve_data.get('critical', 0)
        high_count = cve_data.get('high', 0)

        if critical_count < AlertRule.CVE_CRITICAL_COUNT and high_count < AlertRule.CVE_HIGH_COUNT:
            return

        alert_key = f"cve_{hostname}"
        if not self._should_send_alert(alert_key):
            return

        # Email
        email_subject = f"🛡️ Security Alert: {hostname} - Critical CVEs Detected"
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #f44336;">🛡️ Security Vulnerability Alert</h2>
            <p><strong>{hostname}</strong> has critical security vulnerabilities:</p>

            <table style="border-collapse: collapse; margin: 20px 0;">
                <tr style="background: #f44336; color: white;">
                    <th style="padding: 10px;">Severity</th>
                    <th style="padding: 10px;">Count</th>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;">Critical (CVSS ≥ 9.0)</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold; color: #f44336;">{critical_count}</td>
                </tr>
                <tr style="background: #f5f5f5;">
                    <td style="padding: 10px; border: 1px solid #ddd;">High (CVSS 7.0-8.9)</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold; color: #ff9800;">{high_count}</td>
                </tr>
            </table>

            <p><strong>Action Required:</strong></p>
            <ul>
                <li>Review vulnerabilities in VM Monitor dashboard</li>
                <li>Apply security patches immediately</li>
                <li>Update affected packages</li>
            </ul>
        </body>
        </html>
        """

        self.email.send_email(email_subject, email_body, severity='critical')

        # Slack
        slack_title = f"🛡️ Security Alert: {hostname}"
        slack_message = f"Critical CVE vulnerabilities detected"
        slack_fields = [
            {"title": "Critical CVEs", "value": str(critical_count), "short": True},
            {"title": "High CVEs", "value": str(high_count), "short": True}
        ]

        self.slack.send_slack(slack_title, slack_message, severity='critical', fields=slack_fields)

        self._record_alert(alert_key)
        logger.info(f"✓ CVE alert sent for {hostname}")

    async def send_system_startup_alert(self):
        """Send notification when VM Monitor starts"""
        # Slack only for system events
        self.slack.send_slack(
            title="✅ VM Monitor Started",
            message="Monitoring system is now online",
            severity='info'
        )

        logger.info("✓ System startup notification sent")


# Global notification service instance
notification_service = NotificationService()


# Helper functions for easy access
async def alert_vm_critical(vm_data: Dict):
    """Send critical VM alert"""
    await notification_service.send_vm_critical_alert(vm_data)


async def alert_vm_offline(hostname: str, last_seen: datetime):
    """Send VM offline alert"""
    await notification_service.send_vm_offline_alert(hostname, last_seen)


async def alert_cve_detected(hostname: str, cve_data: Dict):
    """Send CVE detection alert"""
    await notification_service.send_cve_alert(hostname, cve_data)


async def alert_system_startup():
    """Send system startup notification"""
    await notification_service.send_system_startup_alert()
