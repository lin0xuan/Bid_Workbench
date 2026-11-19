"""Job and outbox rows. Lease tokens are omitted from screens."""
from django.db import models


class Job(models.Model):
    """One parse or maintenance job owned by a project."""

    id = models.TextField(primary_key=True)
    project_id = models.TextField()
    document_version_id = models.TextField()
    kind = models.TextField()
    status = models.TextField()
    options_json = models.TextField()
    idempotency_key = models.TextField()
    request_hash = models.TextField()
    attempts = models.IntegerField()
    max_attempts = models.IntegerField()
    available_at = models.FloatField()
    lease_token = models.TextField(null=True, blank=True)
    lease_expires_at = models.FloatField(null=True, blank=True)
    progress = models.IntegerField()
    stage = models.TextField()
    error_code = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    retryable = models.IntegerField()
    created_by = models.TextField()
    created_at = models.TextField()
    updated_at = models.TextField()

    class Meta:
        managed = False
        db_table = 'jobs'
        verbose_name = '任务'
        verbose_name_plural = '任务'

    def __str__(self):
        return f'{self.kind}:{self.status}'


class OutboxEvent(models.Model):
    """A committed job that still needs to be published."""

    id = models.TextField(primary_key=True)
    job_id = models.TextField()
    status = models.TextField()
    available_at = models.FloatField()
    attempts = models.IntegerField()
    lease_token = models.TextField(null=True, blank=True)
    lease_expires_at = models.FloatField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    created_at = models.TextField()
    published_at = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'outbox_events'
        verbose_name = '待发布事件'
        verbose_name_plural = '待发布事件'

    def __str__(self):
        return f'{self.job_id}:{self.status}'
