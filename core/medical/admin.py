from django.contrib import admin

# Register your models here.
from .models import Clinic , ClinicUser
admin.site.register(Clinic)
admin.site.register(ClinicUser)
