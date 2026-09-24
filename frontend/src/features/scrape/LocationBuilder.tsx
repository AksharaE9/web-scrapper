import React, { useState, useEffect, useRef, useCallback } from "react";
import { useScrapeDraft } from "../../stores/useScrapeDraft";
import { api } from "../../api/client";
import { GeoResolution } from "../../types";
import { Input } from "../../components/ui/Input";
import { BoundaryMap } from "./BoundaryMap";
import { Navigation, Sparkles } from "lucide-react";
import { toast } from "sonner";

// Helper to detect true fuzzy typos (small edit distance) without matching identical or unrelated strings
function isFuzzyTypoMatch(input: string, resolved: string): boolean {
  const normA = input.toLowerCase().replace(/[^a-z0-9]/g, "");
  const normB = resolved.toLowerCase().replace(/[^a-z0-9]/g, "");
  if (!normA || !normB || normA === normB) return false;

  const matrix: number[][] = [];
  for (let i = 0; i <= normA.length; i++) {
    matrix[i] = [i];
  }
  for (let j = 0; j <= normB.length; j++) {
    matrix[0][j] = j;
  }
  for (let i = 1; i <= normA.length; i++) {
    for (let j = 1; j <= normB.length; j++) {
      if (normA[i - 1] === normB[j - 1]) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1
        );
      }
    }
  }
  const dist = matrix[normA.length][normB.length];
  const maxLen = Math.max(normA.length, normB.length);
  return dist <= 3 && (dist / maxLen) < 0.35;
}

interface LocationBuilderProps {
  onGeoResolved: (geo: GeoResolution | null) => void;
  resolvedGeo: GeoResolution | null;
}

