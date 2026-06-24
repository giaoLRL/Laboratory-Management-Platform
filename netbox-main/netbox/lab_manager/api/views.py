from rest_framework.routers import APIRootView

from netbox.api.viewsets import NetBoxModelViewSet

from .. import filtersets
from ..models import (
    AgentConversation,
    AgentMessage,
    AgentTool,
    CheckInRecord,
    Hardware,
    HardwareBorrowRecord,
    HardwareImportBatch,
    LabProject,
    MemberOpenRecord,
    Task,
    TaskAttachment,
    TaskComment,
)
from . import serializers


class LabManagerRootView(APIRootView):
    def get_view_name(self):
        return '实验室管理'


class HardwareViewSet(NetBoxModelViewSet):
    queryset = Hardware.objects.prefetch_related('tags')
    serializer_class = serializers.HardwareSerializer
    filterset_class = filtersets.HardwareFilterSet


class TaskViewSet(NetBoxModelViewSet):
    queryset = Task.objects.prefetch_related('tags')
    serializer_class = serializers.TaskSerializer
    filterset_class = filtersets.TaskFilterSet


class TaskCommentViewSet(NetBoxModelViewSet):
    queryset = TaskComment.objects.prefetch_related('tags')
    serializer_class = serializers.TaskCommentSerializer


class TaskAttachmentViewSet(NetBoxModelViewSet):
    queryset = TaskAttachment.objects.prefetch_related('tags')
    serializer_class = serializers.TaskAttachmentSerializer
    filterset_class = filtersets.TaskAttachmentFilterSet


class CheckInRecordViewSet(NetBoxModelViewSet):
    queryset = CheckInRecord.objects.prefetch_related('tags')
    serializer_class = serializers.CheckInRecordSerializer
    filterset_class = filtersets.CheckInRecordFilterSet


class MemberOpenRecordViewSet(NetBoxModelViewSet):
    queryset = MemberOpenRecord.objects.prefetch_related('tags')
    serializer_class = serializers.MemberOpenRecordSerializer
    filterset_class = filtersets.MemberOpenRecordFilterSet


class HardwareImportBatchViewSet(NetBoxModelViewSet):
    queryset = HardwareImportBatch.objects.prefetch_related('tags')
    serializer_class = serializers.HardwareImportBatchSerializer


class AgentToolViewSet(NetBoxModelViewSet):
    queryset = AgentTool.objects.prefetch_related('tags')
    serializer_class = serializers.AgentToolSerializer
    filterset_class = filtersets.AgentToolFilterSet


class LabProjectViewSet(NetBoxModelViewSet):
    queryset = LabProject.objects.prefetch_related('tags')
    serializer_class = serializers.LabProjectSerializer


class HardwareBorrowRecordViewSet(NetBoxModelViewSet):
    queryset = HardwareBorrowRecord.objects.prefetch_related('tags')
    serializer_class = serializers.HardwareBorrowRecordSerializer


class AgentConversationViewSet(NetBoxModelViewSet):
    queryset = AgentConversation.objects.prefetch_related('tags')
    serializer_class = serializers.AgentConversationSerializer


class AgentMessageViewSet(NetBoxModelViewSet):
    queryset = AgentMessage.objects.prefetch_related('tags')
    serializer_class = serializers.AgentMessageSerializer
