# AI 编程规则

> 用于规范 AI 辅助编程行为，减少常见错误，提高协作效率。本项目基于 NetBox v4.6.3 框架以插件方式做实验室管理平台开发。

---

## 一、先思考，再动手

在开始写代码之前，必须完成以下步骤：

- **明确需求**：如果需求模糊，不要假设，先提问澄清。
- **评估方案**：如果存在多种实现方式，列出优缺点再选择，不要默默选定一种。
- **简化优先**：如果能用更简单的方式实现，主动提出；不合理需求要敢于质疑。
- **标注疑问**：不清楚的地方立刻停下来，明确写出困惑所在。

```
禁止行为：看到需求 → 直接写代码
正确行为：看到需求 → 理解确认 → 设计方案 → 写代码
```

---

## 二、简洁至上

以最少的代码解决问题，不做任何多余的事。

### 四条底线

| 规则 | 说明 |
|------|------|
| 不加未要求的功能 | 用户要什么就做什么，不要"顺便"加东西 |
| 不做过度抽象 | 如果代码只在一个地方用，不要提取成工具函数 |
| 不做未要求的灵活性 | 不加配置项、开关、拓展点 |
| 不处理不可能的错误 | 信任内部代码和框架的保证 |

### 自查标准

写完代码后问自己：**"一个有经验的工程师会觉得这里过度设计吗？"** 如果是，重写。

```
200 行能解决的事不要写成 500 行。
3 行重复代码 > 1 个过早的抽象。
```

---

## 三、精准修改

只动需要改的地方，不要"顺手"改别的。

### 修改原则

- **不动无关代码**：不优化、不格式化、不加注释、不重构你本不该碰的代码
- **风格跟随**：即使现有代码风格你不喜欢，也要保持一致
- **看到问题先记录**：发现无关的死代码或 bug，先告知用户，不要直接删除或修复
- **清理自己的痕迹**：你新增的代码产生的孤立导入、变量、函数，必须删除

### 自检标准

**diff 中的每一行改动，都必须能追溯到用户的需求。** 如果有行改了你解释不了为什么改，删掉它。

---

## 四、目标驱动

把模糊需求转化成可验证的目标，循环迭代直到验证通过。

### 需求转化范例

| 模糊需求 | 转化后的可验证目标 |
|----------|-------------------|
| "加个校验" | 先写无效输入的测试用例，再让测试通过 |
| "修这个 bug" | 先写能复现 bug 的测试，再修复，确认测试变绿 |
| "重构 X" | 确保重构前后所有已有测试通过 |
| "加个功能" | 明确功能边界，写完功能代码后写测试验证 |

### 多步骤任务模板

```
1. [步骤一] → 验证: [怎么确认完成]
2. [步骤二] → 验证: [怎么确认完成]
3. [步骤三] → 验证: [怎么确认完成]
```

### 验证闭环

- 强验证标准让你能独立迭代，减少反复确认
- 弱验证标准（"让它能用"）会导致不断的沟通返工

---

## 五、项目技术栈与版本

| 组件 | 版本 | 说明 |
|------|------|------|
| NetBox | **v4.6.3** | 核心框架，**严禁修改源码** |
| Python | **3.12+** | 最低要求 |
| Django | **6.x** | Web 框架 |
| PostgreSQL | **15+** | 必备，特性依赖（JSONField、ArrayField、全文搜索） |
| Redis | **7.x** | 必备，缓存 + django-rq 后台任务队列 |
| Django REST Framework | 3.x | REST API |
| GraphQL | Strawberry | 可选，GraphQL API |
| 前端 | HTMX + vanilla JS | NetBox 原生方案 |
| 搜索 | PostgreSQL 全文搜索 | 通过 SearchIndex 注册 |
| Lint | Ruff | 配置在 `pyproject.toml` |

---

## 六、项目目录结构速查

