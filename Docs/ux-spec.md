# OctaCam UI/UX Specification

**Status:** Final design specification for the MVP, subject to the business inputs listed in §14  
**Companion source of truth:** `product-spec.md` (the attached OctaCam Product Specification)  
**Market and language:** Pakistan; English storefront; PKR  
**Last updated:** 2 October 2026

## 1. Purpose and scope

This document defines how customers and staff experience the OctaCam MVP. The product specification defines business behavior and release boundaries; this document defines navigation, screen content, interactions, responsive behavior, and user-facing states. When a requirement here conflicts with `product-spec.md`, reconcile the two before implementation. Technical rendering, APIs, database structure, and specific UI libraries belong in `architecture.md`.

The store sells **individual** CCTV cameras, DVR/NVR recorders, surveillance storage, and essential accessories throughout Pakistan. Lahore customers can book a **free site survey**, with or without an equipment order. Installation quotes and scheduling happen after the survey, outside the website. Equipment checkout is **COD only**. There are no product bundles, kit builder, digital payments, reviews, coupons, or self-service cancellation in the MVP.

## 2. Experience principles and audiences

1. **Help both novices and installers.** Use plain-language summaries, then accurate model/SKU and structured specifications. Never infer compatibility from incomplete product data.
2. **Put price and availability up front.** Show prices in PKR, identify sale prices honestly, and make shipping, tax, warranty, and availability easy to inspect before commitment.
3. **Keep the route to an order short.** Search, brand and category navigation, cart, and guest checkout must work without requiring account creation or staff contact.
4. **Earn trust with verifiable information.** Show genuine contact routes, approved policies, relevant warranty terms, and precise survey versus installation language. Do not invent testimonials, stock claims, delivery guarantees, or product capabilities.
5. **Support keyboard and mobile use.** Every important action, filter, menu, banner control, form, and status update must work without a pointer.

Primary journeys: a household or small-business buyer browsing by product type; an installer looking up a known model or brand; a guest buying by COD and tracking by secure link; a Lahore customer arranging a site survey; and a staff member processing orders and bookings.

## 3. Brand and visual system

- **Final logo reference:** the first blue-and-black image from the selected OctaCam logo set, preserved in this repository as the RGBA master `Logo/OctacamLogo.png`: interlocking black **O** and electric-blue **C**, with the “Octa” black / “Cam” blue wordmark. Preserve its proportions, letterforms, and real transparency. The frontend asset remains unchanged. On 8 October 2026 the owner approved a horizontal header composition: crop the symbol and original wordmark in SVG viewboxes, with the wordmark to the right. Below 640px show the symbol alone to preserve room for touch controls; the home link retains its accessible OctaCam name. The original square composition remains available for the footer and reference preview. Create an approved dark-surface variant before placing it on dark backgrounds; do not stretch, recolor, or use `Logo/logo.png`, which has a white background, as though it were transparent.
- **Palette application:** white or very light neutral shopping surfaces; near-black body text and headers; logo blue for primary links, focused elements, and key calls to action. Muted greys separate information. Green or amber may communicate genuine success or caution, with accessible text labels; never make status depend on color alone. Sample interface colors from the final export and check contrast before fixing design tokens. This spec does not assert unapproved hexadecimal brand values.
- **Shared styling:** use the centralized design tokens defined in `architecture.md` for colors, typography, spacing, radii, shadows, and motion. Tailwind CSS and reusable shadcn/ui components share those tokens; customize components to OctaCam's visual system while retaining accessible semantics and interaction behavior.
- **Typography:** a clean, legible sans-serif with clear heading hierarchy and readable numbers/model codes. Use a distinct treatment for SKU and technical units, without making long model numbers wrap unpredictably. Keep paragraph widths comfortable and avoid all-caps body text.
- **Visual tone:** modern electronics store, restrained spacing and borders, real product photos, no unverified security promises. White space should help scanning, while product lists can be dense enough for professional shoppers.
- **Page width:** use the full viewport width with no centered page-width cap. Apply a small shared side gutter to header/footer content and the main page wrapper, scaling from 0.75rem on narrow phones to 1.25rem on desktop; homepage banners, section headings, and grids align to that gutter. Keep internal padding for cards and controls, and a narrower measure for long-form reading. The owner refined this full-width direction on 7 October 2026 using Smart Links screenshots showing small side gutters.
- **Header colors and vertical density:** following the owner's Smart Links reference on 7 October 2026, use a near-black service strip, a white logo/search row, and navy desktop navigation and expanded mobile menu with white text and light-blue focus rings. Keep these colors in shared interface tokens; the approved logo stays on white. Reduce the main top/bottom padding to 1rem on phones and 1.5rem on larger screens, and homepage section gaps to 2rem/2.5rem. Use a shorter hero with a display heading capped at 3.5rem, and compact header and footer spacing while retaining 44px control targets.
- **Search and footer treatment:** the owner's 7 October 2026 refinement uses a centered desktop search pill capped at 42rem, with equal header columns on either side so the logo and account/cart widths do not shift it. The 8 October 2026 refinement uses a magnifier-only submit button with an accessible name on desktop and in the mobile search panel, a 0.75px border and immediate blue focus border with a soft halo. Center the service-strip text and reduce the logo/search row to a 4rem minimum height while retaining 44px controls. The footer is a square-cornered navy surface matching navigation, with light headings, readable muted copy, and three desktop columns for the brand/survey information, contact, and policies/support. Stack columns on phones. Display the unchanged logo on a small white panel until an approved dark-surface variant exists; keep the development note on a light strip below. Footer colors, gutter, header height, search border/focus treatment, and search maximum width are shared tokens.
- **Imagery:** use factual product photography with descriptive alternative text. Do not embed essential promo copy only in an image; live headline and button text stay readable when images fail or crop.
- **Icons:** the owner's 8 October 2026 refinement uses library SVGs for cart, account, search/menu, survey, support, and contact channels. Use blue for general actions, violet for account, green for WhatsApp, rose for phone/support, and amber for email; contact and dark-surface icons use light tinted circular badges. Keep these decorative accents in shared tokens, distinct from semantic status colors. Icons accompany visible labels or an accessible control name; hide decorative SVGs from assistive technology. The cart label may be visually hidden on narrow phones to preserve header space, while remaining accessible.

