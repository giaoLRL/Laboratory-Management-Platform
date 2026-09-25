import re


def member_id(pk):
    return f'm{pk}'


def parse_member_id(value):
    """'m3' → 3；非法返回 None。"""
    s = str(value or '')
    if s.startswith('m') and s[1:].isdigit():
        return int(s[1:])
    return None


def next_code(model, prefix, width=3):
    """生成 prefix-001 形式的顺序编号（按数值部分取最大 +1，不依赖字典序）。"""
    pat = re.compile(r'^%s-(\d+)$' % re.escape(prefix))
    max_n = 0
    for (code,) in model.objects.filter(id__startswith=prefix + '-').values_list('id'):
        m = pat.match(code)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f'{prefix}-{max_n + 1:0{width}d}'


def create_with_code(model, prefix, width=3, **kwargs):
    """并发安全地创建带顺序编号主键的记录：next_code + create 包在事务内，
    编号撞主键冲突（IntegrityError）时重试（最多 3 次）。

    用于替代 `Model.objects.create(id=next_code(Model, 'PREFIX'), **data)`
    的裸调用——后者在并发下会生成相同编号导致 500。
    """
    from django.db import IntegrityError, transaction

    for _ in range(3):
        try:
            with transaction.atomic():
                return model.objects.create(id=next_code(model, prefix, width), **kwargs)
        except IntegrityError:
            continue
    raise IntegrityError(f'{model.__name__} 编号分配冲突（prefix={prefix}），请重试')
