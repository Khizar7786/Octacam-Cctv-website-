import { Link } from "react-router";
import { OctacamLogo } from "~/components/brand/octacam-logo";
import { Container } from "~/components/layout/container";
import { StoreIcon } from "~/components/ui/store-icon";
import { contact, policyLinks } from "~/config/storefront";

const channels = [
  { label: "WhatsApp", icon: "whatsapp", value: contact.whatsapp },
  { label: "Phone", icon: "phone", value: contact.phone },
  { label: "Email", icon: "email", value: contact.email },
] as const;

const footerLink = "inline-flex min-h-11 items-center rounded-sm text-footer-muted no-underline hover:text-footer-foreground hover:underline focus-visible:outline-navigation-focus";

export function SiteFooter() {
  return (
    <footer className="mt-6">
      <div className="bg-footer text-footer-foreground">
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
              {channels.map(({ label, icon, value }) => (
                <li className="flex items-start gap-3" key={label}>
                  <StoreIcon badge name={icon} />
                  <div className="min-w-0">
                    <p className="font-semibold">{label}</p>
                    {value
                      ? <a className={footerLink} href={value.href}>{value.display}<span className="sr-only"> (external contact)</span></a>
                      : <p className="mt-1 text-footer-muted">Details pending verification</p>}
                  </div>
                </li>
              ))}
            </ul>
            <Link className={`${footerLink} mt-4 gap-2`} to="/contact"><StoreIcon badge name="contact" />Contact page <span className="ml-2 text-xs">(coming soon)</span></Link>
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
