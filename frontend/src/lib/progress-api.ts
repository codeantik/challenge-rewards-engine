import { apiRequest } from "@/lib/api";

export interface StreakOut {
  challenge_id: string;
  name: string;
  current_streak: number;
  best_streak: number;
  target_length: number;
}

export function fetchStreaks(token: string): Promise<StreakOut[]> {
  return apiRequest<StreakOut[]>("/users/me/streaks", { token });
}
