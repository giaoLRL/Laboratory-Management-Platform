from django.urls import path

from apps.tasksapp import api

urlpatterns = [
    path('tasks', api.tasks_create),
    path('tasks/<str:tid>/update', api.tasks_update),
    path('tasks/<str:tid>/delete', api.tasks_delete),
    path('tasks/<str:tid>/attachment', api.tasks_attachment),
]
