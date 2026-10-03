from rest_framework.exceptions import APIException

class Conflict(APIException):
    status_code = 409
    default_detail = '状态已变化，请刷新后重试'
    default_code = 'conflict'
