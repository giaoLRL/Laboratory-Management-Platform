from netbox.plugins import PluginConfig


class LabManagerConfig(PluginConfig):
    name = 'lab_manager'
    verbose_name = '实验室管理系统'
    description = '大学生电赛实验室管理：硬件资源管理 + 任务分配系统'
    version = '2.0.0'
    author = 'Lab Admin'
    base_url = 'lab-manager'
    min_version = '4.6.0'

    def ready(self):
        super().ready()
        # 插件不会自动发现 signals.py，必须显式导入才能注册接收器
        from . import signals  # noqa: F401


config = LabManagerConfig
