from django.db import models
from django.utils import timezone

class License(models.Model):
    customer_name = models.CharField(max_length=255)
    key = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    domain = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True
    
    def __str__(self):
        return self.domain

class PathaoCredential(models.Model):
    client_id = models.CharField(max_length=100)

    access_token = models.TextField(null=True, blank=True)
    token_expiry_at = models.DateTimeField(null=True, blank=True)

    def is_token_valid(self):
        return self.access_token and self.token_expiry_at and self.token_expiry_at > timezone.now()
    

class FacebookEvent(models.Model):
    text = models.CharField(max_length=255, unique=True)
    event_name = models.CharField(max_length=255)

    def __str__(self):
        return self.text
