import csv
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from attendance.models import Student


class Command(BaseCommand):
    help = 'Import students from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file')

    def handle(self, *args, **opts):
        created = skipped = 0
        with open(opts['csv_file'], newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                roll = row['roll_no'].strip()
                username = row['username'].strip()
                if User.objects.filter(username=username).exists() or \
                   Student.objects.filter(roll_no=roll).exists():
                    skipped += 1
                    self.stdout.write(f'Skipped {username} ({roll}): already exists')
                    continue
                user = User.objects.create_user(
                    username=username,
                    password=row['password'].strip(),
                    first_name=row.get('first_name', '').strip(),
                    last_name=row.get('last_name', '').strip(),
                )
                Student.objects.create(user=user, roll_no=roll)
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Done. Added {created}, skipped {skipped}.'))