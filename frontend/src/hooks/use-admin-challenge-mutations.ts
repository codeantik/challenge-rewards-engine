import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ADMIN_CHALLENGES_KEY } from "@/hooks/use-admin-challenges";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import {
  archiveChallenge,
  createChallenge,
  type ChallengeInput,
  type ChallengeUpdateInput,
  updateChallenge,
} from "@/lib/admin-challenges-api";

function mutationErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

/** Three plain CRUD mutations for the admin console. No optimistic writes
 * here (unlike the forum's create-post/comment mutations) — this is an
 * admin tool where correctness of the re-fetched row matters more than
 * perceived latency, so each just invalidates the list on success. */
export function useCreateChallenge() {
  const { token } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: ChallengeInput) => createChallenge(token as string, input),
    onSuccess: () => {
      toast.success("Challenge created.");
      void queryClient.invalidateQueries({ queryKey: ADMIN_CHALLENGES_KEY });
    },
    onError: (error) => {
      toast.error(mutationErrorMessage(error, "Couldn't create challenge. Please try again."));
    },
  });
}

export function useUpdateChallenge() {
  const { token } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: ChallengeUpdateInput }) =>
      updateChallenge(token as string, id, input),
    onSuccess: () => {
      toast.success("Challenge updated.");
      void queryClient.invalidateQueries({ queryKey: ADMIN_CHALLENGES_KEY });
    },
    onError: (error) => {
      toast.error(mutationErrorMessage(error, "Couldn't update challenge. Please try again."));
    },
  });
}

export function useArchiveChallenge() {
  const { token } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => archiveChallenge(token as string, id),
    onSuccess: () => {
      toast.success("Challenge archived.");
      void queryClient.invalidateQueries({ queryKey: ADMIN_CHALLENGES_KEY });
    },
    onError: (error) => {
      toast.error(mutationErrorMessage(error, "Couldn't archive challenge. Please try again."));
    },
  });
}
