from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QuizProductViewSet

router = DefaultRouter()
router.register('', QuizProductViewSet, basename='product')

urlpatterns = [
    path('', include(router.urls)),
]
