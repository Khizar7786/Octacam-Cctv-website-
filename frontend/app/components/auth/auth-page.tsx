import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, buttonStyles } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import { useAuth } from "~/features/auth/auth-context";
import { authFailure, authFields, authPageLink, authPayload, emptyAuthValues, safeReturnTo, validateAuthValues, type AuthFailure, type AuthField, type AuthMode } from "~/features/auth/forms";
import type { RegistrationDetails } from "~/features/auth/runtime";

const labels: Record<AuthField, string> = { full_name: "Full name", email: "Email address", phone: "Phone number", password: "Password" };

export function AuthPage({ mode }: { mode: AuthMode }) {
  const { state, runtime } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const returnTo = safeReturnTo(new URLSearchParams(location.search));
  const [values, setValues] = useState(emptyAuthValues);
  const [visiblePassword, setVisiblePassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [failure, setFailure] = useState<AuthFailure | null>(null);
  const [logoutFailure, setLogoutFailure] = useState(false);
  const summary = useRef<HTMLDivElement>(null);
  const submission = useRef(false);
  const form = useRef<HTMLFormElement>(null);
  const mounted = useRef(true);
  const fields = authFields(mode);
  const registering = mode === "register";

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (state.status === "authenticated" && returnTo && !logoutFailure) void navigate(returnTo, { replace: true });
  }, [state.status, returnTo, logoutFailure, navigate]);

  useEffect(() => { if (failure) summary.current?.focus(); }, [failure]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submission.current || state.status === "loading") return;
    const errors = { ...validateAuthValues(values, mode) };
    const email = form.current?.elements.namedItem("email") as HTMLInputElement | null;
    if (!errors.email && email?.validity.typeMismatch) errors.email = ["Enter a valid email address."];
    if (Object.keys(errors).length) {
      setFailure({ message: "Please check the highlighted fields.", fields: errors });
      return;
    }
    submission.current = true;
    setPending(true);
    setFailure(null);
    setLogoutFailure(false);
    try {
      const payload = authPayload(values, mode);
      if (registering) await runtime.register(payload as RegistrationDetails);
      else await runtime.login(payload);
      if (mounted.current) { setValues({ ...emptyAuthValues }); setVisiblePassword(false); }
    } catch (error) {
      if (mounted.current) { setFailure(authFailure(error, mode)); setVisiblePassword(false); }
    } finally {
      submission.current = false;
      if (mounted.current) setPending(false);
    }
  }

  async function signOut() {
    if (submission.current) return;
    submission.current = true;
    setPending(true);
    setSigningOut(true);
    setLogoutFailure(false);
    try { await runtime.logout(); }
    catch { if (mounted.current) setLogoutFailure(true); }
    finally { submission.current = false; if (mounted.current) { setPending(false); setSigningOut(false); } }
  }

  return (
    <section className="mx-auto grid max-w-5xl gap-8 py-6 sm:py-10 lg:grid-cols-[0.85fr_1fr] lg:gap-16" aria-labelledby="auth-title">
      <div className="space-y-5">
        <p className="text-sm"><Link to="/">Home</Link> / {registering ? "Create account" : "Sign in"}</p>
        <h1 className="text-[length:var(--font-size-heading)] font-bold leading-tight" id="auth-title">{registering ? "Create your OctaCam account" : "Sign in to OctaCam"}</h1>
        <p className="max-w-md text-muted-foreground">{registering ? "Use an account for orders placed while signed in. Earlier guest orders stay separate." : "Use your email and password to sign in. Customer and staff accounts use the same form."}</p>
        <aside className="space-y-3 border-l-4 border-primary bg-accent p-5" aria-label="Guest shopping">
          <h2 className="text-lg font-semibold">Shop without an account</h2>
          <p className="text-sm">An account is optional for cash-on-delivery equipment purchases.</p>
          <Link className={buttonStyles({ variant: "outline" })} to="/cart">Continue without an account</Link>
          <p className="text-xs text-muted-foreground">Continue to your cart. Guest checkout is being built.</p>
        </aside>
      </div>
      <div className="min-w-0 rounded-lg bg-card p-5 sm:p-8">
        {state.status === "loading" ? <p className="mb-5 text-sm text-muted-foreground" role="status">Checking your session…</p> : null}
        {state.status === "error" ? <Alert className="mb-5" role="alert" variant="warning"><AlertTitle>Your session could not be checked</AlertTitle><AlertDescription>Try again or sign in below.</AlertDescription><Button onClick={() => void runtime.restore()} variant="outline">Check session again</Button></Alert> : null}
        {logoutFailure ? <Alert className="mb-5" role="alert" variant="error"><AlertTitle>Sign-out could not be confirmed</AlertTitle><AlertDescription>Your session may still be active after a reload. Try signing out again.</AlertDescription><Button disabled={pending} onClick={() => void signOut()} variant="outline">Retry sign out</Button></Alert> : null}
        {state.status === "authenticated" ? (
          <div className="space-y-5">
            <Alert role="status" variant="success"><AlertTitle>{state.user.is_staff ? "Signed in to your staff account" : "You are signed in"}</AlertTitle><AlertDescription>{state.user.full_name} · {state.user.email}</AlertDescription></Alert>
            <p className="text-sm text-muted-foreground">{state.user.is_staff ? "The staff workspace is being built." : "Order history and account details are being built."}</p>
            <div className="flex flex-wrap gap-3">
              <Link className={buttonStyles()} to={returnTo ?? "/shop"}>Continue shopping</Link>
              <Button disabled={pending} onClick={() => void signOut()} variant="outline">{pending ? "Signing out…" : "Sign out"}</Button>
            </div>
          </div>
        ) : (
          <form aria-busy={pending} method="post" noValidate onSubmit={(event) => void submit(event)} ref={form}>
            <h2 className="mb-5 text-xl font-semibold">{registering ? "Account details" : "Your sign-in details"}</h2>
            {failure ? (
              <Alert className="mb-5" ref={summary} role="alert" tabIndex={-1} variant="error">
                <AlertTitle>{registering ? "Account creation needs attention" : "Sign-in needs attention"}</AlertTitle>
                <AlertDescription>{failure.message}</AlertDescription>
                <ul className="space-y-1">
                  {Object.entries(failure.fields).flatMap(([field, messages]) => messages.map((message, index) => <li key={`${field}-${index}`}>{fields.includes(field as AuthField) ? <a href={`#auth-${field}`} onClick={(event) => { event.preventDefault(); document.getElementById(`auth-${field}`)?.focus(); }}>{labels[field as AuthField]}: {message}</a> : message}</li>))}
                </ul>
              </Alert>
            ) : null}
            <fieldset className="space-y-5" disabled={pending || state.status === "loading"}>
              <legend className="sr-only">{registering ? "Registration" : "Sign-in"} fields</legend>
              {fields.map((field) => {
                const errors = failure?.fields[field];
                const hint = field === "password" && registering ? "Use at least 8 characters. Avoid common, entirely numeric passwords and similarity to your name or email." : field === "phone" ? "Optional, up to 30 characters." : null;
                const descriptions = [hint ? `auth-${field}-hint` : null, errors?.length ? `auth-${field}-error` : null].filter(Boolean).join(" ") || undefined;
                return (
                  <div className="space-y-2" key={field}>
                    <Label htmlFor={`auth-${field}`}>{labels[field]}{field === "phone" ? " (optional)" : " (required)"}</Label>
                    <div className="flex min-w-0 items-center gap-2">
                      <Input aria-describedby={descriptions} aria-invalid={!!errors?.length} autoComplete={field === "password" ? registering ? "new-password" : "current-password" : field === "email" ? "username" : field === "full_name" ? "name" : "tel"} className="min-w-0" id={`auth-${field}`} maxLength={field === "full_name" ? 255 : field === "phone" ? 30 : undefined} name={field} onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))} required={field !== "phone"} type={field === "password" ? visiblePassword ? "text" : "password" : field === "email" ? "email" : field === "phone" ? "tel" : "text"} value={values[field]} />
                      {field === "password" ? <Button aria-controls="auth-password" aria-pressed={visiblePassword} className="shrink-0 whitespace-nowrap" onClick={() => setVisiblePassword((current) => !current)} variant="outline">{visiblePassword ? "Hide" : "Show"}<span className="sr-only"> password</span></Button> : null}
                    </div>
                    {hint ? <p className="text-xs text-muted-foreground" id={`auth-${field}-hint`}>{hint}</p> : null}
                    {errors?.length ? <ul className="text-sm text-error" id={`auth-${field}-error`}>{errors.map((error, index) => <li key={index}>{error}</li>)}</ul> : null}
                  </div>
                );
              })}
              <Button className="w-full" type="submit">{signingOut ? "Signing out…" : pending ? registering ? "Creating account…" : "Signing in…" : registering ? "Create account" : "Sign in"}</Button>
            </fieldset>
            {pending ? <p className="mt-3 text-sm text-muted-foreground" role="status">{signingOut ? "Signing out…" : registering ? "Creating your account…" : "Signing in…"}</p> : null}
            <p className="mt-5 text-sm">{registering ? "Already have an account?" : "New to OctaCam?"} <Link to={authPageLink(registering ? "login" : "register", returnTo)}>{registering ? "Sign in" : "Create an account"}</Link></p>
            {!registering ? <p className="mt-3 text-xs text-muted-foreground">Password reset is coming soon.</p> : null}
            <noscript><p className="mt-4">Enable JavaScript to sign in or create an account. You can still browse products.</p></noscript>
          </form>
        )}
      </div>
    </section>
  );
}
