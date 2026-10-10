# OctaCam

OctaCam is a Pakistani CCTV store in development. This repository currently contains the specifications, an SSR frontend foundation with a shared public API client and responsive storefront shell, Django backend foundation, account authentication and password reset APIs, customer profile editing and order history, catalog taxonomy, typed product specifications, staff product image management, publication controls, staff stock adjustments, public product APIs, COD checkout with optional survey booking, staff order processing, staff survey slot and booking management, public survey availability, standalone survey booking and private guest status, and a transactional email outbox worker. Checkout and remaining storefront flows remain in development.

## Frontend decisions

The frontend uses React, React Router Framework Mode, and TypeScript: `.ts` for non-JSX modules and `.tsx` for routes/components. SSR is enabled in `frontend/react-router.config.ts`; suitable static content may be pre-rendered in later slices. Tailwind CSS and the initial customized shadcn/ui TypeScript components share centralized brand, semantic, typography, spacing, radius, shadow, focus, and motion tokens from `frontend/app/styles/tokens.css`. The approved RGBA logo master is copied unchanged to `frontend/public/brand/`; an automated check protects its dimensions, alpha channel, and bytes. The header composes the original symbol and wordmark horizontally using SVG viewboxes; phones show the symbol with the home link still named OctaCam. Navigation includes every active brand across backend pagination between All brands and Shop all products. Motion for React remains reserved for restrained homepage entrance and selected scroll animations; simple hover/focus transitions use CSS and collapse under reduced-motion preferences. React Icons supplies named Font Awesome 6 SVGs and Lucide outline icons through the shared `frontend/app/components/ui/store-icon.tsx` wrapper; cart, account, and contact accents come from centralized tokens. The icon dependency is pinned in the lockfile, and no icon font or CDN is used. See [architecture section 6.1](Docs/architecture.md#61-technology) for reasons, ownership, and trade-offs and [the UX specification](Docs/ux-spec.md) for interaction requirements.

The frontend commands below cover lint, independent typechecking of `.ts`/`.tsx` files and generated route types, focused tests, and production build. Generated files, dependencies, and build output are ignored by Git.

See the [frontend readiness review](Docs/frontend-readiness.md) for the 2 October 2026 repository inventory, verified OpenAPI coverage, integration gaps, and checks performed. Guest survey screen behavior and acceptance checks are in [UX section 10.1](Docs/ux-spec.md#101-private-guest-survey-status). Current guest receipt/email URLs lead to JSON tracking APIs; their handoff to customer-facing pages remains a separate integration task.

The header scrolls away with the page and slides back into view when scrolling upward. It stays visible during header keyboard interaction and while the mobile menu/search is open; reduced motion disables the slide. To review it, scroll past the header at phone, tablet, and desktop widths, reverse direction, and try small scroll movements, keyboard focus, and a long mobile menu.

## Run the frontend locally

Use Node **22.15.0+ on the 22.x line, or Node 24+**, and npm. This workspace was verified with Node 22.15.0 and npm 10.9.2. Dependency versions are pinned in `frontend/package-lock.json`. React Router 7 and Vite 7 support this existing Node installation; the current Router 8 release requires newer Node and is not needed for this slice.

From the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/` to review the server-rendered homepage and shared shell. The homepage works without Django but shows an honest catalog-unavailable message; start Django on `http://127.0.0.1:8000` to load genuine published product previews. An empty published catalog omits that section. The development server uses loopback and a fixed port, so it reports an error rather than silently moving ports. The separate `/visual-foundation` route previews the logo, tokens, type, buttons, fields, alerts, and responsive layout primitives. Reload `/foundation` directly to exercise the server client during SSR, then navigate there from another route to exercise the browser client through the local same-origin `/api/v1/` proxy. An unknown URL such as `/missing/nested/page` returns HTTP 404 with a readable recovery link. Public pages still inherit the scaffold's `noindex` and `no-store` policy; remove that only with the later public SEO and product-route work.

The shared shell has an approved-logo header, brand-first and category navigation, a prominent search entry, account and cart entries, a Lahore survey entry, a mobile menu, and a footer. The homepage follows the UX order: code-deployed wide promotions with owner-approved autoplay, factual store information, optional real public catalog records, brand entries, categories, a Lahore survey panel, and the footer, following the owner's 9 October 2026 Smart Links reference using existing sections only. Promotion copy is live text, artwork is responsive and decorative, and the first slide and full headline are visible in SSR without waiting for animation. The wide hero slides automatically every 8 seconds after hydration and types only the first headline once on page reload, at a slower 65ms per character; slim direct indicators replace Previous/Next buttons, with no Play/Pause button. Hover and keyboard focus pause temporarily; leaving the hero resumes automatic slides after a fresh 8-second interval. Direct selection and horizontal touch swipes also restart that interval. Typing is independent of those interactions and never replays during slide changes. Hidden tabs, offscreen heroes and reduced-motion preferences suspend automatic motion. Reduced motion also removes typing/progress/slide transitions. Promotional configuration lives in `frontend/app/config/promotions.ts`; its destinations are real homepage sections. Replace the local desktop placeholders with approved wide banners (1920 x 480, 4:1 recommended), keeping important image details on the right behind the desktop text-safe overlay, and use separate 960 x 480 (2:1) mobile crops. The compact desktop height token ranges from 20 to 26rem, with intrinsic growth for wrapped text. Timing is centralized in the same file; no new animation dependency is needed. Destinations without screens yet open explicit **coming soon** pages; the search entry submits name/model queries to /search, and the cart shows its saved item count after browser hydration. Verified customer contact values belong in `frontend/app/config/storefront.ts`. All three contact channels are currently unset, so the footer states that details are pending verification and emits no WhatsApp, phone, or email link. Policy pages also remain pending approved wording. To review the shell without Django, open the home page, use the Search and Menu buttons at phone/tablet widths, and follow a brand, category, survey, or policy link to its honest status page. Tab through the header and footer; Escape should close an open mobile panel and return focus to its trigger. Check automatic promotion changes, hover/focus pause and resume on leaving, reload-only typing, direct slide indicators, touch swipe versus vertical scrolling, keyboard focus, image failure and reduced motion. With JavaScript disabled the complete first promotion remains readable.

`/shop` now uses a React Router server loader to render Django's published-product list in the first HTML response. The page shows an intentional empty state until staff publish genuine products; it retains published zero-stock records, uses Django's decimal PKR prices and pagination links, and shows recoverable loading/error states. Product cards are shared with the homepage, use compact responsive grids, and link from both their image and text. The public API supplies the optional second image for hover/keyboard-focus previews; missing or failed previews preserve the main image and reduced motion removes the fade. Their detail links now open server-rendered published product pages with image gallery, factual descriptions and specifications, product-specific warranty text when supplied, and current PKR price and stock. Quantity is limited by known stock; Add to cart becomes available after browser cart hydration and saves only product IDs and quantities. Shop, search, brand, and category pages now support URL-backed name/model search, brand/category, PKR price and availability filters, and relevance/price sorting. When an active category has published specification data, its choice, boolean, integer-range, and decimal-range filters appear from Django metadata. Changing category clears technical filters and explains why; apply the category to load its available attributes. Committed filters remain in the URL for reload, pagination, and browser Back. Open `/shop`, try `?page=2` when the API provides a next page, and inspect a product card with a real image, sale price, or zero stock after those records are published.

Catalog discovery matches the cart's borderless white surfaces, black headings, filled native controls, and blue actions. Shared tokens and `app/styles/catalog.css` own the search, filter rail/drawer, sort controls, chips, recovery states, and compact product spacing. At phone/tablet widths, Filters opens the existing accessible right drawer. Review 320px, 390px, tablet, and desktop layouts, keyboard focus/Escape, applying/removing filters, sort, invalid ranges, and no-result recovery; committed selections remain in the URL.

`OCTACAM_API_ORIGIN` configures the server-side Django origin and defaults to `http://127.0.0.1:8000` in local development. It must be an HTTP(S) origin without a path and is required when `NODE_ENV=production`. The variable has no `VITE_` prefix and lives only in server modules and Vite's server configuration, so it is not exposed to browser bundles. Browser requests always use relative `/api/v1/` paths. Vite proxies `/api/v1/` and development `/media/` product images to Django locally; production still needs documented same-origin API and durable media routing. Authentication, token refresh, CSRF handling, checkout, booking, and staff UI remain separate slices.

Product details use a large manual image carousel with thumbnails and keyboard controls, a brand logo from the existing upload API (or the brand name), a compact quantity stepper, and black breadcrumbs. Empty description/specification/warranty sections are omitted. The related-products carousel uses genuine other records from the same category; optional logo/related API failures leave the product usable. Both carousels remain manual and respect reduced motion; product photos and full factual content are present in SSR. Add to cart now updates the browser cart after hydration. Stock is not reserved.

The cart at /cart stores only product IDs and quantities in localStorage. On each visit or manual refresh it walks the published catalog API to display current name, image, PKR unit price, and stock. Unpublished or sold-out items remain visible as unavailable; reduced stock requires choosing the available quantity before that line contributes to the provisional subtotal. Shipping and tax are left for the future Django checkout quote, and no order can be placed from this slice. Because the current public API has no lookup by product ID, a large cart or a missing product can require scanning every catalog page; a public bulk-ID lookup is the smallest separate backend improvement. Test by adding a published in-stock product, reloading /cart, changing its quantity, removing it, and using Refresh prices and stock after a staff stock adjustment.

The cart uses borderless white product rows and a blue-tinted summary with shared design tokens. Image and title links open the product; 44px minus/plus controls complement the labeled quantity input. The summary stacks below items before the 1024px desktop breakpoint. For visual review, check 320px, 390px, tablet, and desktop widths, long product names, keyboard focus, quantity limits/validation, and the empty state.

The homepage’s "Shop by Brands" section shows all active brands across backend pagination in a borderless horizontal logo strip on the page background with evenly spaced logos and a compact heading. Uploaded logos retain their proportions; missing/failed logos use the brand name. Every tile opens its brand route, with All brands beside the heading. The strip scrolls slowly after hydration, pauses on hover/focus, and resumes automatically when you leave. There is no Play/Pause button; compact heading and logo-row spacing keep the section aligned with the page gutter. Its scoped CSS is imported directly by the carousel; development and production tests check the delivered styles to catch missing-style regressions. Reduced motion and JavaScript-disabled pages retain a manually scrollable original list. Visual loop copies add no sequential keyboard stops; hidden tabs and offscreen strips stop animating. For browser review, test 320px, tablet, and wide desktop layouts, hover and leave the strip, focus and leave each brand, swipe the strip, and switch reduced motion on and off. Promotional banners use the separately documented autoplay behavior.

The homepage's "Before you order" section sits directly below the hero promotion and is a compact, square-cornered charcoal strip extending through the shared side gutters, aligned with the full-width navy footer. Four factual items use 16px headings, 14px body text, 48px Lucide outline icons without backgrounds or badges, and subtle internal dividers. The section heading is 20–24px, with a smaller gap above the strip. Shared tokens own its typography and icon sizes, with lighter blue/violet/amber/rose outlines contrast-checked directly against charcoal. The warranty text is "Warranty terms vary by product." All details remain visible in SSR and without JavaScript; the strip has no animation or reveal controls. It stacks one column on phones, two from 640px, and four from 1280px. For browser review, check 320px, tablet, and wide desktop layouts, text zoom, edge-to-edge alignment without page overflow, and the visual separation from the footer.

From `frontend/`, run:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run test:production
```

With Django and the frontend development server already running, `npm run test:api:live` checks a real public catalog request through the browser proxy and a direct SSR document request.

`typecheck` runs React Router type generation before `tsc --noEmit`, covering application `.ts`/`.tsx`, tests, configuration, and generated route types. `lint` uses ESLint with the recommended TypeScript rules and fails on warnings. Its tool configuration is `eslint.config.mjs`; application modules remain TypeScript. A build is not a substitute for typechecking.

Tests use **Node's built-in test runner** and assertions, so no testing dependency was introduced. Node's `--experimental-strip-types` flag runs the `.ts` tests on the existing Node 22.15 installation; type correctness is checked separately by `typecheck`. On this version Node prints an experimental-feature notice. `npm test` covers route-error privacy, structured and malformed API errors, server/browser URL boundaries, cancellation, decimal-string preservation, pagination normalization, logo-source integrity, and the required token contrast pairs. After building, `test:production` starts a local catalog stub plus the official production server on temporary loopback ports, checks direct/repeated SSR including the visual preview, unfinished route destinations and contact placeholders, the built logo asset, compiled client-loader navigation through the same-origin API path, browser-bundle configuration isolation, 404 recovery, CSS/JavaScript delivery, and a test-only injected loader failure, then stops both servers. It does not ship a mock endpoint or error-demo endpoint in the application. React Router 7 also prints advisory notices about future Router 8 flags during development/build; this scaffold retains current behavior.

To run the built production server manually:

```powershell
$env:HOST = "127.0.0.1"
$env:PORT = "3000"
$env:OCTACAM_API_ORIGIN = "http://127.0.0.1:8000"
npm start
```

Open `http://127.0.0.1:3000/foundation` directly, reload it, and check an unknown nested URL. Stop with Ctrl+C, then remove those terminal overrides with `Remove-Item Env:HOST, Env:PORT, Env:OCTACAM_API_ORIGIN`. The official server starts from `build/server/index.js` and serves the built client assets. Browser API navigation on this production server additionally requires the production same-origin reverse route; `react-router-serve` does not proxy Django. These commands verify a local production build, not deployment readiness for live sales.

For browser review of the API foundation, open `/foundation` through client navigation from another route. The result should say it used the browser API client; a direct reload should say it used the server API client. In both cases the published count comes from Django. Check the homepage and placeholder/error pages at narrow phone, tablet, and desktop widths, tab through the skip link and navigation, and activate **Skip to content** and **Return home**. Homepage content must remain readable with JavaScript disabled; entrance animations have not been added.

## Run the backend locally

Requirements: Python 3.12, Docker with a running engine, and Docker Compose. From the repository root:

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
docker compose up -d db
cd backend
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/health/live`, `http://127.0.0.1:8000/health/ready`, `http://127.0.0.1:8000/api/schema/`, or `http://127.0.0.1:8000/api/docs/`. The database container uses host port **5433** to avoid conflicts with an existing PostgreSQL service on 5432. Its `octacam_dev` password is for local development only. Run `docker compose down` from the repository root to stop the container; the named volume keeps local data.

If you already have PostgreSQL, skip Compose and set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` before running Django. `DATABASE_URL` (for example, `postgresql://user:password@host:5432/database?sslmode=require`) takes precedence over those settings. Local defaults match Compose.

### This Windows workspace without Docker

This machine also has an isolated native PostgreSQL cluster in the ignored `.local-postgres/` directory. It uses the same local development credentials and port 5433 as Compose. From the repository root, restart it with:

```powershell
pg_ctl -D .local-postgres\data -l .local-postgres\postgres.log -o '-h 127.0.0.1 -p 5433' start
cd backend
.venv\Scripts\python.exe manage.py runserver
```

Stop Django with Ctrl+C, then run `pg_ctl -D .local-postgres\data stop` from the repository root. Stop this native cluster before starting the Compose database, since both use port 5433. The cluster is local development data and is excluded from Git.

To run checks from `backend/` with the database running:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.test"
.venv\Scripts\python.exe manage.py test
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
Remove-Item Env:DJANGO_SETTINGS_MODULE
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py spectacular --validate --file schema.yml
Remove-Item schema.yml
```

The test suite uses PostgreSQL and needs permission to create a temporary test database. The custom email-login user table is created by `accounts.0001_initial`; do not switch to Django's default user model after migrating.

## Configuration

`manage.py` uses `config.settings.local`; WSGI and ASGI default to `config.settings.production`. Production refuses to start without `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` (comma-separated), a PostgreSQL `DATABASE_URL`, `DJANGO_MEDIA_STORAGE_BACKEND` pointing to configured object storage, an HTTPS `PUBLIC_SITE_URL`, a delivery `EMAIL_BACKEND`, and `DEFAULT_FROM_EMAIL`. No production media or email provider has been selected yet. Production sets secure cookies, HTTPS redirect, and HSTS; configure HTTPS at the reverse proxy before using it. The test settings retain PostgreSQL rather than swapping in SQLite.

COD checkout also requires explicit `CHECKOUT_SHIPPING_FEE` (PKR with two decimal places), `CHECKOUT_TAX_RATE_PERCENT` (approved percentage with two decimal places), and `CHECKOUT_SHIPPING_TAXABLE` (`true` or `false`). No values are provided by the repository; quote and placement return `503 CHECKOUT_NOT_CONFIGURED` until these business inputs are approved and set. The current pricing adapter supports one percentage on product line subtotals and, if configured, shipping. Confirm that this matches the approved tax treatment before accepting real orders.

## Authentication API

The API exposes `POST /api/v1/auth/register/`, `login/`, `refresh/`, and `logout/`; password reset request and confirm routes; `GET /api/v1/auth/csrf/`; `GET /api/v1/account/profile/` for customers; and `GET /api/v1/staff/profile/` for staff. Public registration always creates a customer account. Staff accounts must be created or granted `is_staff` through a trusted administrative process, never through registration input.

Start by requesting `GET /api/v1/auth/csrf/`. It returns `csrfToken` and sets a CSRF cookie. Send that token in `X-CSRFToken` on auth POST endpoints, including both password reset routes. Registration accepts `email`, `full_name`, optional `phone`, and `password`; login accepts `email` and `password`. Both return a short-lived `access` token and user details, and set a seven-day refresh token in an HttpOnly, SameSite=Lax cookie scoped to `/api/v1/auth/` (Secure in production). Keep the access token in application memory and send it as `Authorization: Bearer <token>` to profile endpoints. A page reload can call `refresh/` with the cookie and CSRF header to obtain a new access token and rotated cookie. Coordinate simultaneous refresh attempts into one request; a used refresh token cannot be used again. Logout revokes the refresh cookie and the client discards its access token. An already issued access token remains valid until its five-minute expiry unless the account is disabled or its password changes.

Login, registration, refresh, and password reset have in-process rate limits. Production needs an edge-level rate limit as well when multiple Django processes run. Run `python manage.py flushexpiredtokens` on a schedule to remove expired token records. Do not deploy this foundation to take real orders.

### Customer account API

The existing `/api/v1/account/profile/` route supports GET and PATCH. PATCH permits `full_name` and `phone` only; email, passwords, roles, and account state cannot be edited here. `GET /api/v1/account/orders/` provides paginated history, and `GET /api/v1/account/orders/{public_id}/` returns an owned order's saved details, amounts, COD status, and courier information. All these routes require a customer Bearer access token. Staff use their separate staff routes. Matching checkout email addresses do not grant access to guest or other customers' orders, and profile updates never rewrite order snapshots. See [the customer account API walkthrough](Docs/account-api.md).

### Password recovery and email worker

With PostgreSQL running, apply migrations using `backend\.venv\Scripts\python.exe backend\manage.py migrate` from the repository root. Keep the Django server running, then open a second PowerShell terminal and run:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py process_email_outbox
```

The worker polls every five seconds. Use `process_email_outbox --once` to process one batch and exit, or `--poll-seconds 10` to change the interval. Local email is written to the worker terminal by Django's console backend; it is not sent externally. Stop the worker with Ctrl+C. The outbox is in PostgreSQL, so a queued event survives a server or worker restart.

Placed COD orders now queue an `ORDER_PLACED` event in the same database transaction. The worker sends an order confirmation using saved item and amount snapshots. Guest emails include a signed link to the limited order tracking API. An email delivery failure leaves the placed order intact and is retried by the worker.

The guest placement response also returns `guest_tracking_url` immediately. Open that URL with a GET to see the order's limited status, amounts, and courier details; the order reference alone cannot grant access. Save the link privately. See [the checkout API guide](Docs/checkout-api.md#follow-a-guest-order) for the response fields and privacy rules.

Request a reset through `POST /api/v1/auth/password-reset/request/` with `{"email":"you@example.com"}` and the `X-CSRFToken` from `GET /api/v1/auth/csrf/`. The response is always the same for valid, unknown, or inactive accounts. For an active account, copy `uid` and `token` from the link printed by the worker and send them with `new_password` to `POST /api/v1/auth/password-reset/confirm/`, also with the CSRF header. The link points to the future `/reset-password` storefront page; that page is not implemented yet. Tokens expire after one hour and become invalid after a successful password change.

Staff can inspect `GET /api/v1/staff/overview/` and the paginated `GET /api/v1/staff/activity/`, `GET /api/v1/staff/orders/`, and `GET /api/v1/staff/surveys/bookings/?upcoming=true` lists. The overview includes five-record previews and operational counts. Staff can inspect `GET /api/v1/staff/communications/emails/?status=failed` and request an immediate retry with `POST /api/v1/staff/communications/emails/{id}/retry/` when `retry_available` is true. These routes require a staff Bearer token. Automatic retries use increasing delays and stop after five failed attempts. An expired or invalid password reset request needs a fresh customer request instead of staff retry. The staff list exposes delivery state, attempt count, and a safe failure class without returning template context or reset links. Production must set an HTTPS `PUBLIC_SITE_URL`, `DEFAULT_FROM_EMAIL`, and a real `EMAIL_BACKEND` with its provider settings, such as Django SMTP `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, and `EMAIL_HOST_PASSWORD`. Delivery credentials are environment variables, never committed.

## Catalog APIs

Visitors can list active brands/categories and retrieve them by slug. Staff can list all entries, create them, and edit or deactivate them by ID using a Bearer access token. Lists return 20 entries per page. See [the endpoint and Swagger walkthrough](Docs/catalog-api.md) for request examples and expected permission responses. Apply the catalog migration with `python manage.py migrate` before trying these routes.

Staff brand POST/PATCH also accept optional PNG, JPEG, or WebP `logo` uploads up to 2 MB using multipart form data, while retaining JSON taxonomy edits. Remove a logo with JSON `{"logo": null}` or `remove_logo=true`; omitting these fields preserves it. Public and staff brand responses include nullable `logo_url` from configured storage. Files use ignored local media in development and the production object-storage backend. See [brand logo API details](Docs/catalog-api.md#brand-logos). Product details and the homepage brand strip display these logos with a readable brand-name fallback; staff upload controls remain separate work.

Staff can create product drafts, configure typed specifications per category, assign specification values, upload and order images, publish products, and make reasoned stock adjustments with a movement history. Visitors can search, filter, sort, list, and retrieve published products with image metadata; published products remain visible at zero stock. Filter metadata is available at `/api/v1/catalog/filters/`. Local media files are stored in ignored `backend/media/` and served at `/media/` by Django only in development. See [the product catalog API walkthrough](Docs/product-draft-api.md).

## COD checkout API

`POST /api/v1/checkout/quote/` calculates a current PKR quote for product IDs, quantities, and delivery city/province. `POST /api/v1/checkout/place/` accepts the reviewed quote token, contact and delivery address, and an `Idempotency-Key` UUID. Both guest and Bearer-authenticated customers can use these routes. Send the CSRF cookie and `X-CSRFToken` header from `GET /api/v1/auth/csrf/`. Placement returns an order receipt; a repeat request with the same key and body returns the same receipt. Start `process_email_outbox` in another terminal to see the confirmation email locally. See [the checkout request walkthrough](Docs/checkout-api.md) for payloads, conflicts, and the request-to-database flow.

Placement also accepts an optional `survey` with an approved Lahore site address, needs, and slot public ID. It uses checkout contact and creates both resources in one transaction: an unavailable slot leaves no partial order, stock deduction, booking, audit, or email. The free survey adds no equipment charge and the receipt includes a separate booking reference and guest status link. Preserve the exact key/body/identity after an uncertain response to recover both once. Order and survey changes remain independent after creation. Omit the option or send `null` for equipment alone.

## Staff order processing

After `manage.py migrate`, staff can list and inspect orders, move them through `placed → confirmed → packed → shipped → delivered`, enter manual courier information, mark COD collected independently, and cancel placed or confirmed orders while COD is uncollected. Eligible cancellation restores stock once and queues customer email. Each change is audited. Staff commands require the current order `version` to prevent stale edits. See [the staff order API guide](Docs/staff-order-api.md) for routes, request bodies, errors, and history. Later-stage and collected-COD cancellation need a business policy before enabling them.

## Survey slots and availability

Staff can create, inspect, and edit Lahore site-survey slots with a Bearer access token. The public availability endpoint lists future, open slots with room remaining, without exposing operational counts. Set the approved `SURVEY_SLOT_DURATION_MINUTES` before creating slots or changing their times; there is no default duration. See [the survey slot API guide](Docs/survey-slot-api.md) for the routes, time rules, and conflicts.

Guests and signed-in customers can use `POST /api/v1/surveys/bookings/` to confirm a free site survey without an equipment order. Set `SURVEY_LAHORE_SERVICE_AREAS` to a JSON array of business-approved area labels before accepting new bookings; no coverage is assumed. The endpoint requires a Lahore site city and an approved declared area, CSRF protection, and a UUID `Idempotency-Key`. It locks capacity, returns the confirmed receipt immediately, and queues email. Reuse the same key/body/identity after an uncertain response. Guests also receive a private status link immediately. Installation is quoted and scheduled after the survey. See [the standalone booking guide](Docs/survey-booking-api.md) for payloads, configuration, retries, and privacy.

Staff can inspect bookings/history, replace internal notes, reschedule confirmed surveys, and mark them completed or cancelled. Writes require the inspected booking version and lock capacity; material changes record an audit and queue customer email. Guest tracking exposes only current status, scheduled time, and area/city. Cancellation frees one place and keeps its historical time; equipment orders remain independent. Apply the new booking-management migration before use. See [the staff survey guide](Docs/staff-survey-api.md) and [UX section 10.1](Docs/ux-spec.md#101-private-guest-survey-status).
