import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth-context";
import { fetchAdminChallenge, fetchAdminChallenges } from "@/lib/admin-challenges-api";

export const ADMIN_CHALLENGES_KEY = ["admin", "challenges"] as const;

/** Single responsibility: list every challenge (any status) for the admin
 * console — unlike `useWeeklyChallenge`/`fetchActiveChallenges`, this isn't
 * scoped to the caller's own progress, so it hits `/admin/challenges`
 * rather than the user-facing `/challenges` read endpoints. */
export function useAdminChallenges() {
  const { token } = useAuth();
  return useQuery({
    queryKey: ADMIN_CHALLENGES_KEY,
    queryFn: () => fetchAdminChallenges(token as string),
    enabled: token !== null,
  });
}

export function useAdminChallenge(id: string) {
  const { token } = useAuth();
  return useQuery({
    queryKey: [...ADMIN_CHALLENGES_KEY, id],
    queryFn: () => fetchAdminChallenge(token as string, id),
    enabled: token !== null,
  });
}
