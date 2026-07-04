"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/shell/app-shell";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";

/** Gate for every authenticated route. The JWT lives in `localStorage`
 * (there's no cookie for Next middleware to read on the edge), so the
 * auth check is client-side: render a skeleton until `AuthProvider` has
 * read storage, then bounce to `/login` if there's no session. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status !== "authenticated") {
    return (
      <div className="flex flex-1 items-center justify-center p-16">
        <Skeleton className="h-8 w-48" />
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
