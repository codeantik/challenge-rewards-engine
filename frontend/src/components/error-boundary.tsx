"use client";

import { Component, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  /** Custom fallback; receives a `reset` callback that re-mounts `children`. */
  fallback?: (reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

/** Catches render-time crashes (e.g. a bad chart dataset in Phase 8) that a
 * query's own `isError` state can't — TanStack Query surfaces *fetch*
 * failures, not exceptions thrown while rendering. React only supports this
 * via a class component; there is no hooks equivalent. Every fetch surface
 * gets one of these per CLAUDE.md's "visible retry fallback" requirement. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("ErrorBoundary caught a render error:", error);
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.reset);
      }
      return (
        <div className="border-destructive/30 bg-destructive/5 flex flex-col items-center gap-2 rounded-lg border p-4 text-center text-sm">
          <p className="text-destructive">Couldn&apos;t load this section.</p>
          <Button size="sm" variant="outline" onClick={this.reset}>
            Retry
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
