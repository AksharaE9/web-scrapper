import { renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { useConcept } from "./useConcept";
import { createWrapper } from "../test/utils";

describe("useConcept", () => {
  it("fetches concept card", async () => {
    const { result } = renderHook(() => useConcept("pooja store"), {
      wrapper: createWrapper(),
    });

    expect(result.current).toBeDefined();
  });
});
