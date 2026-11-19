"""Users already stored by the workspace schema."""
from django.db import models


class User(models.Model):
    """Business user. Password hashes stay out of the maintenance screens."""

    id = models.TextField(primary_key=True)
    username = models.TextField(unique=True)
    password_hash = models.TextField()
    is_admin = models.IntegerField(default=0)
    created_at = models.TextField()

    class Meta:
        managed = False
        db_table = 'users'
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        return self.username
