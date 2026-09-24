import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, vi } from "vitest";
import { server } from "./msw/server";

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());

// FAIL ANY TEST THAT LOGS A REACT ERROR OR WARNING.
// This is what would have caught "Objects are not valid as a React child".
let consoleErrors: string[] = [];
beforeEach(() => {
  consoleErrors = [];
  vi.spyOn(console, "error").mockImplementation((...args) => {
    consoleErrors.push(args.map(a => (typeof a === "object" ? JSON.stringify(a) : String(a))).join(" "));
  });
  vi.spyOn(console, "warn").mockImplementation((...args) => {
    consoleErrors.push(args.map(a => (typeof a === "object" ? JSON.stringify(a) : String(a))).join(" "));
  });
});
afterEach(() => {
  const real = consoleErrors.filter(
    (e) =>
      !e.includes("not wrapped in act") &&
      !e.includes("inside a test was not wrapped in act") &&
      !e.includes("unhandled request") &&
      !e.includes("MSW") &&
      !e.includes("width(0) and height(0) of chart")
  );
  if (real.length) {
    throw new Error(`React logged ${real.length} error(s):\n${real.join("\n---\n")}`);
  }
});

// MapLibre needs stubs in jsdom
vi.mock("maplibre-gl", () => {
  const mockMap = vi.fn(() => ({
    on: vi.fn(),
    remove: vi.fn(),
    addSource: vi.fn(),
    addLayer: vi.fn(),
    fitBounds: vi.fn(),
    getSource: vi.fn(),
    flyTo: vi.fn(),
    addControl: vi.fn(),
  }));
  const mockMarker = vi.fn(() => ({
    setLngLat: vi.fn().mockReturnThis(),
    addTo: vi.fn().mockReturnThis(),
    remove: vi.fn(),
  }));
  return {
    default: {
      Map: mockMap,
      NavigationControl: vi.fn(),
      ScaleControl: vi.fn(),
      Marker: mockMarker,
    },
    Map: mockMap,
    NavigationControl: vi.fn(),
    ScaleControl: vi.fn(),
    Marker: mockMarker,
  };
});

// ResizeObserver mock
global.ResizeObserver = class {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
} as any;

// matchMedia mock
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// EventSource mock
global.EventSource = class {
  close = vi.fn();
  addEventListener = vi.fn();
  removeEventListener = vi.fn();
  onmessage = vi.fn();
  onerror = vi.fn();
  onopen = vi.fn();
} as any;
