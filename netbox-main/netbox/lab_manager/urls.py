from django.urls import include, path

from . import agent_api, views
from .api import urls as api_urls
from utilities.urls import get_model_urls

app_name = 'lab_manager'

urlpatterns = [
    # REST API (DRF)
    path('api/', include(api_urls)),

    # Agent API
    path('api/agent/hardware/search/', agent_api.SearchHardwareAPIView.as_view(), name='agent_hardware_search'),
    path('api/agent/hardware/gap-analysis/', agent_api.AnalyzeHardwareGapAPIView.as_view(), name='agent_hardware_gap_analysis'),
    path('api/agent/members/search/', agent_api.SearchMembersAPIView.as_view(), name='agent_members_search'),
    path('api/agent/platform/query/', agent_api.PlatformQueryAPIView.as_view(), name='agent_platform_query'),
    path('api/agent/tasks/search/', agent_api.SearchTasksAPIView.as_view(), name='agent_tasks_search'),
    path('api/agent/tasks/create/', agent_api.CreateTaskAPIView.as_view(), name='agent_task_create'),
    path('api/agent/tasks/videos/', agent_api.SearchTaskVideosAPIView.as_view(), name='agent_task_videos'),
    path('api/agent/checkins/search/', agent_api.SearchCheckInsAPIView.as_view(), name='agent_checkin_search'),
    path('api/agent/member-open-records/search/', agent_api.SearchMemberOpenRecordsAPIView.as_view(), name='agent_member_open_records_search'),
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
    path('member-open-records/', views.MemberOpenRecordListView.as_view(), name='member_open_records'),
    path('member-open-records/<int:pk>/', views.MemberOpenRecordDetailView.as_view(), name='member_open_record_detail'),

    # 拍照定位打卡
    path('checkins/', views.CheckInListView.as_view(), name='checkin_list'),
    path('checkins/new/', views.CheckInCreateView.as_view(), name='checkin_create'),
    path('checkins/<int:pk>/', views.CheckInDetailView.as_view(), name='checkin_detail'),

    # 附件上传
    path('tasks/<int:pk>/upload/', views.TaskUploadAttachmentView.as_view(), name='task_upload'),

    # 标记完成
    path('tasks/<int:pk>/complete/', views.TaskCompleteView.as_view(), name='task_complete'),

    # 评论
    path('tasks/<int:pk>/comment/', views.TaskCommentView.as_view(), name='task_comment'),

    # 删除附件
    path('attachments/<int:pk>/delete/', views.TaskAttachmentDeleteView.as_view(), name='task_attachment_delete'),

    # 硬件借出/归还
    path('borrow-records/', include(get_model_urls('lab_manager', 'hardwareborrowrecord', detail=False))),
    path('borrow-records/<int:pk>/', include(get_model_urls('lab_manager', 'hardwareborrowrecord'))),
    path('borrow-records/<int:pk>/return/', views.HardwareBorrowReturnView.as_view(), name='borrow_return'),

    # 实验项目管理
    path('projects/', include(get_model_urls('lab_manager', 'labproject', detail=False))),
    path('projects/<int:pk>/', include(get_model_urls('lab_manager', 'labproject'))),

    # 智能体工具管理（管理员）
    path('agent-tools/', include(get_model_urls('lab_manager', 'agenttool', detail=False))),
    path('agent-tools/<int:pk>/', include(get_model_urls('lab_manager', 'agenttool'))),

    # 站内通知
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/send/', views.NotificationSendView.as_view(), name='notification_send'),
    path('notifications/read-all/', views.NotificationMarkReadView.as_view(), name='notification_read_all'),
    path('notifications/<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification_read'),

    # 任务日历
    path('calendar/', views.TaskCalendarView.as_view(), name='calendar'),

    # 数据导出
    path('export/', views.ExportDataView.as_view(), name='export_data'),

    # 成员管理
    path('members/', views.MemberListView.as_view(), name='member_list'),
    path('members/<int:pk>/', views.MemberDetailView.as_view(), name='member_detail'),

    # 实验室首页
    path('', views.LabHomeView.as_view(), name='home'),
]
