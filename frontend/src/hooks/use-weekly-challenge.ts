import { useQuery } from "@tanstack/react-query";

import { fetchWeeklyChallenges } from "@/lib/challenges-api";
import { WEEKLY_POLL_INTERVAL_MS } from "@/lib/config";

/**
 * Single responsibility: encapsulate polling the caller's active weekly
 * challenges (with progress) so the widget component stays purely
 * presentational. Poll interval is 30s — evaluation is async and
 * human-scale, so anything faster just hammers the API for progress that
 * only moves on the order of user actions (see explain.md §6).
 *
 * Not enabled without a token: the weekly widget renders on every
 * authenticated route, but there's a brief window before `AuthProvider`
 * finishes reading localStorage where no token exists yet.
 */
export function useWeeklyChallenge(token: string | null) {
  return useQuery({
    queryKey: ["challenges", "weekly"],
    queryFn: () => fetchWeeklyChallenges(token as string),
    enabled: token !== null,
    refetchInterval: WEEKLY_POLL_INTERVAL_MS,
    refetchIntervalInBackground: false,
  });
}
