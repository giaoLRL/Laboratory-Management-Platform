"""批次 UI-1b：CSV 导出、分页器接入通知/成员列表、任务看板模板。"""
import io
import os
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
report, failures = [], []


def read(rel):
    return io.open(os.path.join(BASE, rel), encoding='utf-8').read()


def patch(rel, pairs):
    src = read(rel)
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            failures.append(f'{rel}: 期望 1 次，实际 {n} 次 -> {old.strip().splitlines()[0][:66]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {rel}: {old.strip().splitlines()[0][:64]}')
    if src != orig and APPLY:
        io.open(os.path.join(BASE, rel), 'w', encoding='utf-8', newline='').write(src)


patch('lab_manager/views.py', [
    # 导入 csv / HttpResponse
    (
        "import json\nfrom datetime import timedelta\n",
        "import csv\nimport json\nfrom datetime import timedelta\n",
    ),
    (
        "from django.http import HttpResponseNotAllowed, JsonResponse\n",
        "from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse\n",
    ),
    # CSV 助手 + 两个列表的公共筛选函数
    (
        "def build_page(request, queryset, default_size=DEFAULT_PAGE_SIZE):\n",
        "def csv_response(filename, headers, rows):\n"
        '    """统一的 CSV 下载响应（带 BOM，Excel 可直接打开）。"""\n'
        "    response = HttpResponse(content_type='text/csv; charset=utf-8')\n"
        "    response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'\n"
        "    response.write('\\ufeff')\n"
        "    writer = csv.writer(response)\n"
        "    writer.writerow(headers)\n"
        "    for row in rows:\n"
        "        writer.writerow(row)\n"
        "    return response\n"
        "\n"
        "\n"
        "def filter_checkins(request, queryset):\n"
        '    """打卡记录的公共筛选（列表与导出共用）。"""\n'
        "    if not request.user.is_superuser:\n"
        "        queryset = queryset.filter(user=request.user)\n"
        "    username = (request.GET.get('username') or '').strip()\n"
        "    keyword = (request.GET.get('q') or '').strip()\n"
        "    date_from = (request.GET.get('date_from') or '').strip()\n"
        "    date_to = (request.GET.get('date_to') or '').strip()\n"
        "    if username:\n"
        "        queryset = queryset.filter(\n"
        "            Q(user__username__icontains=username) | Q(user__first_name__icontains=username)\n"
        "            | Q(user__last_name__icontains=username) | Q(user__email__icontains=username)\n"
        "        )\n"
        "    if keyword:\n"
        "        queryset = queryset.filter(Q(address__icontains=keyword) | Q(note__icontains=keyword))\n"
        "    if date_from:\n"
        "        queryset = queryset.filter(created__date__gte=date_from)\n"
        "    if date_to:\n"
        "        queryset = queryset.filter(created__date__lte=date_to)\n"
        "    return queryset\n"
        "\n"
        "\n"
        "def filter_member_open_records(request, queryset):\n"
        '    """浏览记录的公共筛选（列表与导出共用）。"""\n'
        "    username = (request.GET.get('username') or '').strip()\n"
        "    target_type = (request.GET.get('target_type') or '').strip()\n"
        "    keyword = (request.GET.get('q') or '').strip()\n"
        "    date_from = (request.GET.get('date_from') or '').strip()\n"
        "    date_to = (request.GET.get('date_to') or '').strip()\n"
        "    if username:\n"
        "        queryset = queryset.filter(\n"
        "            Q(user__username__icontains=username) | Q(user__first_name__icontains=username)\n"
        "            | Q(user__last_name__icontains=username) | Q(user__email__icontains=username)\n"
        "        )\n"
        "    if target_type:\n"
        "        queryset = queryset.filter(target_type=target_type)\n"
        "    if keyword:\n"
        "        queryset = queryset.filter(Q(path__icontains=keyword) | Q(page_title__icontains=keyword))\n"
        "    if date_from:\n"
        "        queryset = queryset.filter(created__date__gte=date_from)\n"
        "    if date_to:\n"
        "        queryset = queryset.filter(created__date__lte=date_to)\n"
        "    return queryset\n"
        "\n"
        "\n"
        "def build_page(request, queryset, default_size=DEFAULT_PAGE_SIZE):\n",
    ),
    # 打卡视图：get() 支持导出；get_context_data 复用公共筛选
    (
        "    def get(self, request, *args, **kwargs):\n"
        "        record_member_open(request, page_title='打卡记录', target_type='checkin_list')\n"
        "        return super().get(request, *args, **kwargs)\n",
        "    def get(self, request, *args, **kwargs):\n"
        "        if request.GET.get('export') == 'csv':\n"
        "            records = filter_checkins(\n"
        "                request, CheckInRecord.objects.select_related('user').order_by('-created')\n"
        "            )[:5000]\n"
        "            return csv_response(\n"
        "                'lab_checkins.csv',\n"
        "                ['时间', '成员', '纬度', '经度', '精度', '地址备注', '备注', '照片'],\n"
        "                records.values_list('created', 'user__username', 'latitude', 'longitude',\n"
        "                                    'accuracy', 'address', 'note', 'photo'),\n"
        "            )\n"
        "        record_member_open(request, page_title='打卡记录', target_type='checkin_list')\n"
        "        return super().get(request, *args, **kwargs)\n",
    ),
    (
        "        records = CheckInRecord.objects.select_related('user').order_by('-created')\n"
        "        if not request.user.is_superuser:\n"
        "            records = records.filter(user=request.user)\n"
        "        # ── 筛选：成员 / 关键词 / 时间范围 ──\n"
        "        username = (request.GET.get('username') or '').strip()\n"
        "        keyword = (request.GET.get('q') or '').strip()\n"
        "        date_from = (request.GET.get('date_from') or '').strip()\n"
        "        date_to = (request.GET.get('date_to') or '').strip()\n"
        "        if username:\n"
        "            records = records.filter(\n"
        "                Q(user__username__icontains=username) | Q(user__first_name__icontains=username)\n"
        "                | Q(user__last_name__icontains=username) | Q(user__email__icontains=username)\n"
        "            )\n"
        "        if keyword:\n"
        "            records = records.filter(Q(address__icontains=keyword) | Q(note__icontains=keyword))\n"
        "        if date_from:\n"
        "            records = records.filter(created__date__gte=date_from)\n"
        "        if date_to:\n"
        "            records = records.filter(created__date__lte=date_to)\n"
        "        page_obj = add_pagination(ctx, request, records)\n"
        "        ctx['records'] = page_obj.object_list\n"
        "        ctx['is_superuser'] = request.user.is_superuser\n"
        "        ctx['filter_username'] = username\n"
        "        ctx['filter_q'] = keyword\n"
        "        ctx['filter_date_from'] = date_from\n"
        "        ctx['filter_date_to'] = date_to\n"
        "        ctx['filtered_count'] = page_obj.paginator.count\n"
        "        return ctx\n",
        "        records = filter_checkins(\n"
        "            request, CheckInRecord.objects.select_related('user').order_by('-created')\n"
        "        )\n"
        "        page_obj = add_pagination(ctx, request, records)\n"
        "        ctx['records'] = page_obj.object_list\n"
        "        ctx['is_superuser'] = request.user.is_superuser\n"
        "        ctx['filter_username'] = (request.GET.get('username') or '').strip()\n"
        "        ctx['filter_q'] = (request.GET.get('q') or '').strip()\n"
        "        ctx['filter_date_from'] = (request.GET.get('date_from') or '').strip()\n"
        "        ctx['filter_date_to'] = (request.GET.get('date_to') or '').strip()\n"
        "        ctx['filtered_count'] = page_obj.paginator.count\n"
        "        ctx['checkin_create_url'] = reverse('plugins:lab_manager:checkin_create')\n"
        "        return ctx\n",
    ),
    # 浏览记录：get() 支持导出 + 复用公共筛选
    (
        "    def get_context_data(self, **kwargs):\n"
        "        ctx = super().get_context_data(**kwargs)\n"
        "        records = MemberOpenRecord.objects.select_related('user').order_by('-created')\n"
        "        username = self.request.GET.get('username')\n"
        "        target_type = self.request.GET.get('target_type')\n",
        "    def get(self, request, *args, **kwargs):\n"
        "        if request.GET.get('export') == 'csv':\n"
        "            records = filter_member_open_records(\n"
        "                request, MemberOpenRecord.objects.select_related('user').order_by('-created')\n"
        "            )[:5000]\n"
        "            return csv_response(\n"
        "                'lab_member_open_records.csv',\n"
        "                ['时间', '成员', '对象类型', '页面', '路径', 'IP', '纬度', '经度'],\n"
        "                records.values_list('created', 'user__username', 'target_type', 'page_title',\n"
        "                                    'path', 'ip_address', 'latitude', 'longitude'),\n"
        "            )\n"
        "        return super().get(request, *args, **kwargs)\n"
        "\n"
        "    def get_context_data(self, **kwargs):\n"
        "        ctx = super().get_context_data(**kwargs)\n"
        "        records = filter_member_open_records(\n"
        "            self.request, MemberOpenRecord.objects.select_related('user').order_by('-created')\n"
        "        )\n"
        "        username = self.request.GET.get('username')\n"
        "        target_type = self.request.GET.get('target_type')\n",
    ),
])

# 通知 / 成员列表：追加分页器（插入到最后一个 endblock 之前）
for rel, anchor in [('lab_manager/templates/lab_manager/notification_list.html', None),
                    ('lab_manager/templates/lab_manager/member_list.html', None)]:
    src = read(rel)
    if 'inc/paginator.html' in src:
        report.append(f'  -- {rel}: 已有分页器，跳过')
        continue
    idx = src.rfind('{% endblock %}')
    if idx == -1:
        failures.append(f'{rel}: 未找到 endblock')
        continue
    src = src[:idx] + "{% include 'lab_manager/inc/paginator.html' %}\n" + src[idx:]
    if not src.lstrip().startswith('{% extends') or 'lm_ui' not in src.split('\n')[1]:
        # 确保加载 lm_ui（分页器内部会 load，无需在此 load）
        pass
    if APPLY:
        io.open(os.path.join(BASE, rel), 'w', encoding='utf-8', newline='').write(src)
    report.append(f'  ok {rel}: 追加分页器')

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
