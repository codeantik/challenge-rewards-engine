"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { createPost, type PostListResult, type PostSummary } from "@/lib/posts-api";

/** Every newly-created post lands here: latest sort, first page — the view
 * a user is dropped into right after posting. */
const FEED_LANDING_KEY = ["posts", "list", { sort: "latest", page: 1 }] as const;

interface CreatePostInput {
  title: string;
  body: string;
}

interface MutationContext {
  previous: PostListResult | undefined;
}

/**
 * Single responsibility: create a post with an optimistic insert into the
 * feed's cache, real rollback on failure, and a toast either way — used by
 * the create-post form. Navigating to `/feed` happens immediately (before
 * the request resolves) so the optimistic post is visible right away; a
 * failure removes it again in front of the user rather than silently
 * reverting off-screen.
 */
export function useCreatePost() {
  const { token, user } = useAuth();
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: (input: CreatePostInput) => createPost(token as string, input),

    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: FEED_LANDING_KEY });
      const previous = queryClient.getQueryData<PostListResult>(FEED_LANDING_KEY);

      const optimisticPost: PostSummary = {
        id: `optimistic-${crypto.randomUUID()}`,
        author_id: user?.id ?? "",
        title: input.title,
        body: input.body,
        comment_count: 0,
        view_count: 0,
        solution_comment_id: null,
        created_at: new Date().toISOString(),
      };

      queryClient.setQueryData<PostListResult>(FEED_LANDING_KEY, (current) => {
        const base = current ?? {
          posts: [],
          meta: { page: 1, limit: 20, total: 0, total_pages: 1 },
        };
        return {
          posts: [optimisticPost, ...base.posts],
          meta: { ...base.meta, total: base.meta.total + 1 },
        };
      });

      router.push("/feed");
      return { previous } satisfies MutationContext;
    },

    onError: (error, _input, context) => {
      queryClient.setQueryData(FEED_LANDING_KEY, context?.previous);
      toast.error(
        error instanceof ApiError ? error.message : "Couldn't create post. Please try again.",
      );
    },

    onSuccess: () => {
      toast.success("Post published.");
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["posts", "list"] });
    },
  });
}
