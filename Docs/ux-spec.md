# OctaCam UI/UX Specification

**Status:** Final design specification for the MVP, subject to the business inputs listed in §14  
**Companion source of truth:** `product-spec.md` (the attached OctaCam Product Specification)  
**Market and language:** Pakistan; English storefront; PKR  
**Last updated:** 21 September 2026

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

- **Final logo reference:** the first blue-and-black image from the selected OctaCam logo set, `image-gen-1(4).png`: interlocking black **O** and electric-blue **C**, with the “Octa” black / “Cam” blue wordmark. Preserve its proportions, clear space, and letterforms. Create a clean transparent export and appropriate light/dark variants from the approved master before production use; do not stretch, recolor, or use the white-background image as though it were transparent.
- **Palette application:** white or very light neutral shopping surfaces; near-black body text and headers; logo blue for primary links, focused elements, and key calls to action. Muted greys separate information. Green or amber may communicate genuine success or caution, with accessible text labels; never make status depend on color alone. Sample interface colors from the final export and check contrast before fixing design tokens. This spec does not assert unapproved hexadecimal brand values.
- **Typography:** a clean, legible sans-serif with clear heading hierarchy and readable numbers/model codes. Use a distinct treatment for SKU and technical units, without making long model numbers wrap unpredictably. Keep paragraph widths comfortable and avoid all-caps body text.
- **Visual tone:** modern electronics store, restrained spacing and borders, real product photos, no unverified security promises. White space should help scanning, while product lists can be dense enough for professional shoppers.
- **Imagery:** use factual product photography with descriptive alternative text. Do not embed essential promo copy only in an image; live headline and button text stay readable when images fail or crop.

## 4. Information architecture and shared navigation

| Area | Primary route and content |
| --- | --- |
| Home | Logo, search, brand-first navigation, promotion, categories, trust/support, Lahore survey entry. |
| Shop | All products; brand landing routes for **Hikvision** and **Dahua**; category routes for Cameras, DVR/NVR Recorders, Surveillance Storage, Accessories; search results. |
| Product | One separately sellable model/capacity per page; images, overview, specifications, price, stock, warranty, delivery, support. |
| Cart and checkout | Cart, single-page COD checkout, order confirmation. |
| Surveys | Standalone Lahore survey booking and booking confirmation; optional survey section during checkout. |
| Account | Register, sign in, password reset, signed-in order history and order detail. |
| Guest order | Secure email link to a scoped order-status page. |
| Help and policies | Contact, About, Shipping, Returns, Warranty, Privacy, Terms. |
| Staff | Restricted dashboard, catalog maintenance, orders, survey slots and bookings. |

**Desktop header:** logo links home; prominent product/model search; top-level Hikvision, Dahua, All Brands, Cameras, Recorders, Storage, Accessories; cart with item count; account entry; a discoverable “Free Lahore Site Survey” link. Brand routes lead; category routes remain one action away. Use an overflow menu only if needed at narrower widths. A slim, factual service strip may state nationwide equipment delivery and Lahore surveys without promising times or fees that have not been approved.

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

**Decision record:** the earlier concept allowed staff to upload, schedule, reorder, and disable banners in a dashboard. The final selection for launch is **static banners**, so those staff controls and automatic scheduling are deferred. The product spec excludes a general-purpose CMS and timed promotion rules. If staff-controlled banners become a requirement, update both specs before building them. Static promotions must not imply coupon or timed-pricing features.

## 6. Catalog discovery, search, and product cards

**Brand and category pages:** visible heading and concise explanation; product count; sort; filters; responsive product list/grid. Brand pages allow category filtering and category pages allow brand filtering. Available filters include category, brand, price range, stock availability, and **only attributes appropriate to the active category** (for example, camera resolution or indoor/outdoor suitability where the data exists). Technical attributes must come from accurate product records. Do not present a camera-use filter for hard drives.

**Search results:** show the query, result count, current filters, and relevance sort by default; price low-to-high/high-to-low are available. Make matching model numbers visible on cards. A zero-results state echoes the query and offers a way to clear filters, browse categories, or contact support. Do not imply a compatible substitute without verified data.

**Desktop filtering:** an obvious filter area beside results. **Mobile filtering:** a labeled button opens an accessible overlay/panel with Apply and Clear controls; selected filters remain visible as removable chips after closing. Changing sort or filters keeps the shopper oriented, reflects the current results, and does not discard the query. When a selected filter is unavailable for a different category, remove it visibly and explain the changed scope.

**Product card minimum:** real image or neutral fallback; product name; brand and model/SKU; current PKR price; struck-through regular price only for a valid sale; clear In stock/Out of stock text; link to details. Optional quick add only if its stock and quantity behavior are unambiguous; product page remains the reliable add-to-cart route. Out-of-stock cards remain discoverable and cannot be purchased.

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

**Confirmation:** show order reference, confirmed itemized total, COD amount, delivery details and current order state. When selected, show a **separate** survey reference, date/time, address, and booking state with text explaining its independent lifecycle. Offer order-status access and support even if email is delayed. Email contains the order details and secure guest tracking link; survey confirmation is sent separately as required by the product specification. Do not describe a booking as an installation appointment.

