from django.urls import path
from .views import VerifyAccessCodeView, GetGrantView
urlpatterns = [path('verify/', VerifyAccessCodeView.as_view()), path('grants/<int:grant_id>/', GetGrantView.as_view())]
