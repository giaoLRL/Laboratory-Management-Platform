from django.utils import timezone

from ..choices import TaskStatusChoices


def mark_task_completed(task):
    """标记任务完成（辅助函数，供视图层调用）。"""
    task.status = TaskStatusChoices.COMPLETED
    task.completed_at = timezone.now()
    task.save(update_fields=['status', 'completed_at', 'completion_note'])
    return task
