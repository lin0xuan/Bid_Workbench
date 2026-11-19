"""Account application configuration."""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Read-only view of workspace users."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bid_agent.apps.accounts'
    label = 'accounts'
    verbose_name = '账号'
