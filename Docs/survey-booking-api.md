# Standalone site-survey booking API

Guests and signed-in customers can book a **free Lahore site survey** without
buying equipment. This confirms a survey; installation is quoted and scheduled
afterward. Equipment purchased elsewhere is subject to staff review.

Equipment buyers may instead include an optional survey in
[COD checkout](checkout-api.md#include-a-free-lahore-site-survey). It reuses the
same booking service, approved-area validation, capacity locks, audit, and
email outbox, inside the order transaction. Checkout supplies the trusted order
association and inherits its contact/identity; this standalone endpoint still
cannot accept an order association. After combined creation the resources have
independent lifecycles.

## Approved service-area configuration

Set `SURVEY_LAHORE_SERVICE_AREAS` in the backend environment to a JSON array of
business-approved area labels. There is no default coverage. A missing, empty,
or invalid array returns `503 SURVEY_NOT_CONFIGURED` on new bookings.

The site address must declare both Lahore as its city and an area from that
approved list. City and area matching ignore surrounding whitespace and case.
The backend never infers eligibility from an equipment delivery address or
Lahore city alone. Unsupported cities or areas return field-associated
`400 VALIDATION_ERROR` and consume no capacity. Customers should use support
for an address outside the approved coverage.

The business must approve area labels that accurately represent its launch
boundary before accepting bookings. This validates the declared address area;
it does not geocode street addresses. If coverage cuts through an area, define
a more precise address rule before enabling that area. Do not treat illustrative
test labels as approved coverage.

`SURVEY_SLOT_DURATION_MINUTES` continues to control staff slot creation. Booking
uses the dates already saved on the selected slot.

## Submit a booking

Get the CSRF cookie and token from `GET /api/v1/auth/csrf/`. Retain one UUID as
the `Idempotency-Key` for this intended booking. Signed-in customers also send
their Bearer access token; a refresh cookie alone leaves the booking as a guest.

```http
POST /api/v1/surveys/bookings/
X-CSRFToken: <csrf token>
Idempotency-Key: <new UUID>
Content-Type: application/json

{
  "slot_public_id": "<public_id from GET /api/v1/surveys/slots/>",
  "customer_name": "<customer name>",
  "customer_email": "<customer email>",
  "customer_phone": "<customer phone>",
  "site_address_line1": "<site street address>",
  "site_address_line2": "<optional address line>",
  "site_area": "<approved area label>",
  "site_city": "Lahore",
  "needs_description": "<needs or existing equipment>"
}
```

`site_address_line2` is optional. Other fields are required. Customer-provided
user IDs, order associations, status, internal notes, prices, or payment fields
are rejected. A standalone booking always has no related equipment order.

The first successful request returns `201` with a distinct booking reference,
`status: "confirmed"`, the local slot start/end, saved contact and site details,
`service_type: "site_survey"`, `booking_fee: "0.00"`, `currency: "PKR"`, and an
`installation_notice`. Guests receive `guest_tracking_url` immediately;
signed-in customers receive `null` for that field. Show the receipt only after
the server confirms success. No installation appointment or payment is created.

## Capacity, conflicts, and uncertain responses

Booking locks the slot, checks that it is open and starts in the future, and
counts non-cancelled bookings before inserting. Completed bookings also count
under the documented capacity rule. A missing, closed, started, or full slot
returns `409 SURVEY_SLOT_UNAVAILABLE`. Preserve the customer input, refresh
availability, and let the customer choose another slot.

If the first response is lost or times out, retry with the **same key, same
body, and same signed-in or guest identity**. The server returns `200` with the
existing booking, without consuming another place or creating another audit or
email event. This recovery still works after the slot closes or coverage
configuration changes. Reusing the key for another body or identity returns
`409 IDEMPOTENCY_CONFLICT`. Do not generate a new key merely because a response
is uncertain. In-flight identical retries wait for the first transaction and
recover its result; two customers competing for the final place cannot both
create bookings.

## Confirmation email and private guest status

The same transaction writes `SURVEY_BOOKING_CONFIRMED` audit and
`SURVEY_CONFIRMED` email outbox records. Run `process_email_outbox` as documented
in the README. Delivery failures are retried and do not undo a successful booking.
The email uses the confirmed time snapshot in Pakistan local time and explains
that installation is quoted afterward. An outbox database failure rolls back
booking creation, so the customer can safely retry.

The guest URL opens `GET /api/v1/surveys/track/{signed_token}/`. The signed,
revocable link is scoped to that guest booking. Its response contains only the
reference, state, slot time, area/city, and installation notice. It excludes the
street address, contact details, needs text, internal notes, and operational
records. A reference alone, a forged link, a revoked link, or an order link
returns a neutral `404`. Keep the URL private.

Tracking reads the current staff-managed state and scheduled-time snapshot.
Rescheduling updates that time; a cancelled booking retains its last scheduled
time even if staff later edit the freed slot. See [staff survey management](staff-survey-api.md)
for inspection, private notes/history, capacity-safe changes, and customer notifications.

Receipts and tracking responses use `private, no-store`, `no-referrer`, and
`noindex, nofollow`. Django logs redact survey tracking tokens; production proxy,
hosting, and monitoring logs must apply the same rule. Changes and cancellation
continue through support. There is no customer modification endpoint.
