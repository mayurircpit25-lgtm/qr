from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    roll_no = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.roll_no} - {self.user.get_full_name() or self.user.username}"


class ClassSession(models.Model):
    title = models.CharField(max_length=100)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    # Location of the classroom (set by the teacher when the session starts)
    room_name = models.CharField(max_length=50, blank=True, default='')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    radius_m = models.PositiveIntegerField(default=5)  # allowed distance in metres

    def is_active(self):
        return timezone.now() <= self.expires_at

    def has_location(self):
        return self.latitude is not None and self.longitude is not None

    def __str__(self):
        return self.title


class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE)
    marked_at = models.DateTimeField(auto_now_add=True)

    # Where the student was when they scanned
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    distance_m = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'session')

    def __str__(self):
        return f"{self.student} - {self.session}"
