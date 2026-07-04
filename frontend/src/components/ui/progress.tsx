import { cn } from "@/lib/utils";

function Progress({
  value,
  className,
  barClassName,
  complete,
}: {
  value: number;
  className?: string;
  barClassName?: string;
  complete?: boolean;
}) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div
      className={cn("bg-muted h-1.5 w-full overflow-hidden rounded-full", className)}
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn(
          "h-full rounded-full transition-all duration-500 ease-out",
          complete
            ? "bg-success"
            : "from-primary to-accent-cyan bg-gradient-to-r",
          barClassName,
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export { Progress };
