from django.urls import path

from apps.tasksapp import api

urlpatterns = [
    path('tasks', api.tasks_create),
    path('tasks/batch', api.tasks_batch),
    path('tasks/<str:tid>/detail', api.tasks_detail),
    path('tasks/<str:tid>/update', api.tasks_update),
    path('tasks/<str:tid>/submit', api.tasks_submit),
    path('tasks/<str:tid>/review', api.tasks_review),
    path('tasks/<str:tid>/delete', api.tasks_delete),
    path('tasks/<str:tid>/score', api.tasks_score),
    path('tasks/<str:tid>/attachment', api.tasks_attachment),
]
