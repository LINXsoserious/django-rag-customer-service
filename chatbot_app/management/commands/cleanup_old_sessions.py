from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from chatbot_app.models import ChatSession


class Command(BaseCommand):
    help = "Preview old conversations; pass --apply to delete them and related records."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--apply", action="store_true", help="Actually delete matching conversations.")
        group.add_argument("--dry-run", action="store_true", help="Preview only (the default).")

    def handle(self, *args, **options):
        days = options["days"]
        if days <= 0:
            raise CommandError("--days must be greater than zero.")
        sessions = ChatSession.objects.filter(updated_at__lt=timezone.now() - timedelta(days=days))
        count = sessions.count()
        if options["apply"]:
            sessions.delete()
            self.stdout.write(f"Deleted {count} conversation(s) inactive for more than {days} days.")
        else:
            self.stdout.write(f"Dry-run: {count} conversation(s) inactive for more than {days} days; pass --apply to delete.")
