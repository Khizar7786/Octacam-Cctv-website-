# Survey slot API

These endpoints manage **free Lahore site-survey** availability. They do not
book a survey or schedule installation. Apply the survey migrations before use.

## Configuration and time rules

Set `SURVEY_SLOT_DURATION_MINUTES` to an approved positive whole number of
minutes in the backend environment. There is no built-in slot length. Creating
a slot or changing its start time returns `503 SURVEY_NOT_CONFIGURED` while
this value is absent or invalid. The backend calculates `ends_at`; clients
cannot submit it.

Supply `starts_at` as an ISO 8601 timestamp with a numeric UTC offset, such as
`2027-01-15T09:00:00+05:00`. New starts and time edits must be in the future.
The database stores aware instants; API responses display starts and ends in
`Asia/Karachi` (Pakistan local time, with `+05:00` in the timestamp). An
offset-free timestamp is rejected. The example date and time are illustrative,
not a published appointment.

The exact Lahore service boundary is still an approved business input. Slot
management does not establish address eligibility. The later booking API must
check the configured Lahore boundary before reserving a slot.

## Staff routes

Send a staff Bearer access token. A customer or anonymous visitor cannot use
these routes. Both list routes return 20 entries per page in `results`, with
`count`, `next`, and `previous`.

```text
GET   /api/v1/staff/surveys/slots/
POST  /api/v1/staff/surveys/slots/
GET   /api/v1/staff/surveys/slots/{public_id}/
PATCH /api/v1/staff/surveys/slots/{public_id}/
```

Create a slot with a positive integer `capacity`. `is_open` defaults to `true`:

```http
POST /api/v1/staff/surveys/slots/
Authorization: Bearer <staff_access_token>
Content-Type: application/json

{"starts_at":"2027-01-15T09:00:00+05:00","capacity":1,"is_open":true}
```

Staff responses include `public_id`, local `starts_at` and `ends_at`,
`capacity`, `is_open`, `version`, non-cancelled `booked_count`, and derived
`remaining_capacity`. The latter is calculated from bookings and is never a
separate stored counter. Slot creation records `SURVEY_SLOT_CREATED` in the
audit trail. A second slot with the exact same start instant returns
`409 SLOT_TIME_TAKEN`; capacity for that start belongs on the existing slot.
Overlaps at different start times do not yet have an approved scheduling rule.

Read the current `version` before editing. PATCH requires `expected_version`
and at least one of `starts_at`, `capacity`, or `is_open`:

```http
PATCH /api/v1/staff/surveys/slots/{public_id}/
Authorization: Bearer <staff_access_token>
Content-Type: application/json

{"expected_version":0,"capacity":2,"is_open":false}
```

An effective edit increments `version` and records `SURVEY_SLOT_CHANGED`.
A stale version returns `409 SLOT_CHANGED`; reload the slot and review the
current counts before editing again. A time edit on a slot with any
non-cancelled booking returns `409 SLOT_HAS_BOOKINGS`. Reducing capacity below
that booking count returns `409 SLOT_CAPACITY_TOO_LOW`. Closing a slot prevents
new bookings, while its existing appointments keep their saved time and
booking state. A past slot cannot be reopened. There is no delete endpoint.

## Public availability

```http
GET /api/v1/surveys/slots/
```

The paginated public list includes only future, open slots with at least one
place remaining. Each result has only `public_id`, `starts_at`, and `ends_at`,
with times in `Asia/Karachi`. It does not reveal capacity, booking counts,
staff details, or customer details. An empty `results` means no slot is
currently offered; it does not mean an address is inside the Lahore service
area.

Availability is a current view, not a reservation. There is no booking
endpoint in this slice, so API requests cannot yet consume a slot. The next
booking service will lock the selected slot, recheck its time and open state,
recount non-cancelled bookings, check capacity and the Lahore address rule, and
create the booking in one transaction. A slot that filled or closed after this GET
will be rejected at booking time and the customer will choose from refreshed
availability.
