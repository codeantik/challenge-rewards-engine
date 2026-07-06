"use client";

import { ArchiveIcon, PencilIcon, PlayIcon, PlusIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ErrorBoundary } from "@/components/error-boundary";
import { Skeleton } from "@/components/ui/skeleton";
import { useArchiveChallenge, useUpdateChallenge } from "@/hooks/use-admin-challenge-mutations";
import { useAdminChallenges } from "@/hooks/use-admin-challenges";
import type { AdminChallenge } from "@/lib/admin-challenges-api";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-muted text-muted-foreground",
  active: "bg-success/15 text-success",
  expired: "bg-secondary text-secondary-foreground",
  archived: "bg-destructive/10 text-destructive",
};

function ChallengesListSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: 4 }, (_, i) => (
        <Skeleton key={i} className="h-24 w-full" />
      ))}
    </div>
  );
}

function ChallengeRow({ challenge }: { challenge: AdminChallenge }) {
  const [confirmArchiveOpen, setConfirmArchiveOpen] = useState(false);
  const updateMutation = useUpdateChallenge();
  const archiveMutation = useArchiveChallenge();

  const ruleSummary =
    challenge.type === "streak"
      ? `${challenge.rule_config.length ?? "?"}-day streak`
      : `${challenge.rule_config.target ?? "?"}x ${challenge.event_type}`;

  return (
    <Card className="card-hover">
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{challenge.name}</span>
              <Badge className={cn("capitalize", STATUS_STYLES[challenge.status])}>
                {challenge.status}
              </Badge>
              <Badge variant="outline" className="capitalize">
                {challenge.period.replace("_", " ")}
              </Badge>
            </div>
            {challenge.description && (
              <p className="text-muted-foreground text-sm">{challenge.description}</p>
            )}
            <p className="text-muted-foreground text-xs">
              {ruleSummary} · reward: {challenge.reward.amount} {challenge.reward.type}
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-1.5">
            {challenge.status === "draft" && (
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5"
                disabled={updateMutation.isPending}
                onClick={() => updateMutation.mutate({ id: challenge.id, input: { status: "active" } })}
              >
                <PlayIcon className="size-3.5" />
                Activate
              </Button>
            )}
            <Link
              href={`/admin/challenges/${challenge.id}/edit`}
              className={cn(buttonVariants({ size: "sm", variant: "outline" }), "gap-1.5")}
            >
              <PencilIcon className="size-3.5" />
              Edit
            </Link>
            {challenge.status !== "archived" && (
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5"
                disabled={archiveMutation.isPending}
                onClick={() => setConfirmArchiveOpen(true)}
              >
                <ArchiveIcon className="size-3.5" />
                Archive
              </Button>
            )}
          </div>
        </div>
      </CardContent>

      <Dialog open={confirmArchiveOpen} onOpenChange={setConfirmArchiveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Archive &quot;{challenge.name}&quot;?</DialogTitle>
            <DialogDescription>
              Archived challenges stop being evaluated and disappear from the active list. This
              can&apos;t be undone from here, but existing progress and rewards are kept.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmArchiveOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                archiveMutation.mutate(challenge.id);
                setConfirmArchiveOpen(false);
              }}
            >
              Archive
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function AdminChallengesContent() {
  const { data, isLoading, isError, refetch } = useAdminChallenges();

  if (isLoading) return <ChallengesListSkeleton />;

  if (isError) {
    return (
      <div className="border-destructive/30 bg-destructive/5 flex flex-col items-center gap-2 rounded-lg border p-6 text-center text-sm">
        <p className="text-destructive">Couldn&apos;t load challenges.</p>
        <Button size="sm" variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        No challenges yet — create one to get started.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {data.map((challenge) => (
        <ChallengeRow key={challenge.id} challenge={challenge} />
      ))}
    </div>
  );
}

export default function AdminChallengesPage() {
  return (
    <div className="animate-in fade-in flex flex-col gap-4 duration-300">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Manage challenges</h1>
          <p className="text-muted-foreground text-sm">
            Admin-only — configure the data-driven challenges the engine evaluates.
          </p>
        </div>
        <Link href="/admin/challenges/new" className={cn(buttonVariants(), "gap-1.5")}>
          <PlusIcon className="size-3.5" />
          New challenge
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">All challenges</CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorBoundary>
            <AdminChallengesContent />
          </ErrorBoundary>
        </CardContent>
      </Card>
    </div>
  );
}
