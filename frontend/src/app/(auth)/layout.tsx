"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AuroraBackground } from "@/components/aurora-background";
import { useAuth } from "@/lib/auth-context";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/feed");
    }
  }, [status, router]);

  return (
    <div className="brand-glow relative flex flex-1 items-center justify-center overflow-hidden p-6">
      <AuroraBackground intensity={1} />
      <div className="relative flex w-full max-w-sm flex-col items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="brand-gradient-bg flex size-9 shrink-0 items-center justify-center rounded-xl text-base font-bold text-white shadow-sm">
            V
          </span>
          <span className="text-lg font-semibold tracking-tight">Vultr Community</span>
        </div>
        <div className="animate-in fade-in slide-in-from-bottom-2 w-full duration-300">
          {children}
        </div>
      </div>
    </div>
  );
}