export const LocationBuilder: React.FC<LocationBuilderProps> = ({ onGeoResolved, resolvedGeo }) => {
  const {
    location,
    naturalQuery,
    setLocationField,
    setNaturalQuery,
    setIsNaturalMode,
  } = useScrapeDraft();

  const [mode, setMode] = useState<"structured" | "natural" | "coords">("structured");
  const [resolving, setResolving] = useState(false);
  const [resolvedForInput, setResolvedForInput] = useState<string>("");
  const [customLat, setCustomLat] = useState<string>(location.lat ? String(location.lat) : "");
  const [customLon, setCustomLon] = useState<string>(location.lon ? String(location.lon) : "");
  const [customRadius, setCustomRadius] = useState<string>(location.radius_m ? String(location.radius_m) : "1500");

  // In-flight abort controller & sequence number refs to prevent racing stale responses
  const abortControllerRef = useRef<AbortController | null>(null);
  const seqRef = useRef<number>(0);
  const latestCompletedSeqRef = useRef<number>(0);
  const debounceTimerRef = useRef<number | undefined>(undefined);

  // Check if typo was corrected (only for the query that produced the current resolvedGeo)
  const inputLocality = location.locality?.trim() || "";
  const resolvedName = resolvedGeo?.display_name?.split(",")[0]?.trim() || "";
  const isTypoCorrected =
    !resolving &&
    Boolean(
      inputLocality &&
      resolvedName &&
      resolvedForInput.toLowerCase() === inputLocality.toLowerCase() &&
      resolvedGeo?.osm_id?.startsWith("seed/") &&
      isFuzzyTypoMatch(inputLocality, resolvedName)
    );

  // Execute geo preview resolution
  const resolveCurrentInput = useCallback(async () => {
    if (mode === "natural" && !naturalQuery.trim()) {
      onGeoResolved(null);
      setResolvedForInput("");
      return;
    }
    if (mode === "structured" && !location.locality?.trim() && !location.city?.trim()) {
      onGeoResolved(null);
      setResolvedForInput("");
      return;
    }

    if (mode === "coords") {
      const lat = parseFloat(customLat);
      const lon = parseFloat(customLon);
      const radius = parseFloat(customRadius) || 1500;
      if (!isNaN(lat) && !isNaN(lon)) {
        setLocationField("lat" as any, lat as any);
        setLocationField("lon" as any, lon as any);
        setLocationField("radius_m" as any, radius as any);
        const cosLat = Math.max(0.01, Math.cos((lat * Math.PI) / 180));
        const bufDegLat = radius / 111320;
        const bufDegLon = radius / (111320 * cosLat);
        onGeoResolved({
          display_name: `Point (${lat.toFixed(4)}, ${lon.toFixed(4)}) · ${radius}m radius`,
          boundary_kind: "buffered_point",
          boundary_source: "radius_circle",
          polygon_wkt: `POINT(${lon} ${lat})`,
          buffer_m: radius,
          centroid: [lon, lat],
          bbox: [lon - bufDegLon, lat - bufDegLat, lon + bufDegLon, lat + bufDegLat],
          geo_confidence: 1.0,
        });
        setResolvedForInput(`${lat},${lon}`);
        return;
      }
    }

    // Cancel in-flight HTTP request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const reqSeq = ++seqRef.current;
    setResolving(true);
    const queryLocality = location.locality?.trim() || "";

    try {
      const res = await api.previewGeo(
        mode === "natural"
          ? { text: naturalQuery }
          : {
              locality: location.locality,
              city: location.city,
              state: location.state,
              country: location.country || "India",
            },
        controller.signal
      );

      // Sequence guard: Ignore if a newer request already resolved
      if (reqSeq < latestCompletedSeqRef.current) {
        return;
      }
      latestCompletedSeqRef.current = reqSeq;

      if (res && res.centroid) {
        onGeoResolved(res);
        setResolvedForInput(queryLocality);
      } else {
        onGeoResolved(null);
        setResolvedForInput("");
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        return; // Normal cancellation
      }
      onGeoResolved(null);
      setResolvedForInput("");
    } finally {
      if (reqSeq >= seqRef.current) {
        setResolving(false);
      }
    }
  }, [mode, naturalQuery, location.locality, location.city, location.state, location.country, customLat, customLon, customRadius, onGeoResolved, setLocationField]);

  // Single Debounced (400ms) effect watching location input state
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // If input is completely empty, reset immediately
    if (mode === "structured" && !location.locality?.trim() && !location.city?.trim()) {
      onGeoResolved(null);
      setResolving(false);
      return;
    }
    if (mode === "natural" && !naturalQuery.trim()) {
      onGeoResolved(null);
      setResolving(false);
      return;
    }

    debounceTimerRef.current = window.setTimeout(() => {
      resolveCurrentInput();
    }, 200);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [location.locality, location.city, location.state, location.country, naturalQuery, mode, resolveCurrentInput, onGeoResolved]);

  const handleSelectAlternative = (alt: { display_name: string; osm_id: string }) => {
    const parts = alt.display_name.split(",");
    const chosenLocality = parts[0]?.trim() || "";
    const chosenCity = parts[1]?.trim() || location.city;
    setLocationField("locality", chosenLocality);
    if (chosenCity) setLocationField("city", chosenCity);
    toast.success(`Selected area: ${chosenLocality}`);
  };

  return (
    <div className="p-4 rounded-lg border border-border-subtle bg-surface-1 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-accent/10 text-accent flex items-center justify-center font-bold text-xs">
            1
          </div>
          <h3 className="text-sm font-semibold text-text-primary">Where — Target Locality</h3>
        </div>
        <div className="flex items-center gap-1.5 bg-surface-2 p-0.5 rounded-lg text-xs">
          <button
            type="button"
            onClick={() => { setMode("structured"); setIsNaturalMode(false); }}
            className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${mode === "structured" ? "bg-accent text-white font-medium shadow-xs" : "text-text-muted hover:text-text-primary"}`}
          >
            Structured
          </button>
          <button
            type="button"
            onClick={() => { setMode("natural"); setIsNaturalMode(true); }}
            className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${mode === "natural" ? "bg-accent text-white font-medium shadow-xs" : "text-text-muted hover:text-text-primary"}`}
          >
            Natural
          </button>
          <button
            type="button"
            onClick={() => { setMode("coords"); }}
            className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${mode === "coords" ? "bg-accent text-white font-medium shadow-xs" : "text-text-muted hover:text-text-primary"}`}
          >
            Lat/Lon + Radius
          </button>
        </div>
      </div>

      {mode === "natural" && (
        <div className="space-y-2">
          <label className="text-xs font-medium text-text-secondary">Natural Address or Locality Query</label>
          <Input
            id="natural-query"
            value={naturalQuery}
            onChange={(e) => setNaturalQuery(e.target.value)}
            placeholder="e.g. Whitefield, Bengaluru, Karnataka"
            icon={<Navigation className="w-4 h-4" />}
          />
        </div>
      )}

      {mode === "structured" && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label htmlFor="locality" className="text-xs font-medium text-text-secondary block mb-1">Locality *</label>
              <Input
                id="locality"
                aria-label="locality"
                value={location.locality || ""}
                onChange={(e) => setLocationField("locality", e.target.value)}
                placeholder="e.g. Whitefield"
              />
            </div>
            <div>
              <label htmlFor="location-city" className="text-xs font-medium text-text-secondary block mb-1">City</label>
              <Input
                id="location-city"
                aria-label="city"
                value={location.city || ""}
                onChange={(e) => setLocationField("city", e.target.value)}
                placeholder="e.g. Bengaluru"
              />
            </div>
            <div>
              <label htmlFor="location-state" className="text-xs font-medium text-text-secondary block mb-1">State</label>
              <Input
                id="location-state"
                aria-label="state"
                value={location.state || ""}
                onChange={(e) => setLocationField("state", e.target.value)}
                placeholder="e.g. Karnataka"
              />
            </div>
            <div>
              <label htmlFor="location-country" className="text-xs font-medium text-text-secondary block mb-1">Country</label>
              <Input
                id="location-country"
                aria-label="country"
                value={location.country || ""}
                onChange={(e) => setLocationField("country", e.target.value)}
                placeholder="e.g. India"
              />
            </div>
          </div>

          {/* Typo Correction Banner */}
          {isTypoCorrected && (
            <div className="p-2.5 rounded-lg border border-accent/30 bg-accent/5 flex items-center justify-between text-xs text-text-primary">
              <div className="flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-accent shrink-0" />
                <span>
                  Showing results for <strong className="text-accent font-semibold">{resolvedName}</strong> (corrected from "{inputLocality}")
                </span>
              </div>
              <button
                type="button"
                onClick={() => setLocationField("locality", resolvedName)}
                className="text-[11px] font-medium text-accent hover:underline flex items-center gap-1 cursor-pointer"
              >
                Accept & Update Field
              </button>
            </div>
          )}
        </div>
      )}

      {mode === "coords" && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-xs font-medium text-text-secondary block mb-1">Latitude</label>
            <Input
              type="number"
              step="0.0001"
              value={customLat}
              onChange={(e) => setCustomLat(e.target.value)}
              placeholder="e.g. 12.9352"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-text-secondary block mb-1">Longitude</label>
            <Input
              type="number"
              step="0.0001"
              value={customLon}
              onChange={(e) => setCustomLon(e.target.value)}
              placeholder="e.g. 77.6245"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-text-secondary block mb-1">Radius (meters)</label>
            <Input
              type="number"
              step="100"
              value={customRadius}
              onChange={(e) => setCustomRadius(e.target.value)}
              placeholder="e.g. 1500"
            />
          </div>
        </div>
      )}

      {/* Map Preview with 7-tier feedback and alternative picker */}
      <BoundaryMap
        geo={resolvedGeo}
        resolving={resolving}
        resolvingTarget={mode === "natural" ? naturalQuery : location.locality || location.city}
        onSelectAlternative={handleSelectAlternative}
      />
    </div>
  );
};

