"use client";

import { CheckCircle2Icon, TrophyIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/error-boundary";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { useWeeklyChallenge } from "@/hooks/use-weekly-challenge";
import type { ChallengeWithProgress } from "@/lib/challenges-api";
import { cn } from "@/lib/utils";

function ChallengeRow({ challenge }: { challenge: ChallengeWithProgress }) {
  const current = challenge.progress?.current_value ?? 0;
  const target = challenge.progress?.target_value ?? (challenge.rule_config.target as number) ?? 0;
  const complete = challenge.progress?.is_complete ?? false;
  const pct = target > 0 ? Math.round((current / target) * 100) : 0;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-sm font-medium" title={challenge.name}>
          {challenge.name}
        </p>
        <span
          className={cn(
            "flex shrink-0 items-center gap-1 text-xs",
            complete ? "text-success font-medium" : "text-muted-foreground",
          )}
        >
          {complete && <CheckCircle2Icon className="size-3" />}
          {complete ? "Done" : `${current}/${target}`}
        </span>
      </div>
      <Progress value={pct} complete={complete} />
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
    <Card className="border-primary/10 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5 text-sm">
          <TrophyIcon className="text-primary size-4" />
          This Week
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ErrorBoundary>
          <WeeklyChallengeContent />
        </ErrorBoundary>
      </CardContent>
    </Card>
  );
}
