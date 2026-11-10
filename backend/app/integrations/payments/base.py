from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class PaymentError(Exception):
    pass


@dataclass
class PaymentResult:
    succeeded: bool
    provider: str
    provider_ref: str | None
    failure_reason: str | None = None
    simulated: bool = True


class PaymentProvider(Protocol):
    name: str

    def charge(
        self, amount_minor: int, currency: str, idempotency_key: str, method_token: str, reference: str
    ) -> PaymentResult: ...
    def refund(
        self, amount_minor: int, currency: str, idempotency_key: str, charge_ref: str | None, reference: str
    ) -> PaymentResult: ...
