import io
from datetime import timedelta

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from .geo import haversine_m
from .models import Student, ClassSession, Attendance

# Faculty (teachers) are users with is_staff=True. The admin is a superuser.
teacher_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url='/login/')
admin_required = user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='/login/')


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid_coords(lat, lng):
    return lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180


def home(request):
    return render(request, 'attendance/landing.html')


@login_required
def dashboard(request):
    if request.user.is_superuser:
        return redirect('admin_home')
    if request.user.is_staff:
        return redirect('session_list')
    return redirect('my_attendance')


# ---------------------------------------------------------------- faculty

@teacher_required
def session_list(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip() or 'Class'
        room = request.POST.get('room_name', '').strip()
        lat = _float(request.POST.get('latitude'))
        lng = _float(request.POST.get('longitude'))
        try:
            minutes = int(request.POST.get('minutes', 10))
            radius = int(request.POST.get('radius_m', 5))
        except ValueError:
            minutes, radius = 10, 5
        radius = max(1, min(radius, 500))

        if not _valid_coords(lat, lng):
            messages.error(request, 'Room location is missing. Tap "Use my current location" '
                                    'while you are in the classroom, then try again.')
            return redirect('session_list')

        session = ClassSession.objects.create(
            title=title, room_name=room, latitude=lat, longitude=lng, radius_m=radius,
            created_by=request.user, expires_at=timezone.now() + timedelta(minutes=minutes),
        )
        return redirect('session_detail', token=session.token)

    sessions = ClassSession.objects.order_by('-created_at')
    return render(request, 'attendance/session_list.html', {'sessions': sessions})


@teacher_required
def session_detail(request, token):
    session = get_object_or_404(ClassSession, token=token)
    records = Attendance.objects.filter(session=session).select_related('student__user')
    return render(request, 'attendance/session_detail.html', {'session': session, 'records': records})


@teacher_required
def session_qr(request, token):
    session = get_object_or_404(ClassSession, token=token)
    url = request.build_absolute_uri(reverse('mark', args=[session.token]))
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


@teacher_required
def student_list_faculty(request):
    students = Student.objects.select_related('user').order_by('roll_no')
    return render(request, 'attendance/faculty_students.html', {'students': students})


# ---------------------------------------------------------------- student

@login_required
def mark_attendance(request, token):
    """GET shows a page that asks the phone for its location.
    POST receives the coordinates and checks the distance on the server."""
    session = get_object_or_404(ClassSession, token=token)
    student = Student.objects.filter(user=request.user).first()

    if not student:
        messages.error(request, 'Your account is not linked to a student profile.')
        return redirect('my_attendance')
    if not session.is_active():
        messages.error(request, 'This QR code has expired.')
        return redirect('my_attendance')
    if Attendance.objects.filter(student=student, session=session).exists():
        messages.info(request, 'You already marked attendance for this session.')
        return redirect('my_attendance')

    if request.method == 'POST':
        lat = _float(request.POST.get('latitude'))
        lng = _float(request.POST.get('longitude'))
        if not _valid_coords(lat, lng):
            messages.error(request, 'We could not read your location. Turn on location and try again.')
            return redirect('mark', token=token)

        if session.has_location():
            distance = haversine_m(lat, lng, session.latitude, session.longitude)
            if distance > session.radius_m:
                messages.error(request, f'You are about {distance:.0f} m from the classroom. '
                                        f'You must be within {session.radius_m} m to mark attendance.')
                return redirect('mark', token=token)
        else:
            distance = None

        try:
            with transaction.atomic():
                Attendance.objects.create(student=student, session=session,
                                          latitude=lat, longitude=lng, distance_m=distance)
        except IntegrityError:
            messages.info(request, 'You already marked attendance for this session.')
            return redirect('my_attendance')
        messages.success(request, f'Attendance marked for {session.title}.')
        return redirect('my_attendance')

    return render(request, 'attendance/mark.html', {'session': session})


@login_required
def my_attendance(request):
    student = Student.objects.filter(user=request.user).first()
    records = []
    if student:
        records = Attendance.objects.filter(student=student).select_related('session').order_by('-marked_at')
    return render(request, 'attendance/my_attendance.html', {'records': records})


# ---------------------------------------------------------------- admin panel

@admin_required
def admin_home(request):
    context = {
        'faculty_count': User.objects.filter(is_staff=True, is_superuser=False).count(),
        'student_count': Student.objects.count(),
        'session_count': ClassSession.objects.count(),
        'attendance_count': Attendance.objects.count(),
        'recent': Attendance.objects.select_related('student__user', 'session').order_by('-marked_at')[:8],
    }
    return render(request, 'attendance/admin_home.html', context)


def _faculty_qs():
    return User.objects.filter(is_staff=True, is_superuser=False).order_by('first_name', 'username')


@admin_required
def faculty_list(request):
    q = request.GET.get('q', '').strip()
    faculty = _faculty_qs()
    if q:
        faculty = faculty.filter(Q(username__icontains=q) | Q(first_name__icontains=q) |
                                 Q(last_name__icontains=q) | Q(email__icontains=q))
    return render(request, 'attendance/faculty_list.html', {'faculty': faculty, 'q': q})


@admin_required
def faculty_add(request):
    data = {}
    if request.method == 'POST':
        data = {k: request.POST.get(k, '').strip() for k in ('first_name', 'last_name', 'username', 'email')}
        password = request.POST.get('password', '')
        if not data['username'] or not password:
            messages.error(request, 'Username and password are required.')
        elif len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
        elif User.objects.filter(username__iexact=data['username']).exists():
            messages.error(request, 'That username is already taken.')
        else:
            user = User.objects.create_user(password=password, is_staff=True, **data)
            messages.success(request, f'Faculty {user.get_full_name() or user.username} added.')
            return redirect('faculty_list')
    return render(request, 'attendance/faculty_form.html', {'data': data, 'editing': False})


@admin_required
def faculty_edit(request, pk):
    user = get_object_or_404(_faculty_qs(), pk=pk)
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email', '').strip()
        new_password = request.POST.get('password', '')
        if new_password and len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
        else:
            if new_password:
                user.set_password(new_password)
            user.save()
            messages.success(request, 'Faculty updated.')
            return redirect('faculty_list')
    return render(request, 'attendance/faculty_form.html', {'data': user, 'editing': True})


@admin_required
def faculty_delete(request, pk):
    user = get_object_or_404(_faculty_qs(), pk=pk)
    if request.method == 'POST':
        name = user.get_full_name() or user.username
        user.delete()
        messages.success(request, f'Faculty {name} deleted.')
        return redirect('faculty_list')
    return render(request, 'attendance/confirm_delete.html', {
        'what': 'faculty member', 'name': user.get_full_name() or user.username,
        'note': 'Their class sessions and the attendance recorded in them will be deleted too.',
        'back': 'faculty_list'})


@admin_required
def student_list(request):
    q = request.GET.get('q', '').strip()
    students = Student.objects.select_related('user').order_by('roll_no')
    if q:
        students = students.filter(Q(roll_no__icontains=q) | Q(user__username__icontains=q) |
                                   Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q))
    return render(request, 'attendance/student_list.html', {'students': students, 'q': q})


