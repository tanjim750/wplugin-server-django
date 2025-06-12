from django.contrib import admin
from app.models import License, FacebookEvent

# Register your models here.
admin.site.register([License,FacebookEvent])