from netbox.search import SearchIndex, register_search

from . import models


@register_search
class HardwareIndex(SearchIndex):
    model = models.Hardware
    fields = (
        ('name', 100),
        ('model_number', 80),
        ('manufacturer', 60),
        ('remarks', 300),
        ('storage_location', 50),
    )
    display_attrs = ('category', 'status', 'manufacturer')


@register_search
class TaskIndex(SearchIndex):
    model = models.Task
    fields = (
        ('title', 100),
        ('description', 500),
        ('completion_note', 300),
    )
    display_attrs = ('status', 'priority', 'assigned_to')


@register_search
class AgentToolIndex(SearchIndex):
    model = models.AgentTool
    fields = (
        ('name', 100),
        ('display_name', 100),
        ('description', 300),
    )
    display_attrs = ('tool_type', 'category', 'is_enabled')


@register_search
class LabProjectIndex(SearchIndex):
    model = models.LabProject
    fields = (
        ('name', 100),
        ('description', 500),
    )
    display_attrs = ('status', 'leader')


@register_search
class CheckInRecordIndex(SearchIndex):
    model = models.CheckInRecord
    fields = (
        ('address', 80),
        ('note', 300),
    )
    display_attrs = ('user', 'address', 'created')
