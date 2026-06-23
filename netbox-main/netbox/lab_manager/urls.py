from django.urls import include, path

from . import agent_api
from utilities.urls import get_model_urls
from . import views

app_name = 'lab_manager'

urlpatterns = [
    # Agent API
    path('api/agent/hardware/search/', agent_api.SearchHardwareAPIView.as_view(), name='agent_hardware_search'),
    path('api/agent/hardware/gap-analysis/', agent_api.AnalyzeHardwareGapAPIView.as_view(), name='agent_hardware_gap_analysis'),
    path('api/agent/members/search/', agent_api.SearchMembersAPIView.as_view(), name='agent_members_search'),
    path('api/agent/platform/query/', agent_api.PlatformQueryAPIView.as_view(), name='agent_platform_query'),
    path('api/agent/tasks/search/', agent_api.SearchTasksAPIView.as_view(), name='agent_tasks_search'),
    path('api/agent/tasks/videos/', agent_api.SearchTaskVideosAPIView.as_view(), name='agent_task_videos'),
    path('api/agent/hardware/import/validate/', agent_api.ValidateHardwareImportAPIView.as_view(), name='agent_hardware_import_validate'),
    path('api/agent/hardware/import/commit/', agent_api.CommitHardwareImportAPIView.as_view(), name='agent_hardware_import_commit'),

    # Agent Console
    path('agent/', views.AgentAssistantView.as_view(), name='agent_console'),
    path('agent/chat/', views.AgentChatProxyView.as_view(), name='agent_chat_proxy'),

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
