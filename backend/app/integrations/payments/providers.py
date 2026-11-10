from __future__ import annotations

import hashlib

from app.integrations.payments.base import PaymentError, PaymentProvider, PaymentResult

DEV_TOKENS = {"dev_card_ok": "approved", "dev_card_declined": "declined", "dev_card_error": "provider error"}


class DevelopmentPayments:
    """A LABELLED SIMULATOR. It never contacts a payment network and never moves money: results are deterministic
    from the token. Accepts only opaque dev tokens, so card numbers can never reach the system."""

    name = "development"

    def charge(
        self, amount_minor: int, currency: str, idempotency_key: str, method_token: str, reference: str
    ) -> PaymentResult:
        if method_token not in DEV_TOKENS:
            raise PaymentError("unknown development payment method token")
        ref = "dev_" + hashlib.sha256(f"{idempotency_key}|{reference}".encode()).hexdigest()[:16]
        if method_token == "dev_card_declined":
            return PaymentResult(False, self.name, ref, "card declined (simulated)")
        if method_token == "dev_card_error":
            raise PaymentError("simulated provider outage")
        return PaymentResult(True, self.name, ref)

    def refund(
        self, amount_minor: int, currency: str, idempotency_key: str, charge_ref: str | None, reference: str
    ) -> PaymentResult:
        ref = "dev_rf_" + hashlib.sha256(f"{idempotency_key}|{reference}".encode()).hexdigest()[:16]
        return PaymentResult(True, self.name, ref)


def get_payments() -> PaymentProvider:
    return DevelopmentPayments()
