# OctaCam Product Specification

**Status:** MVP product definition  
**Market:** Pakistan  
**Storefront language:** English  
**Currency:** Pakistani rupees (PKR)

## 1. Product overview

OctaCam is an online store for CCTV equipment serving households, small businesses, and professional installers in Pakistan. It should help a first-time buyer understand what a product does while giving an installer the model numbers and technical specifications needed to make a confident purchase.

The first release must support real equipment orders with **cash on delivery (COD) as the only checkout payment method**. Customers may also reserve a free site survey in Lahore. Staff use a small custom dashboard to maintain products and stock, process orders, and manage survey availability. The site should look and behave like a trustworthy commercial store on desktop and mobile.

This document defines product behavior and release boundaries. Detailed layouts belong in `ux-spec.md`; implementation choices and API design belong in `architecture.md` when those documents are created.

## 2. Goals and success criteria

### Goals

- Let shoppers discover, compare, and buy individual CCTV products without calling staff to complete a standard order.
- Present understandable descriptions alongside accurate technical specifications, prices, stock availability, warranty information, and contact options.
- Let customers place and follow COD orders as guests or signed-in users.
- Let Lahore customers book a free site survey, either alongside a product order or on its own.
- Give staff the minimum tools needed to keep the catalog accurate and fulfill orders and survey bookings.

### MVP success criteria

- A customer can complete a valid COD order for an in-stock product and receive an order confirmation.
- The confirmed order total shows product prices, applicable tax, and the flat shipping charge before the customer places the order.
- Staff can process an order from placement through delivery and publish manual courier details for customer tracking.
- A customer can reserve an available Lahore site-survey slot without double booking it.
- Staff can update products, prices, stock, orders, and survey slots without changing application code.
- Public pages work on common mobile and desktop screen sizes and are accessible through keyboard navigation.

## 3. Customers and roles

| Role | Main needs |
| --- | --- |
| Household or small-business buyer | Understand options, see a clear total, order equipment, ask for help, and request a site survey. |
| Professional installer | Find exact models quickly, inspect technical specifications, check availability, and place repeat equipment orders. |
| Guest customer | Shop and track an order or booking without creating an account. |
| Registered customer | Shop using an email-and-password account and view orders placed while signed in. |
| Staff member | Maintain products and stock, process orders, publish shipment details, and manage survey slots and bookings. |

The MVP has one staff permission level. Customer accounts are optional; account creation must never block guest checkout or standalone survey booking.

## 4. MVP customer journeys

### Equipment purchase

1. The customer browses categories or brands, searches by name or model, or uses filters.
2. A product page shows images, description, specifications, PKR price, stock status, warranty information when applicable, and ways to contact OctaCam.
3. The customer adds available items to a cart and reviews quantities and costs.
4. At checkout, the customer enters contact and Pakistan delivery details, sees the final itemized total, and places a COD order as a guest or signed-in user.
5. The site confirms the order and emails its details. Staff process the order and enter courier information. The customer follows progress using an account or secure guest link.

### Site survey

1. A customer with a Lahore site address may choose an available free site-survey slot during equipment checkout or through a standalone booking page.
2. The customer supplies contact information, the site address, and a short description of the site and equipment needs. Equipment bought elsewhere is allowed, subject to staff review.
3. The chosen slot is confirmed immediately and sent by email.
4. Staff conduct the survey, then provide an installation quote and arrange any installation work directly with the customer. The customer may decline the quote.

The booked appointment is **a site survey, not a guaranteed installation appointment**. Installation pricing, scheduling, acceptance, and payment occur outside the website in the MVP.

## 5. Storefront and catalog requirements

### 5.1 Catalog structure and product data

- Launch categories are cameras, DVR/NVR recorders, surveillance storage, and essential CCTV accessories.
- Each separately sellable model or capacity has its own product listing, price, and stock count. The MVP does not offer selectable product variants on one page or bundled kits.
- Staff can assign each product a category, brand, model/SKU, name, images, short and full descriptions, relevant technical specifications, regular price, optional sale price, stock quantity, and publication status.
- Product pages show the current selling price and, when a valid sale price exists, the regular price for comparison. Prices are displayed in PKR.
- Product pages show whether the item is available. Out-of-stock products remain visible but cannot be added to the cart.
- Descriptions and specifications must distinguish factual product capabilities from marketing copy. Unsupported compatibility, warranty, or performance claims must not be invented.
- Warranty terms may differ by product. Display the applicable information where supplied and link to the store's warranty policy.

### 5.2 Discovery

