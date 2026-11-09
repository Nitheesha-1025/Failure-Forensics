import type { ApiErrorBody } from "../types/api";

const TOKEN_STORAGE_KEY = "forensics_access_token";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getApiBaseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL;
  if (typeof base === "string" && base.trim()) {
    return base.replace(/\/$/, "");
  }
  return "http://localhost:8090";
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

type UnauthorizedHandler = () => void;

let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    const detail = body.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d) => d.msg).join("; ");
    }
  } catch {
    /* ignore */
  }
  if (response.status === 401) {
    return "Invalid email or password";
  }
  if (response.status === 404) {
    return "Resource not found";
  }
  if (response.status === 422) {
    return "Validation error";
  }
  if (response.status === 429) {
    return "Too many requests. Please wait and try again.";
  }
  if (response.status === 503) {
    return "The service is temporarily unavailable. Please try again.";
  }
  if (response.status >= 500) {
    return "Something went wrong. Please try again.";
  }
  return "Request failed";
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  formData?: FormData;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, auth = true, formData } = options;
  const headers: Record<string, string> = {};

  if (!formData) {
    headers["Content-Type"] = "application/json";
  }

  if (auth) {
    const token = getStoredToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError("Unable to reach the server. Check your connection.", 0);
  }

  if (response.status === 401 && auth) {
    clearStoredToken();
    onUnauthorized?.();
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}
