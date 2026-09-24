import React from "react";
import { cn } from "../../lib/cn";
import { AlertTriangle, RefreshCw, FolderSearch } from "lucide-react";
import { Button } from "./Button";

export function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
  icon,
  className,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center p-8 text-center rounded-lg border border-dashed border-border-strong bg-surface-1/50", className)}>
      <div className="w-12 h-12 rounded-full bg-surface-2 flex items-center justify-center text-text-muted mb-4">
        {icon || <FolderSearch className="w-6 h-6" />}
      </div>
      <h3 className="text-base font-semibold text-text-primary mb-1">{title}</h3>
      <p className="text-sm text-text-muted max-w-md mb-4">{description}</p>
      {actionLabel && onAction && (
        <Button variant="primary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

export function ErrorState({
  title = "Failed to load data",
  error,
  onRetry,
  className,
}: {
  title?: string;
  error?: string | Error;
  onRetry?: () => void;
  className?: string;
}) {
  const message = typeof error === "string" ? error : error?.message || "An unexpected error occurred.";

  return (
    <div className={cn("p-6 rounded-lg border border-status-critical/30 bg-status-critical/5 text-center flex flex-col items-center justify-center", className)}>
      <div className="w-10 h-10 rounded-full bg-status-critical/10 flex items-center justify-center text-status-critical mb-3">
        <AlertTriangle className="w-5 h-5" />
      </div>
      <h4 className="text-sm font-semibold text-text-primary mb-1">{title}</h4>
      <p className="text-xs text-text-muted max-w-md mb-4 font-mono bg-surface-1 px-3 py-1.5 rounded border border-border-subtle">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="gap-1.5">
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </Button>
      )}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded bg-surface-2", className)} />
  );
}
