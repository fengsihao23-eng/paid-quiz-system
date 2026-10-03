from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.http import Http404
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    自定义异常处理器，统一API错误响应格式
    """
    # 先调用DRF默认的异常处理
    response = exception_handler(exc, context)

    if response is not None:
        # DRF已处理的异常
        error_data = {
            'error': get_error_message(response.data),
            'code': get_error_code(exc),
        }

        # 添加详细信息（仅在DEBUG模式）
        from django.conf import settings
        if settings.DEBUG and hasattr(exc, 'detail'):
            error_data['detail'] = str(exc.detail)

        response.data = error_data
        return response

    # 处理Django原生异常
    if isinstance(exc, Http404):
        return Response({
            'error': '资源未找到',
            'code': 'not_found',
        }, status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, ValidationError):
        return Response({
            'error': '数据验证失败',
            'detail': str(exc),
            'code': 'validation_error',
        }, status=status.HTTP_400_BAD_REQUEST)

    # 未处理的异常，记录日志
    logger.error(f'Unhandled exception: {exc}', exc_info=True)

    return Response({
        'error': '服务器内部错误',
        'code': 'internal_error',
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_error_message(data):
    """从DRF错误数据中提取主要错误消息"""
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        # 获取第一个字段的错误
        for key, value in data.items():
            if isinstance(value, list) and value:
                return f'{key}: {value[0]}'
            return f'{key}: {value}'
    elif isinstance(data, list) and data:
        return str(data[0])
    return str(data)


def get_error_code(exc):
    """根据异常类型返回错误代码"""
    exc_class = exc.__class__.__name__
    code_map = {
        'NotAuthenticated': 'not_authenticated',
        'AuthenticationFailed': 'authentication_failed',
        'PermissionDenied': 'permission_denied',
        'NotFound': 'not_found',
        'ValidationError': 'validation_error',
        'ParseError': 'parse_error',
        'MethodNotAllowed': 'method_not_allowed',
        'Throttled': 'throttled',
    }
    return code_map.get(exc_class, 'error')
