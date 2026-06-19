from rest_framework import serializers

from core.api.serializers_.data import DataFileSerializer, DataSourceSerializer
from extras.models import ConfigContext, ConfigContextProfile, Tag
from netbox.api.serializers import ChangeLogMessageSerializer, PrimaryModelSerializer, ValidatedModelSerializer
from users.api.serializers_.mixins import OwnerMixin

__all__ = (
    'ConfigContextProfileSerializer',
    'ConfigContextSerializer',
)


class ConfigContextProfileSerializer(PrimaryModelSerializer):
    data_source = DataSourceSerializer(
        nested=True,
        required=False
    )
    data_file = DataFileSerializer(
        nested=True,
        required=False
    )

    class Meta:
        model = ConfigContextProfile
        fields = [
            'id', 'url', 'display_url', 'display', 'name', 'description', 'schema', 'tags', 'owner', 'comments',
            'data_source', 'data_path', 'data_file', 'data_synced', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'name', 'description')


class ConfigContextSerializer(OwnerMixin, ChangeLogMessageSerializer, ValidatedModelSerializer):
    profile = ConfigContextProfileSerializer(
        nested=True,
        required=False,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = ConfigContext
        fields = [
            'id', 'url', 'display_url', 'display', 'name', 'profile', 'weight', 'description', 'is_active',
            'tags', 'data_source', 'data_path', 'data_file', 'data', 'data_synced',
            'created', 'last_updated', 'owner',
        ]
        brief_fields = ('id', 'url', 'display', 'name', 'description')
