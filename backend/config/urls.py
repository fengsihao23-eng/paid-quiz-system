from django.contrib import admin
from django.urls import path, include
from config.views import SessionView, HealthView
from apps.operations.views import ExchangeTicketView
urlpatterns = [path('admin/', admin.site.urls), path('api/session/', SessionView.as_view()),
    path('api/health/', HealthView.as_view()), path('api/continue/exchange/', ExchangeTicketView.as_view()),
    path('api/products/', include('apps.catalog.urls')), path('api/orders/', include('apps.checkout.urls')),
    path('api/payments/', include('apps.payments.urls')), path('api/access/', include('apps.access.urls')),
    path('api/quiz/', include('apps.quiz.urls'))]
