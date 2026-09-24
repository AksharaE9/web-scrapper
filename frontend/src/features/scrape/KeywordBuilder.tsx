import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { qk } from "../../lib/queryKeys";
import { useScrapeDraft } from "../../stores/useScrapeDraft";
import { ConceptPreviewPopover } from "./ConceptPreviewPopover";
import { X, Tag, Ban, Sparkles, HelpCircle } from "lucide-react";

export const KeywordBuilder: React.FC = () => {
  const {
    keywords,
    excludeKeywords,
    addKeyword,
    removeKeyword,
    addExcludeKeyword,
    removeExcludeKeyword,
    setKeywords,
    setExcludeKeywords,
  } = useScrapeDraft();

  const [kwInput, setKwInput] = useState("");
  const [exInput, setExInput] = useState("");
  const [hoveredConcept, setHoveredConcept] = useState<string | null>(null);

  const { data: presets } = useQuery({
    queryKey: qk.presets,
    queryFn: () => api.listPresets(),
  });

  const handleKwKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      if (kwInput.trim()) {
        addKeyword(kwInput);
        setKwInput("");
      }
    } else if (e.key === "Backspace" && !kwInput && keywords.length > 0) {
      removeKeyword(keywords[keywords.length - 1]);
    }
  };

  const handleExKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      if (exInput.trim()) {
        addExcludeKeyword(exInput);
        setExInput("");
      }
    } else if (e.key === "Backspace" && !exInput && excludeKeywords.length > 0) {
      removeExcludeKeyword(excludeKeywords[excludeKeywords.length - 1]);
    }
  };

  return (
    <div className="p-4 rounded-lg border border-border-subtle bg-surface-1 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-accent/10 text-accent flex items-center justify-center font-bold text-xs">
            2
          </div>
          <h3 className="text-sm font-semibold text-text-primary">What — Target Keywords & Exclusions</h3>
        </div>

        {/* Presets quick loader */}
        {presets && presets.length > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-text-secondary">
            <Sparkles className="w-3.5 h-3.5 text-accent" />
            <span className="hidden sm:inline">Preset:</span>
            <select
              className="bg-surface-2 border border-border-subtle text-text-primary rounded px-2 py-0.5 text-xs"
              onChange={(e) => {
                const p = presets.find((pr) => pr.id === e.target.value);
                if (p) {
                  setKeywords(p.search_categories);
                  setExcludeKeywords(p.exclude_keywords || []);
                }
              }}
              defaultValue=""
            >
              <option key="preset-default" value="" disabled>Select Preset...</option>
              {presets.map((p, idx) => (
                <option key={p.id || `preset-${idx}`} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Target Keywords Input */}
      <div>
        <label className="text-xs font-medium text-text-secondary block mb-1.5">
          Target Keywords (Press Enter or Comma to add)
        </label>
        <div className="flex flex-wrap gap-1.5 p-2 rounded-md border border-border-strong bg-surface-1 min-h-[42px] items-center">
          {keywords.map((kw) => (
            <div
              key={kw}
              data-testid="keyword-chip"
              className="relative group inline-flex items-center gap-1 px-2.5 py-1 rounded bg-accent/10 text-accent border border-accent/20 text-xs font-medium"
            >
              <Tag className="w-3 h-3" />
              <span>{kw}</span>
              <button
                type="button"
                onClick={() => setHoveredConcept(hoveredConcept === kw ? null : kw)}
                className="opacity-60 hover:opacity-100 transition-opacity ml-0.5 cursor-pointer"
                title="View Concept Card"
              >
                <HelpCircle className="w-3 h-3" />
              </button>
              <button
                type="button"
                onClick={() => removeKeyword(kw)}
                className="opacity-60 hover:opacity-100 transition-opacity ml-1 cursor-pointer"
              >
                <X className="w-3 h-3" />
              </button>

              {/* Concept popover on click */}
              {hoveredConcept === kw && (
                <div className="absolute left-0 top-full mt-2 z-50 bg-surface-1 rounded-lg border border-border-strong shadow-2xl">
                  <ConceptPreviewPopover keyword={kw} />
                </div>
              )}
            </div>
          ))}
          <input
            id="keyword-input"
            value={kwInput}
            onChange={(e) => setKwInput(e.target.value)}
            onKeyDown={handleKwKeyDown}
            placeholder={keywords.length === 0 ? "Add target keyword (e.g. pooja store)..." : "Add keyword..."}
            className="flex-1 min-w-[120px] bg-transparent border-none outline-none text-xs text-text-primary placeholder:text-text-muted"
          />
        </div>
      </div>

      {/* Exclude Keywords Input */}
      <div>
        <label className="text-xs font-medium text-text-secondary block mb-1.5">
          Exclude Keywords (Negative Veto Filter)
        </label>
        <div className="flex flex-wrap gap-1.5 p-2 rounded-md border border-border-subtle bg-surface-2/40 min-h-[42px] items-center">
          {excludeKeywords.map((ex) => (
            <div
              key={ex}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 text-xs font-medium"
            >
              <Ban className="w-3 h-3" />
              <span>{ex}</span>
              <button
                type="button"
                onClick={() => removeExcludeKeyword(ex)}
                className="opacity-60 hover:opacity-100 transition-opacity ml-1 cursor-pointer"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
          <input
            value={exInput}
            onChange={(e) => setExInput(e.target.value)}
            onKeyDown={handleExKeyDown}
            placeholder={excludeKeywords.length === 0 ? "e.g. footwear, taxi, salon..." : "Add exclude..."}
            className="flex-1 min-w-[120px] bg-transparent border-none outline-none text-xs text-text-primary placeholder:text-text-muted"
          />
        </div>
      </div>
    </div>
  );
};
