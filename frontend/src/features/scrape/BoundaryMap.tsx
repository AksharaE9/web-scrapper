import React, { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MLMap, LngLatBoundsLike } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import circle from "@turf/circle";
import { GeoResolution, BoundarySource } from "../../types";
import { MapPin, AlertCircle, Layers, Loader2, Sparkles, HelpCircle, CheckCircle2 } from "lucide-react";
import { Badge } from "../../components/ui/Badge";

export const CARTO_DARK_STYLE: any = {
  version: 8,
  sources: {
    "carto-dark": {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://d.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attributions">CARTO</a>',
    },
  },
  layers: [
    {
      id: "carto-dark-layer",
      type: "raster",
      source: "carto-dark",
      minzoom: 0,
      maxzoom: 20,
    },
  ],
};

const STYLE_SPEC = (import.meta as any).env?.VITE_BASEMAP_STYLE_URL || CARTO_DARK_STYLE;

interface BoundaryMapProps {
  geo?: GeoResolution | null;
  resolving?: boolean;
  resolvingTarget?: string;
  className?: string;
  onSelectAlternative?: (alt: { display_name: string; osm_id: string }) => void;
}

interface ProvenanceMeta {
  source: BoundarySource;
  chip: string;
  variant: "good" | "warning" | "info";
  stroke: "solid" | "dashed";
  colorClass: string;
  tooltip: string;
  ariaDescription: string;
}

export function getProvenanceMeta(geo: GeoResolution): ProvenanceMeta {
  const source: BoundarySource =
    geo.boundary_source ??
    (geo.boundary_kind === "admin_polygon"
      ? "osm_relation"
      : geo.boundary_kind === "division_polygon"
      ? "overture_division_area"
      : "radius_circle");

  const radiusKm = ((geo.buffer_m || 1500) / 1000).toFixed(1);

  switch (source) {
    case "osm_relation":
      return {
        source,
        chip: "Exact boundary",
        variant: "good",
        stroke: "solid",
        colorClass: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
        tooltip: geo.osm_id
          ? `OpenStreetMap administrative relation #${geo.osm_id}`
          : "OpenStreetMap administrative relation",
        ariaDescription: `Showing exact OpenStreetMap administrative boundary for ${geo.display_name}.`,
      };
    case "osm_way":
      return {
        source,
        chip: "Exact boundary",
        variant: "good",
        stroke: "solid",
        colorClass: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
        tooltip: geo.osm_id
          ? `OpenStreetMap area #${geo.osm_id}`
          : "OpenStreetMap area",
        ariaDescription: `Showing exact OpenStreetMap area for ${geo.display_name}.`,
      };
    case "overture_division_area":
      return {
        source,
        chip: "Exact boundary",
        variant: "good",
        stroke: "solid",
        colorClass: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
        tooltip: geo.overture_division_id
          ? `Overture Maps division area #${geo.overture_division_id}`
          : "Overture Maps division area (locality)",
        ariaDescription: `Showing exact Overture Maps division area for ${geo.display_name}.`,
      };
    case "poi_concave_hull":
      return {
        source,
        chip: "Estimated area",
        variant: "warning",
        stroke: "dashed",
        colorClass: "bg-amber-500/10 text-amber-400 border-amber-500/30",
        tooltip: "Estimated from mapped businesses in this locality",
        ariaDescription: `Showing estimated area for ${geo.display_name}, derived from mapped businesses.`,
      };
    case "h3_cover":
      return {
        source,
        chip: "Estimated area",
        variant: "warning",
        stroke: "dashed",
        colorClass: "bg-amber-500/10 text-amber-400 border-amber-500/30",
        tooltip: "Approximate hex-cell cover, ~460 m resolution",
        ariaDescription: `Showing approximate hex-cell cover for ${geo.display_name}.`,
      };
    case "nominatim_bbox":
      return {
        source,
        chip: "Search box only",
        variant: "warning",
        stroke: "dashed",
        colorClass: "bg-amber-500/10 text-amber-400 border-amber-500/30",
        tooltip: "A bounding rectangle, not a real boundary",
        ariaDescription: `Showing bounding search box for ${geo.display_name}.`,
      };
    case "radius_circle":
    default:
      return {
        source: "radius_circle",
        chip: `~${radiusKm} km radius`,
        variant: "warning",
        stroke: "dashed",
        colorClass: "bg-amber-500/10 text-amber-400 border-amber-500/30",
        tooltip: `No boundary exists for this place. Searching within ${radiusKm} km of the centre point.`,
        ariaDescription: `Showing approximate radius circle of ${radiusKm} km for ${geo.display_name}.`,
      };
  }
}

