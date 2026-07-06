"use client";

import { use } from "react";
import { useRouter } from "next/navigation";

import { ChallengeForm } from "@/components/admin/challenge-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/error-boundary";
import { Skeleton } from "@/components/ui/skeleton";
import { useUpdateChallenge } from "@/hooks/use-admin-challenge-mutations";
import { useAdminChallenge } from "@/hooks/use-admin-challenges";

interface EditChallengePageProps {
  params: Promise<{ id: string }>;
}

function EditChallengeContent({ id }: { id: string }) {
  const router = useRouter();
  const { data, isLoading, isError, refetch } = useAdminChallenge(id);
  const { mutate, isPending } = useUpdateChallenge();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-8 w-1/2" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="border-destructive/30 bg-destructive/5 flex flex-col items-center gap-2 rounded-lg border p-6 text-center text-sm">
        <p className="text-destructive">Couldn&apos;t load this challenge.</p>
        <Button size="sm" variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <ChallengeForm
      initial={data}
      isPending={isPending}
      submitLabel="Save changes"
      onSubmit={(input) =>
        mutate({ id, input }, { onSuccess: () => router.push("/admin/challenges") })
      }
    />
  );
}

export default function EditChallengePage({ params }: EditChallengePageProps) {
  const { id } = use(params);

  return (
    <Card className="animate-in fade-in slide-in-from-bottom-2 mx-auto max-w-2xl duration-300">
      <CardHeader>
        <CardTitle>Edit challenge</CardTitle>
        <CardDescription>Changes apply on the worker&apos;s next evaluation pass.</CardDescription>
      </CardHeader>
      <CardContent>
        <ErrorBoundary>
          <EditChallengeContent id={id} />
        </ErrorBoundary>
      </CardContent>
    </Card>
  );
}
