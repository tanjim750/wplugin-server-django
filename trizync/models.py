from django.db import models
from django.utils import timezone

# Create your models here.
# class Account(models.model):

class Account(models.Model):
    name = models.CharField(max_length=100)
    is_general = models.BooleanField(default=False)
    percentage = models.FloatField(default=0.0)  # used only for non-general accounts
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)

    def save(self, *args, **kwargs):
        if not self.pk:  # Only applies on creation
            if not Account.objects.filter(is_general=True).exists():
                self.is_general = True  # First account becomes general
        elif self.is_general:
            # Unset general from all others if this is marked as general
            Account.objects.exclude(pk=self.pk).update(is_general=False)

        super().save(*args, **kwargs)

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('IN', 'Cash In'),
        ('OUT', 'Cash Out'),
        ('TRANSFER', 'Transfer'),
    )
    from_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name='outgoing_transactions')
    to_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='incoming_transactions')
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    purpose = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class Client(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    website = models.CharField(max_length=255,blank=True,null=True)
    page = models.CharField(max_length=255,blank=True,null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class Service(models.Model):
    title =  models.CharField(max_length=255)
    created_at = models.DateField(auto_now_add=True)
    def __str__(self):
        return self.title


class Project(models.Model):
    client = models.ForeignKey(Client,null=True, on_delete=models.SET_NULL)
    service = models.ForeignKey(Service,null=True, on_delete=models.SET_NULL)
    budget = models.FloatField(default=0)
    start_date = models.DateField()
    deadline = models.DateField()
    is_completed = models.BooleanField(default=False)
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.service.title

class ProjectExpanse(models.Model):
    amount = models.FloatField(default=0)
    project = models.ForeignKey(Project,null=True, on_delete=models.SET_NULL)
    trans_id = models.CharField(max_length=255)
    details = models.TextField(blank=True,null=True)
    is_edited = models.BooleanField(default=False)
    date = models.DateField()
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        if self.project and self.project.client and self.project.service:
            return f"{self.project.client.name}:{self.project.service.title}->{self.amount}"
        else:
            return f"{self.amount}"

class ProjectPayment(models.Model):
    amount = models.FloatField(default=0)
    project = models.ForeignKey(Project,null=True, on_delete=models.SET_NULL)
    trans_id = models.CharField(max_length=255)
    details = models.TextField(blank=True,null=True)
    is_edited = models.BooleanField(default=False)
    date = models.DateField()
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount}"
