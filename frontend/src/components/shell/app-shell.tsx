import type { ReactNode } from "react";

import { AuroraBackground } from "@/components/aurora-background";
import { Sidebar } from "@/components/shell/sidebar";
import { WeeklyChallengeWidget } from "@/components/weekly-challenge-widget";

/** Shell A: left sidebar · feed/content · right rail. Mounted once by the
 * `(app)` route group layout so every authenticated page gets the same nav
 * and the same live-polling weekly widget for free — on *every* viewport:
 * the rail is `lg:`+ only, so below that breakpoint the same widget renders
 * inline above the page content instead (both mounted, CSS picks one — the
 * `useWeeklyChallenge` query is shared by key, so this isn't a double
 * fetch). Without this, the widget silently disappeared below 1024px with
 * no fallback, which fails the "present on all 5 pages" requirement on any
 * laptop-width or narrower window. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="brand-glow relative flex flex-1 justify-center overflow-hidden">
      <AuroraBackground intensity={0.22} />
      <div className="relative mx-auto flex w-full max-w-6xl flex-1">
        <Sidebar />
        <main className="border-border min-w-0 flex-1 border-r p-4 sm:p-6">
          <div className="mb-4 lg:hidden">
            <WeeklyChallengeWidget />
          </div>
          {children}
        </main>
        <aside className="hidden w-72 shrink-0 flex-col gap-4 p-6 lg:flex">
          <WeeklyChallengeWidget />
        </aside>
      </div>
    </div>
  );
}
