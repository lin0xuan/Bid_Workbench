"""Knowledge entries stored beside the analysis tables."""
from django.db import models


class KnowledgeEntry(models.Model):
    """One reusable fact, qualification, or material note."""

    id = models.TextField(primary_key=True)
    type = models.TextField()
    title = models.TextField()
    tags = models.TextField(blank=True)
    date_text = models.TextField(blank=True)
    files = models.TextField(blank=True)
    content = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.TextField()
    updated_at = models.TextField()

    class Meta:
        managed = False
        db_table = 'knowledge_entries'
        verbose_name = '知识条目'
        verbose_name_plural = '知识条目'

    def __str__(self):
        return self.title
