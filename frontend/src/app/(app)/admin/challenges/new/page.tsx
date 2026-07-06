"use client";

import { useRouter } from "next/navigation";

import { ChallengeForm } from "@/components/admin/challenge-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useCreateChallenge } from "@/hooks/use-admin-challenge-mutations";

export default function NewChallengePage() {
  const router = useRouter();
  const { mutate, isPending } = useCreateChallenge();

  return (
    <Card className="animate-in fade-in slide-in-from-bottom-2 mx-auto max-w-2xl duration-300">
      <CardHeader>
        <CardTitle>New challenge</CardTitle>
        <CardDescription>
          Configure the event, rule, and reward — the worker picks it up on the next matching
          event once it&apos;s active.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChallengeForm
          isPending={isPending}
          submitLabel="Create challenge"
          onSubmit={(input) =>
            mutate(input, { onSuccess: () => router.push("/admin/challenges") })
          }
        />
      </CardContent>
    </Card>
  );
}
