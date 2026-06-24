"""Management command to export lab data as CSV."""
import csv
import io
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from lab_manager.models import CheckInRecord, Hardware, Task


class Command(BaseCommand):
    help = _('导出实验室数据为 CSV 格式')

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            choices=['hardware', 'tasks', 'checkins'],
            default='hardware',
            help=_('要导出的数据类型'),
        )

    def handle(self, *args, **options):
        model_name = options['model']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'lab_{model_name}_{timestamp}.csv'

        if model_name == 'hardware':
            self._export_hardware(filename)
        elif model_name == 'tasks':
            self._export_tasks(filename)
        elif model_name == 'checkins':
            self._export_checkins(filename)

    def _export_hardware(self, filename):
        rows = Hardware.objects.select_related('custodian').all().values_list(
            'name', 'category', 'model_number', 'manufacturer', 'quantity',
            'status', 'storage_location', 'custodian__username', 'approval_status',
            'remarks', 'created',
        )
        headers = ['名称', '类别', '型号', '厂家', '数量', '状态', '存放位置', '保管人', '审批状态', '备注', '创建时间']
        self._write_csv(filename, headers, rows)
        self.stdout.write(self.style.SUCCESS(f'硬件数据已导出到 {filename}（{len(rows) if hasattr(rows,"__len__") else "N"} 条）'))

    def _export_tasks(self, filename):
        rows = Task.objects.select_related('assigned_to', 'created_by').all().values_list(
            'title', 'status', 'priority', 'assigned_to__username', 'created_by__username',
            'deadline', 'completed_at', 'completion_note', 'created',
        )
        headers = ['标题', '状态', '优先级', '执行人', '创建人', '截止日期', '完成时间', '完成说明', '创建时间']
        self._write_csv(filename, headers, rows)
        self.stdout.write(self.style.SUCCESS(f'任务数据已导出到 {filename}'))

    def _export_checkins(self, filename):
        rows = CheckInRecord.objects.select_related('user').all().values_list(
            'user__username', 'created', 'latitude', 'longitude', 'accuracy', 'address', 'note',
        )
        headers = ['打卡人', '打卡时间', '纬度', '经度', '精度', '地址', '备注']
        self._write_csv(filename, headers, rows)
        self.stdout.write(self.style.SUCCESS(f'打卡数据已导出到 {filename}'))

    def _write_csv(self, filename, headers, rows):
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
