from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Student, ClassSession, Attendance


class StudentInline(admin.StackedInline):
    model = Student
    can_delete = False
    extra = 1
    verbose_name_plural = 'Student profile (roll number)'


class CustomUserAdmin(UserAdmin):
    inlines = [StudentInline]
    list_display = ('username', 'first_name', 'last_name', 'is_staff')


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('roll_no', 'user')
    search_fields = ('roll_no', 'user__username', 'user__first_name')


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'room_name', 'created_by', 'created_at', 'expires_at', 'radius_m')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'marked_at', 'distance_m')
    list_filter = ('session',)