## 4. Information architecture and shared navigation

| Area | Primary route and content |
| --- | --- |
| Home | Logo, search, brand-first navigation, promotion, categories, trust/support, Lahore survey entry. |
| Shop | All products; brand landing routes for **Hikvision** and **Dahua**; category routes for Cameras, DVR/NVR Recorders, Surveillance Storage, Accessories; search results. |
| Product | One separately sellable model/capacity per page; images, overview, specifications, price, stock, warranty, delivery, support. |
| Cart and checkout | Cart, single-page COD checkout, order confirmation. |
| Surveys | Standalone Lahore survey booking and booking confirmation; private guest survey status link; optional survey section during checkout. |
| Account | Register, sign in, password reset, signed-in order history and order detail. |
| Guest order | Secure email link to a scoped order-status page. |
| Help and policies | Contact, About, Shipping, Returns, Warranty, Privacy, Terms. |
| Staff | Restricted dashboard, catalog maintenance, orders, survey slots and bookings. |

**Desktop header:** logo links home; prominent product/model search; All brands, then every active registered brand in backend order, then Shop all products, followed by Cameras, Recorders, Storage, Accessories; cart with item count; account entry; a discoverable “Free Lahore Site Survey” link. Brand routes lead; category routes remain one action away. Wrap desktop navigation when the active brand list grows; the mobile menu exposes the complete list. Include all backend brand pages and never promote inactive records. Hikvision and Dahua remain prominent when registered and active. This navigation ordering was approved by the owner on 8 October 2026. A slim, factual service strip may state nationwide equipment delivery and Lahore surveys without promising times or fees that have not been approved.

**Mobile header:** logo, search control, cart count, and menu control; menu exposes the same brands, categories, survey, account, contact, and policy routes. Menu and search open with clear close controls, visible focus, and no hidden hover dependency. Do not cover the cart or key checkout actions with a floating support button.

**Footer:** contact via WhatsApp, phone, and email; policy links; survey service limitation; verified business details when available. External contact links are labeled clearly. No invented business address or support hours.

**Wayfinding:** category and product pages have breadcrumbs; product URLs are stable and readable; search/filter/sort state persists in a shareable URL where practical. Search box accepts product names and exact or partial model numbers. The logo and primary navigation are consistent across storefront pages; checkout uses a quieter header but retains a safe path back to cart and support.

