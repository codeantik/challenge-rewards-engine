export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

/**
 * Evaluation is async and human-scale — sub-10s polling hammers the API for
 * progress that only changes on the order of user actions. 30s keeps the
 * weekly widget feeling live without wasteful load (see explain.md §6).
 */
export const WEEKLY_POLL_INTERVAL_MS = 30_000;

export const AUTH_STORAGE_KEY = "cre.auth";
