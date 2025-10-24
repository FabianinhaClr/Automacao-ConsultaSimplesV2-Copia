# projeto/app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('upload-page/', views.upload_page, name='upload_page'),
    path('upload/', views.upload, name='upload'),
    path('status/<str:job_id>/', views.status, name='status'),
    path('download/<str:job_id>/', views.download, name='download'),
]
