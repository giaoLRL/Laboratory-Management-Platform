from netbox.api.serializers import NetBoxModelSerializer

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


class HardwareSerializer(NetBoxModelSerializer):
    class Meta:
        model = Hardware
        fields = (
            'id', 'display', 'name', 'category', 'model_number',
            'manufacturer', 'quantity', 'unit_price', 'purchase_date',
            'purchase_link', 'status', 'storage_location', 'custodian',
            'image', 'invoice_image', 'remarks', 'submitted_by',
            'approval_status', 'approved_by', 'approval_note',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'name', 'category', 'status', 'approval_status')


class TaskSerializer(NetBoxModelSerializer):
    class Meta:
        model = Task
        fields = (
            'id', 'display', 'title', 'description', 'priority',
            'status', 'created_by', 'assigned_to', 'deadline',
            'completed_at', 'completion_note',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'title', 'status', 'priority', 'assigned_to')


class TaskCommentSerializer(NetBoxModelSerializer):
    class Meta:
        model = TaskComment
        fields = (
            'id', 'display', 'task', 'user', 'content',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'user', 'content')


class TaskAttachmentSerializer(NetBoxModelSerializer):
    class Meta:
        model = TaskAttachment
        fields = (
            'id', 'display', 'task', 'file', 'uploaded_by', 'remark',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'file', 'uploaded_by')


class CheckInRecordSerializer(NetBoxModelSerializer):
    class Meta:
        model = CheckInRecord
        fields = (
            'id', 'display', 'user', 'photo', 'latitude', 'longitude',
            'accuracy', 'address', 'note',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'user', 'created', 'latitude', 'longitude', 'address')


class MemberOpenRecordSerializer(NetBoxModelSerializer):
    class Meta:
        model = MemberOpenRecord
        fields = (
            'id', 'display', 'user', 'path', 'page_title',
            'target_type', 'target_id', 'user_agent', 'ip_address',
            'photo', 'latitude', 'longitude', 'accuracy', 'address', 'note',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'user', 'page_title', 'path', 'created')


class HardwareImportBatchSerializer(NetBoxModelSerializer):
    class Meta:
        model = HardwareImportBatch
        fields = (
            'id', 'display', 'batch_id', 'created_by',
            'source_type', 'status', 'raw_payload', 'validated_payload',
            'result_summary', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'batch_id', 'source_type', 'status')


class AgentToolSerializer(NetBoxModelSerializer):
    class Meta:
        model = AgentTool
        fields = (
            'id', 'display', 'name', 'display_name', 'description',
            'tool_type', 'category', 'is_enabled',
            'parameters_schema', 'execution_key', 'default_args',
            'requires_superuser', 'sort_order',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'name', 'display_name', 'tool_type', 'category', 'is_enabled')


class LabProjectSerializer(NetBoxModelSerializer):
    class Meta:
        model = LabProject
        fields = (
            'id', 'display', 'name', 'description', 'status',
            'leader', 'members', 'start_date', 'end_date',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'name', 'status', 'leader')


class HardwareBorrowRecordSerializer(NetBoxModelSerializer):
    class Meta:
        model = HardwareBorrowRecord
        fields = (
            'id', 'display', 'hardware', 'borrower',
            'borrow_date', 'expected_return_date', 'actual_return_date',
            'status', 'purpose', 'notes',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'hardware', 'borrower', 'status', 'borrow_date')


class AgentConversationSerializer(NetBoxModelSerializer):
    class Meta:
        model = AgentConversation
        fields = (
            'id', 'display', 'user', 'title', 'mode',
            'workflow_alias', 'coze_conversation_id', 'last_message_preview',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'title', 'mode', 'user', 'last_updated')


class AgentMessageSerializer(NetBoxModelSerializer):
    class Meta:
        model = AgentMessage
        fields = (
            'id', 'display', 'conversation', 'role', 'content',
            'raw_payload', 'coze_chat_id',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'display', 'role', 'content', 'created')
