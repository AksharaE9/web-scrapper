import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { useUiPrefs } from "../stores/useUiPrefs";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30000,
      refetchOnWindowFocus: false,
    },
  },
});

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Uncaught frontend error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-surface-base text-text-primary">
          <div className="max-w-md w-full p-6 rounded-lg border border-border-strong bg-surface-1 shadow-lg text-center">
            <h2 className="text-lg font-bold text-status-critical mb-2">Application Error</h2>
            <p className="text-sm text-text-secondary mb-4">
              A rendering error occurred in the workspace.
            </p>
            <pre className="p-3 bg-surface-2 rounded text-xs font-mono text-left overflow-auto mb-4 border border-border-subtle max-h-40">
              {this.state.error?.message}
            </pre>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-accent text-white rounded font-medium hover:bg-accent-hover transition-colors"
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export function AppProviders({ children }: { children: React.ReactNode }) {
  const theme = useUiPrefs((s) => s.theme);

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster
          theme={theme === "system" ? undefined : theme}
          position="top-right"
          richColors
          closeButton
        />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
