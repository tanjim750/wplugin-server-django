from django.contrib import admin
from trizync.models import *

# Register your models here.
admin.site.register([Client,Service,Project,ProjectExpanse,ProjectPayment])