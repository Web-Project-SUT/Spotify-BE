from django.core.management.base import BaseCommand

from apps.reports import services


class Command(BaseCommand):
    help = "Builds/updates ArtistPayout rows for a given month (default: previous month)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--period", type=str, default=None, help="YYYY-MM, default previous month"
        )

    def handle(self, *args, **options):
        period = services.parse_period(options["period"]) or services.previous_month()
        result = services.build_monthly_payouts(period=period)
        self.stdout.write(
            self.style.SUCCESS(
                f"Payouts for {result['period']}: "
                f"created={result['created']} updated={result['updated']} "
                f"skipped_settled={result['skipped_settled']}"
            )
        )
