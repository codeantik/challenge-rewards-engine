import type { ReactNode } from "react";

import { Sidebar } from "@/components/shell/sidebar";
import { WeeklyChallengeWidget } from "@/components/weekly-challenge-widget";

/** Shell A: left sidebar · feed/content · right rail. Mounted once by the
 * `(app)` route group layout so every authenticated page gets the same nav
 * and the same live-polling weekly widget for free. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1">
      <Sidebar />
      <main className="border-border min-w-0 flex-1 border-r p-6">{children}</main>
      <aside className="hidden w-72 shrink-0 flex-col gap-4 p-6 lg:flex">
        <WeeklyChallengeWidget />
      </aside>
    </div>
  );
}
