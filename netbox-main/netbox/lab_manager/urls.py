from django.urls import include, path

from utilities.urls import get_model_urls
from . import views

app_name = 'lab_manager'

urlpatterns = [
    # 硬件
    path('hardware/', include(get_model_urls('lab_manager', 'hardware', detail=False))),
    path('hardware/<int:pk>/', include(get_model_urls('lab_manager', 'hardware'))),

    # 硬件审核
    path('hardware/<int:pk>/approval/', views.HardwareApprovalView.as_view(), name='hardware_approval'),

    # Task
    path('tasks/', include(get_model_urls('lab_manager', 'task', detail=False))),
    path('tasks/<int:pk>/', include(get_model_urls('lab_manager', 'task'))),

    # 我的任务
    path('my-tasks/', views.MyTasksView.as_view(), name='my_tasks'),

    # 附件上传
    path('tasks/<int:pk>/upload/', views.TaskUploadAttachmentView.as_view(), name='task_upload'),

    # 标记完成
    path('tasks/<int:pk>/complete/', views.TaskCompleteView.as_view(), name='task_complete'),

    # 评论
    path('tasks/<int:pk>/comment/', views.TaskCommentView.as_view(), name='task_comment'),

    # 删除附件
    path('attachments/<int:pk>/delete/', views.TaskAttachmentDeleteView.as_view(), name='task_attachment_delete'),

    # 实验室首页
    path('', views.LabHomeView.as_view(), name='home'),
]
