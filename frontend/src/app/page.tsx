import { HealthCheck } from "@/components/health-check";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 bg-zinc-50 p-16 font-sans dark:bg-black">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Challenge &amp; Rewards Engine</h1>
        <p className="max-w-md text-sm text-zinc-600 dark:text-zinc-400">
          Phase 0 placeholder — confirms Next.js, Tailwind, shadcn/ui, and TanStack Query are wired
          together. See <code>CLAUDE.md</code> and <code>plan.md</code> for what comes next.
        </p>
      </div>
      <HealthCheck />
    </main>
  );
}
