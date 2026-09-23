"use client";
/**
 * Where scans were taken — PostGIS-clustered points, never raw scans.
 * Client-only (leaflet needs `window`); mounted via next/dynamic with ssr:false
 * from web/app/page.tsx.
 */
import "leaflet/dist/leaflet.css";
import { useCallback, useEffect, useRef, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMapEvents } from "react-leaflet";
import type { LatLngBounds } from "leaflet";
import { dashboardApi, type HeatmapCluster } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

// Verdict tokens — the only saturated colour against the muted basemap.
const SEVERITY_COLOR: Record<HeatmapCluster["severity"], string> = {
  FAIL: "#B3261E",
  PENDING: "#B5730B",
  PASS: "#1E7A4D",
};
const SEVERITY_LABEL: Record<HeatmapCluster["severity"], string> = {
  FAIL: "Non-compliant",
  PENDING: "Pending review",
  PASS: "Compliant",
};

const INDIA_CENTER: [number, number] = [22.9734, 78.6569];
const DEFAULT_ZOOM = 5;

function boundsToBbox(bounds: LatLngBounds): string {
  const sw = bounds.getSouthWest();
  const ne = bounds.getNorthEast();
  return `${sw.lat},${sw.lng},${ne.lat},${ne.lng}`;
}

// sqrt scale so marker *area* (not radius) is roughly proportional to count.
function clusterRadius(count: number): number {
  return Math.min(28, 6 + Math.sqrt(count) * 3);
}

function ViewportBridge({
  onViewportChange,
}: {
  onViewportChange: (zoom: number, bbox: string) => void;
}) {
  const map = useMapEvents({
    moveend: () => onViewportChange(map.getZoom(), boundsToBbox(map.getBounds())),
    zoomend: () => onViewportChange(map.getZoom(), boundsToBbox(map.getBounds())),
  });
  useEffect(() => {
    onViewportChange(map.getZoom(), boundsToBbox(map.getBounds()));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

export function Heatmap() {
  const [clusters, setClusters] = useState<HeatmapCluster[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastViewport = useRef<{ zoom: number; bbox: string } | null>(null);

  const load = useCallback(async (zoom: number, bbox: string) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await dashboardApi.heatmap({ zoom, bbox });
      setClusters(data.clusters);
    } catch (err) {
      setError(apiErrorMessage(err, "This area could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchClusters = useCallback(
    (zoom: number, bbox: string) => {
      lastViewport.current = { zoom, bbox };
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => load(zoom, bbox), 300);
    },
    [load]
  );

  const retry = useCallback(() => {
    const viewport = lastViewport.current;
    if (viewport) load(viewport.zoom, viewport.bbox);
  }, [load]);

  return (
    <div>
      <div className="relative" style={{ height: 420 }}>
        <MapContainer
          center={INDIA_CENTER}
          zoom={DEFAULT_ZOOM}
          style={{ height: "100%", width: "100%" }}
          aria-label="National compliance heatmap"
        >
          {/* Muted basemap so the verdict clusters are the only saturated colour. */}
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/attributions">CARTO</a> &copy; OpenStreetMap contributors'
          />
          <ViewportBridge onViewportChange={fetchClusters} />
          {clusters.map((c, i) => (
            <CircleMarker
              key={`${c.lat.toFixed(4)}-${c.lng.toFixed(4)}-${i}`}
              center={[c.lat, c.lng]}
              radius={clusterRadius(c.count)}
              pathOptions={{
                color: SEVERITY_COLOR[c.severity],
                fillColor: SEVERITY_COLOR[c.severity],
                fillOpacity: 0.65,
                weight: 1,
              }}
            >
              <Tooltip direction="top">
                <span className="font-mono text-xs">
                  {c.count} scan{c.count === 1 ? "" : "s"} — {c.pass_count} pass /{" "}
                  {c.fail_count} fail / {c.pending_count} pending
                </span>
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
        {loading && (
          <span className="absolute top-2 right-2 z-[1000] status-chip bg-paper-000 text-ink-600 border-ink-600/20">
            Loading…
          </span>
        )}
        {error && (
          <div
            role="alert"
            className="absolute right-2 top-2 z-[1000] flex items-center gap-2 rounded-card border border-verdict-fail/30 bg-paper-000 px-2.5 py-1.5 shadow-sm"
          >
            <span className="font-body text-xs text-verdict-fail">{error}</span>
            <button
              type="button"
              onClick={retry}
              className="rounded border border-verdict-fail/40 px-2 py-0.5 font-body text-xs font-semibold text-verdict-fail hover:bg-verdict-fail/10"
            >
              Retry
            </button>
          </div>
        )}
      </div>
      <div className="flex items-center gap-4 px-4 py-2 border-t border-ink-900/10">
        {(Object.keys(SEVERITY_LABEL) as HeatmapCluster["severity"][]).map((severity) => (
          <span key={severity} className="flex items-center gap-1.5 font-mono text-xs text-ink-600">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: SEVERITY_COLOR[severity] }}
              aria-hidden
            />
            {SEVERITY_LABEL[severity]}
          </span>
        ))}
      </div>
    </div>
  );
}
