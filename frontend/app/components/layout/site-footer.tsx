import { Link } from "react-router";
import { Container } from "~/components/layout/container";
import { contact, policyLinks } from "~/config/storefront";

const channels = [
  { label: "WhatsApp", value: contact.whatsapp },
  { label: "Phone", value: contact.phone },
  { label: "Email", value: contact.email },
] as const;

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-border bg-card">
      <Container className="grid gap-10 py-12 md:grid-cols-2 lg:grid-cols-[1.15fr_1fr_1fr_1fr]">
        <div>
          <p className="text-lg font-bold">Octa<span className="text-primary">Cam</span></p>
          <p className="mt-3 max-w-xs text-sm text-muted-foreground">CCTV equipment and free Lahore site surveys. The storefront is in development.</p>
        </div>
        <div>
          <h2 className="text-sm font-bold">Contact</h2>
          <ul className="mt-3 grid gap-3 text-sm">
            {channels.map(({ label, value }) => (
              <li key={label}>
                <span className="font-semibold">{label}:</span>{" "}
                {value
                  ? <a href={value.href}>{value.display}<span className="sr-only"> (external contact)</span></a>
                  : <span className="text-muted-foreground">Details pending verification</span>}
              </li>
            ))}
          </ul>
          <p className="mt-4 text-sm"><Link className="inline-flex min-h-11 items-center" to="/contact">Contact page <span className="ml-1 text-xs">(coming soon)</span></Link></p>
        </div>
        <div>
          <h2 className="text-sm font-bold">Information</h2>
          <ul className="mt-3 grid gap-2 text-sm">
            <li><Link className="inline-flex min-h-11 items-center" to="/about">About <span className="ml-1 text-xs">(coming soon)</span></Link></li>
            {policyLinks.map(({ label, to }) => (
              <li key={to}><Link className="inline-flex min-h-11 items-center" to={to}>{label} <span className="ml-1 text-xs">(coming soon)</span></Link></li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="text-sm font-bold">Site surveys</h2>
          <p className="mt-3 text-sm text-muted-foreground">Free site surveys are for Lahore only. Installation is quoted and scheduled separately after the survey.</p>
          <p className="mt-4 text-sm"><Link className="inline-flex min-h-11 items-center" to="/surveys">Survey booking <span className="ml-1 text-xs">(coming soon)</span></Link></p>
        </div>
      </Container>
      <div className="border-t border-border">
        <Container className="py-4 text-xs text-muted-foreground">OctaCam · Storefront in development</Container>
      </div>
    </footer>
  );
}
