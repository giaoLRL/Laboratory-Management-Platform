"""批次4 智能体链路修复。"""
import io
import os
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
report, failures = [], []


def patch(path, pairs, regex_pairs=()):
    full = os.path.join(BASE, path)
    src = io.open(full, encoding='utf-8').read()
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            failures.append(f'{path}: 期望 1 次，实际 {n} 次 -> {old.strip().splitlines()[0][:70]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {path}: {old.strip().splitlines()[0][:70]}')
    import re as _re
    for pat, new, expect in regex_pairs:
        src, n = _re.subn(pat, new, src)
        (report if n == expect else failures).append(
            f'  {"ok" if n == expect else "!!"} {path}(regex, {n}/{expect}): {pat[:60]}')
    if src != orig and APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)


# ── A. tool_registry.py ────────────────────────────────────────
patch('lab_manager/services/tool_registry.py', [
    (
        "import json\nfrom typing import Any, Callable\n",
        "import json\nimport time\nfrom typing import Any, Callable\n\n"
        "from .logging_config import logger\n",
    ),
    (
        "# ── 工具执行函数 ──────────────────────────────────────────────\n",
        "# LLM 按 AgentTool.parameters_schema 传参时用的是 filters_json / fields_json /\n"
        "# record_id，而执行层读的是 filters / fields / id。这里统一归一化，\n"
        "# 否则过滤条件会被静默丢弃，模型会把全量数据当成筛选结果。\n"
        "_ARG_ALIASES = (('filters_json', 'filters'), ('fields_json', 'fields'), ('record_id', 'id'))\n"
        "\n"
        "\n"
        "def normalize_platform_args(args: dict) -> tuple[dict, str]:\n"
        '    """返回 (归一化后的参数, 错误信息)。"""\n'
        "    if not isinstance(args, dict):\n"
        "        return {}, '工具参数必须是对象'\n"
        "    normalized = dict(args)\n"
        "    for src_key, dst_key in _ARG_ALIASES:\n"
        "        if src_key not in normalized:\n"
        "            continue\n"
        "        value = normalized.pop(src_key)\n"
        "        if isinstance(value, str):\n"
        "            text = value.strip()\n"
        "            if not text:\n"
        "                continue\n"
        "            try:\n"
        "                value = json.loads(text)\n"
        "            except json.JSONDecodeError:\n"
        "                return {}, f'{src_key} 不是合法 JSON'\n"
        "        if dst_key not in normalized and value is not None:\n"
        "            normalized[dst_key] = value\n"
        "    return normalized, ''\n"
        "\n"
        "\n"
        "# ── 工具执行函数 ──────────────────────────────────────────────\n",
    ),
    (
        "    from .platform_data_service import PlatformDataError, PlatformDataService\n"
        "    platform = PlatformDataService()\n"
        "    try:\n"
        "        result = platform.execute(user=user, payload=args)\n",
        "    from .platform_data_service import PlatformDataError, PlatformDataService\n"
        "    args, arg_error = normalize_platform_args(args)\n"
        "    if arg_error:\n"
        "        return json.dumps({'ok': False, 'error': arg_error}, ensure_ascii=False)\n"
        "    platform = PlatformDataService()\n"
        "    try:\n"
        "        result = platform.execute(user=user, payload=args)\n",
    ),
    (
        'def _exec_find_members(user, args: dict) -> str:\n'
        '    """搜索平台成员"""\n'
        "    keyword = str(args.get('keyword', '')).strip()\n"
        "    User = get_user_model()\n"
        "    if not keyword:\n"
        "        members = list(User.objects.values('id', 'username', 'email', 'is_active', 'is_superuser')[:20])\n"
        "    else:\n"
        "        members = list(\n"
        "            User.objects.filter(\n"
        "                Q(username__icontains=keyword) | Q(email__icontains=keyword)\n"
        "            ).values('id', 'username', 'email', 'is_active', 'is_superuser')[:20]\n"
        "        )\n"
        "    return json.dumps({'ok': True, 'members': members, 'total': len(members)}, ensure_ascii=False, default=str)\n",
        'def _exec_find_members(user, args: dict) -> str:\n'
        '    """搜索平台成员（只返回启用账号；邮箱仅管理员可见）"""\n'
        "    keyword = str(args.get('keyword', '')).strip()\n"
        "    User = get_user_model()\n"
        "    queryset = User.objects.filter(is_active=True)\n"
        "    if keyword:\n"
        "        queryset = queryset.filter(\n"
        "            Q(username__icontains=keyword) | Q(email__icontains=keyword)\n"
        "            | Q(first_name__icontains=keyword) | Q(last_name__icontains=keyword)\n"
        "        )\n"
        "    fields = ('id', 'username', 'email') if user.is_superuser else ('id', 'username')\n"
        "    members = list(queryset.values(*fields).order_by('username')[:20])\n"
        "    return json.dumps({'ok': True, 'members': members, 'total': len(members)},\n"
        "                      ensure_ascii=False, default=str)\n",
    ),
    (
        'def execute_tool(execution_key: str, user, args: dict[str, Any]) -> str:\n'
        '    """根据执行标识调用对应的工具处理函数。"""\n'
        "    handler = TOOL_REGISTRY.get(execution_key)\n"
        "    if handler is None:\n"
        "        return json.dumps(\n"
        "            {'ok': False, 'error': f'未知工具执行标识: {execution_key}'},\n"
        "            ensure_ascii=False,\n"
        "        )\n"
        "    try:\n"
        "        return handler(user, args)\n"
        "    except Exception as exc:\n"
        "        return json.dumps(\n"
        "            {'ok': False, 'error': f'工具执行异常: {exc}'},\n"
        "            ensure_ascii=False,\n"
        "        )\n",
        'def tool_requires_superuser(execution_key: str) -> bool:\n'
        '    """从数据库读取该执行标识是否要求超级管理员（LangChain 与降级路径统一生效）。"""\n'
        "    try:\n"
        "        from ..models import AgentTool\n"
        "        return bool(\n"
        "            AgentTool.objects.filter(is_enabled=True).filter(\n"
        "                Q(execution_key=execution_key) | Q(execution_key='', name=execution_key)\n"
        "            ).values_list('requires_superuser', flat=True).first()\n"
        "        )\n"
        "    except Exception:  # noqa: BLE001\n"
        "        return False\n"
        "\n"
        "\n"
        'def execute_tool(execution_key: str, user, args: dict[str, Any]) -> str:\n'
        '    """根据执行标识调用对应的工具处理函数。"""\n'
        "    handler = TOOL_REGISTRY.get(execution_key)\n"
        "    if handler is None:\n"
        "        return json.dumps(\n"
        "            {'ok': False, 'error': f'未知工具执行标识: {execution_key}'},\n"
        "            ensure_ascii=False,\n"
        "        )\n"
        "    if tool_requires_superuser(execution_key) and not getattr(user, 'is_superuser', False):\n"
        "        return json.dumps(\n"
        "            {'ok': False, 'error': '该工具仅限管理员使用'},\n"
        "            ensure_ascii=False,\n"
        "        )\n"
        "    started = time.monotonic()\n"
        "    try:\n"
        "        result = handler(user, args)\n"
        "        elapsed = time.monotonic() - started\n"
        "        if elapsed > 10:\n"
        "            logger.warning('工具 %s 执行耗时 %.1fs', execution_key, elapsed)\n"
        "        return result\n"
        "    except Exception as exc:\n"
        "        logger.exception('工具 %s 执行异常', execution_key)\n"
        "        return json.dumps(\n"
        "            {'ok': False, 'error': f'工具执行异常: {exc}'},\n"
        "            ensure_ascii=False,\n"
        "        )\n",
    ),
])

