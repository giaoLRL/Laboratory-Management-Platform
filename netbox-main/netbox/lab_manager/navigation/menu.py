from netbox.plugins.navigation import PluginMenu, PluginMenuItem, PluginMenuButton

menu = PluginMenu(
    label='实验室',
    icon_class='mdi mdi-flask',
    groups=(
        ('硬件管理', (
            PluginMenuItem(
                link='plugins:lab_manager:hardware_list',
                link_text='硬件列表',
                buttons=(
                    PluginMenuButton(
                        link='plugins:lab_manager:hardware_add',
                        title='录入硬件',
                        icon_class='mdi mdi-plus-thick',
                    ),
                )
            ),
        )),
        ('任务管理', (
            PluginMenuItem(
                link='plugins:lab_manager:task_list',
                link_text='全部任务',
                buttons=(
                    PluginMenuButton(
                        link='plugins:lab_manager:task_add',
                        title='创建任务',
                        icon_class='mdi mdi-plus-thick',
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:lab_manager:my_tasks',
                link_text='我的任务',
            ),
        )),
        ('打卡管理', (
            PluginMenuItem(
                link='plugins:lab_manager:checkin_create',
                link_text='拍照定位打卡',
                buttons=(
                    PluginMenuButton(
                        link='plugins:lab_manager:checkin_list',
                        title='打卡记录',
                        icon_class='mdi mdi-format-list-bulleted',
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:lab_manager:member_open_records',
                link_text='成员打卡记录',
            ),
        )),
        ('智能体', (
            PluginMenuItem(
                link='plugins:lab_manager:agent_console',
                link_text='智能体助手',
            ),
        )),
    ),
)
