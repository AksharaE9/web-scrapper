import { create } from "zustand";
import { persist } from "zustand/middleware";
import { LocationQuery } from "../types";

interface ScrapeDraftState {
  naturalQuery: string;
  isNaturalMode: boolean;
  location: LocationQuery;
  keywords: string[];
  excludeKeywords: string[];
  maxResults: number;
  minConfidence: number;
  enrichWebsites: boolean;
  sources: string[];
  cachePolicy: "auto" | "prefer_cache" | "force_fresh";
  maxCacheAgeDays: number;
  
  // Actions
  setNaturalQuery: (q: string) => void;
  setIsNaturalMode: (m: boolean) => void;
  setLocationField: (field: keyof LocationQuery, val: string) => void;
  addKeyword: (kw: string) => void;
  removeKeyword: (kw: string) => void;
  setKeywords: (kws: string[]) => void;
  addExcludeKeyword: (kw: string) => void;
  removeExcludeKeyword: (kw: string) => void;
  setExcludeKeywords: (kws: string[]) => void;
  setMaxResults: (n: number) => void;
  setMinConfidence: (c: number) => void;
  setEnrichWebsites: (e: boolean) => void;
  setSources: (srcs: string[]) => void;
  setCachePolicy: (p: "auto" | "prefer_cache" | "force_fresh") => void;
  setMaxCacheAgeDays: (days: number) => void;
  setDraftFromRun: (runData: { location?: Partial<LocationQuery>; keywords?: string[]; maxResults?: number }) => void;
  resetDraft: () => void;
}

const DEFAULT_DRAFT = {
  naturalQuery: "",
  isNaturalMode: false,
  location: {
    locality: "Whitefield",
    city: "Bengaluru",
    state: "Karnataka",
    country: "India",
  },
  keywords: ["pooja store"],
  excludeKeywords: [],
  maxResults: 100,
  minConfidence: 0.5,
  enrichWebsites: false,
  sources: ["overture", "osm"],
  cachePolicy: "force_fresh" as const,
  maxCacheAgeDays: 0,
};

export const useScrapeDraft = create<ScrapeDraftState>()(
  persist(
    (set) => ({
      ...DEFAULT_DRAFT,
      setNaturalQuery: (naturalQuery) => set({ naturalQuery }),
      setIsNaturalMode: (isNaturalMode) => set({ isNaturalMode }),
      setLocationField: (field, val) =>
        set((s) => ({ location: { ...s.location, [field]: val } })),
      addKeyword: (kw) =>
        set((s) => {
          const clean = kw.trim();
          if (!clean || s.keywords.includes(clean)) return s;
          return { keywords: [...s.keywords, clean] };
        }),
      removeKeyword: (kw) =>
        set((s) => ({ keywords: s.keywords.filter((k) => k !== kw) })),
      setKeywords: (keywords) => set({ keywords }),
      addExcludeKeyword: (kw) =>
        set((s) => {
          const clean = kw.trim();
          if (!clean || s.excludeKeywords.includes(clean)) return s;
          return { excludeKeywords: [...s.excludeKeywords, clean] };
        }),
      removeExcludeKeyword: (kw) =>
        set((s) => ({ excludeKeywords: s.excludeKeywords.filter((k) => k !== kw) })),
      setExcludeKeywords: (excludeKeywords) => set({ excludeKeywords }),
      setMaxResults: (maxResults) => set({ maxResults }),
      setMinConfidence: (minConfidence) => set({ minConfidence }),
      setEnrichWebsites: (enrichWebsites) => set({ enrichWebsites }),
      setSources: (sources) => set({ sources }),
      setCachePolicy: (cachePolicy) => set({ cachePolicy }),
      setMaxCacheAgeDays: (maxCacheAgeDays) => set({ maxCacheAgeDays }),
      setDraftFromRun: (runData) =>
        set((s) => ({
          location: {
            ...s.location,
            ...(runData.location || {}),
          },
          keywords: runData.keywords?.length ? runData.keywords : s.keywords,
          maxResults: runData.maxResults || s.maxResults,
          isNaturalMode: false,
        })),
      resetDraft: () => set(DEFAULT_DRAFT),
    }),
    {
      name: "leadcore_scrape_draft",
    }
  )
);

