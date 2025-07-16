from django.db import models

# Create your models here.
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

    def __str__(self):
        return self.title


class Project(models.Model):
    client = models.ForeignKey(Client,null=True, on_delete=models.SET_NULL)
    service = models.ForeignKey(Service,null=True, on_delete=models.SET_NULL)
    budget = models.FloatField(default=0)
    start_date = models.DateField()
    deadline = models.DateField()
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.service.title

class ProjectExpanse(models.Model):
    amount = models.FloatField(default=0)
    project = models.ForeignKey(Project,null=True, on_delete=models.SET_NULL)
    trans_id = models.CharField(max_length=255)
    details = models.TextField(blank=True,null=True)
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.project.client.name}:{self.project.service.title}->{self.amount}"

class ProjectPayment(models.Model):
    amount = models.FloatField(default=0)
    project = models.ForeignKey(Project,null=True, on_delete=models.SET_NULL)
    trans_id = models.CharField(max_length=255)
    details = models.TextField(blank=True,null=True)
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.project.client.name}:{self.project.service.title}->{self.amount}"
