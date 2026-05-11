from django.core.management.base import BaseCommand

from apps.ledgers.seed import seed_default_chart_of_accounts


class Command(BaseCommand):
    help = "Seed the default chart of accounts for the ledgers app."

    def add_arguments(self, parser):
        parser.add_argument("--currency", default="UGX")

    def handle(self, *args, **options):
        config = seed_default_chart_of_accounts(currency=options["currency"])
        self.stdout.write(self.style.SUCCESS(f"Seeded chart of accounts for configuration {config.id}"))
