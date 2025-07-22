from django.contrib import admin
from trizync.models import *

# Register your models here.
admin.site.register([Account,Client,Service,Project,ProjectExpanse,ProjectPayment,Transaction])