## 5. Homepage and promotional banners

Recommended order on desktop and mobile:

1. Header and search with brand-first navigation.
2. **Hero promotion directly below navigation:** first banner visible immediately, image plus live headline, optional short text, and one clear link to a real product, brand, category, or other existing campaign destination. Give desktop and mobile layouts/assets enough safe space for cropping and text; avoid image-only messaging.
3. Visible Hikvision and Dahua entry links, plus All Brands.
4. Shop by category: Cameras, DVR/NVR Recorders, Surveillance Storage, Accessories. Show no fixed kits as products.
5. Optional curated individual products only when genuine published products are available; otherwise omit the section cleanly. Do not show false “bestseller” labels or ratings.
6. A compact “Need help planning your system?” panel explaining the **free Lahore site survey** and linking to standalone booking; say that installation is quoted afterward.
7. Factual store reassurance (COD, applicable warranty details, delivery policy, support) and footer.

**MVP banner behavior:** banners are configured as static launch content and changed through a code/content deployment. A developer can provide multiple approved banners with desktop and mobile images, live headline, accessible button label, destination, and display order. Show **one at a time**; controls are previous/next buttons and an indicator that names the current slide. The initial banner never waits for interaction to appear. Slides **do not auto-advance**. If there is only one, omit carousel controls. Every banner destination must be valid; no expired sale copy should stay live. Provide a readable fallback when an image fails.

**Motion behavior:** Motion for React is only for restrained homepage entrance and selected scroll animations. Essential content, navigation, banner copy, and shopping/survey links remain immediately visible in the server-rendered page, before hydration and without animations; do not hide them pending an entrance or scroll trigger. Remove nonessential movement when reduced motion is requested. Animation must not delay interaction, shift focus, or change banner selection automatically. Simple hover/focus transitions use CSS, with immediate visible focus and state feedback.

**Decision record:** the earlier concept allowed staff to upload, schedule, reorder, and disable banners in a dashboard. The final selection for launch is **static banners**, so those staff controls and automatic scheduling are deferred. The product spec excludes a general-purpose CMS and timed promotion rules. If staff-controlled banners become a requirement, update both specs before building them. Static promotions must not imply coupon or timed-pricing features.

## 6. Catalog discovery, search, and product cards

**Brand and category pages:** visible heading and concise explanation; product count; sort; filters; responsive product list/grid. Brand pages allow category filtering and category pages allow brand filtering. Available filters include category, brand, price range, stock availability, and **only attributes appropriate to the active category** (for example, camera resolution or indoor/outdoor suitability where the data exists). Technical attributes must come from accurate product records. Do not present a camera-use filter for hard drives.

**Search results:** show the query, result count, current filters, and relevance sort by default; price low-to-high/high-to-low are available. Make matching model numbers visible on cards. A zero-results state echoes the query and offers a way to clear filters, browse categories, or contact support. Do not imply a compatible substitute without verified data.

**Desktop filtering:** an obvious filter area beside results. **Mobile filtering:** a labeled button opens an accessible overlay/panel with Apply and Clear controls; selected filters remain visible as removable chips after closing. Changing sort or filters keeps the shopper oriented, reflects the current results, and does not discard the query. When a selected filter is unavailable for a different category, remove it visibly and explain the changed scope.

**Filter styling refinement (8 October 2026):** use a compact white desktop rail with a navy heading, blue sliders icon, slim section dividers, native selectors, and exact minimum/maximum PKR inputs. Keep controls at least 44px tall, use consistent slim borders with immediate blue focus outlines, and present selected filters as light-blue removable chips. Cap the catalog search measure and align sort controls with the results heading. On phones/tablets, open a full-height right drawer with a dim navy backdrop, a scrollable field area, and fixed Clear/Apply controls that respect the device's bottom safe area. Slide it in over 260ms using shared motion tokens; disable that movement for reduced motion. Focus enters immediately, Tab stays inside, Escape/Close/backdrop dismiss it and restore trigger focus. Switching to desktop dismisses the drawer and restores scrolling. The owner requested this interaction using Smart Links references; it does not change filter semantics or introduce guessed price bounds or brand artwork.

