# Frontend readiness review

**Reviewed:** 2 October 2026

**Scope:** repository and contract review plus documentation only; no application features.

**Evidence:** `agents.md`, `Readme.md`, the product/UX/architecture specifications, actual Django URL configurations, views, serializers, selectors, services, existing tests, and freshly generated OpenAPI.

**Foundation update, 3 October 2026:** the inventory below preserves the review
as of 2 October. The requested frontend foundation has since been implemented:
React Router/TypeScript with SSR enabled, minimal home and `/foundation` routes,
root error handling and real 404s, a pinned npm lockfile, and documented
dev/lint/typecheck/test/build/start commands. The shared public API foundation
separates browser and server requests, normalizes API errors and pagination,
preserves decimal strings, supports cancellation, and provides the local
`/api/v1/` proxy. The visual foundation now adds centralized logo-derived
Tailwind tokens, initial customized shadcn/ui TypeScript source components, and
the `/visual-foundation` development preview. It adds no storefront or
authenticated-session feature. Route-specific Motion work and the backend
contract gaps below remain separate slices. See [current setup](../Readme.md#run-the-frontend-locally).

**Storefront shell update, 5 October 2026:** the shared responsive header,
mobile menu, footer, and page layout now expose the specified navigation in
brand-first order. Unfinished destinations resolve to clearly marked,
`noindex` development pages. Public contact values are centralized but remain
unset because no verified WhatsApp, phone, or email details are in the
repository; policy links also identify missing approved copy. Search, cart
count, account, catalog, and survey booking behavior are still separate slices.

Storefront shell verification passed: lint, typecheck, 15 focused unit tests,
production build, and eight production smoke tests covering SSR, the visual
preview and logo asset, unfinished destinations and contact placeholders,
compiled-client navigation, server-config isolation, 404s, assets, and a
test-only loader failure. Three earlier live integration
checks exercised the running Django catalog through the development proxy,
direct SSR, and Django's validation-error envelope. Headless Edge review at
320px, 390px, 768px, 1280px, and 1440px found no horizontal overflow; mobile
menu/Search disclosure, Escape focus restoration, route focus, keyboard focus,
and reduced-motion CSS were also checked. No backend test suite was repeated. This
update does not change the earlier backend test result.

**Homepage update, 5 October 2026:** the homepage now follows UX section 5
with two provisional code-configured promotions, responsive decorative artwork,
live copy and homepage-anchor destinations, manual controls, and an image
fallback. The first promotion and all static sections appear in SSR. Brand and
category links disclose their unfinished pages. A bounded product preview uses
only records returned by Django's published-product API and disappears on an
empty catalog; an API failure leaves the static homepage visible with a status
message. Development media requests are proxied to Django. The product detail,
browsing, and survey-booking pages remain later slices. The provisional banner
artwork/copy needs business approval before launch. The current homepage checks
add three production scenarios (empty, published, unavailable catalog) and
bring the production smoke test count to 11; keyboard promotion controls,
fallback, reduced motion, and phone/tablet/desktop layouts were checked in Edge.
The Django server was not available for a fresh live-catalog check in this
slice; the published-record case used a contract-shaped test response.

**Shop update, 5 October 2026:** `/shop` renders the paginated public product
collection in React Router's initial HTML, with a reusable homepage/shop card,
textual stock state, exact decimal PKR pricing, valid sale comparison, image
fallback, and an empty state. Pagination follows the backend's validated
next/previous links. Invalid page options and API failure have recoverable
states. Published zero-stock products stay visible. Product detail links open an
honest `noindex` development page until that separate slice is built. Search,
filter, sort, and brand/category browsing controls are still pending.
The shop production checks cover visible initial HTML, a second page, empty
catalog, invalid URLs, backend errors, sale display, and zero stock; the
production smoke suite now has 14 checks.

## Repository snapshot reviewed on 2 October 2026

| Requirement | What exists | Remaining work |
| --- | --- | --- |
| Frontend application | `frontend/` exists and is empty, including hidden files. | React Router Framework Mode foundation, React/TypeScript configuration, package/lockfile, routes, and dependencies. No existing frontend implementation needs migration. |
| Rendering and SEO | Runtime SSR and suitable static pre-rendering are specified in architecture sections 7 and 73–74. | Rendering runtime/configuration, public loaders, metadata/canonicals, sitemap, and private-page indexing/cache controls. These are agreed requirements, not running infrastructure. |
| Styling and reusable UI | Token ownership, customized shadcn/ui, and motion rules are already specified. | Token stylesheet, Tailwind setup, `components.json`, TypeScript UI source, and accessibility/contrast checks. No component library or tokens have been installed/generated. |
| Frontend state and API integration | Architecture specifies loader/URL state, ID/quantity-only browser cart, in-memory access tokens, and separate browser/server API clients. | All clients, auth/session restoration, single-flight refresh, cart persistence, forms, and recovery states. React must not own trusted prices, stock, totals, capacity, or permissions. |
| Customer and staff screens | Product and UX requirements define the journeys; UX section 10.1 already contained a guest-survey definition and is extended in this slice. | Every storefront, account, tracking, and staff screen, including responsive and keyboard verification. |
| Verification | Django tests and README commands for checks, migration consistency, PostgreSQL tests, and OpenAPI validation exist. | No frontend lint, typecheck, tests, or build scripts; no `.github/` CI configuration or configured backend formatter/linter was found. Foundation must define and document its actual checks. |
| Brand assets | `Logo/logo.png` and `Logo/Fb Cover.png` are RGB PNGs; `Logo/OctacamLogo.png` is RGBA with transparent pixels and visually follows the blue/black OC design. | UX names `image-gen-1(4).png`, which is absent. Establish the repository asset's relationship to that approved master, review export quality/light-dark use, then derive and contrast-check tokens. No hex values are approved here. |

Specifications live under the existing `Docs/` directory rather than at repository root. Preserve that actual location and existing links in this slice; the architecture's folder tree is a design example. Unrelated untracked CV files under `Logo/` were left untouched. No real catalog data is seeded automatically; this review does not certify local database contents or product approvals.

## Backend contracts available for frontend integration

All application routes below are under `/api/v1/`. The backend publishes schema at `/api/schema/` and Swagger at `/api/docs/`. Fresh OpenAPI generation/validation succeeded: **57 paths and 67 operations**, including the schema GET. “Available” means the route and contract are implemented; it does not mean live-sales configuration or runtime acceptance has passed.

| Frontend slice | Implemented contract | Constraints to retain |
| --- | --- | --- |
| Navigation and taxonomy | GET `catalog/brands/`, `catalog/brands/{slug}/`, `catalog/categories/`, `catalog/categories/{slug}/`. | Active taxonomy only; paginated lists. Active taxonomy can have no published products, so navigation/landing UX must handle empty destinations. |
| Product browsing and details | GET `catalog/products/`, `catalog/products/{slug}/`, `catalog/filters/`. See [product API guide](product-draft-api.md#public-discovery). | Published products with active brand/category only; SKU/name search, price/availability/brand/category filters, relevance/price sorts, and category-specific `spec_*` filters. Product detail includes images, descriptions, warranty text, typed specifications, and current price/stock. Out-of-stock items remain discoverable. |
| Filters and pagination | Metadata contains scoped brand/category options, price bounds, and observed technical choices/ranges. Lists use `count`, `next`, `previous`, `results`, normally 20 per page. | Metadata accepts only brand/category scope; technical filters require category. Unknown/repeated/invalid parameters are rejected. Empty metadata bounds may be null. Follow the actual contract rather than sending speculative filters. |
| Authentication and recovery | GET `auth/csrf/`; POST register/login/refresh/logout and password-reset request/confirm. | CSRF bootstrap cookie/header for auth POSTs; access JWT in memory, rotating refresh in HttpOnly cookie. Browser must coordinate refresh and retain guest/account identity during uncertain business submissions. Password-reset email targets `/reset-password` with `uid` and `token`; that frontend route is not implemented. |
| Customer account | GET/PATCH `account/profile/`; GET `account/orders/` and `account/orders/{public_id}/`. See [account guide](account-api.md). | Customer Bearer authentication and ownership checks. Profile edits only full name/phone; no saved delivery-address API. Only orders placed while signed in appear; no email-based guest linking. |
| COD checkout | POST `checkout/quote/` and `checkout/place/`. See [checkout guide](checkout-api.md). | Quote contains server-calculated PKR amounts and signed quote token; place recalculates, snapshots, locks stock, and uses UUID idempotency. `CHECKOUT_CHANGED` requires renewed review; unavailable items may leave no usable quote. Keep exact key/body/identity after uncertain responses. COD only. |
| Optional survey in checkout | Placement accepts an optional nested `survey`; receipt returns the separate booking or null. | Atomic order and booking creation/rollback, independent addresses and later lifecycles, no survey charge in equipment totals. Preserve nested input and deliberately correct/drop the option only after a definitive failure. |
| Standalone survey booking | GET `surveys/slots/`; POST `surveys/bookings/`. See [booking guide](survey-booking-api.md). | Slots list only future/open availability and public ID/start/end, no capacity counts. Booking requires CSRF, UUID idempotency, Lahore city and approved declared area; availability is no reservation. No public coverage/configuration discovery exists. |
| Private guest status | GET `orders/track/{signed_token}/` and `surveys/track/{signed_token}/`. | Resource-specific signed/revocable guest links; no login required, no write access. Survey response is limited to reference/status/slot/area/city/installation notice. Neutral 404 and privacy headers; current links open JSON, not HTML screens. |
| Staff catalog and stock | `staff/catalog/` taxonomy, product drafts/edit/publication, specifications/choices, image upload/edit/delete, and stock adjustments/history. | Staff Bearer permission; explicit stock workflow and publication validation. UI must use server errors and actual records, not bypass validation or invent inventory. |
| Staff orders | List/detail/history; transition, courier, COD-collected, and cancellation commands under `staff/orders/`. See [staff guide](staff-order-api.md). | Version checks, allowed transitions, COD separate from fulfillment, eligible cancellation/restock once, audit/email outbox. No customer cancellation endpoint. |
| Staff surveys and operations | Slot list/create/detail/edit; booking list/detail/history/notes/reschedule/transition; `staff/overview/`, `staff/activity/`, email list/retry. See [survey guide](staff-survey-api.md) and README operations notes. | Staff permission, capacity locks/version checks, independent order lifecycle, internal-only notes, bounded overview and retry eligibility. One staff level; no general analytics or CMS. |

The shared handled-error envelope is `error.code`, `error.message`, and field-associated `error.fields`; checkout conflicts additionally include `current_quote`. Frontend decisions must use stable codes. Unexpected server/proxy errors may not be JSON and still need a recoverable UI. Decimal monetary values must be displayed from Django responses, never recomputed as trusted browser totals.

## Blockers identified in the 2 October review

These gaps affect particular later slices, not the whole frontend foundation. No new endpoint or backend implementation is introduced by this review.

| Gap | Impact | Smallest follow-up |
| --- | --- | --- |
| No frontend foundation | There is no runnable UI or verification toolchain. | Build only the agreed React Router/TypeScript, Tailwind tokens, customized shadcn/ui, rendering, API-client foundations, and actual documented checks in a requested foundation slice. |
| Survey eligibility/configuration is backend-only | UX requires coverage checking before offering bookable slots; slot GET does not reveal approved areas or missing coverage configuration. New bookings fail closed with `503 SURVEY_NOT_CONFIGURED`, but the browser cannot discover that beforehand. | Separate backend contract task: expose only validated public coverage labels and booking-configuration availability, reusing existing configuration parsing; define path/schema/errors and focused tests in that task. Do not duplicate area constants in React or infer eligibility from Lahore city/slot availability. |
| Guest URLs lead to APIs | Immediate receipts and all current guest emails open JSON. A future frontend route alone would not fix emailed links. | Separate integration task: issue customer-page URLs from shared guest link builders while keeping signed-token semantics and existing API reads/links usable; coordinate receipt/email tests and documentation for both orders and surveys. No conversion of JSON API endpoints to HTML. |
| Checkout schema omits authentication failure | Quote/place allow guests but still use default JWT authentication; an invalid supplied Bearer token can return 401, which their OpenAPI response annotations omit. | Small backend documentation/test task: annotate 401 with the shared error serializer and verify expired/invalid Bearer behavior. Existing clients must handle auth failure without silently retrying placement as a guest. This does not prevent starting public browsing. |
| Approved business inputs are unverified | Live sales/bookings cannot be enabled from repository defaults. | Business approval/configuration task: tax treatment/rate, flat shipping/taxability, survey coverage and slot duration, genuine products/images/specifications/stock, policies, contacts, delivery statements, and approved banner content/destinations. No guessed values or seeded fake sales data. |
| Production integration remains incomplete | Same-origin routing, internal SSR backend URL, durable media/email, HTTPS, redacted private-page logs, backups/restore, and deployed health checks are requirements, not verified deployment. | Complete the documented production-hardening slice before launch. No new infrastructure or CMS is needed for this review. |
| Local PostgreSQL unreachable during review | Database-backed behavior and data cannot be independently verified in this run. | Restore the README's local database setup, then rerun the focused existing tests below. The documented `pg_ctl` start attempt failed with Windows error 87. |

No backend CMS is required for homepage banners, support/policy content, or this documentation slice. No server-side cart is required. Signed-in survey history is not an agreed account screen/API; signed-in survey receipts and support remain the specified paths. A new survey account feature would need its own product/UX decision.

## Agreed implementation decisions

Architecture section 6.1 owns the technical decisions and trade-offs; README and UX refer to it. This review makes their implementation status explicit without changing product scope:

- React + React Router Framework Mode + TypeScript, using `.ts` for non-JSX and `.tsx` for routes/reusable UI; runtime SSR for dynamic public content and suitable static pre-rendering as specified in section 7.
- One design-token source at `frontend/app/styles/tokens.css`, loaded by `app/styles/app.css`, covering color, typography, spacing, radii, shadows, and motion. Derive brand values from the approved master and check contrast before fixing them.
- shadcn/ui in TypeScript mode, configured in `components.json`, with customized project-owned source under `app/components/ui/`. Preserve semantics, keyboard/focus behavior, accessibility, and ownership of updates.
- Motion for React only for restrained homepage entrance and selected scroll animations, imported where needed. Essential SSR content remains visible before hydration and without animation.
- CSS for simple hover/focus transitions. Both CSS and Motion respect reduced motion, and focus/state feedback remains immediate. Static banners show one at a time, with manual controls and no auto-advance.
- Lint, independent TypeScript typecheck covering route types and `.ts`/`.tsx`, focused tests, and production build must be defined/documented during frontend setup. A build does not replace typechecking.

## Verification and manual review

Passed in this review:

- Django `manage.py check`: no issues.
- `manage.py spectacular --validate --file ../.tmp/frontend-review-schema.yml`: passed with no warnings/errors after creating the ignored output directory. Schema inspected against URL/view/serializer definitions; no generated schema added to Git.
- Documentation diff, relative links, and whitespace check (see final handoff).

Attempted but blocked before any test executed: 31 existing tests covering guest order tracking, standalone survey API behavior/privacy, and staff survey changes. PostgreSQL connections timed out during test database setup; the README's native database start command then failed with Windows error 87. No runtime tests are claimed to pass.

Not run: frontend lint/typecheck/tests/build or browser/mobile/keyboard/motion checks, because no frontend exists; full backend/concurrency suite, migration consistency, production health checks, deployment/media/email/backup verification. This documentation-only slice changes no backend models, services, or APIs and adds no tests.

To review manually:

1. Read this inventory against the specifications, then inspect `git diff -- Readme.md agents.md Docs/architecture.md Docs/ux-spec.md`. Open the new report in the IDE as well, since ordinary `git diff` omits untracked files. A combined diff including the new report is supplied in the handoff.
2. Check that architecture section 6.1 and README describe planned files accurately, and that UX section 10.1 specifies permitted fields, all states, private-page protections, keyboard/mobile behavior, and independent order/survey status.
3. With Django/PostgreSQL available, use `/api/docs/` and the existing checkout/survey guides to compare real response fields. Existing guest URLs should return limited JSON; no customer-facing page is claimed to exist yet. Never share those private URLs.
4. From `backend/`, rerun the focused checks after database access is restored:

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py spectacular --validate --file ../.tmp/frontend-review-schema.yml
.venv\Scripts\python.exe manage.py test apps.orders.tests.test_guest_tracking_api apps.surveys.tests.test_booking_api.SurveyBookingApiTests apps.surveys.tests.test_staff_booking_api.StaffSurveyBookingTests --settings=config.settings.test --noinput
```

Create the ignored `.tmp/` directory first if needed. Use the README for backend/database setup, not assumed npm commands. No application feature, commit, or push is part of this slice.
