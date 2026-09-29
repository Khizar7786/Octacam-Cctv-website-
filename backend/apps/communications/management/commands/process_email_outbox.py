import time

from django.core.management.base import BaseCommand, CommandError

from apps.communications.services import process_email_batch


class Command(BaseCommand):
    help = "Deliver due email outbox events; run continuously or once for local testing."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process one batch and exit.")
        parser.add_argument("--batch-size", type=int, default=20)
        parser.add_argument("--poll-seconds", type=float, default=5)

    def handle(self, *args, **options):
        if options["batch_size"] < 1 or options["poll_seconds"] <= 0:
            raise CommandError("Batch size and poll seconds must be positive")
        while True:
            outcomes = process_email_batch(limit=options["batch_size"])
            if outcomes:
                self.stdout.write(f"Email outbox: {outcomes.count('sent')} sent, {outcomes.count('failed')} failed")
            if options["once"]:
                return
            time.sleep(options["poll_seconds"])
