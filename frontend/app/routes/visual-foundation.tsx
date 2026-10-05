import { Link } from "react-router";
import { OctacamLogo } from "~/components/brand/octacam-logo";
import { Stack } from "~/components/layout/stack";
import { Surface } from "~/components/layout/surface";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";

export function meta() {
  return [
    { title: "Visual foundation | OctaCam" },
    {
      name: "description",
      content: "Development preview of OctaCam's shared visual tokens and interface primitives.",
    },
  ];
}

const colors = [
  { className: "bg-primary", label: "Brand blue", value: "#005FFB" },
  { className: "bg-foreground", label: "Ink", value: "#111820" },
  { className: "bg-card", label: "Surface", value: "#FFFFFF" },
  { className: "bg-muted", label: "Muted", value: "#EDF1F6" },
  { className: "bg-border", label: "Border", value: "#CBD4DF" },
] as const;

function SectionHeading({ children, id, number }: { children: string; id: string; number: string }) {
  return (
    <div className="flex items-baseline gap-3 border-b border-border pb-3">
      <span className="font-mono text-xs font-semibold text-primary" aria-hidden="true">
        {number}
      </span>
      <h2 className="text-xl font-bold tracking-[-0.02em] sm:text-2xl" id={id}>{children}</h2>
    </div>
  );
}

export default function VisualFoundation() {
  return (
    <Stack gap="section">
      <header className="grid gap-8 border-l-4 border-primary pl-5 sm:grid-cols-[minmax(0,1fr)_15rem] sm:items-end sm:pl-8">
        <div className="max-w-3xl">
          <p className="mb-3 text-sm font-semibold text-primary">Development preview</p>
          <h1 className="text-[length:var(--font-size-display)] font-bold leading-[var(--line-height-tight)] tracking-[-0.045em]">
            Built for clear decisions.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
            A compact visual system for comparing CCTV equipment, reading model details, and completing forms with confidence.
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-x-5 gap-y-2 border-t border-border pt-4 text-sm sm:grid-cols-1">
          <div>
            <dt className="text-muted-foreground">Canvas</dt>
            <dd className="font-semibold">Light / responsive</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Motion</dt>
            <dd className="font-semibold">CSS state feedback</dd>
          </div>
        </dl>
      </header>

      <section aria-labelledby="brand-heading">
        <Stack>
          <SectionHeading id="brand-heading" number="01">Brand source</SectionHeading>
          <div className="grid gap-6 lg:grid-cols-[minmax(17rem,0.8fr)_minmax(0,1.2fr)]">
            <Surface className="flex min-h-80 items-center justify-center overflow-hidden">
              <OctacamLogo className="max-w-64" />
            </Surface>
            <div className="grid content-start gap-6">
              <div className="max-w-2xl space-y-3">
                <h3 className="text-lg font-bold">Approved transparent master</h3>
                <p className="text-muted-foreground">
                  The source PNG stays on its original 1:1 canvas with its alpha channel, proportions, clear space, and letterforms intact.
                </p>
                <p className="font-mono text-sm text-foreground">1254 × 1254 px · RGBA · transparent background</p>
              </div>
              <ul className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-5" aria-label="Core color tokens">
                {colors.map((color) => (
                  <li className="bg-card p-3" key={color.label}>
                    <span className={`mb-3 block aspect-[4/3] rounded-sm border border-border ${color.className}`} />
                    <span className="block text-sm font-semibold">{color.label}</span>
                    <span className="font-mono text-xs text-muted-foreground">{color.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Stack>
      </section>

      <section aria-labelledby="type-heading">
        <Stack>
          <SectionHeading id="type-heading" number="02">Type and rhythm</SectionHeading>
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(16rem,0.65fr)]">
            <div className="space-y-5">
              <p className="text-[length:var(--font-size-heading)] font-bold leading-tight tracking-[-0.035em]">
                Details should scan quickly.
              </p>
              <p className="max-w-2xl text-muted-foreground">
                The system sans stack keeps product explanations familiar and legible. Weight and spacing establish hierarchy without relying on decorative type.
              </p>
              <p className="font-mono text-sm font-semibold tracking-[-0.01em]">DS-2CD1023G2-LIU · 2.8 MM · IP67</p>
            </div>
            <Surface tone="subtle" className="grid grid-cols-[auto_1fr] gap-x-5 gap-y-3 text-sm">
              <span className="font-mono text-primary">04</span><span>Base spacing unit</span>
              <span className="font-mono text-primary">44</span><span>Minimum control height</span>
              <span className="font-mono text-primary">03</span><span>Focus ring width</span>
              <span className="font-mono text-primary">43rem</span><span>Reading measure</span>
            </Surface>
          </div>
        </Stack>
      </section>

      <section aria-labelledby="controls-heading">
        <Stack>
          <SectionHeading id="controls-heading" number="03">Buttons and fields</SectionHeading>
          <div className="grid gap-6 lg:grid-cols-2">
            <Surface>
              <Stack>
                <div>
                  <h3 className="font-bold">Action hierarchy</h3>
                  <p className="mt-1 text-sm text-muted-foreground">Hover, tab, and press to review each state.</p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button>Primary action</Button>
                  <Button variant="secondary">Secondary</Button>
                  <Button variant="outline">Outline</Button>
                  <Button variant="ghost">Quiet action</Button>
                  <Button disabled>Unavailable</Button>
                </div>
              </Stack>
            </Surface>

            <Surface>
              <Stack gap="compact">
                <div className="grid gap-2">
                  <Label htmlFor="preview-model">Product or model</Label>
                  <Input id="preview-model" defaultValue="DS-2CD1023G2-LIU" />
                  <p className="text-sm text-muted-foreground">Names and partial model numbers are accepted.</p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="preview-email">Email address</Label>
                  <Input
                    aria-describedby="preview-email-error"
                    aria-invalid="true"
                    id="preview-email"
                    placeholder="name@example.com"
                    type="email"
                  />
                  <p className="text-sm font-medium text-error" id="preview-email-error">Enter a valid email address.</p>
                </div>
              </Stack>
            </Surface>
          </div>
        </Stack>
      </section>

      <section aria-labelledby="alerts-heading">
        <Stack>
          <SectionHeading id="alerts-heading" number="04">Messages</SectionHeading>
          <div className="grid gap-4 sm:grid-cols-2">
            <Alert variant="info">
              <AlertTitle>Check the details</AlertTitle>
              <AlertDescription>Technical information remains readable without depending on color alone.</AlertDescription>
            </Alert>
            <Alert variant="success">
              <AlertTitle>Saved successfully</AlertTitle>
              <AlertDescription>The server confirmed this example state.</AlertDescription>
            </Alert>
            <Alert variant="warning">
              <AlertTitle>Review required</AlertTitle>
              <AlertDescription>A changed price or slot would need another confirmation.</AlertDescription>
            </Alert>
            <Alert variant="error">
              <AlertTitle>Could not save</AlertTitle>
              <AlertDescription>The entered values stay available for correction and retry.</AlertDescription>
            </Alert>
          </div>
        </Stack>
      </section>

      <footer className="border-t border-border pt-6 text-sm text-muted-foreground">
        <p>This route is a review surface, not a storefront page. <Link to="/">Return home</Link>.</p>
      </footer>
    </Stack>
  );
}
