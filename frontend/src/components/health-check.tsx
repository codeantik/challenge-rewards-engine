"use client";

import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { API_BASE_URL } from "@/lib/config";

interface HealthEnvelope {
  data: { status: string };
  meta: Record<string, unknown> | null;
}

async function fetchHealth(): Promise<HealthEnvelope> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`backend health check failed: ${response.status}`);
  }
  return (await response.json()) as HealthEnvelope;
}

export function HealthCheck() {
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: false,
  });

  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-zinc-200 p-6 text-center dark:border-zinc-800">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">Backend (`{API_BASE_URL}`)</p>
      {isLoading && <p className="text-sm">Checking...</p>}
      {error && (
        <p className="text-sm text-red-600 dark:text-red-400">
          Unreachable — is the backend running?
        </p>
      )}
      {data && (
        <p className="text-sm font-medium text-green-600 dark:text-green-400">{data.data.status}</p>
      )}
      <Button size="sm" variant="outline" onClick={() => refetch()}>
        Re-check
      </Button>
    </div>
  );
}
