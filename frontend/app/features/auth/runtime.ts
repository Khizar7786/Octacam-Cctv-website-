import { ApiError, unexpectedApiResponse, type ApiClient, type ApiPath, type ApiRequestOptions } from "../../lib/api/client.ts";

const AUTH_PATH = "/api/v1/auth/" as const;
const CSRF_PATH = `${AUTH_PATH}csrf/` as const;
const REFRESH_PATH = `${AUTH_PATH}refresh/` as const;
const LOGOUT_PATH = `${AUTH_PATH}logout/` as const;

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  is_staff: boolean;
}

export type AuthState =
  | { status: "loading" }
  | { status: "authenticated"; user: AuthUser }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export interface LoginCredentials { email: string; password: string }
export interface RegistrationDetails extends LoginCredentials { full_name: string; phone?: string }
export type UnsafeMethod = "POST" | "PUT" | "PATCH" | "DELETE";

const INITIAL_STATE: AuthState = { status: "loading" };

function authenticationRequired(): ApiError {
  return new ApiError({ status: 401, code: "AUTHENTICATION_REQUIRED", message: "Please sign in to continue." });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseAuthResponse(body: unknown): { user: AuthUser; access: string } {
  if (!isRecord(body) || !isRecord(body.user) || typeof body.access !== "string" || !body.access) {
    throw unexpectedApiResponse(body);
  }
  const user = body.user;
  if (!Number.isSafeInteger(user.id) || (user.id as number) <= 0
    || typeof user.email !== "string" || typeof user.full_name !== "string"
    || typeof user.phone !== "string" || typeof user.is_staff !== "boolean") {
    throw unexpectedApiResponse(body);
  }
  return {
    access: body.access,
    user: {
      id: user.id as number,
      email: user.email,
      full_name: user.full_name,
      phone: user.phone,
      is_staff: user.is_staff,
    },
  };
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "The session could not be restored. Please try again.";
}

function aborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw signal.reason ?? new DOMException("Request cancelled", "AbortError");
}

/** A caller can stop waiting without cancelling the one shared rotating-cookie refresh. */
function waitFor<T>(promise: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return promise;
  aborted(signal);
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => reject(signal.reason ?? new DOMException("Request cancelled", "AbortError"));
    signal.addEventListener("abort", onAbort, { once: true });
    promise.then(resolve, reject).finally(() => signal.removeEventListener("abort", onAbort));
  });
}

/** Per-browser-session runtime. Create it inside React, never as an SSR module singleton. */
export class AuthRuntime {
  private readonly client: ApiClient;
  private state: AuthState = INITIAL_STATE;
  private access: string | null = null;
  private csrf: string | null = null;
  private csrfFlight: Promise<string> | null = null;
  private refreshFlight: Promise<string> | null = null;
  private sessionStartFlight: Promise<unknown> | null = null;
  private logoutFlight: Promise<void> | null = null;
  private lastError: unknown = null;
  private generation = 0;
  private signingOut = false;
  private listeners = new Set<() => void>();

  constructor(client: ApiClient) { this.client = client; }

  readonly getState = (): AuthState => this.state;
  readonly getServerSnapshot = (): AuthState => INITIAL_STATE;
  readonly subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  private setState(state: AuthState): void {
    this.state = state;
    for (const listener of this.listeners) listener();
  }

  async csrfToken(): Promise<string> {
    if (this.csrf) return this.csrf;
    if (this.csrfFlight) return this.csrfFlight;
    const task = (async () => {
      const body = await this.client.request<unknown>(CSRF_PATH, { credentials: "same-origin" });
      if (!isRecord(body) || typeof body.csrfToken !== "string" || !body.csrfToken) {
        throw unexpectedApiResponse(body);
      }
      this.csrf = body.csrfToken;
      return this.csrf;
    })();
    const flight = task.finally(() => { if (this.csrfFlight === flight) this.csrfFlight = null; });
    this.csrfFlight = flight;
    return flight;
  }

  async requestWithCsrf<T>(path: ApiPath, options: ApiRequestOptions & { method: UnsafeMethod }): Promise<T> {
    aborted(options.signal);
    const token = await waitFor(this.csrfToken(), options.signal);
    aborted(options.signal);
    const headers = new Headers(options.headers);
    headers.set("X-CSRFToken", token);
    try {
      return await this.client.request<T>(path, { ...options, credentials: "same-origin", headers });
    } catch (error) {
      if (error instanceof ApiError && error.status === 403 && error.message === "CSRF verification failed.") {
        this.csrf = null;
      }
      throw error;
    }
  }

