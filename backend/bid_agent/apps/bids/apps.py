"""Bid application configuration."""
from django.apps import AppConfig


class BidsConfig(AppConfig):
    """Outline versions and editable sections."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bid_agent.apps.bids'
    label = 'bids'
    verbose_name = '标书'
