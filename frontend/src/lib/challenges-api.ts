import { apiRequest } from "@/lib/api";

export interface ProgressOut {
  challenge_id: string;
  current_value: number;
  target_value: number;
  is_complete: boolean;
  completed_at: string | null;
  updated_at: string;
}

export interface ChallengeWithProgress {
  id: string;
  name: string;
  description: string;
  type: string;
  event_type: string;
  rule_config: Record<string, unknown>;
  reward: Record<string, unknown>;
  status: string;
  period: "one_time" | "weekly";
  start_at: string | null;
  end_at: string | null;
  created_at: string;
  updated_at: string;
  progress: ProgressOut | null;
}

export function fetchWeeklyChallenges(token: string): Promise<ChallengeWithProgress[]> {
  return apiRequest<ChallengeWithProgress[]>("/challenges/weekly", { token });
}

export function fetchActiveChallenges(token: string): Promise<ChallengeWithProgress[]> {
  return apiRequest<ChallengeWithProgress[]>("/challenges", { token });
}
