from django.core.management.base import BaseCommand
from django.db import transaction
from ticketsapp.models import Ticket, generate_ticket_id


class Command(BaseCommand):
    help = (
        "Backfill random, unique ticket_id for existing tickets that are missing "
        "or have an invalid value."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        updated = 0
        examined = 0

        for ticket in Ticket.objects.all().only("id", "ticket_id"):
            examined += 1
            current = (ticket.ticket_id or "").strip()

            # Consider missing, empty, or very short values as invalid
            if not current or len(current) < 6:
                new_code = generate_ticket_id()
                # Ensure uniqueness even if DB already has many records
                while Ticket.objects.filter(ticket_id=new_code).exists():
                    new_code = generate_ticket_id()

                ticket.ticket_id = new_code
                ticket.save(update_fields=["ticket_id"])
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Examined {examined} tickets; backfilled {updated} missing/invalid ticket_id values."
            )
        )