**Product card minimum:** real image or neutral fallback; product name; current PKR price; struck-through regular price only for a valid sale; link to details. In the owner's later 8 October 2026 refinement, separate brand, model/SKU, and stock rows are omitted from cards; those facts remain on product detail pages and availability filters remain available. Optional quick add only if its stock and quantity behavior are unambiguous; product page remains the reliable add-to-cart route. Out-of-stock cards remain discoverable and cannot be purchased.

**Product card refinement (8 October 2026):** following the owner's Smart Links screenshots, use compact image-led cards with square white image areas, rounded image corners, centered product copy, and no oversized padded outer box. Cap cards at 16rem and use two columns on narrow phones, increasing to five on wide desktops; account for the desktop filter rail when sizing catalog grids. Show up to five genuine homepage records. Make the whole card one semantic product link with a pointer cursor and visible keyboard focus, so both the image and text open details. Keep the full product name in accessible text; visually limit the title to three lines. Use only image, product name, and a compact price row in the card, with medium-weight titles and tighter copy spacing. Show a solid green Sale badge with white text only for a valid sale; badge colors use contrast-checked shared tokens. This smaller size and simpler copy follow the owner's second Smart Links comparison on 8 October 2026. On fine-pointer hover or keyboard focus, show the second approved image in staff-defined order if it has loaded; retain the main image when there is no second image or it fails. Touch taps navigate directly. Remove the image fade under reduced motion; initial SSR shows the main image without animation.

## 7. Product detail page

| Area | Required UI |
| --- | --- |
| Identity | Breadcrumb, brand, exact product name, model/SKU, category. |
| Media | Main product image with selectable thumbnails where available, keyboard-operable controls, useful alt text and fallback. |
| Purchase | Selling price in PKR, regular price only if valid sale, stock text, quantity capped by live available stock, Add to cart, concise COD and shipping-policy cue. |
| Explanation | Short plain-language summary followed by factual full description. |
| Technical data | Scannable, labeled specification groups relevant to that type, with units and exact model information. Missing attributes are omitted or marked unavailable, never guessed. |
| Trust and support | Applicable product warranty if supplied; warranty and delivery policy links; WhatsApp, phone, and email support options. |
| Survey | A secondary free Lahore site-survey link where appropriate; clearly separate equipment purchase from later installation quote. |

On mobile, name, price, stock, and purchase action are visible without requiring the customer to read the entire specification first. A sticky add-to-cart bar is optional only if it does not hide content or duplicate contradictory stock/price information. If stock changes, update the quantity/action and announce the change. If the item is out of stock, disable purchase with a textual explanation; do not show a deceptive “notify me” control without a corresponding feature. Product images and text must not promise unsupported compatibility or warranty.

## 8. Cart and single-page COD checkout

### Cart

Show each item’s image, name, model/SKU, unit price, quantity control, line total, and Remove action. Summarize subtotal in PKR and link to shipping information. The flat shipping fee and any tax should be explained; the exact payable total is shown at checkout after applying the business-approved rules. Quantity cannot exceed current stock. A cart is **not a reservation**. Empty-cart UI offers catalog entry points. If a price or stock level changes, explain the change beside the affected item and require review before submission.

### Checkout structure

Single-page sections in this order: (1) contact name, email, phone; (2) Pakistan delivery address; (3) optional **free Lahore site survey**; (4) persistent or nearby order summary and final review. Keep sign-in optional and guest continuation obvious. Signed-in customers may start with saved details but can review and edit them. Label required fields, use helpful input formats and explicit error messages; preserve all entered information on validation failure.

The summary lists item name/model, quantity, unit price and line total, any sale-price saving already included, product subtotal, flat nationwide shipping charge, applicable tax as a separate amount, and **final PKR amount due on delivery**. Show only **Cash on delivery** as payment method; do not hint at cards, wallets, bank transfer, Raast, or an online payment choice. Show published delivery limits/estimates and policy links without assuming their values. The main button says **Place COD order** and is enabled only when the form is valid and the current total has been reviewed.

**Optional survey section:** a clear opt-in control opens Lahore site address, short description of needs or existing equipment, and available dated/timed slots. Explain that booking is free, equipment bought elsewhere can be reviewed, and installation pricing/scheduling happens after the survey. The survey address may differ from the shipping address. Check the launch Lahore coverage before showing bookable slots; an outside-area address gets an explanation and contact option, with the equipment order still possible after the survey option is removed. A customer can proceed with equipment without opting in. Do not infer service eligibility solely from a delivery city field.