- Customers can browse by category and brand, search product names and model numbers, and filter by category, brand, price range, availability, and relevant technical attributes.
- Technical filters should match the product type; for example, camera resolution or indoor/outdoor use should not be forced onto storage products.
- Customers can sort results by relevance or a simple price order.
- Search and filter results must make unavailable products identifiable rather than silently hiding them.

### 5.3 Product content and trust

- Product pages include clear photographs, specifications, price, availability, delivery information, and visible support contact options.
- The storefront includes About, Contact, Shipping, Returns, Warranty, Privacy, and Terms pages. The business supplies and approves the actual policy wording before live sales.
- WhatsApp, email, and phone contact options are visible in suitable places across the storefront.
- The site uses English in the first release. Urdu translation is outside MVP scope.

## 6. Cart, checkout, and orders

### 6.1 Cart

- Customers can add in-stock products, change quantities, remove items, and see a running subtotal.
- The cart must not allow a quantity greater than currently available stock.
- If price or stock changes before order placement, checkout shows the updated information and requires the customer to review the new total.
- A cart does not itself reserve stock; stock is committed when an order is successfully placed.

### 6.2 COD checkout

- COD is the **only** equipment checkout payment method in the MVP. Do not show bank transfer, card, wallet, Raast, or a payment-gateway option.
- Checkout accepts a customer name, email address, phone number, and Pakistan delivery address. It supports both guest and signed-in customers.
- The checkout summary itemizes product prices, discounts already reflected by sale prices, shipping, applicable tax, and the final amount payable on delivery. The final amount must be visible before order submission.
- Equipment shipping uses one business-set flat fee nationwide. The fee and any published delivery limitations or estimates must be clear before checkout.
- Applicable tax is added at checkout using business-approved rules and rates. The site must show the tax amount separately and preserve the calculated amounts on the placed order. The exact tax treatment and rates are a pre-launch business decision, not an assumption in this specification.
- The server validates price, tax, shipping, and available stock when placing the order. A failed or duplicate submission must not create multiple orders or oversell stock.
- Placing an order reduces available stock. Cancelling an order returns stock when appropriate; staff manage that action through the dashboard.
- The order records a snapshot of purchased item names, model/SKU, quantity, unit price, tax, shipping, total, delivery address, and chosen payment method so later catalog changes do not alter the order record.

### 6.3 Order progress and payment

- Staff manage a simple order progression: **placed → confirmed → packed → shipped → delivered**, with **cancelled** available when applicable.
- COD payment starts as **uncollected** and is marked **collected** by staff after confirmation from fulfillment or the courier. Order and payment states remain distinct.
- Staff can enter a courier name, tracking number, and tracking link where available. Courier updates are manual; the MVP has no courier API integration.
- Customers can view order status and entered tracking details from their signed-in order history or a secure, unguessable link sent to the checkout email for guest orders. Guest links must expose only the relevant order and limited personal information.
- Customers request cancellations through support under the published policy. Staff decide eligibility and update the order; there is no self-service cancellation button.
- Returns and warranty cases are handled through the published support channels. The MVP does not include an online return-authorization workflow.

## 7. Customer accounts and communications

- Customers may register and sign in with email and password, reset a forgotten password, and view orders placed while signed in.
- Customers may check out as guests. Earlier guest orders are **not** automatically added to an account created later; those orders remain accessible through their secure links and support.
- Signed-in customers may use saved account information where appropriate, but checkout must allow them to review and edit delivery details for each order.
- Email is used for essential messages: account recovery, order placement and key order-status changes, survey confirmation, and material survey changes or cancellation.
- Order and booking confirmation pages must remain useful if an email is delayed. Staff must be able to identify the underlying order or booking and help the customer.
- Automated SMS, marketing email campaigns, and social sign-in are outside MVP scope.

## 8. Lahore site-survey booking

- Site-survey booking is available only for addresses within the launch Lahore service area. Equipment delivery remains nationwide.
- Customers can book a survey as part of an equipment order or as a standalone request. A standalone booking may concern equipment purchased elsewhere, subject to staff review.
- Staff publish available survey slots through the dashboard. A slot has a date, time, and capacity; confirmed bookings consume capacity so the same capacity cannot be booked twice.
- The survey is free at booking. No installation price or payment is collected through the site.
- A booking collects customer name, email, phone, Lahore site address, selected slot, and a brief description of needs or existing equipment. The form explains that staff will review outside equipment and provide any installation quote after the survey.
- The customer receives an immediate booking confirmation on screen and by email. Staff can view the booking, contact the customer, add internal notes, and mark it confirmed, completed, or cancelled.
- Customers request booking changes or cancellation through support. Staff manage available slots and communicate changes by email or direct contact.
- Equipment orders and survey bookings have separate lifecycles. Cancelling one does not silently cancel the other; staff confirm with the customer when both are related.
- Following the survey, staff quote and schedule installation offline. No online quote acceptance, installer dispatch, installation-calendar management, or installation-payment workflow is required for MVP.

