from django import forms
from django.contrib.postgres.forms import SimpleArrayField
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from netaddr import IPNetwork, AddrFormatError

# IPNetworkFormField stub (ipam module removed)
class IPNetworkFormField(forms.CharField):
    def validate(self, value):
        super().validate(value)
        if value:
            try:
                IPNetwork(value)
            except AddrFormatError:
                raise ValidationError(_('Enter a valid IP network.'))

def prefix_validator(value):
    """Validate that the value is a valid IP prefix."""
    try:
        IPNetwork(value)
    except AddrFormatError:
        raise ValidationError(_('%(value)s is not a valid IP prefix.') % {'value': value})

from users.models import *
from utilities.forms import BulkEditForm
from utilities.forms.fields import DynamicModelChoiceField
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import BulkEditNullBooleanSelect, DateTimePicker

__all__ = (
    'GroupBulkEditForm',
    'ObjectPermissionBulkEditForm',
    'OwnerBulkEditForm',
    'OwnerGroupBulkEditForm',
    'TokenBulkEditForm',
    'UserBulkEditForm',
)


class UserBulkEditForm(BulkEditForm):
    pk = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.MultipleHiddenInput
    )
    first_name = forms.CharField(
        label=_('First name'),
        max_length=150,
        required=False
    )
    last_name = forms.CharField(
        label=_('Last name'),
        max_length=150,
        required=False
    )
    is_active = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect,
        label=_('Active')
    )
    is_superuser = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect,
        label=_('Superuser status')
    )

    model = User
    fieldsets = (
        FieldSet('first_name', 'last_name', 'is_active', 'is_superuser'),
    )
    nullable_fields = ('first_name', 'last_name')


class GroupBulkEditForm(BulkEditForm):
    pk = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.MultipleHiddenInput
    )
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False
    )

    model = User
    fieldsets = (
        FieldSet('description'),
    )
    nullable_fields = ('description',)


class ObjectPermissionBulkEditForm(BulkEditForm):
    pk = forms.ModelMultipleChoiceField(
        queryset=ObjectPermission.objects.all(),
        widget=forms.MultipleHiddenInput
    )
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False
    )
    enabled = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect,
        label=_('Enabled')
    )

    model = ObjectPermission
    fieldsets = (
        FieldSet('enabled', 'description'),
    )
    nullable_fields = ('description',)


class TokenBulkEditForm(BulkEditForm):
    pk = forms.ModelMultipleChoiceField(
        queryset=Token.objects.all(),
        widget=forms.MultipleHiddenInput
    )
    enabled = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect,
        label=_('Enabled')
    )
    write_enabled = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect,
        label=_('Write enabled')
    )
    description = forms.CharField(
        max_length=200,
        required=False,
        label=_('Description')
    )
    expires = forms.DateTimeField(
        required=False,
        widget=DateTimePicker(),
        label=_('Expires')
    )
    allowed_ips = SimpleArrayField(
        base_field=IPNetworkFormField(validators=[prefix_validator]),
        required=False,
        label=_('Allowed IPs')
    )

    model = Token
    fieldsets = (
        FieldSet('enabled', 'write_enabled', 'description', 'expires', 'allowed_ips'),
    )
    nullable_fields = (
        'expires', 'description', 'allowed_ips',
    )


class OwnerGroupBulkEditForm(BulkEditForm):
    pk = forms.ModelMultipleChoiceField(
        queryset=OwnerGroup.objects.all(),
        widget=forms.MultipleHiddenInput
    )
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False
    )

    model = OwnerGroup
    fieldsets = (
        FieldSet('description',),
    )
    nullable_fields = ('description',)


class OwnerBulkEditForm(BulkEditForm):
    pk = forms.ModelMultipleChoiceField(
        queryset=Owner.objects.all(),
        widget=forms.MultipleHiddenInput
    )
    group = DynamicModelChoiceField(
        label=_('Group'),
        queryset=OwnerGroup.objects.all(),
        required=False
    )
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False
    )

    model = Owner
    fieldsets = (
        FieldSet('group', 'description'),
    )
    nullable_fields = ('group', 'description',)