**Submission and race conditions:** before committing, refresh and display any changed price, shipping, tax, or stock; require explicit review of a changed total. If the selected survey slot has been taken, preserve the whole form and ask for another available slot **before submitting either the order or survey**. Do not silently omit a requested booking. While submitting, disable repeated submission, show progress, and give one clear result; an ambiguous network timeout should offer a safe status/retry path without risking a second order. The server remains authoritative for amounts, stock, and slot capacity.

Combined placement uses the same contact and guest/account identity for both
resources; review the independent site address with the selected survey time.
After an uncertain response, retain one checkout UUID and the exact body,
including quote token and survey choice, to recover both references. Do not
change the slot, drop the survey, or generate a fresh UUID while the result is
uncertain. A definitive slot failure creates neither resource: retain all
entries, refresh availability, and require customer review of a new selection.
If survey coverage is not configured, show an unavailable state and preserve
the form; equipment-only continuation requires deliberate removal of the survey
option. Display input errors against the nested site fields.

**Confirmation:** show order reference, confirmed itemized total, COD amount, delivery details and current order state. When selected, show a **separate** survey reference, date/time, address, and booking state with text explaining its independent lifecycle. Offer order-status access and support even if email is delayed. Email contains the order details and secure guest tracking link; survey confirmation is sent separately as required by the product specification. Do not describe a booking as an installation appointment.

The combined receipt includes the survey's free booking fee and installation
explanation without adding them as equipment charges. Show separate private
guest links for equipment and survey immediately. Recovered receipts may show
later staff-managed states; retrying creation must not suggest that a cancelled
order or survey was rebooked. Changes remain support requests for each resource.

## 9. Standalone site-survey flow

Entry points: header, homepage survey panel, product page support area, and relevant help content. The survey page states **Lahore service area only**, **free site survey**, and **installation quote afterward**, with no purchase requirement. Explain that staff review equipment purchased elsewhere. Collect name, email, phone, Lahore site address, short needs/existing-equipment description, and an available slot. Show date/time in Pakistan local time and make capacity only visible through actual available slots, without promising a slot until confirmed.

Before submission, review the address, slot, and contact details. On slot conflict, retain entries and offer fresh available slots. On success, show a distinct booking reference, slot and address summary, support contact for changes, and confirmation-email notice. An unavailable email service does not invalidate a confirmed booking. Customers request changes or cancellation through support; staff update the booking. Do not show a self-service rescheduling or installation-payment action.

The standalone API requires a declared site area from backend-configured approved Lahore coverage, in addition to the site city. When coverage is not configured, explain that booking is unavailable and preserve the form. Retain the same booking UUID and body after an uncertain submission, with the same guest or signed-in identity, to recover the confirmed result. The receipt says **free site survey confirmed; installation quoted and scheduled afterward**. Guests receive their private status link immediately as well as by email.

## 10. Accounts, order status, and contact

- **Account:** register/sign in with email and password, reset password, see signed-in order history and individual order detail. Guest checkout remains prominent. Do not automatically attach historical guest orders to a later account.
- **Order history/detail:** reference, date, item snapshot, total, order state (placed → confirmed → packed → shipped → delivered, or cancelled), and courier name/tracking link when staff has entered them. Display COD payment status **separately** (uncollected/collected), never infer it solely from shipment or delivery.
- **Guest order link:** a long, unguessable emailed link opens only that order, with limited personal information. Avoid placing address or private contact details in a shareable page title or preview. If the link is invalid, show a neutral support path without revealing whether a reference belongs to someone else.
- **Guest survey link:** show only that booking's reference, state, Pakistan-local slot date/time, site area/city, installation-after-survey explanation, and support path. Keep the street address, contact details, needs text, and internal notes off this limited page. Treat the link as private, prevent indexing and caching, and use a neutral support path for invalid links. Changes and cancellation remain support requests.
- **Cancellations/returns/warranty:** show the published policy and support routes; no customer cancellation button, return portal, or online warranty claim workflow.
- **Contact:** verified WhatsApp, phone, and email links on help pages and contextually near purchase decisions. Support is a route for questions, not a mandatory step in buying.

### 10.1 Private guest survey status

