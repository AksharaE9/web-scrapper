import React, { useEffect, useRef } from "react";
import { GeoResolution } from "../../types";
import { Compass } from "lucide-react";

interface MapPreviewProps {
  geo: GeoResolution | null;
  isLoading?: boolean;
}

export const MapPreview: React.FC<MapPreviewProps> = ({ geo }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Draw dark stylized map grid
    ctx.fillStyle = "#090d16";
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
    ctx.lineWidth = 1;
    const gridSize = 24;
    for (let x = 0; x < width; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    if (!geo) {
      // Empty state prompt
      ctx.fillStyle = "rgba(148, 163, 184, 0.4)";
      ctx.font = "12px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("Enter a location to resolve boundary polygon", width / 2, height / 2);
      return;
    }

    // Draw polygon / boundary circle
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) / 3.2;

    // Outer glow
    const grad = ctx.createRadialGradient(centerX, centerY, 5, centerX, centerY, radius);
    grad.addColorStop(0, "rgba(99, 102, 241, 0.25)");
    grad.addColorStop(1, "rgba(99, 102, 241, 0.02)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.fill();

    // Boundary stroke
    ctx.strokeStyle = "#6366f1";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Centroid marker
    ctx.fillStyle = "#38bdf8";
    ctx.beginPath();
    ctx.arc(centerX, centerY, 5, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(centerX, centerY, 7, 0, Math.PI * 2);
    ctx.stroke();

    // Coordinates label
    ctx.fillStyle = "#94a3b8";
    ctx.font = "10px JetBrains Mono, monospace";
    ctx.textAlign = "center";
    ctx.fillText(
      `Centroid: [${geo.centroid[0].toFixed(4)}, ${geo.centroid[1].toFixed(4)}]`,
      centerX,
      height - 12
    );
  }, [geo]);

  return (
    <div className="relative rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden">
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2 bg-slate-900/80 backdrop-blur-md px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300">
        <Compass className="w-3.5 h-3.5 text-indigo-400" />
        <span>OpenFreeMap / Nominatim Geo Preview</span>
      </div>

      {geo && (
        <div className="absolute top-3 right-3 z-10 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-lg text-[11px] font-mono text-emerald-400">
          Confidence: {(geo.geo_confidence * 100).toFixed(0)}%
        </div>
      )}

      <canvas
        ref={canvasRef}
        width={480}
        height={260}
        className="w-full h-56 object-cover"
      />
    </div>
  );
};
