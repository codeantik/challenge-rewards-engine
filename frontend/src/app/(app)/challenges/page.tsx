"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/error-boundary";
import { Skeleton } from "@/components/ui/skeleton";
import { useWeeklyChallenge } from "@/hooks/use-weekly-challenge";
import { useAuth } from "@/lib/auth-context";
import { fetchActiveChallenges, type ChallengeWithProgress } from "@/lib/challenges-api";
import { WEEKLY_POLL_INTERVAL_MS } from "@/lib/config";
import { fetchStreaks } from "@/lib/progress-api";

const CHART_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
];

function challengeTarget(challenge: ChallengeWithProgress): number {
  const configured = challenge.rule_config.target;
  return challenge.progress?.target_value ?? (typeof configured === "number" ? configured : 0);
}

function SectionSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-4 w-full" />
      ))}
    </div>
  );
}

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

/** Reuses the same `useWeeklyChallenge` query the sidebar widget polls, so
 * this section and the widget share one cached 30s poll instead of issuing
 * a second request for the same data. */
function WeeklyBreakdown() {
  const { token } = useAuth();
  const { data, isLoading, isError, refetch } = useWeeklyChallenge(token);

  if (isLoading) return <SectionSkeleton />;
  if (isError) {
    return (
      <SectionError message="Couldn't load this week's challenges." onRetry={() => refetch()} />
    );
  }
  if (!data || data.length === 0) {
    return <p className="text-muted-foreground text-sm">No weekly challenges active right now.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {data.map((challenge) => {
        const current = challenge.progress?.current_value ?? 0;
        const target = challengeTarget(challenge);
        const complete = challenge.progress?.is_complete ?? false;
        return (
          <div key={challenge.id} className="flex items-center justify-between gap-2 text-sm">
            <div className="flex flex-col">
              <span className="font-medium">{challenge.name}</span>
              <span className="text-muted-foreground text-xs">{challenge.description}</span>
            </div>
            <Badge variant={complete ? "secondary" : "outline"}>
              {complete ? "Complete" : `${current}/${target}`}
            </Badge>
          </div>
        );
      })}
    </div>
  );
}

/** The required charting data-viz: a Recharts radial-bar ring per active
 * challenge, showing percent-to-target. Labels are rendered as a plain list
 * beside the chart rather than through Recharts' own `Legend` (which groups
 * by data key, not by bar, for this chart shape). */
function ProgressRings() {
  const { token } = useAuth();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["challenges", "active"],
    queryFn: () => fetchActiveChallenges(token as string),
    enabled: token !== null,
    refetchInterval: WEEKLY_POLL_INTERVAL_MS,
    refetchIntervalInBackground: false,
  });

  if (isLoading) return <SectionSkeleton rows={4} />;
  if (isError) {
    return <SectionError message="Couldn't load challenge progress." onRetry={() => refetch()} />;
  }
  if (!data || data.length === 0) {
    return <p className="text-muted-foreground text-sm">No active challenges right now.</p>;
  }

  const rings = data.map((challenge, i) => {
    const current = challenge.progress?.current_value ?? 0;
    const target = challengeTarget(challenge);
    const pct = target > 0 ? Math.min(100, Math.round((current / target) * 100)) : 0;
    return { name: challenge.name, value: pct, fill: CHART_COLORS[i % CHART_COLORS.length] };
  });

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
      <div className="h-64 w-full sm:w-1/2">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart data={rings} innerRadius="20%" outerRadius="90%" startAngle={90} endAngle={-270}>
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar background dataKey="value" cornerRadius={8} />
            <Tooltip />
          </RadialBarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-1 flex-col gap-2">
        {rings.map((ring) => (
          <div key={ring.name} className="flex items-center gap-2 text-sm">
            <span
              className="size-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: ring.fill }}
            />
            <span className="flex-1 truncate">{ring.name}</span>
            <span className="text-muted-foreground text-xs">{ring.value}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Second chart: current-vs-best streak per streak-type challenge. This is
 * the only place `best_streak` is surfaced (the backend recomputes it live
 * from source events; it isn't cached in `progress`). */
function StreakChart() {
  const { token } = useAuth();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["users", "me", "streaks"],
    queryFn: () => fetchStreaks(token as string),
    enabled: token !== null,
    refetchInterval: WEEKLY_POLL_INTERVAL_MS,
    refetchIntervalInBackground: false,
  });

  if (isLoading) return <SectionSkeleton rows={4} />;
  if (isError) {
    return <SectionError message="Couldn't load streaks." onRetry={() => refetch()} />;
  }
  if (!data || data.length === 0) {
    return <p className="text-muted-foreground text-sm">No streak challenges active right now.</p>;
  }

  const streakData = data.map((s) => ({
    name: s.name,
    current: s.current_streak,
    best: s.best_streak,
  }));

  return (
    <div className="h-60 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={streakData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
          <Tooltip />
          <Legend />
          <Bar dataKey="current" name="Current streak" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} />
          <Bar dataKey="best" name="Best streak" fill="var(--color-chart-3)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function ChallengesPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold">Challenges &amp; Progress</h1>
        <p className="text-muted-foreground text-sm">
          Updates automatically every 30s as the worker evaluates new events.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">This week</CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorBoundary>
            <WeeklyBreakdown />
          </ErrorBoundary>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorBoundary>
            <ProgressRings />
          </ErrorBoundary>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Streaks</CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorBoundary>
            <StreakChart />
          </ErrorBoundary>
        </CardContent>
      </Card>
    </div>
  );
}