The private link on the guest receipt and in survey emails opens the status of
that one booking without sign-in. Signing in later does not attach a guest
booking to the account. Label the page **Site survey status**, with a generic
page title and no personal details in previews. Explain that the link is private.

Show the booking reference, textual **Confirmed**, **Completed**, or
**Cancelled** status, scheduled start/end in **Pakistan time (Asia/Karachi)**,
and site area/city. The current confirmed time changes when staff reschedule;
a cancelled booking retains its last scheduled time, labelled **Cancelled
survey time**. Completion does not promise an installation appointment. Keep
**Free site survey; installation quoted and scheduled afterward** and the
approved support route visible in every successful state. An associated
equipment order has a separate status; this page does not change it.

Do not show the street address, customer name/contact, needs description,
equipment order details, internal notes, staff identities, or change history.
Offer no edit, cancel, reschedule, or installation-payment control. Customers
request changes through support using their booking reference.

On initial load, show a textual loading state. A temporary connection/server
error offers a retry and support; it must not imply the booking was cancelled
or disappeared. An invalid or revoked link shows the same neutral **This
survey link is unavailable. Contact support for help.** message, without
revealing whether another customer's reference exists. Keep successful and
error pages out of search indexes, browser/shared caches, referrers, and URL
analytics. Reopening or retrying a valid link fetches current server status.
Use stacked content on narrow screens, visible focus, and accessible textual
status announcements. The tracking API is implemented; the frontend screen
remains part of the later storefront slice.

**Screen layout and controls:** place the heading and private-link explanation
before a compact booking summary. Use labelled reference, status, survey time,
and area/city rows, followed by the installation notice and approved support
link. Keep the same reading order on phone, tablet, and desktop; long references
and area labels wrap without horizontal scrolling. Retry and support controls
work by keyboard and have visible focus. Announce loading, updated status, and
errors in text without moving focus unexpectedly. A passed scheduled time does
not mean the survey is completed; display only the server-confirmed state.

| State | Content and recovery |
| --- | --- |
| Loading or retrying | Show **Loading site survey status…**; prevent duplicate retries and do not display a speculative booking state. |
| Confirmed | Show **Confirmed** and the current scheduled start/end. Reopening the link after staff reschedule shows the new confirmed time, without a change-history timeline. |
| Completed | Show **Completed** and the saved survey time. Explain that any installation is quoted and scheduled separately; offer support, with no installation-booking control. |
| Cancelled | Show **Cancelled** and **Cancelled survey time** using the retained start/end. No slot picker or rebooking action appears on this status screen; the equipment order remains independent. |
| Invalid, revoked, wrong-resource, or missing link | Show **This survey link is unavailable. Contact support for help.** and the approved support route. This is the single unavailable state, not an empty booking list; never invite lookup by reference or email. |
| Temporary network/server failure or rate limit | Explain that status could not be loaded and offer retry/support; honour a server retry delay when supplied. Never claim that a booking was cancelled or that retry creates a booking. |

**Privacy and contract handoff:** the existing read-only API returns `reference`,
`status`, `slot` (public ID and scheduled start/end), `site_area`, `site_city`,
and `installation_notice`. The slot ID is not customer-facing content. Use only
this limited response; never fetch a staff or full creation receipt to fill
the screen. Invalid-link API failures map to the neutral unavailable message;
unexpected or incomplete responses use the retryable error state, not a guessed
success. No valid-link lookup requires sign-in or a new booking submission.

Apply privacy controls to the HTML page and its data/error responses, including
browser/shared-cache prevention and no-referrer behaviour on support links.
Do not place the token, booking data, or full private URL in persistent browser
storage, analytics, error reports, social previews, or a sitemap. Reopening and
retrying always read current server state; the screen has no automatic refresh
or animation requirement. Approved support details remain a business input;
use a clearly flagged placeholder during development until supplied.

Current guest receipt and email links open the JSON API rather than a storefront
page. The later screen slice must coordinate a customer-page link handoff with
the backend, preserving signed-token scope and existing API links. This UX
definition does not introduce a new endpoint or change booking behaviour.

**Acceptance checks for the later screen slice:**

1. A valid standalone or order-linked guest link shows only its own booking's
   allowed fields, Pakistan time, installation notice, and support path.
2. Reopening after staff rescheduling, completion, or cancellation shows current
   server status; cancellation retains the last survey time and changes no order.
