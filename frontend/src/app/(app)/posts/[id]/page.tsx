"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2Icon, EyeIcon, MessageSquareIcon, SendIcon } from "lucide-react";
import { type FormEvent, use, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import {
  type CommentOut,
  createComment,
  fetchPost,
  markSolution,
  type PostDetail,
} from "@/lib/posts-api";
import { cn, formatRelativeTime } from "@/lib/utils";

interface PostDetailPageProps {
  params: Promise<{ id: string }>;
}

function PostDetailSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-6 w-1/2" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

function CommentRow({
  comment,
  isPostOwner,
  isSolution,
  onMarkSolution,
  isMarking,
}: {
  comment: CommentOut;
  isPostOwner: boolean;
  isSolution: boolean;
  onMarkSolution: () => void;
  isMarking: boolean;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <Card className={cn(isSolution && "bg-success/5 ring-success/30 ring-2")}>
      <CardContent className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground text-xs">
            {formatRelativeTime(comment.created_at)}
          </span>
          {isSolution && (
            <Badge className="bg-success/15 text-success gap-1">
              <CheckCircle2Icon className="size-3" />
              Solution
            </Badge>
          )}
        </div>
        <p className="text-sm">{comment.body}</p>
        {isPostOwner && !isSolution && (
          <>
            <Button
              size="sm"
              variant="outline"
              className="self-start"
              disabled={isMarking}
              onClick={() => setConfirmOpen(true)}
            >
              Mark as solution
            </Button>
            <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Mark as solution?</DialogTitle>
                  <DialogDescription>
                    This flags the comment as the accepted answer for this post. You can only
                    have one solution per post.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setConfirmOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      onMarkSolution();
                      setConfirmOpen(false);
                    }}
                  >
                    Mark as solution
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function PostDetailContent({ id }: { id: string }) {
  const { token, user } = useAuth();
  const queryClient = useQueryClient();
  const [commentBody, setCommentBody] = useState("");
  const detailKey = ["posts", "detail", id];

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: detailKey,
    queryFn: () => fetchPost(token as string, id),
    enabled: token !== null,
  });

  const commentMutation = useMutation({
    mutationFn: (body: string) => createComment(token as string, id, body),
    onMutate: async (body) => {
      await queryClient.cancelQueries({ queryKey: detailKey });
      const previous = queryClient.getQueryData<PostDetail>(detailKey);

      const optimisticComment: CommentOut = {
        id: `optimistic-${crypto.randomUUID()}`,
        post_id: id,
        author_id: user?.id ?? "",
        body,
        created_at: new Date().toISOString(),
      };

      queryClient.setQueryData<PostDetail>(detailKey, (current) =>
        current
          ? {
              ...current,
              comments: [...current.comments, optimisticComment],
              comment_count: current.comment_count + 1,
            }
          : current,
      );

      return { previous };
    },
    onError: (error, _body, context) => {
      queryClient.setQueryData(detailKey, context?.previous);
      toast.error(
        error instanceof ApiError ? error.message : "Couldn't post comment. Please try again.",
      );
    },
    onSuccess: () => {
      setCommentBody("");
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: detailKey });
    },
  });

  const markSolutionMutation = useMutation({
    mutationFn: (commentId: string) => markSolution(token as string, id, commentId),
    onMutate: async (commentId) => {
      await queryClient.cancelQueries({ queryKey: detailKey });
      const previous = queryClient.getQueryData<PostDetail>(detailKey);

      queryClient.setQueryData<PostDetail>(detailKey, (current) =>
        current ? { ...current, solution_comment_id: commentId } : current,
      );

      return { previous };
    },
    onError: (error, _commentId, context) => {
      queryClient.setQueryData(detailKey, context?.previous);
      toast.error(
        error instanceof ApiError ? error.message : "Couldn't mark solution. Please try again.",
      );
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: detailKey });
    },
  });

  function handleCommentSubmit(event: FormEvent) {
    event.preventDefault();
    if (!commentBody.trim()) return;
    commentMutation.mutate(commentBody);
  }

  if (isLoading) {
    return <PostDetailSkeleton />;
  }

  if (isError || !data) {
    return (
      <div className="border-destructive/30 bg-destructive/5 flex flex-col items-center gap-2 rounded-lg border p-6 text-center text-sm">
        <p className="text-destructive">Couldn&apos;t load this post.</p>
        <Button size="sm" variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  const isPostOwner = user?.id === data.author_id;

  return (
    <div className="animate-in fade-in flex flex-col gap-6 duration-300">
      <div className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <h1 className="text-xl font-semibold tracking-tight">{data.title}</h1>
          {data.solution_comment_id && (
            <Badge className="bg-success/15 text-success shrink-0 gap-1">
              <CheckCircle2Icon className="size-3" />
              Solved
            </Badge>
          )}
        </div>
        <p className="text-sm whitespace-pre-wrap">{data.body}</p>
        <p className="text-muted-foreground flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1">
            <MessageSquareIcon className="size-3" />
            {data.comment_count} comments
          </span>
          <span className="flex items-center gap-1">
            <EyeIcon className="size-3" />
            {data.view_count} views
          </span>
          <span>{formatRelativeTime(data.created_at)}</span>
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium">Comments</h2>
        {data.comments.length === 0 ? (
          <p className="text-muted-foreground text-sm">No comments yet.</p>
        ) : (
          data.comments.map((comment) => (
            <CommentRow
              key={comment.id}
              comment={comment}
              isPostOwner={isPostOwner}
              isSolution={comment.id === data.solution_comment_id}
              isMarking={markSolutionMutation.isPending}
              onMarkSolution={() => markSolutionMutation.mutate(comment.id)}
            />
          ))
        )}

        <form className="flex flex-col gap-2" onSubmit={handleCommentSubmit}>
          <Textarea
            placeholder="Add a comment..."
            rows={3}
            maxLength={5_000}
            value={commentBody}
            onChange={(event) => setCommentBody(event.target.value)}
          />
          <Button
            type="submit"
            size="sm"
            className="gap-1.5 self-start"
            disabled={commentMutation.isPending || !commentBody.trim()}
          >
            <SendIcon className="size-3.5" />
            {commentMutation.isPending ? "Posting..." : "Post comment"}
          </Button>
        </form>
      </div>
    </div>
  );
}

export default function PostDetailPage({ params }: PostDetailPageProps) {
  const { id } = use(params);
  return (
    <ErrorBoundary>
      <PostDetailContent id={id} />
    </ErrorBoundary>
  );
}
