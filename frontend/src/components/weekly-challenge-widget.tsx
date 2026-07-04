"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/error-boundary";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { useWeeklyChallenge } from "@/hooks/use-weekly-challenge";
import type { ChallengeWithProgress } from "@/lib/challenges-api";

function ProgressBar({ value, target }: { value: number; target: number }) {
  const pct = target > 0 ? Math.min(100, Math.round((value / target) * 100)) : 0;
  return (
    <div className="bg-muted h-1.5 w-full overflow-hidden rounded-full">
      <div className="bg-primary h-full rounded-full transition-all" style={{ width: `${pct}%` }} />
    </div>
  );
}

function ChallengeRow({ challenge }: { challenge: ChallengeWithProgress }) {
  const current = challenge.progress?.current_value ?? 0;
  const target = challenge.progress?.target_value ?? (challenge.rule_config.target as number) ?? 0;
  const complete = challenge.progress?.is_complete ?? false;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-sm font-medium" title={challenge.name}>
          {challenge.name}
        </p>
        <span className="text-muted-foreground shrink-0 text-xs">
          {complete ? "Done" : `${current}/${target}`}
        </span>
      </div>
      <ProgressBar value={current} target={target} />
    </div>
  );
}

function WeeklyChallengeContent() {
  const { token } = useAuth();
  const { data, isLoading, isError, refetch } = useWeeklyChallenge(token);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-3.5 w-full" />
        <Skeleton className="h-3.5 w-2/3" />
        <Skeleton className="h-3.5 w-full" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-start gap-2 text-sm">
        <p className="text-destructive">Couldn&apos;t load this week&apos;s challenges.</p>
        <Button size="sm" variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return <p className="text-muted-foreground text-sm">No weekly challenges active right now.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {data.map((challenge) => (
        <ChallengeRow key={challenge.id} challenge={challenge} />
      ))}
    </div>
  );
}

/** Layout-level widget — mounted once in the authenticated shell so it's
 * present on every route (Phase 6 requirement). Polling and data-fetching
 * live in `useWeeklyChallenge`; this component is presentation only. */
export function WeeklyChallengeWidget() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">This Week</CardTitle>
      </CardHeader>
      <CardContent>
        <ErrorBoundary>
          <WeeklyChallengeContent />
        </ErrorBoundary>
      </CardContent>
    </Card>
  );
}
