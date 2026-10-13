import { AuthPage } from "~/components/auth/auth-page";

export function meta() {
  return [{ title: "Create account | OctaCam" }, { name: "robots", content: "noindex, nofollow" }];
}

export function headers() {
  return { "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer" };
}

export default function Register() { return <AuthPage key="register" mode="register" />; }
