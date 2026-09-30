# Staff order API

Apply the order migrations before using these endpoints. Sign in as staff and send
the access JWT as `Authorization: Bearer <access_token>`. The refresh cookie alone
does not authorize staff requests. Customers and anonymous visitors cannot use
these routes.

## Find and inspect orders

`GET /api/v1/staff/orders/` returns 20 orders per page, newest first, with
`count`, `next`, `previous`, and `results`. Optional filters are `status`,
`payment_status`, and `q` (all or part of a reference). For example:

```http
GET /api/v1/staff/orders/?status=placed&q=OC-
Authorization: Bearer <staff_access_token>
```

`GET /api/v1/staff/orders/{public_id}/` returns the saved customer contact,
delivery address, items, prices, shipping, tax, total, fulfillment state, COD
state, courier details, and `version`. It does not expose the checkout
idempotency key, request fingerprint, or guest tracking secret. To see who
changed an order and when, use the paginated
`GET /api/v1/staff/orders/{public_id}/history/` endpoint. Audit entries include
the action, staff email, time, before and after values, and safe metadata.

Staff order responses set `Cache-Control: private, no-store` and `X-Robots-Tag:
noindex, nofollow` because they contain customer information.

## Change fulfillment stage

Read the current `version` from the order detail first, then send only the next
stage:

```http
POST /api/v1/staff/orders/{public_id}/transition/
Authorization: Bearer <staff_access_token>
Content-Type: application/json

{"status":"confirmed","expected_version":0}
```

The allowed path is `placed → confirmed → packed → shipped → delivered`. Each
successful command returns the updated order with `version` increased by one,
records `ORDER_STATUS_CHANGED` with the staff actor, and queues one customer
email in the same database transaction. The worker sends email afterward.
Every successful stage change sends an email; courier-only and COD-only changes
do not. Emails use the stage and courier details saved with their event, so a
delayed email does not describe a later stage as if it were the earlier change.
Guest emails include the private tracking link. Courier details remain optional
at the shipped stage because no courier completeness rule is approved.

Skipping, repeating, reversing, or requesting `cancelled` through this endpoint
returns `409 INVALID_STATUS_TRANSITION`. Cancellation will use a separate
workflow. If another staff change used the version you saw, the response is
`409 ORDER_CHANGED`; reload the order before trying again.

## Enter courier information

```http
PATCH /api/v1/staff/orders/{public_id}/courier/
Authorization: Bearer <staff_access_token>
Content-Type: application/json

{"expected_version":1,"courier_name":"<courier>","tracking_number":"<tracking number>","tracking_url":"https://<courier tracking URL>"}
```

Send at least one courier field. Omitted fields keep their saved values; an empty
string clears a field. Tracking links must use HTTP or HTTPS. An actual change
increments `version` and records `COURIER_UPDATED`. Sending the already saved
values again returns the current order without another audit entry. A different
edit based on a stale version returns `409 ORDER_CHANGED`. Customers see saved
courier details through their account or private guest link.

## Record COD collection

Staff must confirm collection with fulfillment or the courier before calling:

```http
POST /api/v1/staff/orders/{public_id}/mark-cod-collected/
Authorization: Bearer <staff_access_token>
Content-Type: application/json

{"expected_version":1}
```

The command changes only `payment_status` from `uncollected` to `collected`,
increments `version`, and records `COD_MARKED_COLLECTED`. It never infers COD
collection from delivery or changes the fulfillment stage. Repeating the command
after collection returns the current order without a second audit entry. A
stale version on an uncollected order returns `409 ORDER_CHANGED`. Courier and
COD commands reject cancelled orders.

All commands use the shared API error shape. There is no unrestricted order
PATCH, and all three mutations lock the order row so concurrent staff updates
cannot silently overwrite each other. No values in this guide are live shipping,
tax, courier, or delivery promises.