function resolveGeoJSON(geo: GeoResolution): any {
  if (
    geo.boundary_geojson &&
    geo.boundary_geojson.type &&
    (geo.boundary_geojson.type === "Polygon" ||
      geo.boundary_geojson.type === "MultiPolygon" ||
      geo.boundary_geojson.type === "Feature" ||
      geo.boundary_geojson.type === "FeatureCollection")
  ) {
    return geo.boundary_geojson;
  }

  // Fallback: geodesic circle using @turf/circle
  const radiusKm = (geo.buffer_m || 1500) / 1000;
  return circle(geo.centroid, radiusKm, { steps: 64, units: "kilometers" });
}

function renderBoundary(map: MLMap, geo: GeoResolution) {
  const exact =
    geo.boundary_source === "osm_relation" ||
    geo.boundary_source === "osm_way" ||
    geo.boundary_source === "overture_division_area" ||
    (!geo.boundary_source &&
      (geo.boundary_kind === "admin_polygon" ||
        geo.boundary_kind === "division_polygon"));

  const geojsonData = resolveGeoJSON(geo);

  if (!map.getSource("boundary")) {
    map.addSource("boundary", {
      type: "geojson",
      data: geojsonData,
    });

    const firstSymbol = map
      .getStyle()
      ?.layers?.find((l) => l.type === "symbol")?.id;

    map.addLayer(
      {
        id: "boundary-fill",
        type: "fill",
        source: "boundary",
        paint: {
          "fill-color": "#6366f1",
          "fill-opacity": exact ? 0.25 : 0.12,
        },
      },
      firstSymbol
    );

    map.addLayer(
      {
        id: "boundary-line",
        type: "line",
        source: "boundary",
        paint: {
          "line-color": exact ? "#6366f1" : "#fbbf24",
          "line-width": 2.5,
          "line-dasharray": exact ? [1] : [2, 2],
        },
      },
      firstSymbol
    );
  } else {
    (map.getSource("boundary") as maplibregl.GeoJSONSource).setData(
      geojsonData
    );
    if (map.getLayer("boundary-fill")) {
      map.setPaintProperty(
        "boundary-fill",
        "fill-opacity",
        exact ? 0.25 : 0.12
      );
    }
    if (map.getLayer("boundary-line")) {
      map.setPaintProperty(
        "boundary-line",
        "line-dasharray",
        exact ? [1] : [2, 2]
      );
      map.setPaintProperty(
        "boundary-line",
        "line-color",
        exact ? "#6366f1" : "#fbbf24"
      );
    }
  }
}

function MapUnavailable({
  message,
  geo,
}: {
  message: string | null;
  geo?: GeoResolution | null;
}) {
  return (
    <div
      data-testid="map-unavailable-card"
      className="w-full h-full p-4 flex flex-col justify-center bg-surface-2 text-xs font-mono rounded-2xl border border-slate-800"
    >
      <div className="flex items-center gap-1.5 text-amber-500 font-semibold mb-2">
        <AlertCircle className="w-4 h-4" /> WebGL Unavailable / Non-Map Fallback
      </div>
      <p className="text-[11px] text-text-muted mb-2">
        {message || "Basemap rendering is disabled or unsupported in this environment."}
      </p>
      {geo && (
        <div className="space-y-1 text-text-secondary bg-surface-1/60 p-2.5 rounded-lg border border-border-subtle">
          <div><strong className="text-text-primary">Place:</strong> {geo.display_name}</div>
          <div><strong className="text-text-primary">Centroid:</strong> {geo.centroid[1].toFixed(5)}, {geo.centroid[0].toFixed(5)}</div>
          <div><strong className="text-text-primary">BBox:</strong> [{geo.bbox.map((b) => b.toFixed(4)).join(", ")}]</div>
          <div>
            <strong className="text-text-primary">Provenance:</strong> {geo.boundary_source || geo.boundary_kind} ({(geo.geo_confidence * 100).toFixed(0)}% confidence)
          </div>
        </div>
      )}
    </div>
  );
}

