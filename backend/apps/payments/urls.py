from django.urls import path
from .views import WeChatPaymentNotifyView
urlpatterns = [path('wechat/notify/', WeChatPaymentNotifyView.as_view())]
