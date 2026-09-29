# Customer account API

Use the existing login or registration flow to obtain an access JWT. Send
`Authorization: Bearer <access>` for every account request. The refresh cookie
alone is not authentication for these endpoints. Login/refresh still use the
existing CSRF convention; profile PATCH authenticates with the Bearer token.
These routes are for customers, while staff use the separate staff routes.

| Method | Route | Result |
| --- | --- | --- |
| GET | `/api/v1/account/profile/` | Current customer identity and permitted profile information. |
| PATCH | `/api/v1/account/profile/` | Update the customer's full name or phone. |
| GET | `/api/v1/account/orders/?page=1` | Saved signed-in order history, 20 orders per page. |
| GET | `/api/v1/account/orders/{public_id}/` | Saved details for an order owned by that customer. |

## Update a profile

```http
PATCH /api/v1/account/profile/
Authorization: Bearer <access>
Content-Type: application/json

{
  "full_name": "Updated Buyer Name",
  "phone": "03001234567"
}
```

Either field can be sent alone. Names must not be blank and have a maximum of
255 characters. Phone has a maximum of 30 characters and can be cleared with
an empty string. Email remains the login identifier; email-change verification
has not been built. Email, password, IDs, roles, account state, address, and
unknown fields are rejected with 400 rather than silently ignored. The response
uses the existing user representation: `id`, `email`, `full_name`, `phone`, and
`is_staff`.

## Read order history and details

History returns `count`, `next`, `previous`, and `results`, ordered by newest
placement date and then order ID. Each result includes `public_id`, reference,
date, saved item names/SKUs/quantities/prices, total, fulfillment status, COD
collection status, and any recorded courier fields. Use the `public_id` from
history in the detail URL.

Detail also includes saved checkout contact information, Pakistan delivery
address, subtotal, tax, shipping, and pricing configuration snapshots. These
values come from the placed order, not today's profile or catalog. Internal
database IDs, idempotency keys, request fingerprints, and guest-link nonces are
not returned. Order reads do not expose a customer cancellation or edit action.

Ownership is based only on the user linked when the order was placed. Another
customer's order, a guest order with a matching email, and a missing order return
the same 404 response from the detail endpoint. Historical guest orders are not
attached when someone registers or edits a profile. Use the existing secure
guest link to access a guest order.

An absent, expired, or inactive-account token returns 401. A staff token returns
403 on these customer routes. Changing name or phone does not invalidate the
access token and does not modify past orders or queued confirmation emails.