3. A forged, revoked, order-token, or missing link gives the same unavailable
   message, with no customer or reference-existence disclosure.
4. Loading, offline/server failure, and retry remain textual and keyboard usable;
   retries perform a read and never create, cancel, or reschedule a booking.
5. Success and error pages carry the privacy headers specified in architecture
   section 34 and remain absent from caches, previews, token-bearing logs,
   analytics, and sitemaps.
6. Narrow-phone, tablet, and desktop layouts have no horizontal overflow; focus
   and announcements work with keyboard use and reduced motion.

## 11. Staff dashboard UX

Authenticated staff see a simple desktop-first workspace that still functions on a smaller screen. One staff permission level applies. The opening view highlights new orders, orders needing action, and upcoming survey bookings, with direct links to each record; no broad analytics suite.

The opening view uses short, bounded lists for recent orders, upcoming surveys,
recent staff activity, and failed transactional emails. Counts indicate more
records; each section links to its paginated list. Show a useful empty state
when there is no work and a retryable loading error when the summary cannot be
fetched. Email rows show delivery state and whether manual retry is available.
Disable the retry action for queued, sent, claimed, automatically due, or
permanently invalid events, and refresh the row after an attempted retry.
Repeated clicks must not imply that another email was queued.

| Screen | Main staff tasks and states |
| --- | --- |
| Products | List/search by name or SKU, filter publication and stock; create/edit name, category, brand, images, specifications, regular/sale price, warranty, stock and published state. Preview customer-facing details; validate required values and show save results. |
| Categories and brands | Maintain the taxonomy used by storefront navigation and filters; optionally upload, replace, or remove a brand logo (PNG, JPEG, or WebP up to 2 MB). A brand without a logo remains usable by name. Unpublished/empty brand destinations must not lead to misleading blank storefront sections. |
| Orders | Find by reference/status; inspect immutable purchase snapshot and delivery details; move through allowed statuses, enter courier fields, mark COD collected independently; confirm cancellation/restock action and its result. For now, offer staff cancellation only on placed or confirmed orders with uncollected COD, require a reason, and show that purchased quantities return to stock. Route other cases to support handling until policy is approved. |
| Survey slots | Add future date/time and capacity; show times in Pakistan local time, booked count, and remaining availability. Staff can close a slot to new bookings while its existing appointments remain confirmed. Explain that booked slots cannot move in time or have capacity reduced below existing non-cancelled bookings; show a save conflict when another staff edit wins. |
| Survey bookings | Find by reference/status; inspect contact, site needs, current survey time, and related order when present; edit clearly labelled internal notes; view who changed the booking and when. Reschedule confirmed bookings to an available future slot, or mark them completed/cancelled. Show old and new times before confirming a move; explain that cancellation releases the survey place and does not cancel equipment. Completed/cancelled bookings have no reopen or reschedule action. |

Sensitive customer data appears only to authorized staff. Use clear labels for internal-only notes and confirmations for consequential status, stock, or slot changes. Show who changed price, stock, order status, or booking status and when, consistent with the product spec. A failed save never appears successful.

For survey changes, retain unsaved notes/slot choice on validation or capacity
failure. If another staff write wins, reload the booking and let staff review
the new state before another attempt. After an uncertain response, inspect
current status/history before retrying; do not silently apply a new move.
Show the confirmed change immediately and explain that the customer email is
queued. Email delay does not undo it. Internal notes are not emailed. Completing
a survey records staff confirmation that the visit occurred; installation is
still quoted and scheduled offline afterward.

**No launch banner editor:** the dashboard does not include banner upload, scheduling, or a general page editor under the chosen static-banner scope (§5).

## 12. Responsive, accessibility, and content rules