```
netbox-main/
├── netbox/                              ← Django 项目根 (manage.py 在此)
│   ├── manage.py                        ← 所有命令由此运行
│   ├── netbox/                          ← 核心配置
│   │   ├── settings.py                  ← 主配置（不要动）
│   │   ├── configuration.py             ← 实例配置 (gitignored, 不要提交)
│   │   ├── configuration_example.py     ← 配置模板
│   │   ├── plugins/                     ← 插件基础设施
│   │   └── models/features.py           ← 模型特性 Mixin（重要参考）
│   ├── dcim/                            ← 数据中心基础设施 (Device/Rack/Cable)
│   ├── extras/                          ← 跨模块功能 (CustomField/Tag/Webhook/Script/EventRule)
│   ├── ipam/                            ← IP 地址管理
│   ├── circuits/                        ← 线路管理
│   ├── core/                            ← 核心数据 (Job/DataSource)
│   ├── users/                           ← 用户管理
│   └── utilities/                       ← 公共工具
├── docs/                                ← MkDocs 文档
├── pyproject.toml                       ← 项目元数据 + Ruff 配置
└── requirements.txt                     ← Python 依赖
```

> **重要**: `manage.py` 在 `netbox/` 子目录下，不是仓库根目录！所有命令必须 `cd netbox/` 后再执行。

---

## 七、本项目专属规则

### 7.1 插件开发铁律

| 规则 | 说明 |
|------|------|
| **绝对禁止修改 NetBox 核心源码** | 所有自定义功能通过插件实现 |
| 插件代码目录 | `netbox/lab_manager/` |
| 插件注册 | 必须继承 `netbox.plugins.PluginConfig` |
| 配置文件 | 插件配置写入 `configuration.py` 的 `PLUGINS` 和 `PLUGINS_CONFIG` |
| 内部 API 不稳定 | 只依赖 NetBox 文档中标记为 public 的 API |

### 7.2 插件目录结构规范

```
netbox/lab_manager/                   ← 插件根目录
├── __init__.py                       ← PluginConfig 定义 (config 变量)
├── api/
│   ├── __init__.py
│   ├── serializers.py                ← 继承 NetBoxModelSerializer
│   ├── views.py                      ← 继承 NetBoxModelViewSet
│   └── urls.py                       ← 通过 NetBoxRouter 注册
├── forms/
│   ├── bulk_edit.py
│   ├── bulk_import.py
│   ├── filtersets.py                 ← FilterForm
│   └── model_forms.py
├── filtersets.py                     ← 继承 NetBoxModelFilterSet
├── graphql/                          ← 可选
│   ├── schema.py
│   └── types.py                      ← Strawberry types
├── models/
│   ├── __init__.py
│   ├── lab_device.py
│   ├── task.py
│   └── video.py
├── navigation/
│   └── menu.py                       ← 导航菜单定义
├── search/
│   └── indexes.py                    ← SearchIndex 注册
├── tables/
│   ├── device.py
│   ├── task.py
│   └── video.py
├── scripts/                          ← 自定义脚本
│   └── notifications.py
├── templates/
│   └── lab_manager/                  ← 模板命名空间
│       ├── device_list.html
│       └── task_list.html
├── ui/
│   └── panels.py                     ← 详情页面板扩展
├── views.py                          ← 继承 generic.ObjectView/ObjectListView 等
├── urls.py                           ← 前端 URL 路由
├── choices.py                        ← ChoiceSet 子类
├── signals.py                        ← Django 信号（按需）
└── tests/
    ├── test_api.py
    ├── test_models.py
    ├── test_views.py
    └── test_filtersets.py
```

### 7.3 模型开发规范

#### 基类选择

