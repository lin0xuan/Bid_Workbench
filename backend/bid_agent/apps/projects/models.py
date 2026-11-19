"""Project rows in the shared business database."""
from django.db import models


class Project(models.Model):
    """One bidding project and its analysis header."""

    id = models.TextField(primary_key=True)
    project_name = models.TextField(null=True, blank=True)
    project_code = models.TextField(null=True, blank=True)
    project_category = models.TextField(null=True, blank=True)
    buyer_name = models.TextField(null=True, blank=True)
    agency_name = models.TextField(null=True, blank=True)
    budget_amount = models.FloatField(null=True, blank=True)
    status = models.TextField(null=True, blank=True)
    created_at = models.TextField()
    updated_at = models.TextField()

    class Meta:
        managed = False
        db_table = 'projects'
        verbose_name = '项目'
        verbose_name_plural = '项目'

    def __str__(self):
        return self.project_name or self.id
