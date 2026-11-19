"""Document application configuration."""
from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    """Uploaded originals and their immutable versions."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bid_agent.apps.documents'
    label = 'documents'
    verbose_name = '文档'
