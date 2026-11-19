"""Document catalog. Object keys are not shown in maintenance screens."""
from django.db import models


class Document(models.Model):
    """A logical document inside a project."""

    id = models.TextField(primary_key=True)
    project_id = models.TextField()
    title = models.TextField()
    kind = models.TextField()
    parent_document_id = models.TextField(null=True, blank=True)
    created_at = models.TextField()

    class Meta:
        managed = False
        db_table = 'documents'
        verbose_name = '文档'
        verbose_name_plural = '文档'

    def __str__(self):
        return self.title


class DocumentVersion(models.Model):
    """One immutable upload of a document."""

    id = models.TextField(primary_key=True)
    document_id = models.TextField()
    version = models.IntegerField()
    file_name = models.TextField()
    media_type = models.TextField()
    object_key = models.TextField()
    sha256 = models.TextField()
    size_bytes = models.IntegerField()
    created_by = models.TextField()
    created_at = models.TextField()

    class Meta:
        managed = False
        db_table = 'document_versions'
        verbose_name = '文档版本'
        verbose_name_plural = '文档版本'

    def __str__(self):
        return f'{self.file_name} v{self.version}'
