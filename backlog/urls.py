from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('backlog/', views.backlog_list, name='backlog'),
    path('ec/kria/', views.ec_create, name='ec_create'),
    path('ec/<str:esc_code>/', views.ec_detail, name='ec_detail'),
    path('ec/<str:esc_code>/aprova/', views.ec_approve, name='ec_approve'),
    path('ec/<str:esc_code>/rejeita/', views.ec_reject, name='ec_reject'),
    path('ec/<str:esc_code>/revisa/', views.ec_revise, name='ec_revise'),
    path('ec/<str:esc_code>/reassign/', views.ec_reassign, name='ec_reassign'),
    path('ec/<str:esc_code>/cancel/', views.ec_cancel, name='ec_cancel'),
    path('ec/<str:esc_code>/prd/', views.ec_set_prd, name='ec_set_prd'),
    path('release/', views.release_list, name='release_list'),
    path('release/<str:release_code>/', views.release_detail, name='release_detail'),
    path('users/', views.user_list, name='user_list'),
]