import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertCircle, RotateCcw, Copy, Check, ShieldAlert } from "lucide-react";
import { Button } from "./Button";

interface BaseErrorBoundaryProps {
  children?: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  context?: string;
  metadata?: Record<string, unknown>;
}

interface BaseErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  copied: boolean;
}

/**
 * RouteErrorBoundary — Catches full-page errors while preserving global shell / navigation.
 */
export class RouteErrorBoundary extends Component<BaseErrorBoundaryProps, BaseErrorBoundaryState> {
  public state: BaseErrorBoundaryState = {
    hasError: false,
    error: null,
    errorInfo: null,
    copied: false,
  };

  public static getDerivedStateFromError(error: Error): Partial<BaseErrorBoundaryState> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    console.error(`[RouteErrorBoundary] Error in ${this.props.context || "route"}:`, error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  private handleCopy = () => {
    const payload = {
      context: this.props.context || "route",
      error: this.state.error?.message,
      stack: this.state.error?.stack,
      componentStack: this.state.errorInfo?.componentStack,
      metadata: this.props.metadata,
      timestamp: new Date().toISOString(),
    };
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    this.setState({ copied: true });
    setTimeout(() => this.setState({ copied: false }), 2000);
  };

  private handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="max-w-3xl mx-auto my-12 p-6 rounded-xl border border-rose-500/30 bg-surface-1 shadow-lg space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-rose-500/10 text-rose-500">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-bold text-text-primary">Something went wrong rendering this view</h2>
              <p className="text-xs text-text-muted">
                {this.props.context ? `Location: ${this.props.context}` : "An unexpected UI error occurred."}
              </p>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-surface-2 font-mono text-xs text-rose-400 border border-border-subtle max-h-48 overflow-y-auto whitespace-pre-wrap">
            {this.state.error?.message || "Unknown error"}
          </div>

          <div className="flex items-center gap-2 pt-2">
            <Button variant="primary" size="sm" onClick={this.handleReset} className="gap-1.5">
              <RotateCcw className="w-3.5 h-3.5" /> Reload View
            </Button>
            <Button variant="secondary" size="sm" onClick={this.handleCopy} className="gap-1.5 font-mono text-xs">
              {this.state.copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
              {this.state.copied ? "Copied" : "Copy Details"}
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

/**
 * SectionErrorBoundary — Catches panel-level failures and keeps adjacent panels alive.
 */
export class SectionErrorBoundary extends Component<BaseErrorBoundaryProps, BaseErrorBoundaryState> {
  public state: BaseErrorBoundaryState = {
    hasError: false,
    error: null,
    errorInfo: null,
    copied: false,
  };

  public static getDerivedStateFromError(error: Error): Partial<BaseErrorBoundaryState> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    console.error(`[SectionErrorBoundary] Error in ${this.props.context || "section"}:`, error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  private handleCopy = () => {
    const payload = {
      context: this.props.context || "section",
      error: this.state.error?.message,
      componentStack: this.state.errorInfo?.componentStack,
      metadata: this.props.metadata,
    };
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    this.setState({ copied: true });
    setTimeout(() => this.setState({ copied: false }), 2000);
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="p-4 rounded-lg border border-rose-500/20 bg-rose-500/5 text-xs text-text-secondary space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-rose-500 flex items-center gap-1.5">
              <AlertCircle className="w-4 h-4 shrink-0" />
              Failed to load section: {this.props.context || "panel"}
            </span>
            <button
              onClick={this.handleCopy}
              className="text-[11px] font-mono text-text-muted hover:text-text-primary flex items-center gap-1"
            >
              {this.state.copied ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
              {this.state.copied ? "Copied" : "Copy details"}
            </button>
          </div>
          <p className="text-[11px] text-text-muted font-mono truncate">
            {this.state.error?.message}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

/**
 * RowErrorBoundary — Catches single lead row failures and renders a graceful degraded row.
 */
interface RowErrorBoundaryProps {
  children: ReactNode;
  lead: any;
  isSelected?: boolean;
  style?: React.CSSProperties;
  onSelectLead?: (lead: any) => void;
}

export class RowErrorBoundary extends Component<RowErrorBoundaryProps, BaseErrorBoundaryState> {
  public state: BaseErrorBoundaryState = {
    hasError: false,
    error: null,
    errorInfo: null,
    copied: false,
  };

  public static getDerivedStateFromError(error: Error): Partial<BaseErrorBoundaryState> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    console.error(`[RowErrorBoundary] Error in lead row ${this.props.lead?.id || "unknown"}:`, error, errorInfo);
  }

  private handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(JSON.stringify(this.props.lead, null, 2));
    this.setState({ copied: true });
    setTimeout(() => this.setState({ copied: false }), 2000);
  };

  public render() {
    if (this.state.hasError) {
      const { lead, isSelected, style, onSelectLead } = this.props;
      const name = lead?.canonical_name || lead?.name || "Lead";
      const phone = lead?.phones_e164?.[0] || lead?.phone_primary || "—";
      const locality = lead?.locality || lead?.address_text || "—";

      return (
        <div
          data-testid="lead-row"
          style={style}
          onClick={() => onSelectLead?.(lead)}
          className={`flex items-center justify-between px-3 py-2 border-b border-border-subtle bg-rose-500/5 hover:bg-rose-500/10 transition-colors text-xs font-mono cursor-pointer ${
            isSelected ? "ring-1 ring-accent" : ""
          }`}
          role="row"
        >
          <div className="flex items-center gap-3 truncate min-w-0">
            <span data-testid="lead-name" className="font-semibold text-text-primary truncate">{name}</span>
            <span className="text-text-muted truncate">({locality})</span>
            <span data-testid="lead-contact" className="text-text-secondary truncate">{phone}</span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className="text-[10px] text-amber-500/90 font-sans">Some details couldn't be displayed</span>
            <button
              onClick={this.handleCopy}
              className="text-[10px] px-2 py-0.5 rounded bg-surface-2 hover:bg-surface-3 text-text-primary border border-border-subtle flex items-center gap-1 font-mono transition-colors"
              title="Copy raw JSON"
            >
              {this.state.copied ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
              {this.state.copied ? "Copied" : "Copy JSON"}
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
