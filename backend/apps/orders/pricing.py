from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings


CENT = Decimal("0.01")


class CheckoutConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class PricingPolicy:
    shipping_fee: Decimal
    tax_rate_percent: Decimal
    shipping_taxable: bool

    @classmethod
    def configured(cls):
        raw_shipping = settings.CHECKOUT_SHIPPING_FEE
        raw_rate = settings.CHECKOUT_TAX_RATE_PERCENT
        raw_shipping_taxable = settings.CHECKOUT_SHIPPING_TAXABLE
        if raw_shipping is None or raw_rate is None or raw_shipping_taxable is None:
            raise CheckoutConfigurationError("Checkout requires approved shipping and tax configuration.")
        try:
            shipping = Decimal(str(raw_shipping))
            rate = Decimal(str(raw_rate))
        except InvalidOperation as exc:
            raise CheckoutConfigurationError("Checkout shipping or tax configuration is invalid.") from exc
        if not shipping.is_finite() or shipping < 0 or shipping >= 10**16:
            raise CheckoutConfigurationError("Checkout shipping configuration is invalid.")
        if not rate.is_finite() or rate < 0 or rate > 100:
            raise CheckoutConfigurationError("Checkout tax configuration is invalid.")
        try:
            if shipping != shipping.quantize(CENT) or rate != rate.quantize(CENT):
                raise CheckoutConfigurationError("Checkout pricing configuration needs two decimal places.")
        except InvalidOperation as exc:
            raise CheckoutConfigurationError("Checkout pricing configuration is invalid.") from exc
        if str(raw_shipping_taxable).lower() not in {"true", "false"}:
            raise CheckoutConfigurationError("Checkout shipping tax configuration is invalid.")
        return cls(shipping, rate, str(raw_shipping_taxable).lower() == "true")

    def tax_on(self, amount):
        return (amount * self.tax_rate_percent / 100).quantize(CENT, rounding=ROUND_HALF_UP)
