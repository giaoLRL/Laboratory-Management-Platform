"""批次6 补丁：动态字段容忍缺失的 core-api（修 17 个导入页 500）、REST 序列化器补 url 字段、
缺失 FilterSet 的模型补最小过滤器。"""
import io
import os
import re as _re
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
        report.append(f'  ok {path}: {old.strip().splitlines()[0][:66]}')
    for pat, new, expect in regex_pairs:
        src, n = _re.subn(pat, new, src)
        (report if n == expect else failures).append(
            f'  {"ok" if n == expect else "!!"} {path}(regex {n}/{expect}): {pat[:55]}')
    if src != orig and APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)


# ── 1. 动态字段：core-api 缺失时不 500（P0-10）───────────────────
patch('utilities/forms/fields/dynamic.py', [
    (
        "        # Set the data URL on the APISelect widget (if not already set)\n"
        "        if not widget.attrs.get('data-url'):\n"
        "            widget.attrs['data-url'] = get_action_url(self.queryset.model, action='list', rest_api=True)\n",
        "        # Set the data URL on the APISelect widget (if not already set)\n"
        "        if not widget.attrs.get('data-url'):\n"
        "            try:\n"
        "                widget.attrs['data-url'] = get_action_url(\n"
        "                    self.queryset.model, action='list', rest_api=True\n"
        "                )\n"
        "            except NoReverseMatch:\n"
        "                # 本实例裁剪掉了核心 REST API（core-api 命名空间不存在）时，\n"
        "                # 动态字段退化为无 API 自动补全，而不是让整个表单页面 500。\n"
        "                widget.attrs['data-url'] = ''\n",
    ),
])

full = os.path.join(BASE, 'utilities/forms/fields/dynamic.py')
src = io.open(full, encoding='utf-8').read()
if 'NoReverseMatch' in src and 'from django.urls import NoReverseMatch' not in src:
    m = _re.search(r'(?m)^from django\.urls import .*$', src)
    if m:
        src = src[:m.start()] + 'from django.urls import NoReverseMatch\n' + src[m.end():].lstrip('\n')
    else:
        m2 = _re.search(r'(?m)^from django\.core\.exceptions import .*$', src)
        if m2:
            src = src[:m2.end()] + '\nfrom django.urls import NoReverseMatch' + src[m2.end():]
        else:
            failures.append('dynamic.py: 未找到可插入 imports 的位置')
    if APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)
    report.append('  ok utilities/forms/fields/dynamic.py: 导入 NoReverseMatch')

# ── 2. REST 序列化器补 url 字段（NetBox API 约定）──────────────
serializers = os.path.join(BASE, 'lab_manager/api/serializers.py')
src = io.open(serializers, encoding='utf-8').read()
n = 0
# 在每个 Meta.fields 元组开头插入 'url'
src2, n = _re.subn(r"(\n        fields = \(\n)(            'id', )", r"\1            'url', 'id', ", src)
if n and APPLY:
    io.open(serializers, 'w', encoding='utf-8', newline='').write(src2)
(report if n else failures).append(f'  {"ok" if n else "!!"} api/serializers.py: 补 url 字段（{n} 个序列化器）')

# ── 3. 缺失 FilterSet 的模型补最小过滤器（?q= 不再静默无效）────
fs_path = os.path.join(BASE, 'lab_manager/filtersets.py')
src = io.open(fs_path, encoding='utf-8').read()
orig = src
if 'class TaskCommentFilterSet' in src:
    report.append('  -- filtersets.py: 已存在新 FilterSet，跳过')
