from django.urls import path
from .views import MyTokenObtainPairView, register, admin_approve, admin_topup_pool, me, create_withdrawal
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('auth/register', register),
    path('auth/token', MyTokenObtainPairView.as_view()),
    path('auth/token/refresh', TokenRefreshView.as_view()),
    path('admin/approve', admin_approve),
    path('admin/pool/topup', admin_topup_pool),
    path('me', me),
    path('withdrawals', create_withdrawal),
]