## 9. Standalone site-survey flow

Entry points: header, homepage survey panel, product page support area, and relevant help content. The survey page states **Lahore service area only**, **free site survey**, and **installation quote afterward**, with no purchase requirement. Explain that staff review equipment purchased elsewhere. Collect name, email, phone, Lahore site address, short needs/existing-equipment description, and an available slot. Show date/time in Pakistan local time and make capacity only visible through actual available slots, without promising a slot until confirmed.

Before submission, review the address, slot, and contact details. On slot conflict, retain entries and offer fresh available slots. On success, show a distinct booking reference, slot and address summary, support contact for changes, and confirmation-email notice. An unavailable email service does not invalidate a confirmed booking. Customers request changes or cancellation through support; staff update the booking. Do not show a self-service rescheduling or installation-payment action.

## 10. Accounts, order status, and contact

- **Account:** register/sign in with email and password, reset password, see signed-in order history and individual order detail. Guest checkout remains prominent. Do not automatically attach historical guest orders to a later account.
- **Order history/detail:** reference, date, item snapshot, total, order state (placed → confirmed → packed → shipped → delivered, or cancelled), and courier name/tracking link when staff has entered them. Display COD payment status **separately** (uncollected/collected), never infer it solely from shipment or delivery.
- **Guest order link:** a long, unguessable emailed link opens only that order, with limited personal information. Avoid placing address or private contact details in a shareable page title or preview. If the link is invalid, show a neutral support path without revealing whether a reference belongs to someone else.
- **Cancellations/returns/warranty:** show the published policy and support routes; no customer cancellation button, return portal, or online warranty claim workflow.
- **Contact:** verified WhatsApp, phone, and email links on help pages and contextually near purchase decisions. Support is a route for questions, not a mandatory step in buying.

## 11. Staff dashboard UX

Authenticated staff see a simple desktop-first workspace that still functions on a smaller screen. One staff permission level applies. The opening view highlights new orders, orders needing action, and upcoming survey bookings, with direct links to each record; no broad analytics suite.

| Screen | Main staff tasks and states |
| --- | --- |
| Products | List/search by name or SKU, filter publication and stock; create/edit name, category, brand, images, specifications, regular/sale price, warranty, stock and published state. Preview customer-facing details; validate required values and show save results. |
| Categories and brands | Maintain the taxonomy used by storefront navigation and filters; unpublished/empty brand destinations must not lead to misleading blank storefront sections. |
| Orders | Find by reference/status; inspect immutable purchase snapshot and delivery details; move through allowed statuses, enter courier fields, mark COD collected independently; confirm cancellation/restock action and its result. |
| Survey slots | Add date/time and capacity, inspect remaining availability, close future slots; warn when editing or closing a slot affects existing confirmed bookings. |
| Survey bookings | View contact/site needs, status and related order when present; add private notes; mark confirmed/completed/cancelled; communicate material changes. |

Sensitive customer data appears only to authorized staff. Use clear labels for internal-only notes and confirmations for consequential status, stock, or slot changes. Show who changed price, stock, order status, or booking status and when, consistent with the product spec. A failed save never appears successful.

**No launch banner editor:** the dashboard does not include banner upload, scheduling, or a general page editor under the chosen static-banner scope (§5).

## 12. Responsive, accessibility, and content rules

- Design mobile-first for narrow phones, then tablet and desktop widths. Validate actual small-phone, tablet, and wide-desktop layouts; avoid fixed width product tables and horizontal page scrolling. Product specs may use stacked name/value rows on mobile.
- Buttons and links have visible text or accessible names, useful focus order, visible focus styling, adequate touch targets and color contrast. Menus, dialogs, filters, image galleries, and carousel controls work with keyboard and assistive technology. Do not move focus unexpectedly when a filter changes.
- Form errors identify the field and correction; announce significant cart, stock, slot, and order-status changes in text. Never use color alone for availability, errors, or status. Provide skip navigation and meaningful page headings. Respect reduced-motion preferences; banners never move on their own.
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

## 14. Approved decisions and pre-launch inputs

**Decisions captured from project planning:** blue/black interlocking OC logo, light shopping surfaces, brand-first navigation featuring Hikvision and Dahua, homepage hero with manually controlled static banners, categories as the first main shopping section, shopping as the primary homepage action, single-page COD checkout, optional integrated survey section, and review/retry when a chosen survey slot is taken.

**Business inputs required before real orders or bookings:** approved tax rules and rates; flat shipping amount and courier coverage/estimates; exact Lahore service boundary and staff slot lengths; verified WhatsApp/phone/email and business identity; approved returns/warranty/cancellation/privacy/terms text; accurate product photos/specifications/stock/prices; production email and support handling. Until supplied, designs and staging content should use explicit placeholders rather than invented values.

**Implementation handoff:** establish brand color tokens from the approved logo master; create responsive page designs for the routes above; confirm the architecture for search discoverability and guest-link privacy; implement and review the flows in small increments. If a decision changes the product behavior (especially banner administration, kits, payment methods, or installation scheduling), update `product-spec.md` and this document together.
