type VerifiedContact = { display: string; href: string } | null;

/** Only publish contact values after the business owner verifies them. */
export const contact = {
  whatsapp: null as VerifiedContact,
  phone: null as VerifiedContact,
  email: null as VerifiedContact,
};

export const brandLinks = [
  { label: "Hikvision", to: "/brands/hikvision" },
  { label: "Dahua", to: "/brands/dahua" },
  { label: "All brands", to: "/brands" },
] as const;

export const categoryLinks = [
  { label: "Cameras", to: "/categories/cameras" },
  { label: "Recorders", to: "/categories/recorders" },
  { label: "Storage", to: "/categories/storage" },
  { label: "Accessories", to: "/categories/accessories" },
] as const;

export const policyLinks = [
  { label: "Shipping", to: "/shipping" },
  { label: "Returns", to: "/returns" },
  { label: "Warranty", to: "/warranty" },
  { label: "Privacy", to: "/privacy" },
  { label: "Terms", to: "/terms" },
] as const;

export const plannedPages = [
  { label: "Hikvision", to: "/brands/hikvision", detail: "The Hikvision brand page is being built." },
  { label: "Dahua", to: "/brands/dahua", detail: "The Dahua brand page is being built." },
  { label: "All brands", to: "/brands", detail: "Brand browsing is being built." },
  { label: "Cameras", to: "/categories/cameras", detail: "The camera category page is being built." },
  { label: "Recorders", to: "/categories/recorders", detail: "The DVR/NVR recorder category page is being built." },
  { label: "Storage", to: "/categories/storage", detail: "The surveillance storage category page is being built." },
  { label: "Accessories", to: "/categories/accessories", detail: "The accessories category page is being built." },
  { label: "Search", to: "/search", detail: "Product and model search is being built." },
  { label: "Cart", to: "/cart", detail: "The cart and its item count are being built." },
  { label: "Account", to: "/login", detail: "Customer sign-in and account screens are being built." },
  { label: "Free Lahore site survey", to: "/surveys", detail: "The free site survey booking screen is being built. Installation is quoted and scheduled after the survey." },
  { label: "Contact", to: "/contact", detail: "Verified support details are still needed before this page can be published." },
  { label: "About", to: "/about", detail: "Verified business information is still needed before this page can be published." },
  { label: "Shipping", to: "/shipping", detail: "The approved shipping policy is still needed before this page can be published." },
  { label: "Returns", to: "/returns", detail: "The approved returns policy is still needed before this page can be published." },
  { label: "Warranty", to: "/warranty", detail: "The approved warranty policy is still needed before this page can be published." },
  { label: "Privacy", to: "/privacy", detail: "The approved privacy policy is still needed before this page can be published." },
  { label: "Terms", to: "/terms", detail: "The approved terms are still needed before this page can be published." },
] as const;
