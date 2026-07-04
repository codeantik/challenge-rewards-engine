"use client";

import { useQuery } from "@tanstack/react-query";
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
import { formatRelativeTime } from "@/lib/utils";

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
        <h1 className="text-lg font-semibold">Feed</h1>
        <Link href="/posts/new" className={buttonVariants({ variant: "default" })}>
          New post
        </Link>
      </div>

      <div className="flex gap-1">
        {SORT_TABS.map((tab) => (
          <Button
            key={tab.value}
            size="sm"
            variant={sort === tab.value ? "secondary" : "ghost"}
            onClick={() => setSort(tab.value)}
          >
            {tab.label}
          </Button>
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
        <p className="text-muted-foreground text-sm">No posts yet — be the first to post.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {data.posts.map((post) => (
            <Card key={post.id}>
              <CardContent className="flex flex-col gap-1.5">
                <div className="flex items-start justify-between gap-2">
                  <Link href={`/posts/${post.id}`} className="truncate font-medium hover:underline">
                    {post.title}
                  </Link>
                  {post.solution_comment_id && <Badge variant="secondary">Solved</Badge>}
                </div>
                <p className="text-muted-foreground line-clamp-2 text-sm">{post.body}</p>
                <p className="text-muted-foreground text-xs">
                  {post.comment_count} comments · {post.view_count} views ·{" "}
                  {formatRelativeTime(post.created_at)}
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