- Design mobile-first for narrow phones, then tablet and desktop widths. Validate actual small-phone, tablet, and wide-desktop layouts; avoid fixed width product tables and horizontal page scrolling. Product specs may use stacked name/value rows on mobile.
- Buttons and links have visible text or accessible names, useful focus order, visible focus styling, adequate touch targets and color contrast. Menus, dialogs, filters, image galleries, and carousel controls work with keyboard and assistive technology. Do not move focus unexpectedly when a filter changes.
- Form errors identify the field and correction; announce significant cart, stock, slot, and order-status changes in text. Never use color alone for availability, errors, or status. Provide skip navigation and meaningful page headings. Respect reduced-motion preferences in Motion and CSS; essential content never waits for animation, and banners never move on their own.
- Keep image sizes and loading behavior appropriate to mobile connections. Prioritize the visible hero and primary product image; prevent layout jumps with reserved image space. Do not let a failed image, network request, or email block a successful order/booking confirmation.
- Public brand, category, product, and help pages use descriptive headings, stable URLs, informative titles/descriptions, and useful text content for search discovery. Details of rendering and indexing belong in `architecture.md`.
- All shipping fees, tax amounts, warranty periods, delivery estimates, service boundaries, and business claims must come from approved business inputs. User-facing copy distinguishes a free **site survey** from a paid, separately quoted installation.

## 13. Screen states and MVP acceptance checks

Every data-driven page needs a purposeful loading, empty, error, and success state. Examples: no published products under a brand; no search matches; empty cart; sold-out product; stale price/stock; no survey slots; taken slot; checkout validation error; uncertain submission result; email delay; invalid guest tracking link; staff save conflict. Recovery controls should preserve user input where appropriate and tell the customer what to do next.

1. A first-time buyer starts at a banner or category, reaches a product, sees real price/stock and specifications, and places a guest **COD** order on mobile with a reviewed PKR total and confirmation.
2. An installer reaches Hikvision/Dahua from primary navigation, searches an exact SKU, filters by relevant attributes, and purchases several separately listed items without needing a sales conversation.
3. Out-of-stock items remain visible in lists and details, with disabled purchase. A checkout stock/price change is explained and requires renewed review.
4. A Lahore buyer adds a free survey during checkout and receives distinct order and survey references. A taken slot leaves entered details intact and stops both submissions until another slot is chosen.
5. A customer books a standalone Lahore survey without purchasing equipment; an outside-area address cannot consume a slot. Installation is described as a separate later quote.
6. A guest follows a secure order link and sees only the relevant order; a registered customer sees signed-in orders only, with order state and COD collection shown separately.
7. Staff can publish/unpublish a product, update stock/price, process and track an order, and manage survey slots/bookings with clear save feedback and recorded changes.
8. At phone and desktop sizes, navigation, banners, filters, checkout, booking, and status pages are keyboard usable and readable; promotional controls do not advance automatically.
9. The MVP never exposes a kit builder, online payment, self-service cancellation/returns, installation booking, or staff banner editor.
10. With normal or reduced-motion settings, and before hydration or without animations, essential homepage content and the initial banner remain visible. Hover/focus feedback is clear; scrolling or elapsed time never advances promotional banners.

Frontend implementation verification includes lint, TypeScript typechecking for `.ts`/`.tsx` files, relevant tests, and a production build using the repository's actual commands. Review shared-token styling and customized UI components for contrast, keyboard/focus behavior, and phone, tablet, and desktop layouts, as well as the motion checks above. A build alone is not a typecheck.

## 14. Approved decisions and pre-launch inputs

**Decisions captured from project planning:** blue/black interlocking OC logo, light shopping surfaces, brand-first navigation featuring Hikvision and Dahua, homepage hero with manually controlled static banners, categories as the first main shopping section, shopping as the primary homepage action, single-page COD checkout, optional integrated survey section, and review/retry when a chosen survey slot is taken.

**Business inputs required before real orders or bookings:** approved tax rules and rates; flat shipping amount and courier coverage/estimates; exact Lahore service boundary and staff slot lengths; verified WhatsApp/phone/email and business identity; approved returns/warranty/cancellation/privacy/terms text; accurate product photos/specifications/stock/prices; production email and support handling. Until supplied, designs and staging content should use explicit placeholders rather than invented values.

**Implementation handoff:** retain React, React Router Framework Mode, TypeScript/TSX, and the existing server-rendering strategy in `architecture.md`; establish centralized design tokens from the approved logo master for Tailwind CSS and customized shadcn/ui components in TypeScript mode; create responsive page designs with the restrained motion rules above; confirm guest-link privacy; implement and review the flows in small increments, including frontend typechecking. Reasons and trade-offs for these frontend choices are recorded in architecture section 6.1. If a decision changes the product behavior (especially banner administration, kits, payment methods, or installation scheduling), update `product-spec.md` and this document together.
