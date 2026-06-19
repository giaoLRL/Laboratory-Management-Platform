from functools import cache

from django.utils.translation import gettext_lazy as _

from netbox.registry import registry

from . import *

#
# Nav menus
#

PROVISIONING_MENU = Menu(
    label=_('Provisioning'),
    icon_class='mdi mdi-file-document-multiple-outline',
    groups=(
        MenuGroup(
            label=_('Configurations'),
            items=(
                get_model_item('extras', 'configcontext', _('Config Contexts'), actions=['add']),
                get_model_item('extras', 'configcontextprofile', _('Config Context Profiles')),
                get_model_item('extras', 'configtemplate', _('Config Templates'), actions=['add']),
            ),
        ),
    ),
)

CUSTOMIZATION_MENU = Menu(
    label=_('Customization'),
    icon_class='mdi mdi-toolbox-outline',
    groups=(
        MenuGroup(
            label=_('Customization'),
            items=(
                get_model_item('extras', 'customfield', _('Custom Fields')),
                get_model_item('extras', 'customfieldchoiceset', _('Custom Field Choices')),
                get_model_item('extras', 'customlink', _('Custom Links')),
                get_model_item('extras', 'exporttemplate', _('Export Templates')),
                get_model_item('extras', 'savedfilter', _('Saved Filters')),
                get_model_item('extras', 'tableconfig', _('Table Configs'), actions=()),
                get_model_item('extras', 'tag', 'Tags'),
                get_model_item('extras', 'imageattachment', _('Image Attachments'), actions=()),
            ),
        ),
        MenuGroup(
            label=_('Scripts'),
            items=(
                MenuItem(
                    link='extras:script_list',
                    link_text=_('Scripts'),
                    permissions=['extras.view_script'],
                    buttons=get_model_buttons('extras', "scriptmodule", actions=['add'])
                ),
            ),
        ),
    ),
)

OPERATIONS_MENU = Menu(
    label=_('Operations'),
    icon_class='mdi mdi-cogs',
    groups=(
        MenuGroup(
            label=_('Integrations'),
            items=(
                get_model_item('core', 'datasource', _('Data Sources')),
                get_model_item('extras', 'eventrule', _('Event Rules')),
                get_model_item('extras', 'webhook', _('Webhooks')),
            ),
        ),
        MenuGroup(
            label=_('Jobs'),
            items=(
                MenuItem(
                    link='core:job_list',
                    link_text=_('Jobs'),
                    permissions=['core.view_job'],
                ),
            ),
        ),
        MenuGroup(
            label=_('Logging'),
            items=(
                get_model_item('extras', 'notificationgroup', _('Notification Groups')),
                get_model_item('extras', 'journalentry', _('Journal Entries'), actions=['bulk_import']),
                get_model_item('core', 'objectchange', _('Change Log'), actions=[]),
            ),
        ),
    ),
)

ADMIN_MENU = Menu(
    label=_('Admin'),
    icon_class='mdi mdi-account-multiple',
    groups=(
        MenuGroup(
            label=_('Authentication'),
            items=(
                get_model_item('users', 'user', _('Users')),
                get_model_item('users', 'group', _('Groups')),
                get_model_item('users', 'token', _('API Tokens')),
                get_model_item('users', 'objectpermission', _('Permissions'), actions=['add']),
            ),
        ),
        MenuGroup(
            label=_('Ownership'),
            items=(
                get_model_item('users', 'ownergroup', _('Owner Groups')),
                get_model_item('users', 'owner', _('Owners')),
            ),
        ),
        MenuGroup(
            label=_('System'),
            items=(
                MenuItem(
                    link='core:system',
                    link_text=_('System'),
                    staff_only=True,
                ),
                MenuItem(
                    link='core:plugin_list',
                    link_text=_('Plugins'),
                    staff_only=True,
                ),
                MenuItem(
                    link='core:configrevision_list',
                    link_text=_('Configuration History'),
                    staff_only=True,
                    permissions=['core.view_configrevision'],
                ),
                MenuItem(
                    link='core:background_queue_list',
                    link_text=_('Background Tasks'),
                    staff_only=True,
                ),
            ),
        ),
    ),
)


@cache
def get_menus():
    """
    Dynamically build and return the list of navigation menus.
    This ensures plugin menus registered during app initialization are included.
    The result is cached since menus don't change without a Django restart.
    """
    menus = [
        PROVISIONING_MENU,
        CUSTOMIZATION_MENU,
        OPERATIONS_MENU,
    ]

    # Add top-level plugin menus
    menus.extend(registry['plugins'].get('menus', []))

    # Add admin menu for staff users
    menus.append(ADMIN_MENU)

    return menus
