"""Saved outlines and section drafts."""
from django.db import models


class BidVersion(models.Model):
    """One generated outline for a project."""

    id = models.TextField(primary_key=True)
    project_id = models.TextField()
    document_version_id = models.TextField(null=True, blank=True)
    title = models.TextField()
    outline_markdown = models.TextField()
    outline_json = models.TextField()
    score_coverage_json = models.TextField()
    created_by = models.TextField()
    created_at = models.TextField()

    class Meta:
        managed = False
        db_table = 'bid_versions'
        verbose_name = '标书版本'
        verbose_name_plural = '标书版本'

    def __str__(self):
        return self.title


class BidSection(models.Model):
    """One section body inside a bid version."""

    id = models.TextField(primary_key=True)
    bid_version_id = models.TextField()
    section_key = models.TextField()
    title = models.TextField()
    level = models.IntegerField()
    sort_order = models.IntegerField()
    body_markdown = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = 'bid_sections'
        verbose_name = '章节'
        verbose_name_plural = '章节'

    def __str__(self):
        return self.title