| 需求 | 继承的类 |
|------|----------|
| 完全自定义模型（需要完整功能） | `netbox.models.NetBoxModel` |
| 仅需变更日志 | `netbox.models.features.ChangeLoggingMixin` |
| 仅需标签 | `netbox.models.features.TagsMixin` |
| 仅需自定义字段 | `netbox.models.features.CustomFieldsMixin` |
| 需要后台任务 | `netbox.models.features.JobsMixin` |
| 需要事件触发 | `netbox.models.features.EventRulesMixin` |
| 文件模型 | `core.models.ManagedFile` |

> **注意**: `NetBoxModel` 自带 `created`、`last_updated`、`custom_field_data`、`tags` 等字段，无需手动添加。

#### 字段规范

```python
from django.db import models
from django.utils.translation import gettext_lazy as _

class MyModel(models.Model):
    name = models.CharField(
        verbose_name=_('名称'),       # 必须加 verbose_name 中文描述
        max_length=100,
    )
    status = models.CharField(
        verbose_name=_('状态'),
        max_length=30,
        choices=[('active', '活跃'), ('inactive', '非活跃')],
    )
    related_user = models.ForeignKey(
        to='users.User',             # 不要用 django.contrib.auth.models.User
        on_delete=models.PROTECT,
        related_name='my_models',
        verbose_name=_('关联用户'),
    )
```

#### 选择字段规范

统一放在 `choices.py` 中，使用 NetBox 的 `ChoiceSet`：

```python
from utilities.choices import ChoiceSet

class TaskStatusChoices(ChoiceSet):
    key = 'Task.status'
    PENDING = 'pending'
    ASSIGNED = 'assigned'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    CHOICES = [
        (PENDING, '待分配'),
        (ASSIGNED, '已分配'),
        (IN_PROGRESS, '进行中'),
        (COMPLETED, '已完成'),
        (CANCELLED, '已取消'),
    ]
```

### 7.4 视图开发规范

#### 使用 `register_model_view()` 注册视图

```python
from netbox.views import generic
from utilities.views import register_model_view

@register_model_view(MyModel, 'list')
class MyModelListView(generic.ObjectListView):
    queryset = MyModel.objects.all()
    table = MyModelTable
    filterset = MyModelFilterSet
    filterset_form = MyModelFilterForm
```

> **不需要手动添加 `select_related()` 或 `prefetch_related()`** — NetBox 的 Table 类和 Serializer 会动态处理。

#### 通用视图基类

| 基类 | 用途 |
|------|------|
| `generic.ObjectListView` | 列表页 |
| `generic.ObjectView` | 详情页 |
| `generic.ObjectEditView` | 编辑/新建 |
| `generic.ObjectDeleteView` | 删除 |
| `generic.BulkImportView` | 批量导入 |
| `generic.BulkEditView` | 批量编辑 |
| `generic.BulkDeleteView` | 批量删除 |
| `generic.ObjectChildrenView` | 关联子对象列表 |

### 7.5 REST API 开发规范

```python
# serializers.py
from netbox.api.serializers import NetBoxModelSerializer

class MyModelSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:lab_manager-api:mymodel-detail')

    class Meta:
        model = MyModel
        fields = ('id', 'url', 'display', 'name', 'status', 'tags', 'custom_fields', ...)

# views.py
from netbox.api.viewsets import NetBoxModelViewSet

class MyModelViewSet(NetBoxModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MyModelSerializer

# urls.py
from netbox.api.routers import NetBoxRouter

router = NetBoxRouter()
router.register('my-models', MyModelViewSet)
urlpatterns = router.urls
```

> **Serializer 中必须包含 `url` 字段** — 为对象的绝对 URL。
> **不需要手动添加 `select_related()`** — Serializer 动态处理。

### 7.6 FilterSet 开发规范

```python
# filtersets.py
import django_filters
from netbox.filtersets import NetBoxModelFilterSet
from utilities.filters import MultiValueCharFilter

class MyModelFilterSet(NetBoxModelFilterSet):
    # FK 字段必须显式声明 _id 变体
    related_user_id = django_filters.ModelMultipleChoiceFilter(
        field_name='related_user',
        queryset=User.objects.all(),
    )

    class Meta:
        model = MyModel
        fields = ('name', 'status', 'related_user')
```