  private async authPost(path: ApiPath, payload?: object): Promise<{ user: AuthUser; access: string }> {
    const body = await this.requestWithCsrf<unknown>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    });
    return parseAuthResponse(body);
  }

  private async refresh(): Promise<string> {
    if (this.signingOut) throw authenticationRequired();
    if (this.refreshFlight) return this.refreshFlight;
    const generation = this.generation;
    const task = (async () => {
      try {
        const session = await this.authPost(REFRESH_PATH);
        if (generation !== this.generation || this.signingOut) throw authenticationRequired();
        this.access = session.access;
        this.lastError = null;
        this.setState({ status: "authenticated", user: session.user });
        return session.access;
      } catch (error) {
        if (generation === this.generation && !this.signingOut) {
          this.access = null;
          this.lastError = error;
          this.setState(error instanceof ApiError && error.status === 401
            ? { status: "unauthenticated" }
            : { status: "error", message: errorMessage(error) });
        }
        throw error;
      }
    })();
    const flight = task.finally(() => { if (this.refreshFlight === flight) this.refreshFlight = null; });
    this.refreshFlight = flight;
    return flight;
  }

  async restore(): Promise<AuthState> {
    if (this.signingOut || this.state.status === "authenticated") return this.state;
    if (!this.refreshFlight) this.setState({ status: "loading" });
    try { await this.refresh(); } catch { /* The state records unauthenticated or a retryable error. */ }
    return this.state;
  }

  private async startSession(path: ApiPath, details: LoginCredentials | RegistrationDetails): Promise<AuthUser> {
    if (this.signingOut) throw authenticationRequired();
    const generation = this.generation;
    if (this.refreshFlight) await this.refreshFlight.catch(() => undefined);
    if (this.sessionStartFlight) await this.sessionStartFlight.catch(() => undefined);
    if (generation !== this.generation || this.signingOut) throw authenticationRequired();
    const task = this.authPost(path, details);
    this.sessionStartFlight = task;
    let session: { user: AuthUser; access: string };
    try { session = await task; }
    finally { if (this.sessionStartFlight === task) this.sessionStartFlight = null; }
    if (generation !== this.generation || this.signingOut) throw authenticationRequired();
    this.generation++;
    this.access = session.access;
    this.lastError = null;
    this.setState({ status: "authenticated", user: session.user });
    return session.user;
  }

  login(details: LoginCredentials): Promise<AuthUser> {
    return this.startSession(`${AUTH_PATH}login/`, details);
  }

  register(details: RegistrationDetails): Promise<AuthUser> {
    return this.startSession(`${AUTH_PATH}register/`, details);
  }

  async requestAuthenticated<T>(path: ApiPath, options: ApiRequestOptions = {}): Promise<T> {
    if (this.signingOut) throw authenticationRequired();
    if (this.state.status === "loading") await waitFor(this.restore(), options.signal);
    aborted(options.signal);
    if (!this.access) {
      if (this.state.status === "error" && this.lastError instanceof Error) throw this.lastError;
      throw authenticationRequired();
    }
    const generation = this.generation;
    const firstToken = this.access;
    const send = (token: string) => {
      const headers = new Headers(options.headers);
      headers.set("Authorization", `Bearer ${token}`);
      return this.client.request<T>(path, { ...options, headers });
    };
    try {
      const result = await send(firstToken);
      if (generation !== this.generation || this.signingOut) throw authenticationRequired();
      return result;
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401 || generation !== this.generation || this.signingOut) throw error;
      // A sibling may already have failed refresh and cleared this token.
      if (!this.access) throw this.lastError instanceof Error ? this.lastError : authenticationRequired();
      // A sibling may have completed refresh after this request used its old token.
      const token = this.access !== firstToken
        ? this.access
        : await waitFor(this.refresh(), options.signal);
      aborted(options.signal);
      if (generation !== this.generation || this.signingOut) throw authenticationRequired();
      try {
        const result = await send(token);
        if (generation !== this.generation || this.signingOut) throw authenticationRequired();
        return result;
      } catch (retryError) {
        if (retryError instanceof ApiError && retryError.status === 401 && this.access === token) {
          this.generation++;
          this.access = null;
          this.setState({ status: "unauthenticated" });
        }
        throw retryError;
      }
    }
  }

  logout(): Promise<void> {
    if (this.logoutFlight) return this.logoutFlight;
    this.generation++;
    this.signingOut = true;
    this.access = null;
    this.lastError = null;
    this.setState({ status: "unauthenticated" });
    const pendingRefresh = this.refreshFlight;
    const pendingStart = this.sessionStartFlight;
    const task = (async () => {
      if (pendingRefresh) await pendingRefresh.catch(() => undefined);
      if (pendingStart) await pendingStart.catch(() => undefined);
      await this.requestWithCsrf<void>(LOGOUT_PATH, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } });
    })();
    const flight = task.finally(() => {
      this.signingOut = false;
      if (this.logoutFlight === flight) this.logoutFlight = null;
    });
    this.logoutFlight = flight;
    return flight;
  }
}
