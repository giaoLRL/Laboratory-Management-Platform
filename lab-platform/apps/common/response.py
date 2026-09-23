from rest_framework.response import Response


def ok(data=None, status=200):
    """成功响应：{"data": ...}；无数据时返回 {"data":{"ok":true}}（契约不允许空 204）。"""
    return Response({'data': data if data is not None else {'ok': True}}, status=status)


def fail(message, status=400):
    """失败响应：{"message": 可展示给用户的说明}。"""
    return Response({'message': message}, status=status)
