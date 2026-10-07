import { Link } from "react-router";
import { OctacamLogo } from "~/components/brand/octacam-logo";
import { Container } from "~/components/layout/container";
import { contact, policyLinks } from "~/config/storefront";

const channels = [
  { label: "WhatsApp", value: contact.whatsapp },
  { label: "Phone", value: contact.phone },
  { label: "Email", value: contact.email },
] as const;

const footerLink = "inline-flex min-h-11 items-center rounded-sm text-footer-muted no-underline hover:text-footer-foreground hover:underline focus-visible:outline-navigation-focus";

function ContactIcon({ channel }: { channel: string }) {
  return (
    <svg aria-hidden="true" className="size-5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" viewBox="0 0 24 24">
      {channel === "Email" ? (
        <><rect height="14" rx="2" width="20" x="2" y="5" /><path d="m3 6 9 7 9-7" /></>
      ) : channel === "WhatsApp" ? (
        <><path d="M21 11.5a9 9 0 0 1-13.5 7.8L3 21l1.7-4.5A9 9 0 1 1 21 11.5Z" /><path d="M8 7.5c0 4 2.5 6.5 6.5 6.5l1-2-2-1-1 1a5 5 0 0 1-2-2l1-1-1-2Z" /></>
      ) : (
        <path d="m8 3 3 4-2 3a14 14 0 0 0 5 5l3-2 4 3-1 4c-9 1-18-8-17-17Z" />
      )}
    </svg>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-6">
      <div className="rounded-[var(--footer-radius)] bg-footer text-footer-foreground">
        <div className="grid gap-8 px-[var(--footer-gutter)] py-8 md:grid-cols-2 lg:grid-cols-[1.1fr_1fr_1fr] lg:gap-12 lg:py-10">
          <div>
            <Link className="block w-28 rounded-lg bg-card p-2 sm:w-32" to="/">
              <OctacamLogo alt="OctaCam home" loading="lazy" />
            </Link>
            <p className="mt-4 max-w-sm text-sm text-footer-muted">CCTV cameras, DVR/NVR recorders, surveillance storage, and accessories.</p>
            <h2 className="mt-5 text-base font-bold">Free Lahore site surveys</h2>
            <p className="mt-2 max-w-sm text-sm text-footer-muted">Free site surveys are for Lahore only. Installation is quoted and scheduled separately after the survey.</p>
            <Link className={`${footerLink} mt-2`} to="/surveys">Survey booking <span className="ml-2 text-xs">(coming soon)</span></Link>
          </div>

          <div>
            <h2 className="text-lg font-bold">Reach out to us</h2>
            <ul className="mt-4 grid gap-4 text-sm">
              {channels.map(({ label, value }) => (
                <li className="flex items-start gap-3" key={label}>
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-navigation-hover text-footer-foreground"><ContactIcon channel={label} /></span>
                  <div className="min-w-0">
                    <p className="font-semibold">{label}</p>
                    {value
                      ? <a className={footerLink} href={value.href}>{value.display}<span className="sr-only"> (external contact)</span></a>
                      : <p className="mt-1 text-footer-muted">Details pending verification</p>}
                  </div>
                </li>
              ))}
            </ul>
            <Link className={`${footerLink} mt-4`} to="/contact">Contact page <span className="ml-2 text-xs">(coming soon)</span></Link>
          </div>

          <nav aria-label="Footer information" className="md:col-span-2 lg:col-span-1">
            <h2 className="text-lg font-bold">Policies and support</h2>
            <ul className="mt-3 grid gap-1 sm:grid-cols-2 lg:grid-cols-1">
              <li><Link className={footerLink} to="/about">About <span className="ml-2 text-xs">(coming soon)</span></Link></li>
              {policyLinks.map(({ label, to }) => (
                <li key={to}><Link className={footerLink} to={to}>{label} <span className="ml-2 text-xs">(coming soon)</span></Link></li>
              ))}
            </ul>
          </nav>
        </div>
      </div>
      <Container className="py-4 text-center text-xs text-muted-foreground">OctaCam · Storefront in development</Container>
    </footer>
  );
}
