export const API_ORIGIN_ENV = "OCTACAM_API_ORIGIN";
export const DEFAULT_LOCAL_API_ORIGIN = "http://127.0.0.1:8000";

export function getServerApiOrigin(
  environment: Readonly<Record<string, string | undefined>> = process.env,
): string {
  const configuredOrigin = environment[API_ORIGIN_ENV]?.trim();
  if (!configuredOrigin && environment.NODE_ENV === "production") {
    throw new Error(`${API_ORIGIN_ENV} is required in production.`);
  }
  const parsed = new URL(configuredOrigin || DEFAULT_LOCAL_API_ORIGIN);

  if (
    !["http:", "https:"].includes(parsed.protocol)
    || parsed.username
    || parsed.password
    || parsed.pathname !== "/"
    || parsed.search
    || parsed.hash
  ) {
    throw new Error(`${API_ORIGIN_ENV} must be an HTTP(S) origin without a path, credentials, query, or fragment.`);
  }

  return parsed.origin;
}
