"use client";

import { useQuery } from "@tanstack/react-query";
import { AwardIcon, SparklesIcon } from "lucide-react";
import { useState } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/error-boundary";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { fetchRewards, fetchRewardsSummary } from "@/lib/rewards-api";
import { formatRelativeTime } from "@/lib/utils";

const LEDGER_LIMIT = 10;

function SectionError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="border-destructive/30 bg-destructive/5 flex flex-col items-center gap-2 rounded-lg border p-4 text-center text-sm">
      <p className="text-destructive">{message}</p>
      <Button size="sm" variant="outline" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

/** Points balance + badges, backed by the server-computed
 * `/users/me/rewards/summary` aggregate — summing the paginated ledger
 * client-side would only ever total whatever page happened to be loaded. */
function PointsSummary() {
  const { token } = useAuth();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["users", "me", "rewards", "summary"],
    queryFn: () => fetchRewardsSummary(token as string),
    enabled: token !== null,
  });

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-4 w-40" />
      </div>
    );
  }
  if (isError) {
    return (
      <SectionError message="Couldn't load your rewards summary." onRetry={() => refetch()} />
    );
  }

  const badges = data?.badges ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="brand-gradient-bg flex items-center gap-3 rounded-xl p-4 text-white shadow-sm">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-white/15">
          <SparklesIcon className="size-5" />
        </span>
        <div>
          <p className="text-3xl leading-tight font-bold tabular-nums">
            {data?.total_points ?? 0}
          </p>
          <p className="text-sm text-white/80">points earned</p>
        </div>
      </div>
      {badges.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {badges.map((badge) => (
            <Badge key={badge.reward_type} variant="secondary" className="gap-1 py-1">
              <AwardIcon className="text-primary size-3" />
              {badge.reward_type} ×{badge.count}
            </Badge>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground text-sm">
          No badges yet — complete a challenge to earn one.
        </p>
      )}
    </div>
  );
}

function LedgerSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: LEDGER_LIMIT }, (_, i) => (
        <div key={i} className="flex items-center justify-between gap-2">
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-12" />
        </div>
      ))}
    </div>
  );
}

function RewardsLedger() {
  const { token } = useAuth();
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["users", "me", "rewards", "list", page],
    queryFn: () => fetchRewards(token as string, { page, limit: LEDGER_LIMIT }),
    enabled: token !== null,
  });

  if (isLoading) return <LedgerSkeleton />;
  if (isError) {
    return <SectionError message="Couldn't load your reward ledger." onRetry={() => refetch()} />;
  }
  if (!data || data.rewards.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        No rewards yet — complete a challenge to earn one.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        {data.rewards.map((reward) => (
          <div
            key={reward.id}
            className="flex items-center justify-between gap-2 border-b pb-2 text-sm last:border-b-0 last:pb-0"
          >
            <div className="flex flex-col">
              <span className="font-medium capitalize">{reward.reward_type}</span>
              <span className="text-muted-foreground text-xs">
                {formatRelativeTime(reward.created_at)}
              </span>
            </div>
            <span className="text-success font-semibold tabular-nums">+{reward.amount}</span>
          </div>
        ))}
      </div>

      {data.meta.total_pages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <Button
            size="sm"
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span className="text-muted-foreground text-xs">
            Page {data.meta.page} of {data.meta.total_pages}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={page >= data.meta.total_pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

export default function ProfilePage() {
  const { user } = useAuth();

  return (
    <div className="animate-in fade-in flex flex-col gap-4 duration-300">
      <div className="flex items-center gap-3">
        <Avatar size="lg" className="ring-border ring-2">
          <AvatarFallback className="brand-gradient-bg text-white">
            {user?.email.slice(0, 2).toUpperCase()}
          </AvatarFallback>
        </Avatar>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Profile &amp; Rewards</h1>
          <p className="text-muted-foreground text-sm">{user?.email}</p>
        </div>
      </div>

      <Card className="card-hover">
        <CardHeader>
          <CardTitle className="text-sm">Points &amp; badges</CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorBoundary>
            <PointsSummary />
          </ErrorBoundary>
        </CardContent>
      </Card>

      <Card className="card-hover">
        <CardHeader>
          <CardTitle className="text-sm">Reward ledger</CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorBoundary>
            <RewardsLedger />
          </ErrorBoundary>
        </CardContent>
      </Card>
    </div>
  );
}
