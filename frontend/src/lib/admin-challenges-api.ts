import { apiRequest } from "@/lib/api";

/** Mirrors `STRATEGIES` in `backend/app/services/strategies.py` — the
 * evaluator reads valid types from that registry, not a hardcoded literal
 * (invariant #3). This list is just the admin form's dropdown options; it
 * doesn't gate anything server-side, so adding a third strategy means
 * adding one entry here, not touching evaluator logic. */
export const CHALLENGE_TYPES = ["count", "streak"] as const;
export type ChallengeType = (typeof CHALLENGE_TYPES)[number];

/** Mirrors the event catalog in CLAUDE.md. */
export const EVENT_TYPES = [
  "post_created",
  "post_viewed",
  "comment_posted",
  "solution_marked",
] as const;
export type EventType = (typeof EVENT_TYPES)[number];

export const CHALLENGE_STATUSES = ["draft", "active", "expired", "archived"] as const;
export type ChallengeStatus = (typeof CHALLENGE_STATUSES)[number];

export const CHALLENGE_PERIODS = ["one_time", "weekly"] as const;
export type ChallengePeriod = (typeof CHALLENGE_PERIODS)[number];

export interface RewardConfig {
  type: string;
  amount: number;
}

export interface AdminChallenge {
  id: string;
  name: string;
  description: string;
  type: string;
  event_type: string;
  rule_config: Record<string, unknown>;
  reward: RewardConfig;
  status: string;
  period: string;
  start_at: string | null;
  end_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChallengeInput {
  name: string;
  description: string;
  type: string;
  event_type: string;
  rule_config: Record<string, unknown>;
  reward: RewardConfig;
  status: ChallengeStatus;
  period: ChallengePeriod;
  start_at: string | null;
  end_at: string | null;
}

export type ChallengeUpdateInput = Partial<ChallengeInput>;

export function fetchAdminChallenges(token: string): Promise<AdminChallenge[]> {
  return apiRequest<AdminChallenge[]>("/admin/challenges", { token });
}

export function fetchAdminChallenge(token: string, id: string): Promise<AdminChallenge> {
  return apiRequest<AdminChallenge>(`/admin/challenges/${id}`, { token });
}

export function createChallenge(token: string, input: ChallengeInput): Promise<AdminChallenge> {
  return apiRequest<AdminChallenge>("/admin/challenges", {
    method: "POST",
    body: input,
    token,
  });
}

export function updateChallenge(
  token: string,
  id: string,
  input: ChallengeUpdateInput,
): Promise<AdminChallenge> {
  return apiRequest<AdminChallenge>(`/admin/challenges/${id}`, {
    method: "PATCH",
    body: input,
    token,
  });
}

export function archiveChallenge(token: string, id: string): Promise<AdminChallenge> {
  return apiRequest<AdminChallenge>(`/admin/challenges/${id}`, { method: "DELETE", token });
}
