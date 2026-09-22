# OctaCam agent instructions

These instructions apply to coding agents working in the OctaCam repository. The project is both a real Pakistani CCTV store and a portfolio project that its owner must be able to explain and maintain. Make focused, reviewable changes and explain consequential decisions in plain language.

## Read before changing code

1. Read `product-spec.md` for product behavior, MVP boundaries, and business inputs.
2. Read the relevant parts of `ux-spec.md` for screens, copy, interactions, accessibility, and responsive behavior.
3. Read the relevant parts of `architecture.md` for structure, APIs, data, transactions, security, and tests.
4. Check `README.md` and nearby code for actual setup commands and established conventions. Do not assume that a planned directory or feature already exists.

The documents have distinct responsibilities; this file governs how agents work. If specifications disagree or a request changes an agreed behavior, identify the conflict and propose the smallest coordinated spec update. Follow an explicit new user decision after documenting the change. Never silently implement an out-of-scope feature. In particular, `architecture.md` calls for guest survey tracking while `ux-spec.md` does not yet fully specify that later tracking screen; update the UX spec when implementing that screen.

## Work in small slices

- Confirm the specific requirement and its acceptance behavior before editing. Inspect only the relevant code and documents, then make the smallest cohesive change. Do not rewrite unrelated areas.
- Use the implementation sequence in `architecture.md` section 92 as a guide, adapting to the actual repository state. Finish one reviewable slice before beginning another unless the user requests a larger scope.
- Briefly explain meaningful choices and trade-offs. Prefer straightforward code the owner can understand in an interview over clever abstractions.
- Add focused tests where failures matter, especially permissions, money, inventory, capacity, idempotency, and authentication. Run the relevant existing checks; report what passed, what failed, and what could not run. Do not claim an unrun check passed.
- Summarize changed files, user-visible behavior, and remaining risks. Suggest one conventional commit message (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, or `chore:`) for the completed slice. Do not commit or push unless the user asks or repository instructions authorize it.
- Avoid adding new major libraries or services without explaining the need, trade-offs, and an update to `architecture.md` where appropriate. Never add secrets, real customer data, or generated build artifacts to Git.

## MVP guardrails

- The storefront is English, uses PKR, and sells separate products in cameras, DVR/NVR recorders, storage, and accessories. Hikvision and Dahua are prominent brand routes; facts about compatibility, warranty, and specifications must come from approved product data.
- Equipment checkout supports guest and registered customers, with **cash on delivery only**. Show the server-calculated itemized amount before submission. Do not add cards, JazzCash, Easypaisa, Raast, bank transfer, or another payment method without a deliberate spec change.
- A Lahore customer may book a **free site survey** alone or with an equipment order. Installation is quoted and scheduled offline after the survey; a survey slot is not an installation appointment. An order and a related booking have separate lifecycles after creation.
- Homepage promotional banners are approved static content shipped with code, shown one at a time with manual controls and no auto-advance. Do not add a staff banner editor, scheduling, or a general CMS to the MVP.
- Excluded features include kits/bundles, variants, coupons, reviews, wishlists, customer self-service cancellation and returns, automated courier tracking, and advanced staff roles. Check the complete exclusions in all three specs before expanding scope.
- Do not invent tax rates, shipping fee, contact details, service-area boundaries, stock, product claims, warranty terms, delivery promises, or policy wording. Keep unresolved business values centralized and clearly flagged for approval before live sales.

## Architecture and code boundaries

- Keep the documented monorepo structure: `frontend/`, `backend/`, `docs/decisions/` when needed, and root specifications. The frontend is React + TypeScript in React Router Framework Mode; the backend is a Django/DRF modular monolith using PostgreSQL and a versioned REST API (`/api/v1/`). The public site and API should appear under one origin in production.
- Server-render useful public product, category, and brand content for search discovery. Keep stable readable URLs, metadata, canonical links, and a sitemap for published public pages. Private account, checkout, guest tracking, and staff pages must be protected and `noindex` where specified.
- Django owns prices, discounts, tax, shipping, stock, survey capacity, totals, roles, fulfillment, and payment state. React never connects to PostgreSQL. Keep the browser cart to product IDs and quantities in local storage; it does not reserve stock or persist trusted prices.
- In Django, keep API/serializer validation, read selectors, domain services, and ORM responsibilities clear. Put consequential writes in explicit services rather than signals: checkout, stock movement, cancellation/restock, survey booking/rescheduling, state transitions, audit records, and email-outbox writes.
- Use database transactions and appropriate row locks for stock and survey capacity. Checkout has quote and place steps; recalculate on placement and require renewed customer review if price or availability changed. Use idempotency keys to prevent duplicate orders/bookings. If a combined checkout cannot book its selected survey slot, roll back the entire creation and preserve form input for correction.
- Store immutable order-item and pricing snapshots. Keep COD collection state separate from order fulfillment state. Preserve an audit trail for sensitive staff changes. Persist transactional email in the PostgreSQL outbox so email failure cannot undo a successful order or booking.
- Use the custom email-login user model from the first migration. Keep access JWTs in memory, rotating refresh tokens in secure HttpOnly cookies, and enforce CSRF protection for cookie-authenticated operations. Enforce staff permissions and customer ownership in Django; a hidden frontend route is not authorization. Guest tracking links must be unguessable, scoped, and privacy-limited.
- Keep public browser API calls on same-origin `/api/v1/` paths; SSR loaders may use the internal backend URL as documented. Preserve the shared API error contract and update OpenAPI documentation when changing API behavior.
- Keep infrastructure simple. Do not add microservices, Redis, Celery, Elasticsearch, Kafka, GraphQL, Kubernetes, Django Channels, a separate staff SPA, a server-side cart, or Redux without a justified architecture change.

## UI and content quality

- Follow `ux-spec.md` for navigation, home layout, forms, states, mobile behavior, and support links. Use the approved blue/black interlocking OC logo master; preserve its proportions and derive actual design tokens from the asset after checking contrast. Do not assume an unapproved hex value or treat a white-background PNG as transparent.
- Make product names and model numbers scannable for installers and explanations clear to new buyers. Display actual product images and structured technical specifications. Keep essential banner copy as live text with a valid destination and an image-failure fallback.
- Provide intentional loading, empty, success, error, stock-change, unavailable-slot, and uncertain-submission states. Preserve entered checkout and survey data on recoverable errors. Never imply an order or booking succeeded until the server confirms it.
- Use semantic HTML, keyboard-accessible controls, visible focus, meaningful alt text, field-associated errors, textual status messages, adequate contrast, and reduced-motion support. Check narrow phone, tablet, and desktop layouts without horizontal overflow.

## Verification before handing off

- For changed frontend code, run the relevant lint, typecheck, tests, and production build that exist in the repository. For backend changes, run relevant format/lint checks, migration consistency, and tests using PostgreSQL where transactional behavior matters. Follow the repository's actual commands rather than inventing them.
- Test key cross-boundary flows when they are touched: guest COD checkout and signed-in history; safe retry with the same idempotency key; final-unit purchase race; final-slot booking race; combined checkout rollback; one-time restock on cancellation; guest-link privacy; staff-only access; and email failure after commit. These are targeted checks, not a demand to run the full suite after every small edit.
- Before live sales, verify approved tax and shipping configuration, genuine policy/contact/product data, HTTPS, durable media, email delivery and retries, database backups with a restore test, and production health checks as required by `product-spec.md` and `architecture.md`.