else:
    src = src.replace(
        "import django_filters\nfrom django.utils.translation import gettext_lazy as _\n",
        "import django_filters\nfrom django.db.models import Q\n"
        "from django.utils.translation import gettext_lazy as _\n", 1)
    src = src.replace(
        "from .models import (\n"
        "    AgentTool, CheckInRecord, Hardware, HardwareBorrowRecord,\n"
        "    LabProject, MemberOpenRecord, Task, TaskAttachment,\n"
        ")\n",
        "from .models import (\n"
        "    AgentConversation, AgentMessage, AgentTool, CheckInRecord, Hardware,\n"
        "    HardwareBorrowRecord, HardwareImportBatch, LabProject, MemberOpenRecord,\n"
        "    Notification, Task, TaskAttachment, TaskComment,\n"
        ")\n", 1)
    src = src.rstrip('\n') + "\n\n\n" + '''class TaskCommentFilterSet(NetBoxModelFilterSet):
    q = django_filters.CharFilter(method='search', label=_('搜索'))

    class Meta:
        model = TaskComment
        fields = ('id', 'task', 'user')

    def search(self, queryset, name, value):
        return queryset.filter(Q(content__icontains=value))


class NotificationFilterSet(NetBoxModelFilterSet):
    q = django_filters.CharFilter(method='search', label=_('搜索'))

    class Meta:
        model = Notification
        fields = ('id', 'user', 'is_read', 'notification_type')

    def search(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(message__icontains=value))


class HardwareImportBatchFilterSet(NetBoxModelFilterSet):
    q = django_filters.CharFilter(method='search', label=_('搜索'))

    class Meta:
        model = HardwareImportBatch
        fields = ('id', 'batch_id', 'status', 'source_type')

    def search(self, queryset, name, value):
        return queryset.filter(Q(batch_id__icontains=value))


class AgentConversationFilterSet(NetBoxModelFilterSet):
    q = django_filters.CharFilter(method='search', label=_('搜索'))

    class Meta:
        model = AgentConversation
        fields = ('id', 'user', 'mode')

    def search(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value))


class AgentMessageFilterSet(NetBoxModelFilterSet):
    q = django_filters.CharFilter(method='search', label=_('搜索'))

    class Meta:
        model = AgentMessage
        fields = ('id', 'conversation', 'role')

    def search(self, queryset, name, value):
        return queryset.filter(Q(content__icontains=value))
'''
    if src != orig and APPLY:
        io.open(fs_path, 'w', encoding='utf-8', newline='').write(src)
    report.append('  ok lab_manager/filtersets.py: 追加 5 个 FilterSet + 模型导入')

# ── 4. viewsets 绑定 FilterSet ────────────────────────────────
patch('lab_manager/api/views.py', [
    (
        "class TaskCommentViewSet(NetBoxModelViewSet):\n"
        "    queryset = TaskComment.objects.prefetch_related('tags')\n"
        "    serializer_class = serializers.TaskCommentSerializer\n",
        "class TaskCommentViewSet(NetBoxModelViewSet):\n"
        "    queryset = TaskComment.objects.prefetch_related('tags')\n"
        "    serializer_class = serializers.TaskCommentSerializer\n"
        "    filterset_class = filtersets.TaskCommentFilterSet\n",
    ),
    (
        "class HardwareImportBatchViewSet(NetBoxModelViewSet):\n"
        "    queryset = HardwareImportBatch.objects.prefetch_related('tags')\n"
        "    serializer_class = serializers.HardwareImportBatchSerializer\n",
        "class HardwareImportBatchViewSet(NetBoxModelViewSet):\n"
        "    queryset = HardwareImportBatch.objects.prefetch_related('tags')\n"
        "    serializer_class = serializers.HardwareImportBatchSerializer\n"
        "    filterset_class = filtersets.HardwareImportBatchFilterSet\n",
    ),
    (
        "class AgentConversationViewSet(NetBoxModelViewSet):\n"
        "    queryset = AgentConversation.objects.prefetch_related('tags')\n"
        "    serializer_class = serializers.AgentConversationSerializer\n",
        "class AgentConversationViewSet(NetBoxModelViewSet):\n"
        "    queryset = AgentConversation.objects.prefetch_related('tags')\n"
        "    serializer_class = serializers.AgentConversationSerializer\n"
        "    filterset_class = filtersets.AgentConversationFilterSet\n",
    ),
    (
        "class AgentMessageViewSet(NetBoxModelViewSet):\n"
        "    queryset = AgentMessage.objects.prefetch_related('tags')\n"
        "    serializer_class = serializers.AgentMessageSerializer\n",
        "class AgentMessageViewSet(NetBoxModelViewSet):\n"
        "    queryset = AgentMessage.objects.prefetch_related('tags')\n"
        "    serializer_class = serializers.AgentMessageSerializer\n"
        "    filterset_class = filtersets.AgentMessageFilterSet\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
