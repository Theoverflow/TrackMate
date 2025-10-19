"""Alerting system with configurable thresholds and notifications."""
import os
import json
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import httpx

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertState(str, Enum):
    """Alert state."""
    FIRING = "firing"
    RESOLVED = "resolved"


@dataclass
class Alert:
    """Alert instance."""
    name: str
    severity: AlertSeverity
    state: AlertState
    message: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    started_at: datetime
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'severity': self.severity.value,
            'state': self.state.value,
            'message': self.message,
            'labels': self.labels,
            'annotations': self.annotations,
            'started_at': self.started_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    severity: AlertSeverity
    message_template: str
    labels: Optional[Dict[str, str]] = None
    cooldown_minutes: int = 5


class AlertManager:
    """
    Alert manager for monitoring system.
    
    Features:
    - Configurable alert rules
    - Multiple notification channels (webhook, email, Slack)
    - Alert cooldown to prevent spam
    - Alert history tracking
    """
    
    def __init__(self):
        """Initialize alert manager."""
        self.rules: List[AlertRule] = []
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.webhook_url: Optional[str] = os.getenv('ALERT_WEBHOOK_URL')
        self.slack_webhook: Optional[str] = os.getenv('SLACK_WEBHOOK_URL')
        self.email_api: Optional[str] = os.getenv('EMAIL_API_URL')
        
        # Initialize default rules
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Setup default alerting rules."""
        # High failure rate
        self.add_rule(AlertRule(
            name='high_failure_rate',
            condition=lambda metrics: (
                metrics.get('failed_jobs', 0) / max(metrics.get('total_jobs', 1), 1) > 0.1
            ),
            severity=AlertSeverity.ERROR,
            message_template='High job failure rate: {failed_jobs}/{total_jobs} ({rate:.1f}%)',
            labels={'category': 'reliability'},
            cooldown_minutes=15
        ))
        
        # Long running jobs
        self.add_rule(AlertRule(
            name='long_running_job',
            condition=lambda metrics: metrics.get('max_duration_s', 0) > 3600,
            severity=AlertSeverity.WARNING,
            message_template='Job running for {max_duration_s:.0f}s (>1h)',
            labels={'category': 'performance'},
            cooldown_minutes=30
        ))
        
        # High memory usage
        self.add_rule(AlertRule(
            name='high_memory_usage',
            condition=lambda metrics: metrics.get('max_memory_mb', 0) > 8192,
            severity=AlertSeverity.WARNING,
            message_template='High memory usage: {max_memory_mb:.0f}MB',
            labels={'category': 'resources'},
            cooldown_minutes=10
        ))
        
        # No jobs received
        self.add_rule(AlertRule(
            name='no_jobs_received',
            condition=lambda metrics: (
                metrics.get('jobs_last_hour', 0) == 0 and
                metrics.get('expected_jobs_per_hour', 0) > 0
            ),
            severity=AlertSeverity.WARNING,
            message_template='No jobs received in the last hour (expected {expected_jobs_per_hour})',
            labels={'category': 'availability'},
            cooldown_minutes=60
        ))
        
        # Event ingestion lag
        self.add_rule(AlertRule(
            name='ingestion_lag',
            condition=lambda metrics: metrics.get('spool_count', 0) > 100,
            severity=AlertSeverity.ERROR,
            message_template='Event ingestion lag: {spool_count} events in spool',
            labels={'category': 'reliability'},
            cooldown_minutes=5
        ))
        
        # Database connection issues
        self.add_rule(AlertRule(
            name='database_connection_failed',
            condition=lambda metrics: metrics.get('db_connection_failed', False),
            severity=AlertSeverity.CRITICAL,
            message_template='Database connection failed',
            labels={'category': 'infrastructure'},
            cooldown_minutes=2
        ))
    
    def add_rule(self, rule: AlertRule) -> None:
        """
        Add an alert rule.
        
        Args:
            rule: Alert rule to add
        """
        self.rules.append(rule)
        logger.info("alert_rule_added", rule_name=rule.name, severity=rule.severity)
    
    def check_rules(self, metrics: Dict[str, Any]) -> List[Alert]:
        """
        Check all rules against current metrics.
        
        Args:
            metrics: Current system metrics
            
        Returns:
            List of new alerts
        """
        new_alerts = []
        now = datetime.utcnow()
        
        for rule in self.rules:
            try:
                # Check if condition is met
                if rule.condition(metrics):
                    # Check cooldown
                    if rule.name in self.active_alerts:
                        alert = self.active_alerts[rule.name]
                        if (now - alert.started_at).total_seconds() < rule.cooldown_minutes * 60:
                            continue  # Still in cooldown
                    
                    # Create alert
                    message = rule.message_template.format(**metrics)
                    
                    alert = Alert(
                        name=rule.name,
                        severity=rule.severity,
                        state=AlertState.FIRING,
                        message=message,
                        labels=rule.labels or {},
                        annotations={'metrics': json.dumps(metrics)},
                        started_at=now
                    )
                    
                    self.active_alerts[rule.name] = alert
                    new_alerts.append(alert)
                    
                    logger.warning(
                        "alert_triggered",
                        alert_name=rule.name,
                        severity=rule.severity,
                        message=message
                    )
                
                else:
                    # Resolve alert if it was active
                    if rule.name in self.active_alerts:
                        alert = self.active_alerts[rule.name]
                        alert.state = AlertState.RESOLVED
                        alert.resolved_at = now
                        
                        self.alert_history.append(alert)
                        del self.active_alerts[rule.name]
                        
                        logger.info(
                            "alert_resolved",
                            alert_name=rule.name,
                            duration_s=(now - alert.started_at).total_seconds()
                        )
            
            except Exception as e:
                logger.error(
                    "alert_rule_check_failed",
                    rule_name=rule.name,
                    error=str(e)
                )
        
        return new_alerts
    
    async def send_alert(self, alert: Alert) -> None:
        """
        Send alert to configured notification channels.
        
        Args:
            alert: Alert to send
        """
        # Send to webhook
        if self.webhook_url:
            await self._send_webhook(alert)
        
        # Send to Slack
        if self.slack_webhook:
            await self._send_slack(alert)
        
        # Send email
        if self.email_api:
            await self._send_email(alert)
    
    async def _send_webhook(self, alert: Alert) -> None:
        """Send alert via webhook."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    self.webhook_url,
                    json=alert.to_dict(),
                    timeout=5.0
                )
            logger.info("alert_sent_webhook", alert_name=alert.name)
        except Exception as e:
            logger.error("webhook_send_failed", error=str(e))
    
    async def _send_slack(self, alert: Alert) -> None:
        """Send alert to Slack."""
        try:
            # Format Slack message
            color = {
                AlertSeverity.INFO: '#36a64f',
                AlertSeverity.WARNING: '#ff9900',
                AlertSeverity.ERROR: '#ff0000',
                AlertSeverity.CRITICAL: '#8b0000'
            }.get(alert.severity, '#808080')
            
            payload = {
                'attachments': [{
                    'color': color,
                    'title': f"🚨 Alert: {alert.name}",
                    'text': alert.message,
                    'fields': [
                        {'title': 'Severity', 'value': alert.severity.value.upper(), 'short': True},
                        {'title': 'State', 'value': alert.state.value.upper(), 'short': True},
                        {'title': 'Time', 'value': alert.started_at.strftime('%Y-%m-%d %H:%M:%S UTC'), 'short': False}
                    ],
                    'footer': 'Wafer Monitor Alert System'
                }]
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(
                    self.slack_webhook,
                    json=payload,
                    timeout=5.0
                )
            logger.info("alert_sent_slack", alert_name=alert.name)
        except Exception as e:
            logger.error("slack_send_failed", error=str(e))
    
    async def _send_email(self, alert: Alert) -> None:
        """Send alert via email."""
        try:
            payload = {
                'subject': f"Alert: {alert.name} ({alert.severity.value.upper()})",
                'body': alert.message,
                'severity': alert.severity.value,
                'alert': alert.to_dict()
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(
                    self.email_api,
                    json=payload,
                    timeout=5.0
                )
            logger.info("alert_sent_email", alert_name=alert.name)
        except Exception as e:
            logger.error("email_send_failed", error=str(e))
    
    def get_active_alerts(self) -> List[Alert]:
        """Get list of active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """
        Get alert history.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of historical alerts
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [a for a in self.alert_history if a.started_at >= cutoff]


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the global alert manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager

