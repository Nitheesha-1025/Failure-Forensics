import { apiRequest } from "./client";
import type { TokenResponse, User } from "../types/api";

export interface RegisterPayload {
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export function registerUser(payload: RegisterPayload): Promise<User> {
  return apiRequest<User>("/v1/auth/register", {
    method: "POST",
    body: payload,
    auth: false,
  });
}

export function loginUser(payload: LoginPayload): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/v1/auth/login", {
    method: "POST",
    body: payload,
    auth: false,
  });
}

export function fetchCurrentUser(): Promise<User> {
  return apiRequest<User>("/v1/auth/me");
}
