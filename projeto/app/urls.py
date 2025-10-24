# projeto/urls.py
from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),  # sua página com o formulário
    path('upload/', views.upload, name='upload'),
    path('status/<str:job_id>/', views.status, name='status'),
    path('download/<str:job_id>/', views.download, name='download'),
]
