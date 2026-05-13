from django.core.management.base import BaseCommand

from apps.ledgers.seed import BUSINESS_TYPE_ACCOUNTS, seed_default_chart_of_accounts

# python manage.py seed_default_chart --business inventory --currency UGX


class Command(BaseCommand):
    help = "Seed the default chart of accounts. Use --business to include domain-specific accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--currency",
            default="UGX",
            help="Reporting currency code (default: UGX).",
        )
        parser.add_argument(
            "--business",
            default="general",
            choices=list(BUSINESS_TYPE_ACCOUNTS.keys()),
            help=(
                "Business type determines which account groups are seeded: "
                "general (core only), inventory, microfinance, real_estate, all."
            ),
        )

    def handle(self, *args, **options):
        config = seed_default_chart_of_accounts(
            currency=options["currency"],
            business_type=options["business"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded '{options['business']}' chart of accounts "
                f"for configuration {config.id}"
            )
        )
