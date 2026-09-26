from django.urls import path

from apps.homepage import api

urlpatterns = [
    path('homepage', api.homepage_get),
    path('homepage/texts', api.homepage_texts_save),
    path('homepage/images', api.homepage_image_upload),
    path('homepage/images/reset', api.homepage_image_reset),
    path('homepage/frame', api.homepage_frame_save),
    path('homepage/scale', api.homepage_scale_save),
    path('homepage/public', api.homepage_public),
]