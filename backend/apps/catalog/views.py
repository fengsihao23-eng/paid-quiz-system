from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import QuizProduct
from .serializers import QuizProductSerializer


class QuizProductViewSet(viewsets.ReadOnlyModelViewSet):
    """商品视图集"""
    queryset = QuizProduct.objects.filter(status='published')
    serializer_class = QuizProductSerializer
    lookup_field = 'slug'

    def list(self, request, *args, **kwargs):
        """获取商品列表"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """获取单个商品详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
