from netbox.api.routers import NetBoxRouter

from . import views

router = NetBoxRouter()
router.APIRootView = views.LabManagerRootView

router.register('hardware', views.HardwareViewSet)
router.register('tasks', views.TaskViewSet)
router.register('task-comments', views.TaskCommentViewSet)
router.register('task-attachments', views.TaskAttachmentViewSet)
router.register('checkin-records', views.CheckInRecordViewSet)
router.register('member-open-records', views.MemberOpenRecordViewSet)
router.register('import-batches', views.HardwareImportBatchViewSet)
router.register('agent-tools', views.AgentToolViewSet)
router.register('projects', views.LabProjectViewSet)
router.register('borrow-records', views.HardwareBorrowRecordViewSet)
router.register('conversations', views.AgentConversationViewSet)
router.register('messages', views.AgentMessageViewSet)

app_name = 'lab_manager-api'
urlpatterns = router.urls