export const BoundaryMap: React.FC<BoundaryMapProps> = React.memo(
  ({
    geo,
    resolving = false,
    resolvingTarget = "",
    className = "",
    onSelectAlternative,
  }) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const mapRef = useRef<MLMap | null>(null);
    const markerRef = useRef<maplibregl.Marker | null>(null);
    const [status, setStatus] = useState<"init" | "ready" | "error">("init");
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const [showDelayedSpinner, setShowDelayedSpinner] = useState(false);

    // 200ms delay before showing spinner so fast (<200ms) resolves never flash
    useEffect(() => {
      let timer: number | undefined;
      if (resolving) {
        timer = window.setTimeout(() => setShowDelayedSpinner(true), 200);
      } else {
        setShowDelayedSpinner(false);
      }
      return () => {
        if (timer) clearTimeout(timer);
      };
    }, [resolving]);

    // 1. CREATE ONCE. StrictMode runs setup->cleanup->setup.
    useEffect(() => {
      if (mapRef.current) return;
      const el = containerRef.current;
      if (!el) return;

      const rect = el.getBoundingClientRect();
      const isJsdom = typeof navigator !== "undefined" && navigator.userAgent?.includes("jsdom");
      if ((rect.height === 0 || rect.width === 0) && !isJsdom) {
        console.error(
          `[BoundaryMap] container is ${rect.width}×${rect.height}. ` +
            `MapLibre will render nothing and will not warn you. ` +
            `Give the container an explicit height.`
        );
      }

      try {
        const map = new maplibregl.Map({
          container: el,
          style: STYLE_SPEC,
          center: geo?.centroid || [78.4867, 17.385],
          zoom: geo ? 13 : 11,
          fadeDuration: 0,
          maxZoom: 18,
          attributionControl: { compact: true },
        });

        mapRef.current = map;

        map.on("error", (e: any) => {
          console.error("[maplibre]", e.error?.message, e.error);
          const errObj = e.error || e;
          const isGpu =
            (typeof (maplibregl as any).GPUInitializationError === "function" &&
              errObj instanceof (maplibregl as any).GPUInitializationError) ||
            errObj?.name === "GPUInitializationError" ||
            /webgl|gpu/i.test(errObj?.message || "");

          if (isGpu) {
            setStatus("error");
            setErrorMsg("Your browser or GPU could not start WebGL.");
          }
        });

        map.on("load", () => {
          setStatus("ready");
          if (geo) {
            renderBoundary(map, geo);
            if (geo.bbox && Array.isArray(geo.bbox) && geo.bbox.length === 4) {
              const bounds: LngLatBoundsLike = [
                [geo.bbox[0], geo.bbox[1]],
                [geo.bbox[2], geo.bbox[3]],
              ];
              map.fitBounds(bounds, {
                padding: { top: 48, bottom: 40, left: 40, right: 40 },
                maxZoom: 15,
                duration: 0,
              });
            } else if (geo.centroid) {
              map.setCenter(geo.centroid);
              map.setZoom(13);
            }
          }
        });

        map.addControl(
          new maplibregl.NavigationControl({ showCompass: false }),
          "top-right"
        );
        map.addControl(
          new maplibregl.ScaleControl({ unit: "metric" }),
          "bottom-left"
        );
      } catch (err: any) {
        const isGpu =
          (typeof (maplibregl as any).GPUInitializationError === "function" &&
            err instanceof (maplibregl as any).GPUInitializationError) ||
          err?.name === "GPUInitializationError" ||
          /webgl|gpu/i.test(err?.message || "");

        if (isGpu) {
          setStatus("error");
          setErrorMsg("WebGL is unavailable in this browser.");
        } else {
          setStatus("error");
          setErrorMsg(String(err));
        }
      }

      return () => {
        mapRef.current?.remove();
        mapRef.current = null;
      };
    }, []);

    // 2. RESIZE. The panel lives in a conditionally-rendered tab.
    useEffect(() => {
      const el = containerRef.current;
      if (!el) return;
      const ro = new ResizeObserver(() => mapRef.current?.resize());
      ro.observe(el);
      return () => ro.disconnect();
    }, []);

    // 3. DATA. Mutate the source; never re-add layers.
    useEffect(() => {
      const map = mapRef.current;
      if (!map || status !== "ready") return;

      if (!geo) {
        const src = map.getSource("boundary") as
          | maplibregl.GeoJSONSource
          | undefined;
        if (src) {
          src.setData({ type: "FeatureCollection", features: [] });
        }
        if (markerRef.current) {
          markerRef.current.remove();
          markerRef.current = null;
        }
        return;
      }

      // Marker at centroid
      if (!markerRef.current) {
        markerRef.current = new maplibregl.Marker({ color: "#6366f1" })
          .setLngLat(geo.centroid)
          .addTo(map);
      } else {
        markerRef.current.setLngLat(geo.centroid);
      }

      renderBoundary(map, geo);

      // Fit bounds safely
      if (geo.bbox && Array.isArray(geo.bbox) && geo.bbox.length === 4) {
        const bounds: LngLatBoundsLike = [
          [geo.bbox[0], geo.bbox[1]],
          [geo.bbox[2], geo.bbox[3]],
        ];

        const prefersReducedMotion =
          typeof window !== "undefined" &&
          typeof window.matchMedia === "function" &&
          window.matchMedia("(prefers-reduced-motion: reduce)")?.matches;

        map.fitBounds(bounds, {
          padding: { top: 48, bottom: 40, left: 40, right: 40 },
          maxZoom: 15,
          duration: prefersReducedMotion ? 0 : 500,
        });
      } else if (geo.centroid) {
        map.flyTo({ center: geo.centroid, zoom: 12 });
      }
    }, [geo, status]);

    const provenance = geo ? getProvenanceMeta(geo) : null;

    if (!geo && !resolving) {
      return (
        <div
          data-testid="boundary-map-empty"
          className={`w-full rounded-2xl border border-dashed border-border-strong bg-surface-2/40 flex flex-col items-center justify-center p-6 text-center ${
            className || "h-72"
          }`}
          style={{ minHeight: 280 }}
        >
          <MapPin className="w-6 h-6 text-text-muted mb-1.5" />
          <span className="text-xs font-medium text-text-muted">
            Enter location to resolve target geographic boundary
          </span>
          <span className="text-[10px] text-text-muted/70 mt-0.5">
            Vector basemap with 7-tier boundary provenance classification
          </span>
        </div>
      );
    }

    return (
      <div className="space-y-2">
        {/* Screen-reader accessible live region */}
        <div
          aria-live="polite"
          className="sr-only"
          data-testid="boundary-aria-announcement"
        >
          {provenance ? provenance.ariaDescription : "Resolving boundary..."}
        </div>

        <div className={`relative w-full rounded-2xl overflow-hidden border border-slate-800 bg-surface-2 ${className}`}>
          {/* Sized Container for MapLibre */}
          <div
            ref={containerRef}
            data-testid="boundary-map-container"
            className="w-full"
            style={{ height: 320, minHeight: 320 }}
          />

          {/* WebGL Error / Fallback State */}
          {status === "error" && (
            <div className="absolute inset-0 z-30">
              <MapUnavailable message={errorMsg} geo={geo} />
            </div>
          )}

          {/* Delayed Loading Overlay */}
          {resolving && showDelayedSpinner && (
            <div
              data-testid="boundary-resolving-overlay"
              className="absolute inset-0 z-20 bg-surface-1/80 backdrop-blur-xs flex flex-col items-center justify-center p-4 text-center animate-in fade-in duration-200"
            >
              <Loader2 className="w-6 h-6 text-accent animate-spin mb-1.5" />
              <span className="text-xs font-medium text-text-primary">
                {resolvingTarget
                  ? `Finding boundary for "${resolvingTarget}"...`
                  : "Resolving target geographic boundary..."}
              </span>
              <span className="text-[10px] text-text-muted mt-0.5">
                Checking division geometries & offline caches
              </span>
            </div>
          )}

          {/* Provenance Chip Overlay */}
          {provenance && (
            <div className="absolute top-3 left-3 z-10 flex items-center gap-2 pointer-events-none">
              <span
                data-testid="boundary-kind"
                title={provenance.tooltip}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border shadow-lg backdrop-blur-md pointer-events-auto cursor-help ${provenance.colorClass}`}
              >
                {provenance.variant === "good" ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : (
                  <Layers className="w-3.5 h-3.5" />
                )}
                <span>{provenance.chip}</span>
                <HelpCircle className="w-3 h-3 opacity-60 ml-0.5" />
              </span>
            </div>
          )}
        </div>

        {geo && (
          <>
            <div className="flex items-center justify-between text-[11px] text-text-muted px-1 font-mono">
              <span
                data-testid="boundary-summary"
                className="truncate max-w-[70%] font-medium text-text-secondary"
                title={geo.display_name}
              >
                {geo.display_name}
              </span>
              <span className="text-text-muted">
                Confidence: {(geo.geo_confidence * 100).toFixed(0)}%
              </span>
            </div>

            {/* Alternatives Disambiguation Pills */}
            {geo.alternatives && geo.alternatives.length > 0 && (
              <div className="p-2.5 rounded-lg border border-border-subtle bg-surface-2/70 text-xs space-y-1.5">
                <div className="text-[11px] font-semibold text-text-secondary flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-accent" /> Did you mean one
                  of these specific areas?
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {geo.alternatives.slice(0, 5).map((alt, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => onSelectAlternative?.(alt)}
                      className="px-2 py-0.5 rounded bg-surface-1 border border-border-subtle hover:border-accent text-[11px] text-text-primary hover:text-accent transition-colors truncate max-w-[280px] cursor-pointer"
                      title={alt.display_name}
                    >
                      {alt.display_name.split(",").slice(0, 2).join(",")}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    );
  }
);
BoundaryMap.displayName = "BoundaryMap";