# ── B. platform_data_service.py：过滤条件非法不再 500 ───────────
patch('lab_manager/services/platform_data_service.py', [
    (
        "            coerced = self._coerce_filter_value(value, field.kind, lookup)\n"
        "            if lookup == 'ne':\n"
        "                queryset = queryset.exclude(**{path: coerced})\n"
        "            else:\n"
        "                queryset = queryset.filter(**{f'{path}{lookup_suffix}': coerced})\n",
        "            try:\n"
        "                coerced = self._coerce_filter_value(value, field.kind, lookup)\n"
        "                if lookup == 'ne':\n"
        "                    queryset = queryset.exclude(**{path: coerced})\n"
        "                else:\n"
        "                    queryset = queryset.filter(**{f'{path}{lookup_suffix}': coerced})\n"
        "            except PlatformDataError:\n"
        "                raise\n"
        "            except Exception as exc:  # noqa: BLE001\n"
        "                # Django 的 ValidationError/FieldError 在这里统一转成业务异常，\n"
        "                # 否则非法日期/数字会让接口直接 500\n"
        "                raise PlatformDataError(f'过滤条件不合法: {raw_key}={value!r}') from exc\n",
    ),
    (
        "        if kind in {'date', 'datetime'} and isinstance(value, str):\n"
        "            return parse_datetime(value) or parse_date(value) or value\n",
        "        if kind in {'date', 'datetime'} and isinstance(value, str):\n"
        "            parsed = parse_datetime(value) or parse_date(value)\n"
        "            if parsed is None:\n"
        "                raise PlatformDataError(f'日期格式不合法: {value!r}')\n"
        "            return parsed\n",
    ),
])

