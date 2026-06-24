from django.contrib import admin

from .models import (
    AgentConversation,
    AgentMessage,
    CheckInRecord,
    Hardware,
    HardwareImportBatch,
    MemberOpenRecord,
    Task,
    TaskAttachment,
    TaskComment,
)


@admin.register(Hardware)
class HardwareAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'status', 'approval_status',
        'custodian', 'quantity', 'created',
    )
    list_filter = ('category', 'status', 'approval_status')
    search_fields = ('name', 'model_number', 'manufacturer', 'remarks')
    readonly_fields = ('created', 'last_updated')
    raw_id_fields = ('custodian', 'submitted_by', 'approved_by')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'status', 'priority', 'assigned_to',
        'created_by', 'deadline', 'completed_at',
    )
    list_filter = ('status', 'priority')
    search_fields = ('title', 'description', 'completion_note')
    readonly_fields = ('created', 'last_updated')
    raw_id_fields = ('created_by', 'assigned_to')


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'content_preview', 'created')
    search_fields = ('content',)
    readonly_fields = ('created', 'last_updated')
    raw_id_fields = ('task', 'user')

    @admin.display(description='内容预览')
    def content_preview(self, obj):
        return obj.content[:80]


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ('task', 'file_preview', 'uploaded_by', 'created')
    search_fields = ('remark', 'task__title')
    readonly_fields = ('created', 'last_updated')
    raw_id_fields = ('task', 'uploaded_by')

    @admin.display(description='文件名')
    def file_preview(self, obj):
        return obj.file.name if obj.file else ''


@admin.register(CheckInRecord)
class CheckInRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'created', 'latitude', 'longitude', 'accuracy', 'address')
    list_filter = ('created',)
    search_fields = ('user__username', 'user__first_name', 'address', 'note')
    readonly_fields = ('created', 'last_updated')
    raw_id_fields = ('user',)


@admin.register(MemberOpenRecord)
class MemberOpenRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'page_title', 'path', 'target_type', 'created')
    list_filter = ('target_type', 'created')
    search_fields = ('user__username', 'page_title', 'path')
    readonly_fields = ('created', 'last_updated')
    raw_id_fields = ('user',)


@admin.register(AgentConversation)
class AgentConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'mode', 'last_message_preview', 'last_updated')
    list_filter = ('mode',)
    search_fields = ('title', 'user__username')
    readonly_fields = ('created', 'last_updated')
    raw_id_fields = ('user',)


@admin.register(AgentMessage)
class AgentMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'content_preview', 'created')
    list_filter = ('role',)
    search_fields = ('content',)
    readonly_fields = ('created', 'last_updated')
    raw_id_fields = ('conversation',)

    @admin.display(description='内容预览')
    def content_preview(self, obj):
        return obj.content[:100]


@admin.register(HardwareImportBatch)
class HardwareImportBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_id', 'source_type', 'status', 'created_by', 'created')
    list_filter = ('source_type', 'status')
    search_fields = ('batch_id',)
    readonly_fields = ('created', 'last_updated', 'batch_id')
    raw_id_fields = ('created_by',)
