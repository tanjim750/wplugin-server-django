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


class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    address = models.CharField(max_length=255)
    items = models.JSONField(null=True,blank=True)

    def __str__(self):
        return self.name

class TrizyncService(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class MessengerUser(models.Model):
    psid = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.psid

class UserMessage(models.Model):
    user = models.ForeignKey(MessengerUser, on_delete=models.CASCADE, related_name='messages')
    text = models.TextField()
    response = models.TextField(null=True)
    received_at = models.DateTimeField(auto_now_add=True)
    intent = models.CharField(max_length=100, blank=True, null=True)  # optional

    def __str__(self):
        return f"{self.user}: {self.text[:30]}"

class UserService(models.Model):
    user = models.ForeignKey(MessengerUser, on_delete=models.CASCADE, related_name='service')
    service = models.ForeignKey(TrizyncService, on_delete=models.CASCADE)
    message = models.ForeignKey(UserMessage, on_delete=models.SET_NULL, null=True, blank=True, related_name='service_extractions')
    detected_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} → {self.service}"
    

class UserBudget(models.Model):
    user = models.ForeignKey(MessengerUser, on_delete=models.CASCADE, related_name='budgets')
    message = models.ForeignKey(UserMessage, on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_extractions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='BDT')
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} {self.currency} for {self.user}"

class UserWebsite(models.Model):
    user = models.ForeignKey(MessengerUser, on_delete=models.CASCADE, related_name='websites')
    message = models.ForeignKey(UserMessage, on_delete=models.SET_NULL, null=True, blank=True, related_name='website_extractions')
    url = models.URLField()
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.url


