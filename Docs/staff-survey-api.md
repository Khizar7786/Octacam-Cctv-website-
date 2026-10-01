# Staff survey bookings and guest tracking

These tools manage a **free site survey**, independently of an equipment order.
Installation is quoted and scheduled offline afterward. Apply backend migrations,
including `surveys.0002_booking_management`, before using them.

## Staff inspection and private notes

All routes require an active staff Bearer access token. Guests and customer
accounts cannot inspect or change bookings through these routes.

```text
GET   /api/v1/staff/surveys/bookings/?status=confirmed&q=<reference fragment>
GET   /api/v1/staff/surveys/bookings/{public_id}/
GET   /api/v1/staff/surveys/bookings/{public_id}/history/
PATCH /api/v1/staff/surveys/bookings/{public_id}/notes/
POST  /api/v1/staff/surveys/bookings/{public_id}/reschedule/
POST  /api/v1/staff/surveys/bookings/{public_id}/transition/
```

List/history return `count`, `next`, `previous`, and `results`, with 20 records
per page under the current setting. Optional list filters are `status` and
reference substring `q`. Detail/list include contact and site details, needs,
scheduled slot time, status, internal notes, version, timestamps, and related
order public ID/reference when present. Tokens, idempotency keys, and request
fingerprints are not returned. History shows action, staff actor email, time,
before/after values, and version. Notes history is private staff information.

Every command requires the current booking `expected_version`. Unknown write
fields are rejected. Replace notes with PATCH; an empty string clears them:

```json
{"expected_version": 0, "internal_notes": "<staff-only notes>"}
```

Notes may contain up to 10,000 characters and remain editable on terminal
bookings. They record an audit event but never send customer email.

## Reschedule or finish a confirmed booking

Choose a destination from the availability API, then submit:

```http
POST /api/v1/staff/surveys/bookings/{public_id}/reschedule/
Authorization: Bearer <staff_access_token>
Content-Type: application/json

{"expected_version": 0, "slot_public_id": "<destination slot public ID>"}
```

Only a confirmed booking can move. The destination must still exist, be open,
start in the future, and have space. Availability does not reserve it. The
transaction locks the booking and both slots in consistent ID order, rechecks
capacity, and moves the booking with its scheduled-time snapshot. A failed move
leaves its old time/place intact. This also serializes with new customer bookings
and staff slot edits.

Use the transition endpoint to complete or cancel:

```json
{"expected_version": 1, "status": "completed"}
```

```json
{"expected_version": 1, "status": "cancelled"}
```

Completion is staff confirmation that the survey occurred. Completed and
cancelled states are terminal; this workflow has no reopen, terminal-state
correction, or customer modification operation. Record a correction in private
notes and handle it through support. Cancellation releases one place by excluding
the booking from occupancy; completion continues to count against its historical
slot. Repeated cancellation cannot release a second place. No command changes
an associated equipment order or installation appointment.

Effective writes return `200` with the current staff booking and increment its
version. With the current version, unchanged notes, moving to its existing slot,
or requesting its existing terminal status return `200` without a new audit,
email, or version. A stale version always returns `409 BOOKING_CHANGED`.

| Error | Recovery |
| --- | --- |
| `400 VALIDATION_ERROR` | Fix the associated input; retain unsaved values. |
| `409 BOOKING_CHANGED` | Reload detail/history and review another staff member's change before submitting again. |
| `409 BOOKING_CLOSED` | The completed/cancelled booking cannot move or change state. |
| `409 SURVEY_SLOT_UNAVAILABLE` | Preserve the booking and choose a fresh available destination. |
| `404 NOT_FOUND` | The staff booking ID was not found. |

After a lost/uncertain response, reload detail/history. Retrying the old version
cannot apply a second move or duplicate a notification. Do not automatically
resubmit using a fresh version without reviewing current state.

## Audit and customer notifications

Reschedule, complete, and cancel record staff identity, previous/new status and
slot times, and booking version in the same transaction as the booking and
email-outbox write. Events use `SURVEY_CHANGED` for a move/completion and
`SURVEY_CANCELLED` for cancellation. Messages explain the survey/installation
distinction, retain event-time snapshots during delayed delivery, and never
include notes or audit details. Outbox persistence failure rolls back the
command; delivery failure after commit does not undo the booking change and is
retried by the existing worker. Run `process_email_outbox` as in the README.

Scheduled times are stored on bookings so cancelled history/tracking stays
correct if staff edit a freed slot afterward. The migration copies existing
times from slots; historical times changed before migration cannot be recovered.

## Private guest tracking

`GET /api/v1/surveys/track/{signed_token}/` remains read-only. The long signed
token binds one guest booking public ID and revocable nonce under a separate
survey salt. A reference alone, tampering, another resource's token, revoked
nonce, or signed-in booking returns the same neutral `404`. Rotating
`guest_link_nonce` invalidates an issued link; this slice does not add a staff
link-rotation endpoint. Links have no time expiry and must be kept private.

The response is an explicit whitelist: `reference`, `status`, `slot` (public ID
and scheduled start/end), `site_area`, `site_city`, and `installation_notice`.
It updates after staff changes and retains the cancelled time. It excludes
customer contact, street address, needs, equipment order details, internal
notes, staff identity, audit history, and mutation controls. Customers request
changes through approved support routes. See UX specification section 10.1
for screen states; frontend implementation is a later slice.

Both tracking and staff booking responses, including errors, use
`Cache-Control: private, no-store`, `Referrer-Policy: no-referrer`, and
`X-Robots-Tag: noindex, nofollow`. Django logs redact tracking tokens. Configure
production proxy/monitoring logs and the later frontend to preserve these rules.
Dates are aware instants displayed in Asia/Karachi. Approved Lahore coverage
and slot duration remain required configuration, with no invented business values.
