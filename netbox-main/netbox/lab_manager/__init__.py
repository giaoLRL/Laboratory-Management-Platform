from netbox.plugins import PluginConfig


class LabManagerConfig(PluginConfig):
    name = 'lab_manager'
    verbose_name = '实验室管理平台'
    description = '大学生电赛实验室管理：硬件资源管理 + 任务分配系统'
    version = '2.0.0'
    author = 'Lab Admin'
    base_url = 'lab-manager'
    min_version = '4.6.0'

    def ready(self):
        super().ready()


config = LabManagerConfig