@admin_required
def student_add(request):
    data = {}
    if request.method == 'POST':
        data = {k: request.POST.get(k, '').strip() for k in ('first_name', 'last_name', 'username', 'roll_no')}
        password = request.POST.get('password', '')
        if not data['username'] or not data['roll_no'] or not password:
            messages.error(request, 'Roll number, username and password are required.')
        elif len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
        elif User.objects.filter(username__iexact=data['username']).exists():
            messages.error(request, 'That username is already taken.')
        elif Student.objects.filter(roll_no__iexact=data['roll_no']).exists():
            messages.error(request, 'That roll number already exists.')
        else:
            with transaction.atomic():
                user = User.objects.create_user(username=data['username'], password=password,
                                                first_name=data['first_name'], last_name=data['last_name'])
                Student.objects.create(user=user, roll_no=data['roll_no'])
            messages.success(request, f'Student {data["roll_no"]} added.')
            return redirect('student_list')
    return render(request, 'attendance/student_form.html', {'data': data})


@admin_required
def student_delete(request, pk):
    student = get_object_or_404(Student.objects.select_related('user'), pk=pk)
    if request.method == 'POST':
        label = student.roll_no
        student.user.delete()  # cascades to the Student row and their attendance
        messages.success(request, f'Student {label} deleted.')
        return redirect('student_list')
    return render(request, 'attendance/confirm_delete.html', {
        'what': 'student', 'name': f'{student.roll_no} - {student.user.get_full_name() or student.user.username}',
        'note': 'Their attendance records will be deleted too.', 'back': 'student_list'})


@admin_required
def attendance_all(request):
    session_id = request.GET.get('session', '')
    records = Attendance.objects.select_related('student__user', 'session').order_by('-marked_at')
    if session_id.isdigit():
        records = records.filter(session_id=int(session_id))
    sessions = ClassSession.objects.annotate(n=Count('attendance')).order_by('-created_at')
    return render(request, 'attendance/attendance_all.html', {
        'records': records, 'sessions': sessions, 'selected': session_id})
