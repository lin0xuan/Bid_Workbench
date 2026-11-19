"""Knowledge application configuration."""
from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    """Company knowledge reused by later bid drafts."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bid_agent.apps.knowledge'
    label = 'knowledge'
    verbose_name = '知识'
