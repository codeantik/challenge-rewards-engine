"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

import type { SortOption } from "@/lib/posts-api";

const DEFAULT_SORT: SortOption = "latest";
const DEFAULT_PAGE = 1;

/**
 * Single responsibility: keep the feed's `sort`/`page` filters synced with
 * the URL querystring instead of component state, so the feed is shareable
 * and a browser back/forward restores the exact view (CLAUDE.md/Phase 7
 * "Done when" criterion).
 */
export function useFeedParams() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const sort: SortOption = searchParams.get("sort") === "trending" ? "trending" : DEFAULT_SORT;
  const pageParam = Number(searchParams.get("page"));
  const page = Number.isFinite(pageParam) && pageParam >= 1 ? Math.floor(pageParam) : DEFAULT_PAGE;

  const push = useCallback(
    (next: { sort?: SortOption; page?: number }) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next.sort !== undefined) params.set("sort", next.sort);
      if (next.page !== undefined) params.set("page", String(next.page));
      router.push(`${pathname}?${params.toString()}`);
    },
    [pathname, router, searchParams],
  );

  const setSort = useCallback(
    (next: SortOption) => push({ sort: next, page: DEFAULT_PAGE }),
    [push],
  );
  const setPage = useCallback((next: number) => push({ page: next }), [push]);

  return { sort, page, setSort, setPage };
}
