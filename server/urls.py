"""
URL configuration for server project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path,include
from django.contrib import admin
from app.views import *

from django.conf import settings
from django.conf.urls.static import static

from trizync.urls import urlpatterns as trizync_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('verify-license/', verify_license),
    path('new-key/',GenerateKey.as_view()),
    path('create-parcel/',CreateParcel.as_view()),
    path('track-parcel/',TrackParcel.as_view()),
    path('fraud-check/',FraudCheck.as_view()),
    path('send-event/',TriggerFbEventView.as_view()),
    path('fb-graph/',FacebookGraphAPI.as_view()),
    path('get-events/',GetAllFacebookEvents.as_view()),
    path('',include('trizync.urls')),
]

urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)