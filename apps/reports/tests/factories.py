from datetime import date
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from apps.reports.models import ArtistPayout, PayoutPolicy


class PayoutPolicyFactory(DjangoModelFactory):
    class Meta:
        model = PayoutPolicy
        django_get_or_create = ("effective_from",)

    per_stream_rate = Decimal("0.003")
    per_listener_rate = Decimal("0.010")
    effective_from = date(2020, 1, 1)


class ArtistPayoutFactory(DjangoModelFactory):
    class Meta:
        model = ArtistPayout

    artist = factory.SubFactory("apps.accounts.tests.factories.ArtistUserFactory")
    period_month = factory.LazyFunction(lambda: date.today().replace(day=1))
    unique_listeners = 2
    streams = 5
    amount = Decimal("1.00")
    status = ArtistPayout.Status.PENDING
