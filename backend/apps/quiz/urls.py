from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QuizAttemptViewSet, StartAttemptView, ResultView
router = DefaultRouter()
router.register('attempts', QuizAttemptViewSet, basename='attempt')
urlpatterns = [path('grants/<int:grant_id>/start/', StartAttemptView.as_view()),
               path('results/<uuid:attempt_id>/', ResultView.as_view()),
               path('results/<uuid:attempt_id>/<str:result_type>/', ResultView.as_view()),
               path('', include(router.urls))]
