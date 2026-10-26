from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='attendance/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # faculty
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/<uuid:token>/', views.session_detail, name='session_detail'),
    path('sessions/<uuid:token>/qr.png', views.session_qr, name='session_qr'),
    path('my-students/', views.student_list_faculty, name='faculty_students'),

    # student
    path('mark/<uuid:token>/', views.mark_attendance, name='mark'),
    path('my-attendance/', views.my_attendance, name='my_attendance'),

    # admin panel (custom, not Django's /admin/)
    path('panel/', views.admin_home, name='admin_home'),
    path('panel/faculty/', views.faculty_list, name='faculty_list'),
    path('panel/faculty/add/', views.faculty_add, name='faculty_add'),
    path('panel/faculty/<int:pk>/edit/', views.faculty_edit, name='faculty_edit'),
    path('panel/faculty/<int:pk>/delete/', views.faculty_delete, name='faculty_delete'),
    path('panel/students/', views.student_list, name='student_list'),
    path('panel/students/add/', views.student_add, name='student_add'),
    path('panel/students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    path('panel/attendance/', views.attendance_all, name='attendance_all'),
]
