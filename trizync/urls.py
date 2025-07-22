from django.urls import path

from rest_framework_simplejwt.views import TokenVerifyView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from trizync.views import *

urlpatterns = [
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/dashboard/',DashBoard.as_view(),name='dashboard'),
    path('api/clients/', ClientView.as_view(), name='client-list-create'),
    path('api/clients/<int:pk>/', ClientView.as_view(), name='client-detail'),
    path('api/services/', ServiceView.as_view(), name='service-list-create'),
    path('api/services/<int:pk>/', ServiceView.as_view(), name='service-detail'),
    path('api/projects/', ProjectView.as_view(), name='project-list-create'),
    path('api/projects/<int:pk>/', ProjectView.as_view(), name='project-detail'),
    path('api/expenses/', ProjectExpanseView.as_view(), name='project-expense-list-create'),
    path('api/expenses/<int:pk>/', ProjectExpanseView.as_view(), name='project-expense-detail'),
    path('api/payments/', ProjectPaymentView.as_view(), name='project-payment-list-create'),
    path('api/payments/<int:pk>/', ProjectPaymentView.as_view(), name='project-payment-detail'),
]