> **FK 过滤器铁则**: 必须显式声明 `<field>_id = ModelMultipleChoiceFilter(field_name='<field>', ...)`，不要依赖 `Meta.fields` 自动生成。

### 7.7 Table 开发规范

```python
# tables/mymodel.py
import django_tables2 as tables
from netbox.tables import NetBoxTable
from netbox.tables.columns import ChoiceFieldColumn

class MyModelTable(NetBoxTable):
    name = tables.Column(linkify=True)  # linkify=True 自动生成详情链接
    status = ChoiceFieldColumn()
    related_user = tables.Column(linkify=True)

    class Meta(NetBoxTable.Meta):
        model = MyModel
        fields = ('pk', 'id', 'name', 'status', 'related_user', 'tags')
        default_columns = ('name', 'status', 'related_user')
```

### 7.8 搜索集成

需要全局搜索的模型，必须注册 `SearchIndex`：

```python
# search/indexes.py
from netbox.search import SearchIndex, register_search

@register_search
class MyModelIndex(SearchIndex):
    model = MyModel
    fields = (
        ('name', 100),
        ('description', 50),
    )
```

### 7.9 导航菜单

```python
# navigation/menu.py
from netbox.navigation.menu import Menu, MenuItem, MenuButton

menu = Menu(
    MenuItem(
        link='plugins:lab_manager:device_list',
        link_text='设备管理',
        buttons=(
            MenuButton(link='plugins:lab_manager:device_add', title='添加设备', icon_class='mdi mdi-plus-thick'),
        )
    ),
    MenuItem(
        link='plugins:lab_manager:task_list',
        link_text='任务管理',
    ),
    MenuItem(
        link='plugins:lab_manager:video_list',
        link_text='视频管理',
    ),
)
```

### 7.10 脚本与后台任务

```python
# scripts/notifications.py
from extras.scripts import Script, ObjectVar, StringVar, TextVar

class TaskNotificationScript(Script):
    class Meta:
        name = "发送任务通知"
        description = "当任务分配时通知相关人员"

    task = ObjectVar(model=Task, label="任务")

    def run(self, data, commit):
        task = data['task']
        # 业务逻辑
        return "通知已发送"
```

- 所有后台任务必须继承 `netbox.jobs.JobRunner`
- 脚本放在 `scripts/` 目录下，自动被发现
- 定时任务（维保检查、逾期提醒）通过 `django-rq` scheduler 或系统 crontab 触发 `manage.py` 管理命令

### 7.11 信号与事件

利用 NetBox 内置的 `EventRule` + `Webhook` 实现自动化：

```python
# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Task)
def on_task_saved(sender, instance, created, **kwargs):
    if created:
        # 触发事件，EventRule 自动匹配并执行
        pass
```

---

## 八、编码检查清单

每次提交代码前，逐条确认：

- [ ] 所有改动都能追溯到用户需求？
- [ ] 有没有不必要的抽象或"将来可能用到"的代码？
- [ ] Model 字段都加了 `verbose_name`？
- [ ] 新建的 Model 继承了正确的基类（`NetBoxModel` 或相关 Mixin）？
- [ ] Choice 字段放到了 `choices.py` 使用 `ChoiceSet` 定义？
- [ ] FK 外键使用 `users.User` 而非 `django.contrib.auth.models.User`？
- [ ] View 使用 `register_model_view()` 注册？
- [ ] FilterSet 中 FK 字段显式声明了 `_id` 变体？
- [ ] Serializer 包含 `url` 字段？
- [ ] API 路由通过 `NetBoxRouter` 注册？
- [ ] 需要搜索的模型注册了 `SearchIndex`？
- [ ] 没有修改 NetBox 核心源码？
- [ ] 没有提交 `configuration.py`（是 gitignored 的）？
- [ ] 没有手动写 migration 文件（用 `makemigrations` 生成）？
- [ ] 代码风格与现有文件一致？
- [ ] 测试能否跑通？