# ── C. agent_api.py ────────────────────────────────────────────
patch('lab_manager/agent_api.py', [
    (
        "        for item in requirements:\n            name = str(item.get('name', '')).strip()\n",
        "        for item in requirements:\n"
        "            if not isinstance(item, dict):\n"
        "                return self.error_response(\n"
        "                    'requirements 的元素必须是对象', code='40003', status=400\n"
        "                )\n"
        "            name = str(item.get('name', '')).strip()\n",
    ),
    (
        "class CommitHardwareImportAPIView(AgentAPIView):\n",
        "class _ImportAborted(Exception):\n"
        '    """导入批次中存在非法数据，整批回滚。"""\n'
        "\n"
        "\n"
        "def _validate_import_item(item) -> str:\n"
        '    """校验单条导入数据，返回错误信息（合法时为空字符串）。"""\n'
        "    if not isinstance(item, dict):\n"
        "        return '数据项必须是对象'\n"
        "    name = str(item.get('name') or '').strip()\n"
        "    if not name:\n"
        "        return 'name 不能为空'\n"
        "    if len(name) > 200:\n"
        "        return 'name 超过 200 字符'\n"
        "    category_values = {c[0] for c in Hardware._meta.get_field('category').choices}\n"
        "    status_values = {c[0] for c in Hardware._meta.get_field('status').choices}\n"
        "    if item.get('category') not in category_values:\n"
        "        return f\"category 不合法: {item.get('category')!r}\"\n"
        "    status = item.get('status') or HardwareStatusChoices.IN_USE\n"
        "    if status not in status_values:\n"
        "        return f'status 不合法: {status!r}'\n"
        "    try:\n"
        "        quantity = int(item.get('quantity'))\n"
        "    except (TypeError, ValueError):\n"
        "        return f\"quantity 必须是整数: {item.get('quantity')!r}\"\n"
        "    if quantity < 0:\n"
        "        return 'quantity 不能为负数'\n"
        "    if len(str(item.get('purchase_link') or '')) > 500:\n"
        "        return 'purchase_link 超过 500 字符'\n"
        "    if len(str(item.get('storage_location') or '')) > 100:\n"
        "        return 'storage_location 超过 100 字符'\n"
        "    unit_price = item.get('unit_price')\n"
        "    if unit_price not in (None, ''):\n"
        "        try:\n"
        "            if abs(float(unit_price)) >= 10 ** 8:\n"
        "                return 'unit_price 超出可存储范围'\n"
        "        except (TypeError, ValueError):\n"
        "            return f'unit_price 不是数字: {unit_price!r}'\n"
        "    return ''\n"
        "\n"
        "\n"
        "class CommitHardwareImportAPIView(AgentAPIView):\n",
    ),
    (
        "        created_ids = []\n"
        "        try:\n"
        "            with transaction.atomic():\n"
        "                for item in valid_items:\n"
        "                    unit_price = _safe_decimal(item.get('unit_price'))\n"
        "                    hardware = Hardware.objects.create(\n"
        "                        name=item['name'],\n"
        "                        category=item['category'],\n"
        "                        model_number=item.get('model_number', ''),\n"
        "                        manufacturer=item.get('manufacturer', ''),\n"
        "                        quantity=int(item['quantity']),\n"
        "                        unit_price=unit_price,\n"
        "                        status=item.get('status') or HardwareStatusChoices.IN_USE,\n"
        "                        storage_location=item.get('storage_location', ''),\n"
        "                        purchase_link=item.get('purchase_link', ''),\n"
        "                        remarks=item.get('remarks', ''),\n"
        "                        submitted_by=self.acting_user,\n"
        "                        approval_status=HardwareApprovalStatusChoices.APPROVED,\n"
        "                        approved_by=self.acting_user,\n"
        "                    )\n"
        "                    created_ids.append(hardware.pk)\n"
        "\n"
        "                batch.status = 'imported'\n"
        "                batch.result_summary = {\n"
        "                    'total': len(valid_items),\n"
        "                    'success_count': len(created_ids),\n"
        "                    'failed_count': 0,\n"
        "                    'created_ids': created_ids,\n"
        "                }\n"
        "                batch.save(update_fields=['status', 'result_summary', 'last_updated'])\n"
        "        except Exception:\n"
        "            return self.error_response('平台内部异常', code='50001', status=500)\n",
        "        created_ids = []\n"
        "        failed_items = []\n"
        "        try:\n"
        "            with transaction.atomic():\n"
        "                # 行级锁 + 锁内重新校验状态：并发提交/重放不会再重复入库\n"
        "                batch = HardwareImportBatch.objects.select_for_update().get(pk=batch.pk)\n"
        "                if batch.status == 'imported':\n"
        "                    return self.error_response('批次已导入，禁止重复提交', code='40902', status=409)\n"
        "                if batch.status != 'validated':\n"
        "                    return self.error_response('预校验未通过，无法提交', code='42201', status=422)\n"
        "\n"
        "                for index, item in enumerate(valid_items):\n"
        "                    item_error = _validate_import_item(item)\n"
        "                    if item_error:\n"
        "                        failed_items.append({'row': index + 1, 'error': item_error})\n"
        "                        continue\n"
        "                    unit_price = _safe_decimal(item.get('unit_price'))\n"
        "                    hardware = Hardware.objects.create(\n"
        "                        name=str(item['name']).strip(),\n"
        "                        category=item['category'],\n"
        "                        model_number=str(item.get('model_number') or ''),\n"
        "                        manufacturer=str(item.get('manufacturer') or ''),\n"
        "                        quantity=int(item['quantity']),\n"
        "                        unit_price=unit_price,\n"
        "                        status=item.get('status') or HardwareStatusChoices.IN_USE,\n"
        "                        storage_location=str(item.get('storage_location') or ''),\n"
        "                        purchase_link=str(item.get('purchase_link') or ''),\n"
        "                        remarks=str(item.get('remarks') or ''),\n"
        "                        submitted_by=self.acting_user,\n"
        "                        approval_status=HardwareApprovalStatusChoices.APPROVED,\n"
        "                        approved_by=self.acting_user,\n"
        "                    )\n"
        "                    created_ids.append(hardware.pk)\n"
        "\n"
        "                if failed_items:\n"
        "                    raise _ImportAborted()\n"
        "\n"
        "                batch.status = 'imported'\n"
        "                batch.result_summary = {\n"
        "                    'total': len(valid_items),\n"
        "                    'success_count': len(created_ids),\n"
        "                    'failed_count': len(failed_items),\n"
        "                    'created_ids': created_ids,\n"
        "                }\n"
        "                batch.save(update_fields=['status', 'result_summary', 'last_updated'])\n"
        "        except _ImportAborted:\n"
        "            return self.error_response(\n"
        "                f'导入数据校验未通过（{len(failed_items)} 条），已整批回滚',\n"
        "                code='42202', status=422,\n"
        "            )\n"
        "        except Exception:\n"
        "            logger.exception('硬件批量导入提交失败 batch_id=%s', batch_id)\n"
        "            return self.error_response('平台内部异常', code='50001', status=500)\n",
    ),
    (
        "                'summary': {\n"
        "                    'total': len(valid_items),\n"
        "                    'success_count': len(created_ids),\n"
        "                    'failed_count': 0,\n"
        "                },\n",
        "                'summary': {\n"
        "                    'total': len(valid_items),\n"
        "                    'success_count': len(created_ids),\n"
        "                    'failed_count': len(failed_items),\n"
        "                },\n",
    ),
])

# ── D. views.py：智能体会话消息分页 ────────────────────────────
patch('lab_manager/views.py', [(
    "        ctx['conversation_messages'] = active_conversation.messages.all() if active_conversation else []\n",
    "        # 长会话只加载最近 200 条，避免整表加载与渲染\n"
    "        if active_conversation:\n"
    "            recent_messages = list(active_conversation.messages.order_by('-created')[:200])\n"
    "            recent_messages.reverse()\n"
    "        else:\n"
    "            recent_messages = []\n"
    "        ctx['conversation_messages'] = recent_messages\n",
)])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
