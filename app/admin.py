from django.contrib import admin
from app.models import *

# Register your models here.
admin.site.register([License,FacebookEvent,Customer,MessengerUser,UserWebsite,UserMessage])