## 9. Staff dashboard

The MVP uses a custom staff dashboard with one authorized staff role. It should cover operational work only:

- Create, edit, publish, and unpublish products; manage categories, brands, images, specifications, regular and sale prices, and stock quantities.
- View orders, customer and delivery details, payment state, and itemized totals; update order state and courier details; record cancellations and restocking.
- Create and close survey slots; view bookings and site details; record internal notes and booking status.
- See enough recent operational activity to notice new orders and upcoming surveys.

Staff access must require authentication. Customer-facing prices and availability come from the same authoritative product and stock records used by checkout. Changes to price, stock, and order or booking status should record who made the change and when. A broad analytics suite, complex role hierarchy, and general-purpose content-management system are outside MVP scope.

## 10. Quality and operational requirements

- **Security and privacy:** Use HTTPS in production, protect staff and customer access, store passwords securely, validate all submitted data, and limit access to personal data. Do not store payment-card data; the MVP accepts COD only.
- **Order integrity:** Calculate totals on the server, prevent duplicate orders and survey bookings, and handle stock changes consistently under concurrent checkout attempts.
- **Usability:** Make the storefront responsive, readable, keyboard accessible, and clear about errors, stock changes, fees, and the COD amount due on delivery.
- **Search visibility:** Public product and category pages should have stable URLs, useful titles and descriptions, and content that search engines can discover. The technical rendering approach belongs in the architecture decision.
- **Reliability:** A failed email must not erase a successfully placed order or booking. Staff need a way to see and follow up on it.
- **Maintainability:** Keep product rules separate from presentation details and use the agreed React, Django REST Framework, PostgreSQL, and REST stack unless an architecture decision explicitly changes it.

## 11. Explicitly outside the MVP

- Online payment gateway, bank transfer, wallets, cards, Raast, and online installation payments.
- Product bundles or fixed CCTV kits, custom system configurators, and automatic product recommendations.
- Coupons, loyalty points, installer-specific pricing, subscriptions, and timed promotion rules.
- Product reviews, wishlists, multilingual content, and editorial buying guides.
- Automatic courier tracking, online returns processing, and customer self-service cancellation.
- Nationwide installation service, guaranteed installation slots, online installation quotes, and installation scheduling or dispatch.
- Automatic linking of guest orders to later customer accounts and advanced staff permissions or analytics.

These are future possibilities, not commitments for the first release.

## 12. Business inputs required before live sales

The product behavior above is defined, but the following values and policies must be supplied and approved by the business before accepting real orders:

- Applicable tax rules and rates, including what amounts are taxable, confirmed by a qualified accountant or tax adviser.
- The nationwide shipping fee, courier arrangements, delivery coverage and estimates, and any location exceptions.
- Published returns, warranty, cancellation, privacy, and terms wording, plus verified WhatsApp, email, and phone details.
- Initial product records, images, accurate specifications, prices, warranty terms, and physical stock counts.
- Lahore survey service boundaries, staff availability and slot lengths, and the offline quote and installation process.
- Production email delivery, hosting, backups, staff access procedures, and a process for handling failed deliveries and uncollected COD orders.

No payment-gateway selection or merchant approval is required for the COD-only MVP.

## 13. Acceptance scenarios

1. A guest buys an in-stock camera with COD, sees the itemized PKR total including shipping and tax, receives a confirmation, and can follow the order through the secure link.
2. A signed-in installer buys several individual products and later sees that order in account history. An earlier guest order does not appear there automatically.
3. Two customers attempt to buy the last unit at nearly the same time; only an order backed by available stock succeeds, and the other customer sees a clear stock-change message.
4. An out-of-stock product stays visible in search and on its product page but cannot be purchased.
5. Staff change an order from placed through shipped, add courier details, and the customer sees the updated status. Staff can mark COD collected separately from delivery status.
6. A customer books an available Lahore site survey without buying equipment; the slot is confirmed once and an email is sent. A customer outside the service area cannot reserve a slot.
7. A Lahore customer adds a survey while buying equipment. The order and survey each have their own confirmation and can be managed separately afterward.
8. Staff cancel an eligible order under the published policy and restore its stock where appropriate. The customer receives a relevant status update.
9. Checkout presents COD only; no online payment or bank-transfer option appears anywhere in the MVP purchase flow.
