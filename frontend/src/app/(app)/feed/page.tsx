"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2Icon, MessageSquareIcon, EyeIcon, PlusIcon, InboxIcon } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/error-boundary";
import { Skeleton } from "@/components/ui/skeleton";
import { useFeedParams } from "@/hooks/use-feed-params";
import { useAuth } from "@/lib/auth-context";
import { fetchPosts, type SortOption } from "@/lib/posts-api";
import { cn, formatRelativeTime } from "@/lib/utils";

const SORT_TABS: { value: SortOption; label: string }[] = [
  { value: "latest", label: "Latest" },
  { value: "trending", label: "Trending" },
];

function FeedSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: 5 }, (_, i) => (
        <Card key={i}>
          <CardContent className="flex flex-col gap-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3.5 w-full" />
            <Skeleton className="h-3.5 w-1/3" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function FeedContent() {
  const { token } = useAuth();
  const { sort, page, setSort, setPage } = useFeedParams();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["posts", "list", { sort, page }],
    queryFn: () => fetchPosts(token as string, { sort, page }),
    enabled: token !== null,
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Feed</h1>
        <Link href="/posts/new" className={cn(buttonVariants({ variant: "default" }), "gap-1.5")}>
          <PlusIcon className="size-4" />
          New post
        </Link>
      </div>

      <div className="bg-muted inline-flex w-fit gap-0.5 rounded-lg p-0.5">
        {SORT_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setSort(tab.value)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-all",
              sort === tab.value
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <FeedSkeleton />
      ) : isError ? (
        <div className="border-destructive/30 bg-destructive/5 flex flex-col items-center gap-2 rounded-lg border p-6 text-center text-sm">
          <p className="text-destructive">Couldn&apos;t load the feed.</p>
          <Button size="sm" variant="outline" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : !data || data.posts.length === 0 ? (
        <div className="text-muted-foreground flex flex-col items-center gap-2 rounded-xl border border-dashed p-12 text-center text-sm">
          <InboxIcon className="text-muted-foreground/50 size-8" />
          No posts yet — be the first to post.
        </div>
      ) : (
        <div className="animate-in fade-in flex flex-col gap-3 duration-300">
          {data.posts.map((post) => (
            <Card key={post.id} className="card-hover">
              <CardContent className="flex flex-col gap-1.5">
                <div className="flex items-start justify-between gap-2">
                  <Link
                    href={`/posts/${post.id}`}
                    className="hover:text-primary truncate font-medium transition-colors"
                  >
                    {post.title}
                  </Link>
                  {post.solution_comment_id && (
                    <Badge variant="secondary" className="bg-success/10 text-success gap-1 shrink-0">
                      <CheckCircle2Icon className="size-3" />
                      Solved
                    </Badge>
                  )}
                </div>
                <p className="text-muted-foreground line-clamp-2 text-sm">{post.body}</p>
                <p className="text-muted-foreground flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1">
                    <MessageSquareIcon className="size-3" />
                    {post.comment_count}
                  </span>
                  <span className="flex items-center gap-1">
                    <EyeIcon className="size-3" />
                    {post.view_count}
                  </span>
                  <span>{formatRelativeTime(post.created_at)}</span>
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {data && data.meta.total_pages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <Button
            size="sm"
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
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
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

export default function FeedPage() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<FeedSkeleton />}>
        <FeedContent />
      </Suspense>
    </ErrorBoundary>
  );
}
