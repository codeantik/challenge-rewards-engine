"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";

/** Second gate stacked on top of `(app)/layout.tsx`'s auth check: that one
 * only proves the caller is logged in, so a plain `user` hitting `/admin/*`
 * needs to be bounced separately. Mirrors the same
 * skeleton-while-unknown/redirect-once-known shape. */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { status, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated" && user?.role !== "admin") {
      router.replace("/feed");
    }
  }, [status, user, router]);

  if (status !== "authenticated" || user?.role !== "admin") {
    return (
      <div className="flex flex-1 items-center justify-center p-16">
        <Skeleton className="h-8 w-48" />
      </div>
    );
  }

  return <>{children}</>;
}
