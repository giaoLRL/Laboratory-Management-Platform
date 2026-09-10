"""界面层自定义模板标签：查询串拼装、库存水位分级、时间线排序等。"""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def lm_qs(context, **kwargs):
    """在当前查询串基础上覆盖参数，返回 `?a=1&b=2`（用于分页/筛选链接保留条件）。

    用法：<a href="{% lm_qs page=2 %}">下一页</a>
          <a href="{% lm_qs page=None %}">清除页码</a>
    """
    request = context.get('request')
    params = request.GET.copy() if request is not None else template.Variable('request')
    if hasattr(params, 'copy'):
        for key, value in kwargs.items():
            if value is None:
                params.pop(key, None)
            else:
                params[key] = value
        encoded = params.urlencode()
        return f'?{encoded}' if encoded else '?'
    return '?'


@register.filter
def lm_pct(value, total):
    """百分比（0–100 整数，除零安全）。"""
    try:
        total = float(total)
        if total <= 0:
            return 0
        return int(round(float(value) / total * 100))
    except (TypeError, ValueError):
        return 0


@register.simple_tag
def lm_stock_level(available, total, minimum=0):
    """库存水位等级：ok / warning / danger。"""
    try:
        available = int(available)
        total = int(total)
        minimum = int(minimum or 0)
    except (TypeError, ValueError):
        return 'ok'
    if available <= 0:
        return 'danger'
    if minimum and available <= minimum:
        return 'warning'
    if total and available / total <= 0.25:
        return 'warning'
    return 'ok'


@register.simple_tag
def lm_stock_width(available, total):
    """水位条宽度百分比（1–100）。"""
    try:
        available = int(available)
        total = int(total)
    except (TypeError, ValueError):
        return 0
    if total <= 0:
        return 100 if available > 0 else 0
    return max(2, min(100, int(round(available / total * 100))))
