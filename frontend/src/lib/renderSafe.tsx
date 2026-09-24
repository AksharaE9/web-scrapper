import React, { Fragment } from "react";

/**
 * renderSafe — Safe dynamic React child rendering guard.
 * Prevents raw objects from crashing React with:
 * "Objects are not valid as a React child (found: object with keys {...})"
 *
 * In development: logs diagnostic error and displays a visible inline error marker.
 * In production: gracefully degrades (returns null or fallback) without unmounting the route.
 */
export function renderSafe(value: unknown, context: string = "unknown", fallback: React.ReactNode = null): React.ReactNode {
  if (value == null || value === false) {
    return fallback;
  }
  if (typeof value === "string" || typeof value === "number") {
    return value;
  }
  if (typeof value === "boolean") {
    return String(value);
  }
  if (React.isValidElement(value)) {
    return value;
  }
  if (Array.isArray(value)) {
    return (
      <Fragment>
        {value.map((v, i) => (
          <Fragment key={i}>{renderSafe(v, `${context}[${i}]`, fallback)}</Fragment>
        ))}
      </Fragment>
    );
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    // If it's a chip-like descriptor with a string label, extract the label safely
    if (typeof obj.label === "string") {
      return obj.label;
    }
    if (typeof obj.message === "string") {
      return obj.message;
    }
    if (typeof obj.name === "string") {
      return obj.name;
    }

    const keys = Object.keys(obj).join(", ");
    console.error(`[renderSafe] Object passed as child in <${context}>: {${keys}}`, value);

    if (import.meta.env?.DEV) {
      return (
        <span
          className="text-rose-500 bg-rose-500/10 border border-rose-500/30 px-1 py-0.5 rounded font-mono text-[10px]"
          title={`Object keys: {${keys}}`}
        >
          [render error: {context} ⟨{keys}⟩]
        </span>
      );
    }
    return fallback;
  }
  return String(value);
}
