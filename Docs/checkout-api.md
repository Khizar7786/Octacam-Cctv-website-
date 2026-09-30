# COD checkout API

This is the equipment-only backend checkout slice. It supports guests and signed-in
customers. Staff tokens can also use the checkout endpoints. Site-survey booking
and combined order/survey checkout are later work; a `survey` field is rejected.
There is no storefront checkout page yet.

## Business configuration

Before trying a quote, supply approved values in the Django server environment:

- `CHECKOUT_SHIPPING_FEE`: nationwide flat PKR amount with two decimal places.
- `CHECKOUT_TAX_RATE_PERCENT`: approved percentage with two decimal places; an
  explicit `0.00` is permitted only if that is the approved rule.
- `CHECKOUT_SHIPPING_TAXABLE`: `true` or `false`, based on the approved rule.

The current pricing adapter taxes each product line subtotal at that percentage,
rounds each line to paisa, optionally taxes shipping, then adds shipping. It does
not model product-specific or jurisdiction-specific tax rules. Confirm the rule
with the business before accepting real orders. Without all three inputs, quote
and place return `503 CHECKOUT_NOT_CONFIGURED`.

Apply migrations and start both Django and the outbox worker as shown in the
repository README. The local worker prints email to its terminal.

## Request a quote

Get `csrfToken` and its cookie from `GET /api/v1/auth/csrf/`. Keep both for the
POST requests. From the same browser session:

```http
POST /api/v1/checkout/quote/
Content-Type: application/json
X-CSRFToken: <csrfToken>

{
  "items": [{"product_id": 1, "quantity": 2}],
  "delivery_city": "Lahore",
  "delivery_province": "Punjab"
}
```

Use an actual published product ID with enough stock. The response contains
current item prices, regular prices, sale savings, per-line tax, availability,
product subtotal, shipping, tax, total due in PKR, and `quote_token`. A quote
does not reserve stock. The signed token expires after 15 minutes.

## Place the reviewed order

Create a UUID for this intended order and keep it for retries. Use the exact
`quote_token` returned above and the same items and delivery city/province.
Guest requests omit `Authorization`; signed-in requests include a Bearer access
token. Keep the CSRF cookie and header from the quote request.

```http
POST /api/v1/checkout/place/
Content-Type: application/json
X-CSRFToken: <csrfToken>
Idempotency-Key: <new UUID>

{
  "items": [{"product_id": 1, "quantity": 2}],
  "quote_token": "<quote_token>",
  "customer_name": "A Buyer",
  "customer_email": "buyer@example.com",
  "customer_phone": "<customer phone>",
  "delivery_address_line1": "<street address>",
  "delivery_address_line2": "",
  "delivery_city": "Lahore",
  "delivery_province": "Punjab",
  "delivery_postal_code": "",
  "delivery_country": "PK"
}
```

The first successful request returns 201 with the order reference, saved item
and address details, COD status `uncollected`, final amounts, and a private guest
tracking URL if the order was placed as a guest. A retry with the same UUID and
identical body returns the same receipt with 200. Reusing the key for different
order data returns `409 IDEMPOTENCY_CONFLICT`. If a network result is uncertain,
retry with the original UUID and body; do not create a new key.

If price, tax, shipping, or stock changed since the quote, placement returns
`409 CHECKOUT_CHANGED` with `current_quote` for renewed review. It creates no
order. If an item is unavailable, `current_quote.quote_token` is null. An
unpublished item produces `current_quote: null` and must be removed from the
cart. A sold-out initial quote returns `409 OUT_OF_STOCK` with current item
availability. Invalid input and expired/tampered quote tokens return 400.

## What the server commits

The place service rechecks the signed quote, locks product rows in product-ID
order, and recalculates prices and stock. One PostgreSQL transaction creates the
Order and immutable OrderItem snapshots, decreases product stock, writes linked
`InventoryMovement` rows with reason `order_placed`, adds an audit event, and
queues an `ORDER_PLACED` email event. Failure in any of those database writes
rolls the whole transaction back. The outbox worker sends email after commit;
delivery failure leaves the order in place for retry.

## Follow a guest order

The guest placement receipt includes `guest_tracking_url` immediately, even if
the email worker is stopped or delivery fails. Save that URL from the 201
response and show it on the confirmation screen. A retry with the same
`Idempotency-Key` and body returns the same URL with 200 unless the link was
revoked in the meantime. The confirmation email
contains that URL when the worker delivers it later. Signed-in orders return
`guest_tracking_url: null`; customers use their account order history instead.

Request the URL as a GET with no login or CSRF token:

```powershell
Invoke-RestMethod -Uri "<guest_tracking_url>"
```

The response shows only this order's reference, saved item and amount details,
order status, separate COD payment status, and courier information when staff
has entered it. It omits names, email, phone, address, internal IDs, notes, and
audit history. The reference by itself cannot open the endpoint. Invalid,
tampered, unknown, and revoked links all return the same `404 NOT_FOUND` API
error. Changing an order's `guest_link_nonce` through a trusted internal
operation revokes its old links; issuing a new link then uses the new nonce.

Treat the link as a secret because anyone holding it can read that limited
status. Receipt and tracking responses set `Cache-Control: private, no-store`,
`Referrer-Policy: no-referrer`, and `X-Robots-Tag: noindex, nofollow`. Django's
access log redacts the token segment. Production reverse proxies, hosting
access logs, error reporting, and analytics must also redact it. The future
storefront tracking page must be `noindex` and use a no-referrer policy.
