export const API_PATH_PREFIX = "/api/v1/" as const;

export type ApiPath = `${typeof API_PATH_PREFIX}${string}`;
export type ApiFieldErrors = Readonly<Record<string, readonly string[]>>;

type FetchImplementation = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>;

export interface ApiRequestOptions extends Omit<RequestInit, "signal"> {
  signal?: AbortSignal;
}

export interface ApiClient {
  request<T>(path: ApiPath, options?: ApiRequestOptions): Promise<T>;
}

interface ApiErrorOptions {
  status: number | null;
  code: string;
  message: string;
  fields?: ApiFieldErrors;
  body?: unknown;
  cause?: unknown;
}

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string;
  readonly fields: ApiFieldErrors;
  readonly body: unknown;

  constructor({ status, code, message, fields = {}, body, cause }: ApiErrorOptions) {
    super(message, { cause });
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.body = body;
  }
}

export function apiPath(value: string): ApiPath {
  if (!value.startsWith(API_PATH_PREFIX) || value.includes("#") || value.includes("\\")) {
    throw new TypeError(`API paths must start with ${API_PATH_PREFIX} and stay on the current origin.`);
  }

  const parsed = new URL(value, "http://octacam.invalid");
  if (parsed.origin !== "http://octacam.invalid" || !parsed.pathname.startsWith(API_PATH_PREFIX)) {
    throw new TypeError(`API paths must start with ${API_PATH_PREFIX} and stay on the current origin.`);
  }

  return `${parsed.pathname}${parsed.search}` as ApiPath;
}

export function createApiClient({
  origin = "",
  fetch: fetchImplementation,
}: {
  origin?: string;
  fetch?: FetchImplementation;
} = {}): ApiClient {
  const normalizedOrigin = origin ? normalizeOrigin(origin) : "";

  return {
    async request<T>(path: ApiPath, options: ApiRequestOptions = {}) {
      const safePath = apiPath(path);
      const headers = new Headers(options.headers);
      if (!headers.has("Accept")) headers.set("Accept", "application/json");

      let response: Response;
      try {
        response = await (fetchImplementation ?? globalThis.fetch)(`${normalizedOrigin}${safePath}`, {
          ...options,
          headers,
        });
      } catch (error) {
        if (isAbortError(error) || options.signal?.aborted) throw error;
        throw networkError(error);
      }

      let body: unknown;
      try {
        body = await readResponseBody(response);
      } catch (error) {
        if (isAbortError(error) || options.signal?.aborted) throw error;
        throw networkError(error);
      }
      if (!response.ok) throw normalizeErrorResponse(response.status, body);
      return body as T;
    },
  };
}

export function unexpectedApiResponse(body: unknown, status = 200): ApiError {
  return new ApiError({
    status,
    code: "UNEXPECTED_API_RESPONSE",
    message: "The server returned an unexpected response. Please try again.",
    body,
  });
}

function normalizeOrigin(value: string): string {
  const parsed = new URL(value);
  if (
    !["http:", "https:"].includes(parsed.protocol)
    || parsed.username
    || parsed.password
    || parsed.pathname !== "/"
    || parsed.search
    || parsed.hash
  ) {
    throw new TypeError("The API origin must be an HTTP(S) origin without a path, credentials, query, or fragment.");
  }
  return parsed.origin;
}

async function readResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const text = await response.text();
  if (!text.trim()) return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function normalizeErrorResponse(status: number, body: unknown): ApiError {
  if (isRecord(body) && isRecord(body.error)) {
    const { code, message, fields } = body.error;
    if (typeof code === "string" && typeof message === "string") {
      return new ApiError({
        status,
        code,
        message,
        fields: normalizeFieldErrors(fields),
        body,
      });
    }
  }

  return unexpectedApiResponse(body, status);
}

function networkError(cause: unknown): ApiError {
  return new ApiError({
    status: null,
    code: "NETWORK_ERROR",
    message: "The API could not be reached. Please try again.",
    cause,
  });
}

function normalizeFieldErrors(value: unknown): ApiFieldErrors {
  if (!isRecord(value)) return {};
  return Object.fromEntries(
    Object.entries(value).flatMap(([field, messages]) => {
      if (!Array.isArray(messages) || !messages.every((message) => typeof message === "string")) return [];
      return [[field, messages]];
    }),
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError"
    || isRecord(error) && error.name === "AbortError";
}
