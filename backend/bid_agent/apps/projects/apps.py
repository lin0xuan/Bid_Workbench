"""Project application configuration."""
from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    """Projects shared by the workspace and the older analysis records."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bid_agent.apps.projects'
    label = 'projects'
    verbose_name = '项目'