---

## 九、常用命令

> **所有命令从 `netbox/` 子目录执行，不是仓库根目录！**

| 命令 | 说明 |
|------|------|
| `cd netbox/ && python manage.py runserver` | 启动开发服务器 |
| `cd netbox/ && python manage.py test` | 运行全部测试 |
| `cd netbox/ && python manage.py test --keepdb --parallel 4` | 快速测试（保留数据库，并行） |
| `cd netbox/ && python manage.py test lab_manager.tests.test_models` | 运行单个测试模块 |
| `cd netbox/ && python manage.py makemigrations` | 生成迁移文件（不要手写） |
| `cd netbox/ && python manage.py migrate` | 执行迁移 |
| `ruff check` | 代码检查（仓库根目录执行） |
| `export NETBOX_CONFIGURATION=netbox.configuration_testing` | 测试前设置环境变量 |

**测试前必须设置环境变量**:
```bash
# Linux/Mac
export NETBOX_CONFIGURATION=netbox.configuration_testing
# Windows PowerShell
$env:NETBOX_CONFIGURATION="netbox.configuration_testing"
```

---

## 十、常见错误与纠正

| 常见错误 | 纠正方式 |
|----------|----------|
| 直接 `from django.contrib.auth.models import User` | 使用 `users.User` 或 `get_user_model()` |
| 在 `__init__.py` 中写大量业务逻辑 | 业务逻辑放到 `views.py` / `models.py` / `utils.py` |
| 忘记注册 SearchIndex 导致搜索不可用 | 模型完成后同步注册 `search/indexes.py` |
| 修改了 NetBox 核心文件解决需求 | 通过插件扩展或 CustomField 实现 |
| 提交时带了无关文件的改动 | 用 `git diff` 逐文件检查后再提交 |
| FilterSet 中 FK 字段没声明 `_id` 变体 | 显式声明 `<field>_id = ModelMultipleChoiceFilter(...)` |
| 从仓库根目录运行 `manage.py` | `manage.py` 在 `netbox/` 子目录下 |
| 没设 `NETBOX_CONFIGURATION` 就跑测试 | 测试前必须设置该环境变量 |
| 手写 migration 文件 | 用 `makemigrations` 自动生成 |
| 提交 `configuration.py` | 该文件在 `.gitignore` 中，包含敏感信息 |
| Serializer 漏了 `url` 字段 | 每个 NetBoxModelSerializer 子类必须包含 |
| List View 手动加了 `select_related()` | NetBox Table 自动处理预加载 |

---

## 十一、实验室管理平台专属模型清单

开发过程中需要实现的模型（按优先级）：

| 模型 | 文件 | 基类 | 说明 |
|------|------|------|------|
| `LabDeviceType` | `models/lab_device.py` | `NetBoxModel` | 实验室设备分类 |
| `LabDevice` | `models/lab_device.py` | `NetBoxModel` | 设备资产实例（关联 dcim.Device） |
| `TaskType` | `models/task.py` | `NetBoxModel` | 任务类型 |
| `Task` | `models/task.py` | `NetBoxModel` | 实验任务（含 EventRulesMixin, JobsMixin） |
| `TaskComment` | `models/task.py` | `ChangeLoggingMixin` | 任务评论 |
| `TaskLog` | `models/task.py` | 普通 models.Model | 任务操作日志 |
| `Video` | `models/video.py` | `NetBoxModel` | 实验视频 |
| `VideoTag` | `models/video.py` | `NetBoxModel` | 视频标签 |

---

> **核心理念**：好的 AI 编程不是写得快，而是改得少、改得准、不出错。

> **版本**: v2.0 | **更新日期**: 2026-06-19 | **适用项目**: NetBox v4.6.3 实验室管理平台插件
