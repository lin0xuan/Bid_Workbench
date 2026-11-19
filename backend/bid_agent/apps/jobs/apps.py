"""Job application configuration."""
from django.apps import AppConfig


class JobsConfig(AppConfig):
    """Durable parse jobs and outbox rows."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bid_agent.apps.jobs'
    label = 'jobs'
    verbose_name = '任务'
