import { apiRequest, apiRequestEnvelope } from "@/lib/api";
import type { PageMeta } from "@/lib/posts-api";

export interface RewardOut {
  id: string;
  reward_type: string;
  amount: number;
  source_challenge_id: string;
  completion_key: string;
  created_at: string;
}

export interface RewardTypeSummary {
  reward_type: string;
  total_amount: number;
  count: number;
  latest_at: string;
}

export interface RewardsSummary {
  total_points: number;
  badges: RewardTypeSummary[];
}

export interface RewardListResult {
  rewards: RewardOut[];
  meta: PageMeta;
}

export async function fetchRewards(
  token: string,
  { page, limit = 20 }: { page: number; limit?: number },
): Promise<RewardListResult> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  const envelope = await apiRequestEnvelope<RewardOut[]>(
    `/users/me/rewards?${params.toString()}`,
    { token },
  );
  return { rewards: envelope.data, meta: envelope.meta as unknown as PageMeta };
}

export function fetchRewardsSummary(token: string): Promise<RewardsSummary> {
  return apiRequest<RewardsSummary>("/users/me/rewards/summary", { token });
}
