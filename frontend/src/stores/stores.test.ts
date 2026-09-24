import { describe, it, expect } from "vitest";
import { useScrapeDraft } from "./useScrapeDraft";
import { useRunTracker } from "./useRunTracker";
import { useUiPrefs } from "./useUiPrefs";

describe("State Stores", () => {
  it("manages all scrape draft actions", () => {
    const draft = useScrapeDraft.getState();
    draft.setNaturalQuery("find temples");
    expect(useScrapeDraft.getState().naturalQuery).toBe("find temples");

    draft.setIsNaturalMode(true);
    expect(useScrapeDraft.getState().isNaturalMode).toBe(true);

    draft.setLocationField("locality", "Koramangala");
    expect(useScrapeDraft.getState().location.locality).toBe("Koramangala");

    draft.addKeyword("organic grocery");
    expect(useScrapeDraft.getState().keywords).toContain("organic grocery");

    draft.removeKeyword("organic grocery");
    expect(useScrapeDraft.getState().keywords).not.toContain("organic grocery");

    draft.setKeywords(["ayurveda", "pooja"]);
    expect(useScrapeDraft.getState().keywords).toEqual(["ayurveda", "pooja"]);

    draft.addExcludeKeyword("wholesale");
    expect(useScrapeDraft.getState().excludeKeywords).toContain("wholesale");

    draft.removeExcludeKeyword("wholesale");
    expect(useScrapeDraft.getState().excludeKeywords).not.toContain("wholesale");

    draft.setExcludeKeywords(["distributor"]);
    expect(useScrapeDraft.getState().excludeKeywords).toEqual(["distributor"]);

    draft.setMaxResults(50);
    expect(useScrapeDraft.getState().maxResults).toBe(50);

    draft.setMinConfidence(0.8);
    expect(useScrapeDraft.getState().minConfidence).toBe(0.8);

    draft.setEnrichWebsites(true);
    expect(useScrapeDraft.getState().enrichWebsites).toBe(true);

    draft.setSources(["overture"]);
    expect(useScrapeDraft.getState().sources).toEqual(["overture"]);

    draft.setCachePolicy("prefer_cache");
    expect(useScrapeDraft.getState().cachePolicy).toBe("prefer_cache");

    draft.setMaxCacheAgeDays(7);
    expect(useScrapeDraft.getState().maxCacheAgeDays).toBe(7);

    draft.setDraftFromRun({ location: { city: "Mysuru" }, keywords: ["silk"], maxResults: 20 });
    expect(useScrapeDraft.getState().location.city).toBe("Mysuru");
    expect(useScrapeDraft.getState().keywords).toEqual(["silk"]);

    draft.resetDraft();
  });

  it("manages run tracker state", () => {
    const tracker = useRunTracker.getState();
    tracker.trackRun("run-123", "pooja store", "HSR Layout");
    expect(useRunTracker.getState().activeRuns["run-123"]).toBeDefined();
    expect(useRunTracker.getState().getActiveCount()).toBe(1);

    tracker.updateRunProgress("run-123", { leadsFound: 10, currentNode: "n3a_overture" });
    expect(useRunTracker.getState().activeRuns["run-123"].leadsFound).toBe(10);
    expect(useRunTracker.getState().activeRuns["run-123"].currentNode).toBe("n3a_overture");

    tracker.markRunFinished("run-123", "completed");
    expect(useRunTracker.getState().getActiveCount()).toBe(0);

    tracker.clearRun("run-123");
    expect(useRunTracker.getState().activeRuns["run-123"]).toBeUndefined();
  });

  it("manages UI preferences", () => {
    const prefs = useUiPrefs.getState();
    prefs.setTheme("light");
    expect(useUiPrefs.getState().theme).toBe("light");

    prefs.setDensity("compact");
    expect(useUiPrefs.getState().density).toBe("compact");
  });
});
